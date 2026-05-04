# WP-I1-010 - Multi-Angle Automation

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Status**: REVIEW
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Output Formats + LLM Control Surface (`export_batch`).

## Intent

Extend `export_batch` so each angle in the batch can carry an operator-defined prompt seed, sampler config, or downstream-workflow dispatch. Use case: operator wants to generate, for the same avatar, the 13-angle yaw set with different prompt slugs (e.g., outfit variations) AND have the manifest record which slug was used for which angle.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 (foundation).
- **Related**: WP-I1-009 identity-export profiles (could be combined into a workflow where each angle exports a full identity bundle).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-04 | JSON Schema object reference | https://json-schema.org/understanding-json-schema/reference/object | JSON Schema treats objects as key/value mappings and supports `additionalProperties`; for this WP, strict validation should apply to the envelope (`per_angle_metadata` list length/shape) while individual metadata dicts remain extensible data. | adapt |
| 2026-05-04 | Python `json` module docs | https://docs.python.org/3.14/library/json.html | Standard-library `json.dump` supports deterministic, human-readable manifest writes via `indent` and optional `sort_keys`; no dependency is needed for manifest extension. | adopt |
| 2026-05-04 | Existing OpenRepose export contract | local `.gov/spec/openrepose_v0_1.md` Output Formats and `.product/src/openrepose/openpose_serialize.py` | Current batch manifest is the correct seam; extend it without changing OpenPose JSON keypoint files. | adopt |

## Reality Boundary

- **Real Seam**: extend `_h_export_batch` to accept an optional `per_angle_metadata: list[dict]` aligned with `angles`. Each dict can carry arbitrary keys (e.g., `prompt_slug`, `seed`, `controlnet_strength`) that get persisted into the manifest.
- **User-Visible Win**: operator (or LLM) submits one batch command with per-angle metadata; manifest contains the full mapping; downstream workflow reads the manifest and dispatches the per-angle generations accordingly.
- **Proof Target**: pytest covers a mixed-metadata batch and the manifest round-trips; manual demo: a downstream Bash/PowerShell script reads the manifest and runs ComfyUI per-angle.

## In Scope

- `export_batch` command schema extended with `per_angle_metadata`.
- Manifest schema extended.
- Tests: empty metadata, partial metadata (some angles have, some don't), full metadata.

## Out Of Scope

- The downstream workflow dispatcher itself (operator's responsibility; this WP just produces the manifest).
- Cross-avatar batches (one avatar per batch).

## Headless LLM Operation Compliance

- [x] LLM agent triggers via the existing `export_batch` command with new optional fields.
- [x] State reflected in `state.json` exports list.
- [x] Snapshot subsystem unchanged.
- [x] No focus theft.
- [x] Tests cover the headless path.

## Definition Of Done

- [x] `export_batch` accepts `per_angle_metadata` and writes it into the manifest.
- [x] Tests cover three configurations (none / partial / full), plus mismatch/oversize/outside-angle rejection.
- [x] **Manual Impact**: Yes - extends `.gov/doc/manual/feature-1-yaw-exporter.md` with `per_angle_metadata` command shape and manifest behavior.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Future Spec Areas / Multi-angle automation; Output Formats (manifest schema); LLM Control Surface (`export_batch`).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (extension of `export_batch` keeps full headless coverage).

## Linked Test Suite

- `.product/tests/test_export_batch_per_angle.py` (NEW) — none / partial / full per-angle metadata; manifest schema round-trip; downstream-script consumption smoke.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-010-multi-angle-automation.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — extend manifest schema + `export_batch` command shape.

### Product (`.product/`)

- `.product/src/openrepose/commands.py` — extend `_h_export_batch` to accept `per_angle_metadata`.
- `.product/src/openrepose/openpose_serialize.py` — extend manifest writer with the metadata mapping.
- `.product/src/openrepose/state.py` — exports list entry retains the per-angle metadata pointer.
- `.product/tests/test_export_batch_per_angle.py` (NEW)

### Build / Output

- `outputs/<avatar-slug>/<run-tag>/manifest.json` — gains `per_angle_metadata` block.
- `target/test-artifacts/WP-I1-010/`

## Risks And Dependencies

- **Risk**: per-angle dicts drift in shape across LLM agents; manifest grows untyped. **Mitigation**: schema-validate well-known keys (`prompt_slug`, `seed`, `controlnet_strength`); allow but flag unknown keys with WARN.
- **Risk**: misalignment between `angles` list length and `per_angle_metadata` length. **Mitigation**: reject the command with a structured ERR before any file is written; do not silently truncate.
- **Dependency**: WP-I0-001..004 (existing `export_batch`).

## Test Coverage Plan

### Functional Flow Tests
- [ ] No metadata: existing batch flow unchanged.
- [ ] Partial metadata (some angles only): manifest contains entries only for the supplied angles.
- [ ] Full metadata: every angle carries its dict.

### Code Correctness Tests
- [ ] Manifest round-trip: write -> read -> identical dict.
- [ ] Length-mismatch case rejected before any file write.
- [ ] Unknown-key WARN logged but command succeeds.

### Red-Team / Abuse Tests
- [ ] `prompt_slug` containing forbidden yaw phrases: stored verbatim (data) but no GUI text constructs new yaw labels from these slugs.
- [ ] Extremely large per-angle dict (1MB) rejected with structured ERR.

### Performance / Reliability Tests
- [ ] 13-angle batch with full metadata writes within 1.1x of no-metadata baseline.

## Rollback Plan

- Files to revert: `commands.py`, `openpose_serialize.py`, `state.py`, the new test file.
- Files to keep: existing `manifest.json` files retain the older schema; loader remains backward-compatible.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/commands.py .product/src/openrepose/openpose_serialize.py .product/src/openrepose/state.py .product/tests/test_export_batch_per_angle.py`

## Decisions Log

- 2026-05-04: Keep per-angle metadata as manifest-only data. Reason: OpenPose JSON keypoint files should remain compatible with DWPose/RenderPeopleKps consumers; workflow metadata belongs in `manifest.json`.
- 2026-05-04: Validate envelope strictly and metadata dicts loosely. Reason: agents need stable list/angle alignment, but downstream workflow keys are intentionally operator/agent-defined.

## Fallback Register

- None.

## Change Ledger

- 2026-05-04: Promoted DRAFT -> IN-PROGRESS for autonomous implementation after operator requested all no-input WPs. Research notes added and spec/manual update planned before product edits.
- 2026-05-04: Implemented `export_batch.per_angle_metadata` as a yaw-bin keyed manifest object, with list-aligned and object-keyed input support, strict angle/list/size validation before output directory creation, unknown-key WARN preservation, and state export telemetry.
- 2026-05-04: Advanced IN-PROGRESS -> REVIEW after focused pytest, compileall, audit, and sample manifest proof.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec extension.
2. Implementation: dispatcher + serializer + state.
3. Verification: pytest + sample manifest.

## Proof Of Implementation

- **Command Runs**:
  - `.\.venv\Scripts\python.exe -m pytest .product/tests/test_export_batch_per_angle.py .product/tests/test_command_handlers.py .product/tests/test_export_png_and_json_format.py -q --tb=short --junitxml=target/test-artifacts/WP-I1-010/pytest_results.xml`
  - `.\.venv\Scripts\python.exe -m compileall -q .product\src\openrepose`
  - `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\audit-repo.ps1`
- **Proof Artifact**: `target/test-artifacts/WP-I1-010/pytest_results.xml` plus `target/test-artifacts/WP-I1-010/sample-manifest-proof.json`.
- **Claim Standard**: never mark `DONE` without operator sign-off.

## Exit Criteria

- [x] Definition of Done items all checked.
- [x] Taskboard row reflects current status.
- [x] Reality Boundary, Fallback Register, Change Ledger truthful.
- [x] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-010/pytest_results.xml`.
- [x] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [x] Headless LLM Operation Compliance: all items checked.

## Evidence

- 2026-05-04: Promoted DRAFT -> IN-PROGRESS; governance kickoff prepared before `.product/` edits.
- 2026-05-04: Focused pytest passed: `test_export_batch_per_angle.py`, `test_command_handlers.py`, `test_export_png_and_json_format.py` -> 19 passed in 47.48s; JUnit `target/test-artifacts/WP-I1-010/pytest_results.xml`.
- 2026-05-04: `compileall -q .product\src\openrepose` clean.
- 2026-05-04: `scripts/audit-repo.ps1` clean (project-rules-fresh skipped because `LIBRARY_DB_URL` unset).
- 2026-05-04: Sample proof written to `target/test-artifacts/WP-I1-010/sample-manifest-proof.json`; 3-angle batch manifest contains metadata for `0`, `her-left 15`, and `her-right 15`.

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
- 2026-05-04: Status DRAFT -> IN-PROGRESS; research recorded; implementation authorized by operator for autonomous overnight work.
- 2026-05-04: Product implementation and validation complete; status IN-PROGRESS -> REVIEW pending operator sign-off.
