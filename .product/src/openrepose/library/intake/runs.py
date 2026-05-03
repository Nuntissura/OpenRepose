"""CRUD on `library_runs` (WP-I3-005).

A run = one ComfyUI generation invocation. Created once per `save_and_register`
call in the bridge; reused across the per-image loop so all outputs of one
contact-sheet save share a `run_id`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg


class LibraryRunError(ValueError):
    """Raised when run input is malformed or a referenced row is missing."""


@dataclass
class LibraryRun:
    id: UUID
    card_id: UUID
    task_id: UUID | None
    pose_guide_id: UUID | None
    sampler: str | None
    cfg: float | None
    steps: int | None
    seed: int | None
    workflow_json: dict[str, Any] | None
    created_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "card_id": str(self.card_id),
            "task_id": str(self.task_id) if self.task_id else None,
            "pose_guide_id": str(self.pose_guide_id) if self.pose_guide_id else None,
            "sampler": self.sampler,
            "cfg": self.cfg,
            "steps": self.steps,
            "seed": self.seed,
            "workflow_json": self.workflow_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def begin_run(
    conn: "psycopg.Connection[object]",
    *,
    card_id: UUID | str,
    task_id: UUID | str | None = None,
    pose_guide_id: UUID | str | None = None,
    sampler: str | None = None,
    cfg: float | None = None,
    steps: int | None = None,
    seed: int | None = None,
    workflow_json: dict[str, Any] | None = None,
) -> LibraryRun:
    """Insert one library_runs row and return it."""
    if not card_id:
        raise LibraryRunError("card_id is required")
    from psycopg.types.json import Jsonb

    workflow_param = Jsonb(workflow_json) if workflow_json is not None else None
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_runs "
            "(card_id, task_id, pose_guide_id, sampler, cfg, steps, seed, workflow_json) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id, card_id, task_id, pose_guide_id, sampler, cfg, "
            "          steps, seed, workflow_json, created_at",
            (
                str(card_id),
                str(task_id) if task_id else None,
                str(pose_guide_id) if pose_guide_id else None,
                sampler,
                cfg,
                steps,
                seed,
                workflow_param,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_run(row)


def resolve_card_by_slug(
    conn: "psycopg.Connection[object]",
    *,
    task_id: UUID | str,
    card_slug: str,
) -> tuple[UUID | None, int]:
    """Resolve a card slug to a card_id within the active task's batches.

    Returns (card_id_or_None, match_count). Caller decides what to do on
    multi-match (the dispatcher logs a WARN; v0.1 takes the first match
    via the SQL ORDER BY).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT e.id FROM library_entries e "
            "JOIN library_batches b ON b.id = e.batch_id "
            "WHERE b.task_id = %s AND e.title = %s "
            "ORDER BY e.created_at ASC",
            (str(task_id), card_slug),
        )
        rows = cur.fetchall()
    if not rows:
        return None, 0
    return rows[0][0], len(rows)


def _row_to_run(row: Any) -> LibraryRun:
    return LibraryRun(
        id=row[0],
        card_id=row[1],
        task_id=row[2],
        pose_guide_id=row[3],
        sampler=row[4],
        cfg=float(row[5]) if row[5] is not None else None,
        steps=int(row[6]) if row[6] is not None else None,
        seed=int(row[7]) if row[7] is not None else None,
        workflow_json=row[8],
        created_at=row[9],
    )
