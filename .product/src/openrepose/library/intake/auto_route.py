"""Auto-route deterministic checks for intake_register_output (WP-I3-004).

Spec: `.gov/spec/openrepose_intake_v0_1.md` "Layer 2: Auto-prefilter".

Loads project-scope severity=auto-route rules from `library_rules`,
evaluates each rule's `machine_check_fn` (a SQL boolean expression
referring to `width`, `height`) against the registered output, and
returns a routing decision.

Rules are loaded live on each registration (no in-memory cache in v0.1
per WP-I3-004 Decisions Log; empty rule set is the default until
WP-I3-007 populates rules through the requirements editor).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg


@dataclass
class AutoRouteResult:
    routed: bool
    rule_id: str | None
    bucket: str | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "routed": self.routed,
            "rule_id": self.rule_id,
            "bucket": self.bucket,
            "reason": self.reason,
        }


def run_auto_route(
    conn: "psycopg.Connection[object]",
    *,
    project_id: UUID | str,
    width: int,
    height: int,
) -> AutoRouteResult:
    """Evaluate every project-scope severity=auto-route rule against the
    output dimensions. Returns the first failing rule (most-specific
    fail-fast) or a no-route result.

    `machine_check_fn` is the rule's SQL boolean expression in terms of
    `width` and `height`. Evaluated server-side via a parameterized
    `SELECT (<expr>)` so the existing CHECK-style expressions in the
    requirements spec (`(width = 1080 AND height = 1440)`) work without
    Python-side parsing.
    """
    rules = _load_auto_route_rules(conn, project_id=project_id)
    for rule in rules:
        passed = _evaluate_predicate(conn, rule["machine_check_fn"], width, height)
        if not passed:
            return AutoRouteResult(
                routed=True,
                rule_id=rule["rule_id"],
                bucket=rule["auto_route_to"] or "intermediate_evidence",
                reason=rule["short"],
            )
    return AutoRouteResult(routed=False, rule_id=None, bucket=None, reason=None)


def _load_auto_route_rules(
    conn: "psycopg.Connection[object]",
    *,
    project_id: UUID | str,
) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT rule_id, name, short, machine_check_fn, auto_route_to "
            "FROM library_rules "
            "WHERE scope_type = 'project' "
            "  AND scope_id = %s "
            "  AND severity = 'auto-route' "
            "  AND machine_check_fn IS NOT NULL "
            "ORDER BY rule_id ASC",
            (str(project_id),),
        )
        rows = cur.fetchall()
    return [
        {
            "rule_id": r[0],
            "name": r[1],
            "short": r[2],
            "machine_check_fn": r[3],
            "auto_route_to": r[4],
        }
        for r in rows
    ]


def _evaluate_predicate(
    conn: "psycopg.Connection[object]",
    expr: str,
    width: int,
    height: int,
) -> bool:
    """Evaluate `<expr>` server-side with `width` and `height` as named
    parameters. Returns True when the predicate holds (no auto-route)."""
    sql = f"SELECT ({expr})"
    with conn.cursor() as cur:
        cur.execute(
            "WITH params(width, height) AS (VALUES (%s::int, %s::int)) "
            f"SELECT (SELECT (CASE WHEN ({expr}) THEN TRUE ELSE FALSE END) "
            "        FROM params)",
            (int(width), int(height)),
        )
        row = cur.fetchone()
    return bool(row[0]) if row else False
