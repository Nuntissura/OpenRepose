"""Intake storage-state, lifecycle events, and file-op outbox (WP-I4-001).

Spec: `.gov/spec/openrepose_intake_v0_1.md`
      "I4 Scale + DB Hardening Extension":
        - Storage State
        - Lifecycle Events (append-only)
        - File-Operation Outbox
        - Recovery / Audit Command

The DB and the filesystem cannot share a transaction manager. This module
is the contract bridge: every status transition that needs a filesystem
effect (move into a bucket, delete on wholesale-reject) inserts a
`library_file_ops` row in the same transaction as the status change.
A separate worker -- or the dispatcher inline, bounded by attempt cap --
executes the filesystem op and updates the row.

Failure leaves a retryable DB state rather than a silent stale path:
`library_outputs.storage_state` becomes `'file_op_failed'` and the
`library_file_ops` row carries the error and `attempt_count`.

Helpers in this module are transaction-passive: callers own commit and
rollback. (See `WP-I4-001 Definition of Done` "Touched intake/library
DB helpers no longer commit internally".)
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg


# Rule-id-named so dispatcher citations and audits resolve cleanly.
INTAKE_006_STORAGE_STATES: tuple[str, ...] = (
    "raw",
    "diagnostic",
    "rejected",
    "soft_accepted",
    "accepted",
    "missing",
    "file_op_failed",
)

# Maps semantic status -> happy-path storage_state. Recovery diverges
# during retry; audit reports any (status, storage_state) outside this
# map (excluding 'missing' / 'file_op_failed' which are explicit
# divergence markers).
STATUS_TO_STORAGE_STATE: dict[str, str] = {
    "pending":       "raw",
    "triaging":      "raw",
    "soft_accepted": "soft_accepted",
    "promoted":      "accepted",
    "rejected":      "rejected",
    "diagnostic":    "diagnostic",
    "abandoned":     "rejected",
}

VALID_EVENT_TYPES: tuple[str, ...] = (
    "register",
    "soft_accept",
    "reject",
    "finalize",
    "auto_route",
    "reroute",
    "wholesale_reject",
    "storage_transition",
    "file_op_failed",
    "recover",
)

VALID_FILE_OP_TYPES: tuple[str, ...] = ("move", "delete")
VALID_FILE_OP_STATUSES: tuple[str, ...] = (
    "pending",
    "in_flight",
    "done",
    "failed",
)


class StorageError(ValueError):
    """Raised when a storage operation receives malformed input."""


# ---------------------------------------------------------------------------
# Lifecycle event recording (transaction-passive)
# ---------------------------------------------------------------------------


def record_event(
    conn: "psycopg.Connection[object]",
    *,
    output_id: UUID | str,
    event_type: str,
    actor: str,
    from_status: str | None = None,
    to_status: str | None = None,
    from_storage_state: str | None = None,
    to_storage_state: str | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    """Append-only insert into `library_output_events`. Returns the new
    event id. Caller owns commit.
    """
    if event_type not in VALID_EVENT_TYPES:
        raise StorageError(
            f"event_type must be one of {VALID_EVENT_TYPES}; got {event_type!r}"
        )
    if not actor:
        raise StorageError("actor is required (agent_id, operator slug, or 'system')")
    from psycopg.types.json import Jsonb

    payload_param = Jsonb(payload if payload is not None else {})
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_output_events "
            "(output_id, event_type, from_status, to_status, "
            " from_storage_state, to_storage_state, actor, payload_json) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id",
            (
                str(output_id),
                event_type,
                from_status,
                to_status,
                from_storage_state,
                to_storage_state,
                actor,
                payload_param,
            ),
        )
        return str(cur.fetchone()[0])


# ---------------------------------------------------------------------------
# storage_state mutation (transaction-passive)
# ---------------------------------------------------------------------------


def set_storage_state(
    conn: "psycopg.Connection[object]",
    *,
    output_id: UUID | str,
    new_storage_state: str,
) -> str | None:
    """Update `library_outputs.storage_state` to `new_storage_state`.

    Returns the previous storage_state for callers that need to record
    a `storage_transition` event (None when the row is missing).
    Caller owns commit. Raises `StorageError` if `new_storage_state`
    is not a known enum value.
    """
    if new_storage_state not in INTAKE_006_STORAGE_STATES:
        raise StorageError(
            f"storage_state must be one of {INTAKE_006_STORAGE_STATES}; "
            f"got {new_storage_state!r}"
        )
    with conn.cursor() as cur:
        cur.execute(
            "SELECT storage_state FROM library_outputs WHERE id = %s",
            (str(output_id),),
        )
        prev_row = cur.fetchone()
        if prev_row is None:
            return None
        previous = prev_row[0]
        cur.execute(
            "UPDATE library_outputs SET storage_state = %s WHERE id = %s",
            (new_storage_state, str(output_id)),
        )
    return previous


# ---------------------------------------------------------------------------
# File-operation outbox (transaction-passive)
# ---------------------------------------------------------------------------


def enqueue_file_op(
    conn: "psycopg.Connection[object]",
    *,
    output_id: UUID | str,
    op_type: str,
    src_path: str,
    dst_path: str | None = None,
) -> str:
    """Insert a `library_file_ops` row at status='pending'. Returns the
    new file_op id. Caller owns commit.

    `op_type='move'` requires `dst_path`. `op_type='delete'` accepts
    `dst_path=None` (the row's `library_file_ops_dst_path_required`
    CHECK enforces both).
    """
    if op_type not in VALID_FILE_OP_TYPES:
        raise StorageError(
            f"op_type must be one of {VALID_FILE_OP_TYPES}; got {op_type!r}"
        )
    if op_type == "move" and not dst_path:
        raise StorageError("dst_path required for op_type='move'")
    if not src_path:
        raise StorageError("src_path is required")
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_file_ops "
            "(output_id, op_type, src_path, dst_path, status, attempt_count) "
            "VALUES (%s, %s, %s, %s, 'pending', 0) "
            "RETURNING id",
            (str(output_id), op_type, src_path, dst_path),
        )
        return str(cur.fetchone()[0])


def claim_pending_file_ops(
    conn: "psycopg.Connection[object]",
    *,
    claimed_by: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Claim up to `limit` pending file-op rows for execution.

    Uses ``SELECT ... FOR UPDATE SKIP LOCKED`` so two workers see
    disjoint claim sets without blocking. Each claimed row is updated
    to status='in_flight' + claimed_by/at and returned. Caller owns
    commit.
    """
    if limit < 1:
        raise StorageError("limit must be >= 1")
    if not claimed_by:
        raise StorageError("claimed_by is required")
    claimed: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, output_id, op_type, src_path, dst_path, attempt_count "
            "FROM library_file_ops "
            "WHERE status = 'pending' "
            "ORDER BY created_at ASC "
            "FOR UPDATE SKIP LOCKED "
            "LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
        for row in rows:
            file_op_id = row[0]
            cur.execute(
                "UPDATE library_file_ops "
                "SET status = 'in_flight', claimed_at = NOW(), claimed_by = %s "
                "WHERE id = %s",
                (claimed_by, file_op_id),
            )
            claimed.append(
                {
                    "file_op_id": str(file_op_id),
                    "output_id": str(row[1]),
                    "op_type": row[2],
                    "src_path": row[3],
                    "dst_path": row[4],
                    "attempt_count": int(row[5]),
                }
            )
    return claimed


def complete_file_op(
    conn: "psycopg.Connection[object]",
    *,
    file_op_id: UUID | str,
    success: bool,
    error_message: str | None = None,
) -> None:
    """Finalize a claimed file-op row.

    On success: status='done', completed_at set, attempt_count++.
    On failure: status='failed', last_error set, attempt_count++.
    Caller owns commit.
    """
    new_status = "done" if success else "failed"
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE library_file_ops "
            "SET status = %s, "
            "    last_error = COALESCE(%s, last_error), "
            "    attempt_count = attempt_count + 1, "
            "    completed_at = CASE WHEN %s THEN NOW() ELSE completed_at END "
            "WHERE id = %s",
            (new_status, error_message, success, str(file_op_id)),
        )


def execute_file_op(
    *,
    op_type: str,
    src_path: str,
    dst_path: str | None,
    outputs_root: Path,
) -> tuple[bool, str | None]:
    """Perform the on-disk operation. Returns (success, error_message).

    Path resolution is hardened: src and dst MUST resolve under
    `outputs_root` -- a producer-supplied path that escapes the root is
    a hard reject (returns (False, 'path_escape')).
    """
    try:
        src = (outputs_root / src_path).resolve()
        src.relative_to(outputs_root.resolve())
    except (ValueError, OSError):
        return False, "path_escape: src not under outputs_root"

    if op_type == "delete":
        try:
            if src.exists():
                src.unlink()
            return True, None
        except OSError as e:
            return False, f"delete_failed: {e}"

    # op_type == 'move'
    if not dst_path:
        return False, "move_missing_dst_path"
    try:
        dst = (outputs_root / dst_path).resolve()
        dst.relative_to(outputs_root.resolve())
    except (ValueError, OSError):
        return False, "path_escape: dst not under outputs_root"
    if not src.exists():
        return False, "src_missing"
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True, None
    except OSError as e:
        return False, f"move_failed: {e}"


def process_pending_file_ops(
    conn: "psycopg.Connection[object]",
    *,
    outputs_root: Path | None,
    claimed_by: str,
    limit: int = 20,
) -> dict[str, Any]:
    """High-level helper: claim -> execute -> complete in one
    transaction per outcome.

    No-op when `outputs_root` is None (test/dispatch paths that do not
    enable filesystem effects). Returns counters of claimed / done /
    failed for telemetry.
    """
    if outputs_root is None:
        return {"claimed": 0, "done": 0, "failed": 0}
    claimed = claim_pending_file_ops(conn, claimed_by=claimed_by, limit=limit)
    if not claimed:
        return {"claimed": 0, "done": 0, "failed": 0}
    conn.commit()  # release the FOR UPDATE locks; later updates are
                   # per-row outside the original lock window.

    done = 0
    failed = 0
    for op in claimed:
        success, error_message = execute_file_op(
            op_type=op["op_type"],
            src_path=op["src_path"],
            dst_path=op["dst_path"],
            outputs_root=outputs_root,
        )
        complete_file_op(
            conn,
            file_op_id=op["file_op_id"],
            success=success,
            error_message=error_message,
        )
        if success:
            done += 1
            # On a successful move, point library_outputs.file_path at
            # the new on-disk location so future reads are correct.
            if op["op_type"] == "move" and op["dst_path"]:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE library_outputs SET file_path = %s "
                        "WHERE id = %s",
                        (op["dst_path"], op["output_id"]),
                    )
        else:
            failed += 1
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE library_outputs SET storage_state = 'file_op_failed' "
                    "WHERE id = %s",
                    (op["output_id"],),
                )
            record_event(
                conn,
                output_id=op["output_id"],
                event_type="file_op_failed",
                actor=claimed_by,
                payload={
                    "file_op_id": op["file_op_id"],
                    "op_type": op["op_type"],
                    "src_path": op["src_path"],
                    "dst_path": op["dst_path"],
                    "error": error_message,
                    "attempt_count": op["attempt_count"] + 1,
                },
            )
        conn.commit()
    return {"claimed": len(claimed), "done": done, "failed": failed}


# ---------------------------------------------------------------------------
# Recovery / audit
# ---------------------------------------------------------------------------


@dataclass
class RecoveryAudit:
    missing_files: list[dict[str, Any]]
    pending_file_ops: list[dict[str, Any]]
    failed_file_ops: list[dict[str, Any]]
    storage_state_mismatches: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "missing_files": self.missing_files,
            "pending_file_ops": self.pending_file_ops,
            "failed_file_ops": self.failed_file_ops,
            "storage_state_mismatches": self.storage_state_mismatches,
        }


def recover_audit(
    conn: "psycopg.Connection[object]",
    *,
    task_id: UUID | str | None = None,
    outputs_root: Path | None = None,
) -> RecoveryAudit:
    """Return rows that need attention. Read-only and idempotent.

    - `missing_files`: rows with `storage_state='missing'`, OR rows
      whose `file_path` does not exist on disk (when `outputs_root` is
      supplied).
    - `pending_file_ops`: file-op rows in 'pending' or 'in_flight'.
    - `failed_file_ops`: file-op rows in 'failed'.
    - `storage_state_mismatches`: rows whose (status, storage_state)
      pair is outside the happy-path map AND not 'missing' /
      'file_op_failed'.
    """
    task_filter = ""
    args: tuple[Any, ...] = ()
    if task_id is not None:
        task_filter = "AND task_id = %s"
        args = (str(task_id),)

    missing_files: list[dict[str, Any]] = []
    pending_file_ops: list[dict[str, Any]] = []
    failed_file_ops: list[dict[str, Any]] = []
    storage_state_mismatches: list[dict[str, Any]] = []

    with conn.cursor() as cur:
        # storage_state='missing' rows
        cur.execute(
            f"SELECT id, file_path, status, storage_state FROM library_outputs "
            f"WHERE storage_state = 'missing' {task_filter}",
            args,
        )
        for row in cur.fetchall():
            missing_files.append(
                {
                    "output_id": str(row[0]),
                    "file_path": row[1],
                    "status": row[2],
                    "storage_state": row[3],
                }
            )

        # Pending / failed file-ops scoped to the task if given.
        op_task_filter = ""
        op_args: tuple[Any, ...] = ()
        if task_id is not None:
            op_task_filter = (
                "AND output_id IN "
                "(SELECT id FROM library_outputs WHERE task_id = %s)"
            )
            op_args = (str(task_id),)

        cur.execute(
            f"SELECT id, output_id, op_type, src_path, dst_path, "
            f"       attempt_count, created_at "
            f"FROM library_file_ops "
            f"WHERE status IN ('pending', 'in_flight') {op_task_filter} "
            f"ORDER BY created_at ASC",
            op_args,
        )
        for row in cur.fetchall():
            pending_file_ops.append(
                {
                    "file_op_id": str(row[0]),
                    "output_id": str(row[1]),
                    "op_type": row[2],
                    "src_path": row[3],
                    "dst_path": row[4],
                    "attempt_count": int(row[5]),
                }
            )

        cur.execute(
            f"SELECT id, output_id, op_type, last_error, attempt_count, "
            f"       claimed_at, completed_at "
            f"FROM library_file_ops "
            f"WHERE status = 'failed' {op_task_filter} "
            f"ORDER BY claimed_at DESC NULLS LAST, created_at DESC",
            op_args,
        )
        for row in cur.fetchall():
            failed_file_ops.append(
                {
                    "file_op_id": str(row[0]),
                    "output_id": str(row[1]),
                    "op_type": row[2],
                    "last_error": row[3],
                    "attempt_count": int(row[4]),
                    "last_attempt_at": row[5].isoformat() if row[5] else None,
                }
            )

        # storage_state mismatches: (status, storage_state) not in the
        # happy-path map, excluding the explicit divergence markers.
        cur.execute(
            f"SELECT id, status, storage_state FROM library_outputs "
            f"WHERE storage_state NOT IN ('missing', 'file_op_failed') "
            f"  {task_filter}",
            args,
        )
        for row in cur.fetchall():
            status = row[1]
            storage_state = row[2]
            expected = STATUS_TO_STORAGE_STATE.get(status)
            if expected is not None and storage_state != expected:
                storage_state_mismatches.append(
                    {
                        "output_id": str(row[0]),
                        "status": status,
                        "storage_state": storage_state,
                        "expected_storage_state": expected,
                    }
                )

        # Disk-presence check (only when outputs_root supplied; bounded
        # to rows whose status is non-terminal-rejected so we do not
        # flood the audit with every cleaned-up reject).
        if outputs_root is not None:
            cur.execute(
                f"SELECT id, file_path, status, storage_state "
                f"FROM library_outputs "
                f"WHERE storage_state NOT IN ('missing','file_op_failed') "
                f"  AND status NOT IN ('rejected','abandoned') "
                f"  {task_filter}",
                args,
            )
            for row in cur.fetchall():
                file_path = row[1]
                if not file_path:
                    continue
                p = (outputs_root / file_path)
                if not p.exists():
                    missing_files.append(
                        {
                            "output_id": str(row[0]),
                            "file_path": file_path,
                            "status": row[2],
                            "storage_state": row[3],
                            "disk_check": "missing_on_disk",
                        }
                    )

    return RecoveryAudit(
        missing_files=missing_files,
        pending_file_ops=pending_file_ops,
        failed_file_ops=failed_file_ops,
        storage_state_mismatches=storage_state_mismatches,
    )


def recover_retry(
    conn: "psycopg.Connection[object]",
    *,
    file_op_id: UUID | str,
    outputs_root: Path | None,
    actor: str = "system",
) -> dict[str, Any]:
    """Retry one file-op exactly once.

    Resets the row to status='pending' if it was 'failed', then runs
    one execute pass. Returns a result dict with the new status,
    attempt_count, and (on failure) an error message.
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE library_file_ops "
            "SET status = 'pending', claimed_by = NULL, claimed_at = NULL "
            "WHERE id = %s AND status IN ('failed','pending') "
            "RETURNING id, output_id, op_type, src_path, dst_path, attempt_count",
            (str(file_op_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise StorageError(
            f"file_op {file_op_id} not in a retryable state ('failed' or 'pending')"
        )
    conn.commit()

    if outputs_root is None:
        return {
            "file_op_id": str(row[0]),
            "status": "pending",
            "attempt_count": int(row[5]),
            "error": "outputs_root not supplied; retry not executed",
        }

    success, error_message = execute_file_op(
        op_type=row[2],
        src_path=row[3],
        dst_path=row[4],
        outputs_root=outputs_root,
    )
    complete_file_op(
        conn,
        file_op_id=row[0],
        success=success,
        error_message=error_message,
    )
    if success:
        if row[2] == "move" and row[4]:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE library_outputs SET file_path = %s "
                    "WHERE id = %s",
                    (row[4], row[1]),
                )
        # Reset storage_state: pick the new state from STATUS_TO_STORAGE_STATE.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM library_outputs WHERE id = %s",
                (row[1],),
            )
            status_row = cur.fetchone()
            if status_row is not None:
                new_storage = STATUS_TO_STORAGE_STATE.get(status_row[0], "raw")
                cur.execute(
                    "UPDATE library_outputs SET storage_state = %s "
                    "WHERE id = %s AND storage_state = 'file_op_failed'",
                    (new_storage, row[1]),
                )
        record_event(
            conn,
            output_id=row[1],
            event_type="recover",
            actor=actor,
            payload={"file_op_id": str(row[0]), "op_type": row[2]},
        )
    conn.commit()
    return {
        "file_op_id": str(row[0]),
        "status": "done" if success else "failed",
        "attempt_count": int(row[5]) + 1,
        "error": error_message,
    }


# ---------------------------------------------------------------------------
# Path computation helpers
# ---------------------------------------------------------------------------


def reject_dst_path(file_path: str) -> str | None:
    """Compute the destination path for a reject move.

    Source is `intake/<task_dir>/<subdir>/<filename>`; destination is
    `intake/<task_dir>/rejected/<filename>`. Returns None if the path
    shape does not look like an intake path.
    """
    parts = Path(file_path).parts
    if len(parts) < 4:
        return None
    if parts[0] != "intake":
        return None
    intake_segment, task_dir = parts[0], parts[1]
    filename = Path(file_path).name
    return f"{intake_segment}/{task_dir}/rejected/{filename}"


def diagnostic_dst_path(file_path: str, *, bucket: str) -> str | None:
    """Compute the destination for an auto-route move into
    `intake/<task_dir>/diagnostic/<bucket>/<filename>`.
    """
    if not bucket:
        return None
    parts = Path(file_path).parts
    if len(parts) < 4:
        return None
    if parts[0] != "intake":
        return None
    intake_segment, task_dir = parts[0], parts[1]
    filename = Path(file_path).name
    return f"{intake_segment}/{task_dir}/diagnostic/{bucket}/{filename}"
