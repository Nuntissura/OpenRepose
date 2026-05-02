# WP-I1-024 - Synchronized Viewport Zoom

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements (extend with synchronized zoom).

## Intent

Wire the WP-I1-023 frame-scale state into all three viewports (3D viewport, OpenPose preview, floating reference window) so they zoom together. Each viewport pads its empty area according to its rules:

- **3D viewport**: pads with the existing dark-gray diagnostic background.
- **OpenPose viewport**: ALWAYS pads with black, regardless of operator color choice — DWPose / OpenPoseXL2 was trained on black-background poses; non-black would corrupt conditioning.
- **Reference portrait window**: pads with operator-chosen color from Options (default white).

## Linked Workpackets

- **Predecessor(s)**: WP-I0-004 must reach DONE; WP-I1-015 (floating reference window); WP-I1-023 (frame reframing).
- **Successor(s)**: none.

## Reality Boundary

- **Real Seam**: GUI bind: each viewport widget reads the `frame` block from AppState on every refresh and applies the same scale + offset before paint. Reference window padding color comes from Options. OpenPose viewport hardcodes black padding.
- **User-Visible Win**: operator drags the frame slider once; all three viewports update together. Operator confirms the framing visually before exporting.
- **Proof Target**: pytest-qt verifies the three viewports use the same `frame_scale` after a single state update; manual: drag the slider; reference window shows the portrait shrinking with white margin; OpenPose preview shrinks with black margin; 3D viewport shrinks with dark gray margin.

## In Scope

- `Viewport3D`, `ViewportOpenPose`, and `ReferenceWindow` (when WP-I1-015 ships) all read the AppState `frame` block.
- Reference window's `padding_color` setting in Options (default white) — exact field name shared with WP-I1-015.
- Hardcoded black padding for the OpenPose viewport, documented inline.
- Tests covering all three viewports respecting the same frame state.

## Out Of Scope

- Per-viewport zoom (operator chooses one global zoom; individual viewport zooms not supported in v0.1).
- Inertial / animated zoom transitions.

## Risks And Dependencies

- **Risk**: WP-I1-015 and WP-I1-023 must ship before this WP makes sense. If either is delayed, this WP defers correspondingly.

## Headless LLM Operation Compliance

- [x] N/A — pure GUI synchronization. The headless surface for `frame` already exists via WP-I1-023's commands. This WP only wires the GUI side.

## Definition Of Done

- [ ] Frame slider on the toolbar drives all three viewports synchronously.
- [ ] OpenPose viewport always uses black padding, regardless of Options color.
- [ ] Reference window uses the Options padding color.
- [ ] 3D viewport uses its diagnostic background as padding.
- [ ] `pytest .product/tests/test_synchronized_zoom.py` zero failures.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / GUI Requirements (extend with synchronized zoom contract); WP-I1-023 frame state is the single source of truth.
- `.gov/AGENTS.md` — Headless LLM Operation Rule (this WP wires GUI only; headless surface for `frame` lives in WP-I1-023).

## Linked Test Suite

- `.product/tests/test_synchronized_zoom.py` (NEW) — three viewports read same `frame` block; per-viewport padding rule enforced; OpenPose viewport always black.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-024-synchronized-viewport-zoom.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — extend GUI Requirements with synchronized-zoom rule and per-viewport padding contract.

### Product (`.product/`)

- `.product/src/openrepose/gui/viewport_3d.py` — read `frame` block; apply scale + offset; pad with the diagnostic dark-gray.
- `.product/src/openrepose/gui/viewport_openpose.py` — read `frame` block; pad with hardcoded black (documented inline).
- `.product/src/openrepose/gui/reference_window.py` — read `frame` block; pad with operator-chosen color (default white).
- `.product/src/openrepose/gui/options.py` — `padding_color` field shared with WP-I1-015 schema.
- `.product/tests/test_synchronized_zoom.py` (NEW)

### Build / Output

- `target/test-artifacts/WP-I1-024/`

## Risks And Dependencies

- **Risk**: drift between viewports if any reads a stale frame snapshot. **Mitigation**: each viewport pulls the `frame` block on every refresh tick from a single AppState getter; dedicated test asserts simultaneous post-update reads agree.
- **Risk**: future change to OpenPose viewport padding could corrupt downstream conditioning. **Mitigation**: hardcode black padding; comment cites the DWPose / OpenPoseXL2 training requirement; test asserts the hardcoded value.
- **Dependency**: WP-I0-004 (GUI scaffold), WP-I1-015 (reference window), WP-I1-023 (frame state). Defers if any of those is delayed.

## Test Coverage Plan

### Functional Flow Tests
- [ ] After `set_frame_scale=0.7`, all three viewports render at scale 0.7 within 1 frame.
- [ ] OpenPose viewport padding is black regardless of Options padding color.
- [ ] Reference window padding matches the Options padding color (verified by sampling pixel color in a known-empty region).
- [ ] 3D viewport padding matches the existing diagnostic dark-gray.

### Code Correctness Tests
- [ ] Single AppState `frame` block update propagates to all three viewports without divergence.
- [ ] Padding-color helper returns the correct color per viewport class.
- [ ] No viewport mutates the `frame` block (read-only path).

### Red-Team / Abuse Tests
- [ ] Operator sets `padding_color=black` in Options: 3D and OpenPose unaffected; reference window adopts black.
- [ ] Operator sets a forbidden-yaw-phrase string in `padding_color`: rejected by the Options validator.
- [ ] Rapid frame changes (60 updates/s for 5 seconds): no viewport falls behind by more than 1 frame.

### Performance / Reliability Tests
- [ ] Three-viewport synchronized refresh under 30ms total at 1920x1080.

## Rollback Plan

- Files to revert: `gui/viewport_3d.py`, `gui/viewport_openpose.py`, `gui/reference_window.py`, `gui/options.py`, the new test file.
- Files to keep: WP-I1-023 frame state remains usable headlessly even without GUI sync.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/gui/viewport_3d.py .product/src/openrepose/gui/viewport_openpose.py .product/src/openrepose/gui/reference_window.py .product/src/openrepose/gui/options.py .product/tests/test_synchronized_zoom.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec extension.
2. Implementation: per-viewport `frame` reader + padding helper.
3. GUI wiring: hookup, Options padding-color field shared with WP-I1-015.
4. Verification: pytest-qt + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_synchronized_zoom.py --junitxml=target/test-artifacts/WP-I1-024/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-024/pytest_results.xml` plus a side-by-side screenshot of the three viewports at `frame_scale=0.6`.
- **Claim Standard**: never mark `DONE` without junit XML evidence and operator-confirmed visual review of the per-viewport padding rules.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-024/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: marked N/A with reason (pure GUI synchronization; headless surface for `frame` covered by WP-I1-023).

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
