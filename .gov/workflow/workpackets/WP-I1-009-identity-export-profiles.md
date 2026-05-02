# WP-I1-009 - Identity-Export Profiles

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: future spec section "Identity-export profiles".

## Intent

Produce locked face/body identity exports for downstream face-swap and img2img conditioning. An identity profile is a structured bundle of: cropped face reference, normalized face landmarks, key feature measurements, OpenPose body landmark snapshot, plus pose metadata. Designed to feed into ComfyUI face-swap workflows and into IPAdapter/InstantID-style identity-conditioning workflows.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 (foundation); ideally WP-I1-001 calibration overlay (more accurate landmarks).
- **Related**: WP-I1-007 pitch/roll (identity profile may want full head pose).

## Reality Boundary

- **Real Seam**: new `identity.py` module that takes a Rig + RotatedRig and serializes a structured profile (JSON + bundled PNG crops) to disk.
- **User-Visible Win**: operator runs `export_identity_profile`; downstream ComfyUI workflows consume the bundle directly without re-running landmark detection.
- **Proof Target**: a sample identity bundle is loadable in a ComfyUI workflow with at least IPAdapter face conditioning and gives a coherent generation.

## In Scope

- Profile schema (face crop dimensions, landmark coordinates, feature measurements, pose metadata).
- Bundle layout under `outputs/<avatar-slug>/identity/<run-tag>/` with `profile.json` + accompanying PNG crops.
- New command `export_identity_profile`; new snapshot target `identity_profile`.
- Tests: round-trip JSON, sample bundle creation.

## Out Of Scope

- Specific ComfyUI workflow integration (this WP produces the bundle; integration is operator-side).
- Training of identity-conditioning models.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via `export_identity_profile`.
- [ ] State reflected in `state.json` exports list with type=`identity_profile`.
- [ ] Snapshot target `identity_profile` shows the bundle's face crop with landmark overlay.
- [ ] No focus theft / modal dialogs from LLM commands.
- [ ] Tests cover the headless command path.

## Definition Of Done

- [ ] Bundle schema documented.
- [ ] Command produces a valid bundle.
- [ ] Sample bundle inspected manually in ComfyUI; at least one downstream workflow consumes it successfully.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Future Spec Areas / Identity-export profiles; Output Formats; LLM Control Surface (new command).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (`export_identity_profile` reachable via command channel; new snapshot target).

## Linked Test Suite

- `.product/tests/test_identity_profile.py` (NEW) — round-trip schema, bundle layout, snapshot target, downstream-loadability smoke.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-009-identity-export-profiles.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — promote identity-export-profiles placeholder to a full spec section (schema + bundle layout).

### Product (`.product/`)

- `.product/src/openrepose/identity.py` (NEW) — profile builder, schema definition, bundle writer.
- `.product/src/openrepose/commands.py` — register `export_identity_profile`.
- `.product/src/openrepose/state.py` — exports list entry with `type="identity_profile"`.
- `.product/src/openrepose/snapshot.py` — register `identity_profile` snapshot target.
- `.product/src/openrepose/render/draw_openpose.py` — face-crop landmark overlay used by the snapshot target.
- `.product/src/openrepose/gui/inspector.py` — new identity-profile readout row.
- `.product/tests/test_identity_profile.py` (NEW)

### Build / Output

- `outputs/<avatar-slug>/identity/<run-tag>/profile.json`
- `outputs/<avatar-slug>/identity/<run-tag>/face_crop.png`
- `outputs/<avatar-slug>/identity/<run-tag>/landmark_overlay.png`
- `target/test-artifacts/WP-I1-009/`

## Risks And Dependencies

- **Risk**: schema drift between identity-bundle producers and ComfyUI consumers. **Mitigation**: include `schema_version` in `profile.json`; document the contract in the spec section.
- **Risk**: face-crop dimensions vary across portraits and break IPAdapter expectations. **Mitigation**: standardize crop to a configurable square (default 512x512) with operator override.
- **Dependency**: WP-I0-001..004 (foundation); ideally WP-I1-001 calibration overlay so landmarks reflect stylized features accurately.

## Test Coverage Plan

### Functional Flow Tests
- [ ] `export_identity_profile` produces all three bundle files at the expected paths.
- [ ] `state.json` exports list gains an entry with `type="identity_profile"` and the run-tag.
- [ ] `snapshot {target: "identity_profile"}` returns a non-empty PNG.

### Code Correctness Tests
- [ ] Round-trip: `load(save(profile)) == profile` for the schema.
- [ ] Bundle layout matches the spec (filenames, directory, JSON schema).
- [ ] Landmark coordinates in `profile.json` match the rotated rig within tolerance.

### Red-Team / Abuse Tests
- [ ] `export_identity_profile` with an unfit rig: structured ERR, no partial bundle written.
- [ ] Path traversal in `run_tag` (e.g., `../../etc`): rejected.
- [ ] No bundle path or filename contains a forbidden yaw phrase.

### Performance / Reliability Tests
- [ ] Bundle write under 200ms on the operator's reference machine.

## Rollback Plan

- Files to revert: `identity.py`, `commands.py`, `state.py`, `snapshot.py`, `render/draw_openpose.py`, `gui/inspector.py`, the new test file.
- Files to keep: any operator-confirmed bundles already exported under `outputs/`.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/identity.py .product/src/openrepose/commands.py .product/src/openrepose/state.py .product/src/openrepose/snapshot.py .product/src/openrepose/render/draw_openpose.py .product/src/openrepose/gui/inspector.py .product/tests/test_identity_profile.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec section.
2. Implementation: `identity.py` + dispatcher + state list entry.
3. Snapshot wiring + GUI readout.
4. Verification: pytest + downstream ComfyUI smoke.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_identity_profile.py --junitxml=target/test-artifacts/WP-I1-009/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-009/pytest_results.xml` plus a sample bundle archived under that dir.
- **Claim Standard**: never mark `DONE` without junit XML evidence and a manually-verified ComfyUI workflow that consumes the bundle.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-009/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths (sample bundle, ComfyUI screenshot).
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
