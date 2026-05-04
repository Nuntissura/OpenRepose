# WP-I3-007 — Requirements Editor + Target Tree Commands

## Header

- **Owner**: `assistant`
- **Date Opened**: `2026-05-03`
- **Last Updated**: `2026-05-03`
- **Status**: `DONE`
- **Iteration**: `I3`
- **Workflow Version**: `1.1`
- **Packet Class**: `IMPLEMENTATION`
- **Effort Estimate**: `L`
- **Linked Spec**: `.gov/spec/openrepose_requirements_v0_1.md`
- **Linked Test Suite**: `.product/tests/test_library_requirements.py`, `.product/tests/test_library_targets.py`, `.product/tests/test_library_requirements_markdown.py`
- **Linked Check Script**: `scripts/audit-repo.ps1` (must pass — extended in WP-I3-009)

## Intent

An LLM agent or operator drops a markdown file describing the EXP120 quota plan and requirements; OpenRepose materializes the target tree (`library_target_groups` + `library_target_cards`) and the project-scoped rules (`library_rules`), then renders the same content back to markdown. The render → DB → render cycle is byte-stable. `state.library.targets` reflects roll-up counters from `library_target_card_counts` so an LLM can self-pace by reading `gap` and `forecast_ok`. After this WP, EXP120's `target_promoted=960` is reachable as a structured DB target tree, and `target_summary` returns the correct flags at every scope.

## Linked Workpackets

- **Predecessor(s)**: `WP-I3-001` (DONE — locked spec), `WP-I3-003` (DONE — schema migration 004 created the tables and view), `WP-I3-004` (DONE — `library_projects` + intake commands; this WP composes on top), `WP-I3-006` (DONE — citation patterns + state-mutation patterns to mirror)
- **Successor(s)**: `WP-I3-008` (Triage GUI tab — reads `state.library.targets`), `WP-I3-010` (end-to-end EXP120 verification)
- **Blocks**: `WP-I3-008`, `WP-I3-010`
- **Blocked-By**: `none`
- **Related**: `WP-I3-009` (REVIEW — its `[citations-cite-real-rule-ids]` check validates that this WP cites real rule_ids)

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_requirements_v0_1.md` § "Requirement Anatomy" (8 kinds + custom)
- `.gov/spec/openrepose_requirements_v0_1.md` § "Inheritance" (lower scope wins; `REQ-001`)
- `.gov/spec/openrepose_requirements_v0_1.md` § "Target Tree" (groups + cards + counts view)
- `.gov/spec/openrepose_requirements_v0_1.md` § "Counters and Satisfaction Semantics" (`fully_satisfied = count_satisfied AND quota_satisfied`; `TARGET-001/002/003`)
- `.gov/spec/openrepose_requirements_v0_1.md` § "EXP120 Worked Example" (round-trip canonical form)
- `.gov/spec/openrepose_requirements_v0_1.md` § "Commands" (8 dispatcher handlers)
- `.gov/spec/openrepose_rules_v0_1.md` § "Error Citation Contract" (canonical rejection shape)
- `.gov/topology.yaml` § `i3_command_surface.requirements_and_targets:` (8 commands declared)
- `.gov/topology.yaml` § `requirements_kinds.values:` (8-kind taxonomy)

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Repo `pyproject.toml` | n/a | PyYAML is NOT a dependency. Adding it would expand the dep surface for a feature that only needs to round-trip a tightly-controlled internal form. | reject (use hand-rolled markdown canonical form) |
| 2026-05-03 | Existing `library/intake/projects.py` (WP-I3-004) | n/a | Pattern: dataclass per row, module-level CRUD functions taking `psycopg.Connection`, dispatcher controls transaction boundaries. This WP mirrors that shape for `requirements/` + `targets.py`. | adopt |
| 2026-05-03 | Existing `commands.py _h_init_batch_package` (WP-I3-006) | n/a | Pattern: `_ensure_pool(d)` → connection → call data-layer → mutate `d.state.set_*` → `set_guidance(...)` with `next_valid_actions`. Same pattern for the 8 new handlers. | adopt |
| 2026-05-03 | Spec § "Counters and Satisfaction Semantics" + migration 004 view | n/a | `library_target_card_counts` already aggregates per-status counts per card. Group-level and project-level rollups are SUM aggregations over this view; spec's "materialized variants may be added later if performance requires" — v0.1 stays with the view + ad-hoc SUM. | adopt |
| 2026-05-03 | Spec § "EXP120 Worked Example" (operator markdown vs. structured rows) | n/a | The spec shows two forms: operator natural-prose + canonical structured-row form. Round-trip requirement is strict only on the canonical form (render → import → render = byte-equal). Natural-prose import is a v0.2 stretch goal. | adopt (canonical-only round-trip in v0.1) |
| 2026-05-03 | Handoff note `.gov/doc/handoff-2026-05-03-i3-implementation-phase-2.md` | n/a | "Markdown round-trip is the EXP120 acceptance gate. Lossy parsing here is unacceptable; project_export_markdown -> project_import_markdown -> project_export_markdown must be byte-equal modulo trailing newline. Write that test first." Tests-first workflow. | adopt |
| 2026-05-03 | `library/citations.py` (WP-I3-006) | n/a | Adding new project-scoped rule_ids (e.g. EXP120-RES-001) does NOT extend `_REGISTRY`; project-scoped rules live in DB via `library_rules`. Audit check #6 already excludes project-scoped families from violation. | adopt (project-scoped stays in DB only) |

## Reality Boundary

Sacred. Captured before work starts.

- **Real Seam**: 8 dispatcher commands (`project_set_target_tree`, `project_add_requirement`, `project_set_requirement`, `project_dump_requirements`, `project_render_markdown`, `project_import_markdown`, `target_summary`, `target_recount`); two new product modules (`library/requirements/` subpackage + `library/targets.py`); new `OpenReposeRequirementsError(OpenReposeLibraryError)` carrying citation; new `state.library.targets` block + `set_targets_state` mutator; canonical markdown render+parse pair stable on EXP120 example.
- **User-Visible Win**: an LLM agent can run `project_import_markdown(project_id, md)` with the EXP120 worked-example markdown, then run `target_summary(scope=project)` and see `total target_promoted=960`, `gap=...`, `forecast_ok=...`. The same LLM can run `project_render_markdown(project_id)` and get back equivalent canonical markdown. `state.library.targets` reflects the tree at every dispatcher tick.
- **Proof Target**: `pytest .product/tests/test_library_requirements.py .product/tests/test_library_targets.py .product/tests/test_library_requirements_markdown.py` returns 0 failures against an ephemeral PostgreSQL instance (pytest-postgresql, already in dev deps). Specifically:
  - Round-trip test `test_exp120_canonical_round_trip_byte_stable` uploads the EXP120 canonical markdown, re-renders, and asserts byte-equal to the original (modulo trailing newline).
  - Counter test `test_target_summary_aggregates_promoted_counts` seeds outputs across pending/promoted/diagnostic states and asserts roll-up at card / group / project scope.
  - Inheritance test `test_card_scope_overrides_project_scope` adds REQ at project scope, overrides at card scope, asserts `project_dump_requirements(scope='card', scope_id=X)` reports the overridden rule with `inherited_from` populated.
- **Allowed Temporary Fallbacks**: (a) `custom` kind not parsed in v0.1 markdown round-trip (deferred to v0.2 per spec out-of-scope); (b) operator natural-prose markdown not round-tripped — only canonical form. Both labeled in code with `# v0.1: ` comment.
- **Promotion Guard**: do not transition WP to REVIEW until: round-trip test green on EXP120 example; `target_summary` returns correct values at all 4 scope_types; `audit-repo.ps1` clean (no new violations from new rule_id citations).

## In Scope

- 8 dispatcher commands listed above.
- New subpackage `.product/src/openrepose/library/requirements/` with modules:
  - `errors.py` — `OpenReposeRequirementsError` (mirror of intake/amood error shape).
  - `rules.py` — CRUD on `library_rules` (project-scoped); inheritance resolution.
  - `markdown_io.py` — render + parse canonical markdown; round-trip stable.
  - `__init__.py` — export the public surface.
- New module `.product/src/openrepose/library/targets.py` — CRUD on `library_target_groups` + `library_target_cards`; counter aggregation off `library_target_card_counts` view; satisfaction flag computation.
- `state.library.targets` tree-shaped block + `set_targets_state` mutator on `AppState` (mirror of `set_intake_state`).
- New rule citations cited in error responses use canonical shape from `openrepose_rules_v0_1.md`. Global rule_ids (`REQ-001`, `REQ-003`, `TARGET-001`, `TARGET-002`, `TARGET-003`) cited where appropriate; project-scoped rule_ids (`EXP120-*`) authored only via `project_add_requirement` (not hardcoded).
- Tests:
  - `.product/tests/test_library_requirements.py` — CRUD + inheritance + 8-kind validation + citation propagation.
  - `.product/tests/test_library_targets.py` — target-tree CRUD; `library_target_card_counts` rollup at card/group/project; `forecast_ok` / `count_satisfied` / `fully_satisfied` math.
  - `.product/tests/test_library_requirements_markdown.py` — round-trip on EXP120 canonical example; round-trip on edge cases (empty `accept_terms`, unicode in `short`, max-length groups).

## Out Of Scope

- `custom` kind in markdown round-trip (deferred to v0.2 per spec).
- Operator natural-prose markdown parsing (the section-headed prose form in the spec). v0.1 round-trips only the canonical form this WP defines.
- ML-backed automatic evaluation of body/pose/face requirements.
- Cross-project requirement copy.
- LLM-issued project-scope requirement authoring (operator-only in v0.1).
- Mid-flight retargeting that re-evaluates already-promoted outputs.
- Materialized counter views (spec says "may be added later if performance requires").
- GUI for the requirements editor (WP-I3-008 follows; this WP is the headless backend).

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I3-007-requirements-editor-target-tree.md` (this file)
- `.gov/workflow/TASKBOARD.md`

### Product (`.product/`)

- `.product/src/openrepose/library/requirements/__init__.py` (new subpackage)
- `.product/src/openrepose/library/requirements/errors.py` (new)
- `.product/src/openrepose/library/requirements/rules.py` (new)
- `.product/src/openrepose/library/requirements/markdown_io.py` (new)
- `.product/src/openrepose/library/targets.py` (new)
- `.product/src/openrepose/state.py` (extend `library` block + add `set_targets_state` mutator)
- `.product/src/openrepose/commands.py` (add 8 handlers + register in `_HANDLERS` + new `OpenReposeRequirementsError`)
- `.product/tests/test_library_requirements.py` (new)
- `.product/tests/test_library_targets.py` (new)
- `.product/tests/test_library_requirements_markdown.py` (new)

### Build / Output (gitignored)

- `target/test-artifacts/WP-I3-007/junit.xml`
- `target/test-artifacts/WP-I3-007/audit-clean.txt`

## Risks And Dependencies

- **Risk**: hand-rolled markdown round-trip is brittle on whitespace and ordering. **Mitigation**: deterministic render order (groups by `ordering` then `slug`, requirements by `rule_id` sort). Round-trip test is the primary acceptance gate; runs before any other test passes are claimed.
- **Risk**: `library_target_card_counts` view aggregates only against `library_outputs.status` populated by intake. If a project has groups + cards but no outputs yet, every counter is 0 — that's correct, but tests need to handle the empty case explicitly. **Mitigation**: test fixture seeds at least one card with at least one output of each status.
- **Risk**: 8-kind taxonomy plus `custom` plus the 4-tier severity create a large set of (kind, severity) combinations. The CHECK constraints in migration 004 enforce both enums; spec § "Severity Tiers" defines which severity is appropriate per kind (hard_output → auto-route or block; body/pose/face → warn or info; quality → warn). **Mitigation**: command layer rejects nonsensical combos (e.g. `kind=hard_output severity=info` is allowed by the DB but warned at command layer with a citation to `REQ-003`).
- **Risk**: Inheritance chain query must walk scope hierarchy correctly (card → batch → task → project). **Mitigation**: SQL ORDER BY scope precedence; tests cover the override case explicitly.
- **Dependency**: PostgreSQL with the I3 schema (migration 004 applied). **Owner**: operator. **Status**: satisfied (WP-I3-003 DONE).
- **Dependency**: `pytest-postgresql` ≥ 6.0 (already in dev deps). **Status**: satisfied.

## Definition Of Done

- [x] `library/requirements/` subpackage exists with `errors.py`, `rules.py`, `markdown_io.py`, `__init__.py` exporting `OpenReposeRequirementsError`, `LibraryRule`, `create_rule`, `update_rule`, `dump_rules`, `render_markdown`, `parse_markdown`.
- [x] `library/targets.py` exists with `LibraryTargetGroup`, `LibraryTargetCard`, `set_target_tree`, `project_summary`, `group_summary`, `card_summary`, `target_recount`, `state_targets_block` (compute_satisfaction_flags collapsed into `TargetSummary.to_dict(quota_satisfied=...)`; cleaner separation than the originally-sketched helper).
- [x] `OpenReposeRequirementsError` in `library/requirements/errors.py` carries `rule_id` + `citation`. Listed in `commands.py` dispatcher's typed-catch alongside `OpenReposeIntakeError` / `OpenReposeAmoodError`; all 8 new handlers raise it on validation failure.
- [x] 8 dispatcher commands registered in `_HANDLERS`: `project_set_target_tree`, `project_add_requirement`, `project_set_requirement`, `project_dump_requirements`, `project_render_markdown`, `project_import_markdown`, `target_summary`, `target_recount`. `_HANDLERS` count: 55 → 63.
- [x] `topology.yaml` `i3_command_surface.requirements_and_targets:` lists all 8 (locked at WP-I3-001; audit check #7 confirms each command resolves).
- [x] `state.library.targets` block populated by `set_targets_state(project=..., groups=[...], active_task=..., active_card=...)` mutator on `AppState`. Refreshed automatically by `_refresh_targets_state` after each project_set_target_tree / project_import_markdown call.
- [x] **Round-trip test**: `test_exp120_canonical_round_trip_byte_stable` passes — render of imported EXP120 canonical markdown is byte-equal to the original. Plus `test_exp120_double_round_trip_stable` (render(parse(render(parse(md)))) == render(parse(md))) and `test_import_then_render_markdown_byte_stable_via_dispatcher` (full round-trip through the dispatcher / DB / dispatcher path).
- [x] **Counter test**: `test_target_summary_aggregates_promoted_counts` passes — synthetic project with 5 promoted + 2 pending + 2 rejected outputs across 2 cards in 1 group reports correct rollups at card / group / project scope.
- [x] **Inheritance test**: `test_card_scope_overrides_project_scope` passes — project-scope `EXP120-CROP-001` + card-scope override returns chain ordered card-then-project.
- [x] `pytest .product/tests/test_library_targets.py .product/tests/test_library_requirements.py .product/tests/test_library_requirements_markdown.py` → **29 passed in 5:13**. junit XML at `target/test-artifacts/WP-I3-007/junit.xml`.
- [x] `pwsh scripts/audit-repo.ps1` clean on HEAD: 8 OK, 1 SKIP (project-rules-fresh, by-design), 0 violations. Output captured at `target/test-artifacts/WP-I3-007/audit-clean.txt`.
- [x] **Manual Impact**: `Yes — extends requirements-and-targets.md to document the v0.1 markdown-native canonical form (the spec's fenced-YAML example remains as historical reference). Adds 8 commands with example invocations. Manual update in this WP.`

## Test Coverage Plan

### Functional Flow Tests
- [ ] EXP120 canonical markdown imports cleanly into 6 groups + 120 target cards + 8 requirements; render returns byte-equal markdown.
- [ ] `target_summary(scope='project', scope_id=...)` returns `target_promoted=960`, `promoted=0`, `gap=960`, `in_flight=0`, `forecast_ok=False`, `fully_satisfied=False` for an unseeded project.
- [ ] After seeding 12 promoted outputs across 2 cards in 1 group, `target_summary(scope='group', ...)` returns `promoted=12`, `gap=148` (160-12), and the group's `complete_cards`/`stable_cards` reflect per-card `target_promoted`/`stability_target` thresholds.
- [ ] `project_set_requirement(scope_type='card', scope_id=card_x, rule_id='EXP120-CROP-001', ...)` overrides the project-scope rule of the same `rule_id`. `project_dump_requirements(scope_type='card', scope_id=card_x)` returns the override with `inherited_from` populated.
- [ ] `target_recount(scope_id=...)` is idempotent: running twice produces identical counters.

### Code Correctness Tests
- [ ] 8-kind enum rejection: `project_add_requirement(kind='nonexistent')` raises `OpenReposeRequirementsError` with citation to spec.
- [ ] Severity enum rejection: `project_add_requirement(severity='maybe')` raises with citation to `openrepose_rules_v0_1.md` severity tiers.
- [ ] Markdown parse rejects malformed input (missing required headings) with line-number diagnostic.
- [ ] `target_promoted` and `expected_card_count` CHECK constraints enforced at DB layer; command layer catches `psycopg.errors.CheckViolation` and re-emits as `OpenReposeRequirementsError`.
- [ ] Static type-check (mypy) clean on all new modules.

### Red-Team / Abuse Tests
- [ ] LLM tries to author a project-scope rule with `rule_id='RUL-999'` (forbidden — global family). Command rejects with `OpenReposeRequirementsError` (rule_id collision with global family).
- [ ] LLM submits markdown with a `kind: custom` requirement. v0.1 rejects with citation explaining `custom` kind is v0.2.
- [ ] LLM submits a target tree with `expected_card_count=0`. CHECK constraint refuses; command reports the CHECK violation as a citation.
- [ ] LLM attempts `project_set_requirement(scope_type='global', ...)`. Refused — global rules are repo-wide governance, only operator may add.

### Performance / Reliability Tests
- [ ] `target_summary(scope='project')` for a 960-card project returns within 100ms (one query against the view + one rollup SUM).
- [ ] Round-trip on the EXP120 canonical markdown completes within 50ms (parse + persist + render).

## Rollback Plan

- Files to revert: the 4 new `library/requirements/*.py` files, `library/targets.py`, the 3 new test files. `state.py` and `commands.py` revert via `git checkout` after staging the kickoff-commit baseline.
- Files to keep: WP file + taskboard row (records intent).
- Recovery command: `git checkout HEAD~1 -- .product/src/openrepose/state.py .product/src/openrepose/commands.py` then remove the new files via `/safe-delete`.

## Decisions Log

- 2026-05-03: Use hand-rolled markdown canonical form instead of fenced YAML. Reason: PyYAML is not a project dep; adding it for a feature that only needs to round-trip a tightly-controlled internal form is an unjustified surface increase. Alternatives considered: (a) bundle PyYAML — rejected (dep cost), (b) ship JSON instead of markdown — rejected (operator authoring is in markdown per spec), (c) tomli — rejected (TOML loses array-of-table ordering nuances we need).
- 2026-05-03: Canonical markdown does not round-trip operator natural-prose. Reason: spec hints at supporting both forms but locks the byte-stable round-trip on the canonical form only. Operator-prose import is a v0.2 stretch.
- 2026-05-03: `set_targets_state` is a single-call replace, not incremental updates. Reason: matches `set_intake_state` pattern; the entire targets block is recomputed on every command tick (cheap — one view query + rollup). Alternative: incremental diff updates — rejected (more code, race-prone).
- 2026-05-03: Project-scoped rule_ids stay in DB; not added to `library/citations.py`. Reason: WP-I3-009 audit check #6 already handles project-scoped families as info-only. The citations.py registry is for global rules; mixing project rules in would defeat the global-vs-project split that openrepose_rules_v0_1.md locks.

## Fallback Register

- **Path**: `library/requirements/markdown_io.py` parser
- **Required Label In Code/UI**: `# v0.1: 'custom' kind not supported in markdown round-trip; use project_add_requirement directly.`
- **Successor / Debt Owner**: v0.2 markdown parser extension WP
- **Exit Condition To Remove**: a project ships at least one `kind=custom` rule that needs round-trip authoring.

- **Path**: `library/requirements/markdown_io.py` natural-prose parser
- **Required Label In Code/UI**: `# v0.1: operator natural-prose markdown is not parsed; only canonical form round-trips.`
- **Successor / Debt Owner**: v0.2 prose-import WP (post-WP-I3-008 GUI)
- **Exit Condition To Remove**: operator workflow demands one-way prose-to-canonical conversion in the GUI.

## Change Ledger

- **What Became Real**: 8 dispatcher commands shipped (project_set_target_tree, project_add_requirement, project_set_requirement, project_dump_requirements, project_render_markdown, project_import_markdown, target_summary, target_recount). New `library/requirements/` subpackage (errors.py + rules.py + markdown_io.py) and new `library/targets.py`. New `OpenReposeRequirementsError` carrying citation; threaded into the dispatcher's typed-catch alongside intake/amood error classes. New `state.library.targets` block + `set_targets_state` mutator on `AppState`; refreshed by `_refresh_targets_state` after every target-mutating command. Markdown round-trip lands as a hand-rolled markdown-native canonical form (no PyYAML dep added). Round-trip verified on the EXP120 worked example: byte-stable across `render(parse(md)) == md`, `render(parse(render(parse(md)))) == render(parse(md))`, AND through the dispatcher (project_import_markdown → DB → project_render_markdown). Counter rollup verified at card / group / project scope against `library_target_card_counts` view + ad-hoc SUM. Inheritance verified via `get_rule_with_inheritance` SQL ordering CASE. Manual extended with a "v0.1 canonical form" subsection so operators see the actual round-trip shape.
- **What Remains Simulated**: (a) `'custom'` kind not parseable from markdown; rejected with citation pointing at WP-I3-007 fallback. (b) Operator natural-prose markdown form is documentation-only — not parsed. (c) `quota_satisfied` flag on `target_summary` is hardcoded `False` — AMood diversity audit (WP-I3-006 surface) is not yet wired into target rollup. The `TargetSummary.to_dict(quota_satisfied=...)` plumbing is in place; only the wire-up is missing.
- **Next Blocking Real Seam**: WP-I3-008 (Triage GUI tab) reads `state.library.targets` and renders the project tree in the GUI. WP-I3-010 (end-to-end EXP120 verification) walks the full path: project_create → project_import_markdown(EXP120) → bridge dropping outputs → counter rollup. Wiring `quota_satisfied` from the AMood `accepted_set_audit` result into `target_summary` will likely happen during WP-I3-010.

## Checkpoint Commit Plan

1. Governance kickoff commit: this WP file + taskboard row. Push must succeed.
2. Test-first commit: `test_library_requirements_markdown.py` with the round-trip test that asserts byte-equality on EXP120. Test should fail at this point (no implementation).
3. Implementation commit(s): `library/requirements/`, `library/targets.py`, state mutator, dispatcher handlers. Tests progressively pass.
4. Verification commit: WP file → REVIEW with Change Ledger + Evidence; taskboard row migrates Active → Pending Review.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_library_requirements*.py .product/tests/test_library_targets.py --junitxml=target/test-artifacts/WP-I3-007/junit.xml`.
- **Audit Runs**: `pwsh scripts/audit-repo.ps1` produces 8 OK + 1 SKIP, 0 violations.
- **Proof Artifact**: `target/test-artifacts/WP-I3-007/`
- **Claim Standard**: never mark `DONE` without round-trip green + audit clean + operator sign-off.

## Headless LLM Operation Compliance

This WP adds 8 LLM-issuable commands to the dispatcher; no GUI surface (the GUI tab arrives in WP-I3-008). Per the Headless LLM Operation Rule:

- [x] An LLM agent can trigger every command through the existing HTTP/inbox channel without touching the GUI (verified via `App.handle_command` in tests).
- [x] An LLM agent can read `state.library.targets` from `outputs/.runtime/state.json` to see the active project's roll-up (verified via `test_set_target_tree_seeds_groups_and_cards`).
- [x] Snapshot target: `N/A — pure command surface; no visual artifact for this WP. WP-I3-008 adds visual snapshot targets that read this WP's state block.`
- [x] No code path calls `raise_()`, `activateWindow()`, `showNormal()`, `setForegroundWindow()`, or any equivalent. (Trivially satisfied — no GUI code in this WP.)
- [x] No modal dialogs in response to LLM-originated commands. (Trivially satisfied.)
- [x] Tests cover the headless path (every test exercises commands through the dispatcher, not a GUI).

## Exit Criteria

- [x] Definition of Done items all checked.
- [x] Taskboard row reflects current status.
- [x] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [x] Linked test suite executed; junit XML at `target/test-artifacts/WP-I3-007/junit.xml`.
- [x] Evidence section populated with concrete paths.
- [x] Operator sign-off recorded in Evidence section.
- [x] **Headless LLM Operation Compliance** section all items checked (snapshot target marked N/A with reason).

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I3-007/junit.xml` (29/29 passed in 5:13 against ephemeral PostgreSQL via pytest-postgresql). Output captured at `target/test-artifacts/WP-I3-007/pytest-output.txt`.
- **Audit Clean Run**: `target/test-artifacts/WP-I3-007/audit-clean.txt` — `pwsh scripts/audit-repo.ps1` exit 0; 8 OK, 1 SKIP (project-rules-fresh, by-design), 0 violations on HEAD post-implementation.
- **Logs**: dispatcher log lines captured per-test in pytest stdout (e.g. `cmd.received: command=project_import_markdown` → `cmd.completed: status=ok`).
- **Screenshots / Exports**: `N/A — non-visual surface in this WP`.
- **Build Artifacts**: `N/A`.
- **Proof Artifact**: `target/test-artifacts/WP-I3-007/` (junit.xml + pytest-output.txt + audit-clean.txt).
- **Operator Sign-off**: 2026-05-04 operator sign-off recorded in chat; requirements editor + target tree accepted as done.

## Progress Log

- `2026-05-03`: WP authored at IN-PROGRESS as Sweep B follow-on (predecessors WP-I3-001/003/004/006 DONE; WP-I3-009 in REVIEW). Kickoff push pending.
- `2026-05-03`: Kickoff commit 36313c7 pushed to origin/main.
- `2026-05-03`: Round-trip test landed first per handoff. EXP120 byte-stable round-trip GREEN on first implementation cut (12/12 markdown tests).
- `2026-05-03`: Implementation completed: library/requirements/ subpackage (errors + rules + markdown_io), library/targets.py, state.set_targets_state mutator, 8 dispatcher handlers wired in commands.py. Two iteration bugs caught by integration tests: (a) library_tasks.intake_dir NOT NULL not seeded in test fixture, (b) project_import_markdown didn't update library_projects.name/status from markdown header. Both fixed; round-trip via dispatcher then byte-stable.
- `2026-05-03`: 29/29 final pytest GREEN (5:13 against ephemeral PG). Audit clean (8 OK, 1 SKIP, 0 violations). Manual extended with v0.1 canonical-form subsection. WP transitioned to REVIEW.
- `2026-05-04`: Operator sign-off recorded; status REVIEW -> DONE; archived under `.gov/workflow/archive/`.
