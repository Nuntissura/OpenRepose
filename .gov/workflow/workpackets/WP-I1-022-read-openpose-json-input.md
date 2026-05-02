# WP-I1-022 - Read OpenPose JSON As Alternate Input

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / Inputs (extend to accept JSON input alongside portrait input).

## Intent

Add a second import path: operator (or LLM) provides an existing OpenPose-format JSON file (the keypoints structure, not a rendered image) and OpenRepose loads the keypoints into AppState directly, skipping the rig fit. This is the trivial inverse of our serialization: every JSON we produce, plus every JSON DWPose / ComfyUI / external tools produce, can be re-loaded.

Use cases: reframe an existing OpenPose set without re-running landmark detection on the source photo; combine with WP-I1-023 reframing for portrait-bias correction; iterate on existing batches without re-fitting.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 must reach DONE.
- **Successor(s)**: WP-I1-023 (frame reframing) consumes this path equally with the rig path.

## Reality Boundary

- **Real Seam**: new `import_openpose_json` command + `Edit → Import OpenPose JSON...` menu. Loads the JSON, validates schema, populates a new `JsonOnlyState` field on AppState (parallel to `Rig`). Yaw / rotation commands return a structured error when only JSON is loaded ("yaw rotation requires a rig; current input is JSON-only"). Reframing (WP-I1-023) and snapshot subsystem work either way.
- **User-Visible Win**: operator drags a `.json` produced by ComfyUI's DWPreprocessor (or a previous OpenRepose batch) into the GUI; viewports populate showing the imported keypoints; operator reframes / re-exports without rerunning rig fit.
- **Proof Target**: pytest covers round-trip (export from rig -> import JSON -> re-export -> identical to first export); manual: import a DWPose-derived JSON from ComfyUI and verify the OpenPose preview matches.

## In Scope

- New command `import_openpose_json {path}`.
- JSON schema validator (matches the schema OpenRepose's serializer produces; tolerant of optional fields like missing hands).
- AppState extension: a `JsonOnlyKeypoints` data class holding body_18 + face_70 + hands + canvas dimensions.
- GUI menu entry + drag-and-drop accepts `.json` (relying on WP-I1-005 drag-and-drop infrastructure).
- Toolbar disables yaw slider + bin dropdown when in JSON-only mode (with a tooltip explaining why).
- Tests: round-trip JSON; malformed JSON rejected; partial schema (missing hands, missing face) accepted with WARN.

## Out Of Scope

- Reading an OpenPose PNG image (reverse-engineer keypoints from rendered colored skeleton). Would need RESEARCH WP first.
- Detecting OpenPose JSON variants from other tools (different schemas). Stick to the canonical schema produced by OpenPose / DWPose / OpenRepose.

## Risks And Dependencies

- **Risk**: imported JSON may lack canvas dimensions; default to a sensible canvas if missing and emit WARN.
- **Risk**: imported JSON keypoints may have different coordinate ranges than expected (e.g., normalized 0..1 vs pixel). Validate and reject gracefully.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via `import_openpose_json`.
- [ ] State reflected in `state.json` (new `input_type`: `rig` | `json` | `none`).
- [ ] LLM pulls visual via existing `openpose_viewport` snapshot (renders directly from imported keypoints).
- [ ] No focus theft / modal dialogs.
- [ ] Tests cover headless command path.

## Definition Of Done

- [ ] `import_openpose_json` command works headlessly and via the menu.
- [ ] OpenPose preview renders from imported keypoints.
- [ ] Yaw controls disabled with tooltip in JSON-only mode.
- [ ] Round-trip test passes (export from rig -> import JSON -> re-export equals first).
- [ ] Schema validation rejects malformed JSON with structured ERR.
- [ ] Full project suite green.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / Inputs (extend to JSON path); LLM Control Surface (`import_openpose_json`); state schema gains `input_type`.
- `.gov/AGENTS.md` — Headless LLM Operation Rule (`import_openpose_json` reachable headlessly; existing snapshot targets render from imported keypoints).

## Linked Test Suite

- `.product/tests/test_import_openpose_json.py` (NEW) — round-trip, malformed-JSON rejection, partial-schema acceptance, JSON-only mode disables yaw controls.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-022-read-openpose-json-input.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — extend Inputs + LLM Control Surface; add `input_type` to state schema.

### Product (`.product/`)

- `.product/src/openrepose/openpose_serialize.py` — extract a JSON validator/loader (mirror of the writer).
- `.product/src/openrepose/commands.py` — register `import_openpose_json`.
- `.product/src/openrepose/state.py` — `input_type` (`rig` | `json` | `none`); `JsonOnlyKeypoints` data class.
- `.product/src/openrepose/render/draw_openpose.py` — render directly from `JsonOnlyKeypoints` if no rig.
- `.product/src/openrepose/gui/main_window.py` — `Edit → Import OpenPose JSON...` menu entry.
- `.product/src/openrepose/gui/toolbar.py` — disable yaw slider + bin dropdown in JSON-only mode with explanatory tooltip.
- `.product/tests/test_import_openpose_json.py` (NEW)
- `.product/tests/fixtures/sample_openpose.json` (NEW — ComfyUI/DWPose-derived sample).

### Build / Output

- `target/test-artifacts/WP-I1-022/`

## Risks And Dependencies

- **Risk**: imported JSON may use normalized 0..1 coords instead of pixels. **Mitigation**: validator detects coordinate range; auto-converts using canvas dimensions if present, otherwise rejects with structured ERR.
- **Risk**: missing canvas dimensions in imported JSON. **Mitigation**: default to a sensible canvas (1024x1024) and emit WARN; record the substitution in state.json.
- **Dependency**: WP-I0-001..004 (existing serializer + state machine). Composes with WP-I1-023 reframing.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Round-trip: export from rig -> `import_openpose_json` -> re-export -> identical to first export.
- [ ] DWPose-derived JSON (sample fixture) imports and renders in the OpenPose viewport.
- [ ] In JSON-only mode, yaw slider and bin dropdown are disabled with the documented tooltip.

### Code Correctness Tests
- [ ] Schema validator accepts the canonical OpenPose schema and OpenRepose's serializer output.
- [ ] Partial schema (missing hands or face): accepted with WARN; absent groups stay null.
- [ ] state.json `input_type` flips to `json` after import; back to `rig` after a subsequent `import_portrait`.

### Red-Team / Abuse Tests
- [ ] Malformed JSON (truncated, extra keys, wrong types): structured ERR; no state mutation.
- [ ] Yaw set-command in JSON-only mode: structured ERR ("yaw rotation requires a rig; current input is JSON-only"); no state mutation.
- [ ] No imported filename echoed into a label that would render a forbidden yaw phrase verbatim.

### Performance / Reliability Tests
- [ ] Import + render under 100ms for a typical OpenPose JSON (< 100KB).

## Rollback Plan

- Files to revert: `openpose_serialize.py`, `commands.py`, `state.py`, `render/draw_openpose.py`, `gui/main_window.py`, `gui/toolbar.py`, the new test and fixture.
- Files to keep: existing serializer behavior unchanged for the rig path.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/openpose_serialize.py .product/src/openrepose/commands.py .product/src/openrepose/state.py .product/src/openrepose/render/draw_openpose.py .product/src/openrepose/gui/main_window.py .product/src/openrepose/gui/toolbar.py .product/tests/test_import_openpose_json.py .product/tests/fixtures/sample_openpose.json`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec extension.
2. Implementation: validator + dispatcher + state.
3. GUI wiring: menu entry + toolbar disabled state + tooltip.
4. Verification: pytest + round-trip evidence + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_import_openpose_json.py --junitxml=target/test-artifacts/WP-I1-022/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-022/pytest_results.xml` plus the round-trip diff archived under that directory.
- **Claim Standard**: never mark `DONE` without junit XML evidence and a manual import of a DWPose-derived JSON.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-022/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
