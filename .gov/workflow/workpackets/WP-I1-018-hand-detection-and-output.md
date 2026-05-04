# WP-I1-018 - Hand Detection (MediaPipe Hands) + OpenPose Hand Output

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Status**: IN-PROGRESS
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / Rig Construction + OpenPose Schema Mapping (extend to include hands).

## Intent

Add MediaPipe Hands detection to the rig pipeline and emit the resulting 21-keypoint hand schemas in the OpenPose JSON output. v0.1 explicitly suppresses hands (`hand_left_keypoints_2d=null`, `hand_right_keypoints_2d=21*[0.0]`) — that's why operator-tested portraits show no hand wireframes in the OpenPose preview. DWPose / OpenPoseXL2 ControlNet do consume hand keypoints, so this materially improves generation when the source portrait shows visible hands.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 must reach DONE.
- **Related**: WP-I1-014 MediaPipe Tasks API migration — if Tasks API ships first, this WP uses `mp.tasks.vision.HandLandmarker`; otherwise `mp.solutions.hands.Hands`.
- **Related**: WP-I1-017 per-body-part visibility — operator can suppress hands via the `hands` flag once both ship.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-04 | Google AI Edge MediaPipe Hand Landmarker Python docs | https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python | Current Tasks API supports still-image hand detection via `HandLandmarker` IMAGE mode, returns 21 normalized landmarks, world landmarks, and handedness; use this path instead of legacy `mp.solutions.hands` for new work. | adopt |
| 2026-05-04 | Google AI Edge MediaPipe source | https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/python/vision/hand_landmarker.py | `HandLandmarkerResult` exposes `hand_landmarks`, `hand_world_landmarks`, and `handedness`; the module also defines hand connection groups usable as the drawing topology reference. | adapt |
| 2026-05-04 | OpenPose output docs | https://cmu-perceptual-computing-lab.github.io/openpose/web/html/doc/md_doc_02_output.html | OpenPose serializes hands as `hand_left_keypoints_2d` and `hand_right_keypoints_2d`, analogous to pose/face arrays, with flat coordinate/confidence triples. | adopt |

## Reality Boundary

- **Real Seam**: extend `_run_mediapipe()` in `rig.py` to also run MediaPipe Hands. Persist the hand landmarks (left and right, with confidence per landmark) on the `Rig`. Apply the same y-axis rotation to hand keypoints in `rotation.rotate_yaw`. Emit `hand_left_keypoints_2d` and `hand_right_keypoints_2d` arrays in the OpenPose JSON when hands are detected and the visibility flag is on. `draw_openpose.py` extended to draw hand bones.
- **User-Visible Win**: operator imports a portrait that includes hands; the OpenPose preview shows the hand skeletons. Exported JSON contains 21*3 hand triples per detected hand. DWPose / OpenPoseXL2-driven generation respects the hand pose.
- **Proof Target**: pytest covers a fixture portrait with visible hands; the JSON contains 21*3 non-zero hand triples; the OpenPose preview shows the hand skeleton; ComfyUI `RenderPeopleKps` of the JSON renders hands at correct positions.

## In Scope

- MediaPipe Hands integration in the rig fit step (or HandLandmarker if WP-I1-014 closes first).
- 21-keypoint per-hand schema following OpenPose convention (wrist + 4 keypoints * 5 fingers).
- Rotation of hand keypoints with the rig.
- Hand bones drawn in `draw_openpose.py`.
- Optional `Rig.fit_metrics.hand_left_detected` / `.hand_right_detected` booleans for state.json telemetry.
- Calibration on the z-scale for hand depth (similar trick as the Pose-z calibration we did for body, using the wrist as a common landmark with body Pose).
- Tests: portrait with hands, portrait without hands, hand-only flag suppression (when WP-I1-017 ships).
- New test fixture: a portrait with clearly visible hands.

## Out Of Scope

- Hand pose locks / IK (covered in deferred WP-I1-021).
- Per-finger joint manipulation (deferred).
- Multi-hand portraits (pairs only — left + right per subject).

## Risks And Dependencies

- **Risk**: MediaPipe Hands' z scale differs from FaceMesh's z scale (different again). Need per-portrait calibration using wrist landmarks (Pose has wrist; Hands has wrist; ratio gives the scale).
- **Risk**: rotation of hand keypoints assumes the hand is rigid. For 90 deg yaw the back of one hand becomes occluded; need visibility cull similar to face/body.
- **Dependency**: WP-I1-014 Tasks API migration affects the import path; this WP can ship before or after but the integration call site differs slightly.

## Headless LLM Operation Compliance

- [ ] LLM agent uses the existing `import_portrait` (now also detects hands) and existing snapshot targets.
- [ ] State reflected in `state.json` `rig` block (extended with hand-detection counts) and per-bin export JSONs.
- [ ] LLM pulls visual via existing `openpose_viewport` snapshot.
- [ ] No focus theft / modal dialogs.
- [ ] Tests cover headless path with the new hand fixture.

## Definition Of Done

- [ ] MediaPipe Hands detection runs as part of `Rig.from_portrait`.
- [ ] Rotated rig produces hand keypoints in OpenPose JSON.
- [ ] OpenPose preview draws hand skeletons.
- [ ] Verified end-to-end via `RenderPeopleKps` rendering of an exported JSON.
- [ ] Per-body-part `hands` flag (when WP-I1-017 ships) toggles suppression.
- [ ] `pytest` zero failures.
- [ ] **Manual Impact**: Yes - extends `.gov/doc/manual/feature-1-yaw-exporter.md` with hand-detection/output behavior and the `hands_unavailable` runtime note.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / Rig Construction + OpenPose Schema Mapping (extend with hands).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (`import_portrait` continues to satisfy headless flow; existing snapshot targets reflect hand skeleton).

## Linked Test Suite

- `.product/tests/test_hand_detection.py` (NEW) — fixture portrait with visible hands, per-hand keypoint count, rotation correctness, suppression via WP-I1-017 `hands` flag.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-018-hand-detection-and-output.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — extend Rig Construction + OpenPose Schema Mapping with hand schemas.

### Product (`.product/`)

- `.product/src/openrepose/rig.py` — extend `_run_mediapipe()` to also run MediaPipe Hands (or `mp.tasks.vision.HandLandmarker` if WP-I1-014 closes first).
- `.product/src/openrepose/rotation.py` — apply rig yaw to hand keypoints.
- `.product/src/openrepose/openpose_serialize.py` — emit `hand_left_keypoints_2d` / `hand_right_keypoints_2d` 21*3 arrays.
- `.product/src/openrepose/render/draw_openpose.py` — draw 21-keypoint hand bones.
- `.product/src/openrepose/state.py` — `rig.fit_metrics.hand_left_detected` / `.hand_right_detected`.
- `.product/tests/test_hand_detection.py` (NEW)
- `.product/tests/fixtures/portrait_with_hands.png` (NEW operator-authorized fixture).

### Build / Output

- `outputs/<avatar-slug>/<run-tag>/` — per-export JSONs gain hand triples when detected.
- `target/test-artifacts/WP-I1-018/`

## Risks And Dependencies

- **Risk**: MediaPipe Hands z-scale differs from FaceMesh and Pose; uncalibrated z corrupts depth-based rotation. **Mitigation**: per-portrait calibration using the wrist landmark (Pose has wrist; Hands has wrist; ratio gives the scale).
- **Risk**: at 90deg yaw, the back of one hand becomes occluded; emitting full 21 keypoints fakes visibility. **Mitigation**: visibility cull similar to the face/body cull; emit confidence-zero triples for occluded keypoints.
- **Dependency**: WP-I0-001..004 (foundation). Related WP-I1-014 affects import path; related WP-I1-017 supplies the suppression flag.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Fixture portrait with visible hands: rig fit detects both hands; JSON contains 21*3 non-zero triples per hand.
- [ ] Portrait without visible hands: hand schemas remain null/zero per spec.
- [ ] When WP-I1-017's `hands` flag is false: hand triples are zeroed even if detected.

### Code Correctness Tests
- [ ] Rotation of hand keypoints matches the rig yaw within tolerance at her-left 30 / 60 / 90 and her-right 30 / 60 / 90.
- [ ] Wrist-calibrated z scale produces consistent depth between Pose and Hands.
- [ ] OpenPose preview draws hand bones at expected positions.

### Red-Team / Abuse Tests
- [ ] Portrait with one hand: only that hand carries non-zero triples; the other side stays zeroed without crash.
- [ ] Adversarial portrait (gloves, motion blur): hand detection returns no result; no crash; state.json reflects `hand_*_detected = false`.
- [ ] No fixture or output filename contains a forbidden yaw phrase.

### Performance / Reliability Tests
- [ ] Rig fit with hands within 1.4x of hands-disabled baseline.

## Rollback Plan

- Files to revert: `rig.py`, `rotation.py`, `openpose_serialize.py`, `render/draw_openpose.py`, `state.py`, the new test and fixture.
- Files to keep: existing exports retain their schema (loader still accepts hands-null entries).
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/rig.py .product/src/openrepose/rotation.py .product/src/openrepose/openpose_serialize.py .product/src/openrepose/render/draw_openpose.py .product/src/openrepose/state.py .product/tests/test_hand_detection.py .product/tests/fixtures/portrait_with_hands.png`

## Decisions Log

- 2026-05-04: Use MediaPipe Tasks `HandLandmarker` in IMAGE mode for still portraits instead of legacy `mp.solutions.hands`. Reason: current Google AI Edge docs describe Tasks as the active Python surface and expose handedness + normalized landmarks directly. Alternatives considered: legacy `mp.solutions.hands`, rejected for new code path unless Tasks import is unavailable.

## Fallback Register

- **Path**: hand detector runtime when MediaPipe Tasks/model asset is unavailable. **Required Label In Code/UI**: `hands_unavailable`. **Successor / Debt Owner**: WP-I1-018. **Exit Condition To Remove**: MediaPipe task dependency and model asset path are available in the runtime environment.

## Change Ledger

- 2026-05-04: Promoted DRAFT -> IN-PROGRESS after operator requested autonomous overnight implementation. Research recorded. Governance kickoff commit pending before `.product/` edits.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec extension + fixture acquisition.
2. Implementation: hand detection in rig fit + rotation extension + serializer.
3. GUI wiring: preview renderer draws hand bones.
4. Verification: pytest + downstream `RenderPeopleKps` smoke + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_hand_detection.py --junitxml=target/test-artifacts/WP-I1-018/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-018/pytest_results.xml` plus a `RenderPeopleKps`-rendered PNG of an exported JSON.
- **Claim Standard**: never mark `DONE` without junit XML evidence and a downstream-render confirmation that hands appear at correct positions.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-018/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths (downstream render confirmation).
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- 2026-05-04: Promoted DRAFT -> IN-PROGRESS after operator requested autonomous overnight implementation. Research recorded. Governance kickoff commit pending before `.product/` edits.

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.

- 2026-05-04: Status DRAFT -> IN-PROGRESS; research notes added; implementation authorized by operator for autonomous overnight work.
- 2026-05-04: Product implementation pass landed for hand landmark storage, yaw rotation, OpenPose JSON hand arrays, preview hand rendering, state telemetry, and built-in Help manual note. Validation evidence pending; WP stays IN-PROGRESS until tests/visual proof are run.
