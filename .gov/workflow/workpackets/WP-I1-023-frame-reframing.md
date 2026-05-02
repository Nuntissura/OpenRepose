# WP-I1-023 - Frame Reframing (Robust Rerender)

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: REVIEW
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / OpenPose Schema Mapping + Output Formats (extend with frame parameters).

## Intent

Add operator-controlled framing parameters (`frame_scale`, `frame_offset_x`, `frame_offset_y`, optional `frame_anchor`) that re-render the OpenPose output at a different effective framing without changing rig geometry. Implementation is the **robust** path: scale and offset the keypoint coordinates, then re-render the wireframe with `draw_openpose.py` at the same line widths and dot sizes. Naive image-resize is explicitly rejected — line strokes and keypoint dots must stay at the widths DWPose / OpenPoseXL2 was trained on.

Solves the portrait-bias / cropped-feet problem operators hit when image generators default to tight portrait crops. Operator zooms out (`frame_scale < 1.0`) to add black margin around the figure (forces a wider shot); zooms in (`> 1.0`) to fill the frame.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 must reach DONE.
- **Composes With**: WP-I1-022 (read JSON input) — same transform math applies whether keypoints come from a rig or from imported JSON.
- **Successor(s)**: WP-I1-024 (synchronized viewport zoom) — wires this transform into the GUI.

## Reality Boundary

- **Real Seam**: extend `openpose_serialize.serialize` and `draw_openpose.render_openpose` with `frame_scale` (float, default 1.0), `frame_offset` (tuple of int, default (0,0)), and `frame_anchor` (one of `head_anchor` | `canvas_center` | `(x, y)` tuple, default `head_anchor`). Transform per keypoint: `new = (kp - anchor) * frame_scale + anchor + frame_offset`. Canvas size remains operator-chosen. Empty area fills with black (the OpenPose ControlNet expectation).
- **User-Visible Win**: operator drags a "frame" slider; the OpenPose preview updates live; figure shrinks (more black margin) or grows. Exported JSON has scaled keypoints and the same canvas dimensions. Downstream ControlNet generation respects the new framing.
- **Proof Target**: pytest covers each frame parameter independently and combined; manual: render at `frame_scale=0.6` from a tight portrait master, verify the OpenPose preview shows the figure smaller with black margin, run through a downstream ComfyUI workflow and confirm the generation has appropriate framing (legs/feet visible instead of cropped).

## In Scope

- Three new state fields under a `frame` block in `state.json`: `scale` (float), `offset_x` (int), `offset_y` (int). Plus `anchor_mode` (`head_anchor` | `canvas_center` | `custom`) and optional `anchor_point` (tuple).
- New commands: `set_frame_scale`, `set_frame_offset`, `set_frame_anchor`, `reset_frame`.
- Serializer + renderer extensions accepting these parameters.
- Toolbar additions (or new "Frame" tab in the dock) for the frame controls.
- Tests covering: pure scale; pure offset; combined; anchor variants; geometry preserved (line widths constant after re-render); canvas size preserved.

## Out Of Scope

- Per-export-target framing (single export and batch share the same frame params unless explicitly overridden in the command).
- Non-uniform scaling (different x and y scales). Defer.
- Aspect-ratio re-cropping / canvas resize at export time. Defer to a later WP if needed.
- Naive image-resize fallback. Explicitly excluded — robust rerender is the only path.

## Risks And Dependencies

- **Risk**: extreme scales (e.g., 0.1 or 5.0) push keypoints outside the canvas. Document behavior: keypoints with confidence > 0 are still emitted in JSON (some downstream consumers handle off-canvas), but the rendered preview clips to canvas.
- **Risk**: when `frame_scale > 1.0`, keypoints and connecting lines may extend past canvas bounds; the renderer must clip cleanly without crash.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via 4 new commands.
- [ ] State reflected in `state.json` `frame` block.
- [ ] LLM pulls visual via existing `openpose_viewport` snapshot (reflects the frame state).
- [ ] No focus theft / modal dialogs.
- [ ] Tests cover headless path.

## Definition Of Done

- [ ] All 4 commands functional.
- [ ] Toolbar / Frame tab updates state and re-renders the preview live.
- [ ] Round-trip preserves geometry: `scale=1.0, offset=(0,0)` produces output identical to v0.1 baseline.
- [ ] Line widths and dot sizes stay constant across all scales (verifiable by pixel-counting in the rendered PNG).
- [ ] Composes with WP-I1-022: importing a JSON, applying frame, re-exporting works end-to-end.
- [ ] `pytest` zero failures.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / OpenPose Schema Mapping + Output Formats (extend with frame parameters); LLM Control Surface (4 new commands).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (frame commands reachable headlessly; existing snapshot reflects state).

## Linked Test Suite

- `.product/tests/test_frame_reframing.py` (NEW) — pure scale, pure offset, combined; anchor variants; line-width invariance; off-canvas keypoint clipping.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-023-frame-reframing.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — extend OpenPose Schema Mapping + Output Formats with frame parameters; register the 4 new commands.

### Product (`.product/`)

- `.product/src/openrepose/openpose_serialize.py` — accept `frame_scale`, `frame_offset`, `frame_anchor`; transform keypoints before emit.
- `.product/src/openrepose/render/draw_openpose.py` — render at constant line widths regardless of scale; clean clipping.
- `.product/src/openrepose/state.py` — `frame` block (`scale`, `offset_x`, `offset_y`, `anchor_mode`, optional `anchor_point`).
- `.product/src/openrepose/commands.py` — register `set_frame_scale`, `set_frame_offset`, `set_frame_anchor`, `reset_frame`.
- `.product/src/openrepose/gui/toolbar.py` — frame slider + anchor selector (or new "Frame" tab).
- `.product/tests/test_frame_reframing.py` (NEW)

### Build / Output

- `outputs/<avatar-slug>/<run-tag>/` — exports written with the active frame state.
- `target/test-artifacts/WP-I1-023/`

## Risks And Dependencies

- **Risk**: extreme `frame_scale` (e.g., 0.1 or 5.0) pushes keypoints off-canvas; some downstream consumers crash on negative coords. **Mitigation**: emit a WARN when more than 10% of keypoints clip; document behavior in the spec; preserve confidence values regardless.
- **Risk**: line widths and dot sizes drifting with scale would corrupt DWPose / OpenPoseXL2 conditioning. **Mitigation**: dedicated test asserts pixel-counted line widths constant across scales; CI gates promotion on this test.
- **Dependency**: WP-I0-001..004; composes with WP-I1-022 (same transform applies to imported JSON).

## Test Coverage Plan

### Functional Flow Tests
- [ ] `frame_scale=1.0, offset=(0,0)` produces output identical to v0.1 baseline (regression).
- [ ] `frame_scale=0.6` shrinks the figure, black margin appears in the canvas.
- [ ] `frame_offset=(50, -30)` shifts the figure; anchor untouched.
- [ ] `anchor_mode="canvas_center"` keeps canvas-centered anchor under scale.
- [ ] Composes with WP-I1-022: import JSON, apply frame, re-export end-to-end.

### Code Correctness Tests
- [ ] Line widths and dot sizes (pixel-counted) are constant across `frame_scale in {0.5, 1.0, 1.5}`.
- [ ] Round-trip: write -> read -> identical for the `frame` block in state.json.
- [ ] Confidence values preserved even when keypoints land off-canvas.

### Red-Team / Abuse Tests
- [ ] `frame_scale=0`: rejected with structured ERR.
- [ ] `frame_scale=10.0`: accepted but renderer clips cleanly without crash; WARN on >10% clip.
- [ ] `frame_offset` huge integer: accepted; keypoints land off-canvas; renderer clips cleanly.
- [ ] No GUI label introduces a forbidden yaw phrase.

### Performance / Reliability Tests
- [ ] Single-frame re-render under 30ms; 13-angle batch with frame applied within 1.2x of baseline.

## Rollback Plan

- Files to revert: `openpose_serialize.py`, `render/draw_openpose.py`, `state.py`, `commands.py`, `gui/toolbar.py`, the new test file.
- Files to keep: previously exported JSONs (loader tolerates absent `frame` block).
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/openpose_serialize.py .product/src/openrepose/render/draw_openpose.py .product/src/openrepose/state.py .product/src/openrepose/commands.py .product/src/openrepose/gui/toolbar.py .product/tests/test_frame_reframing.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- **What Became Real**:
  - `openpose_schema.py`: `ANCHOR_MODES` (`head_anchor`, `canvas_center`, `custom`), `default_frame()`, `resolve_frame_anchor()`, `apply_frame_to_keypoints(kp_xy, frame, head_anchor_xy, canvas_size)`. Identity fast-path: scale=1 + offset=(0,0) returns input unchanged. Transform: `(kp - anchor) * scale + anchor + offset`.
  - `openpose_serialize.py`: `serialize()` and `serialize_to_string()` accept optional `frame` kwarg; transform applied to body_18 + face_70[:, :2] before flatten. Head anchor pulled from `rotated.head_anchor[:2]`.
  - `render/draw_openpose.py`: `render_openpose()` accepts `frame` kwarg; transform applied to body18 + face70 XY before draw. Line widths and dot sizes are canvas-pixel constants and stay invariant by construction.
  - `state.py`: new `frame` block defaulting to identity (scale=1.0, offset=(0,0), anchor_mode=head_anchor).
  - `commands.py`: 5 new handlers — `set_frame_scale` (positive float; 0 + negative + non-numeric rejected), `set_frame_offset` (numeric x + y), `set_frame_anchor` (mode in ANCHOR_MODES; custom requires point), `reset_frame`, `get_frame`. Export handlers + `_h_snapshot` thread `dict(state.frame)` through.
  - `snapshot.py`: signature gains `frame` kwarg; threaded into `render_openpose` for `openpose_viewport` and `full_window` targets.
  - `gui/options.py`: 4 new signals (`frame_scale_changed`, `frame_offset_changed`, `frame_anchor_changed`, `frame_reset_clicked`). Frame controls in OptionsPane: scale slider (30-200 → 0.30x-2.00x with live label), offset x/y QSpinBox (-2048..2048), anchor QComboBox (head_anchor / canvas_center), Reset frame button. `load_frame()` syncs from state.
  - `gui/main_window.py`: wires the four new signals to dispatch the matching commands. Initial sync via `load_frame()` on construction.
  - `test_frame_reframing.py` (NEW): 30 tests — defaults / anchor modes / resolve_anchor (3 modes + 2 error paths) / transform math (identity / pure scale / pure offset / combined / canvas_center / anchor-invariance under scale) / dispatcher commands (5 happy + error paths) / end-to-end (default baseline / scale=0.5 changes positions / offset translates positions / state block) / line width invariance under scale.
- **What Remains Simulated / Deferred**:
  - Toolbar frame controls (the WP suggested "toolbar additions or new Frame tab"; OptionsPane is the chosen location for now — moving to toolbar can be a polish followup).
  - Per-export-target framing (single + batch share state; spec lists this as Out Of Scope).
  - Non-uniform x/y scaling (Out Of Scope).
  - Composes-with WP-I1-022 (read OpenPose JSON as alternate input) — WP-I1-022 not yet implemented; the frame transform applies regardless of where keypoints came from once it lands.
- **Next Blocking Real Seam**: WP-I1-022 to enable importing OpenPose JSON; WP-I1-024 to wire frame state into 3D viewport / OpenPose preview / reference window for synchronized zoom.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec extension.
2. Implementation: serializer + renderer + state + dispatcher.
3. GUI wiring: frame slider + anchor selector.
4. Verification: pytest + line-width invariance + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_frame_reframing.py --junitxml=target/test-artifacts/WP-I1-023/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-023/pytest_results.xml` plus before/after PNGs at multiple scales archived under that directory.
- **Claim Standard**: never mark `DONE` without junit XML evidence and operator-confirmed downstream generation showing legs/feet visible after `frame_scale<1.0`.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-023/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths (before/after PNGs, downstream confirmation).
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I1-023/pytest_results.xml` — 277 passed, 0 failed (full suite; +30 new from this WP).
- **Local Audit Run**: `pwsh scripts/audit-repo.ps1` exits 0.
- **Build Artifacts**: schema/serializer/renderer/snapshot/state/commands modifications; `gui/options.py` extended with frame controls; `gui/main_window.py` wires the signals; new `test_frame_reframing.py`.
- **Operator Sign-off**: PENDING — operator to verify by adjusting the frame scale slider in Options, exporting, and confirming downstream ControlNet generation (e.g. legs/feet visible at scale=0.6 from a tight portrait). Bundled with the rest of the fast-track batch.

## Progress Log

- 2026-05-02: WP drafted, status DRAFT. Robust rerender approach is the only allowed path; naive image-resize is excluded by spec decision.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
- 2026-05-03: Operator approved fast-track batch (slot 4). Status DRAFT -> IN-PROGRESS. Implementation complete: schema helpers + serializer + renderer + state + 5 commands + Options frame controls + 30 tests. 277/277 passing. Audit clean. Status -> REVIEW.
