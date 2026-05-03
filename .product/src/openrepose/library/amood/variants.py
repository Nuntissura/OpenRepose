"""AMood variant ladder (WP-I3-006).

Spec: `.gov/spec/openrepose_amood_v0_1.md` "library_create_variants".

Spawns child library_entries rows under a parent card with
`parent_card_id` FK + `variant_label` set + default change-rule
metadata applied. v0.1 ships fully-populated change-rule defaults for
the three most-used variant labels (baseline, intimate, explicit_plus);
the other three (editorial, raw_cam, story_plus) ship with a stub
change-rule that the operator overrides via subsequent `update_entry`
calls.

FALLBACK label per WP-I3-006 Fallback Register:
  WP-I3-006 variant change-rules subset (editorial/raw_cam/story_plus
  return stub).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg


LIBRARY_VARIANT_LABELS: tuple[str, ...] = (
    "baseline",
    "intimate",
    "explicit_plus",
    "editorial",
    "raw_cam",
    "story_plus",
)


# v0.1 change-rule defaults. Mapped to the metadata keys that the TSV
# variant-ladder view exports (`amood:preserved_trigger`,
# `amood:change_lever`, ...). The keys map 1:1 to TSV columns so a
# round-trip through `amood_export_tsv` then `amood_import_tsv` is
# stable.
_VARIANT_CHANGE_RULES: dict[str, dict[str, str]] = {
    "baseline": {
        "amood:preserved_trigger": "primary",
        "amood:change_lever": "none",
        "amood:intensity_delta": "0",
        "amood:story_delta": "carries the parent card story",
        "amood:camera_delta": "no change",
        "amood:wardrobe_delta": "no change",
        "amood:set_delta": "no change",
        "amood:palette_delta": "no change",
        "amood:negative_delta": "no change",
        "amood:expected_risk": "low",
    },
    "intimate": {
        "amood:preserved_trigger": "primary",
        "amood:change_lever": "lighting + softening",
        "amood:intensity_delta": "-1",
        "amood:story_delta": "softens the moment toward private intimacy",
        "amood:camera_delta": "tighter framing toward face/torso",
        "amood:wardrobe_delta": "one layer reduced toward exposure",
        "amood:set_delta": "warmer/softer lighting; same setting",
        "amood:palette_delta": "warmer skin tones",
        "amood:negative_delta": "tighten 'no clothing covering target'",
        "amood:expected_risk": "low",
    },
    "explicit_plus": {
        "amood:preserved_trigger": "primary",
        "amood:change_lever": "exposure escalation on one axis",
        "amood:intensity_delta": "+1",
        "amood:story_delta": "escalates the reveal arc by one step",
        "amood:camera_delta": "no pose-family change; closer or lower angle if needed",
        "amood:wardrobe_delta": "explicitly removes one obstruction to the trigger",
        "amood:set_delta": "no change",
        "amood:palette_delta": "no change",
        "amood:negative_delta": "stricter 'no hand on target'",
        "amood:expected_risk": "moderate",
    },
    # FALLBACK: WP-I3-006 variant change-rules subset
    "editorial": {
        "amood:preserved_trigger": "primary",
        "amood:change_lever": "operator-defined",
        "amood:intensity_delta": "operator-defined",
        "amood:story_delta": "operator-defined",
        "amood:camera_delta": "operator-defined",
        "amood:wardrobe_delta": "operator-defined",
        "amood:set_delta": "operator-defined",
        "amood:palette_delta": "operator-defined",
        "amood:negative_delta": "operator-defined",
        "amood:expected_risk": "operator-defined",
    },
    "raw_cam": {
        "amood:preserved_trigger": "primary",
        "amood:change_lever": "operator-defined",
        "amood:intensity_delta": "operator-defined",
        "amood:story_delta": "operator-defined",
        "amood:camera_delta": "operator-defined",
        "amood:wardrobe_delta": "operator-defined",
        "amood:set_delta": "operator-defined",
        "amood:palette_delta": "operator-defined",
        "amood:negative_delta": "operator-defined",
        "amood:expected_risk": "operator-defined",
    },
    "story_plus": {
        "amood:preserved_trigger": "primary",
        "amood:change_lever": "operator-defined",
        "amood:intensity_delta": "operator-defined",
        "amood:story_delta": "operator-defined",
        "amood:camera_delta": "operator-defined",
        "amood:wardrobe_delta": "operator-defined",
        "amood:set_delta": "operator-defined",
        "amood:palette_delta": "operator-defined",
        "amood:negative_delta": "operator-defined",
        "amood:expected_risk": "operator-defined",
    },
}


class AmoodVariantError(ValueError):
    """Raised when variant input is malformed or a parent row is missing."""


@dataclass(frozen=True)
class _ParentSnapshot:
    """Fields copied from the parent card to a variant child."""
    avatar_slug: str
    batch_id: UUID
    sexual_trigger: str | None
    kink_cue: str | None
    porn_archetype: str | None
    fantasy_mode: str | None
    explicit_family: str | None
    exposure_detail: str | None
    archetype_signal: str | None
    scene_engine: str | None
    shot_purpose: str | None
    dedupe_signature: str
    compatibility_signature: str
    metadata: dict[str, Any]


def create_variants(
    conn: psycopg.Connection[object],
    *,
    parent_card_id: UUID | str,
    variants: list[str],
    operator_slug: str | None = None,
) -> list[dict[str, Any]]:
    """Spawn one child library_entries row per requested variant label.

    Each child inherits the parent's AMood card-schema columns, gets
    `parent_card_id` set to the parent, and `variant_label` set to the
    requested label. The change-rule defaults are written to the
    child's metadata under `amood:<key>` keys so the variant-ladder
    view round-trips them through TSV export/import.

    Returns a list of child dicts (id, slug, variant_label, etc.).
    """
    if not variants:
        raise AmoodVariantError("variants list must contain at least one label")

    unknown = [v for v in variants if v not in LIBRARY_VARIANT_LABELS]
    if unknown:
        raise AmoodVariantError(
            f"unknown variant labels: {unknown!r}; allowed: {LIBRARY_VARIANT_LABELS}"
        )

    parent = _load_parent_snapshot(conn, parent_card_id)
    children: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        for variant_label in variants:
            child_metadata = dict(parent.metadata)
            for k, v in _VARIANT_CHANGE_RULES[variant_label].items():
                child_metadata[k] = v
            child_metadata["amood:parent_card_id"] = str(parent_card_id)
            child_metadata["amood:variant_label"] = variant_label

            cur.execute(
                """
                INSERT INTO library_entries (
                    avatar_slug, title, batch_id, status,
                    sexual_trigger, kink_cue, porn_archetype, fantasy_mode,
                    explicit_family, exposure_detail, archetype_signal,
                    scene_engine, shot_purpose,
                    dedupe_signature, compatibility_signature,
                    parent_card_id, variant_label, metadata,
                    created_by
                ) VALUES (
                    %s, %s, %s, 'pending',
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s::jsonb,
                    %s
                )
                RETURNING id, title, variant_label
                """,
                (
                    parent.avatar_slug,
                    f"{_parent_slug_prefix(parent)}-{variant_label}",
                    str(parent.batch_id),
                    parent.sexual_trigger,
                    parent.kink_cue,
                    parent.porn_archetype,
                    parent.fantasy_mode,
                    parent.explicit_family,
                    parent.exposure_detail,
                    parent.archetype_signal,
                    parent.scene_engine,
                    parent.shot_purpose,
                    parent.dedupe_signature,
                    parent.compatibility_signature,
                    str(parent_card_id),
                    variant_label,
                    _json_dumps(child_metadata),
                    operator_slug,
                ),
            )
            row = cur.fetchone()
            children.append(
                {
                    "id": str(row[0]),
                    "slug": row[1],
                    "variant_label": row[2],
                    "parent_card_id": str(parent_card_id),
                    "change_rule_keys": list(_VARIANT_CHANGE_RULES[variant_label].keys()),
                }
            )
    conn.commit()
    return children


def _parent_slug_prefix(parent: _ParentSnapshot) -> str:
    if isinstance(parent.metadata, dict):
        return parent.metadata.get("amood:parent_slug_prefix", "card")
    return "card"


def _load_parent_snapshot(
    conn: psycopg.Connection[object],
    parent_card_id: UUID | str,
) -> _ParentSnapshot:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT avatar_slug, batch_id, sexual_trigger, kink_cue, porn_archetype,
                   fantasy_mode, explicit_family, exposure_detail, archetype_signal,
                   scene_engine, shot_purpose,
                   dedupe_signature, compatibility_signature, metadata, title
            FROM library_entries
            WHERE id = %s
            """,
            (str(parent_card_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AmoodVariantError(f"parent_card_id {parent_card_id!r} not found")
    if row[1] is None:
        raise AmoodVariantError(
            f"parent_card_id {parent_card_id!r} has no batch_id; cannot spawn variants"
        )
    metadata = row[13] if isinstance(row[13], dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata.setdefault("amood:parent_slug_prefix", row[14])
    return _ParentSnapshot(
        avatar_slug=row[0],
        batch_id=row[1],
        sexual_trigger=row[2],
        kink_cue=row[3],
        porn_archetype=row[4],
        fantasy_mode=row[5],
        explicit_family=row[6],
        exposure_detail=row[7],
        archetype_signal=row[8],
        scene_engine=row[9],
        shot_purpose=row[10],
        dedupe_signature=row[11] or "",
        compatibility_signature=row[12] or "",
        metadata=metadata,
    )


def _json_dumps(d: dict[str, Any]) -> str:
    import json
    return json.dumps(d, ensure_ascii=False)
