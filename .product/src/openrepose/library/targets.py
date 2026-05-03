"""Target tree CRUD + counter rollup (WP-I3-007).

Spec: `.gov/spec/openrepose_requirements_v0_1.md` § "Target Tree" + § "Counters
and Satisfaction Semantics". The schema is created by migration 004
(`library_target_groups`, `library_target_cards`, `library_target_card_counts`
view); this module exposes the Python surface the dispatcher uses to
manipulate it and roll counters up to group + project scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg

from .requirements.errors import OpenReposeRequirementsError


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LibraryTargetGroup:
    id: UUID
    project_id: UUID
    group_slug: str
    group_name: str
    expected_card_count: int
    target_per_card: int
    ordering: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "slug": self.group_slug,
            "name": self.group_name,
            "expected_card_count": self.expected_card_count,
            "target_per_card": self.target_per_card,
            "ordering": self.ordering,
        }


@dataclass
class LibraryTargetCard:
    id: UUID
    group_id: UUID
    card_slug: str
    card_id: UUID | None
    target_promoted: int
    stability_target: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "group_id": str(self.group_id),
            "card_slug": self.card_slug,
            "card_id": str(self.card_id) if self.card_id else None,
            "target_promoted": self.target_promoted,
            "stability_target": self.stability_target,
        }


@dataclass
class TargetSummary:
    """Roll-up at any scope. Counters are zero when no outputs exist yet."""
    scope_type: str  # 'project' | 'group' | 'card'
    scope_id: str
    target_promoted: int
    promoted: int
    pending: int
    triaging: int
    soft_accepted: int
    rejected: int
    diagnostic: int
    abandoned: int

    @property
    def in_flight(self) -> int:
        return self.pending + self.triaging + self.soft_accepted

    @property
    def gap(self) -> int:
        return max(0, self.target_promoted - self.promoted)

    @property
    def forecast_ok(self) -> bool:
        return self.in_flight >= self.gap

    @property
    def count_satisfied(self) -> bool:
        return self.gap == 0

    def to_dict(self, *, quota_satisfied: bool = False) -> dict[str, Any]:
        # quota_satisfied is computed by AMood diversity audit (out of scope
        # for this WP); default False so v0.1 surfaces just the count side.
        return {
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "target_promoted": self.target_promoted,
            "promoted": self.promoted,
            "pending": self.pending,
            "triaging": self.triaging,
            "soft_accepted": self.soft_accepted,
            "rejected": self.rejected,
            "diagnostic": self.diagnostic,
            "abandoned": self.abandoned,
            "in_flight": self.in_flight,
            "gap": self.gap,
            "forecast_ok": self.forecast_ok,
            "count_satisfied": self.count_satisfied,
            "quota_satisfied": quota_satisfied,
            "fully_satisfied": self.count_satisfied and quota_satisfied,
        }


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------


def set_target_tree(
    conn: "psycopg.Connection[object]",
    *,
    project_id: UUID | str,
    groups: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create or replace the target tree for a project.

    Each input group dict has keys: slug, name, expected_card_count,
    target_per_card, ordering. Optionally `target_per_card_override` may
    be supplied per-card later via `card_target_override`; v0.1 keeps it
    flat: every card in a group inherits `group.target_per_card`.

    Replaces the existing tree atomically (DELETE + INSERT in one tx).
    Pre-seeds `library_target_cards` with `<slug>-<NN>` from 1..expected_card_count
    so counters can roll up immediately even before cards are created.
    """
    if not groups:
        # Allow an explicit empty tree (e.g. brand-new project).
        groups = []

    pid = str(project_id)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM library_target_groups WHERE project_id = %s", (pid,))
        created_groups: list[LibraryTargetGroup] = []
        created_cards: list[LibraryTargetCard] = []
        for g in groups:
            for required in ("slug", "name", "expected_card_count", "target_per_card"):
                if required not in g:
                    raise OpenReposeRequirementsError(
                        f"target group missing required field: {required!r}",
                        rule_id="REQ-001",
                    )
            if g["expected_card_count"] <= 0:
                raise OpenReposeRequirementsError(
                    "expected_card_count must be > 0 (CHECK constraint enforced)",
                    rule_id="REQ-001",
                )
            if g["target_per_card"] <= 0:
                raise OpenReposeRequirementsError(
                    "target_per_card must be > 0 (CHECK constraint enforced)",
                    rule_id="REQ-001",
                )
            cur.execute(
                "INSERT INTO library_target_groups "
                "(project_id, group_slug, group_name, expected_card_count, target_per_card, ordering) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "RETURNING id, project_id, group_slug, group_name, "
                "          expected_card_count, target_per_card, ordering",
                (
                    pid, g["slug"], g["name"],
                    int(g["expected_card_count"]),
                    int(g["target_per_card"]),
                    int(g.get("ordering", 0)),
                ),
            )
            row = cur.fetchone()
            group = LibraryTargetGroup(
                id=row[0], project_id=row[1], group_slug=row[2], group_name=row[3],
                expected_card_count=row[4], target_per_card=row[5], ordering=row[6],
            )
            created_groups.append(group)

            # Pre-seed N target cards: <slug>-01 .. <slug>-NN.
            for n in range(1, group.expected_card_count + 1):
                card_slug = f"{group.group_slug}-{n:02d}"
                cur.execute(
                    "INSERT INTO library_target_cards "
                    "(group_id, card_slug, target_promoted, stability_target) "
                    "VALUES (%s, %s, %s, %s) "
                    "RETURNING id, group_id, card_slug, card_id, "
                    "          target_promoted, stability_target",
                    (str(group.id), card_slug, group.target_per_card, 4),
                )
                crow = cur.fetchone()
                created_cards.append(LibraryTargetCard(
                    id=crow[0], group_id=crow[1], card_slug=crow[2], card_id=crow[3],
                    target_promoted=crow[4], stability_target=crow[5],
                ))
    conn.commit()
    return {
        "groups": [g.to_dict() for g in created_groups],
        "cards": [c.to_dict() for c in created_cards],
    }


# ---------------------------------------------------------------------------
# Read + roll-up
# ---------------------------------------------------------------------------


def list_groups(
    conn: "psycopg.Connection[object]",
    *,
    project_id: UUID | str,
) -> list[LibraryTargetGroup]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, project_id, group_slug, group_name, "
            "       expected_card_count, target_per_card, ordering "
            "FROM library_target_groups "
            "WHERE project_id = %s "
            "ORDER BY ordering, group_slug",
            (str(project_id),),
        )
        rows = cur.fetchall()
    return [
        LibraryTargetGroup(
            id=r[0], project_id=r[1], group_slug=r[2], group_name=r[3],
            expected_card_count=r[4], target_per_card=r[5], ordering=r[6],
        )
        for r in rows
    ]


def list_cards(
    conn: "psycopg.Connection[object]",
    *,
    group_id: UUID | str,
) -> list[LibraryTargetCard]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, group_id, card_slug, card_id, "
            "       target_promoted, stability_target "
            "FROM library_target_cards "
            "WHERE group_id = %s "
            "ORDER BY card_slug",
            (str(group_id),),
        )
        rows = cur.fetchall()
    return [
        LibraryTargetCard(
            id=r[0], group_id=r[1], card_slug=r[2], card_id=r[3],
            target_promoted=r[4], stability_target=r[5],
        )
        for r in rows
    ]


def project_summary(
    conn: "psycopg.Connection[object]",
    *,
    project_id: UUID | str,
) -> TargetSummary:
    """Roll up `library_target_card_counts` to project scope."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT "
            "  COALESCE(SUM(tc.target_promoted), 0) AS target_promoted, "
            "  COALESCE(SUM(c.promoted_count), 0) AS promoted, "
            "  COALESCE(SUM(c.pending_count), 0) AS pending, "
            "  COALESCE(SUM(c.triaging_count), 0) AS triaging, "
            "  COALESCE(SUM(c.soft_accepted_count), 0) AS soft_accepted, "
            "  COALESCE(SUM(c.rejected_count), 0) AS rejected, "
            "  COALESCE(SUM(c.diagnostic_count), 0) AS diagnostic, "
            "  COALESCE(SUM(c.abandoned_count), 0) AS abandoned "
            "FROM library_target_groups g "
            "JOIN library_target_cards tc ON tc.group_id = g.id "
            "LEFT JOIN library_target_card_counts c ON c.target_card_id = tc.id "
            "WHERE g.project_id = %s",
            (str(project_id),),
        )
        row = cur.fetchone()
    return TargetSummary(
        scope_type="project",
        scope_id=str(project_id),
        target_promoted=int(row[0]),
        promoted=int(row[1]),
        pending=int(row[2]),
        triaging=int(row[3]),
        soft_accepted=int(row[4]),
        rejected=int(row[5]),
        diagnostic=int(row[6]),
        abandoned=int(row[7]),
    )


def group_summary(
    conn: "psycopg.Connection[object]",
    *,
    group_id: UUID | str,
) -> TargetSummary:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT "
            "  COALESCE(SUM(tc.target_promoted), 0) AS target_promoted, "
            "  COALESCE(SUM(c.promoted_count), 0) AS promoted, "
            "  COALESCE(SUM(c.pending_count), 0) AS pending, "
            "  COALESCE(SUM(c.triaging_count), 0) AS triaging, "
            "  COALESCE(SUM(c.soft_accepted_count), 0) AS soft_accepted, "
            "  COALESCE(SUM(c.rejected_count), 0) AS rejected, "
            "  COALESCE(SUM(c.diagnostic_count), 0) AS diagnostic, "
            "  COALESCE(SUM(c.abandoned_count), 0) AS abandoned "
            "FROM library_target_cards tc "
            "LEFT JOIN library_target_card_counts c ON c.target_card_id = tc.id "
            "WHERE tc.group_id = %s",
            (str(group_id),),
        )
        row = cur.fetchone()
    return TargetSummary(
        scope_type="group",
        scope_id=str(group_id),
        target_promoted=int(row[0]),
        promoted=int(row[1]),
        pending=int(row[2]),
        triaging=int(row[3]),
        soft_accepted=int(row[4]),
        rejected=int(row[5]),
        diagnostic=int(row[6]),
        abandoned=int(row[7]),
    )


def card_summary(
    conn: "psycopg.Connection[object]",
    *,
    target_card_id: UUID | str,
) -> TargetSummary:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tc.target_promoted, "
            "       COALESCE(c.promoted_count, 0), "
            "       COALESCE(c.pending_count, 0), "
            "       COALESCE(c.triaging_count, 0), "
            "       COALESCE(c.soft_accepted_count, 0), "
            "       COALESCE(c.rejected_count, 0), "
            "       COALESCE(c.diagnostic_count, 0), "
            "       COALESCE(c.abandoned_count, 0) "
            "FROM library_target_cards tc "
            "LEFT JOIN library_target_card_counts c ON c.target_card_id = tc.id "
            "WHERE tc.id = %s",
            (str(target_card_id),),
        )
        row = cur.fetchone()
        if row is None:
            raise OpenReposeRequirementsError(
                f"library_target_cards row {target_card_id} not found",
                rule_id="REQ-001",
            )
    return TargetSummary(
        scope_type="card",
        scope_id=str(target_card_id),
        target_promoted=int(row[0]),
        promoted=int(row[1]),
        pending=int(row[2]),
        triaging=int(row[3]),
        soft_accepted=int(row[4]),
        rejected=int(row[5]),
        diagnostic=int(row[6]),
        abandoned=int(row[7]),
    )


def target_recount(
    conn: "psycopg.Connection[object]",
    *,
    scope_type: str,
    scope_id: UUID | str,
) -> TargetSummary:
    """Force a re-aggregation. Since v0.1 reads from a live VIEW, this is
    just a dispatcher of the same scope query — exposed as its own command
    so a future materialized-view variant has a hook point."""
    if scope_type == "project":
        return project_summary(conn, project_id=scope_id)
    if scope_type == "group":
        return group_summary(conn, group_id=scope_id)
    if scope_type == "card":
        return card_summary(conn, target_card_id=scope_id)
    raise OpenReposeRequirementsError(
        f"target_recount: scope_type must be project|group|card; got {scope_type!r}",
        rule_id="REQ-001",
    )


def state_targets_block(
    conn: "psycopg.Connection[object]",
    *,
    project_id: UUID | str | None,
    project_slug: str | None = None,
) -> dict[str, Any]:
    """Build the `state.library.targets` block for a given project.

    Returns a dict shaped per spec § "State Surface". `active_task` /
    `active_card` are populated by the caller (this WP only fills the
    project + groups levels). Returns an empty skeleton when no project.
    """
    if project_id is None:
        return {
            "project": None,
            "groups": [],
            "active_task": None,
            "active_card": None,
        }

    summary = project_summary(conn, project_id=project_id)
    groups = list_groups(conn, project_id=project_id)
    group_blocks = []
    for g in groups:
        gs = group_summary(conn, group_id=g.id)
        # Per-group stable / complete card counts.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT "
                "  COUNT(*) FILTER (WHERE c.promoted_count >= tc.stability_target) AS stable_cards, "
                "  COUNT(*) FILTER (WHERE c.promoted_count >= tc.target_promoted) AS complete_cards, "
                "  COUNT(*) AS created_cards "
                "FROM library_target_cards tc "
                "LEFT JOIN library_target_card_counts c ON c.target_card_id = tc.id "
                "WHERE tc.group_id = %s",
                (str(g.id),),
            )
            stable, complete, created = cur.fetchone()
        group_blocks.append({
            "slug": g.group_slug,
            "name": g.group_name,
            "target_promoted": gs.target_promoted,
            "promoted": gs.promoted,
            "gap": gs.gap,
            "stable_cards": int(stable or 0),
            "complete_cards": int(complete or 0),
            "expected_cards": g.expected_card_count,
            "created_cards": int(created or 0),
        })

    return {
        "project": {
            "id": str(project_id),
            "slug": project_slug,
            "target_promoted": summary.target_promoted,
            "promoted": summary.promoted,
            "gap": summary.gap,
            "in_flight": summary.in_flight,
            "forecast_ok": summary.forecast_ok,
            "count_satisfied": summary.count_satisfied,
            "quota_satisfied": False,  # AMood-side; out of WP-I3-007 scope
            "fully_satisfied": False,
        },
        "groups": group_blocks,
        "active_task": None,
        "active_card": None,
    }
