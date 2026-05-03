"""`library_search()` SQL function wrapper.

Spec: `.gov/spec/openrepose_library_v0_1.md` Database Schema
(library_search ranking) + Command Surface (`library_search` LLM command).

Returns hybrid-ranked entries combining trigram (titles + tags) with
tsvector (prompts + story_beats + notes). Each result includes the
top 3 manual / smart tags so the GUI list view does not need a second
round-trip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg

DEFAULT_LIMIT = 50
HARD_LIMIT = 200


@dataclass(frozen=True)
class SearchResult:
    entry_id: UUID
    rank: float
    title: str
    avatar_slug: str
    yaw_bin: str | None
    top_tags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": str(self.entry_id),
            "rank": float(self.rank),
            "title": self.title,
            "avatar_slug": self.avatar_slug,
            "yaw_bin": self.yaw_bin,
            "top_tags": list(self.top_tags),
        }


def search(
    conn: "psycopg.Connection[object]",
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[SearchResult]:
    """Run the SQL `library_search(query)` function and join in the entry
    metadata + top 3 tags per row. Returns rank-ordered list (DESC).

    `query` is passed verbatim to the SQL function (it handles
    plainto_tsquery / similarity internally). `limit` is clamped to
    `HARD_LIMIT` since the SQL function itself caps at 200.
    """
    capped = max(1, min(int(limit), HARD_LIMIT))
    with conn.cursor() as cur:
        cur.execute(
            "WITH ranked AS ("
            "  SELECT entry_id, rank FROM library_search(%s)"
            ") "
            "SELECT r.entry_id, r.rank, e.title, e.avatar_slug, e.yaw_bin, "
            "       COALESCE(("
            "         SELECT array_agg(t.name ORDER BY t.name) "
            "         FROM ("
            "           SELECT name FROM tags tg "
            "           JOIN entry_tags et ON et.tag_id = tg.id "
            "           WHERE et.entry_id = r.entry_id "
            "           ORDER BY name LIMIT 3"
            "         ) t"
            "       ), ARRAY[]::TEXT[]) AS top_tags "
            "FROM ranked r JOIN library_entries e ON e.id = r.entry_id "
            "ORDER BY r.rank DESC "
            "LIMIT %s",
            (query, capped),
        )
        rows = cur.fetchall()
    out: list[SearchResult] = []
    for row in rows:
        eid = row[0] if isinstance(row[0], UUID) else UUID(str(row[0]))
        out.append(
            SearchResult(
                entry_id=eid,
                rank=float(row[1]),
                title=row[2] or "",
                avatar_slug=row[3] or "",
                yaw_bin=row[4],
                top_tags=tuple(row[5] or ()),
            )
        )
    return out
