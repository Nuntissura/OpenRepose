"""AMood TSV view column-order mirror (WP-I3-006).

Mirrors `migrations/005_i3_amood_tsv_views.sql`. Both copies exist so
the Python TSV exporter can pre-validate column order without round-
tripping through the DB and so the audit script (WP-I3-009) can verify
they stay in sync.

Additive-only rule (per AMood blueprint Changelog): future migrations
append columns on the right. Never reorder, rename, or drop existing
columns. The migration uses `CREATE OR REPLACE VIEW` which enforces
this at the SQL layer; this Python mirror enforces the same shape on
the export side.

If you change the column list in either copy without changing the
other, `test_amood_tsv.py::test_view_column_order_matches_python_mirror`
fails immediately.
"""

from __future__ import annotations

from collections.abc import Mapping

_QUOTA_PLAN_COLUMNS: tuple[str, ...] = (
    "batch_slug",
    "axis",
    "value",
    "target_count",
    "current_count",
    "status",
    "notes",
)

_BATCH_MATRIX_COLUMNS: tuple[str, ...] = (
    "batch_slug",
    "row_id",
    "card_id",
    "status",
    "sexual_trigger",
    "kink_cue",
    "porn_archetype",
    "explicit_family",
    "exposure_detail",
    "fantasy_mode",
    "archetype_signal",
    "fantasy_story",
    "viewer_intensifier",
    "arousal_hook",
    "beauty_strategy",
    "pose_family",
    "orientation",
    "wardrobe_state",
    "held_object",
    "support_object",
    "setting_family",
    "specific_setting",
    "set_designer_notes",
    "composition_rule",
    "palette_family",
    "accent_color",
    "lighting_family",
    "camera_family",
    "gaze",
    "mouth_tongue",
    "mood",
    "texture_1",
    "texture_2",
    "negative_focus",
    "story_beat",
    "acceptance_gate",
    "scene_engine",
    "shot_purpose",
    "compatibility_signature",
    "dedupe_signature",
    "variant_plan",
    "generation_priority",
    "notes",
)

_VARIANT_LADDER_COLUMNS: tuple[str, ...] = (
    "card_id",
    "slug",
    "variant",
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
    "status",
    "notes",
)

_ANTI_REPETITION_COLUMNS: tuple[str, ...] = (
    "card_id",
    "slug",
    "explicit_family",
    "exposure_detail",
    "pose_family",
    "orientation",
    "fantasy_mode",
    "kink_cue",
    "porn_archetype",
    "setting_family",
    "specific_setting",
    "wardrobe_state",
    "held_object",
    "support_object",
    "composition_rule",
    "palette_family",
    "lighting_family",
    "camera_family",
    "gaze",
    "mouth_tongue",
    "arousal_strategy",
    "dedupe_signature",
    "status",
    "notes",
)

_PROMPT_MANIFEST_COLUMNS: tuple[str, ...] = (
    "card_id",
    "slug",
    "status",
    "workflow_model_family",
    "variant",
    "explicit_family",
    "sexual_trigger",
    "kink_cue",
    "porn_archetype",
    "fantasy_mode",
    "scene_engine",
    "positive_prompt_path",
    "negative_prompt_path",
    "positive_prompt_inline",
    "negative_prompt_inline",
    "aspect_ratio",
    "seed_plan",
    "steps_cfg_sampler_notes",
    "control_guidance_notes",
    "output_tag",
    "notes",
)

_RUN_MANIFEST_COLUMNS: tuple[str, ...] = (
    "run_id",
    "card_id",
    "slug",
    "variant",
    "workflow_model_family",
    "workflow_file",
    "prompt_manifest_row",
    "seed",
    "width",
    "height",
    "steps",
    "cfg",
    "sampler",
    "scheduler",
    "checkpoint",
    "lora_stack",
    "control_stack",
    "output_file",
    "status",
    "error_or_blocker",
    "notes",
)

_REVIEW_MANIFEST_COLUMNS: tuple[str, ...] = (
    "review_id",
    "run_id",
    "card_id",
    "slug",
    "variant",
    "output_file",
    "review_status",
    "primary_rejection_reason",
    "adult_gate_pass",
    "explicit_gate_pass",
    "arousal_gate_pass",
    "beauty_gate_pass",
    "story_gate_pass",
    "composition_gate_pass",
    "palette_gate_pass",
    "camera_gate_pass",
    "anatomy_gate_pass",
    "artifact_gate_pass",
    "identity_gate_pass",
    "accepted_output_tag",
    "next_change",
    "notes",
)

_SCORECARD_COLUMNS: tuple[str, ...] = (
    "review_id",
    "run_id",
    "card_id",
    "slug",
    "variant",
    "output_file",
    "adult_gate_score",
    "trigger_clarity_score",
    "explicit_target_score",
    "arousal_score",
    "beauty_score",
    "story_readability_score",
    "pose_mechanics_score",
    "wardrobe_mechanism_score",
    "set_design_score",
    "composition_score",
    "palette_score",
    "camera_score",
    "anatomy_score",
    "artifact_score",
    "novelty_score",
    "commercial_usability_score",
    "total_score",
    "promotion_decision",
    "primary_rejection_reason",
    "notes",
)

_POSE_CONTROL_GUIDE_COLUMNS: tuple[str, ...] = (
    "guide_id",
    "card_id",
    "slug",
    "variant",
    "guide_type",
    "pose_family",
    "orientation",
    "source_path",
    "png_path",
    "json_path",
    "workflow_node",
    "control_weight",
    "control_start",
    "control_end",
    "target_visibility_rule",
    "status",
    "primary_failure",
    "linked_run_ids",
    "notes",
)

_SERIES_PLAN_COLUMNS: tuple[str, ...] = (
    "series_id",
    "shot_id",
    "card_id",
    "slug",
    "shot_order",
    "shot_purpose",
    "preserved_trigger",
    "story_phase",
    "camera_family",
    "framing",
    "pose_delta",
    "wardrobe_delta",
    "set_delta",
    "palette_delta",
    "texture_delta",
    "acceptance_gate",
    "notes",
)


# Schema name -> ordered column list (Python-side mirror of migration 005).
AMOOD_VIEW_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "quota_plan":          _QUOTA_PLAN_COLUMNS,
    "batch_matrix":        _BATCH_MATRIX_COLUMNS,
    "variant_ladder":      _VARIANT_LADDER_COLUMNS,
    "anti_repetition":     _ANTI_REPETITION_COLUMNS,
    "prompt_manifest":     _PROMPT_MANIFEST_COLUMNS,
    "run_manifest":        _RUN_MANIFEST_COLUMNS,
    "review_manifest":     _REVIEW_MANIFEST_COLUMNS,
    "scorecard":           _SCORECARD_COLUMNS,
    "pose_control_guide":  _POSE_CONTROL_GUIDE_COLUMNS,
    "series_plan":         _SERIES_PLAN_COLUMNS,
}


# Schema name -> migration-005 view name.
_VIEW_NAMES: Mapping[str, str] = {
    "quota_plan":          "library_amood_quota_plan_v",
    "batch_matrix":        "library_amood_batch_matrix_v",
    "variant_ladder":      "library_amood_variant_ladder_v",
    "anti_repetition":     "library_amood_anti_repetition_v",
    "prompt_manifest":     "library_amood_prompt_manifest_v",
    "run_manifest":        "library_amood_run_manifest_v",
    "review_manifest":     "library_amood_review_manifest_v",
    "scorecard":           "library_amood_scorecard_v",
    "pose_control_guide":  "library_amood_pose_control_guide_v",
    "series_plan":         "library_amood_series_plan_v",
}


def view_for_schema(schema: str) -> str:
    """Return the migration-005 view name for an AMood TSV schema.

    Raises KeyError for unknown schemas; the dispatcher handler maps
    that to a citation against the (project-scoped) schema-name rule.
    """
    return _VIEW_NAMES[schema]
