"""CRUD on `library_projects` (WP-I3-004).

Spec: `.gov/spec/openrepose_intake_v0_1.md` "Hierarchy / library_projects".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg


_VALID_STATUSES = ("active", "paused", "closed")


class LibraryProjectError(ValueError):
    """Raised when project input is malformed or a row is missing."""


@dataclass
class LibraryProject:
    id: UUID
    slug: str
    name: str
    status: str
    owner_slug: str
    created_at: datetime | None = None
    closed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "slug": self.slug,
            "name": self.name,
            "status": self.status,
            "owner_slug": self.owner_slug,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }


def create_project(
    conn: "psycopg.Connection[object]",
    *,
    slug: str,
    name: str,
    owner_slug: str,
    status: str = "active",
) -> LibraryProject:
    if not slug or not name or not owner_slug:
        raise LibraryProjectError("slug, name, owner_slug are all required")
    if status not in _VALID_STATUSES:
        raise LibraryProjectError(f"status must be one of {_VALID_STATUSES}; got {status!r}")
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_projects (slug, name, owner_slug, status) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, slug, name, status, owner_slug, created_at, closed_at",
            (slug, name, owner_slug, status),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_project(row)


def get_project(
    conn: "psycopg.Connection[object]",
    *,
    project_id: UUID | str | None = None,
    slug: str | None = None,
) -> LibraryProject | None:
    if project_id is None and not slug:
        raise LibraryProjectError("get_project requires project_id or slug")
    if project_id is not None:
        where, args = "id = %s", (str(project_id),)
    else:
        where, args = "slug = %s", (slug,)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id, slug, name, status, owner_slug, created_at, closed_at "
            f"FROM library_projects WHERE {where}",
            args,
        )
        row = cur.fetchone()
    return _row_to_project(row) if row else None


def list_projects(
    conn: "psycopg.Connection[object]",
    *,
    status: str | None = None,
) -> list[LibraryProject]:
    args: tuple[Any, ...]
    if status is not None:
        if status not in _VALID_STATUSES:
            raise LibraryProjectError(f"status filter must be one of {_VALID_STATUSES}")
        sql = (
            "SELECT id, slug, name, status, owner_slug, created_at, closed_at "
            "FROM library_projects WHERE status = %s ORDER BY created_at DESC"
        )
        args = (status,)
    else:
        sql = (
            "SELECT id, slug, name, status, owner_slug, created_at, closed_at "
            "FROM library_projects ORDER BY created_at DESC"
        )
        args = ()
    with conn.cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    return [_row_to_project(r) for r in rows]


def _row_to_project(row: Any) -> LibraryProject:
    return LibraryProject(
        id=row[0],
        slug=row[1],
        name=row[2],
        status=row[3],
        owner_slug=row[4],
        created_at=row[5],
        closed_at=row[6],
    )
