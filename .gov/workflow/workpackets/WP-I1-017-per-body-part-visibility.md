# WP-I1-017 - Per-Body-Part Visibility Toggles

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: REVIEW
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / OpenPose Schema Mapping (add visibility-toggle layer); LLM Control Surface (add commands).

## Intent

Operator-controlled visibility toggles for body part groups. Lets the operator suppress legs / arms / face / hands from the OpenPose output entirely. Useful when (a) the source portrait is bust-only and DWPose's hallucinated lower-body keypoints would mislead generation, (b) the operator wants a face-only OpenPose for face-detail conditioning, (c) hands are not needed for a particular workflow.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-004 must reach DONE.
- **Related**: WP-I1-018 (hand detection) — once hands are detected, this WP's `hands` toggle decides whether to emit them.

## Reality Boundary

- **Real Seam**: new `body_part_visibility` block in `state.json` with bool flags `face`, `body_torso`, `arms`, `legs`, `hands`. The OpenPose serializer reads these flags and zeros out the corresponding keypoint groups before writing the JSON. Same flags mirrored in the OpenPose preview renderer (hidden parts not drawn).
- **User-Visible Win**: operator unchecks "Legs" in Options; subsequent exports omit legs; the OpenPose preview renders without legs. Re-checking restores them.
- **Proof Target**: pytest covers each toggle independently; manual verifies a face-only export and a torso-only export look correct.

## In Scope

- New state block + new commands `set_body_part_visibility`, `get_body_part_visibility`.
- Options-pane checkboxes for each group (5 checkboxes: face, body_torso, arms, legs, hands).
- Serializer reads the flags and zeros corresponding triples in the OpenPose JSON output.
- Preview renderer (`draw_openpose.py`) honors the flags.
- Tests: each toggle individually; combinations; persistence (when WP-I1-003 ships).

## Out Of Scope

- Per-keypoint visibility (only body part groups in v0.1).
- Per-side suppression (left / right separately) — both sides toggle together.
- Per-export-target visibility (e.g., "legs visible in batch but not single") — flags are global.

## Risks And Dependencies

- **Risk**: zeroing keypoints in OpenPose JSON should NOT be confused with "occluded" by ControlNet — a fully-zeroed group reads as "this part is not present", which is exactly what we want. Verify on DWPose / OpenPoseXL2.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via 2 new commands.
- [ ] State reflected in `state.json` `body_part_visibility` block.
- [ ] LLM pulls visual via existing `openpose_viewport` snapshot (reflects flag state).
- [ ] No focus theft / modal dialogs.
- [ ] Tests cover headless path.

## Definition Of Done

- [ ] All 5 part toggles functional.
- [ ] Headless commands and Options-pane checkboxes both update the flags.
- [ ] OpenPose JSON outputs reflect the flags (verified by inspecting written file).
- [ ] Full project suite green.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / OpenPose Schema Mapping (add visibility-toggle layer); LLM Control Surface (`set_body_part_visibility`, `get_body_part_visibility`).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (commands reachable headlessly; state mirrored; OpenPose viewport snapshot reflects flags).

## Linked Test Suite

- `.product/tests/test_body_part_visibility.py` (NEW) — each toggle, combinations, JSON keypoint zeroing, preview rendering, persistence (when WP-I1-003 ships).

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-017-per-body-part-visibility.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — extend OpenPose Schema Mapping + LLM Control Surface.

### Product (`.product/`)

- `.product/src/openrepose/state.py` — `body_part_visibility` block (`face`, `body_torso`, `arms`, `legs`, `hands`).
- `.product/src/openrepose/commands.py` — register `set_body_part_visibility`, `get_body_part_visibility`.
- `.product/src/openrepose/openpose_serialize.py` — zero suppressed keypoint groups.
- `.product/src/openrepose/render/draw_openpose.py` — skip suppressed groups in the preview.
- `.product/src/openrepose/gui/options.py` — five checkboxes wired to the new commands.
- `.product/tests/test_body_part_visibility.py` (NEW)

### Build / Output

- `outputs/<avatar-slug>/<run-tag>/` — per-export OpenPose JSONs reflect the flags.
- `target/test-artifacts/WP-I1-017/`

## Risks And Dependencies

- **Risk**: zeroed keypoints could be misinterpreted as "occluded" rather than "absent" by some downstream models. **Mitigation**: confirm DWPose / OpenPoseXL2 treat all-zero triples as absent during the WP; document the contract in the spec.
- **Risk**: combinations explode the test matrix. **Mitigation**: parametrize tests over single-flag and a curated combination set rather than full powerset.
- **Dependency**: WP-I0-004 (Options pane + dispatcher); WP-I1-018 (hand detection) gates whether the `hands` flag has anything to suppress.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Each of the five flags toggles independently.
- [ ] Curated combinations (face-only, torso-only, no-hands) produce expected JSON.
- [ ] OpenPose preview omits suppressed groups.

### Code Correctness Tests
- [ ] state.json `body_part_visibility` block matches command inputs after each set.
- [ ] Zeroed keypoint triples are byte-identical to `[0.0, 0.0, 0.0]` in the written JSON.
- [ ] No regression when all flags are true (current v0.1 behavior).

### Red-Team / Abuse Tests
- [ ] Unknown flag key in `set_body_part_visibility`: structured ERR; existing flags unchanged.
- [ ] No GUI checkbox label introduces a forbidden yaw phrase.

### Performance / Reliability Tests
- [ ] Toggle-driven re-render under 50ms.

## Rollback Plan

- Files to revert: `state.py`, `commands.py`, `openpose_serialize.py`, `render/draw_openpose.py`, `gui/options.py`, the new test file.
- Files to keep: previously exported JSONs (loader tolerates the older schema).
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/state.py .product/src/openrepose/commands.py .product/src/openrepose/openpose_serialize.py .product/src/openrepose/render/draw_openpose.py .product/src/openrepose/gui/options.py .product/tests/test_body_part_visibility.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- **What Became Real**:
  - `openpose_schema.py`: `BODY_GROUPS` (5: face/body_torso/arms/legs/hands), `BODY_18_INDICES_BY_GROUP` (group→indices map), `default_body_part_visibility()` helper, `apply_body_part_visibility(body18, face70, mask)` helper that zeros suppressed indices and validates unknown groups.
  - `openpose_serialize.py`: `serialize()` and `serialize_to_string()` accept optional `body_part_visibility` kwarg; mask applied via the schema helper before flatten.
  - `render/draw_openpose.py`: `render_openpose()` accepts optional `body_part_visibility`; mask applied via the schema helper before draw.
  - `state.py`: new `body_part_visibility` block defaulting to all-true.
  - `commands.py`: 2 new handlers — `set_body_part_visibility` (accepts any subset of group flags; validates names + booleans; rejects empty payload) and `get_body_part_visibility` (read-only). `_h_export_single` and `_h_export_batch` now pass `dict(d.state.body_part_visibility)` into the serializer. `_h_snapshot` passes the mask into `do_snapshot` so `openpose_viewport` and `full_window` reflect the active flags.
  - `snapshot.py`: `snapshot()` and `_render` accept optional `body_part_visibility`; threaded into the openpose path.
  - `gui/options.py`: 5 inline checkboxes wired to `body_part_visibility_changed(group, bool)` signal that fires immediately on toggle. New `load_body_part_visibility()` syncs from state.
  - `gui/main_window.py`: connects the new signal to `_on_body_part_visibility_changed`, which dispatches `set_body_part_visibility` per toggle. Initial sync on construction.
  - `test_body_part_visibility.py` (NEW): 18 tests — schema layer (defaults, identity-fast-return, face-off zeros face_70 + body face indices, legs-off zeros only leg indices, unknown group raises, float conf array support); dispatcher commands (read defaults, single + multi flag updates, unknown group rejected, non-bool rejected, empty payload rejected); end-to-end (legs-off export zeros only leg keypoints in JSON, face-off export zeros face_70 + body face indices, default-all-true regression); state.json block.
- **What Remains Simulated / Deferred**:
  - `hands` flag is reserved for WP-I1-018 (hand detection). v0.1 has no hand keypoints to suppress; the flag is wired through state + commands + GUI for forward compatibility but has no observable effect on the JSON / preview yet.
  - WP-I1-029 (per-marker visibility) layers on top of these group flags with documented precedence; that's the next WP.
- **Next Blocking Real Seam**: WP-I1-029 can compose against this layer.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec extension.
2. Implementation: state + dispatcher + serializer + renderer.
3. GUI wiring: Options checkboxes + tooltips.
4. Verification: pytest + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_body_part_visibility.py --junitxml=target/test-artifacts/WP-I1-017/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-017/pytest_results.xml` plus sample JSONs at face-only and torso-only configurations.
- **Claim Standard**: never mark `DONE` without junit XML evidence and DWPose / OpenPoseXL2 confirmation that suppressed groups behave as "absent".

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-017/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths (sample JSONs, downstream confirmation).
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I1-017/pytest_results.xml` — 225 passed, 0 failed (full suite; +18 new from this WP).
- **Local Audit Run**: `pwsh scripts/audit-repo.ps1` exits 0.
- **Build Artifacts**: modifications to `openpose_schema.py`, `openpose_serialize.py`, `render/draw_openpose.py`, `snapshot.py`, `state.py`, `commands.py`, `gui/options.py`, `gui/main_window.py`; new `test_body_part_visibility.py`.
- **Operator Sign-off**: PENDING — operator to verify by toggling body-part checkboxes in Options and inspecting an exported JSON.

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
- 2026-05-03: Operator approved fast-track batch (slot 2). Status DRAFT -> IN-PROGRESS. Implementation complete: schema helper + serializer + renderer + state + 2 commands + Options checkboxes + 18 tests. 225/225 passing. Audit clean. Status -> REVIEW.
