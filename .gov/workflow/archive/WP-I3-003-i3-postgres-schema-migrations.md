# WP-I3-003 - I3 PostgreSQL Schema Migrations

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: REVIEW
- **Iteration**: I3
- **Workflow Version**: 1.1
- **Packet Class**: INFRASTRUCTURE
- **Effort Estimate**: L
- **Linked Spec**:
  - `.gov/spec/openrepose_intake_v0_1.md` — Hierarchy / New tables / Status Enum / Pose Guide Pairing / Rule Citations
  - `.gov/spec/openrepose_amood_v0_1.md` — Card Schema Extension / Anti-Repetition Service / Acceptance & Scoring Storage / Concept-to-Entity Mapping
  - `.gov/spec/openrepose_requirements_v0_1.md` — Target Tree / Counters / Requirement Anatomy / Tables
  - `.gov/spec/openrepose_rules_v0_1.md` — Severity Tiers / Initial Registry / Project-Scoped Storage
- **Linked Test Suite**: `.product/tests/test_db_migrator_i3.py` (new); extends pattern from `.product/tests/test_db_migrator.py`
- **Linked Check Script**: `scripts/audit-repo.ps1` (existing; extension lands in WP-I3-009, not here)

## Intent

Land all I3 schema in three additive PostgreSQL migrations applied on top of `schema_version=1`. After this WP, the OpenRepose library DB carries every table, view, function, index, and CHECK constraint that the four I3 specs assume. WP-I3-004..010 wire commands, GUI, and integrations against this schema; nothing in this WP touches dispatcher, GUI, or operator-facing surfaces.

## Linked Workpackets

- **Predecessor(s)**: WP-I3-001 (DONE — spec lock).
- **Successor(s)**: WP-I3-004 (intake/project/task command surface), WP-I3-005 (default-staging bridge), WP-I3-006 (AMood data-model commands + dedupe), WP-I3-007 (requirements editor + target tree), WP-I3-008 (Triage GUI tab), WP-I3-009 (audit script extension), WP-I3-010 (end-to-end EXP120 verification).
- **Blocks**: WP-I3-004, WP-I3-005, WP-I3-006, WP-I3-007, WP-I3-008.
- **Blocked-By**: none.
- **Related**: WP-I2-001 (PostgreSQL pool + migrator — at REVIEW; this WP applies on top of `schema_version=1` either way), WP-I2-003 (`library_entries` columns this WP extends).

## Linked Requirements / Spec Sections

- `openrepose_intake_v0_1.md` / `## Hierarchy / ### New tables`
- `openrepose_intake_v0_1.md` / `## Status Enum`
- `openrepose_intake_v0_1.md` / `## Pose Guide Pairing`
- `openrepose_intake_v0_1.md` / `## Two-Stage Acceptance` (CHECK constraint `promotion_requires_operator`)
- `openrepose_amood_v0_1.md` / `## Card Schema Extension (on library_entries)`
- `openrepose_amood_v0_1.md` / `## Anti-Repetition Service` (`library.dedupe_check` SQL function)
- `openrepose_amood_v0_1.md` / `## Acceptance & Scoring Storage` (CHECK constraints AMOOD-003, AMOOD-004, SAFE-001/002/003)
- `openrepose_requirements_v0_1.md` / `## Target Tree / ### Tables`
- `openrepose_requirements_v0_1.md` / `## Counters` (view `library_target_card_counts`)
- `openrepose_rules_v0_1.md` / `## Global vs Project-Scoped Rules` (`library_rules` table)

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Local codebase | `.product/migrations/001_library_initial.sql` + `.product/src/openrepose/db/migrator.py` | Migration runner is filename-prefix-ordered (`NNN_<slug>.sql`); each file runs in one transaction with an advisory lock; `schema_version` row inserted at the end. Three additive files (`002_i3_intake.sql`, `003_i3_amood_card_schema.sql`, `004_i3_requirements_targets.sql`) compose cleanly with this runner with zero migrator changes. | adopt |
| 2026-05-03 | Local spec gap | `openrepose_intake_v0_1.md` `ALTER TABLE library_runs ...` and `ALTER TABLE library_batches ...` | I2 did not ship `library_runs` or `library_batches`; the I3 spec text presumes they exist. Operator confirmed (2026-05-03) that WP-I3-003 creates these tables with the I3-required FK columns baked in from creation. The spec ALTER text is satisfied by end-state shape. | adopt |
| 2026-05-03 | PostgreSQL docs | https://www.postgresql.org/docs/16/ddl-constraints.html | Named CHECK constraints surface in error messages as `new row for relation "X" violates check constraint "Y"`. Naming the constraint after the rule_id (e.g. `library_outputs_promotion_requires_operator`, `library_outputs_safe_001_juvenile_block`) makes the audit's "every CHECK constraint cites a rule_id" check (WP-I3-009) trivial. | adopt |
| 2026-05-03 | PostgreSQL docs | https://www.postgresql.org/docs/16/pgtrgm.html | `gin_trgm_ops` on `dedupe_signature` (text built from 8 pipe-delimited axis values) is the right index for the AMood threshold-overlap check; the `library.dedupe_check` SQL function uses string_to_array + cardinality(intersection) rather than relying on the GIN index alone, but the index supports broader trigram queries (recent-warnings list in `state.library.amood`). | adopt |
| 2026-05-03 | PostgreSQL docs | https://www.postgresql.org/docs/16/sql-createview.html | `library_target_card_counts` is a plain VIEW (not materialized) for v0.1 — counters are filtered aggregates over `library_outputs.status`. Materialized variant deferred per requirements spec out-of-scope note. | adopt |
| 2026-05-03 | PostgreSQL docs | https://www.postgresql.org/docs/16/indexes-partial.html | Partial indexes on `library_outputs (task_id) WHERE status IN ('pending','triaging')` and `WHERE status = 'soft_accepted'` keep triage-queue queries fast as terminal-status rows accumulate. Spec mandates these. | adopt |
| 2026-05-03 | PostgreSQL docs | https://www.postgresql.org/docs/16/sql-altertable.html | ON DELETE CASCADE chosen for child→parent FKs where wholesale-reject of a task drops every dependent row in one transaction (`library_outputs.task_id`, `library_outputs.run_id`, `library_runs.task_id`, `library_batches.task_id`, `library_target_groups.project_id`, `library_target_cards.group_id`, `library_tasks.project_id`, `library_rules.scope_id` left without action — operator-driven, intentional). | adopt |

Existing approach is correct for migration discovery + lock + apply pattern; no better alternative found in the WP-I2-001 lock window.

## Reality Boundary

- **Real Seam**: three new PostgreSQL migration files (`002_i3_intake.sql`, `003_i3_amood_card_schema.sql`, `004_i3_requirements_targets.sql`) applied by the existing migrator. End-state DB carries: `library_projects`, `library_tasks`, `library_outputs`, `library_pose_guides`, `library_runs`, `library_batches`, `library_target_groups`, `library_target_cards`, `library_rules`, `library_scorecards`, `library_diagnostics`, `library_diversity_audits`; 16 new columns + 5 indexes on `library_entries`; one VIEW (`library_target_card_counts`); one SQL function (`library.dedupe_check`); CHECK constraints citing INTAKE-001, AMOOD-003, AMOOD-004, SAFE-001/002/003, plus status enum guards.
- **User-Visible Win**: none directly — this is the foundation. WP-I3-004..008 land the operator-facing and LLM-facing surfaces against this schema.
- **Proof Target**: `pytest .product/tests/test_db_migrator_i3.py` passes against an ephemeral PostgreSQL 16 instance (same pattern WP-I2-001 established); junit XML at `target/test-artifacts/WP-I3-003/pytest_results.xml`. Tests cover: clean apply on `schema_version=1`, idempotent re-apply, every CHECK constraint rejects its forbidden state with an error mentioning the rule_id, `library.dedupe_check` returns expected overlaps, view rolls up correctly with synthetic outputs.
- **Allowed Temporary Fallbacks**: none — schema is the contract, fallbacks belong in WPs that wire surfaces over it.
- **Promotion Guard**: do not declare WP-I3-003 stable until: (a) all 3 migration files apply cleanly on a fresh DB and idempotently re-apply, (b) every CHECK constraint named in the I3 specs is in the schema and rejects its forbidden state, (c) `library.dedupe_check` returns the expected candidates against synthetic data with overlap_count exact, (d) `library_target_card_counts` view aggregates correctly across all seven status enum values.

## In Scope

- New migration `.product/migrations/002_i3_intake.sql`:
  - CREATE TABLE `library_projects`, `library_tasks`, `library_outputs`, `library_pose_guides`, `library_runs`, `library_batches`.
  - Status enum CHECK on `library_tasks.status` and `library_outputs.status`.
  - CHECK constraint `library_outputs_promotion_requires_operator` (cites INTAKE-001 in name).
  - Partial indexes on `library_outputs` (pending/triaging, soft_accepted, content_hash).
  - GIN index on `library_pose_guides` join columns.
  - FK shape baked in from CREATE (no ALTER for this WP — see Decisions Log).

- New migration `.product/migrations/003_i3_amood_card_schema.sql`:
  - ALTER TABLE `library_entries` adds 16 AMood card-schema columns (`sexual_trigger`, `kink_cue`, `porn_archetype`, `fantasy_mode`, `explicit_family`, `exposure_detail`, `archetype_signal`, `scene_engine`, `shot_purpose`, `dedupe_signature`, `compatibility_signature`, `parent_card_id`, `variant_label`, `stability_target`, `target_promoted`, `abandonment_reason`, `abandoned_after_seeds`).
  - 5 indexes per spec (`gin_trgm_ops` on `dedupe_signature`; B-tree on `explicit_family`, `fantasy_mode`, `porn_archetype`; partial on `parent_card_id`).
  - CREATE TABLE `library_scorecards`, `library_diagnostics`, `library_diversity_audits`.
  - CHECK constraints `library_scorecards_amood_003_fast_triage`, `library_scorecards_safe_001_juvenile_block`, `library_scorecards_safe_002_coercion_block`, `library_scorecards_safe_003_hidden_camera_block`, `library_scorecards_amood_004_safety_boundary` (all cite their rule_id in the constraint name).
  - CREATE SCHEMA `library` (if not exists) + `library.dedupe_check(p_project_id uuid, p_dedupe_signature text, p_threshold int default 6)` SQL function returning `(candidate_id uuid, candidate_slug text, overlap_count int)`.

- New migration `.product/migrations/004_i3_requirements_targets.sql`:
  - CREATE TABLE `library_target_groups`, `library_target_cards`, `library_rules`.
  - CHECK constraints on `library_rules.severity` (auto-route|block|warn|info), `library_rules.scope_type` (project|task|batch|card), `library_rules.kind` (8 enum values from requirements spec + `custom`).
  - UNIQUE constraints per spec.
  - CREATE OR REPLACE VIEW `library_target_card_counts`.

- New tests `.product/tests/test_db_migrator_i3.py`:
  - Clean apply 001 → 002 → 003 → 004 against ephemeral PG; verify `schema_version` rows for 1, 2, 3, 4.
  - Idempotent re-apply (running migrator twice in a row is no-op; existing `apply_pending` behavior verified).
  - For each CHECK constraint, INSERT a forbidden row, assert `psycopg.errors.CheckViolation` with constraint name in message.
  - Synthetic insert: 1 project, 1 task, 1 batch, 1 card, 1 run, ≥6 outputs spanning all 7 status values; assert `library_target_card_counts` view returns correct per-status counts.
  - Synthetic dedupe scenario: 3 cards with engineered signatures; `library.dedupe_check(project_id, signature, threshold=6)` returns expected candidate(s) with exact overlap_count.

## Out Of Scope

- Dispatcher commands consuming this schema (WP-I3-004 onwards).
- Default-staging ComfyUI bridge change (WP-I3-005).
- TSV view definitions for AMood (WP-I3-006 — views are SELECT statements layered over base tables; specifying them outside the migrator is intentional so they can iterate without a migration version bump).
- Audit script extension verifying every rule_id resolves to a manual anchor (WP-I3-009).
- Seeding the initial registry of 25 rule_ids into `library_rules` for project scope (WP-I3-007 owns project-rule authoring; global registry is in `topology.yaml` and is not stored in DB by this WP).
- Materialized variant of `library_target_card_counts` (deferred per requirements spec out-of-scope).

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I3-003-i3-postgres-schema-migrations.md`
- `.gov/workflow/TASKBOARD.md`

### Product (`.product/`)

- `.product/migrations/002_i3_intake.sql` (new)
- `.product/migrations/003_i3_amood_card_schema.sql` (new)
- `.product/migrations/004_i3_requirements_targets.sql` (new)
- `.product/tests/test_db_migrator_i3.py` (new)

### Build / Output (gitignored)

- `target/test-artifacts/WP-I3-003/pytest_results.xml`

## Risks And Dependencies

- **Risk**: ephemeral-PG fixture from `conftest.py` is configured for I2 schema only; I3 tests may need an extension. **Mitigation**: existing `test_db_migrator.py` uses the same fixture and applies migrations live — extend the fixture parameter rather than fork it.
- **Risk**: `library_entries` ALTER on a populated table (operators with I2 data already loaded) may be slow; ADD COLUMN with default values fills in-place in PG 11+. **Mitigation**: every new column is nullable except `dedupe_signature` and `compatibility_signature`, which are NOT NULL; for those, the migration sets `DEFAULT ''` for backfill then drops the default — keeps ALTER fast and lets WP-I3-006 populate correct values when cards are migrated. Decision logged.
- **Risk**: `library.dedupe_check` SQL function semantics drift from blueprint over time. **Mitigation**: function body is short, fully tested with deterministic synthetic data, and cited from `openrepose_amood_v0_1.md` "Anti-Repetition Service" so any change requires a spec amendment + new migration.
- **Risk**: CHECK constraint names exceed PostgreSQL 63-char identifier limit. **Mitigation**: use abbreviated forms (`lib_outputs_intake_001_two_stage` rather than spelled out); document mapping in the migration file header comment.
- **Dependency**: PostgreSQL 16 ephemeral fixture, pg_trgm + uuid-ossp + unaccent extensions (already enabled by 001). **Owner**: assistant. **Status**: satisfied.
- **Dependency**: psycopg 3 (already in use). **Owner**: assistant. **Status**: satisfied.

## Definition Of Done

- [x] `.product/migrations/002_i3_intake.sql` exists, applies cleanly on `schema_version=1`, contains all tables/indexes/CHECK constraints listed in In Scope.
- [x] `.product/migrations/003_i3_amood_card_schema.sql` exists, applies cleanly on `schema_version=2`, ALTERs `library_entries` and creates AMood scorecard tables + dedupe function.
- [x] `.product/migrations/004_i3_requirements_targets.sql` exists, applies cleanly on `schema_version=3`, creates target tree + rules table + counts view.
- [x] After all three migrations, `SELECT MAX(version) FROM schema_version` returns 4.
- [x] `.product/tests/test_db_migrator_i3.py` passes locally against ephemeral PG (21/21); junit XML saved to `target/test-artifacts/WP-I3-003/pytest_results.xml`.
- [x] Every CHECK constraint mentioned in In Scope rejects its forbidden state with the rule_id visible in the constraint name (verified by `test_intake_001_two_stage_acceptance_blocks_promote_without_finalizer`, `test_amood_003_fast_triage_blocks_promote_with_low_adult_gate`, `test_amood_004_promotion_thresholds_blocks_promote_with_low_arousal`, `test_safety_boundaries_block_promote[*]`, `test_library_outputs_status_enum_rejects_unknown`, `test_library_rules_severity_enum_rejects_unknown`, `test_library_rules_kind_enum_rejects_unknown`, `test_batches_dedupe_threshold_range`).
- [x] `library.dedupe_check` returns correct overlap counts for synthetic scenarios (3 dedicated tests covering threshold-at, threshold-above, and cross-project isolation).
- [x] `library_target_card_counts` view aggregates correctly across all 7 status values (verified by `test_target_card_counts_aggregates_all_seven_status_values` + empty-card test).
- [x] `powershell -ExecutionPolicy Bypass -File scripts/audit-repo.ps1` exits 0.
- [x] **Manual Impact**: No — pure schema change with no operator-facing surface; manual updates land in WP-I3-004..008 alongside the surfaces.

## Test Coverage Plan

### Functional Flow Tests
- [x] Migrator discovers and applies 001..004 in order; `schema_version` rows present for each.
- [x] Re-running `apply_pending()` on a fully-migrated DB is a no-op.

### Code Correctness Tests
- [x] Schema present: every CREATE TABLE / VIEW / FUNCTION / INDEX in In Scope is queryable post-apply.
- [x] CHECK constraints named per rule_id reject their forbidden state.
- [x] `library_outputs.status` only accepts the 7 enum values.
- [x] `lib_outputs_intake_001_two_stage_acceptance` rejects `status='promoted' AND finalized_by IS NULL`.
- [x] `library_target_card_counts` view returns correct counts for synthetic data.
- [x] `library.dedupe_check(project_id, sig, 6)` returns candidate(s) with exact `overlap_count`; threshold=8 returns subset.

### Red-Team / Abuse Tests
- [x] Forbidden status enum value (e.g. `'oops'`) rejected by CHECK.
- [x] Promotion without operator finalize blocked at DB level (cannot bypass two-stage acceptance even with hand-crafted SQL).
- [x] AMood safety constraints (SAFE-001/002/003) reject forbidden scorecard combinations even if dispatcher sends them.

### Performance / Reliability Tests
- [x] N/A — schema-only migration; performance budget verification belongs to WP-I3-008/010.

## Rollback Plan

- Files to revert: the three new SQL files + `test_db_migrator_i3.py`. Migrator is unchanged.
- Files to keep: WP file + taskboard row (for history; mark CANCELLED if abandoned, do not delete).
- Recovery command: `git revert <impl-commit-hash>`. On a real DB rollback, applying the revert + restoring from `pg_dump` taken before WP-I3-003 was run is the operator's path. Schema downgrade (drop tables/columns) is intentionally not authored here — additive-only is the I3 stance per AMood blueprint.

## Decisions Log

- 2026-05-03: **Three migration files instead of one**. Reason: each maps to one I3 spec (intake/amood/requirements); easier to review, easier to roll back conceptually, and matches operator preference confirmed today. Alternatives considered: single `002_i3.sql` (rejected — too large for one PR-style review pass), four files split by concern (rejected — `library_runs`/`library_batches` are intake-shape, fit there).
- 2026-05-03: **CREATE library_runs + library_batches in 002, not ALTER**. Reason: operator confirmed I2 did not ship these tables; the I3 spec text "ALTER TABLE library_runs ADD COLUMN task_id" describes end-state shape, not literal DDL recipe. Alternatives: spec amendment first (rejected by operator — additive-only stance covers this; the spec's end-state is satisfied either way).
- 2026-05-03: **NOT NULL columns with empty-string default backfill**. Reason: `dedupe_signature` and `compatibility_signature` are NOT NULL on `library_entries`, but I2 already has rows. ADD COLUMN ... NOT NULL DEFAULT '' fills in-place fast in PG 11+; WP-I3-006 backfills real values when cards are migrated to the AMood schema. Alternatives: NULL allowed (rejected — spec mandates NOT NULL), separate backfill migration (rejected — overkill for v0.1).
- 2026-05-03: **CHECK constraint names embed rule_id**. Reason: WP-I3-009 audit script extension will verify "every CHECK constraint that triggers a rejection cites a rule_id"; the cheapest implementation is constraint-name regex `<table>_<rule_id_lowercase>_<short>`. Alternative: rule_id only in COMMENT ON CONSTRAINT (rejected — not surfaced in error messages, audit can't grep).
- 2026-05-03: **`library_entries` gets `batch_id` (nullable) + `status` (NOT NULL DEFAULT 'pending')** in 002. Reason: amood spec `dedupe_check` SQL function restricts on `library_entries.status IN ('soft_accepted','promoted')`, and intake spec `Hierarchy` says "card belongs to exactly one batch" — neither column was explicitly added by any I3 ALTER. Both belong with the hierarchy migration (002), not the AMood card content migration (003). Status uses the unified 7-value enum to match `library_outputs.status`. Alternative: denormalize `project_id` onto `library_entries` for dedupe perf (rejected — JOIN through batches.project_id is one hop; can be added later if needed).
- 2026-05-03: **`library_scorecards` schema sourced from AMood blueprint lines 1120-1145 + 1952-1953**. Reason: neither intake nor amood spec defines the library_scorecards columns; the blueprint scorecard TSV header is the structural source. 16 score fields + total_score + promotion_decision + primary_rejection_reason + notes + identifiers (review_id, run_id, output_id). CHECK constraints split per rule_id: AMOOD-003 fast-triage (4 fields gate), AMOOD-004 full-rubric (3 additional fields gate), SAFE-001/002/003 (one per safety boundary). Constraint shape "promotion_decision <> 'promote' OR (...)" expresses "promote requires conditions; non-promote unrestricted". Alternative: combine all into one CHECK (rejected — audit can't map back to individual rule_ids).

## Fallback Register

- None.

## Change Ledger

- **What Became Real**: Three new SQL migrations under `.product/migrations/` (`002_i3_intake.sql`, `003_i3_amood_card_schema.sql`, `004_i3_requirements_targets.sql`) apply on top of `schema_version=1` taking the DB to `schema_version=4`. End-state schema carries 12 new tables (`library_projects`, `library_tasks`, `library_batches`, `library_pose_guides`, `library_runs`, `library_outputs`, `library_scorecards`, `library_diagnostics`, `library_diversity_audits`, `library_target_groups`, `library_target_cards`, `library_rules`), 18 new columns on `library_entries` (16 AMood card-schema columns from spec + the two hierarchy hookups `batch_id` / `status`), 7 new indexes on `library_entries` (trigram + partial), partial indexes on `library_outputs` for triage queue queries, the `library_target_card_counts` VIEW, the `library` schema with the `library.dedupe_check` SQL function, and rule-cited CHECK constraints (INTAKE-001 two-stage acceptance; AMOOD-003 fast-triage; AMOOD-004 full-rubric thresholds; SAFE-001/002/003 safety boundaries; status / severity / scope_type / kind / tier / decision / dedupe-threshold-range enums). 21 new tests in `test_db_migrator_i3.py` exercise apply order, idempotency, schema presence, every CHECK rejection, dedupe overlap correctness, view roll-up across all 7 status values, and cross-project dedupe isolation. Existing `test_db_migrator.py`, `test_db_connection.py`, `test_library_commands.py` updated to reflect the new `schema_version=4` end-state (4 line changes total). Suite results: 528/528 passed (full suite minus the pre-existing Windows `test_state_write_atomic_no_partial` reader-thread `PermissionError` warning that WP-I3-002 also flagged); audit script clean.
- **What Remains Simulated**: nothing in this WP's scope. Surfaces over the schema (dispatcher commands, GUI, ComfyUI bridge default-staging, audit-script extension, end-to-end EXP120 walkthrough) land in WP-I3-004..010. The `library_rules` table is created empty; project-scoped rule authoring lands in WP-I3-007 (requirements editor markdown round-trip). The 16 AMood card-schema columns on `library_entries` are present but not populated for legacy I2 rows; backfill happens in WP-I3-006 when cards are migrated to the AMood schema (NOT NULL columns `dedupe_signature` and `compatibility_signature` carry `DEFAULT ''` for the legacy rows per Decisions Log).
- **Next Blocking Real Seam**: WP-I3-004 (intake + project + task command surface) wires the dispatcher commands that consume this schema; WP-I3-005 changes the ComfyUI bridge to default-staging; WP-I3-006 adds the AMood data-model commands + populates AMood card columns; WP-I3-007 adds the requirements editor and markdown round-trip; WP-I3-009 audit extension verifies every CHECK constraint and rule_id resolves.

## Spec Gaps Resolved In This WP

Three implementation-level gaps surfaced during drafting; all flagged to operator before writing migrations and resolved without spec relitigation per the operator's "gap confirmed, fix it" stance (2026-05-03):

1. `library_runs` and `library_batches` were referenced by all three I3 specs as if they existed (`ALTER TABLE library_runs ADD COLUMN task_id`) but were never shipped by I2. Resolution: CREATE both in 002 with the I3-required FKs (`task_id`, `pose_guide_id`, `card_id`, `project_id`) baked in from creation. Spec ALTER text describes end-state; how we got there is implementation.
2. `library_entries.batch_id` and `library_entries.status` are required by the spec semantics (cards belong to one batch; `dedupe_check` filters on status) but no I3 ALTER added them. Resolution: both columns added in 002 alongside the hierarchy tables; `batch_id` nullable for legacy I2 rows; `status` defaults to `'pending'` using the unified 7-value enum.
3. `library_scorecards` is referenced by both intake and amood specs but neither defines its column shape. Resolution: column shape sourced from the operator-canonical AMood blueprint TSV header (`.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` lines 1120-1145 + 1952-1953), which the assistant treats as read-only. Promotion CHECK constraints split per rule_id (AMOOD-003 fast-triage, AMOOD-004 full-rubric thresholds, SAFE-001/002/003) so the WP-I3-009 audit extension can verify each by constraint-name regex.

One implementation defect caught in test:
- `OVERLAPS` is a reserved word in PostgreSQL (temporal range operator). The first draft of `library.dedupe_check` named a CTE `overlaps`; PG parsed it as an operator. Renamed to `axis_matches`. All 21 tests pass after the rename.

## Checkpoint Commit Plan

1. Governance kickoff commit (this WP file + taskboard row).
2. Migration commit (`002_i3_intake.sql` + `003_i3_amood_card_schema.sql` + `004_i3_requirements_targets.sql`).
3. Test commit (`test_db_migrator_i3.py`) + REVIEW transition (Change Ledger + Evidence + taskboard move).

Single squash-merge would also be acceptable; three commits keep the diff reviewable.

## Proof Of Implementation

- **Command Runs**: `.\.venv\Scripts\python.exe -m pytest .product/tests/test_db_migrator_i3.py --junitxml=target/test-artifacts/WP-I3-003/pytest_results.xml -q` returns 0.
- **Proof Artifact**: `target/test-artifacts/WP-I3-003/`.
- **Claim Standard**: never mark `DONE` without linked command evidence and artifact paths.

## Headless LLM Operation Compliance

N/A — pure DB schema change. No GUI, no command channel, no snapshot target. The downstream WPs (WP-I3-004..008) cite headless-compliance against this schema.

## Exit Criteria

- [x] Definition of Done items all checked.
- [x] Taskboard row reflects current status.
- [x] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [x] Linked test suite has executed results saved under `target/test-artifacts/WP-I3-003/`.
- [x] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence section.
- [x] **Headless LLM Operation Compliance** section either marked `N/A` with reason, or all items checked.

## Evidence

- **Test Suite Execution**:
  - WP-I3-003 dedicated suite: `.\.venv\Scripts\python.exe -m pytest .product/tests/test_db_migrator_i3.py --junitxml=target/test-artifacts/WP-I3-003/pytest_results.xml -q` → 21/21 passed.
  - DB-touching tests after assertion update: `.\.venv\Scripts\python.exe -m pytest .product/tests/test_db_connection.py .product/tests/test_library_commands.py .product/tests/test_db_migrator.py .product/tests/test_db_migrator_i3.py -q` → 57/57 passed.
  - Full suite: `.\.venv\Scripts\python.exe -m pytest .product/tests/ -q` → 528/528 passed (3 pre-update regressions fixed by line-level `schema_version` assertion bumps; one pre-existing `PermissionError` warning in `test_state_write_atomic_no_partial` reader thread is unchanged from WP-I3-002 baseline).
- **Audit**: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/audit-repo.ps1` → `audit-repo: OK no violations` (exit 0).
- **Logs**: pytest stdout in this session; junit XML at `target/test-artifacts/WP-I3-003/pytest_results.xml`.
- **Screenshots / Exports**: N/A — schema only.
- **Build Artifacts**: N/A — no installer/dist artifact.
- **Proof Artifact**: `target/test-artifacts/WP-I3-003/`
- **Operator Sign-off**: pending.

## Progress Log

- 2026-05-03: WP drafted at READY per operator authorization. Governance refactor exempt from product-edit gate; kickoff commit + push will land this WP file + taskboard row before any `.product/` file is opened.
- 2026-05-03: Kickoff push landed (commit `3ce31ba`) on `origin/main`; predecessor housekeeping commit `738ef04` consolidated stranded prior-assistant work (audit test harness + spec lock stamps). Status READY -> IN-PROGRESS. Two additional spec gaps noted before writing migrations: (1) `library_entries` needs `batch_id` + `status` columns to support the hierarchy + dedupe_check semantics — added to 002 with Decisions Log entry; (2) `library_scorecards` column schema sourced from AMood blueprint TSV header (operator-canonical, read-only).
- 2026-05-03: Three migrations + 21 dedicated tests authored. First test run hit `psycopg.errors.SyntaxError: syntax error at or near "overlaps"` — `OVERLAPS` is a reserved word in PostgreSQL. Renamed the CTE in `library.dedupe_check` from `overlaps` to `axis_matches`. 21/21 pass on rerun.
- 2026-05-03: Full suite run surfaced 3 regressions in I2 tests asserting `schema_version == 1` (`test_db_connection::test_app_boots_with_live_db_and_runs_migrations`, `test_db_connection::test_pool_schema_version_after_migration`, `test_library_commands::test_dump_library_schema_returns_version_and_tables`). Updated assertions to `== 4` (4 line-level changes; comments updated to acknowledge new end-state). Suite 528/528 green. Audit clean. Status IN-PROGRESS -> REVIEW.
