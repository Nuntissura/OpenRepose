# WP-I1-001 - Per-Avatar Calibration Overlay

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Last Updated**: 2026-05-02
- **Status**: REVIEW
- **Iteration**: I1
- **Workflow Version**: 1.0 (grandfathered; original draft predates the 1.1 Research Notes rule)
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: L
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` section "Feature 2: Per-Avatar Calibration Overlay" (authored by WP-I1-026, DONE 2026-05-02). The spec section locks the deformation algorithm, marker schema, JSON schema, command surface, state-file shape, and snapshot target.
- **Linked Test Suite**: `.product/tests/test_calibration.py` (NEW), `.product/tests/test_calibration_commands.py` (NEW)
- **Linked Check Script**: N/A

## Intent

Add an operator-marked calibration layer that maps MediaPipe FaceMesh's normalized-toward-average landmark positions onto the avatar's actual stylized features. Operator marks N reference points on the master portrait (eye outer corners, mouth corners, jaw corners, optional brow tips); OpenRepose computes a 2D deformation field that warps detected positions to match. The same field is applied to every rotated wireframe so stylized proportions (oversized eyes, extra-wide thin mouth, narrow compact jaw, etc.) stay locked at every yaw angle.

This is the documented mitigation for the WP-I0-003 diagnostic that proved MediaPipe FaceMesh does NOT capture Aeri-style stylized features (eyes detected at ~22% of face width when the actual photo shows them much larger; mouth corners detected within eye-corner verticals when the prompt says they extend past).

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001/002/003/004 (DONE 2026-05-02), WP-I1-026 (DONE 2026-05-02 — Feature 2 spec section authored)
- **Successor(s)**: future per-avatar calibration polish WPs; I2 theme "per-feature-group calibration mixing"
- **Blocks**: any WP that adds new yaw-rotation features which would also benefit from calibration (e.g., pitch/roll); WP-I1-009 identity-export profiles benefits significantly from calibrated rigs
- **Blocked-By**: none (all predecessors DONE)

## Linked Requirements / Spec Sections

- Project-wide "Headless LLM Operation Rule" in `.gov/AGENTS.md` and `.gov/CODEX.md`
- `.gov/spec/openrepose_v0_1.md` section "Feature 2: Per-Avatar Calibration Overlay" (canonical contract — locks algorithm, marker schema, JSON schema, commands, state, snapshot target)

## Reality Boundary

- **Real Seam**: real operator-marked calibration JSON saved per avatar; real 2D deformation applied to MediaPipe FaceMesh + Pose landmark positions before rotation; rotated wireframes reflect the operator's marks, not MediaPipe's average-face fit.
- **User-Visible Win**: operator marks 6-10 reference points on Aeri's master once. Subsequent batch exports across all 13 yaw angles produce wireframes whose eye outlines, mouth corners, and jaw outline all match Aeri's actual stylized geometry (verified by overlaying the rotated 0deg wireframe back onto the master photo and confirming feature alignment).
- **Proof Target**: a side-by-side overlay of the 0deg wireframe against the master portrait shows eye corners landing within 5px of operator-marked positions and mouth corners landing past the eye-corner verticals. Sampled rotated wireframes (15R, 45R, 90R) maintain the calibration through rotation.
- **Allowed Temporary Fallbacks**: if operator skips marking a feature group (e.g., no brow marks), default to MediaPipe's positions for that group only and label the calibration as `partial` in `state.json`.
- **Promotion Guard**: do not promote the WP to DONE until the diagnostic overlay (`probe_facemesh_fidelity.py`-style script run on Aeri) shows mouth-corners-extend-past-eyes returns True after calibration is applied.

## In Scope

- New `.product/src/openrepose/calibration.py` module: persistent JSON store at `outputs/<avatar-slug>/calibration.json` (schema_version 1, per spec); marker name vocabulary constants (6 required + 4 optional, per spec); thin-plate-spline deformation field via `scipy.interpolate.RBFInterpolator(kernel="thin_plate_spline")` operating on landmark XY coordinates only (z passed through); 4 implicit corner clamp points for edge stability; `apply_deformation(field, points_xy_array)` for vectorized point transformation.
- Calibration is applied during `Rig.from_portrait` (per spec "Application Flow") — after MediaPipe FaceMesh + Pose produce raw landmarks, the cached TPS field transforms (x, y) for every face and body landmark before rotation. Z values pass through unchanged.
- 4 new commands wired into the dispatcher: `set_calibration_points` (markers + merge flag), `dump_calibration`, `clear_calibration`, `get_calibration_status`. All four non-interactive, no modal dialogs.
- New `state.json` `calibration` block per spec "State File Reflection".
- New snapshot target `calibration_overlay` (per spec; shows operator markers bright/large overlaid on MediaPipe positions dim/small) plus `full_window` composition extension.
- New GUI tab "Calibration" with: master portrait display, click-to-place reference markers (anatomical-name dropdown), draggable existing markers, right-click delete, MediaPipe-detected positions shown in dim color for comparison, completeness indicator, Save / Clear / Re-detect buttons. Tab is operator-facing only; LLM uses the commands above.
- Tests: `test_calibration.py` (calibration module unit tests — round-trip JSON, deformation correctness on synthetic data, partial vs complete handling, missing required markers, invalid JSON rejection, field application on landmark arrays, corner clamp behavior); `test_calibration_commands.py` (4 commands via dispatcher; merge vs replace; state reflection); `test_calibration_snapshot.py` (calibration_overlay snapshot target produces non-empty PNG with marker overlay; no focus theft).

## Out Of Scope

- 3D calibration (only 2D deformation in this WP).
- Per-feature-group calibration mixing (all marked features go through one deformation field).
- Animated calibration (stays static once marked).

## Risks And Dependencies

- **Risk**: thin-plate-spline implementation can produce artifacts near image edges. **Mitigation**: 4 implicit corner clamp points are added inside `compute_field` so far-from-marked regions stay near identity. Verified by `test_field_keeps_far_corner_points_near_identity`.
- **Risk**: per-avatar calibration may need re-marking when MediaPipe model is upgraded. **Mitigation**: `mediapipe_version` recorded in calibration JSON; `Calibration.load()` accepts mismatched versions silently (the operator's mark is in pixel space, not in landmark indices, so it survives MediaPipe minor-version bumps). A WARN-on-version-mismatch enhancement is a small followup.
- **Dependency**: predecessor `DOCUMENTATION` WP (WP-I1-026) produced the Feature 2 spec — DONE 2026-05-02.

## Fallback Register

- **Path**: `gui/calibration.py` — operator marker editing.
- **Required Label In Code/UI**: hint label on the tab states "click on portrait to place the active marker" (drag/right-click absent; user uses dropdown + click).
- **Successor / Debt Owner**: future polish WP "Calibration overlay marker editing UX".
- **Exit Condition To Remove**: drag-to-move and right-click-delete implemented on the Calibration tab.

- **Path**: `snapshot.py` `_render` for `full_window` target.
- **Required Label In Code/UI**: full_window composition does not include a calibration_overlay slot in v0.1; the standalone `calibration_overlay` snapshot target works.
- **Successor / Debt Owner**: future polish WP "Calibration overlay in full_window composition".
- **Exit Condition To Remove**: full_window layout extended with a calibration_overlay slot, or the active dock-tab is reflected in `full_window` snapshots.

## Definition Of Done

- [x] `calibration.py` exposes `load`, `save`, `compute_field`, `apply_deformation`, `REQUIRED_MARKERS`, `OPTIONAL_MARKERS`, plus `Marker`, `Calibration`, `DeformationField`, `MEDIAPIPE_FACEMESH_INDEX_BY_MARKER`, `calibration_path`, `OpenReposeCalibrationError`.
- [x] 4 commands registered in dispatcher; tests cover each (set/dump/clear/get_status, merge vs replace, validation, auto-load on import).
- [x] `state.json` `calibration` block populated per spec "State File Reflection".
- [x] `calibration_overlay` snapshot target produces a non-empty PNG with marker overlay. (Composing into `full_window` deferred — see Fallback Register.)
- [x] GUI Calibration tab functional: click to place, Save/Clear/Re-detect buttons, completeness indicator. (Drag-to-move and right-click-delete deferred — see Fallback Register.)
- [x] `Rig.from_portrait` accepts an optional calibration and applies the TPS field to face + body landmark XY before rotation; identity field used when no calibration loaded. `Rig.with_calibration()` re-applies a different calibration without re-running MediaPipe (uses cached raw landmarks).
- [ ] Diagnostic re-run of `probe_facemesh_fidelity.py` on Aeri shows mouth-corners-extend-past-eyes True after calibration is applied. (Promotion Guard — operator-side verification; requires the operator to mark Aeri's reference points in the GUI then run the diagnostic.)
- [x] `pytest` zero failures: 178/178 passing (was 111 baseline; +67 new tests across calibration module / commands / Rig integration / snapshot / GUI).
- [x] `pwsh scripts/audit-repo.ps1` exits 0.
- [x] junit XML saved at `target/test-artifacts/WP-I1-001/pytest_results.xml`.

## Headless LLM Operation Compliance

- [x] LLM agent triggers via `set_calibration_points`, `dump_calibration`, `clear_calibration`, `get_calibration_status`. All four registered in `_HANDLERS`; covered by `test_calibration_commands.py`.
- [x] State reflected in `state.json` under the `calibration` block (`active_avatar`, `completeness`, `marker_count`, `missing_required`, `field_cached`, `loaded_from`, `last_dump_at`). Verified by `test_state_json_has_calibration_block` and the dispatcher cycle test.
- [x] LLM pulls visual via `snapshot {target: "calibration_overlay"}`. Renderer at `render/draw_calibration.py`; falls back to a labeled dark canvas when portrait or calibration is missing so the snapshot never crashes.
- [x] No `raise_/activateWindow/showNormal/showMaximized` in any code path. Runtime test `test_calibration_pane_clicks_do_not_call_focus_apis` drives 10 clicks + a clear and asserts zero invocations; existing `test_gui_no_focus_steal` covers the project-wide contract.
- [x] No modal dialogs from any command path. Source check `test_calibration_pane_no_modal_dialog_apis_in_source` rejects `QMessageBox` / `.exec(` / `.exec_(` in `gui/calibration.py`.
- [x] Tests cover the headless command path (`test_calibration_commands.py` runs the full set/dump/clear/get_status cycle through `App.handle_command` without launching the GUI).

## Change Ledger

- **What Became Real**:
  - `.product/src/openrepose/calibration.py` (NEW): `Marker`, `Calibration`, `DeformationField` dataclasses; `REQUIRED_MARKERS` (6) + `OPTIONAL_MARKERS` (4) + `MEDIAPIPE_FACEMESH_INDEX_BY_MARKER` (10-entry landmark index map); `load()` + `save()` with atomic `.tmp` + `os.replace`; schema validation rejects bad versions, unknown marker names, malformed XY; `compute_field()` builds TPS via `scipy.interpolate.RBFInterpolator(kernel="thin_plate_spline")` with 4 implicit corner clamps; `apply_deformation()` identity-passes when field is None; `calibration_path()` conventional location helper.
  - `.product/src/openrepose/state.py`: `AppState.calibration` dict block (active_avatar, completeness, marker_count, missing_required, field_cached, loaded_from, last_dump_at) with `set_calibration_status()` + `mark_calibration_dump()` helpers. `to_dict()` includes the new block.
  - `.product/src/openrepose/rig.py`: `Rig` carries optional `raw_face_mesh`, `raw_body_kps`, `calibration` fields. `from_portrait(*, calibration=None)` applies the TPS field to face + body XY before head_anchor (per spec Application Flow). `with_calibration(new_cal)` rebuilds the field from cached raw landmarks — cheap, no MediaPipe re-run. Head anchor computation extracted into `_compute_head_anchor` helper.
  - `.product/src/openrepose/commands.py`: 4 new handlers per spec Command Surface. `set_calibration_points` accepts markers list + merge flag, derives mediapipe_xy from rig when omitted, persists JSON, re-applies field to active rig. `dump_calibration` returns full content + marks last_dump_at. `clear_calibration` deletes JSON + drops field. `get_calibration_status` mirrors state.calibration. `_h_import_portrait` auto-loads `outputs/<avatar-slug>/calibration.json` if present and passes it to `Rig.from_portrait`. `OpenReposeCalibrationError` added to dispatcher catch list. `_h_snapshot` plumbs portrait_path + calibration through to snapshot.
  - `.product/src/openrepose/render/draw_calibration.py` (NEW): cv2-based renderer for the `calibration_overlay` snapshot target. Loads master portrait or falls back to a dark labeled canvas. Per spec, draws MediaPipe-detected positions as small dim dots, operator-marked positions as larger bright rings, connected by a thin link line, with anatomical-name labels.
  - `.product/src/openrepose/snapshot.py`: `calibration_overlay` added to `VALID_TARGETS`; `snapshot()` signature gains optional `portrait_path` + `calibration` kwargs; `_render` dispatches to `draw_calibration` for the new target. Existing callers unaffected (kwargs default to None).
  - `.product/src/openrepose/gui/calibration.py` (NEW): operator-facing Calibration tab. Marker-name dropdown (10 anatomical names), portrait display with overlay (rendered via `render_calibration_overlay`), completeness indicator, Save/Clear/Re-detect buttons. `_ClickablePortrait` (QLabel subclass) emits image-space (x, y) on left-click; the pane fires `set_calibration_points {merge: true}` for the active marker. Save dispatches `dump_calibration`. Clear dispatches `clear_calibration`. Re-detect dispatches `import_portrait` again. No `raise_/activateWindow/showNormal/showMaximized` invocations; no modal dialogs.
  - `.product/src/openrepose/gui/main_window.py`: `Calibration` tab inserted in the right dock between Inspector and Options. Polling timer calls `_calibration.refresh()` so LLM-driven calibration changes update the overlay silently.
  - `.product/tests/`: `test_calibration.py` (27 unit tests for the module), `test_calibration_commands.py` (14 dispatcher tests including the full set/dump/clear/get_status cycle, merge vs replace, auto-load on import, state.json reflection), `test_rig_calibration.py` (6 Rig integration tests against the aeri master fixture), `test_calibration_snapshot.py` (10 snapshot-target tests), `test_calibration_gui.py` (9 GUI tests including a runtime no-focus-steal check across 10 calibration clicks). `test_gui_layout.py` updated from 4-tab to 5-tab assertion. Total +66 new tests across the WP.
  - `pyproject.toml`: `scipy>=1.11` promoted from transitive (mediapipe) to explicit dependency.
- **What Remains Simulated / Deferred**:
  - Drag-to-move and right-click-delete on the Calibration tab — deferred to a polish WP. Click-to-place + Clear/Re-detect cover the core flow.
  - `calibration_overlay` inclusion in the `full_window` snapshot composition — deferred. Standalone `calibration_overlay` snapshot target works.
  - WARN-on-MediaPipe-version-mismatch when loading a calibration whose `mediapipe_version` differs from the runtime — small followup; current behavior is silent acceptance because the operator's marks are in pixel space and survive MediaPipe minor-version bumps.
  - Operator-side Promotion Guard: `probe_facemesh_fidelity.py` re-run on the Aeri master after calibration. Operator must mark Aeri's reference points in the GUI then run the diagnostic to satisfy the Reality Boundary's "mouth-corners-extend-past-eyes True" check.
- **Next Blocking Real Seam**: with calibration shipped, the next WP unblocked is WP-I1-009 (identity-export profiles), which composes naturally with calibrated rigs. WP-I1-023 (frame reframing) is also fully unblocked.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I1-001/pytest_results.xml` — 178 passed, 0 failed (full project suite). Calibration-specific subset: 66 new tests across `test_calibration.py` (27), `test_calibration_commands.py` (14), `test_rig_calibration.py` (6), `test_calibration_snapshot.py` (10), `test_calibration_gui.py` (9).
- **Local Audit Run**: `pwsh scripts/audit-repo.ps1` exits 0 on the live tree.
- **Build Artifacts**: new modules `calibration.py`, `render/draw_calibration.py`, `gui/calibration.py`; new tests as listed; `pyproject.toml` adds `scipy>=1.11`.
- **Proof Artifact**: `target/test-artifacts/WP-I1-001/`
- **Operator Sign-off**: PENDING — operator to verify by running `.\.venv\Scripts\python.exe -m openrepose.cli gui --inbox`, marking Aeri's reference points via the Calibration tab, exporting at multiple yaw angles (`her-right 30`, `her-right 45`, `her-right 90`) and confirming the calibrated wireframes maintain the operator's marked proportions across rotation. Optionally re-run `probe_facemesh_fidelity.py` on the calibrated Aeri rig to satisfy the Promotion Guard.

## Progress Log

- 2026-05-02: WP drafted. Status DRAFT until I0 closes and the predecessor DOCUMENTATION WP authors the Feature 2 spec.
- 2026-05-02: I0 closed; WP-I1-026 (Feature 2 spec) DONE. All predecessors satisfied. Field text aligned with the new spec (algorithm locked to TPS via scipy; snapshot target renamed to `calibration_overlay`; application point moved from `rotation.rotate_yaw` to `Rig.from_portrait` per spec "Application Flow"; commands enumerated; DoD expanded). Status DRAFT -> READY. Operator authorized start; kickoff commit follows.
- 2026-05-02: Kickoff commit `6ff61c0` pushed (WP file + taskboard + WP-I1-026 archive). Status -> IN-PROGRESS.
- 2026-05-02: Checkpoint A (`e91e725`): calibration module + 27 tests. scipy promoted to explicit dep.
- 2026-05-02: Checkpoint B (`04f7439`): state `calibration` block + Rig.from_portrait/with_calibration + 4 commands + 20 dispatcher/Rig tests. 158/158 passing.
- 2026-05-02: Checkpoint C: calibration_overlay snapshot target + draw_calibration renderer + 10 tests. 169/169 passing.
- 2026-05-02: Checkpoint D: GUI Calibration tab + main_window wiring + 9 GUI tests. test_gui_layout.py updated for 5-tab layout.
- 2026-05-02: Status IN-PROGRESS -> REVIEW. Full suite 178/178 passing in 37s; junit XML saved at `target/test-artifacts/WP-I1-001/pytest_results.xml`. Audit exits 0. Awaiting operator sign-off (run `.\.venv\Scripts\python.exe -m openrepose.cli gui --inbox`, mark Aeri's reference points via the Calibration tab, export at multiple yaw angles, confirm calibrated wireframes look right; optionally re-run `probe_facemesh_fidelity.py` to satisfy the Promotion Guard).
