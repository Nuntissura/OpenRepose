"""Bulk intake registration (WP-I4-001).

Spec: `.gov/spec/openrepose_intake_v0_1.md`
      "I4 Scale + DB Hardening Extension / Bulk Registration Command".

`register_outputs_bulk` is the bulk counterpart to
`intake_register_output`. It does NOT replace the single-output
primitive -- bulk shares its validation, auto-route, and event-
emission paths.

Per-run scope: every bulk request carries one `(task_id, run_id)`
pair. Provenance stays explicit; runs are not implicitly created.

Idempotency: a retried bulk request with the same
`(task_id, agent_id, idempotency_key)` set returns each existing row
in `duplicates`. Zero new rows; `library_tasks.received_count` is not
double-incremented. Backed by the partial UNIQUE index
`library_outputs_idempotency_uk` plus `INSERT ... ON CONFLICT`.

Caller owns transaction. Pass `commit_local=True` to make the bulk
helper commit on its own (default, backwards-compatible). Pass
`commit_local=False` when the dispatcher wants to compose multiple
operations into one transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from .auto_route import run_auto_route
from .storage import diagnostic_dst_path, enqueue_file_op, record_event

if TYPE_CHECKING:
    import psycopg


# Producer-soft cap on outputs-per-request (INTAKE-008). Operators may
# tune via dispatcher option in a future WP; v1 fixes the default.
BULK_BATCH_MAX_DEFAULT: int = 200


class BulkIntakeError(ValueError):
    """Raised when the bulk request payload is malformed."""


@dataclass
class BulkOutputResult:
    inserted: list[dict[str, Any]] = field(default_factory=list)
    duplicates: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    diagnostic: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inserted": self.inserted,
            "duplicates": self.duplicates,
            "rejected": self.rejected,
            "diagnostic": self.diagnostic,
        }

    @property
    def inserted_count(self) -> int:
        return len(self.inserted)

    @property
    def total_processed(self) -> int:
        return (
            len(self.inserted)
            + len(self.duplicates)
            + len(self.rejected)
            + len(self.diagnostic)
        )


def register_outputs_bulk(  # noqa: PLR0912, PLR0915
    conn: "psycopg.Connection[object]",
    *,
    task_id: UUID | str,
    run_id: UUID | str,
    project_id: UUID | str,
    agent_id: str,
    source_model: str | None = None,
    outputs: list[dict[str, Any]],
    outputs_root: Any | None = None,  # Path-like; only used for file-op enqueue
    bulk_batch_max: int = BULK_BATCH_MAX_DEFAULT,
    commit_local: bool = True,
) -> BulkOutputResult:
    """Insert up to `bulk_batch_max` outputs in one transaction.

    Each output dict accepts:
      - file_path        (required, relative to outputs_root)
      - content_hash     (required)
      - width, height    (required)
      - idempotency_key  (optional but strongly recommended for retry safety)
      - producer_run_id  (optional)
      - metadata         (optional dict; not persisted in v1, reserved)
    """
    if not agent_id:
        raise BulkIntakeError("agent_id is required for bulk registration")
    if not isinstance(outputs, list):
        raise BulkIntakeError("outputs must be a list")
    if len(outputs) > bulk_batch_max:
        raise BulkIntakeError(
            f"INTAKE-008: bulk request size {len(outputs)} exceeds "
            f"bulk_batch_max={bulk_batch_max}"
        )
    if not outputs:
        return BulkOutputResult()

    result = BulkOutputResult()

    # Pre-pass: detect in-request idempotency-key collisions
    # deterministically. First wins; later duplicates land in `rejected`.
    seen_keys: set[str] = set()
    candidates: list[tuple[int, dict[str, Any]]] = []
    for idx, item in enumerate(outputs):
        key = item.get("idempotency_key")
        if key is not None and key in seen_keys:
            result.rejected.append(
                {
                    "idempotency_key": key,
                    "reason": "duplicate_idempotency_key_in_request",
                    "rule_id": "INTAKE-005",
                    "request_index": idx,
                }
            )
            continue
        if key is not None:
            seen_keys.add(key)
        candidates.append((idx, item))

    inserted_count_for_task_counter = 0

    for idx, item in candidates:
        # Per-row validation. Validation failures land in `rejected`
        # rather than aborting the bulk -- the caller can retry just
        # the failed rows.
        try:
            file_path = str(item["file_path"])
            content_hash = str(item["content_hash"])
            width = int(item["width"])
            height = int(item["height"])
        except (KeyError, ValueError, TypeError) as e:
            result.rejected.append(
                {
                    "idempotency_key": item.get("idempotency_key"),
                    "reason": f"validation_failed: {e}",
                    "rule_id": "INTAKE-005",
                    "request_index": idx,
                }
            )
            continue

        if width <= 0 or height <= 0:
            result.rejected.append(
                {
                    "idempotency_key": item.get("idempotency_key"),
                    "reason": "validation_failed: width and height must be positive",
                    "rule_id": "INTAKE-005",
                    "request_index": idx,
                }
            )
            continue

        idempotency_key = item.get("idempotency_key")
        producer_run_id = item.get("producer_run_id")

        with conn.cursor() as cur:
            # ON CONFLICT against the partial UNIQUE index. The DO
            # NOTHING + RETURNING pattern returns NULL on conflict;
            # we then fetch the existing row by the conflict tuple.
            cur.execute(
                "INSERT INTO library_outputs "
                "(run_id, task_id, file_path, content_hash, width, height, "
                " status, storage_state, "
                " agent_id, idempotency_key, source_model, producer_run_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'pending', 'raw', "
                "        %s, %s, %s, %s) "
                "ON CONFLICT ON CONSTRAINT library_outputs_idempotency_uk "
                "DO NOTHING "
                "RETURNING id",
                (
                    str(run_id),
                    str(task_id),
                    file_path,
                    content_hash,
                    width,
                    height,
                    agent_id,
                    idempotency_key,
                    source_model,
                    producer_run_id,
                ),
            )
            row = cur.fetchone()

            if row is None:
                # Conflict: fetch the existing row.
                cur.execute(
                    "SELECT id, content_hash FROM library_outputs "
                    "WHERE task_id = %s AND agent_id = %s "
                    "  AND idempotency_key = %s",
                    (str(task_id), agent_id, idempotency_key),
                )
                existing = cur.fetchone()
                if existing is None:
                    # Race condition or partial-NULL idempotency_key.
                    # The INSERT was suppressed but no row found -- log
                    # a deterministic rejected entry rather than
                    # silently dropping.
                    result.rejected.append(
                        {
                            "idempotency_key": idempotency_key,
                            "reason": "conflict_without_match",
                            "rule_id": "INTAKE-005",
                            "request_index": idx,
                        }
                    )
                    continue
                result.duplicates.append(
                    {
                        "idempotency_key": idempotency_key,
                        "existing_output_id": str(existing[0]),
                        "content_hash_match": existing[1] == content_hash,
                    }
                )
                continue

            output_id = str(row[0])
            inserted_count_for_task_counter += 1

            # Append-only register event.
            record_event(
                conn,
                output_id=output_id,
                event_type="register",
                actor=agent_id,
                to_status="pending",
                to_storage_state="raw",
                payload={
                    "agent_id": agent_id,
                    "idempotency_key": idempotency_key,
                    "source_model": source_model,
                    "producer_run_id": producer_run_id,
                    "request_index": idx,
                },
            )

        # Auto-route under the same connection -- still inside the
        # bulk transaction so a routing failure rolls back with the
        # rest. run_auto_route reads project requirements but does
        # not commit.
        auto = run_auto_route(
            conn, project_id=project_id, width=width, height=height,
        )
        if auto.routed and auto.rule_id is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE library_outputs SET status = 'diagnostic', "
                    "       storage_state = 'diagnostic' "
                    "WHERE id = %s",
                    (output_id,),
                )
                cur.execute(
                    "INSERT INTO library_diagnostics "
                    "(output_id, rule_id, bucket, reason) "
                    "VALUES (%s, %s, %s, %s)",
                    (output_id, auto.rule_id, auto.bucket, auto.reason),
                )
            record_event(
                conn,
                output_id=output_id,
                event_type="auto_route",
                actor=agent_id,
                from_status="pending",
                to_status="diagnostic",
                from_storage_state="raw",
                to_storage_state="diagnostic",
                payload={
                    "rule_id": auto.rule_id,
                    "bucket": auto.bucket,
                    "reason": auto.reason,
                },
            )
            # Enqueue file-op outbox row for the move-to-diagnostic.
            dst = (
                diagnostic_dst_path(file_path, bucket=auto.bucket or "misc")
                if auto.bucket
                else None
            )
            if dst is not None:
                enqueue_file_op(
                    conn,
                    output_id=output_id,
                    op_type="move",
                    src_path=file_path,
                    dst_path=dst,
                )
            result.diagnostic.append(
                {
                    "idempotency_key": idempotency_key,
                    "output_id": output_id,
                    "auto_route_bucket": auto.bucket,
                    "rule_id": auto.rule_id,
                }
            )
        else:
            result.inserted.append(
                {
                    "idempotency_key": idempotency_key,
                    "output_id": output_id,
                }
            )

    # Update received_count by the number of NEW rows. Duplicates and
    # rejects do not count as received outputs.
    if inserted_count_for_task_counter:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE library_tasks "
                "SET received_count = received_count + %s "
                "WHERE id = %s",
                (inserted_count_for_task_counter, str(task_id)),
            )

    if commit_local:
        conn.commit()

    # outputs_root is reserved for a future inline file-op
    # processing pass invoked here when commit_local=True. v1 leaves
    # the post-commit file-op execution to the caller (or the
    # recovery/audit path), so the bulk command is a pure DB shape
    # transformation. The function signature accepts it now so callers
    # do not need to change when that path is wired up.
    _ = outputs_root

    return result
