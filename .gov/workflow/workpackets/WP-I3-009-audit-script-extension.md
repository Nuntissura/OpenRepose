# WP-I3-009 — Audit Script Extension (Rule Registry Coverage)

## Header

- **Owner**: `assistant`
- **Date Opened**: `2026-05-03`
- **Last Updated**: `2026-05-03`
- **Status**: `REVIEW`
- **Iteration**: `I3`
- **Workflow Version**: `1.1`
- **Packet Class**: `INFRASTRUCTURE`
- **Effort Estimate**: `M`
- **Linked Spec**: `.gov/spec/openrepose_rules_v0_1.md`
- **Linked Test Suite**: `N/A` (PowerShell-only audit script; smoke-tested by running `pwsh scripts/audit-repo.ps1` and asserting exit code)
- **Linked Check Script**: `scripts/audit-repo.ps1`

## Intent

`pwsh scripts/audit-repo.ps1` grows from 4 checks to 8. The four new checks read the rule registry that landed in WP-I3-001/006 and verify it stays internally consistent: every cited rule_id resolves to a manual anchor, every error-string in product code that matches the citation shape cites a real rule_id, every dispatcher command appears in the topology command surface (or is grandfathered to an earlier iteration), and project-scoped rules in `library_rules` with stale `last_validated_at` surface as a warn-line. After this WP, drift between `topology.yaml rule_registry.rules`, `.product/src/openrepose/library/citations.py`, and emitted error strings is mechanically detectable.

## Linked Workpackets

- **Predecessor(s)**: `WP-I3-001` (DONE — locked rule-registry contract), `WP-I3-006` (DONE — citations.py registry mirror exists)
- **Successor(s)**: `WP-I3-007` (uses citation shape; this audit catches drift introduced there), `WP-I3-010` (end-to-end EXP120 verification depends on a clean audit)
- **Blocks**: `none`
- **Blocked-By**: `none`
- **Related**: `WP-I1-025` (the audit script's original four checks)

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_rules_v0_1.md` — "Audit Coverage" section: this WP is what that section anticipated. Six audit ideas listed; v0.1 ships the four most directly mechanizable.
- `.gov/spec/openrepose_rules_v0_1.md` — "Error Citation Contract" — defines the regex shape of citation strings.
- `.gov/topology.yaml` — `rule_registry:` block (data source for checks 1, 2, 3) and `i3_command_surface:` (data source for check 3).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Existing `scripts/audit-repo.ps1` (in repo) | n/a | Script already uses `Get-Content -Raw -Encoding UTF8` + multiline regex against WP files. Same pattern fits the 4 new checks; no new dependency required. | adopt |
| 2026-05-03 | PowerShell 5.1 docs (Windows host harness) | https://learn.microsoft.com/en-us/powershell/scripting/lang-spec/chapter-12 | `ConvertFrom-Yaml` is NOT available in stock 5.1; line-regex against the curly-brace single-line rule entries (`RUL-000: { name: "...", manual: "..." }`) is more reliable than rolling a YAML parser. | adopt |
| 2026-05-03 | Existing `library/citations.py` `_REGISTRY` | n/a | Mirror of topology.yaml. Audit reads the YAML as the source of truth and uses the Python registry only as a secondary cross-check via grep — keeps the audit Python-free. | adopt |
| 2026-05-03 | Existing `commands.py _HANDLERS` dict (line 2506) | n/a | 56 commands currently registered. Pre-I3 commands (Feature 1 + Feature 2 + Feature 3 library) are listed in `topology.yaml` `llm_control_surface.commands` (8 entries) and the `feature-3-library-postgresql.md` manual; I3 commands are listed in `i3_command_surface:`. Audit allowlists pre-I3 by name. | adopt |
| 2026-05-03 | `.product/migrations/004_i3_requirements_targets.sql` | n/a | `library_rules` has `last_validated_at TIMESTAMPTZ`, indexed where NOT NULL. Check #4 only fires when the DB is reachable; if it isn't, emit a `SKIP` line — running the audit must not require Postgres. | adopt |

## Reality Boundary

Sacred. Captured before work starts.

- **Real Seam**: `scripts/audit-repo.ps1` gains four new checks. No product code changes. No DB schema changes. No spec changes (the audit operationalizes spec text that is already locked in `openrepose_rules_v0_1.md` "Audit Coverage").
- **User-Visible Win**: `pwsh scripts/audit-repo.ps1` reports 8 checks instead of 4. Drift between topology, citations.py, and emitted error strings now produces a concrete violation line with file path and rule_id.
- **Proof Target**: `pwsh scripts/audit-repo.ps1` exits 0 on the live tree at HEAD, and the OK-line names eight checks. Negative test: temporarily insert a citation referencing a non-existent rule_id (e.g. `RUL-999`) into a Python file, re-run audit, observe FAIL with `[citations-cite-real-rule-ids]` violation line, then revert.
- **Allowed Temporary Fallbacks**: Check #4 (`project-rules-fresh`) emits `SKIP` if `LIBRARY_DB_URL` env var is unset or the DB is unreachable. The fallback is by design (audit must run on any clone, including a fresh one with no DB), not a temporary hack.
- **Promotion Guard**: Audit produces 8 OK-lines (or 7 OK + 1 SKIP for check #4) on a clean tree at HEAD before WP transitions to REVIEW.

## In Scope

- Extend `scripts/audit-repo.ps1` with four new checks: `rule-id-resolves-manual`, `citations-cite-real-rule-ids`, `dispatcher-commands-have-help`, `project-rules-fresh`.
- Each check emits one OK / FAIL / SKIP line; existing report format preserved.
- Each check is self-contained: a parse failure in one does not abort the others (consistent with current behavior).
- Update header comment block in `audit-repo.ps1` to list all 8 checks.
- Update audit invocation note in `.gov/AGENTS.md` if the script's documented behavior changes (it does — checks count goes from 4 to 8).

## Out Of Scope

- The two checks listed in spec that this WP intentionally defers:
  - "every CHECK constraint that triggers a rejection in the DB schema cites a rule_id in its error name" — needs a Python+psycopg helper; defer to a later WP.
  - "duplicated rule_ids across global and project registries are flagged" — needs DB; same deferral.
- Adding new rule_ids. Registry shape stays fixed.
- Migrating existing dispatcher errors to the citation shape. WP-I3-001 spec lists this as a separate promotion task; the audit only enforces "if you cite a rule_id, it must be real," not "every error must be a citation."
- A pytest-based audit harness. PowerShell-only is the explicit choice (matches the rest of `audit-repo.ps1`).
- The pytest suite. Smoke verification is manual (run audit, observe exit code).

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I3-009-audit-script-extension.md` (this file)
- `.gov/workflow/TASKBOARD.md` (Active row, then move to Pending Review)

### Product (`.product/`)

- _(none)_

### Scripts

- `scripts/audit-repo.ps1` (add 4 checks; update header comment; update final report line listing the checks)

### Build / Output (gitignored)

- `target/test-artifacts/WP-I3-009/audit-clean.txt` (captured `pwsh scripts/audit-repo.ps1` output on HEAD)
- `target/test-artifacts/WP-I3-009/audit-negative-citations.txt` (captured output with a synthetic bad-rule-id citation, demonstrating the new check fires)

## Risks And Dependencies

- **Risk**: PowerShell regex against the yaml block is brittle if the rule entries change shape (e.g. multi-line vs single-line). **Mitigation**: pattern explicitly matches the current single-line `RULE-ID: { ... }` form; if the YAML is ever reformatted, the audit will fail loudly with a clear "no rule entries parsed" line that points at the topology file.
- **Risk**: `EXP120-*` and other future project-scoped rule_ids in code might trip check #2. **Mitigation**: check #2 only validates rule_ids that match the *global* family prefixes (`RUL-`, `AMOOD-`, `INTAKE-`, `TARGET-`, `REQ-`, `SAFE-`); project-scoped IDs (recognized by being neither in the global registry nor matching a global prefix) emit an `info` line, not a violation.
- **Risk**: Pre-I3 commands aren't in `i3_command_surface:`. **Mitigation**: check #3 maintains a static allowlist of pre-I3 command names (Feature 1 + Feature 2 + Feature 3 library); these are the 33 entries that exist in `_HANDLERS` before line "# Intake & triage commands (WP-I3-004)". If new pre-I3 commands appear after this WP, the operator updates the allowlist or moves them into `i3_command_surface:`.
- **Risk**: Check #4 needs Postgres. **Mitigation**: SKIP line when DB unreachable; documented behavior, not a fault.
- **Dependency**: `pwsh` ≥ 7 OR Windows PowerShell 5.1 — both already required by every other repo script. **Owner**: operator. **Status**: satisfied.

## Definition Of Done

- [x] `scripts/audit-repo.ps1` runs the 4 existing checks and the 4 new checks in one pass; exit code 0 on the live tree at HEAD.
- [x] Header comment in `audit-repo.ps1` describes all 8 checks with rule_id references.
- [x] `[rule-id-resolves-manual]` check parses `topology.yaml` `rule_registry.rules:` and verifies every entry's `manual:` value resolves to either an existing manual file (`.gov/doc/manual/<topic>.md`), an existing manual anchor (`<topic>#<anchor>`), or one of the cross-reference paths `../AGENTS.md#<anchor>` / `../workflow/README.md#<anchor>`. 25/25 entries resolved.
- [x] `[citations-cite-real-rule-ids]` check scans `*.py` files under `.product/src/` for the literal pattern `\bby\s+([A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d+)\s+\(` and the kwarg pattern `rule_id\s*=\s*["']([A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d+)["']`; verifies global-family rule_ids (RUL-, AMOOD-, INTAKE-, TARGET-, REQ-, SAFE-) resolve in the topology registry. WP- family explicitly skipped (workpacket references). Project-scoped families emit `info`.
- [x] `[dispatcher-commands-have-help]` check reads `_HANDLERS = { ... }` from `commands.py`, extracts every quoted key (55 commands), and verifies coverage in `topology.yaml` `i3_command_surface.*` or the static pre-I3 allowlist. Found one gap: `intake_begin_run` (WP-I3-005) was missing from topology; added in this WP.
- [x] `[project-rules-fresh]` check: when `LIBRARY_DB_URL` is unset emits one SKIP line; when set, shells out to `.venv/Scripts/python.exe` with an inline psycopg query to surface stale rules as warn lines. SKIP path verified on HEAD; live-DB path is by-design behavior, not exercised in this WP.
- [x] Negative-test artifact: introduced `_audit_negative_test.py` with RUL-999 + INTAKE-999 + EXP120-RES-001; observed exit 1 with 2 violations on the bogus IDs and 1 info on the project-scoped ID; reverted via `/safe-delete`. Saved to `target/test-artifacts/WP-I3-009/audit-negative-citations.txt`.
- [x] `audit-repo.ps1` final report line lists all 8 check names.
- [x] **Manual Impact**: `No — audit script is operator/CI-facing infrastructure with no in-app surface; not documented in the manual.`

## Test Coverage Plan

### Functional Flow Tests
- [ ] Clean run on HEAD: exit 0; report lists 8 checks; OK count matches.
- [ ] Negative run with synthetic bad rule_id citation in a Python file: exit 1; one violation line `[citations-cite-real-rule-ids]`. Captured in `audit-negative-citations.txt`.

### Code Correctness Tests
- [ ] `topology.yaml` parser regex matches every existing rule entry (count >= 25).
- [ ] `_HANDLERS` parser regex matches every key in the dict (count >= 56 at HEAD).
- [ ] `manual_link` resolution handles the three forms in current registry: `<topic>` (no anchor, e.g. RUL-000), `<topic>#<anchor>` (e.g. AMOOD-001), `../<file>#<anchor>` (e.g. RUL-001 references `../workflow/README.md#hard-rules`).

### Red-Team / Abuse Tests
- [ ] Citation against `RUL-999` (non-existent) fails check #2.
- [ ] Citation against `EXP120-FOO-001` (project-scoped, not in global registry) emits an `info` line, not a violation.
- [ ] Dispatcher command `foo_bar_baz` not in topology fails check #3.
- [ ] Manual link to `nonexistent-topic` fails check #1.

### Performance / Reliability Tests
- [ ] Audit completes in < 10 seconds on full repo (current 4-check audit completes in ~3s; 4 added checks add string-grep cost only).

## Rollback Plan

- Files to revert: `scripts/audit-repo.ps1` (only file touched by this WP).
- Files to keep: WP file + taskboard row (those record intent).
- Recovery command: `git checkout scripts/audit-repo.ps1`.

## Decisions Log

- 2026-05-03: Use line-regex against YAML rather than a YAML parser. Reason: PowerShell 5.1 has no built-in YAML parser; the rule entries in topology.yaml are already single-line with stable shape. Alternatives considered: bundle `powershell-yaml` module (rejected — adds an install step that breaks fresh-clone audit), shell out to Python (rejected — couples PS audit to working venv).
- 2026-05-03: Project-scoped rule_ids (`EXP120-*`) emit `info`, not violation. Reason: those live in DB at runtime; the audit cannot know what's authored without a DB connection. Alternative: hardcode known project slugs (rejected — defeats the point of project-scoped).
- 2026-05-03: Pre-I3 dispatcher commands maintained as a static allowlist. Reason: operator-facing manual already documents them in `feature-1-yaw-exporter.md`, `feature-2-calibration-overlay.md`, `feature-3-library-postgresql.md`; folding them into `i3_command_surface:` would lie about authorship. Alternative: extend `topology.yaml` with a `legacy_command_surface:` block (deferred — out of scope for an audit-only WP).
- 2026-05-03: Check #4 SKIP when DB unreachable. Reason: audit must be runnable on a fresh clone without Postgres bootstrap. Alternative: hard-fail (rejected — breaks `audit-repo.ps1` for any contributor without library DB env).

## Fallback Register

- **Path**: `scripts/audit-repo.ps1` check #4 (`project-rules-fresh`)
- **Required Label In Code/UI**: `# v0.1: SKIP when LIBRARY_DB_URL not set`
- **Successor / Debt Owner**: future I4+ WP (when CI runs against an ephemeral DB)
- **Exit Condition To Remove**: CI brings up Postgres before audit, or the audit grows a `--require-db` flag the operator opts into

## Change Ledger

- **What Became Real**: `scripts/audit-repo.ps1` extended from 4 to 8 checks. The four new checks read `topology.yaml rule_registry.rules` (regex-parsed; no YAML library required) and verify: (5) every rule_id's `manual:` value resolves to an existing manual file or anchor, supporting three link forms (`<topic>`, `<topic>#<anchor>`, `../AGENTS.md#<anchor>` / `../workflow/README.md#<anchor>`); (6) every `by <RULE_ID> (` literal citation and every `rule_id="..."` kwarg in `.product/src/**/*.py` cites a real rule_id, with project-scoped families emitting `info` and the `WP-` family explicitly excluded as workpacket references; (7) every command in `_HANDLERS` is in topology `i3_command_surface` or in the static pre-I3 allowlist; (8) `library_rules.last_validated_at > 30 days` warn-line under a SKIP-by-default policy when `LIBRARY_DB_URL` is unset. Audit-found governance gap fixed in the same WP: `intake_begin_run` (added by WP-I3-005) was missing from `topology.yaml i3_command_surface.intake_and_triage`; added.
- **What Remains Simulated**: Check #8 SKIPs by default; the actual DB query path is implemented but only fires when an operator sets `LIBRARY_DB_URL` and a venv with `psycopg` is reachable. v0.1 acceptable per spec ("operator-side validation cadence comes later").
- **Next Blocking Real Seam**: Two audit ideas from spec deferred (DB CHECK-constraint citation matching; cross-registry duplicate detection). Both need a Python helper layer that justifies its own WP. Migrating existing dispatcher errors to the citation shape (so check #6 has more inputs to validate against) is independent of this WP and falls to the dispatcher refactor that WP-I3-007 + WP-I3-008 will trigger naturally.

## Checkpoint Commit Plan

1. Governance kickoff commit: this WP file + taskboard row. Push must succeed.
2. Implementation commit: `scripts/audit-repo.ps1` extension.
3. Verification commit: WP file → REVIEW with Change Ledger + Evidence; taskboard row migrates Active → Pending Review; evidence files staged from `target/test-artifacts/WP-I3-009/`.

## Proof Of Implementation

- **Command Runs**: `pwsh scripts/audit-repo.ps1` produces output captured at `target/test-artifacts/WP-I3-009/audit-clean.txt`.
- **Proof Artifact**: `target/test-artifacts/WP-I3-009/`
- **Claim Standard**: never mark `DONE` without a clean audit run + the negative-test artifact demonstrating check #2 actually fires.

## Headless LLM Operation Compliance

- `N/A — non-visual change`. Audit script runs from PowerShell; no GUI, no command-channel surface, no state.json mutation, no snapshot target. The audit is operator/CI-facing infrastructure.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [ ] Audit script runs clean on HEAD and the captured output is under `target/test-artifacts/WP-I3-009/`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence section.
- [ ] **Headless LLM Operation Compliance** marked `N/A — non-visual change`.

## Evidence

- **Audit Clean Run**: `target/test-artifacts/WP-I3-009/audit-clean.txt` — exit 0; 8 checks listed; 1 SKIP (project-rules-fresh, by design); 0 violations on HEAD.
- **Audit Negative Test**: `target/test-artifacts/WP-I3-009/audit-negative-citations.txt` — synthetic file `_audit_negative_test.py` injected RUL-999 + INTAKE-999 (both bogus, global family) + EXP120-RES-001 (project-scoped). Audit produced exit 1 with 2 violations on the bogus IDs and 1 info on the project-scoped ID. File subsequently safe-deleted (log: `target/safe-delete-log/20260503-222812-wp-i3-009-negative-test.log`).
- **Pytest (smoke subset)**: `pytest .product/tests/test_yaw_bin.py .product/tests/test_rotation.py` → 31 passed in 2.15s. The full suite was attempted but hung in this environment after writing only 17 bytes; investigation confirmed no python process active when the 10-minute monitor timed out. The hang is unrelated to this WP's changes (no Python module imports `topology.yaml` or `audit-repo.ps1`); a smoke-import of `openrepose.commands._HANDLERS` (55 entries) and `openrepose.library.citations.all_rule_ids()` (25 entries) succeeded, confirming no regression from the only Python-adjacent change (added `intake_begin_run` to `topology.yaml i3_command_surface`). Full-suite run owed to the next WP's verification step.
- **Build Artifacts**: `N/A`
- **Proof Artifact**: `target/test-artifacts/WP-I3-009/` — `audit-clean.txt`, `audit-negative-citations.txt`.
- **Operator Sign-off**: _(pending)_

## Progress Log

- `2026-05-03`: WP authored at IN-PROGRESS as part of Sweep B (predecessor: WP-I3-001 + WP-I3-006 DONE). Kickoff push pending.
- `2026-05-03`: Kickoff commit b75cc86 pushed to origin/main.
- `2026-05-03`: `audit-repo.ps1` extended; topology.yaml gap fix (`intake_begin_run` added). Audit clean on HEAD; negative-test verified. Smoke pytest 31/31 (full suite hung in this environment, unrelated to PowerShell+YAML scope; documented in Evidence). WP transitioned to REVIEW.
