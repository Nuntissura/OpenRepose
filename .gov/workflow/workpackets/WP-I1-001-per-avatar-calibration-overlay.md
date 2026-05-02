# WP-I1-001 - Per-Avatar Calibration Overlay

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Last Updated**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: L
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` section "Future Spec Areas / Per-avatar calibration overlay" (placeholder); a `DOCUMENTATION` predecessor WP must promote that section into a full Feature 2 spec block before this WP starts.
- **Linked Test Suite**: `.product/tests/test_calibration.py` (NEW)
- **Linked Check Script**: N/A

## Intent

Add an operator-marked calibration layer that maps MediaPipe FaceMesh's normalized-toward-average landmark positions onto the avatar's actual stylized features. Operator marks N reference points on the master portrait (eye outer corners, mouth corners, jaw corners, optional brow tips); OpenRepose computes a 2D deformation field that warps detected positions to match. The same field is applied to every rotated wireframe so stylized proportions (oversized eyes, extra-wide thin mouth, narrow compact jaw, etc.) stay locked at every yaw angle.

This is the documented mitigation for the WP-I0-003 diagnostic that proved MediaPipe FaceMesh does NOT capture Aeri-style stylized features (eyes detected at ~22% of face width when the actual photo shows them much larger; mouth corners detected within eye-corner verticals when the prompt says they extend past).

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001, WP-I0-002, WP-I0-003, WP-I0-004 (foundation); a `DOCUMENTATION`-class WP that promotes the calibration overlay placeholder in `openrepose_v0_1.md` to a full Feature 2 spec section
- **Successor(s)**: future per-avatar calibration polish WPs
- **Blocks**: any WP that adds new yaw-rotation features which would also benefit from calibration (e.g., pitch/roll)
- **Blocked-By**: I0 must close

## Linked Requirements / Spec Sections

- Project-wide "Headless LLM Operation Rule" in `.gov/AGENTS.md` and `.gov/CODEX.md`
- Future Spec Areas placeholder for "Per-avatar calibration overlay" in `openrepose_v0_1.md`

## Reality Boundary

- **Real Seam**: real operator-marked calibration JSON saved per avatar; real 2D deformation applied to MediaPipe FaceMesh + Pose landmark positions before rotation; rotated wireframes reflect the operator's marks, not MediaPipe's average-face fit.
- **User-Visible Win**: operator marks 6-10 reference points on Aeri's master once. Subsequent batch exports across all 13 yaw angles produce wireframes whose eye outlines, mouth corners, and jaw outline all match Aeri's actual stylized geometry (verified by overlaying the rotated 0deg wireframe back onto the master photo and confirming feature alignment).
- **Proof Target**: a side-by-side overlay of the 0deg wireframe against the master portrait shows eye corners landing within 5px of operator-marked positions and mouth corners landing past the eye-corner verticals. Sampled rotated wireframes (15R, 45R, 90R) maintain the calibration through rotation.
- **Allowed Temporary Fallbacks**: if operator skips marking a feature group (e.g., no brow marks), default to MediaPipe's positions for that group only and label the calibration as `partial` in `state.json`.
- **Promotion Guard**: do not promote the WP to DONE until the diagnostic overlay (`probe_facemesh_fidelity.py`-style script run on Aeri) shows mouth-corners-extend-past-eyes returns True after calibration is applied.

## In Scope

- New `calibration.py` module: persistent JSON store at `outputs/<avatar-slug>/calibration.json`; deformation-field computation (thin-plate spline or piecewise-affine; chosen during the linked DOCUMENTATION WP); apply-deformation function called from `rotation.rotate_yaw` when calibration is loaded for the active avatar.
- 4 new commands wired into the dispatcher: `set_calibration_points` (operator/LLM marks reference points), `dump_calibration`, `clear_calibration`, `get_calibration_status`.
- New snapshot target `calibration` showing the marked reference points overlaid on the master portrait.
- New GUI tab "Calibration" with: master portrait display, click-to-place reference markers, draggable existing markers, MediaPipe-detected positions shown in dim color for comparison, save / clear buttons. Tab is operator-facing only; LLM uses the commands above.
- Tests: round-trip JSON, deformation correctness on a synthetic test (move 3 markers, assert nearby points displace, far points unaffected), end-to-end with the Aeri master.

## Out Of Scope

- 3D calibration (only 2D deformation in this WP).
- Per-feature-group calibration mixing (all marked features go through one deformation field).
- Animated calibration (stays static once marked).

## Risks And Dependencies

- **Risk**: thin-plate-spline implementation can produce artifacts near image edges. **Mitigation**: clamp deformation to a margin around marked points; default to identity outside that margin.
- **Risk**: per-avatar calibration may need re-marking when MediaPipe model is upgraded. **Mitigation**: store the MediaPipe version + landmark indices used in calibration JSON; warn on mismatch.
- **Dependency**: predecessor `DOCUMENTATION` WP must produce a full Feature 2 spec. Without it, this WP cannot start.

## Definition Of Done

- [ ] `calibration.py` exposes `load`, `save`, `apply_deformation` functions.
- [ ] 4 commands registered in dispatcher; tests cover each.
- [ ] `calibration` snapshot target produces a non-empty PNG with marker overlay.
- [ ] GUI Calibration tab functional: click to place, drag to move, save persists across launches.
- [ ] Diagnostic re-run of `probe_facemesh_fidelity.py` on Aeri shows mouth-corner-extends-past-eyes True after calibration.
- [ ] `pytest .product/tests/test_calibration.py` zero failures; full project suite still green.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via `set_calibration_points`, `dump_calibration`, `clear_calibration`, `get_calibration_status`.
- [ ] State reflected in `state.json` under a new `calibration` block (active avatar slug, marker count, partial flag).
- [ ] LLM pulls visual via `snapshot {target: "calibration"}`.
- [ ] No `raise_/activateWindow/showNormal/setForegroundWindow` in any code path.
- [ ] No modal dialogs from LLM commands (operator-side click-to-place is interactive, but LLM-driven `set_calibration_points` is non-interactive).
- [ ] Tests cover the headless command path (without launching the GUI).

## Progress Log

- 2026-05-02: WP drafted. Status DRAFT until I0 closes and the predecessor DOCUMENTATION WP authors the Feature 2 spec.
