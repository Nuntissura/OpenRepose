-- WP-I3-003 / Spec: .gov/spec/openrepose_intake_v0_1.md
--
-- I3 intake hierarchy: Project / Task / Batch / Card / Run / Output.
--
-- This migration creates the new tables that the intake & triage spec
-- builds on. It composes with 003_i3_amood_card_schema.sql (AMood card
-- content + scorecards) and 004_i3_requirements_targets.sql (target tree
-- + rules registry).
--
-- Spec text uses "ALTER TABLE library_runs / library_batches" as if those
-- tables existed at I2. They were never shipped. Per WP-I3-003 Decisions
-- Log (2026-05-03), this migration creates them with the I3-required
-- columns baked in from CREATE — the spec's end-state shape is satisfied.
--
-- CHECK constraint names embed rule_ids so WP-I3-009 audit can verify
-- "every CHECK constraint that triggers a rejection cites a real rule_id"
-- by constraint-name regex.

-- ---------------------------------------------------------------------
-- 1. library_projects   long-lived workstream
-- ---------------------------------------------------------------------
CREATE TABLE library_projects (
    id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug        TEXT         NOT NULL UNIQUE,
    name        TEXT         NOT NULL,
    status      TEXT         NOT NULL DEFAULT 'active',
    owner_slug  TEXT         NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    closed_at   TIMESTAMPTZ,
    CONSTRAINT library_projects_status_enum
        CHECK (status IN ('active','paused','closed'))
);

CREATE INDEX library_projects_status_idx ON library_projects (status);

-- ---------------------------------------------------------------------
-- 2. library_tasks   one LLM execution unit (a "960-image run")
-- ---------------------------------------------------------------------
CREATE TABLE library_tasks (
    id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID         NOT NULL REFERENCES library_projects(id) ON DELETE CASCADE,
    slug            TEXT         NOT NULL,
    source          TEXT,                                    -- 'comfyui_bridge' | 'manual_import' | 'orchestrator' | ...
    llm_model       TEXT,
    expected_count  INT,
    received_count  INT          NOT NULL DEFAULT 0,
    status          TEXT         NOT NULL DEFAULT 'pending',
    intake_dir      TEXT         NOT NULL,                   -- relative path under outputs/intake/
    summary_json    JSONB,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    finalized_at    TIMESTAMPTZ,
    UNIQUE (project_id, slug),
    CONSTRAINT library_tasks_status_enum
        CHECK (status IN ('pending','triaging','complete','rejected_wholesale','aborted'))
);

CREATE INDEX library_tasks_project_idx ON library_tasks (project_id);
CREATE INDEX library_tasks_status_idx  ON library_tasks (status);

-- ---------------------------------------------------------------------
-- 3. library_batches   AMood batch_slug (1 quota plan, 1 matrix)
-- ---------------------------------------------------------------------
CREATE TABLE library_batches (
    id                       UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id               UUID         NOT NULL REFERENCES library_projects(id) ON DELETE CASCADE,
    task_id                  UUID         NOT NULL REFERENCES library_tasks(id)    ON DELETE CASCADE,
    slug                     TEXT         NOT NULL,
    name                     TEXT,
    tier                     TEXT         NOT NULL DEFAULT 'production',
    primary_explicit_family  TEXT,
    dedupe_threshold         INT          NOT NULL DEFAULT 6,
    package_path             TEXT,
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, slug),
    CONSTRAINT library_batches_tier_enum
        CHECK (tier IN ('quick','mini','production')),
    CONSTRAINT library_batches_dedupe_threshold_range
        CHECK (dedupe_threshold BETWEEN 4 AND 8)
);

CREATE INDEX library_batches_task_idx    ON library_batches (task_id);
CREATE INDEX library_batches_project_idx ON library_batches (project_id);

-- ---------------------------------------------------------------------
-- 4. library_pose_guides   first-class pose-guide artifacts
--    Spec: openrepose_intake_v0_1.md "Pose Guide Pairing"
--    Yaw exporter (Feature 1) registers a pose guide on every PNG+JSON
--    export. Triage view fetches both files via library_runs.pose_guide_id.
-- ---------------------------------------------------------------------
CREATE TABLE library_pose_guides (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    guide_type   TEXT         NOT NULL,
    png_path     TEXT         NOT NULL,
    json_path    TEXT         NOT NULL,
    source_path  TEXT,
    content_hash TEXT         NOT NULL UNIQUE,
    card_id      UUID         REFERENCES library_entries(id) ON DELETE SET NULL,
    batch_id     UUID         REFERENCES library_batches(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT library_pose_guides_type_enum
        CHECK (guide_type IN ('openpose','dwpose','depth','canny','segmentation','mask'))
);

CREATE INDEX idx_library_pose_guides_card  ON library_pose_guides (card_id)  WHERE card_id  IS NOT NULL;
CREATE INDEX idx_library_pose_guides_batch ON library_pose_guides (batch_id) WHERE batch_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- 5. library_runs   one ComfyUI generation invocation
--    A run belongs to a card (parent moodboard card) and may carry a
--    task_id (when initiated through intake) and a pose_guide_id
--    (when the workflow used a control-net pose guide).
-- ---------------------------------------------------------------------
CREATE TABLE library_runs (
    id             UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    card_id        UUID         NOT NULL REFERENCES library_entries(id)    ON DELETE CASCADE,
    task_id        UUID         REFERENCES library_tasks(id)               ON DELETE CASCADE,
    pose_guide_id  UUID         REFERENCES library_pose_guides(id)         ON DELETE SET NULL,
    sampler        TEXT,
    cfg            REAL,
    steps          INT,
    seed           BIGINT,
    workflow_json  JSONB,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX library_runs_card_idx ON library_runs (card_id);
CREATE INDEX library_runs_task_idx ON library_runs (task_id) WHERE task_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- 6. library_outputs   one generated image file
--    Status enum is the unified 7-value lifecycle. Two-stage acceptance
--    is enforced at DB level: status='promoted' requires finalized_by NOT
--    NULL (operator-supplied), so a hallucinating LLM cannot bypass via
--    direct SQL.
-- ---------------------------------------------------------------------
CREATE TABLE library_outputs (
    id                       UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id                   UUID         NOT NULL REFERENCES library_runs(id)  ON DELETE CASCADE,
    task_id                  UUID         NOT NULL REFERENCES library_tasks(id) ON DELETE CASCADE,
    file_path                TEXT         NOT NULL,
    content_hash             TEXT         NOT NULL,
    width                    INT          NOT NULL,
    height                   INT          NOT NULL,
    status                   TEXT         NOT NULL,
    primary_rejection_reason TEXT,
    soft_accepted_at         TIMESTAMPTZ,
    promoted_at              TIMESTAMPTZ,
    rejected_at              TIMESTAMPTZ,
    finalized_by             TEXT,                            -- operator slug, populated only on stage-2 finalize
    notes                    TEXT,
    created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT library_outputs_status_enum
        CHECK (status IN ('pending','triaging','soft_accepted','promoted','rejected','diagnostic','abandoned')),
    CONSTRAINT lib_outputs_intake_001_two_stage_acceptance
        CHECK (status <> 'promoted' OR finalized_by IS NOT NULL)
);

CREATE INDEX idx_library_outputs_status_pending ON library_outputs (task_id) WHERE status IN ('pending','triaging');
CREATE INDEX idx_library_outputs_status_softacc ON library_outputs (task_id) WHERE status = 'soft_accepted';
CREATE INDEX idx_library_outputs_content_hash   ON library_outputs (content_hash);
CREATE INDEX library_outputs_run_idx            ON library_outputs (run_id);

-- ---------------------------------------------------------------------
-- 7. ALTER library_entries: hierarchy hookup
--    Cards belong to exactly one batch; status uses the unified enum so
--    library_search can filter pending/soft_accepted by default per
--    spec rule INTAKE-004.
--
--    batch_id is nullable so existing I2 rows (created before I3) remain
--    valid. WP-I3-006 backfills batch_id when cards are migrated to the
--    AMood schema.
-- ---------------------------------------------------------------------
ALTER TABLE library_entries
    ADD COLUMN batch_id UUID REFERENCES library_batches(id) ON DELETE SET NULL,
    ADD COLUMN status   TEXT NOT NULL DEFAULT 'pending'
        CONSTRAINT library_entries_status_enum
            CHECK (status IN ('pending','triaging','soft_accepted','promoted','rejected','diagnostic','abandoned'));

CREATE INDEX library_entries_batch_idx  ON library_entries (batch_id) WHERE batch_id IS NOT NULL;
CREATE INDEX library_entries_status_idx ON library_entries (status);
