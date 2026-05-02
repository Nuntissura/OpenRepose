# WP-I0-001 - Rig And Rotation Core

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Last Updated**: 2026-05-02
- **Status**: DONE
- **Iteration**: I0
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` sections "Application-Wide Conventions / Yaw Terminology Lock", "Application-Wide Conventions / Output Formats", "Feature 1 / Rig Construction", "Feature 1 / Rotation", "Feature 1 / Projection", "Feature 1 / OpenPose Schema Mapping"
- **Linked Test Suite**: `.product/tests/test_rig.py`, `.product/tests/test_rotation.py`, `.product/tests/test_openpose_serialize.py`
- **Linked Check Script**: `N/A` (use `pytest` invocation)

## Intent

Build the headless core of OpenRepose: load a frontal portrait, fit a locked 3D rig from MediaPipe FaceMesh + MediaPipe Pose, rotate the rig rigidly about its vertical axis, and serialize the rotated rig to OpenPose-format JSON matching the schema OpenPoseXL2 was trained on. No GUI, no LLM control surface, no snapshot subsystem yet — just a clean Python module that takes `(portrait_path, yaw_value_deg)` and writes one OpenPose JSON file. Tests verify rig fit on a real portrait and rotation produces sensible JSON across angle bins.

## Linked Workpackets

- **Predecessor(s)**: none
- **Successor(s)**: WP-I0-002, WP-I0-003, WP-I0-004
- **Blocks**: WP-I0-002, WP-I0-003, WP-I0-004
- **Blocked-By**: none
- **Related**: none

## Linked Requirements / Spec Sections

- Yaw Terminology Lock (`her-left N` / `her-right N` / `0` only; forbidden phrases banned)
- Output Formats (OpenPose JSON schema: `people[].pose_keypoints_2d` 18*3, `face_keypoints_2d` 70*3, `hand_left_keypoints_2d` null, `hand_right_keypoints_2d` 21*3 zeros, `canvas_width`, `canvas_height`)
- Rig Construction (MediaPipe FaceMesh 478, MediaPipe Pose 33, anchored at neck, locked rigid object)
- Rotation (rigid yaw about y-axis through neck point; pitch/roll out of scope for v0.1)
- Projection (orthographic default, perspective optional with focal-length parameter)
- OpenPose Schema Mapping (478 face -> 70 face indices; 33 body -> 18 body indices, body_18 schema)

## Reality Boundary

- **Real Seam**: real MediaPipe FaceMesh + MediaPipe Pose detection on a real portrait, real 3D rotation matrix math, real OpenPose JSON serialization. No synthetic z values, no flat-z body shortcuts. Both face and body get real measured 3D depth.
- **User-Visible Win**: an operator (or LLM) can call `python -m openrepose.cli render --portrait <path> --yaw "her-right 30" --out outputs/test.json` and get a valid OpenPose JSON file at the right schema, openable in `RenderPeopleKps` to produce a wireframe PNG.
- **Proof Target**: pytest suite passes; one manual run produces `outputs/test/aeri_yaw_her-right-30.json` that, when fed through `RenderPeopleKps` in ComfyUI, draws a head turned to image-right with anatomical-right side visible.
- **Allowed Temporary Fallbacks**: hip/elbow/wrist body keypoints may default to zero confidence if MediaPipe Pose can't detect them on bust portraits (which is the usual case). Document in the rig dump.
- **Promotion Guard**: fallbacks are tolerable as long as the visible-in-the-master keypoints (nose, neck, shoulders, ears, eyes) all carry real measured z. If any of those drop to synthetic z, fail the WP.

## In Scope

- `.product/src/openrepose/rig.py` — `Rig` class with `face_mesh`, `body_kps`, `head_anchor`, `fit_metrics`. Constructor takes a portrait path; runs MediaPipe FaceMesh and Pose; stores measured 3D landmarks.
- `.product/src/openrepose/rotation.py` — `rotate_yaw(rig, value_deg) -> RotatedRig` pure function. Rigid y-axis rotation through neck anchor. Includes orthographic projection to 2D + per-keypoint visibility computation.
- `.product/src/openrepose/openpose_schema.py` — index map from MediaPipe 478 face to OpenPose 70; from MediaPipe Pose 33 body to OpenPose body_18. Documented inline.
- `.product/src/openrepose/openpose_serialize.py` — `serialize(rotated_rig, canvas_w, canvas_h) -> dict` returning the JSON schema. Visibility decisions reflected in confidences (0.0 for hidden).
- `.product/src/openrepose/yaw_bin.py` — yaw bin <-> degree conversion utilities. The `0`, `her-left N`, `her-right N` strings are the canonical bins; degree values are derived. Forbidden phrase detection raises on the banned strings.
- `.product/src/openrepose/cli.py` — minimal CLI entry point with `render` subcommand. Headless. Used for tests and for the operator's first manual run.
- `.product/tests/test_rig.py` — fits the rig on a fixture portrait, asserts face count == 478 (or whatever MediaPipe returns at the pinned version), body count == 33, neck anchor coordinates within expected bounds.
- `.product/tests/test_rotation.py` — rotates the rig at 0, ±15, ±45, ±90; asserts nose-x increases monotonically with positive yaw, anatomical-right shoulder gets closer to camera at positive yaw.
- `.product/tests/test_openpose_serialize.py` — serializes at multiple angles; asserts schema validity (key names, array lengths, canvas fields), asserts visibility cull is consistent with the rotation direction.
- `.product/tests/fixtures/aeri_master_640.png` — small fixture portrait for tests (operator-provided or synthetic).
- `pyproject.toml` at repo root — declares the `openrepose` package, dev dependencies (pytest, mypy, ruff), and runtime dependencies (mediapipe, numpy, opencv-python, pillow). Under v0.1 we use mediapipe even though the user originally also installed pyrender; pyrender comes in WP-I0-003.

## Out Of Scope

- GUI of any kind.
- LLM control surface (HTTP, file-watch, command schema).
- Snapshot subsystem.
- ComfyUI integration; the JSON output is meant to be loadable by `RenderPeopleKps` but this WP doesn't run ComfyUI.
- Pitch / roll rotation.
- Multi-subject portraits.
- Performance tuning beyond what falls out for free.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I0-001-rig-and-rotation-core.md` (this file)
- `.gov/workflow/TASKBOARD.md` (status updates)

### Product (`.product/`)

- `.product/src/openrepose/__init__.py` (version bump to 0.1.0-dev0)
- `.product/src/openrepose/rig.py` (NEW)
- `.product/src/openrepose/rotation.py` (NEW)
- `.product/src/openrepose/openpose_schema.py` (NEW)
- `.product/src/openrepose/openpose_serialize.py` (NEW)
- `.product/src/openrepose/yaw_bin.py` (NEW)
- `.product/src/openrepose/cli.py` (NEW)
- `.product/tests/conftest.py` (NEW)
- `.product/tests/test_rig.py` (NEW)
- `.product/tests/test_rotation.py` (NEW)
- `.product/tests/test_openpose_serialize.py` (NEW)
- `.product/tests/fixtures/aeri_master_640.png` (NEW; 640px-wide fixture)

### Build / Output

- `pyproject.toml` (NEW; repo root)
- `target/test-artifacts/WP-I0-001/` (pytest junit, evidence)

## Risks And Dependencies

- **Risk**: MediaPipe Pose on a tight bust portrait sometimes fails to detect. **Mitigation**: pin the FaceMesh fallback to provide head-region body keypoints (nose, eyes, ears) when Pose fails; document the fallback in the rig dump and the WP Change Ledger.
- **Risk**: MediaPipe version drift breaks landmark indices. **Mitigation**: pin `mediapipe` version in `pyproject.toml`; tests assert landmark counts to catch drift early.
- **Dependency**: a fixture frontal portrait. **Owner**: operator. **Status**: pending — operator to provide or assistant generates a synthetic test fixture.

## Definition Of Done

- [ ] `pyproject.toml` declares the package; `pip install -e .[dev]` succeeds.
- [ ] `from openrepose.rig import Rig` works in a fresh interpreter.
- [ ] `Rig("path/to/master.png")` returns a Rig with `face_mesh` (478,3), `body_kps` (33,3 with confidences), and `head_anchor` (3,) attributes.
- [ ] `rotate_yaw(rig, -30.0)` returns a RotatedRig where the nose has moved to image-right relative to the neck anchor (verified by test assertion).
- [ ] `serialize(rotated_rig, 1024, 1280)` returns a dict matching the OpenPose schema described in the spec.
- [ ] `python -m openrepose.cli render --portrait <fixture> --yaw "her-right 30" --out outputs/test.json` produces a valid file.
- [ ] `pytest .product/tests` returns zero failures.
- [ ] One produced JSON, when fed through ComfyUI's `RenderPeopleKps` (manually verified by operator), draws a head turned to image-right with the anatomical-right side visible.
- [ ] No use of forbidden phrases (`image-left`, `image-right`, `viewer-left`, `viewer-right`, `left view`, `right view`) in any source file. Verified by a grep check listed in the test suite.
- [ ] `target/test-artifacts/WP-I0-001/pytest_results.xml` saved.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Fit rig on fixture portrait; assert landmark counts and anchor coordinates.
- [ ] Rotate at 0, +15, +45, +90, -15, -45, -90; assert nose-x trajectory monotonic.
- [ ] Serialize at each angle; assert schema validity and array lengths.

### Code Correctness Tests
- [ ] yaw_bin string parser accepts `0`, `her-left 15`, `her-right 90`; rejects forbidden phrases.
- [ ] yaw_bin -> degree conversion is reversible.
- [ ] openpose_schema index map is bijective on the relevant subset (478 -> 70, 33 -> 18).
- [ ] openpose_serialize output passes JSON Schema validation against a schema file checked in.

### Red-Team / Abuse Tests
- [ ] yaw_bin parser raises a typed exception on `image-left`, `viewer-right`, `left view`, `right view`, or any other forbidden phrase. Exception type is `OpenReposeForbiddenTerminologyError`.
- [ ] Rig fit on a non-portrait image (no face detected) raises a typed exception, not a silent zero-keypoint Rig.
- [ ] CLI rejects out-of-range yaw values (e.g. `--yaw 200`) with a non-zero exit code and an `ERR` log line.

### Performance / Reliability Tests
- [ ] Rig fit on a 1024x1024 portrait completes in under 5 seconds on the test machine (sanity, not gating).

## Rollback Plan

- Files to revert: all NEW files listed under Expected Files Touched.
- Files to keep: this WP file (move to archive with status `CANCELLED` instead of deleting).
- Recovery command: `git restore --staged .product/ pyproject.toml; git checkout -- .product/ pyproject.toml`.

## Decisions Log

- `2026-05-02`: chose MediaPipe FaceMesh + MediaPipe Pose as the rig source for v0.1. Reason: both run on CPU, no GPU dependency, both already proven on the master portrait. Alternatives considered: FLAME (heavier setup, license review), 3DDFA_V2 (license-blocked). Decision can be revisited in a later WP if accuracy is insufficient.
- `2026-05-02`: chose orthographic projection as default, perspective as optional. Reason: ControlNet OpenPose XL2 was trained on real DWPose detections of real photos, which are de-facto perspective; orthographic produces close-enough geometry at typical portrait focal lengths and is simpler. Document the assumption; revisit if accepted-image quality at high yaw fails the visual gate.

## Fallback Register

- **Path**: `openrepose/rig.py` body-pose fallback for missing hip/elbow/wrist keypoints.
- **Required Label In Code/UI**: log line `WARN rig.fit_body_partial: missing=hip,elbow,wrist; fallback=zero_confidence`. Field `body_partial: true` in rig metrics dict.
- **Successor / Debt Owner**: WP-I0-001 itself; no successor needed if operator accepts that bust portraits don't have hips.
- **Exit Condition To Remove**: not removed for v0.1; document as expected behavior in the rig dump.

## Change Ledger

- **What Became Real**:
  - `pyproject.toml` declares the package + runtime/dev deps; `pip install -e .[dev]` works inside `.venv`.
  - Yaw terminology lock and parser (`yaw_bin.py`) — `parse_bin`, `signed_deg_to_bin`, `direction_arrow`, `standard_13_angle_bins`. Forbidden phrases raise `OpenReposeForbiddenTerminologyError`.
  - MediaPipe-to-OpenPose schema mapping (`openpose_schema.py`) — 478-face -> 70-face index map, 33-pose -> 18-body map with synthesized neck.
  - Rig fit (`rig.py`) — fits MediaPipe FaceMesh (478, refined for iris pupils) + MediaPipe Pose (model_complexity=2) on a portrait. Calibrates Pose z into FaceMesh z scale using nose tip as common landmark; head anchor is the synthesized neck (mean of MP shoulders 11/12).
  - Rigid yaw rotation (`rotation.py`) — pure y-axis rotation about head anchor with corrected sign convention (positive = her-left = nose to +x edge of frame). Per-face-landmark surface-normal visibility cull. Body eye/ear cull on the correct anatomical side.
  - OpenPose JSON serialization (`openpose_serialize.py`) — emits the schema OpenPoseXL2 was trained on (`pose_keypoints_2d` 18*3, `face_keypoints_2d` 70*3, hand_left null, hand_right zeros, canvas_width/height).
  - CLI (`cli.py`) — `openrepose render --portrait <p> --yaw <bin> --out <path>` and `openrepose list-bins`. Mechanical-format log lines on stdout.
  - 47-test pytest suite covering yaw_bin parser, rig fit on the Aeri master fixture, rotation behavior (including monotonic nose-x as yaw increases), eye/ear cull at high yaw, OpenPose serialization schema, and a grep test that rejects forbidden phrases in code (with `yaw_bin.py` allowlisted as the canonical definition file).
  - End-to-end manual run: `openrepose render --portrait .../aeri_master.png --yaw "her-left 30" --out .../smoke.json` produces a JSON that `RenderPeopleKps` (live ComfyUI 8188) renders to a wireframe with nose to +x edge and the long ear-chain extending to -x edge (back-of-rotated-head silhouette = anatomical-right ear). her-right 30 mirrors. her-left 90 collapses body to a vertical line and culls the anatomical-left eye/ear.
- **What Remains Simulated**:
  - Body keypoints below the chest (hips, knees, ankles, hands) are taken from MediaPipe Pose hallucinations on bust portraits. They get x=0,y=0,c=0 in the export when MP confidence is low. `body_partial=true` is recorded in the rig metrics dict and `WARN rig.fit_body_partial` is logged. This is the documented intended behavior for v0.1 (bust portraits don't have visible hips).
  - z-scale calibration uses nose-tip ratio. Other anatomical points (ears, eyes) might benefit from a more sophisticated calibration in a later WP, but this approach produces visually correct rotations on the Aeri master across the standard 13 bins.
- **Next Blocking Real Seam**:
  - WP-I0-002 LLM Control Surface: replace the bare CLI invocation with a state file + command channel so an LLM agent can drive the same pipeline through HTTP or file-watch inbox.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row.
2. Implementation commit: `pyproject.toml` + product source files + tests + fixtures.
3. Verification commit: `target/test-artifacts/WP-I0-001/pytest_results.xml` references in this WP's Evidence section.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests --junitxml=target/test-artifacts/WP-I0-001/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I0-001/`
- **Claim Standard**: never mark `DONE` without the junit XML present and a manual `RenderPeopleKps` verification recorded in Evidence.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, and Change Ledger truthful.
- [ ] Linked test suite executed; results saved under `target/test-artifacts/WP-I0-001/`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off: APPROVED.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I0-001/pytest_results.xml` — 47 passed, 0 failed.
- **Logs**: stdout from `openrepose render` calls captured during smoke runs:
  - `OK   rig.fit: portrait='.../aeri_master.png' face=478 body=33 t_ms=1053 body_partial=yes`
  - `WARN rig.fit_body_partial: missing=right_elbow,right_wrist,left_wrist; fallback=zero_confidence`
  - `OK   render.write: yaw='her-left 30' signed_deg=30.0 out='target/test-artifacts/WP-I0-001/smoke_aeri_yaw_her-left-30.json'`
- **Screenshots / Exports**:
  - `target/test-artifacts/WP-I0-001/smoke_aeri_yaw_her-left-30.json`
  - `target/test-artifacts/WP-I0-001/smoke_aeri_yaw_her-right-30.json`
  - `target/test-artifacts/WP-I0-001/smoke_aeri_yaw_her-left-90.json`
  - `target/test-artifacts/WP-I0-001/renders/openrepose_aeri_her-left-30_00001_.png` (rendered through `RenderPeopleKps`)
  - `target/test-artifacts/WP-I0-001/renders/openrepose_aeri_her-right-30_00001_.png`
  - `target/test-artifacts/WP-I0-001/renders/openrepose_aeri_her-left-90_00001_.png`
  - `target/test-artifacts/WP-I0-001/renders/WP-I0-001_smoke_contact_sheet.png` (3-up summary)
- **Build Artifacts**: `pyproject.toml` at repo root; editable install in `.venv`.
- **Proof Artifact**: `target/test-artifacts/WP-I0-001/`
- **Operator Sign-off**: APPROVED 2026-05-02 — operator verified `WP-I0-001_smoke_contact_sheet.png` shows correct rotation direction. Quote: "contact sheet is correct, lets proceed".

## Progress Log

- `2026-05-02`: WP initialized, status READY, no predecessors, eligible to start.
- `2026-05-02`: status -> IN-PROGRESS. Implementation starting with `pyproject.toml`, then yaw_bin -> openpose_schema -> rig -> rotation -> openpose_serialize -> cli, then tests.
- `2026-05-02`: implementation done. 47/47 pytest passing. Manual `RenderPeopleKps` verification on her-left 30, her-right 30, her-left 90 confirms rotation direction matches the spec contract. Status -> REVIEW. Operator sign-off pending on the contact sheet at `target/test-artifacts/WP-I0-001/renders/WP-I0-001_smoke_contact_sheet.png`.
- `2026-05-02`: operator approved the contact sheet. Status -> DONE. File archived from `.gov/workflow/workpackets/` to `.gov/workflow/archive/`.
