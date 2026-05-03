"""CRUD on `library_rules` (project-scoped) + inheritance resolution.

Spec: `.gov/spec/openrepose_requirements_v0_1.md` § "Requirement Anatomy"
and § "Inheritance" (REQ-001: lower scope wins). The same `library_rules`
table is also written by intake auto-route logic (WP-I3-004); commands
+ GUI read either transparently per § "Global vs Project-Scoped Rules".

Project-scoped rule_ids must NOT collide with global families (RUL-,
AMOOD-, INTAKE-, TARGET-, REQ-, SAFE-) — the global registry is repo-wide
governance and only operator-authored governance refactors may extend it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg

from .errors import OpenReposeRequirementsError

_VALID_KINDS = (
    "hard_output", "body", "pose", "face", "crop", "quality",
    "clothing_story", "structural", "custom",
)
_VALID_SEVERITIES = ("auto-route", "block", "warn", "info")
_VALID_SCOPE_TYPES = ("project", "task", "batch", "card")
_GLOBAL_FAMILIES = ("RUL", "AMOOD", "INTAKE", "TARGET", "REQ", "SAFE")


@dataclass
class LibraryRule:
    id: UUID
    rule_id: str
    scope_type: str
    scope_id: UUID
    name: str
    short: str
    severity: str
    manual_link: str | None = None
    machine_check_fn: str | None = None
    auto_route_to: str | None = None
    accept_terms: list[str] | None = None
    reject_terms: list[str] | None = None
    kind: str | None = None
    inherited_from: UUID | None = None
    created_at: datetime | None = None
    last_validated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "rule_id": self.rule_id,
            "scope_type": self.scope_type,
            "scope_id": str(self.scope_id),
            "name": self.name,
            "short": self.short,
            "severity": self.severity,
            "manual_link": self.manual_link,
            "machine_check_fn": self.machine_check_fn,
            "auto_route_to": self.auto_route_to,
            "accept_terms": list(self.accept_terms) if self.accept_terms else None,
            "reject_terms": list(self.reject_terms) if self.reject_terms else None,
            "kind": self.kind,
            "inherited_from": str(self.inherited_from) if self.inherited_from else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_validated_at": (
                self.last_validated_at.isoformat() if self.last_validated_at else None
            ),
        }


def _validate_rule_id_not_global(rule_id: str) -> None:
    family = rule_id.split("-", 1)[0] if "-" in rule_id else rule_id
    if family in _GLOBAL_FAMILIES:
        raise OpenReposeRequirementsError(
            f"rule_id {rule_id!r}: family {family!r} is reserved for global "
            f"governance (.gov/topology.yaml rule_registry). Use a project-scoped "
            f"prefix (e.g. EXP120-RES-001).",
            rule_id="REQ-001",
        )


def _validate_kind(kind: str | None) -> None:
    if kind is not None and kind not in _VALID_KINDS:
        raise OpenReposeRequirementsError(
            f"kind must be one of {_VALID_KINDS}; got {kind!r}",
            rule_id="REQ-003",
        )


def _validate_severity(severity: str) -> None:
    if severity not in _VALID_SEVERITIES:
        raise OpenReposeRequirementsError(
            f"severity must be one of {_VALID_SEVERITIES}; got {severity!r}",
            rule_id="REQ-001",
        )


def _validate_scope_type(scope_type: str) -> None:
    if scope_type not in _VALID_SCOPE_TYPES:
        raise OpenReposeRequirementsError(
            f"scope_type must be one of {_VALID_SCOPE_TYPES}; got {scope_type!r}",
            rule_id="REQ-001",
        )


def create_rule(
    conn: "psycopg.Connection[object]",
    *,
    rule_id: str,
    scope_type: str,
    scope_id: UUID | str,
    name: str,
    short: str,
    severity: str,
    kind: str | None = None,
    manual_link: str | None = None,
    machine_check_fn: str | None = None,
    auto_route_to: str | None = None,
    accept_terms: list[str] | None = None,
    reject_terms: list[str] | None = None,
    inherited_from: UUID | str | None = None,
) -> LibraryRule:
    if not rule_id:
        raise OpenReposeRequirementsError("rule_id is required")
    _validate_rule_id_not_global(rule_id)
    _validate_scope_type(scope_type)
    _validate_severity(severity)
    _validate_kind(kind)
    if not name or not short:
        raise OpenReposeRequirementsError("name and short are required")

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_rules ("
            "  rule_id, scope_type, scope_id, name, short, severity, "
            "  manual_link, machine_check_fn, auto_route_to, "
            "  accept_terms, reject_terms, kind, inherited_from"
            ") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "RETURNING id, rule_id, scope_type, scope_id, name, short, severity, "
            "          manual_link, machine_check_fn, auto_route_to, "
            "          accept_terms, reject_terms, kind, inherited_from, "
            "          created_at, last_validated_at",
            (
                rule_id, scope_type, str(scope_id), name, short, severity,
                manual_link, machine_check_fn, auto_route_to,
                accept_terms, reject_terms, kind,
                str(inherited_from) if inherited_from else None,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return _row_to_rule(row)


def update_rule(
    conn: "psycopg.Connection[object]",
    *,
    rule_uuid: UUID | str,
    name: str | None = None,
    short: str | None = None,
    severity: str | None = None,
    kind: str | None = None,
    manual_link: str | None = None,
    machine_check_fn: str | None = None,
    auto_route_to: str | None = None,
    accept_terms: list[str] | None = None,
    reject_terms: list[str] | None = None,
    last_validated_at: datetime | None = None,
) -> LibraryRule:
    """Partial update; pass only fields you want to change.

    Note: pass-through Nones do NOT clear fields. v0.1 has no field-clear
    operation (a delete + re-create achieves the same end). Documented as
    intentional simplification; v0.2 may add explicit clear semantics.
    """
    if severity is not None:
        _validate_severity(severity)
    if kind is not None:
        _validate_kind(kind)

    sets: list[str] = []
    args: list[Any] = []
    for col, val in [
        ("name", name), ("short", short), ("severity", severity),
        ("manual_link", manual_link), ("machine_check_fn", machine_check_fn),
        ("auto_route_to", auto_route_to), ("accept_terms", accept_terms),
        ("reject_terms", reject_terms), ("kind", kind),
        ("last_validated_at", last_validated_at),
    ]:
        if val is not None:
            sets.append(f"{col} = %s")
            args.append(val)
    if not sets:
        raise OpenReposeRequirementsError("update_rule called with no fields to change")
    args.append(str(rule_uuid))

    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE library_rules SET {', '.join(sets)} "
            "WHERE id = %s "
            "RETURNING id, rule_id, scope_type, scope_id, name, short, severity, "
            "          manual_link, machine_check_fn, auto_route_to, "
            "          accept_terms, reject_terms, kind, inherited_from, "
            "          created_at, last_validated_at",
            args,
        )
        row = cur.fetchone()
        if row is None:
            raise OpenReposeRequirementsError(f"library_rules row {rule_uuid} not found")
    conn.commit()
    return _row_to_rule(row)


def delete_rule(
    conn: "psycopg.Connection[object]",
    *,
    rule_uuid: UUID | str,
) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM library_rules WHERE id = %s", (str(rule_uuid),))
        deleted = cur.rowcount
    conn.commit()
    return deleted > 0


def dump_rules(
    conn: "psycopg.Connection[object]",
    *,
    scope_type: str | None = None,
    scope_id: UUID | str | None = None,
    rule_id: str | None = None,
) -> list[LibraryRule]:
    """Return rules at a given scope (or all rules if no filter)."""
    where: list[str] = []
    args: list[Any] = []
    if scope_type is not None:
        _validate_scope_type(scope_type)
        where.append("scope_type = %s")
        args.append(scope_type)
    if scope_id is not None:
        where.append("scope_id = %s")
        args.append(str(scope_id))
    if rule_id is not None:
        where.append("rule_id = %s")
        args.append(rule_id)
    sql = (
        "SELECT id, rule_id, scope_type, scope_id, name, short, severity, "
        "       manual_link, machine_check_fn, auto_route_to, "
        "       accept_terms, reject_terms, kind, inherited_from, "
        "       created_at, last_validated_at "
        "FROM library_rules"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY rule_id, scope_type"
    with conn.cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    return [_row_to_rule(r) for r in rows]


def get_rule_with_inheritance(
    conn: "psycopg.Connection[object]",
    *,
    rule_id: str,
    scope_type: str,
    scope_id: UUID | str,
    project_id: UUID | str,
) -> list[LibraryRule]:
    """Resolve effective rule(s) at the given scope walking the inheritance chain.

    Returns a list ordered from most-specific (the queried scope) to least-specific
    (project). Per REQ-001: lower scope wins on conflict; the first entry is the
    effective rule. Project-scoped rules with the same `rule_id` at higher scopes
    are still included so the caller can render the inheritance chain.

    v0.1 walks only project ↔ scope (intermediate task / batch scope rules with
    matching rule_id are joined into the chain when present; full hierarchy walk
    is delegated to the SQL query).
    """
    _validate_scope_type(scope_type)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, rule_id, scope_type, scope_id, name, short, severity, "
            "       manual_link, machine_check_fn, auto_route_to, "
            "       accept_terms, reject_terms, kind, inherited_from, "
            "       created_at, last_validated_at "
            "FROM library_rules "
            "WHERE rule_id = %s "
            "  AND ( "
            "       (scope_type = %s AND scope_id = %s) "
            "    OR (scope_type = 'project' AND scope_id = %s) "
            "  ) "
            "ORDER BY CASE scope_type "
            "          WHEN 'card' THEN 1 "
            "          WHEN 'batch' THEN 2 "
            "          WHEN 'task' THEN 3 "
            "          WHEN 'project' THEN 4 "
            "         END",
            (rule_id, scope_type, str(scope_id), str(project_id)),
        )
        rows = cur.fetchall()
    return [_row_to_rule(r) for r in rows]


def _row_to_rule(row: Any) -> LibraryRule:
    return LibraryRule(
        id=row[0],
        rule_id=row[1],
        scope_type=row[2],
        scope_id=row[3],
        name=row[4],
        short=row[5],
        severity=row[6],
        manual_link=row[7],
        machine_check_fn=row[8],
        auto_route_to=row[9],
        accept_terms=list(row[10]) if row[10] else None,
        reject_terms=list(row[11]) if row[11] else None,
        kind=row[12],
        inherited_from=row[13],
        created_at=row[14],
        last_validated_at=row[15],
    )
