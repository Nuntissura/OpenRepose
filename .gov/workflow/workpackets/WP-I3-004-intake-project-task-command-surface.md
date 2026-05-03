# WP-I3-004 - Intake + Project + Task Command Surface

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: READY
- **Iteration**: I3
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: L
- **Linked Spec**:
  - `.gov/spec/openrepose_intake_v0_1.md` — Triage Commands / Two-Stage Acceptance / Self-Documenting Surface / Status Enum / Default-Staging ComfyUI Bridge (handshake half)
  - `.gov/spec/openrepose_rules_v0_1.md` — Error Citation Contract / Severity Tiers
  - `.gov/spec/openrepose_requirements_v0_1.md` — Counters (counter math reused by `task_summary`)
  - `.gov/spec/openrepose_amood_v0_1.md` — n/a in this WP (AMood-specific commands land in WP-I3-006)
- **Linked Test Suite**: `.product/tests/test_intake_commands.py` (new); existing `test_command_handlers.py` for dispatcher envelope
- **Linked Check Script**: `scripts/audit-repo.ps1`

## Intent

Wire the 15 dispatcher commands from `openrepose_intake_v0_1.md` against the schema landed by WP-I3-003. After this WP, an LLM agent can drive a full intake-and-triage flow through the existing HTTP/inbox channels — create a project, create a task, register outputs, list/inspect the queue, soft-accept, reject, reroute — and an operator (token-gated) can finalize, bulk-promote, and wholesale-reject. `state.library.intake` and `state.library.guidance` reflect the active task on every command. Every error response follows the `ERR cmd=<command>: <action_result> by <rule_id> (<rule_name>): <short>. See manual: <manual_link>. Fix: <suggested>.` shape per `openrepose_rules_v0_1.md`.

## Linked Workpackets

- **Predecessor(s)**: WP-I3-003 (REVIEW) — the schema this WP consumes. Building on REVIEW per handoff guidance ("you can implement I3 against the I2 codebase as it stands at REVIEW").
- **Successor(s)**: WP-I3-005 (default-staging ComfyUI bridge — calls `intake_register_output`), WP-I3-006 (AMood data-model commands), WP-I3-007 (requirements editor + target tree commands), WP-I3-008 (Triage GUI tab — reads from `state.library.intake` and renders queue), WP-I3-010 (end-to-end EXP120 verification).
- **Blocks**: WP-I3-005, WP-I3-006, WP-I3-008.
- **Blocked-By**: none (WP-I3-003 schema present at REVIEW; build on it).
- **Related**: WP-I2-004 (library LLM commands — same dispatcher pattern), WP-I3-002 (`adult_production_boundary` envelope on every command response).

## Linked Requirements / Spec Sections

- `openrepose_intake_v0_1.md` / `## Triage Commands` (the 15 commands)
- `openrepose_intake_v0_1.md` / `## Two-Stage Acceptance` (operator-token gate on `intake_finalize` / `promote_to_library`)
- `openrepose_intake_v0_1.md` / `## Self-Documenting Surface` (`state.library.intake` + `state.library.guidance` blocks)
- `openrepose_intake_v0_1.md` / `## Triage Workflow / ### Layer 2: Auto-prefilter` (auto-route hook on `intake_register_output`)
- `openrepose_rules_v0_1.md` / `## Error Citation Contract` (uniform error shape)
- `openrepose_rules_v0_1.md` / `## Severity Tiers` (`auto-route` semantics)

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Local codebase | `.product/src/openrepose/commands.py` (1739 lines) + `.product/src/openrepose/library/` package | Existing dispatcher pattern: handler `_h_<cmd>(d, cmd_dict) -> dict`; registered in `_HANDLERS` mapping at the bottom of `commands.py`; `CommandResult.to_dict()` already embeds `adult_production_boundary` (WP-I3-002). I2 library handlers (`_h_register_library_entry` etc.) acquire DB connections via `_ensure_pool(d)` then call `library/<module>.py` data-layer functions. New intake handlers follow the same shape. | adopt |
| 2026-05-03 | Local codebase | `.product/src/openrepose/state.py` lines 167-185 | `state.library` is a single dict on `AppState`; existing keys (`connected`, `schema_version`, `operator_slug`, `library_root`, `last_search_*`, ...). Add `intake` and `guidance` sub-keys without restructuring; preserves I2 callers. State-write helper signature unchanged. | adopt |
| 2026-05-03 | Spec + topology | `.gov/topology.yaml` `rule_registry:` block | Global rules (RUL-/AMOOD-/INTAKE-/TARGET-/REQ-/SAFE-) live in topology.yaml. Project-scoped rules in `library_rules` table (created by WP-I3-003). Error citation shape needs both — load global from topology.yaml at App init; query DB at command time for project-scoped. v0.1 keeps it simple: cite by rule_id + look up the static `name`/`short`/`manual` fields from a Python dict mirroring the topology.yaml registry. Mirroring is intentional: WP-I3-009 audit will verify they stay in sync. | adopt |
| 2026-05-03 | PostgreSQL docs | https://www.postgresql.org/docs/16/sql-update.html | UPDATE ... RETURNING for status transitions returns the post-update row in one round-trip; matches `intake_soft_accept` / `intake_reject` semantics. Atomic via the implicit transaction on `with conn`. | adopt |
| 2026-05-03 | Spec | `openrepose_intake_v0_1.md` / "Layer 2: Auto-prefilter" | Auto-route runs deterministic checks (severity=auto-route) on every output insert. Rules come from `library_rules` table which WP-I3-007 populates; v0.1 ships the *scaffolding* — query library_rules for project-scope severity=auto-route, evaluate `machine_check_fn` SQL expression with width/height substituted, route to `diagnostic` status with `auto_route_to` bucket recorded in `library_diagnostics`. Empty rule set = pass-through (output stays `pending`). | adopt |
| 2026-05-03 | Local codebase | `.product/src/openrepose/settings.py` | Operator token: `Settings` already carries `operator_slug`; v0.1 token gate checks command payload for `operator_token` field that matches a value derived from settings (e.g. SHA-256 of `operator_slug + library_root` — non-LLM-readable from the command surface side, set once at GUI session start). Future WP can swap for a session-scoped opaque token. | adopt-with-fallback |

## Reality Boundary

- **Real Seam**: 15 new dispatcher handlers in `commands.py`; new `library/intake/` subpackage (`projects.py`, `tasks.py`, `outputs.py`, `auto_route.py`, `tokens.py`); `state.library.intake` + `state.library.guidance` dict blocks on `AppState`; rule-citation helper module `library/citations.py` mirroring the topology.yaml global registry; outputs-tree initialization (`outputs/intake/<task_slug>/` with `raw/`, `diagnostic/`, `contact_sheets/`, `rejected/` subdirs; recoverable from DB).
- **User-Visible Win**: an LLM agent can, against a live PG, drive: `project_create exposure-120` → `task_create T-001 expected_count=80` → `intake_register_output run_id=X file_path=...` (writes to `outputs/intake/<task_slug>/raw/`) → `intake_list status=pending` → `intake_inspect output_id=Y` → `intake_soft_accept output_id=Y` → (operator with token) `intake_finalize output_id=Y` → output flips to `promoted`, file moves to `outputs/library/<project>/<batch>/accepted/`. Every error response cites a rule_id with manual link.
- **Proof Target**: `pytest .product/tests/test_intake_commands.py` passes against ephemeral PG. Tests cover: project + task creation; output registration including auto-route routing; soft-accept LLM-issuable; finalize blocked for non-operator (cites INTAKE-001); finalize succeeds with operator token; reject path; intake_list filter + pagination; task_summary counters match `library_target_card_counts` view; wholesale-reject transactional rollback (no orphan files; all output rows transition in one commit); error-citation shape verified against the spec format string.
- **Allowed Temporary Fallbacks**:
  - Operator token derivation is SHA-256 of (`operator_slug` + `library_root`) for v0.1; flagged with FALLBACK comment, replaced by session-scoped opaque token in a successor WP. The dispatcher-level INTAKE-001 gate is layered ON TOP of the DB-level CHECK constraint from WP-I3-003, so even a leaked token cannot bypass two-stage acceptance — the DB constraint is the kill switch.
  - Auto-route rule loading: v0.1 reads `library_rules` rows live on each registration. No in-memory cache yet; WP-I3-008 may add caching when the GUI tab triages large queues.
- **Promotion Guard**: do not declare WP-I3-004 stable until: (a) all 15 commands return responses with `adult_production_boundary` envelope (verified by `test_command_handlers.py` regression sweep), (b) operator-only commands reject LLM-issued calls with the exact INTAKE-001 citation string, (c) wholesale-reject correctly rolls back ≥50 outputs in one transaction without orphan files, (d) auto-route reversal (`intake_reroute`) restores a `diagnostic` row to `pending` and the `library_diagnostics` row remains as audit trail.

## In Scope

- New library subpackage `library/intake/`:
  - `projects.py` — `create_project`, `list_projects`, `get_project`.
  - `tasks.py` — `create_task` (also creates `outputs/intake/<task_slug>/` directory tree), `list_tasks`, `get_task`, `task_summary` (counters from view), `wholesale_reject_task` (one transaction; deletes intake_dir via `safe-delete` operator helper).
  - `outputs.py` — `register_output` (auto-route hook), `list_outputs` (filter by status/limit/offset), `get_output`, `soft_accept_output`, `reject_output`, `finalize_output` (operator-only; INTAKE-001 dispatcher gate on top of DB CHECK), `bulk_promote_task` (operator-only), `reroute_output`.
  - `auto_route.py` — load project-scope severity=auto-route rules from `library_rules`; evaluate `machine_check_fn` against output dimensions; on fail, set status='diagnostic', write `library_diagnostics` row, move file to bucket directory.
  - `tokens.py` — `expected_operator_token(settings)` → SHA-256 of operator_slug + library_root; `verify_operator_token(payload, settings)` returns bool; FALLBACK-marked.

- New `library/citations.py`:
  - Static dict mirroring `topology.yaml rule_registry.rules` (rule_id → name/short/severity/manual).
  - `format_citation(rule_id, command, action_result, fix_action) -> str` produces the exact error citation shape.
  - `RuleNotInRegistryError` for unknown rule_ids (enforces every error cites a real rule).

- Extend `commands.py`:
  - 15 new `_h_*` handlers (one per command) wired into `_HANDLERS`.
  - New error class `OpenReposeIntakeError(OpenReposeLibraryError)` with `rule_id` + pre-formatted citation; dispatcher's typed-error catch propagates `payload["citation"]` and `payload["rule_id"]`.

- Extend `state.py`:
  - `state.library["intake"]` block (active_task_id/slug, received_count, pending/triaging/soft_accepted/promoted/rejected/diagnostic counts, current_card_id, queue_depth).
  - `state.library["guidance"]` block (current_focus, next_valid_actions[], active_rules[], manual_index, topic_pointers{}). Capped ~20 lines per spec.
  - Mutators called by intake handlers; reads on every `dump_state` and on every command's begin/end.

- New tests `.product/tests/test_intake_commands.py`:
  - Ephemeral PG fixture (same pattern as `test_db_migrator_i3.py`).
  - One test per command happy path.
  - Operator-token gate tests (LLM call without token rejected with INTAKE-001 citation; operator call with token succeeds).
  - Auto-route test: insert library_rules row with severity=auto-route + `machine_check_fn = 'width = 1080 AND height = 1440'`; register output 1024×1536; expect status=diagnostic + diagnostics row written.
  - Wholesale-reject test: 50 synthetic outputs in mixed statuses; `task_reject_wholesale`; assert all transitioned to rejected, intake_dir gone, no orphan files.
  - State surface test: after intake_register_output × N, `state.library.intake.received_count == N`; `state.library.guidance.next_valid_actions` contains `intake_inspect`.
  - Error-citation regression: every operator-only command rejected for LLM caller carries the exact citation shape.

## Out Of Scope

- ComfyUI bridge default-staging change (WP-I3-005 — bridge will *call* `intake_register_output`; this WP just exposes the entrypoint).
- AMood `init_batch_package` / card-creation commands (WP-I3-006).
- Triage GUI tab (WP-I3-008).
- Probabilistic auto-prefilter (advisory hints only per spec; no ML).
- `library_demote` command (out of scope per intake spec).
- Streaming intake (poll-based via `intake_list` only in v0.1).
- TSV exports of intake state (AMood-specific TSVs land in WP-I3-006).

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I3-004-intake-project-task-command-surface.md`
- `.gov/workflow/TASKBOARD.md`

### Product (`.product/`)

- `.product/src/openrepose/commands.py` (extend; ~15 new handlers + `OpenReposeIntakeError` class)
- `.product/src/openrepose/state.py` (extend `library` dict with `intake` + `guidance` keys)
- `.product/src/openrepose/library/__init__.py` (re-export new symbols)
- `.product/src/openrepose/library/citations.py` (new)
- `.product/src/openrepose/library/intake/__init__.py` (new)
- `.product/src/openrepose/library/intake/projects.py` (new)
- `.product/src/openrepose/library/intake/tasks.py` (new)
- `.product/src/openrepose/library/intake/outputs.py` (new)
- `.product/src/openrepose/library/intake/auto_route.py` (new)
- `.product/src/openrepose/library/intake/tokens.py` (new)
- `.product/tests/test_intake_commands.py` (new)
- `.product/tests/test_command_handlers.py` (extend with adult_production_boundary regression on the 15 new commands)

### Build / Output (gitignored)

- `target/test-artifacts/WP-I3-004/pytest_results.xml`
- `outputs/intake/<task_slug>/{raw,diagnostic,contact_sheets,rejected}/` (created at runtime by `task_create`)

## Risks And Dependencies

- **Risk**: 15 commands in one WP risks an L→XL slip. **Mitigation**: each command has the same shape (validate payload → DB call → state write → return dict); the data-layer functions in `library/intake/*` carry the actual logic so handlers stay thin. Cap at L; if it slips during implementation, split out wholesale-reject + auto-route into a follow-up WP and document in Change Ledger.
- **Risk**: operator-token derivation could leak if the payload is logged. **Mitigation**: token field is redacted in log lines (existing `Logger` redact pattern from WP-I2-001); FALLBACK comment flags the v0.1 weakness.
- **Risk**: filesystem operations (file moves on accept/reject, directory creation on task_create, intake_dir delete on wholesale-reject) can leave the DB row and the file out of sync if the process crashes mid-call. **Mitigation**: DB write happens first (in transaction); file move happens after commit; if file move fails, DB row points to a missing file but the row is recoverable (`library_outputs.file_path` records the relative path; broken-link detection lands in WP-I3-008). Wholesale-reject deletes intake_dir via `scripts/safe-delete.ps1` only — never `Remove-Item` directly per RUL-006.
- **Risk**: state.library blocks bloat — spec caps `guidance` at ~20 lines but no enforcement. **Mitigation**: cap `active_rules` to last 20 cited rule_ids, `recent_operator_corrections` to last 10. Test asserts cap.
- **Dependency**: WP-I3-003 schema (REVIEW). **Owner**: assistant. **Status**: REVIEW — building on it per handoff stance.
- **Dependency**: psycopg 3, pg_trgm (already in 001). **Status**: satisfied.

## Definition Of Done

- [ ] 15 dispatcher handlers added: `project_create`, `project_list`, `task_create`, `task_list`, `task_summary`, `task_inspect`, `intake_register_output`, `intake_list`, `intake_inspect`, `intake_soft_accept`, `intake_reject`, `intake_finalize`, `intake_reroute`, `promote_to_library`, `task_reject_wholesale`.
- [ ] All 15 commands return responses carrying the `adult_production_boundary` envelope.
- [ ] Operator-only commands (`intake_finalize`, `promote_to_library`, `task_reject_wholesale`) reject LLM callers with the exact INTAKE-001 error citation shape.
- [ ] `state.library["intake"]` written on every command begin/end; `state.library["guidance"]` reflects current focus + next valid actions.
- [ ] `intake_register_output` runs auto-route deterministic checks against `library_rules` (severity=auto-route, project scope); writes `library_diagnostics` row on fail; moves file to `outputs/intake/<task_slug>/diagnostic/<auto_route_to>/`.
- [ ] `task_reject_wholesale` rolls back ≥50 outputs in one DB transaction; deletes `intake_dir` via `scripts/safe-delete.ps1`; no orphan files remain.
- [ ] `pytest .product/tests/test_intake_commands.py` passes; junit XML at `target/test-artifacts/WP-I3-004/pytest_results.xml`.
- [ ] Full suite `pytest .product/tests/` remains 528+ passing (regression sweep).
- [ ] `powershell -ExecutionPolicy Bypass -File scripts/audit-repo.ps1` exits 0.
- [ ] **Manual Impact**: Yes — extends `intake-and-triage.md` with the 15 dispatcher commands table + worked LLM example + operator-token note + auto-route hint.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Happy path: project_create → task_create → intake_register_output × 5 → intake_list → intake_soft_accept × 3 → intake_finalize × 3 (operator token).
- [ ] Each of the 15 commands has at least one happy-path test.

### Code Correctness Tests
- [ ] Auto-route: width/height predicate fails → status=diagnostic + library_diagnostics row + file in diagnostic bucket.
- [ ] Auto-route: passes → status=pending; no library_diagnostics row.
- [ ] `task_summary` counters match `library_target_card_counts` view aggregates for synthetic outputs.
- [ ] State surface: every command updates `state.library.intake.received_count` / `pending_count` / etc. correctly.
- [ ] Citation registry mirrors topology.yaml: every rule_id in `format_citation` resolves to a real entry.

### Red-Team / Abuse Tests
- [ ] LLM call to `intake_finalize` without operator_token → INTAKE-001 citation; output unchanged.
- [ ] LLM call to `intake_finalize` with bogus operator_token → INTAKE-001 citation.
- [ ] LLM call to `task_reject_wholesale` → INTAKE-001 citation.
- [ ] Direct DB insert with status='promoted' AND finalized_by IS NULL → DB CHECK rejects (already verified by WP-I3-003 test, repeated here as a paranoia regression).
- [ ] `intake_register_output` payload with `task_id` for a `rejected_wholesale`/`aborted` task → command rejected with structured error.

### Performance / Reliability Tests
- [ ] Wholesale-reject 100 outputs: single transaction; observed via `pg_stat_activity` outside the test (manual verification noted in evidence).
- [ ] Concurrent `intake_register_output` from 2 connections (advisory-lock-free path) lands both rows without UNIQUE collisions.

## Rollback Plan

- Files to revert: the new `library/intake/` package + new `library/citations.py` + commands.py extensions + state.py extensions + new test file.
- Files to keep: WP file + taskboard row.
- Recovery command: `git revert <impl-commit-hash>`. Schema (WP-I3-003) remains; just no command handlers consume it. Existing I2 commands unaffected.

## Decisions Log

- 2026-05-03: **One package `library/intake/` instead of one big `intake.py`**. Reason: 15 commands + auto-route logic + token gate is too much for one module; package naturally splits along DB-table boundaries (projects/tasks/outputs) plus cross-cutting concerns (auto_route, tokens). Alternative: flat module (rejected — 1500+ lines hurts review).
- 2026-05-03: **Citation registry mirrored from topology.yaml as a Python dict** in `library/citations.py`. Reason: importing topology.yaml at runtime adds a YAML parser dependency; mirroring statically with a docstring linking back to the canonical block keeps imports clean. WP-I3-009 audit script will verify they stay in sync. Alternative: load from topology.yaml at App init (rejected — adds yaml dependency that's not currently in pyproject.toml).
- 2026-05-03: **Operator-token v0.1 = SHA-256(operator_slug + library_root)**, FALLBACK-marked. Reason: gives a deterministic per-install token without yet building a session-scoped token system. The DB-level CHECK constraint is the actual kill switch — token gate is defense-in-depth. Alternative: opaque session token (rejected for v0.1 — out of scope; can be added in a successor WP without breaking commands).
- 2026-05-03: **Auto-route v0.1 reads library_rules live, no cache**. Reason: empty rule set is the v0.1 default; WP-I3-007 populates rules via the requirements editor. Caching is premature. Alternative: in-memory cache from App init (rejected — invalidation complexity for v0.1).

## Fallback Register

- **Path**: `.product/src/openrepose/library/intake/tokens.py`
- **Required Label In Code/UI**: `# FALLBACK v0.1: operator-token derivation is SHA-256(operator_slug + library_root). Replaced by session-scoped opaque token in a successor WP. The DB-level CHECK constraint is the actual kill switch; this gate is defense-in-depth.`
- **Successor / Debt Owner**: future I3+ token-hardening WP (not yet drafted)
- **Exit Condition To Remove**: a successor WP introduces `library_sessions` (or equivalent) and replaces `expected_operator_token` with a session-bound opaque token.

## Change Ledger

_Captured at REVIEW. Truthful summary._

- **What Became Real**: _filled at REVIEW._
- **What Remains Simulated**: _filled at REVIEW._
- **Next Blocking Real Seam**: _filled at REVIEW._

## Checkpoint Commit Plan

1. Governance kickoff commit (this WP file + taskboard row).
2. Library subpackage commit (`library/intake/` + `library/citations.py` + state.py extensions).
3. Dispatcher commit (commands.py 15 handlers + register).
4. Test + manual commit + REVIEW transition.

Squash to one if the diff stays manageable; four commits if review prefers granular history.

## Proof Of Implementation

- **Command Runs**: `.\.venv\Scripts\python.exe -m pytest .product/tests/test_intake_commands.py --junitxml=target/test-artifacts/WP-I3-004/pytest_results.xml -q` returns 0; full suite remains green.
- **Proof Artifact**: `target/test-artifacts/WP-I3-004/`
- **Claim Standard**: never mark `DONE` without linked command evidence and artifact paths.

## Headless LLM Operation Compliance

- [ ] An LLM agent can trigger every command through the existing HTTP/inbox channels without touching the GUI.
- [ ] An LLM agent can read intake state from `outputs/.runtime/state.json` (`state.library.intake` + `state.library.guidance`).
- [ ] N/A for snapshot — the Triage GUI tab + its snapshot targets land in WP-I3-008. This WP exposes only state + commands.
- [ ] No code path in the new handlers calls `raise_()`, `activateWindow()`, `showNormal()`, `setForegroundWindow()`, or any equivalent.
- [ ] No modal dialogs in any new code path.
- [ ] Tests cover the headless path (every test uses the dispatcher; no GUI imports).

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [ ] Linked test suite has executed results saved under `target/test-artifacts/WP-I3-004/`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence section.
- [ ] **Headless LLM Operation Compliance** section either marked `N/A` with reason, or all items checked.

## Evidence

- **Test Suite Execution**: _filled at REVIEW._
- **Logs**: _filled at REVIEW._
- **Screenshots / Exports**: N/A — non-GUI surface.
- **Build Artifacts**: N/A.
- **Proof Artifact**: `target/test-artifacts/WP-I3-004/`
- **Operator Sign-off**: pending.

## Progress Log

- 2026-05-03: WP drafted at READY per operator authorization ("ok go" 2026-05-03). Predecessor WP-I3-003 at REVIEW; building on it per handoff guidance. Kickoff commit + push will land this WP file + taskboard row before any `.product/` file is opened.
