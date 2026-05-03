"""AMood card creation (WP-I3-006).

Spec: `.gov/spec/openrepose_amood_v0_1.md` "library_create_card" + "Card
Schema Extension".

`create_card` inserts a row into `library_entries` with the 16 AMood
card-schema columns populated, runs `library.dedupe_check` BEFORE
INSERT to surface AMOOD-001 with the matching card_id + overlap count
when the threshold is met, mirrors the 13 amood:* tag-namespaced axes
to the `tags` + `entry_tags` tables for the accepted-set audit, and
writes free-text metadata fields under `amood:<key>` keys for
TSV round-trip stability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from .compatibility import check_compatibility
from .dedupe import (
    DEDUPE_AXIS_COUNT,
    DEFAULT_DEDUPE_THRESHOLD,
    DedupeMatch,
    check_card_pre_insert,
    compose_signature,
)

if TYPE_CHECKING:
    import psycopg


# Tag-namespaced axes (per spec "Card Schema Extension"); mirrored to
# tags table when the field is set on a new card so accepted_set_audit
# can query coverage at the tag layer.
_TAG_AXIS_KEYS: tuple[str, ...] = (
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

# Free-text metadata keys that the batch_matrix / variant_ladder /
# anti_repetition views read from `library_entries.metadata` JSONB.
# These are the columns from the AMood blueprint TSV headers that don't
# map to a library_entries direct column. `create_card` accepts any
# keyword whose name appears here and writes it to metadata.
_METADATA_FREE_TEXT_KEYS: tuple[str, ...] = (
    # batch_matrix
    "fantasy_story",
    "viewer_intensifier",
    "arousal_hook",
    "beauty_strategy",
    "specific_setting",
    "set_designer_notes",
    "composition_rule",
    "mood",
    "texture_1",
    "texture_2",
    "negative_focus",
    "story_beat",
    "acceptance_gate",
    "variant_plan",
    "generation_priority",
    "notes",
    # anti_repetition
    "arousal_strategy",
    # prompt_manifest
    "workflow_model_family",
    "positive_prompt_path",
    "negative_prompt_path",
    "aspect_ratio",
    "seed_plan",
    "steps_cfg_sampler_notes",
    "control_guidance_notes",
    "output_tag",
    # variant_ladder (operator-set on later update; create_card seeds blanks)
    "preserved_trigger",
    "change_lever",
    "intensity_delta",
    "story_delta",
    "camera_delta",
    "wardrobe_delta",
    "set_delta",
    "palette_delta",
    "negative_delta",
    "expected_risk",
    # series_plan
    "series_id",
    "shot_id",
    "shot_order",
    "story_phase",
    "framing",
    "pose_delta",
    "texture_delta",
)


class AmoodCardError(ValueError):
    """Raised when card input is malformed or a referenced row is missing."""


@dataclass
class AmoodCardResult:
    """Return value of `create_card`. Includes the dedupe match so the
    dispatcher can emit AMOOD-001 with the correct overlap_count + matched
    card_slug visible to the LLM caller."""
    card_id: UUID
    slug: str
    dedupe_signature: str
    compatibility_signature: str
    dedupe_match: DedupeMatch
    compatibility_warnings: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": str(self.card_id),
            "slug": self.slug,
            "dedupe_signature": self.dedupe_signature,
            "compatibility_signature": self.compatibility_signature,
            "dedupe_match": self.dedupe_match.to_dict(),
            "compatibility_warnings": list(self.compatibility_warnings),
        }


def create_card(
    conn: psycopg.Connection[object],
    *,
    batch_id: UUID | str,
    avatar_slug: str,
    slug: str,
    # AMood card-schema columns (direct on library_entries):
    sexual_trigger: str | None = None,
    kink_cue: str | None = None,
    porn_archetype: str | None = None,
    fantasy_mode: str | None = None,
    explicit_family: str | None = None,
    exposure_detail: str | None = None,
    archetype_signal: str | None = None,
    scene_engine: str | None = None,
    shot_purpose: str | None = None,
    # Tag-namespaced axes (mirrored to tags):
    pose_family: str | None = None,
    orientation: str | None = None,
    wardrobe_state: str | None = None,
    held_object: str | None = None,
    support_object: str | None = None,
    setting_family: str | None = None,
    lighting_family: str | None = None,
    camera_family: str | None = None,
    gaze: str | None = None,
    mouth_tongue: str | None = None,
    palette_family: str | None = None,
    accent_color: str | None = None,
    # Optional pre-computed signatures (default: derived from inputs).
    dedupe_signature: str | None = None,
    compatibility_signature: str | None = None,
    dedupe_threshold: int = DEFAULT_DEDUPE_THRESHOLD,
    operator_slug: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> AmoodCardResult:
    if not slug:
        raise AmoodCardError("card slug must be non-empty")
    if not avatar_slug:
        raise AmoodCardError("avatar_slug must be non-empty")

    project_id = _resolve_project_id_for_batch(conn, batch_id)
    if project_id is None:
        raise AmoodCardError(f"batch_id {batch_id!r} not found")

    # Compose signatures.
    sig = dedupe_signature or compose_signature(
        explicit_family=explicit_family or "",
        pose_family=pose_family or "",
        orientation=orientation or "",
        wardrobe_state=wardrobe_state or "",
        support_object=support_object or "",
        setting_family=setting_family or "",
        camera_family=camera_family or "",
        palette_family=palette_family or "",
    )
    if sig.count("|") != DEDUPE_AXIS_COUNT - 1:
        raise AmoodCardError(
            f"dedupe_signature must have exactly {DEDUPE_AXIS_COUNT} pipe-delimited "
            f"axes; got {sig!r}"
        )
    comp_sig = compatibility_signature or _compose_compatibility_sig(
        explicit_family=explicit_family or "",
        pose_family=pose_family or "",
        orientation=orientation or "",
        camera_family=camera_family or "",
        wardrobe_state=wardrobe_state or "",
        support_object=support_object or "",
        palette_family=palette_family or "",
    )

    # Pre-insert dedupe check (AMOOD-001 surface point).
    dedupe_match = check_card_pre_insert(
        conn,
        project_id=project_id,
        dedupe_signature=sig,
        threshold=int(dedupe_threshold),
    )

    # Light compatibility-check warnings (no hard reject here; the
    # `compatibility_check` command surfaces hard rejects before the
    # operator runs `create_card`. We still record warnings so the
    # response carries them.)
    compat = check_compatibility(
        sexual_trigger=sexual_trigger or "",
        explicit_family=explicit_family or "",
        pose_family=pose_family or "",
        orientation=orientation or "",
        camera_family=camera_family or "",
        wardrobe_state=wardrobe_state or "",
        support_object=support_object or "",
        palette_family=palette_family or "",
        lighting_family=lighting_family or "",
        fantasy_mode=fantasy_mode or "",
    )

    # Build metadata block.
    metadata: dict[str, Any] = dict(extra_metadata or {})
    # Mirror tag-axis values into metadata so TSV round-trip is lossless.
    tag_inputs = {
        "explicit_family":  explicit_family,
        "pose_family":      pose_family,
        "orientation":      orientation,
        "wardrobe_state":   wardrobe_state,
        "held_object":      held_object,
        "support_object":   support_object,
        "setting_family":   setting_family,
        "lighting_family":  lighting_family,
        "camera_family":    camera_family,
        "gaze":             gaze,
        "mouth_tongue":     mouth_tongue,
        "palette_family":   palette_family,
        "accent_color":     accent_color,
    }
    for key, value in tag_inputs.items():
        if value is not None and value != "":
            metadata[f"amood:{key}"] = value
    # Free-text metadata fields from extra_metadata: any caller-supplied
    # key that matches the v0.1 free-text whitelist gets a `amood:`
    # prefix added (caller may also pass already-prefixed keys, in which
    # case we leave them alone).
    free_text_kwargs = (
        {k: extra_metadata[k] for k in _METADATA_FREE_TEXT_KEYS if k in extra_metadata}
        if extra_metadata
        else {}
    )
    for key, value in free_text_kwargs.items():
        if value is not None and value != "":
            metadata[f"amood:{key}"] = value

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO library_entries (
                avatar_slug, title, batch_id, status,
                sexual_trigger, kink_cue, porn_archetype, fantasy_mode,
                explicit_family, exposure_detail, archetype_signal,
                scene_engine, shot_purpose,
                dedupe_signature, compatibility_signature,
                metadata, created_by
            ) VALUES (
                %s, %s, %s, 'pending',
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s::jsonb, %s
            )
            RETURNING id
            """,
            (
                avatar_slug,
                slug,
                str(batch_id),
                sexual_trigger,
                kink_cue,
                porn_archetype,
                fantasy_mode,
                explicit_family,
                exposure_detail,
                archetype_signal,
                scene_engine,
                shot_purpose,
                sig,
                comp_sig,
                json.dumps(metadata, ensure_ascii=False),
                operator_slug,
            ),
        )
        card_id: UUID = cur.fetchone()[0]
        # Wire up library_target_cards.card_id when a target row with the
        # matching slug exists in the project (spec contract: target rows
        # are seeded by project_set_target_tree before library_create_card
        # runs; create_card populates the link). Caught by WP-I3-010 e2e
        # verification — without this, counters cannot roll up because the
        # library_target_card_counts view joins on tc.card_id = r.card_id.
        cur.execute(
            "UPDATE library_target_cards "
            "SET card_id = %s "
            "WHERE card_slug = %s "
            "  AND card_id IS NULL "
            "  AND group_id IN ("
            "      SELECT id FROM library_target_groups WHERE project_id = %s"
            "  )",
            (str(card_id), slug, str(project_id)),
        )
        # Mirror tag-axis values to tags + entry_tags so accepted_set_audit
        # can query coverage at the tag layer.
        for key in _TAG_AXIS_KEYS:
            value = tag_inputs.get(key)
            if value is None or value == "":
                continue
            tag_name = f"amood:{key}:{value}"
            cur.execute(
                "INSERT INTO tags (name) VALUES (%s) "
                "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
                "RETURNING id",
                (tag_name,),
            )
            tag_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO entry_tags (entry_id, tag_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (card_id, tag_id),
            )
    conn.commit()

    return AmoodCardResult(
        card_id=card_id,
        slug=slug,
        dedupe_signature=sig,
        compatibility_signature=comp_sig,
        dedupe_match=dedupe_match,
        compatibility_warnings=list(compat.warnings),
    )


def _compose_compatibility_sig(
    *,
    explicit_family: str,
    pose_family: str,
    orientation: str,
    camera_family: str,
    wardrobe_state: str,
    support_object: str,
    palette_family: str,
) -> str:
    """Compatibility signature is a 7-axis pipe-delimited summary used
    for fast triage filtering; format is informal in the blueprint, so
    v0.1 picks a stable canonical join."""
    return "|".join(
        v.replace("|", "/") if v else ""
        for v in (
            explicit_family,
            pose_family,
            orientation,
            camera_family,
            wardrobe_state,
            support_object,
            palette_family,
        )
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
