"""Generic helper for the `story_beats` and `notes` tables.

Both tables share the same shape: `id, entry_id, body, created_at,
created_by, search_doc TSVECTOR GENERATED ALWAYS AS (…) STORED`. This
module factors the CRUD so the dispatcher does not duplicate the SQL
twice.

Caller controls the transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg

# Hard-allowlist the tables this helper writes to. Identifiers are NOT
# parameterizable in libpq, so we substitute via f-string after this
# allowlist check.
_ALLOWED_TABLES = frozenset({"story_beats", "notes"})


@dataclass
class TextRecord:
    table: str
    id: int
    entry_id: UUID
    body: str
    created_at: datetime | None = None
    created_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": int(self.id),
            "entry_id": str(self.entry_id),
            "body": self.body,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }


def add_text_record(
    conn: "psycopg.Connection[object]",
    table: str,
    entry_id: UUID | str,
    *,
    body: str,
    created_by: str | None = None,
) -> TextRecord:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"unsupported text-records table: {table!r}")
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {table} (entry_id, body, created_by) "
            "VALUES (%s, %s, %s) "
            "RETURNING id, entry_id, body, created_at, created_by",
            (str(entry_id), body, created_by),
        )
        row = cur.fetchone()
    assert row is not None
    return _row(table, row)


def list_text_records(
    conn: "psycopg.Connection[object]", table: str, entry_id: UUID | str
) -> list[TextRecord]:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"unsupported text-records table: {table!r}")
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id, entry_id, body, created_at, created_by FROM {table} "
            "WHERE entry_id = %s ORDER BY created_at DESC, id DESC",
            (str(entry_id),),
        )
        return [_row(table, r) for r in cur.fetchall()]


def _row(table: str, row: tuple[Any, ...]) -> TextRecord:
    return TextRecord(
        table=table,
        id=int(row[0]),
        entry_id=row[1] if isinstance(row[1], UUID) else UUID(str(row[1])),
        body=row[2] or "",
        created_at=row[3],
        created_by=row[4],
    )
