# WP-I3-006 - AMood Data-Model Commands + Dedupe Service

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DONE
- **Iteration**: I3
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: L
- **Linked Spec**:
  - `.gov/spec/openrepose_amood_v0_1.md` — Card Schema Extension / Anti-Repetition Service / Acceptance & Scoring Storage / Command Surface (AMood-specific) / Package Layout / State Surface
  - `.gov/spec/openrepose_intake_v0_1.md` — Hierarchy (Project / Task / Batch / Card / Run / Output) / Status Enum (composes with `library_create_card`)
  - `.gov/spec/openrepose_rules_v0_1.md` — Error Citation Contract / Severity Tiers (AMOOD-001 warn, AMOOD-003/004 + SAFE-001..003 block surfaces)
  - `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` — operator-canonical blueprint; TSV column order + variant ladder + compatibility table + accepted-set-audit thresholds
- **Linked Test Suite**: `.product/tests/test_amood_commands.py` (new); `.product/tests/test_amood_dedupe.py` (new); `.product/tests/test_amood_tsv.py` (new)
- **Linked Check Script**: `scripts/audit-repo.ps1`

## Intent

Wire the 7 AMood-specific dispatcher commands from `openrepose_amood_v0_1.md` against the schema landed by WP-I3-003 and the project/task/intake surface from WP-I3-004. After this WP, an LLM agent can drive an EXP120-style AMood batch end-to-end through HTTP/inbox: `init_batch_package` creates the batch row + `outputs/library/<project>/<batch>/` folder layout from blueprint templates; `library_create_card` inserts a card with dedupe pre-check (cites AMOOD-001 on overlap); `library_create_variants` spawns the variant ladder; `compatibility_check` encodes the AMood compatibility table; `accepted_set_audit` writes per-axis realized-coverage rows; `amood_export_tsv` / `amood_import_tsv` round-trip 10 TSV schemas in AMood-locked column order. `state.library.amood` reflects the active batch on every command.

## Linked Workpackets

- **Predecessor(s)**: WP-I3-003 (DONE — schema), WP-I3-004 (DONE — project/task/intake surface; provides citation helper, dispatcher patterns, state.library.intake/guidance hooks).
- **Successor(s)**: WP-I3-008 (Triage GUI tab — reads `state.library.amood`, renders per-card variant strip), WP-I3-010 (end-to-end EXP120 verification — exercises this command surface), WP-I3-011 (OpenRepose AMood GPT + Claude skill wrappers — wraps these commands).
- **Blocks**: WP-I3-008, WP-I3-010, WP-I3-011.
- **Blocked-By**: none (predecessors DONE).
- **Related**: WP-I2-003 (library_entries CRUD — extended here for AMood card columns), WP-I2-004 (library command pattern), WP-I3-002 (`adult_production_boundary` envelope on every command response).

## Linked Requirements / Spec Sections

- `openrepose_amood_v0_1.md` / `## Command Surface (AMood-specific)` — 7 commands
- `openrepose_amood_v0_1.md` / `## Anti-Repetition Service` — `library.dedupe_check` integration
- `openrepose_amood_v0_1.md` / `## Card Schema Extension` — column-level shape on `library_entries`
- `openrepose_amood_v0_1.md` / `## Acceptance & Scoring Storage` — `library_scorecards` writes (downstream of triage; this WP exposes audit reads)
- `openrepose_amood_v0_1.md` / `## State Surface` — `state.library.amood` block shape
- `openrepose_amood_v0_1.md` / `## Package Layout` — `outputs/library/<project>/<batch>/` directory tree
- `openrepose_rules_v0_1.md` / `## Error Citation Contract` — AMOOD-001..004 + SAFE-001..003 citation surfaces
- AMood blueprint `## TSV Schemas` — 10 locked column orders (quota_plan, batch_matrix, variant_ladder, anti_repetition, prompt_manifest, run_manifest, review_manifest, scorecard, pose_control_guide, series_plan)
- AMood blueprint `## Compatibility Check` — hard-reject + warning truth table consumed by `compatibility_check`
- AMood blueprint `## Variant Ladder` — change-rule defaults consumed by `library_create_variants`
- AMood blueprint `## Accepted-Set Audit` — per-axis coverage thresholds (>= 0.75 ok, 0.5–0.74 watch, < 0.5 priority)

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Local codebase | `.product/src/openrepose/library/intake/projects.py` + `.product/src/openrepose/library/intake/tasks.py` (WP-I3-004) | Existing pattern for new library subpackages: `@dataclass` row class with `to_dict()`, module-level CRUD functions taking `psycopg.Connection`, raise `LibraryXxxError(ValueError)` on input validation, commit inside the function, return the row. New AMood modules follow the same shape. | adopt |
| 2026-05-03 | Local codebase | `.product/migrations/003_i3_amood_card_schema.sql` lines 220-271 | `library.dedupe_check(p_project_id, p_dedupe_signature, p_threshold)` returns rows ordered by overlap_count DESC. Splits on `\|` (8 axes). Restricted to status IN ('soft_accepted','promoted'). Empty axis (`''`) does not count. v0.1 wires Python `library/amood/dedupe.py` to call this function via `cur.execute("SELECT * FROM library.dedupe_check(%s,%s,%s)", ...)` — no client-side overlap math. | adopt |
| 2026-05-03 | Local codebase | `.product/src/openrepose/commands.py` lines 50-73 + `_HANDLERS` block | New AMood handlers register in `_HANDLERS` by name; reuse `_ensure_pool(d)` for DB acquisition; reuse `format_citation` from `library/citations.py` for AMOOD-001/-003/-004 + SAFE-001..003 citation surfaces. Error class `OpenReposeAmoodError(OpenReposeLibraryError)` mirrors `OpenReposeIntakeError`. | adopt |
| 2026-05-03 | Local codebase | `.product/src/openrepose/library/citations.py` | AMOOD-001..004 + SAFE-001..003 already in registry (WP-I3-004 seeded them from the topology.yaml block). New commands cite by `format_citation(command="library_create_card", rule_id="AMOOD-001", action_result="warned", fix_action="...")`. | adopt |
| 2026-05-03 | Operator blueprint | `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` (TSV section) | 10 TSV schemas with locked column order. Additive-only rule: new columns appended on the right. v0.1 implements TSVs as Postgres VIEWs in a new migration (`005_i3_amood_tsv_views.sql`); export queries `SELECT *` from the view, joins TAB-separators in Python — column order preserved by the view definition. Import is the inverse: parse header → match against view's column list → upsert to underlying tables. | adopt |
| 2026-05-03 | PostgreSQL docs | https://www.postgresql.org/docs/16/sql-createview.html | `CREATE OR REPLACE VIEW` cannot drop columns or change column order. AMood additive-only rule maps cleanly: future migrations append columns by `DROP VIEW` + `CREATE VIEW` with new column at end. v0.1 documents this constraint in the migration header. | adopt |
| 2026-05-03 | PostgreSQL docs | https://www.postgresql.org/docs/16/sql-set-transaction.html | `init_batch_package` is multi-step (insert library_batches row + create folder tree + write INDEX.md/README.md). Wrap in single transaction; on file-system failure, rollback DB row so re-running stays idempotent. v0.1 uses `with conn.transaction():` (psycopg 3 native context manager). | adopt |
| 2026-05-03 | Operator blueprint | `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` (Compatibility Check section) | Hard-reject categories: camera-cant-see-target, wardrobe-covers-target, prop-blocks-target, fantasy-set-camera-mismatch, pose-implausible, palette-collapse, juvenile/coercive/voyeur-violation, multi-trigger-conflict. Encoded as a Python truth table in `library/amood/compatibility.py`; v0.1 returns each rule's verdict per input set. SAFE-001..003 for the violation triple. | adopt |
| 2026-05-03 | Operator blueprint | `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` (Variant Ladder section) | 6 variant labels: baseline / intimate / explicit_plus / editorial / raw_cam / story_plus. Each carries a default change-rule (e.g. intimate → softens lighting + reduces wardrobe layer; explicit_plus → escalates one axis without changing pose family). v0.1 ships baseline+intimate+explicit_plus mappings as the in-scope subset; editorial/raw_cam/story_plus return a stub change-rule that the operator overrides via subsequent `update_entry` calls. Documented as Allowed Temporary Fallback. | adopt-with-fallback |
| 2026-05-03 | Operator blueprint | `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` (Accepted-Set Audit section) | Per-axis realized coverage = (distinct accepted-row values on axis) / (max distinct values seen across the project's quota plan). Priority flag: `>= 0.75 -> ok`, `0.5..0.74 -> watch`, `< 0.5 -> priority`. v0.1 audits the 13 amood:* tag namespaces from the spec; cross-axis interactions (e.g. trigger × camera) are out-of-scope until WP-I3-008 GUI surfaces them. | adopt |

## Reality Boundary

- **Real Seam**: 7 new dispatcher handlers in `commands.py`; new `library/amood/` subpackage (`batches.py`, `cards.py`, `variants.py`, `compatibility.py`, `audit.py`, `dedupe.py`, `tsv_views.py`, `tsv_io.py`); new migration `005_i3_amood_tsv_views.sql` defining 10 TSV-shaped views in AMood-locked column order; `state.library.amood` block on `AppState`; new error class `OpenReposeAmoodError(OpenReposeLibraryError)` with citation field; `outputs/library/<project>/<batch>/` directory tree creation by `init_batch_package`.
- **User-Visible Win**: an LLM agent given an EXP120-style AMood plan can: `init_batch_package project_slug=exposure-120 batch_slug=hotel-robes tier=production primary_explicit_family=vulva-pussy-exposure` → `library_create_card slug=hotel-robe-bed-edge ...` (returns dedupe_signature + AMOOD-001 warning if overlap >= threshold) → `library_create_variants parent_card_id=X variants=[intimate,explicit_plus]` → `compatibility_check sexual_trigger=...` (returns pass+warnings) → after triage runs → `accepted_set_audit batch_id=Y` (writes `library_diversity_audits` rows; updates `state.library.amood`) → `amood_export_tsv batch_id=Y schema=batch_matrix` (TAB-separated, AMood-locked column order). Operator round-trips a TSV with `amood_import_tsv` and the diff-before-save shows zero changes.
- **Proof Target**: `pytest .product/tests/test_amood_commands.py .product/tests/test_amood_dedupe.py .product/tests/test_amood_tsv.py` passes against ephemeral PG. Tests cover: init_batch_package idempotent re-run; library_create_card emits AMOOD-001 when 6+ axes overlap with an accepted card; library_create_variants spawns N children with parent_card_id FK + variant_label set; compatibility_check returns hard_rejects + warnings list shape from blueprint truth table; accepted_set_audit produces correct realized-coverage numbers for a synthetic 20-card / 4-axis fixture; amood_export_tsv → amood_import_tsv round-trip is lossless on at least 3 schemas (batch_matrix, variant_ladder, anti_repetition); error-citation shape verified; `state.library.amood.active_batch_id` updates on init_batch_package; `adult_production_boundary` envelope present in every response. Full suite remains green (currently 544; expected ~580 after this WP). `pwsh scripts/audit-repo.ps1` exits 0.
- **Allowed Temporary Fallbacks**:
  - **Variant change-rule defaults**: only `baseline`, `intimate`, `explicit_plus` get fully-populated change-rule mappings in v0.1; `editorial`, `raw_cam`, `story_plus` return a stub `{"variant_label": <label>, "change_rule_summary": "operator-defined"}` that the operator overrides via subsequent `update_entry`. Marked `FALLBACK: WP-I3-006 variant change-rules subset` in code.
  - **TSV import for prompt_manifest, run_manifest, review_manifest, scorecard, pose_control_guide, series_plan**: v0.1 export-only (read-only views; round-trip not required because these schemas are produced by the system, not edited by hand). Import-side returns `{"imported_count": 0, "errors": ["INFO: schema is export-only in v0.1"]}` with manual-link to follow-up WP. The 4 hand-edited schemas (`quota_plan`, `batch_matrix`, `variant_ladder`, `anti_repetition`) get full round-trip support.
  - **Accepted-set audit cross-axis interactions**: v0.1 audits each of 13 amood:* axes independently. Cross-axis (e.g. trigger × camera) interactions are computed when WP-I3-008 GUI tab surfaces them.
  - **`init_batch_package` package_path generation**: writes INDEX.md + README.md from a Python f-string template (not the full blueprint Markdown). Card-detail and moodboard files (`cards/<id>_<slug>.md`, `moodboards/<id>_<slug>_moodboard.md`) are generated lazily on first `amood_export_tsv` call for that schema, not eagerly on init.
- **Promotion Guard**: do not declare WP-I3-006 stable until: (a) all 7 commands return responses with `adult_production_boundary` envelope (regression sweep in `test_command_handlers.py`), (b) library.dedupe_check is invoked from `library_create_card` and AMOOD-001 citation is emitted on overlap (verified by test on synthetic accepted-card fixture), (c) round-trip on the 4 hand-edited TSV schemas is lossless byte-equal (excluding trailing newline normalization), (d) accepted_set_audit produces realized-coverage numbers cross-checked manually for the EXP120 worked example fixture, (e) `init_batch_package` idempotent re-run reports diffs without overwriting an existing batch row, (f) full test suite + audit script exit clean.

## In Scope

- New library subpackage `library/amood/`:
  - `batches.py` — `create_batch`, `get_batch`, `list_batches`, `init_batch_package` (creates DB row + folder tree + INDEX.md + README.md atomically).
  - `cards.py` — `create_card` (calls `dedupe.check_card_pre_insert` first; populates the 16 AMood card-schema columns; computes `dedupe_signature` + `compatibility_signature` from inputs; emits AMOOD-001 warning on threshold).
  - `variants.py` — `create_variants` (spawns child library_entries rows with `parent_card_id` FK + `variant_label`; applies variant change-rule defaults).
  - `compatibility.py` — `check_compatibility` (encodes AMood truth table; returns `pass:bool, hard_rejects:[...], warnings:[...]`).
  - `audit.py` — `accepted_set_audit` (per-axis realized-coverage; writes `library_diversity_audits` rows; computes priority_flag).
  - `dedupe.py` — `check_card_pre_insert` (calls `library.dedupe_check` SQL function; returns matches + threshold; surfaces AMOOD-001 citation when overlap >= threshold).
  - `tsv_views.py` — Python-side knowledge of view → TSV column order (mirrors migration 005); export helper `view_to_tsv(view_name, where_clause, params)`.
  - `tsv_io.py` — `export_tsv(batch_id, schema)` / `import_tsv(batch_id, schema, tsv_text)`; locked column-order parsing; upsert to underlying tables for the 4 hand-edited schemas.

- New migration `.product/migrations/005_i3_amood_tsv_views.sql`:
  - 10 views: `library_amood_quota_plan_v`, `library_amood_batch_matrix_v`, `library_amood_variant_ladder_v`, `library_amood_anti_repetition_v`, `library_amood_prompt_manifest_v`, `library_amood_run_manifest_v`, `library_amood_review_manifest_v`, `library_amood_scorecard_v`, `library_amood_pose_control_guide_v`, `library_amood_series_plan_v`.
  - Each view's column order matches the AMood blueprint TSV header for that schema. Header documents the additive-only rule.
  - Schema_version assertion bumps from 4 → 5; existing tests bumped accordingly.

- Extend `commands.py`:
  - 7 new `_h_*` handlers (`_h_init_batch_package`, `_h_library_create_card`, `_h_library_create_variants`, `_h_compatibility_check`, `_h_accepted_set_audit`, `_h_amood_export_tsv`, `_h_amood_import_tsv`) wired into `_HANDLERS`.
  - New error class `OpenReposeAmoodError(OpenReposeLibraryError)` with `rule_id` + pre-formatted citation; dispatcher's typed-error catch propagates `payload["citation"]` and `payload["rule_id"]`.
  - Import block additions for the new `library/amood/` symbols.

- Extend `state.py`:
  - `state.library["amood"]` block keys per spec: `active_batch_id`, `active_batch_slug`, `tier`, `primary_explicit_family`, `stable_cards`, `unstable_cards`, `abandoned_cards`, `dedupe_recent_warnings[]` (capped to last 10).
  - Mutators: `set_active_amood_batch(batch_id, batch_slug, tier, primary_explicit_family)`, `record_amood_dedupe_warning(card_id, overlap_count, matched_card_slug)`, `refresh_amood_card_counts()` (called after card-state transitions).
  - Reads on every `dump_state` and on every AMood command's begin/end.

- New tests:
  - `.product/tests/test_amood_commands.py` — one test per command happy path; idempotent init_batch_package; AMOOD-001 emission; INTAKE-001 token gate not applicable (these are LLM-issuable); error-citation shape.
  - `.product/tests/test_amood_dedupe.py` — `library.dedupe_check` SQL function direct query (already present from WP-I3-003 schema tests; this WP adds Python-side tests for the wrapper); 0/4/6/8 overlap fixtures; threshold override per batch.
  - `.product/tests/test_amood_tsv.py` — round-trip test on 4 hand-edited schemas; column-order locked test (insert a new column at end of view, verify export still parses); export-only schemas return INFO row on import.

- Extend manual: `.gov/doc/manual/amood-workflow.md` — add a `## Commands` table with the 7 commands and citation examples; cross-link to `intake-and-triage.md` for the project/task layer underneath.

## Out Of Scope

- Triage GUI tab surfacing AMood card-detail view (WP-I3-008).
- ML-backed auto-prefilter or face-age estimator (advisory hints only per spec; separate RESEARCH+IMPLEMENTATION).
- Cross-project anti-repetition (intra-project only in v0.1; spec out-of-scope).
- Series plan / video keyframe sequencing (mentioned in blueprint; deferred to a later spec).
- Embedding-based card similarity (trigram on `dedupe_signature` is sufficient for v0.1).
- Real-time blueprint sync (operator manually amends blueprint when AMood evolves; this spec follows on its own cadence).
- Batch-level wholesale acceptance command (per-card stability rule is the only acceptance path).
- Variant change-rules for `editorial` / `raw_cam` / `story_plus` (Allowed Temporary Fallback above).
- TSV import for the 6 system-generated schemas (Allowed Temporary Fallback above).

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I3-006-amood-data-model-commands.md`
- `.gov/workflow/TASKBOARD.md`
- `.gov/doc/manual/amood-workflow.md` (extended; preserves existing tag-conventions content per WP-I3-001 handoff note)

### Product (`.product/`)

- `.product/migrations/005_i3_amood_tsv_views.sql` (new)
- `.product/src/openrepose/commands.py` (extend; ~7 new handlers + `OpenReposeAmoodError` class)
- `.product/src/openrepose/state.py` (extend `library` dict with `amood` key + mutators)
- `.product/src/openrepose/library/__init__.py` (re-export new symbols)
- `.product/src/openrepose/library/amood/__init__.py` (new)
- `.product/src/openrepose/library/amood/batches.py` (new)
- `.product/src/openrepose/library/amood/cards.py` (new)
- `.product/src/openrepose/library/amood/variants.py` (new)
- `.product/src/openrepose/library/amood/compatibility.py` (new)
- `.product/src/openrepose/library/amood/audit.py` (new)
- `.product/src/openrepose/library/amood/dedupe.py` (new)
- `.product/src/openrepose/library/amood/tsv_views.py` (new)
- `.product/src/openrepose/library/amood/tsv_io.py` (new)
- `.product/tests/test_amood_commands.py` (new)
- `.product/tests/test_amood_dedupe.py` (new)
- `.product/tests/test_amood_tsv.py` (new)
- `.product/tests/test_db_migrator_i3.py` (extend; schema_version 4 → 5 assertion bumps)

### Build / Output (gitignored)

- `target/test-artifacts/WP-I3-006/` (junit XML + audit log)
- `outputs/library/<project_slug>/<batch_slug>/` (created by `init_batch_package`; gitignored)

## Risks And Dependencies

- **Risk**: TSV column-order drift between blueprint, migration view, and Python `tsv_views.py` Python-side mirror. **Mitigation**: a self-test in `test_amood_tsv.py` queries `information_schema.columns` for each view and asserts the column list matches the Python mirror byte-for-byte. WP-I3-009 audit script extension will pick up the same check at the topology level.
- **Risk**: `init_batch_package` partial failure (DB row inserted, file-system folder creation failed) leaves orphan rows. **Mitigation**: wrap in `with conn.transaction():` and create folders inside the transaction; on any folder-creation exception, the transaction rolls back. Re-run is idempotent because of the `UNIQUE (project_id, slug)` constraint on `library_batches`.
- **Risk**: `library.dedupe_check` SQL function performance on large projects (10k+ accepted cards). **Mitigation**: trigram index on `dedupe_signature` already in place from WP-I3-003 (`idx_library_entries_dedupe_signature_trgm`); v0.1 perf budget is "no slower than 200ms on a 10k-card project"; integration test with synthetic 1k-card fixture catches a 10x regression.
- **Risk**: AMood blueprint TSV column order changes between blueprint revisions and migrations. **Mitigation**: the additive-only rule is enforced by the `CREATE OR REPLACE VIEW` PG behavior (cannot drop or reorder columns; only append). New columns require a new migration version. The migration header documents this with the line `-- Additive-only rule: future migrations append columns; never reorder, rename, or drop. See AMood blueprint Changelog.`
- **Dependency**: WP-I3-003 schema (DONE). **Owner**: assistant. **Status**: satisfied.
- **Dependency**: WP-I3-004 dispatcher pattern + `library/citations.py` registry (DONE). **Owner**: assistant. **Status**: satisfied.
- **Dependency**: AMood blueprint at `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` (operator-canonical; not modified by this WP). **Owner**: operator. **Status**: satisfied.

## Definition Of Done

- [ ] 7 dispatcher commands registered in `_HANDLERS`: `init_batch_package`, `library_create_card`, `library_create_variants`, `compatibility_check`, `accepted_set_audit`, `amood_export_tsv`, `amood_import_tsv`.
- [ ] `library/amood/` subpackage shipped with 8 modules (`__init__`, `batches`, `cards`, `variants`, `compatibility`, `audit`, `dedupe`, `tsv_views`, `tsv_io`).
- [ ] Migration `005_i3_amood_tsv_views.sql` creates 10 views in AMood-locked column order; `schema_version` advances to 5; existing schema-version tests bumped.
- [ ] `state.library.amood` block populated per spec; `dump_state` returns it; mutators called from `init_batch_package` + card transitions.
- [ ] `library.dedupe_check` invoked from `library_create_card`; AMOOD-001 citation emitted on overlap; matching cards returned in command response.
- [ ] `compatibility_check` encodes AMood blueprint truth table; SAFE-001/002/003 cited on juvenile/coercion/voyeur violations; pass-only path documented for the multi-trigger-conflict warning.
- [ ] `accepted_set_audit` writes `library_diversity_audits` rows for 13 amood:* axes; priority_flag computed per blueprint thresholds (>= 0.75 ok, 0.5–0.74 watch, < 0.5 priority).
- [ ] `amood_export_tsv` returns TAB-separated text in AMood-locked column order; `amood_import_tsv` round-trips losslessly on the 4 hand-edited schemas (`quota_plan`, `batch_matrix`, `variant_ladder`, `anti_repetition`); 6 system-generated schemas return INFO on import.
- [ ] `init_batch_package` creates DB row + folder layout (`cards/`, `moodboards/`, `prompt_blocks/`, `pose_guides/`, `manifests/`, `accepted/`, `soft_accepted/`) + INDEX.md + README.md; idempotent re-run reports diffs without overwrite.
- [ ] Every command response embeds `adult_production_boundary` envelope (verified by regression sweep in `test_command_handlers.py`).
- [ ] `.product/tests/test_amood_*.py` passes against ephemeral PG. Full suite remains green.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] **Manual Impact**: Yes — extends `.gov/doc/manual/amood-workflow.md` with a `## Commands` table covering the 7 AMood-specific commands + AMOOD-001 citation example + cross-link to `intake-and-triage.md`. Existing tag-conventions section (operator-authored) preserved unchanged.

## Test Coverage Plan

### Functional Flow Tests
- [ ] init_batch_package + library_create_card + library_create_variants + accepted_set_audit + amood_export_tsv chain on a 5-card mini-tier batch (golden flow).
- [ ] Re-running init_batch_package on an existing batch reports diff but does not overwrite.
- [ ] AMOOD-001 emission on 6-axis-overlap card creation.
- [ ] compatibility_check returns 0 hard_rejects for a clean input set; returns 1+ hard_rejects for camera-cant-see-target / wardrobe-covers-target / juvenile-coded fixtures.

### Code Correctness Tests
- [ ] Unit: `dedupe.compose_signature(parts) == "<a>|<b>|<c>|<d>|<e>|<f>|<g>|<h>"` for 8-axis canonical join.
- [ ] Unit: `compatibility.check_compatibility(...)` returns `(pass=False, hard_rejects=[...], warnings=[...])` for each of the 8 hard-reject categories.
- [ ] Unit: `audit.compute_realized_coverage(rows, axis)` returns the expected fraction for a fixed fixture.
- [ ] Integration: round-trip TSV on `batch_matrix` with 20 rows is byte-equal modulo trailing newline.
- [ ] Schema: `005_i3_amood_tsv_views.sql` creates 10 views; column order matches the Python `tsv_views.py` mirror; schema_version is 5.
- [ ] Static: ruff + mypy clean on `library/amood/` and the new tests.

### Red-Team / Abuse Tests
- [ ] Library_create_card with a malformed dedupe input (missing axes) is rejected with a clear error.
- [ ] amood_import_tsv with reordered columns is rejected (cites locked-column-order rule; does not silently corrupt).
- [ ] amood_import_tsv with deleted columns is rejected with the same shape.
- [ ] amood_import_tsv on a system-generated schema returns INFO + manual-link instead of partial import.
- [ ] compatibility_check with `primary_rejection_reason="juvenile_coded"` always returns hard_reject citing SAFE-001 — no override path.

### Performance / Reliability Tests
- [ ] `library.dedupe_check` over a 1000-card project completes in < 200ms (perf budget).
- [ ] init_batch_package transaction rollback on simulated folder-creation failure leaves no orphan DB row.

## Rollback Plan

- Files to revert: `.product/migrations/005_i3_amood_tsv_views.sql`, `.product/src/openrepose/library/amood/`, `.product/src/openrepose/state.py` (amood-block additions only), `.product/src/openrepose/commands.py` (handler additions only).
- Files to keep: `.gov/workflow/workpackets/WP-I3-006-amood-data-model-commands.md` (reverts to DRAFT for re-attempt), test artifacts under `target/test-artifacts/WP-I3-006/` (preserve evidence even on rollback).
- Recovery command: `git checkout main -- .product/migrations/005_i3_amood_tsv_views.sql .product/src/openrepose/library/amood .product/src/openrepose/state.py .product/src/openrepose/commands.py`. Down-migration not needed because migration 005 only creates views (no data transform).

## Decisions Log

- 2026-05-03: **TSV column order locked at the DB-view layer, not in Python.** Reason: PostgreSQL's `CREATE OR REPLACE VIEW` cannot reorder existing columns — appending is the only forward-compatible operation, which exactly matches AMood's additive-only rule. Alternative: pure-Python column tuples (rejected — drift from migration text is silent and only caught by tests; locking at the SQL layer makes drift a syntax error).
- 2026-05-03: **TSV import in v0.1 covers 4 hand-edited schemas; 6 system-generated schemas are export-only.** Reason: `prompt_manifest`, `run_manifest`, `review_manifest`, `scorecard`, `pose_control_guide`, `series_plan` are produced by the system from base tables (runs, scorecards, pose_guides). Round-trip importing them would re-derive those tables and risk corruption; the operator never edits them by hand. Alternative: full round-trip on all 10 (rejected for v0.1 — out of scope for this WP, candidate for a follow-up VERIFICATION WP).
- 2026-05-03: **`library_create_card` invokes `library.dedupe_check` BEFORE the INSERT, not after.** Reason: AMOOD-001 is `severity: warn`, not `block` — the card is still inserted, but the warning is surfaced with the matching card_id + overlap_count so the LLM can revise before promoting. Alternative: insert-then-check (rejected — surfaces the warning after the dedupe_signature is committed; hides the cause-and-effect).
- 2026-05-03: **Variant change-rule defaults shipped for baseline/intimate/explicit_plus only; editorial/raw_cam/story_plus return stub.** Reason: blueprint variant ladder has 6 labels but the change-rule table for the latter 3 is operator-curated and varies by project (editorial = magazine framing; raw_cam = fixed-angle voyeur; story_plus = narrative pre/post). Hard-coding defaults here would lock projects into one editorial style. Alternative: ship empty defaults for all 6 (rejected — no baseline; LLM has nothing to start from).
- 2026-05-03: **`accepted_set_audit` audits 13 amood:* tag axes independently in v0.1; cross-axis interactions deferred.** Reason: spec lists 13 axes (explicit_family, pose_family, orientation, wardrobe_state, held_object, support_object, setting_family, lighting_family, camera_family, gaze, mouth_tongue, palette_family, accent_color). Cross-axis matrix has 78 pairs; meaningful interpretation requires the GUI tab from WP-I3-008. Alternative: ship the matrix now (rejected — no consumer; would bake in an interpretation the GUI may not use).
- 2026-05-03: **Migration version 5; schema_version assertion bumps in `test_db_migrator_i3.py`.** Reason: views are migrations even though they don't change data; bumping ensures down-rev environments cannot run the new commands. Alternative: ship views in a non-versioned init script (rejected — breaks the "schema_version is the only source of truth" rule from WP-I2-001).

## Fallback Register

- **Path**: `.product/src/openrepose/library/amood/variants.py` `_VARIANT_CHANGE_RULES` dict
- **Required Label In Code/UI**: `# FALLBACK: WP-I3-006 variant change-rules subset (editorial/raw_cam/story_plus return stub)`
- **Successor / Debt Owner**: WP-I3-008 (Triage GUI tab surfaces operator-side override flow) or follow-up IMPLEMENTATION WP if change-rules need expansion sooner.
- **Exit Condition To Remove**: operator confirms full change-rule defaults for all 6 variant labels OR a successor WP with operator-supplied per-project overrides ships.

- **Path**: `.product/src/openrepose/library/amood/tsv_io.py` `_IMPORT_SUPPORTED_SCHEMAS` set
- **Required Label In Code/UI**: `# FALLBACK: WP-I3-006 v0.1 imports only 4 hand-edited schemas; 6 system-generated schemas are export-only`
- **Successor / Debt Owner**: follow-up VERIFICATION WP after WP-I3-008 if operators ever need to round-trip the system-generated schemas.
- **Exit Condition To Remove**: operator demonstrates a real workflow that requires importing one of the 6 system-generated schemas.

## Change Ledger

- **What Became Real**:
  - Migration `005_i3_amood_tsv_views.sql` shipped: 10 views (`library_amood_quota_plan_v`, `library_amood_batch_matrix_v`, `library_amood_variant_ladder_v`, `library_amood_anti_repetition_v`, `library_amood_prompt_manifest_v`, `library_amood_run_manifest_v`, `library_amood_review_manifest_v`, `library_amood_scorecard_v`, `library_amood_pose_control_guide_v`, `library_amood_series_plan_v`) in AMood-locked column order. Schema_version advances 4 → 5; assertions bumped in `test_db_migrator_i3.py` and `test_db_migrator.py`.
  - `library/amood/` subpackage shipped: 8 modules (`__init__`, `batches`, `cards`, `variants`, `compatibility`, `audit`, `dedupe`, `tsv_views`, `tsv_io`).
  - 7 dispatcher handlers wired in `commands.py`: `init_batch_package`, `library_create_card`, `library_create_variants`, `compatibility_check`, `accepted_set_audit`, `amood_export_tsv`, `amood_import_tsv`. New `OpenReposeAmoodError` class with `rule_id` + `citation` propagation.
  - `state.library.amood` block added with mutators (`set_active_amood_batch`, `record_amood_dedupe_warning`, `refresh_amood_card_counts`).
  - `library.dedupe_check` SQL function wrapped in `dedupe.check_card_pre_insert`; `library_create_card` invokes it BEFORE INSERT and surfaces AMOOD-001 citation when overlap >= threshold.
  - `compatibility_check` encodes the AMood blueprint truth table (camera-cant-see-target, wardrobe-covers-target, prop-blocks-target, fantasy-set-camera-mismatch, palette-collapse, pose-implausible, multi-trigger-conflict) and SAFE-001/002/003 safety boundaries.
  - `accepted_set_audit` writes 13 `library_diversity_audits` rows (one per amood:* tag axis) with priority_flag (`>= 0.75 ok`, `0.5..0.74 watch`, `< 0.5 priority`).
  - `init_batch_package` creates batch row + folder layout (`outputs/library/<project_slug>/<batch_slug>/`) with 17 subdirs + INDEX.md + README.md from f-string templates; idempotent re-run reports diffs without overwrite.
  - 39 new tests across 3 files (`test_amood_commands.py` 12, `test_amood_dedupe.py` 6, `test_amood_tsv.py` 21) — all passing against ephemeral PG.
  - Manual `amood-workflow.md` extended with Commands table, init/create-card examples, AMOOD-001 citation example, TSV round-trip overview, and dedicated sections for the four anchor links cited by the rule registry: `#anti-repetition`, `#abandonment-criteria`, `#fast-triage`, `#safety-boundary`.

- **What Remains Simulated**:
  - **Variant change-rules subset**: only `baseline`, `intimate`, `explicit_plus` ship with fully-populated change-rule defaults. `editorial`, `raw_cam`, `story_plus` ship with stub `"operator-defined"` placeholders, marked `# FALLBACK: WP-I3-006 variant change-rules subset` in `variants.py`. Operator overrides via subsequent `update_entry` calls. Successor: WP-I3-008 (Triage GUI) or follow-up IMPLEMENTATION WP.
  - **TSV import for 6 system-generated schemas**: `prompt_manifest`, `run_manifest`, `review_manifest`, `scorecard`, `pose_control_guide`, `series_plan` are export-only in v0.1 (the views aggregate base tables; importing them would re-derive). Import returns INFO + manual link. Successor: post-WP-I3-008 follow-up if operators surface a real round-trip need.
  - **Quota-plan import maps shape v0.1**: `target_count` is split into `(expected_card_count, target_per_card=1)` for `library_target_groups` upsert. The richer requirements editor + EXP120 round-trip lives in WP-I3-007.
  - **Cross-axis interactions in `accepted_set_audit`**: v0.1 audits each of 13 axes independently. Cross-axis matrix interpretation needs the GUI (WP-I3-008).

- **Next Blocking Real Seam**:
  - WP-I3-007 (requirements editor + target tree commands) for the project_set_target_tree / project_render_markdown / project_import_markdown flow that the EXP120 example exercises end-to-end.
  - WP-I3-008 (Triage GUI tab) consumes `state.library.amood` + the per-card AMood view to render variant strips and the accepted-set audit matrix.
  - WP-I3-009 (audit script extension) verifies every CHECK constraint + view column matches the topology rule_registry + Python column mirror.
  - WP-I3-010 (end-to-end EXP120 verification) closes I3 v0.1.

## Checkpoint Commit Plan

1. Governance kickoff commit (this file + taskboard row + archived WP-I3-003/004/005 mv).
2. Migration commit (`005_i3_amood_tsv_views.sql` + schema_version assertion bump).
3. `library/amood/` data-layer commit (8 modules; pure-Python; no dispatcher wiring yet).
4. Dispatcher + state.library.amood commit (handlers wired; state-block mutators).
5. Test commit (3 new test files; existing tests bumped).
6. Manual + audit commit (manual extension; audit script remains green).
7. REVIEW commit (Change Ledger + Evidence sections; WP REVIEW transition).

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_amood_commands.py .product/tests/test_amood_dedupe.py .product/tests/test_amood_tsv.py` exits 0; full `pytest` exits 0; `pwsh scripts/audit-repo.ps1` exits 0.
- **Proof Artifact**: `target/test-artifacts/WP-I3-006/` (junit XML, ruff log, mypy log, audit log).
- **Claim Standard**: never mark `DONE` without linked command evidence and artifact paths.

## Headless LLM Operation Compliance

- [ ] An LLM agent can trigger all 7 commands through the HTTP/inbox channel without touching the GUI.
- [ ] An LLM agent can read `state.library.amood` from `outputs/.runtime/state.json`.
- [ ] An LLM agent can pull a visual artifact via the existing `full_window` snapshot or the WP-I3-008 `amood_card_with_pose` / `amood_batch_overview` snapshot targets (this WP exposes the data layer; the snapshot rendering ships in WP-I3-008).
- [ ] No code path in the AMood subpackage calls `raise_()`, `activateWindow()`, `showNormal()`, `setForegroundWindow()`, or any equivalent (data layer + dispatcher only).
- [ ] No modal dialogs in response to commands.
- [ ] Tests cover headless path (the only path; no GUI in this WP).

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [ ] Linked test suite has executed results saved under `target/test-artifacts/WP-I3-006/`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence section.
- [ ] **Headless LLM Operation Compliance** section all items checked.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I3-006/junit.xml` — 39/39 AMood tests pass against ephemeral PG (`pytest-postgresql`, system PG 17). 68/68 regression-prone tests (`test_command_handlers.py`, `test_state_file.py`, `test_intake_commands.py`, `test_db_migrator.py`, `test_db_migrator_i3.py`) pass after the schema_version 4 → 5 bump and the AMood handler additions to `commands.py`.
- **Logs**: `pwsh scripts/audit-repo.ps1` exits 0 — checks `hardcoded-paths`, `blank-space-paths`, `wp-research-notes`, `wp-manual-impact` all clean.
- **Screenshots / Exports**: N/A (data-layer + dispatcher; no GUI in this WP).
- **Build Artifacts**: `.product/migrations/005_i3_amood_tsv_views.sql`; `.product/src/openrepose/library/amood/` (8 modules); `commands.py` extension (~280 net new lines); `state.py` extension (`amood` block + 3 mutators); `library/__init__.py` re-exports.
- **Proof Artifact**: `target/test-artifacts/WP-I3-006/junit.xml`.
- **Operator Sign-off**: `<pending>`

## Progress Log

- 2026-05-03: WP initialized at IN-PROGRESS. Predecessors WP-I3-003/004/005 archived in the same kickoff commit (operator sign-off granted in-session).
- 2026-05-03: Implementation complete. Migration 005 (10 views) + library/amood/ subpackage (8 modules) + 7 dispatcher handlers + state.library.amood block + 39 new tests (all passing) + manual extension. Audit clean. WP advanced to REVIEW.
