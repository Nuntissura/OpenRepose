"""Prompt history for a library entry (one row per revision).

Spec: `.gov/spec/openrepose_library_v0_1.md` Inputs (Prompts) +
Database Schema (`prompts` table). Caller controls the transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg


@dataclass
class PromptRevision:
    id: int
    entry_id: UUID
    positive: str
    negative: str
    created_at: datetime | None = None
    created_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": int(self.id),
            "entry_id": str(self.entry_id),
            "positive": self.positive,
            "negative": self.negative,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }


def add_prompt(
    conn: "psycopg.Connection[object]",
    entry_id: UUID | str,
    *,
    positive: str = "",
    negative: str = "",
    created_by: str | None = None,
) -> PromptRevision:
    """Insert a new prompt revision; return it."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prompts (entry_id, positive, negative, created_by) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, entry_id, positive, negative, created_at, created_by",
            (str(entry_id), positive or "", negative or "", created_by),
        )
        row = cur.fetchone()
    assert row is not None  # INSERT RETURNING always returns
    return _row(row)


def latest_prompt(
    conn: "psycopg.Connection[object]", entry_id: UUID | str
) -> PromptRevision | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, entry_id, positive, negative, created_at, created_by "
            "FROM prompts WHERE entry_id = %s "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (str(entry_id),),
        )
        row = cur.fetchone()
    return _row(row) if row else None


def list_prompts(
    conn: "psycopg.Connection[object]", entry_id: UUID | str
) -> list[PromptRevision]:
    """Every revision, newest first."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, entry_id, positive, negative, created_at, created_by "
            "FROM prompts WHERE entry_id = %s "
            "ORDER BY created_at DESC, id DESC",
            (str(entry_id),),
        )
        return [_row(r) for r in cur.fetchall()]


def _row(row: tuple[Any, ...]) -> PromptRevision:
    return PromptRevision(
        id=int(row[0]),
        entry_id=row[1] if isinstance(row[1], UUID) else UUID(str(row[1])),
        positive=row[2] or "",
        negative=row[3] or "",
        created_at=row[4],
        created_by=row[5],
    )
