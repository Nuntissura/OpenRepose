# WP-I1-007 - Pitch / Roll Rotation Extension

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: future spec section "Pitch / roll rotation extension" — promote from placeholder to full block via predecessor `DOCUMENTATION` WP.

## Intent

Extend the rig from yaw-only to full head-pose (yaw + pitch + roll). Adds head tilt (chin up/down) and head lean (ear-toward-shoulder) as independently controllable axes. Each axis has the same locked-terminology and headless-control treatment as yaw.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 (foundation); a `DOCUMENTATION` WP that authors the spec section for pitch/roll terminology and bin conventions.
- **Successor(s)**: identity-export profiles (which want full head pose).

## Reality Boundary

- **Real Seam**: extend `rotation.py` with `rotate_pose(rig, yaw, pitch, roll)`; extend `YawBin` schema to a `Pose` schema; new commands `set_pitch`, `set_roll`, `set_pose`; new state.json fields `current_pitch_deg`, `current_roll_deg`; toolbar gains pitch + roll sliders.
- **User-Visible Win**: operator can produce wireframes at, say, "her-left 30 + chin-down 15 + lean-right 5" to match a specific reference photograph's pose.
- **Proof Target**: pytest covers all three axes independently and combined; manual: produce wireframes at extreme combined-axis values and visually verify they look anatomically plausible.

## In Scope

- Pose schema and bin conventions (locked terminology to be authored in the predecessor DOCUMENTATION WP — likely `chin-up N` / `chin-down N` for pitch and `lean-left N` / `lean-right N` for roll).
- Forbidden-phrase grep test extended for the new axes.
- 3 new commands; state.json updates; GUI widgets for the new axes.
- Tests across all three axes.

## Out Of Scope

- 6DoF (translation) — keep rotations only.
- Animated pose (still images only).
- Per-axis calibration.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via `set_pitch`, `set_roll`, `set_pose`.
- [ ] State reflected in `state.json` extended pose block.
- [ ] LLM pulls visual via existing snapshot targets (3d_viewport / openpose_viewport reflect the new pose).
- [ ] No focus theft.
- [ ] Tests cover headless command path.

## Definition Of Done

- [ ] Rig fits + rotation works at non-zero pitch and roll.
- [ ] Forbidden-phrase test extended; new bin parser rejects equivalents of `image-up`, `viewer-tilted`, etc.
- [ ] 3 new commands functional; tests pass.
- [ ] GUI sliders render the new poses live.
- [ ] Spec section authored.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / Rig Construction + Rotation, OpenPose Schema Mapping; predecessor DOCUMENTATION WP authors the pitch/roll terminology block.
- `.gov/AGENTS.md` — Headless LLM Operation Rule (new commands `set_pitch`, `set_roll`, `set_pose` reachable headlessly).

## Linked Test Suite

- `.product/tests/test_rotation_pose.py` (NEW) — yaw/pitch/roll independent and combined; forbidden-phrase grep extended to new axes.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-007-pitch-roll-rotation.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — promote pitch/roll placeholder to a full section (locked terminology, bin convention).

### Product (`.product/`)

- `.product/src/openrepose/rotation.py` — add `rotate_pose(rig, yaw, pitch, roll)`.
- `.product/src/openrepose/yaw_bin.py` — extend (or sister module) for pitch/roll bin parsing.
- `.product/src/openrepose/state.py` — `current_pitch_deg`, `current_roll_deg` fields.
- `.product/src/openrepose/commands.py` — register `set_pitch`, `set_roll`, `set_pose`.
- `.product/src/openrepose/openpose_serialize.py` — apply pose rotation before keypoint emission.
- `.product/src/openrepose/render/draw_3d.py` — 3D viewport reflects pose.
- `.product/src/openrepose/gui/toolbar.py` — pitch + roll sliders with locked terminology labels.
- `.product/src/openrepose/gui/inspector.py` — show all three axes.
- `.product/tests/test_rotation_pose.py` (NEW)
- `.product/tests/test_forbidden_phrases.py` — extend grep with new-axis forbidden equivalents.

### Build / Output

- `target/test-artifacts/WP-I1-007/`

## Risks And Dependencies

- **Risk**: composing yaw/pitch/roll rotations in the wrong order produces incorrect anatomy. **Mitigation**: lock the order (intrinsic Y-X-Z or Tait-Bryan as decided in DOCUMENTATION WP); unit-test against fixed reference points.
- **Risk**: bin terminology drift introducing forbidden phrases (e.g., `image-up`, `viewer-tilted`). **Mitigation**: extend the forbidden-phrase grep test to cover pitch/roll equivalents.
- **Dependency**: predecessor DOCUMENTATION WP must author pitch/roll spec section (terminology, bin tables) before this WP starts.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Pure yaw rotation matches WP-I0-001 baseline (regression-safe).
- [ ] Pure pitch and pure roll produce expected landmark trajectories.
- [ ] Combined yaw + pitch + roll renders without crash and exports OpenPose JSON with valid coordinates.

### Code Correctness Tests
- [ ] Rotation order is consistent across `rotation.py`, the renderer, and the OpenPose serializer.
- [ ] Bin parser rejects forbidden equivalents (tested via parametrized `pytest.raises`).
- [ ] state.json contains `current_pitch_deg` and `current_roll_deg` after each set-command.

### Red-Team / Abuse Tests
- [ ] Forbidden phrases (`image-up`, `viewer-tilted`, equivalents) absent from code, UI text, and bin labels.
- [ ] Out-of-range pose values clamped or rejected with structured ERR; no silent wrap.

### Performance / Reliability Tests
- [ ] Triple-axis rotation per yaw step under 5ms; 13-angle batch within 1.5x of yaw-only baseline.

## Rollback Plan

- Files to revert: `rotation.py`, `state.py`, `commands.py`, `openpose_serialize.py`, `render/draw_3d.py`, `gui/toolbar.py`, `gui/inspector.py`, plus the new and extended test files.
- Files to keep: existing yaw-only behavior remains the default when pitch/roll are zero.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/rotation.py .product/src/openrepose/state.py .product/src/openrepose/commands.py .product/src/openrepose/openpose_serialize.py .product/src/openrepose/render/draw_3d.py .product/src/openrepose/gui/toolbar.py .product/src/openrepose/gui/inspector.py .product/tests/test_rotation_pose.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec section authored by predecessor DOCUMENTATION WP.
2. Implementation: rotation math + serializer + state + commands.
3. GUI wiring: toolbar sliders + inspector readouts.
4. Verification: pytest + forbidden-phrase suite + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_rotation_pose.py .product/tests/test_forbidden_phrases.py --junitxml=target/test-artifacts/WP-I1-007/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-007/pytest_results.xml` plus a wireframe sequence at extreme combined-axis values.
- **Claim Standard**: never mark `DONE` without junit XML evidence plus operator-confirmed manual review of the wireframe sequence.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-007/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
