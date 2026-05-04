# WP-I1-002 - Orbital Camera In 3D Viewport

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Status**: IN-PROGRESS
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements (existing 3D viewport pane description) — extend with operator-controlled inspection camera.

## Intent

Add operator-controlled orbital camera to the 3D mesh viewport so the operator can rotate the inspection viewpoint independently from the rig's locked yaw rotation. Mouse drag in the viewport orbits the camera; the rig orientation set by the toolbar slider is unchanged. Recorded as a documented fallback in WP-I0-004 (deferred to polish).

## Linked Workpackets

- **Predecessor(s)**: WP-I0-004 must reach DONE.
- **Successor(s)**: none.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-04 | Qt for Python QWidget docs | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html | QWidget exposes `mousePressEvent`, `mouseMoveEvent`, and `mouseReleaseEvent`; implementing orbital drag directly on the viewport widget is the native Qt seam. | adopt |
| 2026-05-04 | Qt for Python QMouseEvent docs | https://doc.qt.io/qtforpython-6/PySide6/QtGui/QMouseEvent.html | QMouseEvent exposes widget-relative pointer position; use position deltas rather than global cursor state so the drag does not depend on OS focus/window position. | adopt |
| 2026-05-04 | Existing OpenRepose snapshot contract | local `.gov/spec/openrepose_v0_1.md` Snapshot Subsystem | LLM `3d_viewport` snapshots must stay deterministic; operator orbital camera state is GUI-only and must not affect the snapshot renderer. | adopt |

## Reality Boundary

- **Real Seam**: extend `render/draw_3d.py` with `camera_yaw_deg` and `camera_pitch_deg` arguments that rotate the world points before projection. Wire mouse events in `gui/viewport_3d.py` to update camera state and redraw.
- **User-Visible Win**: operator drags inside the 3D viewport with left button held; the wireframe rotates in space, separate from the rig's yaw bin.
- **Proof Target**: pytest-qt drag-event simulation produces different rendered images than no-drag baseline; operator-confirmed manual smoke shows smooth orbital motion.

## In Scope

- Camera state on `Viewport3D` widget: `camera_yaw_deg`, `camera_pitch_deg` (clamped to ±89° to avoid gimbal flip).
- Mouse handlers: press, move, release. Wheel optional (zoom — defer to polish if non-trivial).
- Extension to `render_3d_viewport()` taking optional camera params.
- Tests: camera state changes on simulated drag; rendered image differs.

## Out Of Scope

- Translation / pan / zoom (defer if needed).
- Saving camera position across launches.
- Affecting snapshot 3D viewport (snapshots stay at canonical camera so LLM gets a deterministic image).

## Headless LLM Operation Compliance

- [x] N/A — non-LLM-facing polish. The LLM-side snapshot of `3d_viewport` keeps the canonical camera. Operator orbital camera is a GUI-only convenience.

## Definition Of Done

- [ ] Mouse drag rotates the 3D viewport image in real time.
- [ ] Snapshot output for `3d_viewport` is unaffected by operator's orbital camera state.
- [ ] pytest-qt suite covers drag → camera state change → render delta.
- [ ] **Manual Impact**: Yes - extends `.gov/doc/manual/feature-1-yaw-exporter.md` with the distinction between rig yaw and GUI-only orbital inspection camera.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / GUI Requirements (3D viewport pane).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (this WP is GUI-only convenience; LLM-facing snapshot keeps canonical camera).

## Linked Test Suite

- `.product/tests/test_orbital_camera.py` (NEW) — pytest-qt drag simulation, render-delta, snapshot-canonical-camera assertion.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-002-orbital-camera-3d-viewport.md` (this file)
- `.gov/workflow/TASKBOARD.md`

### Product (`.product/`)

- `.product/src/openrepose/render/draw_3d.py` — extend `render_3d_viewport()` to accept optional `camera_yaw_deg`, `camera_pitch_deg`.
- `.product/src/openrepose/gui/viewport_3d.py` — add `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`; clamp pitch ±89°.
- `.product/tests/test_orbital_camera.py` (NEW)

### Build / Output

- `target/test-artifacts/WP-I1-002/`

## Risks And Dependencies

- **Risk**: gimbal-flip near ±90° pitch produces visual jitter. **Mitigation**: hard-clamp `camera_pitch_deg` to ±89°; add a unit test asserting the clamp.
- **Risk**: operator confuses orbital camera with rig yaw and thinks export changed. **Mitigation**: status-bar caption distinguishes "view camera" from "rig yaw"; snapshot subsystem ignores orbital camera (canonical-camera-only).
- **Dependency**: WP-I0-004 (GUI scaffold + `render_3d_viewport` wiring) must be DONE.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Simulated left-button drag rotates the rendered image.
- [ ] Releasing button leaves camera at the dragged orientation.

### Code Correctness Tests
- [ ] `camera_pitch_deg` clamps at ±89° regardless of cumulative drag.
- [ ] `render_3d_viewport(camera_yaw_deg=0, camera_pitch_deg=0)` is byte-identical to the WP-I0-004 baseline.
- [ ] Setting any orbital camera state has no effect on `snapshot {target: "3d_viewport"}` output.

### Red-Team / Abuse Tests
- [ ] LLM `set_yaw_bin` while operator drags orbital camera: rig orientation updates, operator's camera state preserved.
- [ ] No forbidden yaw phrase introduced anywhere in new code or UI text.

### Performance / Reliability Tests
- [ ] 60Hz drag for 30s produces no dropped frames or memory growth.

## Rollback Plan

- Files to revert: `render/draw_3d.py`, `gui/viewport_3d.py`.
- Files to keep: `target/test-artifacts/WP-I1-002/` if any partial evidence is useful.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/render/draw_3d.py .product/src/openrepose/gui/viewport_3d.py .product/tests/test_orbital_camera.py`

## Decisions Log

- 2026-05-04: Keep orbital camera GUI-only; no command/state surface. Reason: it is an inspection convenience, while LLM snapshots need deterministic canonical camera output.

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- 2026-05-04: Promoted DRAFT -> IN-PROGRESS for autonomous implementation after filtering out operator-preference/release-gated WPs. Research notes and manual-impact line added before product edits.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row.
2. Implementation: `render/draw_3d.py` camera math.
3. GUI wiring: `gui/viewport_3d.py` mouse handlers + state.
4. Verification: pytest results + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_orbital_camera.py --junitxml=target/test-artifacts/WP-I1-002/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-002/pytest_results.xml`
- **Claim Standard**: never mark `DONE` without the junit XML committed and a manual smoke confirming the snapshot-canonical-camera invariant.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-002/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: marked N/A with reason (GUI-only polish; LLM snapshot keeps canonical camera).

## Evidence

- 2026-05-04: Promoted DRAFT -> IN-PROGRESS; governance kickoff prepared before `.product/` edits.

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
- 2026-05-04: Status DRAFT -> IN-PROGRESS; implementation authorized by operator for autonomous overnight work.
