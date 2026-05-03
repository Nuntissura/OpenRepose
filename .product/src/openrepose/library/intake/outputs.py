"""CRUD on `library_outputs` + status transitions (WP-I3-004).

Spec: `.gov/spec/openrepose_intake_v0_1.md` "Triage Commands" + "Status
Enum" + "Two-Stage Acceptance".

LLM-issuable: register_output, soft_accept_output, reject_output,
reroute_output, list_outputs, get_output.

Operator-only (token gate enforced in commands layer; DB CHECK is the
kill switch): finalize_output, bulk_promote_task.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from .auto_route import AutoRouteResult, run_auto_route

if TYPE_CHECKING:
    import psycopg


_VALID_STATUSES = (
    "pending", "triaging", "soft_accepted", "promoted",
    "rejected", "diagnostic", "abandoned",
)
_REROUTE_TARGETS = ("pending", "diagnostic", "rejected")


class IntakeOutputError(ValueError):
    """Raised when output input is malformed or a row is missing."""


@dataclass
class IntakeOutput:
    id: UUID
    run_id: UUID
    task_id: UUID
    file_path: str
    content_hash: str
    width: int
    height: int
    status: str
    primary_rejection_reason: str | None
    soft_accepted_at: datetime | None
    promoted_at: datetime | None
    rejected_at: datetime | None
    finalized_by: str | None
    notes: str | None
    created_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "run_id": str(self.run_id),
            "task_id": str(self.task_id),
            "file_path": self.file_path,
            "content_hash": self.content_hash,
            "width": self.width,
            "height": self.height,
            "status": self.status,
            "primary_rejection_reason": self.primary_rejection_reason,
            "soft_accepted_at": self.soft_accepted_at.isoformat() if self.soft_accepted_at else None,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
            "rejected_at": self.rejected_at.isoformat() if self.rejected_at else None,
            "finalized_by": self.finalized_by,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def register_output(
    conn: "psycopg.Connection[object]",
    *,
    run_id: UUID | str,
    task_id: UUID | str,
    project_id: UUID | str,
    file_path: str,
    content_hash: str,
    width: int,
    height: int,
    outputs_root: Path | None = None,
) -> tuple[IntakeOutput, AutoRouteResult]:
    """Insert one library_outputs row at status='pending', then run
    auto-route. On auto-route fire, the row is updated to status='diagnostic'
    + a library_diagnostics row is written + the file is moved to the
    bucket subdirectory. The DB and filesystem are kept in sync inside
    the same transaction (commit at the end).
    """
    if width <= 0 or height <= 0:
        raise IntakeOutputError("width and height must be positive")

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_outputs "
            "(run_id, task_id, file_path, content_hash, width, height, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'pending') "
            "RETURNING id, run_id, task_id, file_path, content_hash, "
            "          width, height, status, primary_rejection_reason, "
            "          soft_accepted_at, promoted_at, rejected_at, "
            "          finalized_by, notes, created_at",
            (str(run_id), str(task_id), file_path, content_hash, width, height),
        )
        row = cur.fetchone()
        cur.execute(
            "UPDATE library_tasks SET received_count = received_count + 1 "
            "WHERE id = %s",
            (str(task_id),),
        )
    output = _row_to_output(row)

    auto = run_auto_route(conn, project_id=project_id, width=width, height=height)
    if auto.routed and auto.rule_id is not None:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE library_outputs SET status = 'diagnostic' "
                "WHERE id = %s "
                "RETURNING id, run_id, task_id, file_path, content_hash, "
                "          width, height, status, primary_rejection_reason, "
                "          soft_accepted_at, promoted_at, rejected_at, "
                "          finalized_by, notes, created_at",
                (str(output.id),),
            )
            output = _row_to_output(cur.fetchone())
            cur.execute(
                "INSERT INTO library_diagnostics "
                "(output_id, rule_id, bucket, reason) "
                "VALUES (%s, %s, %s, %s)",
                (str(output.id), auto.rule_id, auto.bucket, auto.reason),
            )
    conn.commit()

    if auto.routed and outputs_root is not None and auto.bucket:
        _move_to_bucket(outputs_root, output, bucket=f"diagnostic/{auto.bucket}")

    return output, auto


def get_output(
    conn: "psycopg.Connection[object]",
    *,
    output_id: UUID | str,
) -> IntakeOutput | None:
    with conn.cursor() as cur:
        cur.execute(_SELECT_BASE + " WHERE id = %s", (str(output_id),))
        row = cur.fetchone()
    return _row_to_output(row) if row else None


def list_outputs(
    conn: "psycopg.Connection[object]",
    *,
    task_id: UUID | str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[IntakeOutput]:
    if status is not None and status not in _VALID_STATUSES:
        raise IntakeOutputError(
            f"status filter must be one of {_VALID_STATUSES}; got {status!r}"
        )
    if limit < 1 or offset < 0:
        raise IntakeOutputError("limit must be >= 1, offset must be >= 0")
    where_parts: list[str] = []
    args: list[Any] = []
    if task_id is not None:
        where_parts.append("task_id = %s")
        args.append(str(task_id))
    if status is not None:
        where_parts.append("status = %s")
        args.append(status)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    args.extend([int(limit), int(offset)])
    with conn.cursor() as cur:
        cur.execute(
            f"{_SELECT_BASE} {where} ORDER BY created_at ASC LIMIT %s OFFSET %s",
            tuple(args),
        )
        rows = cur.fetchall()
    return [_row_to_output(r) for r in rows]


def soft_accept_output(
    conn: "psycopg.Connection[object]",
    *,
    output_id: UUID | str,
    notes: str | None = None,
) -> IntakeOutput:
    """LLM-issuable. Transition from pending/triaging to soft_accepted."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE library_outputs "
            "SET status = 'soft_accepted', soft_accepted_at = NOW(), "
            "    notes = COALESCE(%s, notes) "
            "WHERE id = %s "
            "  AND status IN ('pending', 'triaging') "
            f"RETURNING {_RETURNING_COLS}",
            (notes, str(output_id)),
        )
        row = cur.fetchone()
    if row is None:
        existing = get_output(conn, output_id=output_id)
        if existing is None:
            raise IntakeOutputError(f"output {output_id} not found")
        raise IntakeOutputError(
            f"output {output_id} not in pending/triaging (status={existing.status})"
        )
    conn.commit()
    return _row_to_output(row)


def reject_output(
    conn: "psycopg.Connection[object]",
    *,
    output_id: UUID | str,
    primary_rejection_reason: str,
    notes: str | None = None,
    operator_slug: str | None = None,
    outputs_root: Path | None = None,
) -> IntakeOutput:
    """LLM-issuable in v0.1 (operator-only-finalize is the gate that
    matters). Transition any non-terminal status to 'rejected'; move
    file to <intake_dir>/rejected/."""
    if not primary_rejection_reason:
        raise IntakeOutputError("primary_rejection_reason is required")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE library_outputs "
            "SET status = 'rejected', rejected_at = NOW(), "
            "    primary_rejection_reason = %s, notes = COALESCE(%s, notes), "
            "    finalized_by = COALESCE(%s, finalized_by) "
            "WHERE id = %s "
            "  AND status NOT IN ('rejected', 'promoted') "
            f"RETURNING {_RETURNING_COLS}",
            (primary_rejection_reason, notes, operator_slug, str(output_id)),
        )
        row = cur.fetchone()
    if row is None:
        existing = get_output(conn, output_id=output_id)
        if existing is None:
            raise IntakeOutputError(f"output {output_id} not found")
        raise IntakeOutputError(
            f"output {output_id} already terminal (status={existing.status})"
        )
    output = _row_to_output(row)
    conn.commit()
    if outputs_root is not None:
        _move_to_bucket(outputs_root, output, bucket="rejected")
    return output


def finalize_output(
    conn: "psycopg.Connection[object]",
    *,
    output_id: UUID | str,
    operator_slug: str,
) -> IntakeOutput:
    """Operator-only (token gate in commands layer; DB CHECK is the kill
    switch). Transition soft_accepted -> promoted; sets finalized_by so
    the lib_outputs_intake_001_two_stage_acceptance constraint holds."""
    if not operator_slug:
        raise IntakeOutputError("operator_slug is required for finalize")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE library_outputs "
            "SET status = 'promoted', promoted_at = NOW(), "
            "    finalized_by = %s "
            "WHERE id = %s AND status = 'soft_accepted' "
            f"RETURNING {_RETURNING_COLS}",
            (operator_slug, str(output_id)),
        )
        row = cur.fetchone()
    if row is None:
        existing = get_output(conn, output_id=output_id)
        if existing is None:
            raise IntakeOutputError(f"output {output_id} not found")
        raise IntakeOutputError(
            f"output {output_id} not in soft_accepted (status={existing.status}); "
            f"only soft_accepted rows may be finalized"
        )
    conn.commit()
    return _row_to_output(row)


def bulk_promote_task(
    conn: "psycopg.Connection[object]",
    *,
    task_id: UUID | str,
    operator_slug: str,
) -> list[str]:
    """Operator-only. Promote every soft_accepted row for the task in
    one transaction."""
    if not operator_slug:
        raise IntakeOutputError("operator_slug required")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE library_outputs "
            "SET status = 'promoted', promoted_at = NOW(), finalized_by = %s "
            "WHERE task_id = %s AND status = 'soft_accepted' "
            "RETURNING id",
            (operator_slug, str(task_id)),
        )
        ids = [str(r[0]) for r in cur.fetchall()]
    conn.commit()
    return ids


def reroute_output(
    conn: "psycopg.Connection[object]",
    *,
    output_id: UUID | str,
    target_status: str,
) -> IntakeOutput:
    """LLM-issuable. Move a row to one of pending/diagnostic/rejected
    (e.g. operator notices a metadata mis-detection put a fine output
    in `diagnostic/intermediate_evidence/` — they reroute to pending)."""
    if target_status not in _REROUTE_TARGETS:
        raise IntakeOutputError(
            f"target_status must be one of {_REROUTE_TARGETS}; got {target_status!r}"
        )
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE library_outputs SET status = %s "
            "WHERE id = %s AND status NOT IN ('promoted') "
            f"RETURNING {_RETURNING_COLS}",
            (target_status, str(output_id)),
        )
        row = cur.fetchone()
    if row is None:
        existing = get_output(conn, output_id=output_id)
        if existing is None:
            raise IntakeOutputError(f"output {output_id} not found")
        raise IntakeOutputError(
            f"output {output_id} is promoted; reroute denied (REQ-002 reversibility "
            f"applies only to non-promoted rows in v0.1)"
        )
    conn.commit()
    return _row_to_output(row)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

_RETURNING_COLS = (
    "id, run_id, task_id, file_path, content_hash, width, height, status, "
    "primary_rejection_reason, soft_accepted_at, promoted_at, rejected_at, "
    "finalized_by, notes, created_at"
)
_SELECT_BASE = f"SELECT {_RETURNING_COLS} FROM library_outputs"


def _row_to_output(row: Any) -> IntakeOutput:
    return IntakeOutput(
        id=row[0],
        run_id=row[1],
        task_id=row[2],
        file_path=row[3],
        content_hash=row[4],
        width=int(row[5]),
        height=int(row[6]),
        status=row[7],
        primary_rejection_reason=row[8],
        soft_accepted_at=row[9],
        promoted_at=row[10],
        rejected_at=row[11],
        finalized_by=row[12],
        notes=row[13],
        created_at=row[14],
    )


def _move_to_bucket(
    outputs_root: Path,
    output: IntakeOutput,
    *,
    bucket: str,
) -> str | None:
    """Move the output's file from raw/ into the bucket subdirectory,
    inside the same intake_dir. Returns the new relative path under
    `outputs_root` or None if the source file does not exist.
    Best-effort: filesystem failures do not roll back the DB transition.
    """
    src = (Path(outputs_root) / output.file_path).resolve()
    intake_root = (Path(outputs_root) / "intake").resolve()
    try:
        src.relative_to(intake_root)
    except ValueError:
        return None
    if not src.exists():
        return None
    # destination = same parent of intake_dir, but in the bucket subtree.
    # output.file_path is `intake/<task_dir>/raw/<filename>` typically.
    parts = Path(output.file_path).parts
    if len(parts) < 4:
        return None
    intake_segment, task_dir, _maybe_subdir, *rest = parts
    filename = "/".join(rest) if rest else parts[-1]
    dest_dir = (Path(outputs_root) / intake_segment / task_dir / bucket)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(filename).name
    shutil.move(str(src), str(dest))
    return str(dest.relative_to(Path(outputs_root))).replace("\\", "/")
