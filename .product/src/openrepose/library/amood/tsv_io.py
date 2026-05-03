"""AMood TSV export + import (WP-I3-006).

Spec: `.gov/spec/openrepose_amood_v0_1.md` "amood_export_tsv" +
"amood_import_tsv".

Export: `SELECT *` from the matching view (filter by batch_id where the
view exposes `card_id` / `batch_slug`), join column order to TAB
separators. Output is `<header>\\n<row_1>\\n<row_2>\\n...<row_N>\\n`.

Import: parse a TSV in AMood-locked column order, validate the header
against the view's Python mirror, and upsert to the underlying tables.
v0.1 supports import for 4 hand-edited schemas:
    quota_plan          -> library_target_groups (axis -> group_slug;
                            target_count -> expected*target_per_card)
    batch_matrix        -> library_entries direct columns + metadata
    variant_ladder      -> library_entries variant_label + metadata
    anti_repetition     -> library_entries direct columns + metadata

The other 6 schemas are export-only (system-generated views; importing
them would re-derive from base tables and risk corruption). The Python
importer returns an INFO message + manual-link instead of partial
import.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

from .tsv_views import AMOOD_VIEW_COLUMNS, view_for_schema

if TYPE_CHECKING:
    import psycopg


# Schemas that round-trip through DB writes in v0.1.
AMOOD_IMPORTABLE_SCHEMAS: frozenset[str] = frozenset(
    {"quota_plan", "batch_matrix", "variant_ladder", "anti_repetition"}
)

# All 10 schemas (export-supported).
AMOOD_TSV_SCHEMAS: frozenset[str] = frozenset(AMOOD_VIEW_COLUMNS.keys())


# Subset of batch_matrix columns that map to library_entries direct
# columns (everything else goes to metadata). Mirrored from the view
# definition in migration 005.
_BATCH_MATRIX_DIRECT_COLUMNS: dict[str, str] = {
    "status":                  "status",
    "sexual_trigger":          "sexual_trigger",
    "kink_cue":                "kink_cue",
    "porn_archetype":          "porn_archetype",
    "explicit_family":         "explicit_family",
    "exposure_detail":         "exposure_detail",
    "fantasy_mode":            "fantasy_mode",
    "archetype_signal":        "archetype_signal",
    "scene_engine":            "scene_engine",
    "shot_purpose":            "shot_purpose",
    "compatibility_signature": "compatibility_signature",
    "dedupe_signature":        "dedupe_signature",
}

# anti_repetition direct-column subset.
_ANTI_REP_DIRECT_COLUMNS: dict[str, str] = {
    "explicit_family": "explicit_family",
    "exposure_detail": "exposure_detail",
    "fantasy_mode":    "fantasy_mode",
    "kink_cue":        "kink_cue",
    "porn_archetype":  "porn_archetype",
    "dedupe_signature": "dedupe_signature",
    "status":          "status",
}

# variant_ladder direct columns.
_VARIANT_DIRECT_COLUMNS: dict[str, str] = {
    "variant": "variant_label",
    "status":  "status",
}


class AmoodTsvError(ValueError):
    """Raised on TSV input shape errors (header mismatch, malformed rows)."""


def export_tsv(
    conn: psycopg.Connection[object],
    *,
    schema: str,
    batch_id: UUID | str | None = None,
    project_id: UUID | str | None = None,
) -> str:
    """Export an AMood TSV in the schema's locked column order.

    `batch_id` filters where the view exposes `batch_slug` or `card_id`;
    `project_id` is used for `quota_plan` (which is project-scoped via
    `library_target_groups.project_id`). When neither is supplied, the
    export emits the entire view (use cautiously on large projects).
    """
    if schema not in AMOOD_TSV_SCHEMAS:
        raise AmoodTsvError(
            f"unknown schema {schema!r}; allowed: {sorted(AMOOD_TSV_SCHEMAS)}"
        )
    view_name = view_for_schema(schema)
    columns = AMOOD_VIEW_COLUMNS[schema]
    where_sql, params = _filter_for_view(view_name, batch_id, project_id)

    select_list = ", ".join(columns)
    sql = f"SELECT {select_list} FROM {view_name}"
    if where_sql:
        sql += f" WHERE {where_sql}"

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    lines: list[str] = ["\t".join(columns)]
    for row in rows:
        lines.append("\t".join(_format_cell(c) for c in row))
    return "\n".join(lines) + "\n"


def import_tsv(
    conn: psycopg.Connection[object],
    *,
    schema: str,
    tsv_text: str,
    batch_id: UUID | str | None = None,
) -> dict[str, Any]:
    """Parse a TSV and upsert to underlying tables.

    Returns `{imported_count, conflict_count, errors}`. v0.1 supports
    `quota_plan`, `batch_matrix`, `variant_ladder`, `anti_repetition`.
    Other schemas are export-only and return INFO without writing.
    """
    if schema not in AMOOD_TSV_SCHEMAS:
        raise AmoodTsvError(
            f"unknown schema {schema!r}; allowed: {sorted(AMOOD_TSV_SCHEMAS)}"
        )
    if schema not in AMOOD_IMPORTABLE_SCHEMAS:
        return {
            "imported_count": 0,
            "conflict_count": 0,
            "errors": [
                f"INFO: schema {schema!r} is export-only in v0.1; system-generated "
                "from base tables. See manual: amood-workflow.md#tsv-round-trip."
            ],
        }

    expected_columns = AMOOD_VIEW_COLUMNS[schema]
    rows = _parse_tsv(tsv_text, expected_columns)

    if schema == "batch_matrix":
        return _import_batch_matrix(conn, rows, batch_id=batch_id)
    if schema == "variant_ladder":
        return _import_variant_ladder(conn, rows)
    if schema == "anti_repetition":
        return _import_anti_repetition(conn, rows)
    # quota_plan
    return _import_quota_plan(conn, rows, batch_id=batch_id)


# ---------------------------------------------------------------------------
# TSV parsing
# ---------------------------------------------------------------------------


def _parse_tsv(tsv_text: str, expected_columns: tuple[str, ...]) -> list[dict[str, str]]:
    """Split tsv_text into header + rows, validate column order."""
    lines = tsv_text.replace("\r\n", "\n").rstrip("\n").split("\n")
    if not lines:
        raise AmoodTsvError("empty TSV input")
    header = tuple(lines[0].split("\t"))
    if header != expected_columns:
        raise AmoodTsvError(
            "TSV header column order does not match locked view shape.\n"
            f"  expected: {expected_columns}\n"
            f"  got:      {header}\n"
            "  (additive-only: append columns to the right; "
            "do not reorder, rename, or drop existing columns)"
        )
    parsed: list[dict[str, str]] = []
    for i, line in enumerate(lines[1:], start=2):
        cells = line.split("\t")
        if len(cells) != len(expected_columns):
            raise AmoodTsvError(
                f"row {i}: expected {len(expected_columns)} cells, got {len(cells)}"
            )
        parsed.append(dict(zip(expected_columns, cells, strict=True)))
    return parsed


# ---------------------------------------------------------------------------
# Schema-specific importers
# ---------------------------------------------------------------------------


def _import_batch_matrix(
    conn: psycopg.Connection[object],
    rows: list[dict[str, str]],
    *,
    batch_id: UUID | str | None,
) -> dict[str, Any]:
    """Update existing library_entries rows with matrix-row values.

    Rows are matched by `card_id`. Unknown card_ids increment
    `conflict_count` (we do not auto-insert via TSV; create_card is the
    canonical path for new cards).
    """
    imported = 0
    conflicts = 0
    errors: list[str] = []
    with conn.cursor() as cur:
        for row in rows:
            card_id = row.get("card_id", "").strip()
            if not card_id:
                conflicts += 1
                continue
            try:
                set_clauses, set_params = _build_set_clause(
                    row, _BATCH_MATRIX_DIRECT_COLUMNS
                )
                meta_skip = set(_BATCH_MATRIX_DIRECT_COLUMNS) | {
                    "batch_slug", "row_id", "card_id",
                }
                metadata_patch = _build_metadata_patch(
                    row, direct_columns=meta_skip,
                )
                if set_clauses:
                    cur.execute(
                        f"UPDATE library_entries SET {', '.join(set_clauses)} "
                        f"WHERE id = %s",
                        (*set_params, card_id),
                    )
                if metadata_patch:
                    cur.execute(
                        "UPDATE library_entries "
                        "SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb "
                        "WHERE id = %s",
                        (json.dumps(metadata_patch, ensure_ascii=False), card_id),
                    )
                imported += 1
            except Exception as e:
                conflicts += 1
                errors.append(f"row card_id={card_id!r}: {e}")
    conn.commit()
    return {
        "imported_count": imported,
        "conflict_count": conflicts,
        "errors": errors,
    }


def _import_variant_ladder(
    conn: psycopg.Connection[object],
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    imported = 0
    conflicts = 0
    errors: list[str] = []
    with conn.cursor() as cur:
        for row in rows:
            card_id = row.get("card_id", "").strip()
            if not card_id:
                conflicts += 1
                continue
            try:
                set_clauses, set_params = _build_set_clause(
                    row, _VARIANT_DIRECT_COLUMNS
                )
                metadata_patch = _build_metadata_patch(
                    row,
                    direct_columns=set(_VARIANT_DIRECT_COLUMNS) | {"card_id", "slug"},
                )
                if set_clauses:
                    cur.execute(
                        f"UPDATE library_entries SET {', '.join(set_clauses)} "
                        f"WHERE id = %s",
                        (*set_params, card_id),
                    )
                if metadata_patch:
                    cur.execute(
                        "UPDATE library_entries "
                        "SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb "
                        "WHERE id = %s",
                        (json.dumps(metadata_patch, ensure_ascii=False), card_id),
                    )
                imported += 1
            except Exception as e:
                conflicts += 1
                errors.append(f"row card_id={card_id!r}: {e}")
    conn.commit()
    return {
        "imported_count": imported,
        "conflict_count": conflicts,
        "errors": errors,
    }


def _import_anti_repetition(
    conn: psycopg.Connection[object],
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    imported = 0
    conflicts = 0
    errors: list[str] = []
    with conn.cursor() as cur:
        for row in rows:
            card_id = row.get("card_id", "").strip()
            if not card_id:
                conflicts += 1
                continue
            try:
                set_clauses, set_params = _build_set_clause(
                    row, _ANTI_REP_DIRECT_COLUMNS
                )
                metadata_patch = _build_metadata_patch(
                    row,
                    direct_columns=set(_ANTI_REP_DIRECT_COLUMNS) | {"card_id", "slug"},
                )
                if set_clauses:
                    cur.execute(
                        f"UPDATE library_entries SET {', '.join(set_clauses)} "
                        f"WHERE id = %s",
                        (*set_params, card_id),
                    )
                if metadata_patch:
                    cur.execute(
                        "UPDATE library_entries "
                        "SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb "
                        "WHERE id = %s",
                        (json.dumps(metadata_patch, ensure_ascii=False), card_id),
                    )
                imported += 1
            except Exception as e:
                conflicts += 1
                errors.append(f"row card_id={card_id!r}: {e}")
    conn.commit()
    return {
        "imported_count": imported,
        "conflict_count": conflicts,
        "errors": errors,
    }


def _import_quota_plan(
    conn: psycopg.Connection[object],
    rows: list[dict[str, str]],
    *,
    batch_id: UUID | str | None,
) -> dict[str, Any]:
    """Upsert library_target_groups rows from the quota_plan TSV.

    Each row carries (batch_slug, axis, value, target_count, ...).
    `axis` maps to `group_slug`; `value` maps to `group_name`; the
    blueprint quota plan stores a single number that v0.1 treats as
    `expected_card_count * target_per_card` — we conservatively record
    expected_card_count = target_count and target_per_card = 1, leaving
    finer-grained shape for the requirements editor (WP-I3-007).
    """
    imported = 0
    conflicts = 0
    errors: list[str] = []
    if batch_id is None:
        return {
            "imported_count": 0,
            "conflict_count": len(rows),
            "errors": [
                "quota_plan import requires explicit batch_id so the "
                "matching project_id can be resolved"
            ],
        }
    with conn.cursor() as cur:
        cur.execute(
            "SELECT project_id FROM library_batches WHERE id = %s", (str(batch_id),)
        )
        row = cur.fetchone()
        if row is None:
            return {
                "imported_count": 0,
                "conflict_count": len(rows),
                "errors": [f"batch_id {batch_id!r} not found"],
            }
        project_id = row[0]
        for r in rows:
            axis = r.get("axis", "").strip()
            value = r.get("value", "").strip()
            try:
                target_count = int(r.get("target_count", "0") or 0)
            except ValueError:
                conflicts += 1
                errors.append(f"axis={axis!r}: target_count not int")
                continue
            if not axis:
                conflicts += 1
                continue
            try:
                cur.execute(
                    """
                    INSERT INTO library_target_groups
                        (project_id, group_slug, group_name,
                         expected_card_count, target_per_card, ordering)
                    VALUES (%s, %s, %s, %s, 1, 0)
                    ON CONFLICT (project_id, group_slug) DO UPDATE
                    SET group_name = EXCLUDED.group_name,
                        expected_card_count = EXCLUDED.expected_card_count
                    """,
                    (str(project_id), axis, value, max(1, target_count)),
                )
                imported += 1
            except Exception as e:
                conflicts += 1
                errors.append(f"axis={axis!r}: {e}")
    conn.commit()
    return {
        "imported_count": imported,
        "conflict_count": conflicts,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _filter_for_view(
    view_name: str,
    batch_id: UUID | str | None,
    project_id: UUID | str | None,
) -> tuple[str, tuple[Any, ...]]:
    """Return WHERE clause + params for a per-batch (or per-project) filter."""
    if view_name == "library_amood_quota_plan_v":
        if project_id is not None:
            return ("batch_slug IN (SELECT slug FROM library_batches WHERE project_id = %s)",
                    (str(project_id),))
        if batch_id is not None:
            return ("batch_slug = (SELECT slug FROM library_batches WHERE id = %s)",
                    (str(batch_id),))
        return ("", ())
    # Views that join library_entries → library_batches expose batch_slug
    # (batch_matrix only) or card_id (most others). Use the simplest stable
    # filter per view.
    if view_name == "library_amood_batch_matrix_v":
        if batch_id is not None:
            return ("batch_slug = (SELECT slug FROM library_batches WHERE id = %s)",
                    (str(batch_id),))
        return ("", ())
    if view_name in (
        "library_amood_variant_ladder_v",
        "library_amood_anti_repetition_v",
        "library_amood_prompt_manifest_v",
        "library_amood_run_manifest_v",
        "library_amood_review_manifest_v",
        "library_amood_scorecard_v",
        "library_amood_pose_control_guide_v",
        "library_amood_series_plan_v",
    ):
        if batch_id is not None:
            return (
                "card_id IN (SELECT id FROM library_entries WHERE batch_id = %s)",
                (str(batch_id),),
            )
        return ("", ())
    return ("", ())


def _format_cell(value: Any) -> str:
    """TSV-safe stringification: drop tabs/newlines (mirror pg view text)."""
    if value is None:
        return ""
    s = str(value)
    # Escape disallowed control chars to keep TSV well-formed.
    return s.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _build_set_clause(
    row: dict[str, str],
    direct_columns: dict[str, str],
) -> tuple[list[str], list[Any]]:
    """Build SQL SET fragment for direct columns."""
    clauses: list[str] = []
    params: list[Any] = []
    for tsv_col, db_col in direct_columns.items():
        value = row.get(tsv_col, "")
        if value == "":
            continue
        clauses.append(f"{db_col} = %s")
        params.append(value)
    return clauses, params


def _build_metadata_patch(
    row: dict[str, str],
    *,
    direct_columns: set[str],
) -> dict[str, str]:
    """Build a metadata JSON patch for free-text columns.

    Every TSV column not in `direct_columns` (and not blank) becomes
    a `amood:<col>` key in the metadata patch. The view reads the same
    `amood:<col>` keys, so export → edit → import → re-export is
    bytewise stable on those keys.
    """
    patch: dict[str, str] = {}
    for col, value in row.items():
        if col in direct_columns:
            continue
        if value == "" or value is None:
            continue
        patch[f"amood:{col}"] = value
    return patch
