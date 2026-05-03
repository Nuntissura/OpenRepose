"""Accepted-set diversity audit (WP-I3-006).

Spec: `.gov/spec/openrepose_amood_v0_1.md` "accepted_set_audit".

Computes per-axis realized coverage on the accepted set of a batch (or
project) and writes one `library_diversity_audits` row per axis. The
priority flag is computed from the AMood blueprint thresholds:

    >= 0.75 -> ok
    0.50..0.74 -> watch
    < 0.50 -> priority

Realized coverage is defined as:

    distinct_accepted_axis_values / max_distinct_axis_values_seen_in_project

For v0.1 the denominator is the count of distinct values for that axis
across all cards in the project (any status); the numerator is the
count of distinct values across cards with status='promoted'. This
matches the blueprint intent "how much of the planned diversity has
been satisfied" without requiring an explicit quota plan.

13 amood:* tag axes audited per spec:
    explicit_family, pose_family, orientation, wardrobe_state,
    held_object, support_object, setting_family, lighting_family,
    camera_family, gaze, mouth_tongue, palette_family, accent_color.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg


_AUDITED_AXES: tuple[str, ...] = (
    "explicit_family",
    "pose_family",
    "orientation",
    "wardrobe_state",
    "held_object",
    "support_object",
    "setting_family",
    "lighting_family",
    "camera_family",
    "gaze",
    "mouth_tongue",
    "palette_family",
    "accent_color",
)


_OK_THRESHOLD = 0.75
_WATCH_LOWER = 0.50


class AcceptedSetAuditError(ValueError):
    """Raised when audit input is malformed or batch is missing."""


@dataclass
class AxisCoverage:
    axis: str
    realized_coverage: float
    accepted_distinct: int
    project_distinct: int
    priority_flag: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "realized_coverage": self.realized_coverage,
            "accepted_distinct": self.accepted_distinct,
            "project_distinct": self.project_distinct,
            "priority_flag": self.priority_flag,
        }


@dataclass
class AcceptedSetAuditResult:
    batch_id: UUID
    axes: list[AxisCoverage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": str(self.batch_id),
            "axes": [a.to_dict() for a in self.axes],
        }


def compute_realized_coverage(
    accepted_distinct: int,
    project_distinct: int,
) -> float:
    """Return the realized-coverage fraction for one axis.

    Matches the blueprint shape: numerator = distinct accepted axis
    values; denominator = max distinct axis values seen in project.
    Returns 0.0 when the denominator is 0 (no cards in project use
    that axis yet), which surfaces as `priority` after `priority_for`.
    """
    if project_distinct <= 0:
        return 0.0
    return accepted_distinct / project_distinct


def priority_for(coverage: float) -> str:
    if coverage >= _OK_THRESHOLD:
        return "ok"
    if coverage >= _WATCH_LOWER:
        return "watch"
    return "priority"


def accepted_set_audit(
    conn: psycopg.Connection[object],
    *,
    batch_id: UUID | str,
) -> AcceptedSetAuditResult:
    """Compute coverage for all 13 audited axes and persist the rows.

    Writes one `library_diversity_audits` row per axis (axis +
    realized_coverage + priority_flag) keyed by batch_id with the
    current timestamp; old audit rows are kept (they are time-series).
    """
    project_id = _resolve_project_id_for_batch(conn, batch_id)
    if project_id is None:
        raise AcceptedSetAuditError(f"batch_id {batch_id!r} not found")

    axes: list[AxisCoverage] = []
    with conn.cursor() as cur:
        for axis in _AUDITED_AXES:
            tag_prefix = f"amood:{axis}:"
            cur.execute(
                """
                SELECT
                    COUNT(DISTINCT t.name) FILTER (
                        WHERE e.status = 'promoted'
                    ) AS accepted_distinct,
                    COUNT(DISTINCT t.name)        AS project_distinct
                FROM library_entries e
                JOIN library_batches  b ON b.id = e.batch_id
                JOIN entry_tags       et ON et.entry_id = e.id
                JOIN tags             t  ON t.id = et.tag_id
                WHERE b.project_id = %s
                  AND t.name LIKE %s
                """,
                (str(project_id), f"{tag_prefix}%"),
            )
            row = cur.fetchone() or (0, 0)
            accepted_distinct = int(row[0] or 0)
            project_distinct = int(row[1] or 0)
            coverage = compute_realized_coverage(accepted_distinct, project_distinct)
            flag = priority_for(coverage)
            axes.append(
                AxisCoverage(
                    axis=axis,
                    realized_coverage=coverage,
                    accepted_distinct=accepted_distinct,
                    project_distinct=project_distinct,
                    priority_flag=flag,
                )
            )
            cur.execute(
                """
                INSERT INTO library_diversity_audits
                    (batch_id, axis, realized_coverage, priority_flag, details_json)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (
                    str(batch_id),
                    axis,
                    coverage,
                    flag,
                    _json_dumps(
                        {
                            "accepted_distinct": accepted_distinct,
                            "project_distinct": project_distinct,
                        }
                    ),
                ),
            )
    conn.commit()
    return AcceptedSetAuditResult(
        batch_id=UUID(str(batch_id)) if not isinstance(batch_id, UUID) else batch_id,
        axes=axes,
    )


def _resolve_project_id_for_batch(
    conn: psycopg.Connection[object],
    batch_id: UUID | str,
) -> UUID | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT project_id FROM library_batches WHERE id = %s",
            (str(batch_id),),
        )
        row = cur.fetchone()
    return row[0] if row else None


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
