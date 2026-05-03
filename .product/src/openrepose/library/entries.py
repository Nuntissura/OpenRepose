"""CRUD on `library_entries`.

Spec: `.gov/spec/openrepose_library_v0_1.md` Database Schema +
Multi-Operator Concurrency.

Each function takes a live `psycopg.Connection` so the caller (commands
layer in WP-I2-004) controls transaction boundaries. `update_entry` and
`delete_entry` acquire a row-level lock via `SELECT ... FOR UPDATE
NOWAIT` and surface a `LibraryEntryLockedError` when another operator
holds the row — mirroring the structured-error contract in the spec.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg

# Permitted completeness markers. The spec uses these as a coarse signal
# for the GUI's per-entry status badge; values aren't enforced at the
# database layer.
COMPLETENESS_PARTIAL = "partial"
COMPLETENESS_COMPLETE = "complete"
COMPLETENESS_VALUES = (COMPLETENESS_PARTIAL, COMPLETENESS_COMPLETE)


class LibraryEntryError(ValueError):
    """Raised when entry input is malformed or a row is missing."""


class LibraryEntryLockedError(RuntimeError):
    """Raised when SELECT ... FOR UPDATE NOWAIT cannot acquire the row."""

    def __init__(self, entry_id: str, locked_by: str | None = None) -> None:
        super().__init__(
            f"library entry {entry_id} locked by {locked_by!r}"
            if locked_by
            else f"library entry {entry_id} is locked by another operator"
        )
        self.entry_id = entry_id
        self.locked_by = locked_by


@dataclass
class LibraryEntry:
    """In-memory view of a `library_entries` row."""

    id: UUID
    avatar_slug: str
    title: str = ""
    yaw_bin: str | None = None
    portrait_path: str | None = None
    openpose_json_path: str | None = None
    openpose_png_path: str | None = None
    generated_image_path: str | None = None
    comfyui_workflow: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    completeness: str = COMPLETENESS_PARTIAL
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None
    locked_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "avatar_slug": self.avatar_slug,
            "title": self.title,
            "yaw_bin": self.yaw_bin,
            "portrait_path": self.portrait_path,
            "openpose_json_path": self.openpose_json_path,
            "openpose_png_path": self.openpose_png_path,
            "generated_image_path": self.generated_image_path,
            "comfyui_workflow": self.comfyui_workflow,
            "metadata": dict(self.metadata),
            "completeness": self.completeness,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "locked_by": self.locked_by,
        }


_COLUMNS = (
    "id",
    "avatar_slug",
    "title",
    "yaw_bin",
    "portrait_path",
    "openpose_json_path",
    "openpose_png_path",
    "generated_image_path",
    "comfyui_workflow",
    "metadata",
    "completeness",
    "created_at",
    "updated_at",
    "created_by",
    "locked_by",
)
_SELECT_COLS = ", ".join(_COLUMNS)


def _row_to_entry(row: tuple[Any, ...]) -> LibraryEntry:
    return LibraryEntry(
        id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
        avatar_slug=row[1] or "",
        title=row[2] or "",
        yaw_bin=row[3],
        portrait_path=row[4],
        openpose_json_path=row[5],
        openpose_png_path=row[6],
        generated_image_path=row[7],
        comfyui_workflow=row[8],
        metadata=row[9] or {},
        completeness=row[10] or COMPLETENESS_PARTIAL,
        created_at=row[11],
        updated_at=row[12],
        created_by=row[13],
        locked_by=row[14],
    )


def _validate_completeness(value: str | None) -> str:
    if value is None:
        return COMPLETENESS_PARTIAL
    if value not in COMPLETENESS_VALUES:
        raise LibraryEntryError(
            f"invalid completeness {value!r}; expected one of {COMPLETENESS_VALUES}"
        )
    return value


# Fields a caller may patch via `update_entry`. `id`, `created_at`,
# `created_by` are immutable; `updated_at` is set by the function;
# `locked_by` is managed by the row-lock acquisition path.
_UPDATABLE_FIELDS = (
    "avatar_slug",
    "title",
    "yaw_bin",
    "portrait_path",
    "openpose_json_path",
    "openpose_png_path",
    "generated_image_path",
    "comfyui_workflow",
    "metadata",
    "completeness",
)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_entry(
    conn: "psycopg.Connection[object]",
    *,
    avatar_slug: str,
    title: str = "",
    yaw_bin: str | None = None,
    portrait_path: str | None = None,
    openpose_json_path: str | None = None,
    openpose_png_path: str | None = None,
    generated_image_path: str | None = None,
    comfyui_workflow: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    completeness: str | None = None,
    created_by: str | None = None,
) -> LibraryEntry:
    """Insert a new entry; return the persisted row (with server-assigned
    UUID + timestamps). Caller commits. `metadata` is JSON-encoded."""
    if not avatar_slug or not isinstance(avatar_slug, str):
        raise LibraryEntryError("avatar_slug is required (non-empty str)")
    completeness = _validate_completeness(completeness)
    md = metadata or {}
    workflow = comfyui_workflow

    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO library_entries ("
            f"avatar_slug, title, yaw_bin, "
            f"portrait_path, openpose_json_path, openpose_png_path, "
            f"generated_image_path, comfyui_workflow, metadata, "
            f"completeness, created_by"
            f") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            f"RETURNING {_SELECT_COLS}",
            (
                avatar_slug,
                title or "",
                yaw_bin,
                portrait_path,
                openpose_json_path,
                openpose_png_path,
                generated_image_path,
                json.dumps(workflow) if workflow is not None else None,
                json.dumps(md),
                completeness,
                created_by,
            ),
        )
        row = cur.fetchone()
    if row is None:  # pragma: no cover - INSERT RETURNING always returns
        raise LibraryEntryError("INSERT did not return a row")
    return _row_to_entry(row)


def get_entry(
    conn: "psycopg.Connection[object]", entry_id: UUID | str
) -> LibraryEntry | None:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {_SELECT_COLS} FROM library_entries WHERE id = %s",
            (str(entry_id),),
        )
        row = cur.fetchone()
    return _row_to_entry(row) if row else None


def list_entries(
    conn: "psycopg.Connection[object]",
    *,
    avatar_slug: str | None = None,
    yaw_bin: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[LibraryEntry]:
    """Filter by avatar_slug / yaw_bin; ordered by `created_at DESC`."""
    where_parts: list[str] = []
    params: list[Any] = []
    if avatar_slug is not None:
        where_parts.append("avatar_slug = %s")
        params.append(avatar_slug)
    if yaw_bin is not None:
        where_parts.append("yaw_bin = %s")
        params.append(yaw_bin)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    params.extend([int(limit), int(offset)])
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {_SELECT_COLS} FROM library_entries {where} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
            params,
        )
        return [_row_to_entry(r) for r in cur.fetchall()]


def update_entry(
    conn: "psycopg.Connection[object]",
    entry_id: UUID | str,
    *,
    operator_slug: str | None = None,
    **patch: Any,
) -> LibraryEntry:
    """Acquire row lock then patch fields. Raises `LibraryEntryLockedError`
    when another session holds the row. Unknown / immutable fields raise
    `LibraryEntryError`. Returns the updated row.

    `operator_slug` is recorded in `locked_by` for the duration of the
    transaction so a peek by another session sees who is editing."""
    if not patch:
        raise LibraryEntryError("update_entry requires at least one patch field")
    for key in patch:
        if key not in _UPDATABLE_FIELDS:
            raise LibraryEntryError(
                f"unknown / immutable update field {key!r}; "
                f"editable: {sorted(_UPDATABLE_FIELDS)}"
            )
    if "completeness" in patch:
        patch["completeness"] = _validate_completeness(patch["completeness"])

    sid = str(entry_id)
    with conn.cursor() as cur:
        try:
            cur.execute(
                "SELECT id, locked_by FROM library_entries WHERE id = %s "
                "FOR UPDATE NOWAIT",
                (sid,),
            )
        except Exception as e:
            # psycopg raises `psycopg.errors.LockNotAvailable` (subclass
            # of `OperationalError`) when NOWAIT cannot acquire. We
            # promote to a structured error the dispatcher can return.
            from psycopg.errors import LockNotAvailable  # local import keeps the dep optional

            if isinstance(e, LockNotAvailable):
                conn.rollback()
                raise LibraryEntryLockedError(sid) from e
            raise
        row = cur.fetchone()
        if row is None:
            raise LibraryEntryError(f"library entry {sid} not found")

        # Build the SET clause for whatever was provided.
        set_fragments: list[str] = []
        params: list[Any] = []
        for key, value in patch.items():
            if key in {"comfyui_workflow", "metadata"}:
                set_fragments.append(f"{key} = %s::jsonb")
                params.append(json.dumps(value) if value is not None else None)
            else:
                set_fragments.append(f"{key} = %s")
                params.append(value)
        # Always bump updated_at + record locked_by for the txn.
        set_fragments.append("updated_at = NOW()")
        set_fragments.append("locked_by = %s")
        params.append(operator_slug)
        params.append(sid)

        cur.execute(
            f"UPDATE library_entries SET {', '.join(set_fragments)} "
            f"WHERE id = %s RETURNING {_SELECT_COLS}",
            params,
        )
        row = cur.fetchone()
    if row is None:  # pragma: no cover - UPDATE-RETURNING returns the row we just locked
        raise LibraryEntryError(f"library entry {sid} disappeared mid-update")
    return _row_to_entry(row)


def delete_entry(
    conn: "psycopg.Connection[object]", entry_id: UUID | str
) -> bool:
    """Delete the entry. Cascades to entry_tags / prompts / story_beats /
    notes via the FK ON DELETE CASCADE in the schema. Returns True when a
    row was deleted, False when no entry with that id existed."""
    sid = str(entry_id)
    with conn.cursor() as cur:
        try:
            cur.execute(
                "SELECT id FROM library_entries WHERE id = %s FOR UPDATE NOWAIT",
                (sid,),
            )
        except Exception as e:
            from psycopg.errors import LockNotAvailable

            if isinstance(e, LockNotAvailable):
                conn.rollback()
                raise LibraryEntryLockedError(sid) from e
            raise
        if cur.fetchone() is None:
            return False
        cur.execute("DELETE FROM library_entries WHERE id = %s", (sid,))
    return True
