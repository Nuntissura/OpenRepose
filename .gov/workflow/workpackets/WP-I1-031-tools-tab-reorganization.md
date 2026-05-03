# WP-I1-031 - Tools Tab Reorganization

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: REVIEW
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements (right dock layout) + Feature 2 / GUI Requirements (Calibration tab location).
- **Linked Test Suite**: extend `.product/tests/test_gui_layout.py` + `.product/tests/test_calibration_gui.py`.
- **Linked Check Script**: N/A.

## Intent

Reorganize the right-dock tabs into a coherent grouping. The current dock has Inspector / Calibration / Markers / Options / Log / Help — six top-level tabs. The operator wants a `Tools` top-level tab that contains a sub-`QTabWidget` of operator-driven editing tools: **Calibration** and **Reframer** (frame controls currently lumped into Options). Markers also moves into Tools as a sibling sub-tab (per the proposed default — operator can override at promotion).

After this WP the dock has: **Inspector | Tools (Calibration / Markers / Reframer) | Options | Log | Help** — five top-level tabs, with three editing tools grouped together.

## Linked Workpackets

- **Predecessor(s)**: WP-I1-001 (Calibration tab — DONE), WP-I1-029 (Markers tab — REVIEW), WP-I1-023 (frame controls in Options — REVIEW), WP-I0-004 (dock layout — DONE), WP-I1-027 (Options pane — REVIEW since the Reframer extraction touches it).
- **Successor(s)**: WP-I1-028 (calibration zoom + mesh inspector + show-all + drag-and-drop — operates inside the Calibration sub-tab once it exists).
- **Blocks**: none.
- **Blocked-By**: WP-I1-027 + WP-I1-029 + WP-I1-023 should be DONE first so this WP doesn't conflict with their REVIEW state. Acceptable to start while they are in REVIEW if operator authorizes.
- **Related**: any future WP adding more editing tools naturally sits as another Tools sub-tab.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements — extend with the Tools tab + sub-tab layout.
- `.gov/spec/openrepose_v0_1.md` Feature 2 / GUI Requirements — update Calibration location reference.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | PySide6 `QTabWidget` nested | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTabWidget.html | Nested QTabWidget is well-supported and standard. Inner tabs can be styled distinctly via the `QTabBar` selector. | adopt |
| 2026-05-03 | Operator UX feedback 2026-05-03 | this session | Operator wants Tools tab grouping editing tools (Calibration + Reframer + Markers). Current 6-top-level-tab dock feels cluttered. | adopt |
| 2026-05-03 | Existing Inspector + Options layout precedent | local | Inspector / Options stay as top-level (read-only / settings, not editing tools). Log / Help stay top-level (utility tabs). | adopt |

Decision: top-level dock becomes `Inspector | Tools | Options | Log | Help` (five tabs). The `Tools` widget is a `QTabWidget(Orientation.North)` with sub-tabs `Calibration | Markers | Reframer`. Frame controls move out of OptionsPane into a new `ReframerPane` widget that holds the same scale slider + offset spinboxes + anchor combo + reset button; the OptionsPane no longer renders the frame fields. Body-part visibility checkboxes stay in OptionsPane (they are coarse enable/disable settings, not an editing tool).

## Reality Boundary

- **Real Seam**: real `QTabWidget` reorganization in `gui/main_window.py`. New `gui/tools_pane.py` holds the inner `QTabWidget`. Frame controls extracted from `gui/options.py` into new `gui/reframer.py`. No dispatcher / state / spec contract changes.
- **User-Visible Win**: operator opens the GUI; right dock shows fewer top-level tabs; Calibration + Markers + Reframer are grouped under a single Tools tab; existing functionality unchanged.
- **Proof Target**: extended pytest-qt assertions on the dock layout (5 top-level tabs in expected order; Tools tab contains 3 sub-tabs in expected order; ReframerPane functional and connected to dispatcher); existing GUI tests still pass after reshuffle.
- **Allowed Temporary Fallbacks**: none.
- **Promotion Guard**: do not promote until the operator confirms the new layout matches their expectation and that all editing tools (calibration markers, marker visibility, frame slider) still work end-to-end.

## In Scope

- `gui/tools_pane.py` (NEW): `ToolsPane(QWidget)` containing an inner `QTabWidget`. Adds three sub-tabs (CalibrationPane, MarkersPane, ReframerPane).
- `gui/reframer.py` (NEW): `ReframerPane(QWidget)` extracted from the frame controls currently in OptionsPane. Owns the scale slider + offset spinboxes + anchor combo + reset button. Same signals as before (`frame_scale_changed`, `frame_offset_changed`, `frame_anchor_changed`, `frame_reset_clicked`).
- `gui/options.py`: remove frame controls + their signals + `load_frame()`. Body-part visibility checkboxes stay.
- `gui/main_window.py`: replace the three top-level tabs (Calibration / Markers / Options-with-frame) with `Tools` containing `CalibrationPane` / `MarkersPane` / `ReframerPane`. Wire `ReframerPane` signals to dispatcher commands. Initial sync via `load_frame()` on the new pane.
- `test_gui_layout.py`: update `test_six_dock_tabs_present` to expect `["Inspector", "Tools", "Options", "Log", "Help"]` (5 tabs); add `test_tools_tab_has_three_sub_tabs`.
- `test_calibration_gui.py`: any test that asserts via `window._calibration` continues to work because we keep `window._calibration` as an attribute pointing at the same widget instance (now a child of ToolsPane instead of the top dock).

## Out Of Scope

- Visual styling / icons for the Tools tab and sub-tabs (separate polish WP if desired).
- Keyboard shortcuts for switching between Tools sub-tabs (covered by WP-I1-004 extended keyboard shortcuts).
- New tools beyond the three (calibration / markers / reframer). Operator's call to add more later.
- Reordering Inspector / Options / Log / Help.

## Expected Files Touched

### Governance (`.gov/`)
- `.gov/workflow/workpackets/WP-I1-031-tools-tab-reorganization.md` (this file).
- `.gov/workflow/TASKBOARD.md` — Active row at READY when promoted.
- `.gov/spec/openrepose_v0_1.md` — small extension to GUI Requirements + Feature 2 location reference.

### Product (`.product/`)
- `.product/src/openrepose/gui/tools_pane.py` (NEW).
- `.product/src/openrepose/gui/reframer.py` (NEW).
- `.product/src/openrepose/gui/options.py` — remove frame controls.
- `.product/src/openrepose/gui/main_window.py` — replace tab construction.
- `.product/tests/test_gui_layout.py` — update tab expectations.
- `.product/tests/test_tools_pane.py` (NEW) — sub-tab presence + Reframer functionality.

### Build / Output (gitignored)
- `target/test-artifacts/WP-I1-031/`

## Risks And Dependencies

- **Risk**: tests that reference `window._calibration` or `window._markers` directly. **Mitigation**: keep these attributes on MainWindow pointing at the same widget instances (now hosted inside ToolsPane); existing test code keeps working.
- **Risk**: operator confused by the reorg if mid-flow. **Mitigation**: ship together with a small note in the Help tab pointing at the new structure.
- **Risk**: ReframerPane extraction risks signal disconnection. **Mitigation**: preserve the same signal names; main_window's `_wire_actions` block updates accordingly.
- **Dependency**: WP-I1-027 / 029 / 023 should ideally be DONE first — but if operator wants to start before they sign off, the changes can land on top of REVIEW state without conflict (this WP only reshuffles widget hosting, not their behavior).

## Definition Of Done

- [ ] Top-level dock has exactly 5 tabs in order: Inspector / Tools / Options / Log / Help.
- [ ] Tools tab contains exactly 3 sub-tabs in order: Calibration / Markers / Reframer.
- [ ] Frame controls function identically inside Reframer (set_frame_scale / set_frame_offset / set_frame_anchor / reset_frame still dispatched).
- [ ] No regression in existing GUI tests (calibration, markers, options minus frame).
- [ ] `pytest` zero failures; junit XML at `target/test-artifacts/WP-I1-031/pytest_results.xml`.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] Operator confirms the new layout works as expected.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Window has 5 top-level tabs in expected order.
- [ ] Tools tab contains Calibration / Markers / Reframer sub-tabs.
- [ ] Adjusting Reframer scale slider dispatches `set_frame_scale` (verify state update).
- [ ] Adjusting Reframer offset dispatches `set_frame_offset`.
- [ ] Reframer reset button dispatches `reset_frame`.
- [ ] Calibration tab still functional (existing tests).
- [ ] Markers tab still functional (existing tests).

### Code Correctness Tests
- [ ] `MainWindow._calibration`, `_markers`, `_reframer` attributes present and point to live widget instances.
- [ ] OptionsPane no longer exposes `frame_scale_slider` / `frame_offset_x` / `frame_offset_y` / `frame_anchor_combo` / `btn_frame_reset`.

### Red-Team / Abuse Tests
- [ ] No focus-stealing API call introduced by the reorg (existing test_gui_no_focus_steal continues to pass).
- [ ] No GUI string introduces a forbidden yaw phrase.

## Rollback Plan

- Files to revert: gui/options.py, gui/main_window.py; delete new gui/tools_pane.py + gui/reframer.py; revert test_gui_layout.py; remove new test_tools_pane.py.
- Recovery: `git restore --staged .product/ .gov/spec/; git checkout -- .product/ .gov/spec/`.

## Decisions Log

- 2026-05-03: Markers under Tools (not standalone). Reason: operator's mental model groups editing tools together; Markers is per-keypoint editing, Calibration is per-marker editing — both belong under the same Tools umbrella. Operator can override at promotion.
- 2026-05-03: Body-part visibility checkboxes stay in OptionsPane. Reason: coarse enable/disable settings are configuration, not editing.
- 2026-05-03: Inspector + Log + Help stay top-level. Reason: read-only tabs (Inspector, Log) and reference (Help) don't fit under "Tools".

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: WP file + taskboard row + spec extension.
2. Implementation: extract ReframerPane + ToolsPane + reshuffle main_window.
3. Verification: pytest + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_gui_layout.py .product/tests/test_tools_pane.py .product/tests/test_calibration_gui.py --junitxml=target/test-artifacts/WP-I1-031/pytest_results.xml`.
- **Proof Artifact**: `target/test-artifacts/WP-I1-031/pytest_results.xml`.

## Headless LLM Operation Compliance

- [ ] N/A — pure GUI reorganization. No new commands, no new state, no new snapshot target. Existing headless surface unchanged.
- [ ] No `raise_/activateWindow/showNormal/setForegroundWindow` from any path.
- [ ] No modal dialogs.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects DONE.
- [ ] Reality Boundary truthful (Change Ledger filled at REVIEW).
- [ ] Linked test suite executed; junit XML saved.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded.

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at status DRAFT. Awaits operator promotion to READY.
- 2026-05-03: Operator authorized fast-track. New `gui/tools_pane.py` (ToolsPane wrapping QTabWidget with Calibration / Markers / Reframer sub-tabs). New `gui/reframer.py` (ReframerPane extracted from OptionsPane: scale slider+QDoubleSpinBox, offset_x slider+QSpinBox, offset_y slider+QSpinBox, anchor combo, per-section reset buttons + global Reset). OptionsPane no longer hosts frame controls. main_window.py replaces top-level Calibration + Markers tabs (and the in-Options frame controls) with a single Tools top-level tab. Top-level dock now: Inspector / Tools / Options / Log / Help (5 tabs). MainWindow keeps `self._calibration` / `self._markers` / `self._reframer` references pointing at the same widget instances under ToolsPane so existing tests + state-poll path keep working. Per-section reset signals dispatch the matching command. Operator's request "frame offsets are sliders but also numerical inputs + a reset" is satisfied by the slider+spinbox bidirectional binding + the Reset XY button + global Reset frame button. Full suite 323/323. Audit clean. Status IN-PROGRESS -> REVIEW.
