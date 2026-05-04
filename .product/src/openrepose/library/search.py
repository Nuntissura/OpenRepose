"""`library_search()` SQL function wrapper.

Spec: `.gov/spec/openrepose_library_v0_1.md` Database Schema
(library_search ranking) + Command Surface (`library_search` LLM command).
WP-I4-001 extension: "I4 Multi-Operator Concurrency Hardening /
library_search Default Filtering".

Returns hybrid-ranked entries combining trigram (titles + tags) with
tsvector (prompts + story_beats + notes). Each result includes the
top 3 manual / smart tags so the GUI list view does not need a second
round-trip.

Default filter (INTAKE-009): excludes intake-staging rows so the main
library view stays clean under multi-producer load. A row counts as
intake-staging iff it has `batch_id IS NOT NULL` AND
`status <> 'promoted'`. Direct `register_library_entry` rows
(`batch_id IS NULL`) are always visible regardless of status -- they
never went through intake and were never staging.

Override with `include_staging=True` (adds non-promoted batch_id
rows) or `status_filter=[...]` (explicit allowlist; overrides the
default entirely).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg

DEFAULT_LIMIT = 50
HARD_LIMIT = 200

# Statuses that count as intake staging when paired with a non-NULL
# batch_id. Promoted is not in the set: a promoted row has cleared
# stage 2 finalize and belongs in the main library view.
_STAGING_STATUSES: frozenset[str] = frozenset(
    {"pending", "triaging", "soft_accepted", "diagnostic", "rejected", "abandoned"}
)


@dataclass(frozen=True)
class SearchResult:
    entry_id: UUID
    rank: float
    title: str
    avatar_slug: str
    yaw_bin: str | None
    top_tags: tuple[str, ...]
    status: str | None = None
    batch_id: UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": str(self.entry_id),
            "rank": float(self.rank),
            "title": self.title,
            "avatar_slug": self.avatar_slug,
            "yaw_bin": self.yaw_bin,
            "top_tags": list(self.top_tags),
            "status": self.status,
            "batch_id": str(self.batch_id) if self.batch_id else None,
        }


def search(  # noqa: PLR0913
    conn: "psycopg.Connection[object]",
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    include_staging: bool = False,
    status_filter: list[str] | None = None,
    include_legacy: bool = True,
) -> list[SearchResult]:
    """Run the SQL `library_search(query)` function and join in entry
    metadata + top 3 tags per row. Returns rank-ordered list (DESC).

    Parameters
    ----------
    query : str
        Free-text query; passed verbatim to the SQL function.
    limit : int, default 50
        Max rows. Clamped to `HARD_LIMIT` (200).
    include_staging : bool, default False
        When True, also returns intake-staging rows (rows with
        `batch_id IS NOT NULL` and non-promoted `status`).
    status_filter : list[str] | None, default None
        Explicit allowlist of statuses to include. When set, overrides
        the default filter entirely (and `include_staging` is ignored).
    include_legacy : bool, default True
        When True, also returns rows with `status IS NULL` (pre-I3
        entries that never received a status). The I3 migration set
        DEFAULT 'pending' so this should be a no-op in practice;
        retained for forward safety.
    """
    capped = max(1, min(int(limit), HARD_LIMIT))

    where_clauses: list[str] = []
    args: list[Any] = [query]

    if status_filter is not None:
        # Explicit allowlist overrides everything.
        if not status_filter:
            return []
        placeholders = ",".join(["%s"] * len(status_filter))
        where_clauses.append(f"e.status IN ({placeholders})")
        args.extend(status_filter)
    else:
        # INTAKE-009 default: exclude intake-staging rows.
        # Visible rows: batch_id IS NULL (direct register), OR
        #               status = 'promoted' (made it through intake), OR
        #               include_staging (operator opt-in).
        # Plus include_legacy controls status IS NULL visibility.
        clauses: list[str] = ["e.batch_id IS NULL", "e.status = 'promoted'"]
        if include_staging:
            clauses.append(
                f"e.status IN ({','.join(['%s'] * len(_STAGING_STATUSES))})"
            )
            args.extend(sorted(_STAGING_STATUSES))
        if include_legacy:
            clauses.append("e.status IS NULL")
        where_clauses.append("(" + " OR ".join(clauses) + ")")

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    args.append(capped)

    with conn.cursor() as cur:
        cur.execute(
            "WITH ranked AS ("
            "  SELECT entry_id, rank FROM library_search(%s)"
            ") "
            "SELECT r.entry_id, r.rank, e.title, e.avatar_slug, e.yaw_bin, "
            "       e.status, e.batch_id, "
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
            f"{where_sql} "
            "ORDER BY r.rank DESC "
            "LIMIT %s",
            tuple(args),
        )
        rows = cur.fetchall()
    out: list[SearchResult] = []
    for row in rows:
        eid = row[0] if isinstance(row[0], UUID) else UUID(str(row[0]))
        bid = row[6]
        if bid is not None and not isinstance(bid, UUID):
            bid = UUID(str(bid))
        out.append(
            SearchResult(
                entry_id=eid,
                rank=float(row[1]),
                title=row[2] or "",
                avatar_slug=row[3] or "",
                yaw_bin=row[4],
                status=row[5],
                batch_id=bid,
                top_tags=tuple(row[7] or ()),
            )
        )
    return out
