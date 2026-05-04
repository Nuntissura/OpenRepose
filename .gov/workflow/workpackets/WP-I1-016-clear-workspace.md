# WP-I1-016 - Clear Workspace Command + Button

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Status**: REVIEW
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: XS
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` LLM Control Surface (add command).

## Intent

A `clear_workspace` command + a "Clear workspace" toolbar button (placed immediately next to the Open button) that drops the rig of the **active document**, resets its yaw to `0`, and clears the viewports back to "no rig loaded". Distinct from `clear_outputs` (which only purges the state arrays). Does NOT touch OptionsPane settings, avatar slug, run tag, channel toggles, log, or any inactive document tucked in another tab.

Today the application has a single-document model so "active document" == "the only loaded portrait"; the contract is written this way to remain correct after WP-I1-036 lands the multi-file workspace.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-004 must reach DONE.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-04 | Local codebase | `.product/src/openrepose/state.py` (set_rig / set_yaw / set_portrait), `.product/src/openrepose/commands.py` (existing `_h_clear_outputs` for handler shape), `.product/src/openrepose/gui/toolbar.py`, `.product/src/openrepose/gui/main_window.py` | All primitives required by the contract already exist. Handler composes existing state setters; toolbar receives a new QAction adjacent to Open. No new external dependency. | adopt |
| 2026-05-04 | Operator decision (kickoff) | n/a | Scope = active document only (forward-compat with WP-I1-036). Today active == only loaded portrait, so handler addresses `dispatcher._rig` directly; refactor to a `state.active_document_id` indirection lands when WP-I1-036 ships. | adopt |

- **Real Seam**: new `_h_clear_workspace` handler clears the active document's rig (`dispatcher._rig` today), calls `state.set_rig(status="none", ...)`, calls `state.set_yaw(value_deg=0.0, bin_label="0")`, calls `state.set_portrait(None)`. Toolbar button (next to Open) + `Edit → Clear workspace` menu entry both dispatch the command. Scope = active document only; non-active documents (when WP-I1-036 lands) are untouched.
- **User-Visible Win**: operator clicks Clear workspace; viewports go blank; status bar reads `rig=none`; settings tab is unchanged. After WP-I1-036, only the active tab clears.
- **Proof Target**: pytest covers the clear command and verifies state changes; full project suite still green.

## In Scope

- New command handler.
- Toolbar button + menu entry.
- Tests: clear flips rig.status to none, yaw to 0, portrait to None; settings preserved; subsequent `import_portrait` works as expected; existing `clear_outputs` semantics unchanged.

## Out Of Scope

- Confirmation dialog before clearing (the operator-explicit command means no confirmation needed).
- Undo / redo.

## Headless LLM Operation Compliance

- [x] LLM agent triggers via `clear_workspace`.
- [x] State reflected in `state.json` (rig.status="none", yaw bin "0", portrait null, avatar_slug null).
- [x] LLM pulls visual via existing snapshot targets (3D viewport renders the "no rig loaded" placeholder after clear).
- [x] No focus theft / modal dialogs (tested in `test_gui_no_focus_steal.py` regression).
- [x] Tests cover headless path (9 of 11 tests in `test_clear_workspace.py` are pure headless dispatch).

## Definition Of Done

- [x] Command works headlessly and via the toolbar button.
- [x] OptionsPane settings, log, and channel toggles are confirmed unchanged after clear.
- [x] Toolbar button placed immediately right of the Open button.
- [x] `pytest` zero failures across the affected suites.
- [x] Manual Impact: Yes — extends `feature-1-yaw-exporter.md` with the Clear workspace command + button + the active-document scope note.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — LLM Control Surface (add `clear_workspace`); Feature 1 / GUI Requirements (toolbar button + Edit menu).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (`clear_workspace` reachable headlessly; state mirrored in `state.json`).

## Linked Test Suite

- `.product/tests/test_clear_workspace.py` (NEW) — clear flips rig/yaw/portrait, settings preserved, subsequent import works.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-016-clear-workspace.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — register `clear_workspace` in the command table.

### Product (`.product/`)

- `.product/src/openrepose/commands.py` — register `_h_clear_workspace`.
- `.product/src/openrepose/state.py` — confirm `set_rig`, `set_yaw`, `set_portrait` cover the reset.
- `.product/src/openrepose/gui/toolbar.py` — Clear workspace button.
- `.product/src/openrepose/gui/main_window.py` — `Edit → Clear workspace` menu entry.
- `.product/tests/test_clear_workspace.py` (NEW)

### Build / Output

- `target/test-artifacts/WP-I1-016/`

## Risks And Dependencies

- **Risk**: confusion with `clear_outputs` semantics. **Mitigation**: docstring + Help pane line clearly describing the difference; test explicitly asserts `clear_outputs` and `clear_workspace` do different things.
- **Risk**: clearing while a batch export is in flight could leave orphan files. **Mitigation**: command refuses (structured ERR) when an export is running; status bar shows the reason.
- **Dependency**: WP-I0-004 (toolbar + menu + dispatcher).

## Test Coverage Plan

### Functional Flow Tests
- [ ] After `clear_workspace`: `state.rig.status == "none"`, `state.yaw.bin_label == "0"`, `state.portrait is None`.
- [ ] Toolbar button dispatches the same command as the menu entry.
- [ ] Subsequent `import_portrait` succeeds normally.

### Code Correctness Tests
- [ ] Settings, log, and channel toggles unchanged after clear.
- [ ] `clear_outputs` semantics unchanged after this WP.

### Red-Team / Abuse Tests
- [ ] `clear_workspace` issued during a running batch: structured ERR, no state mutation.
- [ ] No GUI text or tooltip introduces forbidden yaw phrases.

### Performance / Reliability Tests
- [ ] Clear under 30ms; viewports redraw to "no rig loaded" within 1 frame.

## Rollback Plan

- Files to revert: `commands.py`, `gui/toolbar.py`, `gui/main_window.py`, the new test file.
- Files to keep: existing `clear_outputs` handler unchanged.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/commands.py .product/src/openrepose/gui/toolbar.py .product/src/openrepose/gui/main_window.py .product/tests/test_clear_workspace.py`

## Decisions Log

- 2026-05-04 (kickoff): scope = ACTIVE document only. Forward-compat with WP-I1-036 multi-file workspace. Today active == only loaded portrait, but the handler is written to address `state.active_document` (or equivalent) rather than mutating all documents. Reason: operator-stated preference; avoids a future breaking-semantics change.
- 2026-05-04 (kickoff): toolbar button placement = adjacent to the Open button (not at the end of the toolbar). Reason: operator-stated preference; pairs the destructive workspace action with its constructive sibling.
- 2026-05-04 (implementation): "active document" today is the only document, so handler addresses `dispatcher._rig` directly + the single `state.{rig,yaw,portrait,avatar_slug}` block. When WP-I1-036 lands, refactor the handler to read `state.active_document_id` (or equivalent) and only clear that document; the existing tests will guide the change.
- 2026-05-04 (implementation): no "export-running" guard added. The original WP draft Risk note suggested a guard ("clearing while a batch export is in flight could leave orphan files") — but exports are synchronous and run inside the dispatcher lock, so concurrent clear during export is structurally impossible. Removing the guard kept the handler under 10 lines. Recorded in Fallback Register.
- 2026-05-04 (implementation): widened `state.set_portrait(path: str)` → `set_portrait(path: str | None)` so a single call cleanly resets the active portrait + avatar_slug. Existing callers (which always pass `str`) are unaffected; the wider type narrows behaviour without breaking them.

## Fallback Register

- 2026-05-04: dropped the planned "export-running" guard. Reason: exports are synchronous + serialized through the dispatcher lock; a concurrent `clear_workspace` cannot interleave with an in-flight export. Reinstating the guard would be dead code today; revisit only if exports ever go async.

## Change Ledger

- 2026-05-04 — Added `_h_clear_workspace` handler in `commands.py` (resets `dispatcher._rig`, `state.set_rig(status="none")`, `state.set_yaw(0, "0")`, `state.set_portrait(None)`). Returns `{cleared, portrait, avatar_slug, rig, yaw}`.
- 2026-05-04 — Registered `clear_workspace` in `_HANDLERS` and added to audit-repo.ps1 `$preI3Allowlist`.
- 2026-05-04 — Widened `AppState.set_portrait` signature to accept `path: str | None`; clearing path also clears `avatar_slug` so they travel together.
- 2026-05-04 — Toolbar gained `clear_workspace_clicked` Signal + a "Clear workspace" QPushButton placed immediately right of Open. Tooltip explains the active-document scope.
- 2026-05-04 — MainWindow gained an `Edit` menu with the "Clear workspace" QAction (`act_clear_workspace`). Both surfaces dispatch the same headless command via `MainWindow._on_clear_workspace`.
- 2026-05-04 — Added `.product/tests/test_clear_workspace.py` with 11 tests: rig+yaw+portrait reset, state.json reflection, re-import after clear, idempotent clear-on-empty, settings preserved, body-part-visibility preserved, log preserved, `clear_outputs` semantics unchanged, adult_production_boundary surfaced, toolbar button dispatch, Edit menu action dispatch.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec extension.
2. Implementation: dispatcher handler + GUI wiring.
3. Verification: pytest + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_clear_workspace.py --junitxml=target/test-artifacts/WP-I1-016/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-016/pytest_results.xml`
- **Claim Standard**: never mark `DONE` without junit XML evidence and a manual smoke confirming settings/logs survive the clear.

## Exit Criteria

- [x] Definition of Done items all checked.
- [x] Taskboard row reflects current status.
- [x] Reality Boundary, Fallback Register, Change Ledger truthful (export-running-guard fallback recorded; active-document forward-compat note recorded).
- [x] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-016/pytest_results.xml`.
- [x] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [x] Headless LLM Operation Compliance: all items checked.

## Evidence

- `target/test-artifacts/WP-I1-016/pytest_results.xml` — 11/11 passing.
- Combined polish-bundle regression: 119/119 passing across `test_drag_and_drop.py` + `test_clear_workspace.py` + `test_settings_commands.py` + `test_settings_store.py` + `test_export_folder.py` + `test_command_handlers.py` + `test_gui_layout.py` + `test_gui_no_focus_steal.py` + `test_gui_state_sync.py`.
- `pwsh scripts/audit-repo.ps1` clean (8 OK, 1 SKIP).
- Manual: `.gov/doc/manual/feature-1-yaw-exporter.md` "Clearing the workspace" section.

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
- 2026-05-04: Promoted DRAFT → IN-PROGRESS as part of polish bundle (with WP-I1-003 + WP-I1-005). Workflow Version bumped 1.0 → 1.1; Manual Impact line added; active-document scope frozen; button placement frozen (next to Open).
- 2026-05-04: IMPLEMENTATION → REVIEW. Handler + toolbar button + Edit menu shipped; 11/11 new tests passing; manual extended; widened `state.set_portrait` to accept None.
