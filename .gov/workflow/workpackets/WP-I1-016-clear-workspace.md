# WP-I1-016 - Clear Workspace Command + Button

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: XS
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` LLM Control Surface (add command).

## Intent

A `clear_workspace` command + a "Clear workspace" toolbar button that drops the active rig, resets yaw to `0`, and clears the viewports back to "no rig loaded". Distinct from `clear_outputs` (which only purges the state arrays). Does NOT touch OptionsPane settings, avatar slug, run tag, channel toggles, or log.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-004 must reach DONE.

## Reality Boundary

- **Real Seam**: new `_h_clear_workspace` handler clears `dispatcher._rig`, calls `state.set_rig(status="none", ...)`, calls `state.set_yaw(value_deg=0.0, bin_label="0")`, calls `state.set_portrait(None)`. Toolbar button + `Edit → Clear workspace` menu entry both dispatch the command.
- **User-Visible Win**: operator clicks Clear workspace; viewports go blank; status bar reads `rig=none`; settings tab is unchanged.
- **Proof Target**: pytest covers the clear command and verifies state changes; full project suite still green.

## In Scope

- New command handler.
- Toolbar button + menu entry.
- Tests: clear flips rig.status to none, yaw to 0, portrait to None; settings preserved; subsequent `import_portrait` works as expected; existing `clear_outputs` semantics unchanged.

## Out Of Scope

- Confirmation dialog before clearing (the operator-explicit command means no confirmation needed).
- Undo / redo.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via `clear_workspace`.
- [ ] State reflected in `state.json` (rig.status="none", yaw bin "0", portrait null).
- [ ] LLM pulls visual via existing snapshot targets (3D viewport falls back to "no rig loaded" placeholder).
- [ ] No focus theft / modal dialogs.
- [ ] Tests cover headless path.

## Definition Of Done

- [ ] Command works headlessly and via the toolbar button.
- [ ] OptionsPane settings, log, and channel toggles are confirmed unchanged after clear.
- [ ] `pytest` zero failures.

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

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec extension.
2. Implementation: dispatcher handler + GUI wiring.
3. Verification: pytest + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_clear_workspace.py --junitxml=target/test-artifacts/WP-I1-016/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-016/pytest_results.xml`
- **Claim Standard**: never mark `DONE` without junit XML evidence and a manual smoke confirming settings/logs survive the clear.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-016/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
