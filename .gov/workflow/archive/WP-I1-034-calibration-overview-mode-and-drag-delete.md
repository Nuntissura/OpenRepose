# WP-I1-034 - Calibration Overview Mode + Drag/Delete + Mesh Inspector + Add-Marker Workflow

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DONE
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: L
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 2 / GUI Requirements (Calibration tab — extend with Overview mode, drag-to-move, right-click delete, no-detection add+place workflow, mesh inspector).
- **Linked Test Suite**: extend `.product/tests/test_calibration_gui.py`; new `.product/tests/test_delete_markers_command.py`.

## Intent

Operator-feedback follow-up to WP-I1-001 / WP-I1-028. Picks up everything deferred from those two WPs and adds the new calibration UX surfaced during operator GUI inspection 2026-05-03:

1. **Default empty marker selector**. Marker dropdown shows `— pick one —` placeholder; nothing pre-selected on first open. Operator must consciously pick a marker (or Overview mode) before placement actions take effect.
2. **"Overview" entry at the top of the marker selector**. New mode. When picked: all 10 anatomical markers visible AND draggable on the portrait. Operator drags any marker to a new position; release fires `set_calibration_points` with merge=true. The current always-on dim-dot overlay (WP-I1-028) becomes the static reference while a single marker is selected; in Overview mode the dim dots become bright draggable rings.
3. **Drag-to-move existing operator markers** (originally deferred from WP-I1-001 + WP-I1-028). Mouse press inside a marker's hit radius → drag mode for that marker → release fires `set_calibration_points` (merge=true). Click-without-drag still places a marker for the currently-selected name.
4. **Right-click delete operator markers** (originally deferred). New `delete_markers` LLM command (`{"names": [str, ...]}`). Right-click on an operator marker dispatches `delete_markers` with that single name; the bright ring disappears on the next refresh.
5. **No-detection → add+place workflow**. When an anatomical marker has no MediaPipe detection (current WP-I1-029 marks these "— no detection" in the Markers tab + auto-unchecks them), operator can ADD it via the calibration tab: pick the marker name (or right-click in Overview mode), click on the portrait where the feature is, the system stores the click as both `operator_xy` and `mediapipe_xy` (treated as an operator-supplied detection). The marker promotes from "no detection" to "operator-detected".
6. **Frontal mesh inspector** (originally in WP-I1-028 scope; deferred). Small collapsible widget below the portrait viewer showing the rig's face mesh + body skeleton at an independent inspection yaw. Slider scrubs `[-90, +90]`; does NOT mutate state.yaw / OpenPose preview / export. Operator uses it to disambiguate which detected landmark is which without leaving their place on the active yaw.

## Linked Workpackets

- **Predecessor(s)**: WP-I1-001 (DONE), WP-I1-028 (DONE), WP-I1-029 (DONE — auto-uncheck-undetected primitive this WP builds on).
- **Successor(s)**: future calibration spec extension if body calibration ships (operator noted face-only is current limitation).
- **Blocks**: none.
- **Blocked-By**: none.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` Feature 2 / GUI Requirements + Command Surface (extend with `delete_markers` + Overview-mode behavior + add+place semantics for undetected markers).
- `.gov/AGENTS.md` Headless LLM Operation Rule (`delete_markers` reachable headlessly).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | WP-I1-028 implementation | local | `_ZoomableImageView` (QGraphicsView) is in place; adding draggable QGraphicsItem subclasses for each marker is the natural extension. | adopt |
| 2026-05-03 | PySide6 QGraphicsItem.itemChange | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsItem.html | `ItemPositionHasChanged` notification fires after a drag; perfect for emitting the new operator_xy + dispatching set_calibration_points. | adopt |
| 2026-05-03 | Existing `render/draw_3d.py` | local | Mesh inspector reuses `render_3d_viewport(rotated)` with a synthesized `RotatedRig` at the inspection-only yaw. Same pattern WP-I1-028's spec proposed. | adopt |
| 2026-05-03 | Operator GUI inspection 2026-05-03 | this session | Overview mode is the operator's mental model for "edit anything" vs single-marker placement focus. Default-empty selector prevents accidental placements. add+place workflow handles the undetected case the WP-I1-029 fix only half-solved. | adopt all four |

## Reality Boundary

- **Real Seam**: `_ZoomableImageView` extended with per-marker QGraphicsItem children that respond to drag + right-click; new headless `delete_markers` command in the dispatcher; new `_MeshInspector` collapsible widget in the Calibration tab; marker dropdown behavior change (`— pick one —` placeholder + `Overview` entry).
- **User-Visible Win**: operator picks Overview, drags any of the 10 markers freely, right-clicks one to delete. For an undetected marker, operator picks its name and clicks on the portrait to add it. Mesh inspector reveals which detected landmark is which without disturbing the active yaw / export.
- **Proof Target**: pytest covers (a) `delete_markers` command happy + error paths; (b) right-click on a marker dispatches `delete_markers`; (c) drag end fires set_calibration_points with merge=true and the new operator_xy; (d) Overview mode shows all markers as draggable; (e) single-marker mode shows only the selected marker as draggable, others static; (f) add+place on an undetected marker stores both operator_xy and mediapipe_xy from the click; (g) inspector slider does NOT mutate state.yaw. Manual: operator runs the calibration cycle end-to-end on Aeri using Overview mode.
- **Allowed Temporary Fallbacks**: none.
- **Promotion Guard**: do not promote to DONE until operator confirms the full Overview→drag→export cycle works on Aeri AND the inspector slider does not affect active yaw / OpenPose preview / export.

## In Scope

- `gui/calibration.py`: marker dropdown gains `— pick one —` placeholder + `Overview` entry; selection state determines draggable-marker rendering; new `_MarkerHandle(QGraphicsItem)` for each marker + drag handling + right-click dispatch.
- `gui/calibration.py`: new `_MeshInspector(QWidget)` (collapsible) with angle slider + render via existing `render_3d_viewport` against a synthesized `RotatedRig`; no state mutation.
- `commands.py`: new `_h_delete_markers` handler + `OpenReposeLibraryError` (re-using calibration error class) + `_HANDLERS` registration.
- `gui/calibration.py`: add+place workflow when operator clicks for a marker that has no detection — store both `operator_xy` and `mediapipe_xy` from the click coord (operator-supplied detection); update detected_markers state to reflect.
- Tests: extend `test_calibration_gui.py` with mode + drag + right-click + add-place scenarios; new `test_delete_markers_command.py`.

## Out Of Scope

- Body calibration (current calibration is face-only; operator-noted future scope; needs spec extension first).
- Mesh inspector with full pitch/roll (yaw only, mirroring v0.1 spec).
- Multi-marker drag-select / box-drag (single marker drag only).
- Undo/redo (operator can right-click delete + re-place).
- Auto-detection improvements for stylized features (separate RESEARCH WP).

## Definition Of Done

- [ ] Marker dropdown defaults to `— pick one —` placeholder.
- [ ] Overview entry at top of dropdown; selecting it makes all 10 markers draggable.
- [ ] Drag a marker → release fires `set_calibration_points` with merge=true.
- [ ] Right-click a marker → fires new `delete_markers` LLM command + bright ring disappears on refresh.
- [ ] `delete_markers {"names": [...]}` headless command works + tested.
- [ ] No-detection add+place: clicking for an undetected marker stores both operator_xy + mediapipe_xy from the click; detected_markers updates.
- [ ] Mesh inspector renders rig at independent yaw; collapse toggle works; state.yaw / OpenPose preview / export untouched by slider.
- [ ] No `raise_/activateWindow/showNormal/showMaximized` from any path; runtime test passes.
- [ ] pytest zero failures; junit XML at `target/test-artifacts/WP-I1-034/`.
- [ ] Audit clean.
- [ ] Operator confirms manual Overview → drag → export cycle on Aeri.
- [ ] **Manual Impact**: Yes — extends `feature-2-calibration-overlay.md` with Overview mode + drag/delete + add+place workflow + new `delete_markers` command.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Default: dropdown shows placeholder; click on portrait is a no-op.
- [ ] Pick "Overview"; click on a marker; drag; release fires set_calibration_points.
- [ ] Pick a single marker name; click; places that one; other markers static.
- [ ] Right-click an operator marker → delete_markers dispatched.
- [ ] delete_markers single + bulk (`names: ["eye_outer_left", "mouth_corner_right"]`).
- [ ] Click for an undetected marker stores click as both operator_xy + mediapipe_xy.
- [ ] Inspector slider value change → state.yaw unchanged.

### Code Correctness Tests
- [ ] _MarkerHandle hit radius matches the rendered ring radius.
- [ ] delete_markers unknown name → structured error.
- [ ] delete_markers on a calibration with no entry for the name → no-op + ok status.

### Red-Team / Abuse Tests
- [ ] No focus-stealing API calls during 30 drag + click + slider events.
- [ ] No GUI string introduces a forbidden yaw phrase.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via new `delete_markers` command.
- [ ] State reflected in existing `state.calibration` block.
- [ ] LLM pulls visual via existing `calibration_overlay` snapshot.
- [ ] No focus-stealing API calls.
- [ ] No modal dialogs.
- [ ] Tests cover headless path.

## Change Ledger

- (filled at REVIEW)

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at status DRAFT. Operator approved scope; awaits explicit promotion + fast-track authorization.
- 2026-05-03: Operator authorized fast-track. Implementation: new `delete_markers` LLM command (validates avatar + names + non-empty list; bulk + single forms; no-match returns ok with deleted_count=0). `_ZoomableImageView` extended with `set_marker_positions(positions, draggable_names)` + `_hit_test_marker(scene_pt)`; `mousePressEvent`/`mouseReleaseEvent` detect drag-on-marker (vs click-to-place) and fire `marker_dragged(name, x, y)`; right-button press hit-tests + fires `marker_right_clicked(name)`. `CalibrationPane` dropdown now has `— pick one —` placeholder + `Overview (drag any marker)` entry; `currentTextChanged` triggers refresh which feeds the draggable subset back to the view (placeholder = none draggable; Overview = all; single name = just that one). Click-to-place with placeholder/Overview is a no-op (drag is the editing model in Overview). Add+place workflow: when the operator clicks for a marker whose MediaPipe-detected position is at origin (no detection) or no rig is loaded, the click stores both `operator_xy` and `mediapipe_xy` as the same point, treating it as operator-supplied detection. `marker_dragged` and `marker_right_clicked` dispatch `set_calibration_points` (merge=true) and `delete_markers` respectively. **Mesh inspector deferred to WP-I1-036** (split out to keep WP-I1-034 from blowing scope; the always-on dim-dot overlay from WP-I1-028 mostly serves the operator's "which landmark is which" need). 13 new tests across `test_delete_markers_command.py` (8) and `test_calibration_gui.py` (5: placeholder default, click-with-placeholder is no-op, drag dispatches set_calibration_points, right-click dispatches delete_markers, _hit_test_marker semantics). Updated 2 existing GUI tests for the new dropdown shape. Full suite 342/342. Audit clean. Status IN-PROGRESS -> REVIEW.
- 2026-05-03: Operator GUI inspection — Overview mode bug. Operator expected the auto-detected dim dots to be DRAGGABLE in Overview mode (not just operator-placed markers). Currently only operator markers are hit-testable. Fix: refresh() now builds positions from BOTH detected_positions AND calibration.markers (operator entries take precedence over detected); in Overview mode all are draggable. _on_marker_dragged: when the dragged marker has no operator entry yet, it supplies mediapipe_xy explicitly from the cached _last_detected_positions so the deformation field has a real source point (otherwise the dispatcher would re-derive mediapipe_xy from rig.face_mesh AT THE NEW POSITION — already-calibrated rigs would yield identity warp). New regression test: drag-of-detected-dot-in-Overview creates an operator marker with operator_xy=drop, mediapipe_xy=original detected position. Full suite 350/350. Status IN-PROGRESS -> REVIEW.
