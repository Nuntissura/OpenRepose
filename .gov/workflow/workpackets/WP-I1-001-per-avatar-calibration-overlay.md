# WP-I1-001 - Per-Avatar Calibration Overlay

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Last Updated**: 2026-05-02
- **Status**: READY
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

- **Risk**: thin-plate-spline implementation can produce artifacts near image edges. **Mitigation**: clamp deformation to a margin around marked points; default to identity outside that margin.
- **Risk**: per-avatar calibration may need re-marking when MediaPipe model is upgraded. **Mitigation**: store the MediaPipe version + landmark indices used in calibration JSON; warn on mismatch.
- **Dependency**: predecessor `DOCUMENTATION` WP must produce a full Feature 2 spec. Without it, this WP cannot start.

## Definition Of Done

- [ ] `calibration.py` exposes `load`, `save`, `compute_field`, `apply_deformation`, `REQUIRED_MARKERS`, `OPTIONAL_MARKERS`.
- [ ] 4 commands registered in dispatcher; tests cover each (set/dump/clear/get_status, merge vs replace).
- [ ] `state.json` `calibration` block populated per spec "State File Reflection".
- [ ] `calibration_overlay` snapshot target produces a non-empty PNG with marker overlay; composes into `full_window`.
- [ ] GUI Calibration tab functional: click to place, drag to move, right-click to delete, Save/Clear/Re-detect buttons, completeness indicator.
- [ ] `Rig.from_portrait` accepts an optional calibration and applies the TPS field to face + body landmark XY before rotation; identity field used when no calibration loaded.
- [ ] Diagnostic re-run of `probe_facemesh_fidelity.py` on Aeri shows mouth-corners-extend-past-eyes True after calibration is applied. (Promotion Guard.)
- [ ] `pytest .product/tests/test_calibration.py .product/tests/test_calibration_commands.py .product/tests/test_calibration_snapshot.py` zero failures; full project suite still green (>= 111 + new tests).
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] junit XML saved at `target/test-artifacts/WP-I1-001/pytest_results.xml`.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via `set_calibration_points`, `dump_calibration`, `clear_calibration`, `get_calibration_status`.
- [ ] State reflected in `state.json` under a new `calibration` block (active avatar slug, marker count, partial flag).
- [ ] LLM pulls visual via `snapshot {target: "calibration"}`.
- [ ] No `raise_/activateWindow/showNormal/setForegroundWindow` in any code path.
- [ ] No modal dialogs from LLM commands (operator-side click-to-place is interactive, but LLM-driven `set_calibration_points` is non-interactive).
- [ ] Tests cover the headless command path (without launching the GUI).

## Progress Log

- 2026-05-02: WP drafted. Status DRAFT until I0 closes and the predecessor DOCUMENTATION WP authors the Feature 2 spec.
- 2026-05-02: I0 closed; WP-I1-026 (Feature 2 spec) DONE. All predecessors satisfied. Field text aligned with the new spec (algorithm locked to TPS via scipy; snapshot target renamed to `calibration_overlay`; application point moved from `rotation.rotate_yaw` to `Rig.from_portrait` per spec "Application Flow"; commands enumerated; DoD expanded). Status DRAFT -> READY. Operator authorized start; kickoff commit follows.
