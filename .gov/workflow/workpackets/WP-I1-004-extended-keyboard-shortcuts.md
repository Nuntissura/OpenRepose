# WP-I1-004 - Extended Keyboard Shortcuts

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: XS
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements.

## Intent

Add the rest of the operator-friendly keyboard shortcuts beyond the four primaries (`Ctrl+O`, `Ctrl+E`, `Ctrl+Shift+E`, `Ctrl+Q`) shipped in WP-I0-004. Recorded as a fallback there.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-004 must reach DONE.

## Reality Boundary

- **Real Seam**: register additional `QShortcut` / `QAction` bindings in `gui/main_window.py`.
- **User-Visible Win**: operator can fully drive the GUI from keyboard alone. Shortcut list visible in the Help tab.
- **Proof Target**: pytest-qt simulates each shortcut and asserts the corresponding command was dispatched.

## In Scope

Shortcuts to add (final list refined when WP promoted to READY):
- `Ctrl+R` — reload current portrait
- `Ctrl+1`..`Ctrl+9` — select bin from list (1=0, 2=her-left 15, etc.)
- `[` / `]` — yaw slider step -5 / +5 degrees
- `Shift+[` / `Shift+]` — yaw slider step -15 / +15 degrees
- `F5` — refresh viewports
- `Ctrl+Shift+S` — save settings (when WP-I1-003 closes)
- `Ctrl+Shift+C` — open Calibration tab (when WP-I1-001 closes)
- `Ctrl+,` — focus Options tab
- `Ctrl+L` — focus Log tab
- `F1` — focus Help tab
- `Esc` — cancel current operation (where applicable)

## Out Of Scope

- Custom user-rebindable shortcuts.
- Drag-and-drop (separate WP).

## Headless LLM Operation Compliance

- [x] N/A — keyboard shortcuts are operator-only convenience; LLM uses the command channel.

## Definition Of Done

- [ ] All listed shortcuts registered and functional.
- [ ] Help tab text updated to list them.
- [ ] pytest-qt covers each shortcut.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / GUI Requirements (keyboard shortcut list).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (operator-only convenience; LLM uses command channel).

## Linked Test Suite

- `.product/tests/test_keyboard_shortcuts.py` (NEW) — pytest-qt simulates each binding and asserts the dispatched command.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-004-extended-keyboard-shortcuts.md` (this file)
- `.gov/workflow/TASKBOARD.md`

### Product (`.product/`)

- `.product/src/openrepose/gui/main_window.py` — register `QShortcut` / `QAction` for each binding.
- `.product/src/openrepose/gui/help_pane.py` — update reference text with the full shortcut table.
- `.product/tests/test_keyboard_shortcuts.py` (NEW)

### Build / Output

- `target/test-artifacts/WP-I1-004/`

## Risks And Dependencies

- **Risk**: shortcut conflicts with platform / Qt defaults (e.g., `Ctrl+,` on macOS). **Mitigation**: document Windows-first; verify each shortcut against Qt's reserved set; reassign on conflict.
- **Risk**: shortcuts firing while text fields have focus could mutate the rig. **Mitigation**: scope `QShortcut` to `Qt.WindowShortcut` and skip when an editable widget has keyboard focus.
- **Dependency**: WP-I0-004 (toolbar + dispatcher) DONE; some shortcuts gate on WP-I1-001 / WP-I1-003.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Each shortcut in the In-Scope list fires its handler exactly once.
- [ ] `Ctrl+1` selects bin `0`; `Ctrl+2` selects `her-left 15`; `Ctrl+9` selects `her-right 90`.
- [ ] `[` and `]` step yaw by -5 / +5; `Shift+[` / `Shift+]` step by -15 / +15.

### Code Correctness Tests
- [ ] No shortcut fires while a `QLineEdit` / `QPlainTextEdit` has focus.
- [ ] Help pane text matches the registered shortcut set (table-vs-code parity test).

### Red-Team / Abuse Tests
- [ ] No registered shortcut text contains a forbidden yaw phrase (`image-left`, `image-right`, `viewer-left`, `viewer-right`, `left view`, `right view`).
- [ ] Holding a shortcut does not enqueue duplicate commands (autorepeat suppressed where dangerous, e.g., on Export).

### Performance / Reliability Tests
- [ ] Shortcut-driven yaw step at autorepeat speed produces no dropped renders for 5 seconds.

## Rollback Plan

- Files to revert: `gui/main_window.py`, `gui/help_pane.py`, the new test file.
- Files to keep: WP file moved to archive `CANCELLED` if rolled back.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/gui/main_window.py .product/src/openrepose/gui/help_pane.py .product/tests/test_keyboard_shortcuts.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row.
2. Implementation: register shortcuts in `main_window.py` + update `help_pane.py`.
3. Verification: pytest-qt suite + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_keyboard_shortcuts.py --junitxml=target/test-artifacts/WP-I1-004/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-004/pytest_results.xml`
- **Claim Standard**: never mark `DONE` without junit XML evidence and a manual smoke run that exercises every shortcut.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-004/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: marked N/A with reason (operator-only keyboard convenience; LLM uses command channel).

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
