-- WP-I3-003 / Spec: .gov/spec/openrepose_amood_v0_1.md
--
-- I3 AMood card-schema extension + scoring storage + dedupe service.
--
-- Adds the 16 AMood card-schema columns to library_entries (see spec
-- "Card Schema Extension"); creates library_scorecards for fast-triage
-- + full-rubric scoring (column shape from AMood blueprint TSV header,
-- lines 1120-1145 + 1952-1953); creates library_diagnostics +
-- library_diversity_audits supporting tables; creates the library
-- schema and the library.dedupe_check SQL function.
--
-- Promotion is gated at DB level by CHECK constraints citing AMOOD-003
-- (fast-triage), AMOOD-004 (full-rubric thresholds), and SAFE-001/002/003
-- (juvenile / coercion / hidden-camera boundaries) so a hallucinating LLM
-- cannot bypass safety boundaries via direct SQL.

-- ---------------------------------------------------------------------
-- 1. ALTER library_entries: 16 AMood card-schema columns
--
--    NOT-NULL columns (dedupe_signature, compatibility_signature) get
--    DEFAULT '' so ADD COLUMN fills in-place fast on tables with existing
--    I2 rows. WP-I3-006 backfills real values when cards are migrated to
--    the AMood schema (per WP-I3-003 Decisions Log).
-- ---------------------------------------------------------------------
ALTER TABLE library_entries
    ADD COLUMN sexual_trigger          TEXT,
    ADD COLUMN kink_cue                TEXT,
    ADD COLUMN porn_archetype          TEXT,
    ADD COLUMN fantasy_mode            TEXT,
    ADD COLUMN explicit_family         TEXT,
    ADD COLUMN exposure_detail         TEXT,
    ADD COLUMN archetype_signal        TEXT,
    ADD COLUMN scene_engine            TEXT,
    ADD COLUMN shot_purpose            TEXT,
    ADD COLUMN dedupe_signature        TEXT NOT NULL DEFAULT '',
    ADD COLUMN compatibility_signature TEXT NOT NULL DEFAULT '',
    ADD COLUMN parent_card_id          UUID REFERENCES library_entries(id) ON DELETE SET NULL,
    ADD COLUMN variant_label           TEXT,
    ADD COLUMN stability_target        INT  NOT NULL DEFAULT 4,
    ADD COLUMN target_promoted         INT,
    ADD COLUMN abandonment_reason      TEXT,
    ADD COLUMN abandoned_after_seeds   INT;

-- variant_label enum guard (NULL allowed for non-variant rows)
ALTER TABLE library_entries
    ADD CONSTRAINT library_entries_variant_label_enum
        CHECK (variant_label IS NULL OR variant_label IN
               ('baseline','intimate','explicit_plus','editorial','raw_cam','story_plus'));

-- abandonment_reason enum guard (NULL allowed for non-abandoned rows)
ALTER TABLE library_entries
    ADD CONSTRAINT library_entries_abandonment_reason_enum
        CHECK (abandonment_reason IS NULL OR abandonment_reason IN
               ('trigger_fights_model','pose_needs_guide','wardrobe_incompatible',
                'identity_drift','duplicate_scene','safety_boundary'));

-- fantasy_mode enum guard (NULL allowed)
ALTER TABLE library_entries
    ADD CONSTRAINT library_entries_fantasy_mode_enum
        CHECK (fantasy_mode IS NULL OR fantasy_mode IN
               ('archetype-heavy fantasy','casual intimate','staged voyeur',
                'raw-cam performance','editorial porn'));

-- scene_engine enum guard (NULL allowed)
ALTER TABLE library_entries
    ADD CONSTRAINT library_entries_scene_engine_enum
        CHECK (scene_engine IS NULL OR scene_engine IN
               ('performance','private-room','editorial-porn','raw-cam','environment-pressure'));

CREATE INDEX idx_library_entries_dedupe_signature_trgm
    ON library_entries USING GIN (dedupe_signature gin_trgm_ops);
CREATE INDEX idx_library_entries_explicit_family
    ON library_entries (explicit_family) WHERE explicit_family IS NOT NULL;
CREATE INDEX idx_library_entries_fantasy_mode
    ON library_entries (fantasy_mode) WHERE fantasy_mode IS NOT NULL;
CREATE INDEX idx_library_entries_porn_archetype
    ON library_entries (porn_archetype) WHERE porn_archetype IS NOT NULL;
CREATE INDEX idx_library_entries_parent_card_id
    ON library_entries (parent_card_id) WHERE parent_card_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- 2. library_scorecards   fast-triage 4 fields + full-rubric 16 fields
--
--    Column shape from AMood blueprint scorecard TSV header
--    (.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md, lines
--    1120-1145 + 1952-1953). Promotion CHECK constraints split per
--    rule_id so WP-I3-009 audit can map back to manual anchors.
-- ---------------------------------------------------------------------
CREATE TABLE library_scorecards (
    id                          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    review_id                   TEXT         NOT NULL UNIQUE,
    run_id                      UUID         NOT NULL REFERENCES library_runs(id)    ON DELETE CASCADE,
    output_id                   UUID         NOT NULL REFERENCES library_outputs(id) ON DELETE CASCADE,
    -- Fast-triage 4 fields (AMOOD-003 gate)
    adult_gate_score            INT,
    trigger_clarity_score       INT,
    anatomy_score               INT,
    artifact_score              INT,
    -- Full-rubric remaining 12 fields
    explicit_target_score       INT,
    arousal_score               INT,
    beauty_score                INT,
    story_readability_score     INT,
    pose_mechanics_score        INT,
    wardrobe_mechanism_score    INT,
    set_design_score            INT,
    composition_score           INT,
    palette_score               INT,
    camera_score                INT,
    novelty_score               INT,
    commercial_usability_score  INT,
    -- Decision
    total_score                 INT,
    promotion_decision          TEXT,
    primary_rejection_reason    TEXT,
    notes                       TEXT,
    created_at                  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (output_id),

    CONSTRAINT library_scorecards_promotion_decision_enum
        CHECK (promotion_decision IS NULL OR
               promotion_decision IN ('promote','reject','defer','abandon')),

    -- AMOOD-003 fast-triage gate: any of 4 fast fields below bar => no promote
    CONSTRAINT lib_scorecards_amood_003_fast_triage
        CHECK (
            promotion_decision <> 'promote'
            OR (adult_gate_score      IS NOT NULL AND adult_gate_score      >= 5
                AND trigger_clarity_score IS NOT NULL AND trigger_clarity_score >= 4
                AND anatomy_score      IS NOT NULL AND anatomy_score      >= 3
                AND artifact_score     IS NOT NULL AND artifact_score     >= 4)
        ),

    -- AMOOD-004 promotion thresholds (full-rubric additional gates)
    CONSTRAINT lib_scorecards_amood_004_promotion_thresholds
        CHECK (
            promotion_decision <> 'promote'
            OR (explicit_target_score IS NOT NULL AND explicit_target_score >= 4
                AND arousal_score IS NOT NULL AND arousal_score >= 4
                AND beauty_score  IS NOT NULL AND beauty_score  >= 4)
        ),

    -- SAFE-001 juvenile-coded boundary: cannot promote
    CONSTRAINT lib_scorecards_safe_001_juvenile_block
        CHECK (
            promotion_decision <> 'promote'
            OR primary_rejection_reason IS NULL
            OR primary_rejection_reason <> 'juvenile_coded'
        ),

    -- SAFE-002 coercion-coded boundary: cannot promote
    CONSTRAINT lib_scorecards_safe_002_coercion_block
        CHECK (
            promotion_decision <> 'promote'
            OR primary_rejection_reason IS NULL
            OR primary_rejection_reason <> 'coercion_coded'
        ),

    -- SAFE-003 hidden-camera-coded boundary: cannot promote
    CONSTRAINT lib_scorecards_safe_003_hidden_camera_block
        CHECK (
            promotion_decision <> 'promote'
            OR primary_rejection_reason IS NULL
            OR primary_rejection_reason <> 'hidden_camera_coded'
        )
);

CREATE INDEX library_scorecards_run_idx                ON library_scorecards (run_id);
CREATE INDEX library_scorecards_promotion_decision_idx ON library_scorecards (promotion_decision)
    WHERE promotion_decision IS NOT NULL;

-- ---------------------------------------------------------------------
-- 3. library_diagnostics   per-output diagnostic events
--    Captures auto-route fires, advisory-hint flags, and other rule
--    citations against an output. Audit script consumes this to verify
--    rule_id coverage.
-- ---------------------------------------------------------------------
CREATE TABLE library_diagnostics (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    output_id    UUID         NOT NULL REFERENCES library_outputs(id) ON DELETE CASCADE,
    rule_id      TEXT         NOT NULL,
    bucket       TEXT,                                    -- e.g. 'intermediate_evidence' (auto_route_to)
    reason       TEXT,
    details_json JSONB,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX library_diagnostics_output_idx ON library_diagnostics (output_id);
CREATE INDEX library_diagnostics_rule_idx   ON library_diagnostics (rule_id);

-- ---------------------------------------------------------------------
-- 4. library_diversity_audits   accepted_set_audit output rows
--    Spec: openrepose_amood_v0_1.md "accepted_set_audit"
--    Per-axis realized coverage with priority flag (ok/watch/priority).
--    Keyed by (batch_id, axis, created_at) for time-series review.
-- ---------------------------------------------------------------------
CREATE TABLE library_diversity_audits (
    id                 UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id           UUID         NOT NULL REFERENCES library_batches(id) ON DELETE CASCADE,
    axis               TEXT         NOT NULL,
    realized_coverage  REAL         NOT NULL,
    priority_flag      TEXT         NOT NULL,
    details_json       JSONB,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT lib_diversity_audits_priority_enum
        CHECK (priority_flag IN ('ok','watch','priority')),
    CONSTRAINT lib_diversity_audits_coverage_range
        CHECK (realized_coverage >= 0.0 AND realized_coverage <= 1.0)
);

CREATE INDEX library_diversity_audits_batch_idx ON library_diversity_audits (batch_id);
CREATE INDEX library_diversity_audits_axis_idx  ON library_diversity_audits (axis);

-- ---------------------------------------------------------------------
-- 5. library schema + dedupe_check function
--    Spec: openrepose_amood_v0_1.md "Anti-Repetition Service"
--    Splits both signatures on '|' (8 axes by AMood blueprint), counts
--    shared axes, returns rows where overlap >= p_threshold restricted
--    to status IN ('soft_accepted','promoted') and same project.
-- ---------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS library;

CREATE OR REPLACE FUNCTION library.dedupe_check(
    p_project_id        UUID,
    p_dedupe_signature  TEXT,
    p_threshold         INT  DEFAULT 6
) RETURNS TABLE (
    candidate_id    UUID,
    candidate_slug  TEXT,
    overlap_count   INT
) AS $$
    -- Each signature is 8 pipe-delimited axis values:
    --   <explicit_family>|<pose_family>|<orientation>|<wardrobe_state>|
    --   <support_object>|<setting_family>|<camera_family>|<palette_family>
    -- Overlap = number of identical axis values at the same position.
    -- Empty axis values ('') do not count as overlap.
    WITH split_input AS (
        SELECT string_to_array(p_dedupe_signature, '|') AS axes
    ),
    candidates AS (
        SELECT
            e.id,
            e.title,
            e.dedupe_signature,
            string_to_array(e.dedupe_signature, '|') AS axes
        FROM library_entries e
        JOIN library_batches  b ON b.id = e.batch_id
        WHERE b.project_id = p_project_id
          AND e.status IN ('soft_accepted','promoted')
          AND e.dedupe_signature <> ''
    ),
    axis_matches AS (
        SELECT
            c.id   AS candidate_id,
            c.title AS candidate_slug,
            (
                SELECT COUNT(*)::INT
                FROM generate_subscripts(c.axes, 1) AS i
                WHERE
                    array_length((SELECT axes FROM split_input), 1) IS NOT NULL
                    AND i <= array_length((SELECT axes FROM split_input), 1)
                    AND c.axes[i] = (SELECT axes FROM split_input)[i]
                    AND c.axes[i] <> ''
            ) AS overlap_count
        FROM candidates c
    )
    SELECT o.candidate_id, o.candidate_slug, o.overlap_count
    FROM axis_matches o
    WHERE o.overlap_count >= p_threshold
    ORDER BY o.overlap_count DESC, o.candidate_id ASC;
$$ LANGUAGE SQL STABLE;
