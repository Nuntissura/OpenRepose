# WP-I1-011 - Multi-Subject Scenes

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1+
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: L
- **Linked Spec**: future spec section "Multi-subject scenes".

## Intent

Extend the rig schema to support two or more subjects in one frame (production scenes with two performers). Each subject has its own Rig with its own yaw/pitch/roll state; rotation and export commands accept a `subject_index` argument.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 (foundation); ideally WP-I1-007 pitch/roll (multi-subject scenes typically need full pose).
- **Related**: WP-I1-009 identity-export profiles (may want per-subject identity bundles).

## Reality Boundary

- **Real Seam**: `App` holds a list of Rigs, not a single Rig. State.json gains a `subjects` list. Commands accept `subject_index` (0-based); 0 is the primary subject for backward compatibility.
- **User-Visible Win**: operator imports two portraits, OpenRepose fits both rigs, viewports show both subjects, exports produce per-subject OpenPose JSONs in one batch.
- **Proof Target**: end-to-end test: import two portraits, set per-subject yaw, export batch, verify two manifest entries with two sets of files.

## In Scope

- Subjects list in AppState.
- `subject_index` argument on rig-touching commands.
- New commands: `import_portrait` accepts `subject_index`; `set_yaw`, `set_yaw_bin` accept `subject_index`; `remove_subject`.
- GUI: subject selector dropdown in toolbar; per-subject inspector tab or shared inspector with subject toggle.
- Tests covering multi-subject lifecycle.

## Out Of Scope

- Inter-subject pose constraints (e.g., one subject's hand on another's shoulder).
- Multi-rig camera composition for the snapshot subsystem (each subject stays in its own canvas; composition is operator-side).

## Headless LLM Operation Compliance

- [ ] LLM agent passes `subject_index` to relevant commands.
- [ ] State reflected in `state.json` `subjects` list.
- [ ] Snapshot targets accept optional `subject_index`.
- [ ] No focus theft.
- [ ] Tests cover headless path.

## Definition Of Done

- [ ] Multi-subject end-to-end works.
- [ ] GUI lets operator pick which subject the toolbar drives.
- [ ] No regression in single-subject flow.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Future Spec Areas / Multi-subject scenes; LLM Control Surface; Rig schema (extend to a list).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (commands accept `subject_index`; state mirrors a `subjects` list; snapshots accept `subject_index`).

## Linked Test Suite

- `.product/tests/test_multi_subject.py` (NEW) — single-subject backward compat, two-subject lifecycle, per-subject yaw, per-subject export, removal.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-011-multi-subject-scenes.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — promote multi-subject placeholder to a full section (state schema, command extensions, snapshot extensions).

### Product (`.product/`)

- `.product/src/openrepose/app.py` — `App` holds a list of Rigs.
- `.product/src/openrepose/state.py` — `subjects` list; backward-compatible getter for index 0.
- `.product/src/openrepose/commands.py` — accept `subject_index` on rig-touching commands; new `remove_subject`.
- `.product/src/openrepose/rig.py` — clarify single-subject creation; nothing else changes per-rig.
- `.product/src/openrepose/rotation.py` — operates on a single rig, called per subject.
- `.product/src/openrepose/openpose_serialize.py` — emit per-subject keypoints (OpenPose schema supports a `people[]` list).
- `.product/src/openrepose/snapshot.py` — accept optional `subject_index`.
- `.product/src/openrepose/gui/toolbar.py` — subject selector dropdown.
- `.product/src/openrepose/gui/inspector.py` — per-subject readouts (toggle or tab).
- `.product/tests/test_multi_subject.py` (NEW)

### Build / Output

- `outputs/<avatar-slug>/<run-tag>/subject_<i>/...` per-subject output layout.
- `target/test-artifacts/WP-I1-011/`

## Risks And Dependencies

- **Risk**: introducing `subject_index` breaks existing single-subject tests. **Mitigation**: default `subject_index=0` everywhere; extend tests in two phases (compat first, multi second).
- **Risk**: GUI complexity inflates with subject toggles. **Mitigation**: ship a single subject selector dropdown in the toolbar; defer per-subject docks to a follow-up WP.
- **Dependency**: WP-I0-001..004 (foundation); ideally WP-I1-007 pitch/roll (multi-subject scenes typically need full pose).

## Test Coverage Plan

### Functional Flow Tests
- [ ] Import portrait without `subject_index` -> populates subject 0; existing flow unchanged.
- [ ] Import second portrait with `subject_index=1`; both rigs fit.
- [ ] Per-subject yaw bin set; rotation applied only to the chosen subject.
- [ ] Batch export writes per-subject files under `subject_<i>/`.
- [ ] `remove_subject {subject_index: 1}` clears subject 1; subject 0 untouched.

### Code Correctness Tests
- [ ] state.json `subjects` list shape matches the spec on every set-command.
- [ ] Snapshot target `3d_viewport {subject_index: i}` returns the i-th subject.
- [ ] Commands missing `subject_index` default to 0 (backward compat).

### Red-Team / Abuse Tests
- [ ] `subject_index` out of range: structured ERR, no state mutation.
- [ ] No GUI text introduces forbidden yaw phrases (extended grep test).
- [ ] Concurrent set-commands on different subjects do not corrupt state.

### Performance / Reliability Tests
- [ ] Two-subject batch export within 2.2x single-subject baseline.

## Rollback Plan

- Files to revert: `app.py`, `state.py`, `commands.py`, `openpose_serialize.py`, `snapshot.py`, `gui/toolbar.py`, `gui/inspector.py`, the new test file.
- Files to keep: existing single-subject outputs untouched.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/app.py .product/src/openrepose/state.py .product/src/openrepose/commands.py .product/src/openrepose/openpose_serialize.py .product/src/openrepose/snapshot.py .product/src/openrepose/gui/toolbar.py .product/src/openrepose/gui/inspector.py .product/tests/test_multi_subject.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec section.
2. Implementation: AppState `subjects` list + dispatcher + serializer.
3. GUI wiring: subject selector + inspector toggle.
4. Verification: pytest + manual two-subject smoke.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_multi_subject.py --junitxml=target/test-artifacts/WP-I1-011/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-011/pytest_results.xml` plus a sample two-subject batch archive.
- **Claim Standard**: never mark `DONE` without junit XML evidence plus a manual smoke that imports two portraits and exports a per-subject batch.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-011/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT. Likely deferred to I2; complexity warrants splitting if scope creeps.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
