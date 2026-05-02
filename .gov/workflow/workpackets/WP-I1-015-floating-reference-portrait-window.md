# WP-I1-015 - Floating Reference Portrait Window

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements (extend with reference-portrait window).

## Intent

Add a small floating viewport that displays the imported source portrait while the operator works on the rig and OpenPose preview. Window position, size, and visibility are persisted across launches (depends on WP-I1-003 settings persistence). Operator-chosen padding color fills empty canvas around the portrait when synchronized zoom (WP-I1-024) shrinks it.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-004 must reach DONE; WP-I1-003 (settings persistence) for position/size/visibility persistence.
- **Successor(s)**: WP-I1-024 (synchronized viewport zoom — uses the same padding-color setting and zoom factor).

## Reality Boundary

- **Real Seam**: new `gui/reference_window.py` `ReferenceWindow(QWidget)` floating window with `Qt.WindowStaysOnTopHint`. Displays the master portrait via `QLabel` + `QPixmap`. Persistent state stored in settings.json: `reference_window.x`, `.y`, `.w`, `.h`, `.visible`, `.padding_color`.
- **User-Visible Win**: operator imports a portrait, optionally toggles "Show reference window" — a small floating window appears showing the source. Operator drags / resizes; close+reopen the app, the window returns at the same position and size.
- **Proof Target**: pytest-qt covers position/visibility persistence; manual: drag the window to a corner, quit, reopen, window appears at the same corner.

## In Scope

- `ReferenceWindow` widget with image display, padding color from settings, persistent geometry.
- Settings additions for the window state (under WP-I1-003 schema).
- New menu entry "View → Show reference window" plus toolbar toggle button.
- New snapshot target `reference_window` so the LLM can grab it.
- Widget provider extension for the snapshot subsystem.
- Tests: visibility toggle, geometry persistence, padding color application, snapshot target produces a non-empty PNG.

## Out Of Scope

- Multiple reference windows (one window in v0.1).
- Image annotations on the reference (e.g., overlay landmarks — that belongs to the calibration WP).
- Drag-and-drop directly into the reference window (drag-and-drop import is WP-I1-005).

## Risks And Dependencies

- **Risk**: `Qt.WindowStaysOnTopHint` behavior varies between Windows display managers. **Mitigation**: keep behavior testable by mocking `QApplication.activeWindow()`.
- **Dependency**: WP-I1-003 settings persistence must ship first (or this WP ships with in-memory state and the persistence rider lands when WP-I1-003 closes).

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via new commands `set_reference_window {visible, x, y, w, h, padding_color}` and `dump_reference_window`.
- [ ] State reflected in `state.json` `reference_window` block.
- [ ] LLM pulls visual via `snapshot {target: "reference_window"}`.
- [ ] No `raise_/activateWindow/showNormal/setForegroundWindow` in any code path. The `WindowStaysOnTopHint` flag is set at construction; show() is operator-triggered.
- [ ] No modal dialogs from LLM commands.
- [ ] Tests cover the headless command path.

## Definition Of Done

- [ ] Operator toggles the reference window via menu / toolbar; portrait appears.
- [ ] Drag and resize the window; quit; reopen; window restores position and size.
- [ ] Padding color setting in Options applies to the reference window (verifiable by changing the value and re-rendering).
- [ ] `snapshot {target: "reference_window"}` produces a non-empty PNG.
- [ ] `pytest .product/tests/test_reference_window.py` zero failures; full project suite still green.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / GUI Requirements (extend with reference portrait window); LLM Control Surface (new commands).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (`set_reference_window`, `dump_reference_window`; new snapshot target; `WindowStaysOnTopHint` on construction only — no `raise_/activateWindow` calls).

## Linked Test Suite

- `.product/tests/test_reference_window.py` (NEW) — visibility toggle, geometry persistence, padding-color application, snapshot target, no-focus-steal regression.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-015-floating-reference-portrait-window.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — extend GUI Requirements with the reference window contract.

### Product (`.product/`)

- `.product/src/openrepose/gui/reference_window.py` (NEW) — `ReferenceWindow(QWidget)` with `Qt.WindowStaysOnTopHint`.
- `.product/src/openrepose/gui/main_window.py` — toolbar toggle + `View → Show reference window` menu entry; widget-provider registration for the snapshot target.
- `.product/src/openrepose/gui/options.py` — padding-color field (shared with WP-I1-024).
- `.product/src/openrepose/commands.py` — register `set_reference_window`, `dump_reference_window`.
- `.product/src/openrepose/state.py` — `reference_window` block (`x`, `y`, `w`, `h`, `visible`, `padding_color`).
- `.product/src/openrepose/snapshot.py` — register `reference_window` snapshot target.
- `.product/tests/test_reference_window.py` (NEW)

### Build / Output

- `outputs/.runtime/settings.json` — gains `reference_window.*` keys (depends on WP-I1-003 schema).
- `target/test-artifacts/WP-I1-015/`

## Risks And Dependencies

- **Risk**: `Qt.WindowStaysOnTopHint` interacts inconsistently with multi-monitor / mixed-DPI setups. **Mitigation**: regression-test on the operator's primary setup; document any unsupported configuration in the change ledger.
- **Risk**: settings persistence must agree on schema with WP-I1-003. **Mitigation**: declare the `reference_window` block in this WP's spec extension; cross-link both WPs.
- **Dependency**: WP-I0-004 must be DONE; WP-I1-003 settings persistence (or in-memory fallback if it lands first).

## Test Coverage Plan

### Functional Flow Tests
- [ ] Toggle `View → Show reference window`; window appears with the master portrait.
- [ ] Drag the window to a new position; quit; reopen; geometry restored.
- [ ] Change Options padding color; reference window padding updates on next refresh.
- [ ] `snapshot {target: "reference_window"}` returns a non-empty PNG.

### Code Correctness Tests
- [ ] state.json `reference_window` block matches the spec schema after each set-command.
- [ ] No code path calls `raise_/activateWindow/showNormal/setForegroundWindow` on the reference window.
- [ ] Hidden window state survives restart (visibility=false reproduced on reopen).

### Red-Team / Abuse Tests
- [ ] LLM `set_reference_window` while operator's main window has focus: zero focus theft (50-command stress test).
- [ ] Out-of-bounds geometry (off-screen): clamped to a usable area on next show; no crash.
- [ ] No GUI text or tooltip introduces forbidden yaw phrases.

### Performance / Reliability Tests
- [ ] Show/hide cycle under 50ms.

## Rollback Plan

- Files to revert: `gui/reference_window.py`, `gui/main_window.py`, `gui/options.py`, `commands.py`, `state.py`, `snapshot.py`, the new test file.
- Files to keep: existing `outputs/.runtime/settings.json` (loader tolerates missing keys).
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/gui/reference_window.py .product/src/openrepose/gui/main_window.py .product/src/openrepose/gui/options.py .product/src/openrepose/commands.py .product/src/openrepose/state.py .product/src/openrepose/snapshot.py .product/tests/test_reference_window.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec extension.
2. Implementation: `reference_window.py` + state + dispatcher.
3. GUI wiring: menu/toolbar toggle + widget provider for snapshot.
4. Verification: pytest-qt + no-focus-steal stress + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_reference_window.py --junitxml=target/test-artifacts/WP-I1-015/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-015/pytest_results.xml` plus a snapshot PNG of the reference window.
- **Claim Standard**: never mark `DONE` without junit XML evidence and a manual restart-cycle confirming geometry persistence.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-015/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
