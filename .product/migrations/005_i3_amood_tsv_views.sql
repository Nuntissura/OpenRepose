-- WP-I3-006 / Spec: .gov/spec/openrepose_amood_v0_1.md "TSV exports preserve
--                   AMood's locked column order (additive-only rule)"
--                   Operator blueprint: .gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md
--
-- I3 AMood TSV-shaped views.
--
-- 10 views, one per AMood blueprint TSV schema, in AMood-locked column
-- order. The Python TSV exporter (`library/amood/tsv_io.py`) does
-- `SELECT * FROM <view> WHERE <filter>` and joins TAB-separators; the
-- importer parses a TSV in the same column order back to the underlying
-- tables.
--
-- Additive-only rule (AMood blueprint Changelog rule):
--   Future migrations append columns on the right. Never reorder, rename,
--   or drop existing columns. Postgres `CREATE OR REPLACE VIEW` enforces
--   this at the SQL layer (it cannot drop or reorder existing columns --
--   only add new ones at the end).
--
-- Column-source convention:
--   1. Columns that match a library_entries / library_batches / library_runs
--      / library_outputs / library_scorecards / library_pose_guides direct
--      column use that column.
--   2. All other AMood blueprint TSV columns (free-text fantasy_story /
--      viewer_intensifier / arousal_hook / beauty_strategy / ...; tag-
--      namespaced axes pose_family / orientation / wardrobe_state / ...)
--      pull from `library_entries.metadata->>'amood:<column_name>'` with
--      a coalesce to '' so missing keys serialize as empty TSV cells
--      rather than null.
--
--   The Python importer (`tsv_io.py`) writes the same `amood:<col>` keys
--   into metadata JSONB, so export -> edit -> import -> export is bytewise
--   lossless on the 4 hand-edited schemas (quota_plan, batch_matrix,
--   variant_ladder, anti_repetition).
--
--   Tag-namespaced axes are mirrored to the `tags` + `entry_tags` tables
--   by `library_create_card` so `accepted_set_audit` can compute
--   per-axis realized coverage via the tag layer; the metadata copy is
--   the round-trip-stable canonical value.

-- ---------------------------------------------------------------------
-- 1. library_amood_quota_plan_v
--    Blueprint header:
--      batch_slug  axis  value  target_count  current_count  status  notes
--
--    Sources from library_target_groups (one row per group expanded to
--    one TSV row per axis-value combination via the metadata-stored
--    quota plan; v0.1 emits one row per target group with axis = group
--    slug, value = group_name). target_count = expected_card_count *
--    target_per_card; current_count derived from library_target_card_counts
--    aggregated over the group.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_amood_quota_plan_v AS
SELECT
    b.slug                                                                AS batch_slug,
    g.group_slug                                                          AS axis,
    g.group_name                                                          AS value,
    (g.expected_card_count * g.target_per_card)                           AS target_count,
    COALESCE(SUM(c.promoted_count), 0)::INT                               AS current_count,
    CASE
        WHEN COALESCE(SUM(c.promoted_count), 0) >= g.expected_card_count * g.target_per_card
        THEN 'satisfied'
        ELSE 'open'
    END                                                                   AS status,
    COALESCE(g.group_name, '')                                            AS notes
FROM library_target_groups g
JOIN library_batches       b ON b.project_id = g.project_id
LEFT JOIN library_target_cards     tc ON tc.group_id = g.id
LEFT JOIN library_target_card_counts c ON c.target_card_id = tc.id
GROUP BY b.slug, g.group_slug, g.group_name, g.expected_card_count, g.target_per_card;

-- ---------------------------------------------------------------------
-- 2. library_amood_batch_matrix_v
--    Blueprint header (43 columns):
--      batch_slug  row_id  card_id  status  sexual_trigger  kink_cue
--      porn_archetype  explicit_family  exposure_detail  fantasy_mode
--      archetype_signal  fantasy_story  viewer_intensifier  arousal_hook
--      beauty_strategy  pose_family  orientation  wardrobe_state
--      held_object  support_object  setting_family  specific_setting
--      set_designer_notes  composition_rule  palette_family  accent_color
--      lighting_family  camera_family  gaze  mouth_tongue  mood
--      texture_1  texture_2  negative_focus  story_beat  acceptance_gate
--      scene_engine  shot_purpose  compatibility_signature  dedupe_signature
--      variant_plan  generation_priority  notes
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_amood_batch_matrix_v AS
SELECT
    b.slug                                                       AS batch_slug,
    e.title                                                      AS row_id,
    e.id                                                         AS card_id,
    e.status                                                     AS status,
    COALESCE(e.sexual_trigger, '')                               AS sexual_trigger,
    COALESCE(e.kink_cue, '')                                     AS kink_cue,
    COALESCE(e.porn_archetype, '')                               AS porn_archetype,
    COALESCE(e.explicit_family, '')                              AS explicit_family,
    COALESCE(e.exposure_detail, '')                              AS exposure_detail,
    COALESCE(e.fantasy_mode, '')                                 AS fantasy_mode,
    COALESCE(e.archetype_signal, '')                             AS archetype_signal,
    COALESCE(e.metadata->>'amood:fantasy_story', '')             AS fantasy_story,
    COALESCE(e.metadata->>'amood:viewer_intensifier', '')        AS viewer_intensifier,
    COALESCE(e.metadata->>'amood:arousal_hook', '')              AS arousal_hook,
    COALESCE(e.metadata->>'amood:beauty_strategy', '')           AS beauty_strategy,
    COALESCE(e.metadata->>'amood:pose_family', '')               AS pose_family,
    COALESCE(e.metadata->>'amood:orientation', '')               AS orientation,
    COALESCE(e.metadata->>'amood:wardrobe_state', '')            AS wardrobe_state,
    COALESCE(e.metadata->>'amood:held_object', '')               AS held_object,
    COALESCE(e.metadata->>'amood:support_object', '')            AS support_object,
    COALESCE(e.metadata->>'amood:setting_family', '')            AS setting_family,
    COALESCE(e.metadata->>'amood:specific_setting', '')          AS specific_setting,
    COALESCE(e.metadata->>'amood:set_designer_notes', '')        AS set_designer_notes,
    COALESCE(e.metadata->>'amood:composition_rule', '')          AS composition_rule,
    COALESCE(e.metadata->>'amood:palette_family', '')            AS palette_family,
    COALESCE(e.metadata->>'amood:accent_color', '')              AS accent_color,
    COALESCE(e.metadata->>'amood:lighting_family', '')           AS lighting_family,
    COALESCE(e.metadata->>'amood:camera_family', '')             AS camera_family,
    COALESCE(e.metadata->>'amood:gaze', '')                      AS gaze,
    COALESCE(e.metadata->>'amood:mouth_tongue', '')              AS mouth_tongue,
    COALESCE(e.metadata->>'amood:mood', '')                      AS mood,
    COALESCE(e.metadata->>'amood:texture_1', '')                 AS texture_1,
    COALESCE(e.metadata->>'amood:texture_2', '')                 AS texture_2,
    COALESCE(e.metadata->>'amood:negative_focus', '')            AS negative_focus,
    COALESCE(e.metadata->>'amood:story_beat', '')                AS story_beat,
    COALESCE(e.metadata->>'amood:acceptance_gate', '')           AS acceptance_gate,
    COALESCE(e.scene_engine, '')                                 AS scene_engine,
    COALESCE(e.shot_purpose, '')                                 AS shot_purpose,
    COALESCE(e.compatibility_signature, '')                      AS compatibility_signature,
    COALESCE(e.dedupe_signature, '')                             AS dedupe_signature,
    COALESCE(e.metadata->>'amood:variant_plan', '')              AS variant_plan,
    COALESCE(e.metadata->>'amood:generation_priority', '')       AS generation_priority,
    COALESCE(e.metadata->>'amood:notes', '')                     AS notes
FROM library_entries e
JOIN library_batches  b ON b.id = e.batch_id;

-- ---------------------------------------------------------------------
-- 3. library_amood_variant_ladder_v
--    Blueprint header:
--      card_id  slug  variant  preserved_trigger  change_lever
--      intensity_delta  story_delta  camera_delta  wardrobe_delta
--      set_delta  palette_delta  negative_delta  expected_risk  status  notes
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_amood_variant_ladder_v AS
SELECT
    e.id                                                         AS card_id,
    e.title                                                      AS slug,
    COALESCE(e.variant_label, '')                                AS variant,
    COALESCE(e.metadata->>'amood:preserved_trigger', '')         AS preserved_trigger,
    COALESCE(e.metadata->>'amood:change_lever', '')              AS change_lever,
    COALESCE(e.metadata->>'amood:intensity_delta', '')           AS intensity_delta,
    COALESCE(e.metadata->>'amood:story_delta', '')               AS story_delta,
    COALESCE(e.metadata->>'amood:camera_delta', '')              AS camera_delta,
    COALESCE(e.metadata->>'amood:wardrobe_delta', '')            AS wardrobe_delta,
    COALESCE(e.metadata->>'amood:set_delta', '')                 AS set_delta,
    COALESCE(e.metadata->>'amood:palette_delta', '')             AS palette_delta,
    COALESCE(e.metadata->>'amood:negative_delta', '')            AS negative_delta,
    COALESCE(e.metadata->>'amood:expected_risk', '')             AS expected_risk,
    e.status                                                     AS status,
    COALESCE(e.metadata->>'amood:notes', '')                     AS notes
FROM library_entries e
WHERE e.parent_card_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- 4. library_amood_anti_repetition_v
--    Blueprint header:
--      card_id  slug  explicit_family  exposure_detail  pose_family
--      orientation  fantasy_mode  kink_cue  porn_archetype  setting_family
--      specific_setting  wardrobe_state  held_object  support_object
--      composition_rule  palette_family  lighting_family  camera_family
--      gaze  mouth_tongue  arousal_strategy  dedupe_signature  status  notes
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_amood_anti_repetition_v AS
SELECT
    e.id                                                         AS card_id,
    e.title                                                      AS slug,
    COALESCE(e.explicit_family, '')                              AS explicit_family,
    COALESCE(e.exposure_detail, '')                              AS exposure_detail,
    COALESCE(e.metadata->>'amood:pose_family', '')               AS pose_family,
    COALESCE(e.metadata->>'amood:orientation', '')               AS orientation,
    COALESCE(e.fantasy_mode, '')                                 AS fantasy_mode,
    COALESCE(e.kink_cue, '')                                     AS kink_cue,
    COALESCE(e.porn_archetype, '')                               AS porn_archetype,
    COALESCE(e.metadata->>'amood:setting_family', '')            AS setting_family,
    COALESCE(e.metadata->>'amood:specific_setting', '')          AS specific_setting,
    COALESCE(e.metadata->>'amood:wardrobe_state', '')            AS wardrobe_state,
    COALESCE(e.metadata->>'amood:held_object', '')               AS held_object,
    COALESCE(e.metadata->>'amood:support_object', '')            AS support_object,
    COALESCE(e.metadata->>'amood:composition_rule', '')          AS composition_rule,
    COALESCE(e.metadata->>'amood:palette_family', '')            AS palette_family,
    COALESCE(e.metadata->>'amood:lighting_family', '')           AS lighting_family,
    COALESCE(e.metadata->>'amood:camera_family', '')             AS camera_family,
    COALESCE(e.metadata->>'amood:gaze', '')                      AS gaze,
    COALESCE(e.metadata->>'amood:mouth_tongue', '')              AS mouth_tongue,
    COALESCE(e.metadata->>'amood:arousal_strategy', '')          AS arousal_strategy,
    COALESCE(e.dedupe_signature, '')                             AS dedupe_signature,
    e.status                                                     AS status,
    COALESCE(e.metadata->>'amood:notes', '')                     AS notes
FROM library_entries e;

-- ---------------------------------------------------------------------
-- 5. library_amood_prompt_manifest_v
--    Blueprint header:
--      card_id  slug  status  workflow_model_family  variant
--      explicit_family  sexual_trigger  kink_cue  porn_archetype
--      fantasy_mode  scene_engine  positive_prompt_path
--      negative_prompt_path  positive_prompt_inline  negative_prompt_inline
--      aspect_ratio  seed_plan  steps_cfg_sampler_notes
--      control_guidance_notes  output_tag  notes
--    System-generated; export-only in v0.1.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_amood_prompt_manifest_v AS
SELECT
    e.id                                                         AS card_id,
    e.title                                                      AS slug,
    e.status                                                     AS status,
    COALESCE(e.metadata->>'amood:workflow_model_family', '')     AS workflow_model_family,
    COALESCE(e.variant_label, '')                                AS variant,
    COALESCE(e.explicit_family, '')                              AS explicit_family,
    COALESCE(e.sexual_trigger, '')                               AS sexual_trigger,
    COALESCE(e.kink_cue, '')                                     AS kink_cue,
    COALESCE(e.porn_archetype, '')                               AS porn_archetype,
    COALESCE(e.fantasy_mode, '')                                 AS fantasy_mode,
    COALESCE(e.scene_engine, '')                                 AS scene_engine,
    COALESCE(e.metadata->>'amood:positive_prompt_path', '')      AS positive_prompt_path,
    COALESCE(e.metadata->>'amood:negative_prompt_path', '')      AS negative_prompt_path,
    COALESCE(p.positive, '')                                     AS positive_prompt_inline,
    COALESCE(p.negative, '')                                     AS negative_prompt_inline,
    COALESCE(e.metadata->>'amood:aspect_ratio', '')              AS aspect_ratio,
    COALESCE(e.metadata->>'amood:seed_plan', '')                 AS seed_plan,
    COALESCE(e.metadata->>'amood:steps_cfg_sampler_notes', '')   AS steps_cfg_sampler_notes,
    COALESCE(e.metadata->>'amood:control_guidance_notes', '')    AS control_guidance_notes,
    COALESCE(e.metadata->>'amood:output_tag', '')                AS output_tag,
    COALESCE(e.metadata->>'amood:notes', '')                     AS notes
FROM library_entries e
LEFT JOIN LATERAL (
    SELECT positive, negative
    FROM prompts
    WHERE entry_id = e.id
    ORDER BY created_at DESC
    LIMIT 1
) p ON TRUE;

-- ---------------------------------------------------------------------
-- 6. library_amood_run_manifest_v
--    Blueprint header:
--      run_id  card_id  slug  variant  workflow_model_family
--      workflow_file  prompt_manifest_row  seed  width  height
--      steps  cfg  sampler  scheduler  checkpoint  lora_stack
--      control_stack  output_file  status  error_or_blocker  notes
--    System-generated; export-only in v0.1.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_amood_run_manifest_v AS
SELECT
    r.id                                                         AS run_id,
    r.card_id                                                    AS card_id,
    e.title                                                      AS slug,
    COALESCE(e.variant_label, '')                                AS variant,
    COALESCE(e.metadata->>'amood:workflow_model_family', '')     AS workflow_model_family,
    COALESCE(r.workflow_json->>'workflow_file', '')              AS workflow_file,
    COALESCE(e.metadata->>'amood:prompt_manifest_row', '')       AS prompt_manifest_row,
    COALESCE(r.seed::TEXT, '')                                   AS seed,
    COALESCE(o.width::TEXT, '')                                  AS width,
    COALESCE(o.height::TEXT, '')                                 AS height,
    COALESCE(r.steps::TEXT, '')                                  AS steps,
    COALESCE(r.cfg::TEXT, '')                                    AS cfg,
    COALESCE(r.sampler, '')                                      AS sampler,
    COALESCE(r.workflow_json->>'scheduler', '')                  AS scheduler,
    COALESCE(r.workflow_json->>'checkpoint', '')                 AS checkpoint,
    COALESCE(r.workflow_json->>'lora_stack', '')                 AS lora_stack,
    COALESCE(r.workflow_json->>'control_stack', '')              AS control_stack,
    COALESCE(o.file_path, '')                                    AS output_file,
    COALESCE(o.status, '')                                       AS status,
    COALESCE(o.primary_rejection_reason, '')                     AS error_or_blocker,
    COALESCE(o.notes, '')                                        AS notes
FROM library_runs r
JOIN library_entries e ON e.id = r.card_id
LEFT JOIN LATERAL (
    SELECT file_path, width, height, status, primary_rejection_reason, notes
    FROM library_outputs
    WHERE run_id = r.id
    ORDER BY created_at ASC
    LIMIT 1
) o ON TRUE;

-- ---------------------------------------------------------------------
-- 7. library_amood_review_manifest_v
--    Blueprint header:
--      review_id  run_id  card_id  slug  variant  output_file
--      review_status  primary_rejection_reason  adult_gate_pass
--      explicit_gate_pass  arousal_gate_pass  beauty_gate_pass
--      story_gate_pass  composition_gate_pass  palette_gate_pass
--      camera_gate_pass  anatomy_gate_pass  artifact_gate_pass
--      identity_gate_pass  accepted_output_tag  next_change  notes
--    Pass = score>=4 (or AMOOD-003 specific bars); export-only in v0.1.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_amood_review_manifest_v AS
SELECT
    s.review_id                                                  AS review_id,
    s.run_id                                                     AS run_id,
    r.card_id                                                    AS card_id,
    e.title                                                      AS slug,
    COALESCE(e.variant_label, '')                                AS variant,
    COALESCE(o.file_path, '')                                    AS output_file,
    COALESCE(s.promotion_decision, '')                           AS review_status,
    COALESCE(s.primary_rejection_reason, '')                     AS primary_rejection_reason,
    CASE WHEN COALESCE(s.adult_gate_score, 0) >= 5 THEN 'pass' ELSE 'fail' END        AS adult_gate_pass,
    CASE WHEN COALESCE(s.explicit_target_score, 0) >= 4 THEN 'pass' ELSE 'fail' END   AS explicit_gate_pass,
    CASE WHEN COALESCE(s.arousal_score, 0) >= 4 THEN 'pass' ELSE 'fail' END           AS arousal_gate_pass,
    CASE WHEN COALESCE(s.beauty_score, 0) >= 4 THEN 'pass' ELSE 'fail' END            AS beauty_gate_pass,
    CASE WHEN COALESCE(s.story_readability_score, 0) >= 3 THEN 'pass' ELSE 'fail' END AS story_gate_pass,
    CASE WHEN COALESCE(s.composition_score, 0) >= 3 THEN 'pass' ELSE 'fail' END       AS composition_gate_pass,
    CASE WHEN COALESCE(s.palette_score, 0) >= 3 THEN 'pass' ELSE 'fail' END           AS palette_gate_pass,
    CASE WHEN COALESCE(s.camera_score, 0) >= 3 THEN 'pass' ELSE 'fail' END            AS camera_gate_pass,
    CASE WHEN COALESCE(s.anatomy_score, 0) >= 3 THEN 'pass' ELSE 'fail' END           AS anatomy_gate_pass,
    CASE WHEN COALESCE(s.artifact_score, 0) >= 4 THEN 'pass' ELSE 'fail' END          AS artifact_gate_pass,
    CASE WHEN COALESCE((s.notes ~* 'identity[ _-]?ok'), FALSE) THEN 'pass' ELSE 'fail' END AS identity_gate_pass,
    COALESCE(e.metadata->>'amood:accepted_output_tag', '')       AS accepted_output_tag,
    COALESCE(s.notes, '')                                        AS next_change,
    COALESCE(s.notes, '')                                        AS notes
FROM library_scorecards s
JOIN library_runs    r ON r.id = s.run_id
JOIN library_entries e ON e.id = r.card_id
LEFT JOIN library_outputs o ON o.id = s.output_id;

-- ---------------------------------------------------------------------
-- 8. library_amood_scorecard_v
--    Blueprint header:
--      review_id  run_id  card_id  slug  variant  output_file
--      adult_gate_score  trigger_clarity_score  explicit_target_score
--      arousal_score  beauty_score  story_readability_score
--      pose_mechanics_score  wardrobe_mechanism_score  set_design_score
--      composition_score  palette_score  camera_score  anatomy_score
--      artifact_score  novelty_score  commercial_usability_score
--      total_score  promotion_decision  primary_rejection_reason  notes
--    System-generated; export-only in v0.1.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_amood_scorecard_v AS
SELECT
    s.review_id                                                  AS review_id,
    s.run_id                                                     AS run_id,
    r.card_id                                                    AS card_id,
    e.title                                                      AS slug,
    COALESCE(e.variant_label, '')                                AS variant,
    COALESCE(o.file_path, '')                                    AS output_file,
    COALESCE(s.adult_gate_score::TEXT, '')                       AS adult_gate_score,
    COALESCE(s.trigger_clarity_score::TEXT, '')                  AS trigger_clarity_score,
    COALESCE(s.explicit_target_score::TEXT, '')                  AS explicit_target_score,
    COALESCE(s.arousal_score::TEXT, '')                          AS arousal_score,
    COALESCE(s.beauty_score::TEXT, '')                           AS beauty_score,
    COALESCE(s.story_readability_score::TEXT, '')                AS story_readability_score,
    COALESCE(s.pose_mechanics_score::TEXT, '')                   AS pose_mechanics_score,
    COALESCE(s.wardrobe_mechanism_score::TEXT, '')               AS wardrobe_mechanism_score,
    COALESCE(s.set_design_score::TEXT, '')                       AS set_design_score,
    COALESCE(s.composition_score::TEXT, '')                      AS composition_score,
    COALESCE(s.palette_score::TEXT, '')                          AS palette_score,
    COALESCE(s.camera_score::TEXT, '')                           AS camera_score,
    COALESCE(s.anatomy_score::TEXT, '')                          AS anatomy_score,
    COALESCE(s.artifact_score::TEXT, '')                         AS artifact_score,
    COALESCE(s.novelty_score::TEXT, '')                          AS novelty_score,
    COALESCE(s.commercial_usability_score::TEXT, '')             AS commercial_usability_score,
    COALESCE(s.total_score::TEXT, '')                            AS total_score,
    COALESCE(s.promotion_decision, '')                           AS promotion_decision,
    COALESCE(s.primary_rejection_reason, '')                     AS primary_rejection_reason,
    COALESCE(s.notes, '')                                        AS notes
FROM library_scorecards s
JOIN library_runs    r ON r.id = s.run_id
JOIN library_entries e ON e.id = r.card_id
LEFT JOIN library_outputs o ON o.id = s.output_id;

-- ---------------------------------------------------------------------
-- 9. library_amood_pose_control_guide_v
--    Blueprint header:
--      guide_id  card_id  slug  variant  guide_type  pose_family
--      orientation  source_path  png_path  json_path  workflow_node
--      control_weight  control_start  control_end  target_visibility_rule
--      status  primary_failure  linked_run_ids  notes
--    System-generated; export-only in v0.1.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_amood_pose_control_guide_v AS
SELECT
    g.id                                                         AS guide_id,
    g.card_id                                                    AS card_id,
    COALESCE(e.title, '')                                        AS slug,
    COALESCE(e.variant_label, '')                                AS variant,
    g.guide_type                                                 AS guide_type,
    COALESCE(e.metadata->>'amood:pose_family', '')               AS pose_family,
    COALESCE(e.metadata->>'amood:orientation', '')               AS orientation,
    COALESCE(g.source_path, '')                                  AS source_path,
    g.png_path                                                   AS png_path,
    g.json_path                                                  AS json_path,
    COALESCE(e.metadata->>'amood:workflow_node', '')             AS workflow_node,
    COALESCE(e.metadata->>'amood:control_weight', '')            AS control_weight,
    COALESCE(e.metadata->>'amood:control_start', '')             AS control_start,
    COALESCE(e.metadata->>'amood:control_end', '')               AS control_end,
    COALESCE(e.metadata->>'amood:target_visibility_rule', '')    AS target_visibility_rule,
    COALESCE(e.status, '')                                       AS status,
    COALESCE(e.metadata->>'amood:primary_failure', '')           AS primary_failure,
    COALESCE(e.metadata->>'amood:linked_run_ids', '')            AS linked_run_ids,
    COALESCE(e.metadata->>'amood:notes', '')                     AS notes
FROM library_pose_guides g
LEFT JOIN library_entries e ON e.id = g.card_id;

-- ---------------------------------------------------------------------
-- 10. library_amood_series_plan_v
--     Blueprint header:
--       series_id  shot_id  card_id  slug  shot_order  shot_purpose
--       preserved_trigger  story_phase  camera_family  framing
--       pose_delta  wardrobe_delta  set_delta  palette_delta
--       texture_delta  acceptance_gate  notes
--     v0.1: series plan is operator-driven (not yet a first-class
--     entity); view scaffolds the column order from per-card metadata
--     so future migrations (and future series-plan command surface) can
--     append columns without breaking the locked column order.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_amood_series_plan_v AS
SELECT
    COALESCE(e.metadata->>'amood:series_id', '')                 AS series_id,
    COALESCE(e.metadata->>'amood:shot_id', '')                   AS shot_id,
    e.id                                                         AS card_id,
    e.title                                                      AS slug,
    COALESCE(e.metadata->>'amood:shot_order', '')                AS shot_order,
    COALESCE(e.shot_purpose, '')                                 AS shot_purpose,
    COALESCE(e.metadata->>'amood:preserved_trigger', '')         AS preserved_trigger,
    COALESCE(e.metadata->>'amood:story_phase', '')               AS story_phase,
    COALESCE(e.metadata->>'amood:camera_family', '')             AS camera_family,
    COALESCE(e.metadata->>'amood:framing', '')                   AS framing,
    COALESCE(e.metadata->>'amood:pose_delta', '')                AS pose_delta,
    COALESCE(e.metadata->>'amood:wardrobe_delta', '')            AS wardrobe_delta,
    COALESCE(e.metadata->>'amood:set_delta', '')                 AS set_delta,
    COALESCE(e.metadata->>'amood:palette_delta', '')             AS palette_delta,
    COALESCE(e.metadata->>'amood:texture_delta', '')             AS texture_delta,
    COALESCE(e.metadata->>'amood:acceptance_gate', '')           AS acceptance_gate,
    COALESCE(e.metadata->>'amood:notes', '')                     AS notes
FROM library_entries e
WHERE e.metadata ? 'amood:series_id';
