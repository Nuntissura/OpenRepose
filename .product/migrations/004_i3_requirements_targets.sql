-- WP-I3-003 / Spec: .gov/spec/openrepose_requirements_v0_1.md
--                   .gov/spec/openrepose_rules_v0_1.md
--
-- I3 typed scoped requirements + target tree + project-scoped rules.
--
-- Creates library_target_groups + library_target_cards (operator-declared
-- expected output counts; counters derived from library_outputs.status),
-- library_rules (project-scoped rule registry; same shape as the global
-- rules in .gov/topology.yaml so commands and GUI see one logical
-- registry), and the library_target_card_counts VIEW that rolls up
-- per-status counts from library_outputs through library_runs.

-- ---------------------------------------------------------------------
-- 1. library_target_groups   set-level target grouping
--    EXP120: 6 groups (SF / SR / IF / IR / LF / LR), 20 expected cards
--    each, 8 promoted per card target.
-- ---------------------------------------------------------------------
CREATE TABLE library_target_groups (
    id                  UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID         NOT NULL REFERENCES library_projects(id) ON DELETE CASCADE,
    group_slug          TEXT         NOT NULL,
    group_name          TEXT         NOT NULL,
    expected_card_count INT          NOT NULL,
    target_per_card     INT          NOT NULL,
    ordering            INT          NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, group_slug),
    CONSTRAINT library_target_groups_expected_count_positive
        CHECK (expected_card_count > 0),
    CONSTRAINT library_target_groups_target_per_card_positive
        CHECK (target_per_card > 0)
);

CREATE INDEX library_target_groups_project_idx ON library_target_groups (project_id);

-- ---------------------------------------------------------------------
-- 2. library_target_cards   per-card target rows
--    card_id is nullable: rows are seeded from the operator's target
--    tree (e.g. SF-01 .. SF-20) before the actual library_entries card
--    exists; populated by library_create_card.
-- ---------------------------------------------------------------------
CREATE TABLE library_target_cards (
    id                  UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id            UUID         NOT NULL REFERENCES library_target_groups(id) ON DELETE CASCADE,
    card_slug           TEXT         NOT NULL,
    card_id             UUID         REFERENCES library_entries(id) ON DELETE SET NULL,
    target_promoted     INT          NOT NULL,
    stability_target    INT          NOT NULL DEFAULT 4,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (group_id, card_slug),
    CONSTRAINT library_target_cards_target_promoted_positive
        CHECK (target_promoted > 0),
    CONSTRAINT library_target_cards_stability_positive
        CHECK (stability_target > 0)
);

CREATE INDEX library_target_cards_group_idx ON library_target_cards (group_id);
CREATE INDEX library_target_cards_card_idx  ON library_target_cards (card_id) WHERE card_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- 3. library_rules   project-scoped rule registry
--    Same shape as the global registry in .gov/topology.yaml. Commands
--    + GUI read either transparently. Lifetime = project; archived when
--    the project closes (REQ-001 inheritance: lower scope wins).
-- ---------------------------------------------------------------------
CREATE TABLE library_rules (
    id                 UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_id            TEXT         NOT NULL,
    scope_type         TEXT         NOT NULL,
    scope_id           UUID         NOT NULL,
    name               TEXT         NOT NULL,
    short              TEXT         NOT NULL,
    severity           TEXT         NOT NULL,
    manual_link        TEXT,
    machine_check_fn   TEXT,
    auto_route_to      TEXT,
    accept_terms       TEXT[],
    reject_terms       TEXT[],
    kind               TEXT,
    inherited_from     UUID         REFERENCES library_rules(id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_validated_at  TIMESTAMPTZ,
    UNIQUE (rule_id, scope_type, scope_id),
    CONSTRAINT library_rules_severity_enum
        CHECK (severity IN ('auto-route','block','warn','info')),
    CONSTRAINT library_rules_scope_type_enum
        CHECK (scope_type IN ('project','task','batch','card')),
    CONSTRAINT library_rules_kind_enum
        CHECK (kind IS NULL OR kind IN
               ('hard_output','body','pose','face','crop','quality',
                'clothing_story','structural','custom'))
);

CREATE INDEX library_rules_rule_idx       ON library_rules (rule_id);
CREATE INDEX library_rules_scope_idx      ON library_rules (scope_type, scope_id);
CREATE INDEX library_rules_validated_idx  ON library_rules (last_validated_at)
    WHERE last_validated_at IS NOT NULL;

-- ---------------------------------------------------------------------
-- 4. library_target_card_counts   roll-up VIEW
--    Spec: openrepose_requirements_v0_1.md "Counters"
--    Aggregates library_outputs.status per target card. Group-level
--    and project-level counters are SUM aggregations over this view.
--    Materialized variant deferred per requirements spec out-of-scope.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_target_card_counts AS
SELECT
    tc.id              AS target_card_id,
    tc.card_id,
    tc.target_promoted,
    tc.stability_target,
    COUNT(*) FILTER (WHERE o.status = 'pending')        AS pending_count,
    COUNT(*) FILTER (WHERE o.status = 'triaging')       AS triaging_count,
    COUNT(*) FILTER (WHERE o.status = 'soft_accepted')  AS soft_accepted_count,
    COUNT(*) FILTER (WHERE o.status = 'promoted')       AS promoted_count,
    COUNT(*) FILTER (WHERE o.status = 'rejected')       AS rejected_count,
    COUNT(*) FILTER (WHERE o.status = 'diagnostic')     AS diagnostic_count,
    COUNT(*) FILTER (WHERE o.status = 'abandoned')      AS abandoned_count
FROM library_target_cards tc
LEFT JOIN library_runs    r ON r.card_id = tc.card_id
LEFT JOIN library_outputs o ON o.run_id  = r.id
GROUP BY tc.id, tc.card_id, tc.target_promoted, tc.stability_target;
