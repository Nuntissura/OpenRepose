# WP-I3-010 — End-to-End EXP120 Verification (closes I3 v0.1)

## Header

- **Owner**: `assistant`
- **Date Opened**: `2026-05-04`
- **Last Updated**: `2026-05-04`
- **Status**: `IN-PROGRESS`
- **Iteration**: `I3`
- **Workflow Version**: `1.1`
- **Packet Class**: `VERIFICATION`
- **Effort Estimate**: `M`
- **Linked Spec**: `.gov/spec/openrepose_intake_v0_1.md`, `.gov/spec/openrepose_requirements_v0_1.md`, `.gov/spec/openrepose_amood_v0_1.md`, `.gov/spec/openrepose_rules_v0_1.md`
- **Linked Test Suite**: `.product/tests/test_e2e_exp120.py`
- **Linked Check Script**: `scripts/audit-repo.ps1`

## Intent

A single integration test walks the full I3 v0.1 surface end-to-end against an ephemeral PostgreSQL: project_create → project_import_markdown(EXP120) → task_create → init_batch_package → library_create_card → intake_begin_run → 50+ intake_register_output → auto-prefilter routes wrong-resolution outputs → intake_soft_accept → intake_finalize (operator token) → target_summary verifies counters at every scope → accepted_set_audit produces realized-coverage → wholesale-reject of a separate task verifies transactional rollback. After this WP runs green, the I3 v0.1 contract is verified across every surface.

## Linked Workpackets

- **Predecessor(s)**: every prior I3 WP — WP-I3-001 (spec lock), WP-I3-002 (stance primitives), WP-I3-003 (PG schema), WP-I3-004 (intake commands), WP-I3-005 (default-staging bridge), WP-I3-006 (AMood data-model), WP-I3-007 (requirements editor + targets), WP-I3-008 (Triage GUI tab + snapshot targets), WP-I3-009 (audit script extension)
- **Successor(s)**: I3 v0.1 closes after this WP signs off DONE
- **Blocks**: `none`
- **Blocked-By**: `none`
- **Related**: `none`

## Linked Requirements / Spec Sections

- `openrepose_intake_v0_1.md` § "Two-Stage Acceptance" (`INTAKE-001`); § "Auto-Prefilter" (`REQ-002`); § "Per-Task Isolation" (`INTAKE-003`)
- `openrepose_requirements_v0_1.md` § "EXP120 Worked Example"; § "Counters and Satisfaction Semantics" (`TARGET-001`/`TARGET-002`/`TARGET-003`)
- `openrepose_amood_v0_1.md` § "Accepted-Set Diversity Audit"
- `openrepose_rules_v0_1.md` § "Severity Tiers" (auto-route routes; doesn't count toward target)

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-04 | `commands.py _h_intake_register_output` (WP-I3-004) | n/a | Bridge mode (`image_b64` + `filename`) writes raw bytes under `outputs/intake/<task_dir>/raw/`, computes content_hash, runs auto-route. The test uses the disk-already-on-disk variant (`file_path` + `content_hash`) to avoid encoding 50 base64 blobs. | adopt |
| 2026-05-04 | `library/intake/auto_route.py` | n/a | `run_auto_route` evaluates `machine_check_fn` server-side via parameterized SELECT. EXP120-RES-001 's `(width = 1080 AND height = 1440)` will route any non-1080x1440 output to `intermediate_evidence`. | adopt |
| 2026-05-04 | `library/intake/runs.py resolve_card_by_slug` | n/a | Card-slug resolution joins `library_entries` (title=slug) → `library_batches.task_id`. The test creates cards via `library_create_card` (WP-I3-006) which inserts `library_entries.title=slug` under the active batch. | adopt |
| 2026-05-04 | `commands.py _require_operator_token` | n/a | `intake_finalize` and `task_reject_wholesale` need a valid operator_token. `expected_operator_token(settings)` computes the token from `operator_slug` + `library_db_url`; the test reuses the helper as `test_intake_commands.py` does. | adopt |
| 2026-05-04 | `INTAKE-003` per-task isolation | n/a | `task_reject_wholesale` triggers a directory delete + DB row delete in one transaction. The test seeds two tasks; rejects one; asserts the other's library_outputs / library_runs survive. | adopt |

## Reality Boundary

Sacred. Captured before work starts.

- **Real Seam**: a single new pytest file `.product/tests/test_e2e_exp120.py` that orchestrates the full I3 surface against an ephemeral PostgreSQL via `pytest-postgresql`. No new product code; the test exercises existing dispatchers + DB schema.
- **User-Visible Win**: I3 v0.1 ships verified end-to-end. After this test passes, an operator and an LLM agent each have a checked recipe: project markdown → task → bridge intake → auto-route → triage → finalize → counters → accepted-set audit → safe wholesale reject. Future regressions in any I3 surface fail this test.
- **Proof Target**: `pytest .product/tests/test_e2e_exp120.py` returns 0 failures against ephemeral PG. Audit script clean. The test asserts (not exhaustive list):
  - 50 outputs registered → 30 pass auto-route (status=pending), 20 routed to diagnostic with `auto_route.rule_id == 'EXP120-RES-001'`.
  - Auto-routed outputs do NOT count toward `target_promoted` (verified via `target_summary`).
  - 4 of 30 pending outputs flow soft_accept → finalize → status=promoted.
  - Project-scope `target_summary.promoted == 4`; group-scope same; card-scope same.
  - `accepted_set_audit` returns axis coverage data for the batch.
  - Second task's wholesale reject removes ALL its rows (runs, outputs, diagnostics, intake folder); first task's rows untouched.
- **Allowed Temporary Fallbacks**: (a) test seeds outputs via the disk-already-on-disk path (file_path + content_hash) instead of bridge bytes — bridge bytes path is exercised by WP-I3-005's tests separately. (b) The dummy file_path values point under outputs_root but the files don't actually exist — `intake_register_output` doesn't read them, only auto-route uses width/height. (c) `accepted_set_audit` may report zero priority axes if the seeded card metadata lacks `kink_cue` / `pose_family`; that's fine — the test asserts the audit returns a result, not specific coverage values.
- **Promotion Guard**: do not transition WP to REVIEW until: the integration test passes against fresh ephemeral PG; no flakiness across 3 consecutive runs; audit clean.

## In Scope

- One pytest file: `.product/tests/test_e2e_exp120.py`.
- Helper that constructs an `App` against the ephemeral PG (mirroring `test_intake_commands.py` fixture).
- Helper that builds the operator_token via `expected_operator_token` for finalize / reject commands.
- A minimal EXP120 markdown string (1 group, 4 cards, 1 hard_output rule) — small enough to keep the test fast, big enough to exercise auto-route + counters.
- Assertions across: auto-route correctness, two-stage acceptance, counter rollup, accepted_set_audit return shape, wholesale-reject isolation.

## Out Of Scope

- New product code; this WP is VERIFICATION-class.
- Schema migrations or new commands.
- Snapshot capture of the triage view as part of the e2e flow (already covered by WP-I3-008 tests).
- ComfyUI bridge wire-format coverage (already covered by WP-I3-005 tests).
- AMood diversity-audit numerical correctness on synthetic data (the audit returns a structured shape; this test asserts shape, not values — values are AMood blueprint design ground).
- Failure-recovery / partial-rollback variants (the spec calls for one transactional reject; richer partial-failure semantics are a v0.2 concern).

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I3-010-e2e-exp120-verification.md` (this file)
- `.gov/workflow/TASKBOARD.md`

### Product (`.product/`)

- `.product/tests/test_e2e_exp120.py` (new; only file in this WP)

### Build / Output (gitignored)

- `target/test-artifacts/WP-I3-010/junit.xml`
- `target/test-artifacts/WP-I3-010/audit-clean.txt`

## Risks And Dependencies

- **Risk**: PG spin-up cost — single test file with multiple test cases against pytest-postgresql still pays the ~3-minute one-time PG startup. **Mitigation**: keep the test file small (3-5 test functions) so the startup amortizes. Already the standard pattern in `test_library_targets.py` etc.
- **Risk**: card_slug → card_id resolution depends on `library_create_card` populating `library_entries.title=slug`. **Mitigation**: the test asserts the link by reading `library_target_cards.card_id` after `library_create_card`; if the link isn't auto-populated by `library_create_card`, the test does the wire-up manually and records that as a v0.2 follow-up in the Change Ledger.
- **Risk**: `task_reject_wholesale` filesystem rm of `outputs/intake/<task_dir>/` when the dir doesn't exist could throw. **Mitigation**: test creates the task via `task_create` which materializes the directory tree (verified by `test_intake_commands.test_task_create_makes_intake_dir_tree`).
- **Dependency**: `pytest-postgresql` ≥ 6.0 already in dev deps.
- **Dependency**: every prior I3 WP DONE (WP-I3-007/008/009 currently in REVIEW; operator green-lit running this WP in parallel — same green-light as WP-I3-008).

## Definition Of Done

- [ ] `.product/tests/test_e2e_exp120.py` exists with one orchestration test (`test_exp120_full_flow`) plus a focused wholesale-reject test (`test_wholesale_reject_isolates_one_task`).
- [ ] `test_exp120_full_flow` exercises every step in the Reality Boundary "Proof Target" list and asserts each.
- [ ] `test_wholesale_reject_isolates_one_task` creates two tasks, registers outputs in both, rejects one, asserts complete row removal for the rejected task and zero collateral on the surviving task.
- [ ] Both tests pass against ephemeral PG (`pytest .product/tests/test_e2e_exp120.py`).
- [ ] `pwsh scripts/audit-repo.ps1` clean (8 OK, 1 SKIP) on HEAD.
- [ ] **Manual Impact**: `No — verification-only WP. The integration test is operator/CI infrastructure; does not affect operator-facing manual content.`

## Test Coverage Plan

### Functional Flow Tests
- [ ] EXP120 markdown round-trip via dispatcher seeds 1 group + 4 cards + 1 auto-route rule.
- [ ] 50 intake_register_output calls (30 at 1080x1440, 20 at 1024x1024) produce correct status mix: 30 pending, 20 diagnostic.
- [ ] Auto-routed outputs carry `auto_route.rule_id == 'EXP120-RES-001'` in the response payload.
- [ ] target_summary at project / group / card scope returns matching values; auto-routed outputs do NOT contribute to `promoted`.
- [ ] After 4 finalize cycles, `target_summary.promoted == 4`; `gap == target_promoted - 4`.
- [ ] `accepted_set_audit(batch_id=...)` returns a result with `axes` array (shape assertion only).

### Code Correctness Tests
- [ ] No new code paths introduced — this WP exercises existing handlers only.
- [ ] Auto-route SQL evaluation works against `(width = 1080 AND height = 1440)` predicate without injection-style escaping issues.

### Red-Team / Abuse Tests
- [ ] `intake_finalize` without operator_token rejected with `INTAKE-001` citation.
- [ ] After `task_reject_wholesale`, attempts to register outputs against the rejected task return `task is terminal` error.

### Performance / Reliability Tests
- [ ] e2e flow completes within 60 seconds wall-clock against ephemeral PG (50 register calls + 4 finalize + 1 audit + 1 reject).

## Rollback Plan

- Files to revert: `.product/tests/test_e2e_exp120.py`. WP file + taskboard row record intent.
- Recovery command: `git checkout HEAD~1 -- .product/tests/test_e2e_exp120.py` (or `/safe-delete` once the file is no longer tracked).

## Decisions Log

- 2026-05-04: Two test functions, not one giant function. Reason: easier to localize a regression. Pytest-postgresql session-scoped PG amortizes startup.
- 2026-05-04: Use `file_path` + `content_hash` payload for `intake_register_output` (skip the base64 path). Reason: 50 base64-encoded calls bloat the test for no incremental coverage; bridge wire format is verified by WP-I3-005's tests.
- 2026-05-04: Don't assert AMood diversity-audit numerical values. Reason: `accepted_set_audit` math is the AMood blueprint's domain; this test verifies the contract (it returns a structured result), not the algorithm.

## Fallback Register

_(none — pure verification)_

## Change Ledger

_(captured at REVIEW time)_

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row.
2. Test commit: `test_e2e_exp120.py`.
3. REVIEW commit: WP file → REVIEW + Change Ledger + Evidence; taskboard transitions.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_e2e_exp120.py --junitxml=target/test-artifacts/WP-I3-010/junit.xml`.
- **Audit Runs**: `pwsh scripts/audit-repo.ps1` produces 8 OK + 1 SKIP, 0 violations.
- **Proof Artifact**: `target/test-artifacts/WP-I3-010/`.

## Headless LLM Operation Compliance

- `N/A — non-visual change. Verification-only WP; no GUI, no command surface, no state mutation outside the existing handlers.`

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [ ] Linked test suite executed; junit XML at `target/test-artifacts/WP-I3-010/`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence section.
- [ ] **Headless LLM Operation Compliance** section marked `N/A — non-visual change`.

## Evidence

_(captured at REVIEW time)_

## Progress Log

- `2026-05-04`: WP authored at IN-PROGRESS as I3-closing WP (predecessors WP-I3-007/008/009 in REVIEW; operator green-lit running this WP in parallel). Kickoff push pending.
