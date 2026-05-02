# WP-I1-005 - Drag-And-Drop Portrait Import

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: XS
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements.

## Intent

Operator drags a PNG/JPG file from Explorer into the OpenRepose window; OpenRepose triggers `import_portrait` automatically. Recorded as out-of-scope in WP-I0-004; this WP delivers it.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-004 must reach DONE.

## Reality Boundary

- **Real Seam**: enable `setAcceptDrops(True)` on `MainWindow`; implement `dragEnterEvent` (accept image MIME types) and `dropEvent` (extract path, dispatch `import_portrait`).
- **User-Visible Win**: drag-and-drop works on the central widget area and on either viewport pane.
- **Proof Target**: pytest-qt drag-event simulation triggers `import_portrait` with the dropped path.

## In Scope

- Drop handler on MainWindow + both viewport panes (forwarding to MainWindow).
- Validation: reject non-image MIME types, reject multi-file drops with WARN.
- Status bar feedback during fit.

## Out Of Scope

- Drag-and-drop of calibration-marker JSON files (calibration WP scope).
- Drag-and-drop reordering of UI elements.

## Headless LLM Operation Compliance

- [x] N/A — drag-and-drop is operator-only convenience; LLM uses `import_portrait`.

## Definition Of Done

- [ ] Drag a portrait into the window; rig fits; viewports populate.
- [ ] Non-image drops rejected with a log WARN, no crash.
- [ ] Tests cover both happy and rejection paths.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / GUI Requirements (portrait import flows).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (drag-and-drop is operator-only; LLM uses `import_portrait`).

## Linked Test Suite

- `.product/tests/test_drag_and_drop.py` (NEW) — pytest-qt mime-data drop simulation; happy path + rejection paths.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-005-drag-and-drop-portrait-import.md` (this file)
- `.gov/workflow/TASKBOARD.md`

### Product (`.product/`)

- `.product/src/openrepose/gui/main_window.py` — `setAcceptDrops(True)`, `dragEnterEvent`, `dropEvent`.
- `.product/src/openrepose/gui/viewport_3d.py` — forward drop to MainWindow.
- `.product/src/openrepose/gui/viewport_openpose.py` — forward drop to MainWindow.
- `.product/tests/test_drag_and_drop.py` (NEW)

### Build / Output

- `target/test-artifacts/WP-I1-005/`

## Risks And Dependencies

- **Risk**: Windows Explorer drops can include shell-link `.lnk` files that resolve to images; resolution may surprise the operator. **Mitigation**: reject `.lnk`; require a real image MIME type.
- **Risk**: multi-file drop ambiguity. **Mitigation**: accept the first image, log WARN listing the ignored files; do not silently iterate.
- **Dependency**: WP-I0-004 (`MainWindow` + `import_portrait` command) must be DONE.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Drop a PNG onto the central widget — `import_portrait` dispatched with the file path.
- [ ] Drop a JPG onto either viewport pane — dispatched the same way.

### Code Correctness Tests
- [ ] `dragEnterEvent` accepts `image/png` + `image/jpeg` and rejects everything else.
- [ ] Multi-file drop logs WARN listing ignored entries; first image still imports.
- [ ] Non-image MIME (`text/plain`, `application/pdf`) rejected without crash.

### Red-Team / Abuse Tests
- [ ] Drop of a 4 GB file: rejected before the AppState mutates (size check), WARN logged.
- [ ] Drop of a `.lnk` shell link: rejected.
- [ ] Drop of a path containing forbidden yaw phrases in its filename: import proceeds (filename is data), but no GUI text echoes the path verbatim into a label that would render the phrase.

### Performance / Reliability Tests
- [ ] Drop-to-rig-fit latency comparable to File > Open path (within 50ms).

## Rollback Plan

- Files to revert: `gui/main_window.py`, `gui/viewport_3d.py`, `gui/viewport_openpose.py`, the new test file.
- Files to keep: nothing else affected.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/gui/main_window.py .product/src/openrepose/gui/viewport_3d.py .product/src/openrepose/gui/viewport_openpose.py .product/tests/test_drag_and_drop.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row.
2. Implementation: drop handlers on MainWindow + forwarders on the two viewports.
3. Verification: pytest-qt suite + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_drag_and_drop.py --junitxml=target/test-artifacts/WP-I1-005/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-005/pytest_results.xml`
- **Claim Standard**: never mark `DONE` without junit XML evidence plus a manual drag from Explorer.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-005/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: marked N/A with reason (operator-only convenience; LLM uses `import_portrait`).

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
