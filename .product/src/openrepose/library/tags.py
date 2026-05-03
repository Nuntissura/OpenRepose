"""Tags + entry_tags M-to-N relation helpers.

Spec: `.gov/spec/openrepose_library_v0_1.md` Tag System (free-form text;
namespaced convention `namespace:value`; smart tags prefixed `auto:`;
trigram-indexed for fuzzy search).

These helpers run inside an existing psycopg connection / transaction.
They do not commit; the caller (commands layer in WP-I2-004) decides
transaction boundaries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable
from uuid import UUID

from .smart_tags import AUTO_TAG_PREFIX

if TYPE_CHECKING:
    import psycopg


class LibraryTagError(ValueError):
    """Raised when a tag name is malformed or a relation cannot be resolved."""


def _normalize_tag(name: str) -> str:
    """Lowercase + strip; reject empty / whitespace-only names."""
    if not isinstance(name, str):
        raise LibraryTagError(f"tag must be str; got {type(name).__name__}")
    cleaned = name.strip().lower()
    if not cleaned:
        raise LibraryTagError("tag name must be non-empty after strip")
    return cleaned


def _ensure_tags(
    conn: "psycopg.Connection[object]", names: Iterable[str]
) -> dict[str, int]:
    """Resolve every input name to a `tags.id`, inserting new ones.

    Returns a mapping `{normalized_name: id}` for the supplied names.
    Concurrency-safe: uses `INSERT ... ON CONFLICT DO NOTHING` then
    `SELECT` in one round-trip. Caller controls transaction.
    """
    normalized = sorted({_normalize_tag(n) for n in names})
    if not normalized:
        return {}
    with conn.cursor() as cur:
        # Insert any not-yet-present names; no error on duplicates.
        cur.executemany(
            "INSERT INTO tags (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            [(n,) for n in normalized],
        )
        cur.execute(
            "SELECT id, name FROM tags WHERE name = ANY(%s)", (normalized,)
        )
        return {row[1]: int(row[0]) for row in cur.fetchall()}


def add_tags(
    conn: "psycopg.Connection[object]",
    entry_id: UUID | str,
    tag_names: Iterable[str],
    *,
    is_auto: bool = False,
) -> list[str]:
    """Attach the given tags to `entry_id`. Returns the normalized names
    that were attached (existing attachments are no-ops, returned too).

    `is_auto=True` forces every name to start with `auto:` (helps callers
    ensure the smart-tag extractor cannot leak unprefixed tags). Use
    `is_auto=False` for operator-supplied tags; the caller may still
    pre-pend `auto:` if needed.
    """
    names = list(tag_names)
    if not names:
        return []
    if is_auto:
        names = [
            n if n.startswith(AUTO_TAG_PREFIX) else f"{AUTO_TAG_PREFIX}{n}"
            for n in names
        ]

    tag_ids = _ensure_tags(conn, names)
    pairs = [(str(entry_id), tag_id) for tag_id in tag_ids.values()]
    if not pairs:
        return []
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO entry_tags (entry_id, tag_id) VALUES (%s, %s) "
            "ON CONFLICT (entry_id, tag_id) DO NOTHING",
            pairs,
        )
    return sorted(tag_ids.keys())


def remove_tags(
    conn: "psycopg.Connection[object]",
    entry_id: UUID | str,
    tag_names: Iterable[str],
) -> list[str]:
    """Detach the given tags from `entry_id`. Returns the normalized
    names that were detached. Names that were not attached are silently
    ignored (no error)."""
    normalized = sorted({_normalize_tag(n) for n in tag_names})
    if not normalized:
        return []
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM entry_tags WHERE entry_id = %s AND tag_id IN ("
            "  SELECT id FROM tags WHERE name = ANY(%s)"
            ") RETURNING tag_id",
            (str(entry_id), normalized),
        )
        deleted_ids = {int(row[0]) for row in cur.fetchall()}
        if not deleted_ids:
            return []
        cur.execute(
            "SELECT name FROM tags WHERE id = ANY(%s)", (sorted(deleted_ids),)
        )
        return sorted(row[0] for row in cur.fetchall())


def list_entry_tags(
    conn: "psycopg.Connection[object]", entry_id: UUID | str
) -> list[str]:
    """Return the normalized tag names attached to `entry_id`, sorted."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT t.name FROM tags t JOIN entry_tags et ON et.tag_id = t.id "
            "WHERE et.entry_id = %s ORDER BY t.name",
            (str(entry_id),),
        )
        return [row[0] for row in cur.fetchall()]


def set_entry_tags(
    conn: "psycopg.Connection[object]",
    entry_id: UUID | str,
    tag_names: Iterable[str],
    *,
    replace: bool = False,
    preserve_auto: bool = True,
) -> list[str]:
    """Bulk-set the tag list for an entry.

    `replace=False`: additive — equivalent to `add_tags(...)`.
    `replace=True`: detaches every currently-attached tag whose name does
    not appear in `tag_names`, then attaches the new set. Smart tags
    (`auto:` prefix) are preserved across replace by default
    (`preserve_auto=True`) to match the spec ("With `replace=true`,
    replaces the entire tag set excluding smart tags; smart tags stay").

    Returns the resulting full attached-tags list (sorted).
    """
    normalized_new = {_normalize_tag(n) for n in tag_names}

    if not replace:
        add_tags(conn, entry_id, normalized_new)
        return list_entry_tags(conn, entry_id)

    current = set(list_entry_tags(conn, entry_id))
    keepers = (
        {t for t in current if t.startswith(AUTO_TAG_PREFIX)}
        if preserve_auto
        else set()
    )
    target = normalized_new | keepers
    to_remove = current - target
    to_add = target - current

    if to_remove:
        remove_tags(conn, entry_id, to_remove)
    if to_add:
        add_tags(conn, entry_id, to_add)
    return list_entry_tags(conn, entry_id)
