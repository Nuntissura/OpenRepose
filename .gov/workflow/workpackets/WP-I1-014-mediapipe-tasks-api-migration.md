# WP-I1-014 - MediaPipe Tasks API Migration

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: INFRASTRUCTURE
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / Rig Construction (current dependency on `mp.solutions.face_mesh.FaceMesh` and `mp.solutions.pose.Pose`).

## Intent

Migrate `rig.py` from MediaPipe's deprecated `mp.solutions.*` Solutions API to the current `mp.tasks.vision.*` Tasks API. The Solutions namespace was dropped in mediapipe 0.10.30+; we currently pin `<0.10.30` to keep the old API working. Tasks API is forward-compatible and the documented path.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 must reach DONE.

## Reality Boundary

- **Real Seam**: rewrite `_run_mediapipe()` in `rig.py` to use `mp.tasks.python.vision.FaceLandmarker` and `mp.tasks.python.vision.PoseLandmarker`; bundle / download the `.task` model files (`face_landmarker.task`, `pose_landmarker_heavy.task`) at first run; update `pyproject.toml` to remove the upper bound on `mediapipe`.
- **User-Visible Win**: future MediaPipe upgrades (security patches, new features) work without breaking OpenRepose.
- **Proof Target**: full pytest suite passes with the latest mediapipe; rig fits on Aeri produce numerically equivalent landmarks (within tolerance) to the old Solutions API output.

## In Scope

- Switch FaceMesh → FaceLandmarker (Tasks API, refine_landmarks=True for iris).
- Switch Pose → PoseLandmarker.
- Model file management: bundle in `installers/` for the installer build, OR download on first run with cache under app-data dir.
- Numerical equivalence test: rig output on the Aeri master before/after migration is within 5px on every keypoint.
- Update test fixtures if Tasks API gives subtly different positions.
- Remove `mediapipe<0.10.30` upper bound in `pyproject.toml`.

## Out Of Scope

- Switching to a different landmark library (covered by WP-I1-008).
- Re-training or fine-tuning the landmark model.

## Risks And Dependencies

- **Risk**: Tasks API may produce subtly different landmark positions than Solutions API; existing per-avatar calibrations would need re-marking. **Mitigation**: numerical equivalence test gates the migration; if positions drift more than 5px, hold the migration and document.
- **Risk**: model file licensing — Google's `.task` files are under their AI Edge license terms; verify commercial-use compatibility.
- **Dependency**: build a download / cache mechanism for model files OR bundle them.

## Headless LLM Operation Compliance

- [x] N/A — INFRASTRUCTURE refactor. No new commands or visual surface.

## Definition Of Done

- [ ] All pytest passes with latest mediapipe + Tasks API.
- [ ] Numerical equivalence test confirms < 5px landmark drift on Aeri master.
- [ ] Model file management documented in README and topology.
- [ ] Upper bound on `mediapipe` removed from `pyproject.toml`.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / Rig Construction (currently uses `mp.solutions.face_mesh.FaceMesh` and `mp.solutions.pose.Pose`).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (INFRASTRUCTURE refactor; no command surface change but rig output must remain reachable through existing commands).

## Linked Test Suite

- `.product/tests/test_rig_tasks_api.py` (NEW) — numerical-equivalence check vs Solutions API on the Aeri master; first-run cache mechanism; full project suite with latest mediapipe.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-014-mediapipe-tasks-api-migration.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — update Rig Construction section to reference Tasks API.
- `.gov/topology.yaml` — document model file location.

### Product (`.product/`)

- `.product/src/openrepose/rig.py` — rewrite `_run_mediapipe()` against `mp.tasks.python.vision.FaceLandmarker` and `mp.tasks.python.vision.PoseLandmarker`.
- `.product/src/openrepose/state.py` — record model-file paths/versions in state telemetry.
- `.product/pyproject.toml` — remove the `mediapipe<0.10.30` upper bound.
- `.product/src/openrepose/_models.py` (NEW) — model file resolver: bundled location first, fallback to download cache.
- `.product/tests/test_rig_tasks_api.py` (NEW)
- `.product/tests/fixtures/aeri_master.png` (existing — referenced for equivalence test).

### Build / Output

- `<app-data>/openrepose/models/face_landmarker.task`
- `<app-data>/openrepose/models/pose_landmarker_heavy.task`
- `target/test-artifacts/WP-I1-014/`

## Risks And Dependencies

- **Risk**: Tasks API outputs differ from Solutions API beyond the 5px tolerance; existing per-avatar calibrations would need re-marking. **Mitigation**: numerical-equivalence test gates promotion; if delta exceeds 5px, hold the migration and document in the change ledger.
- **Risk**: model-file licensing (Google AI Edge terms). **Mitigation**: licensing review captured in `.gov/doc/mediapipe_tasks_license_review.md`; ship terms with the installer.
- **Dependency**: WP-I0-001..004 (foundation); operator approval of model-file distribution path (bundle vs download).

## Test Coverage Plan

### Functional Flow Tests
- [ ] `Rig.from_portrait(aeri_master.png)` succeeds with the Tasks API path.
- [ ] First-run downloads (or finds bundled) `.task` files and caches them; second run reuses cache.
- [ ] All existing rig-driven tests pass with the latest mediapipe.

### Code Correctness Tests
- [ ] Numerical equivalence: per-keypoint delta on Aeri master < 5px between old and new APIs.
- [ ] `_models.py` resolver returns the bundled path when present; falls back to download otherwise.
- [ ] `pyproject.toml` no longer pins `mediapipe<0.10.30`.

### Red-Team / Abuse Tests
- [ ] Missing model file + offline run: structured ERR with operator-actionable message; no crash.
- [ ] Tampered model file (wrong size): rejected by checksum; download retried once then ERR.

### Performance / Reliability Tests
- [ ] Rig fit time within 1.3x of Solutions API baseline on the operator's reference machine.

## Rollback Plan

- Files to revert: `rig.py`, `state.py`, `_models.py`, `pyproject.toml`, the new test file.
- Files to keep: cached `.task` files under `<app-data>/openrepose/models/` (harmless if API reverts).
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/rig.py .product/src/openrepose/state.py .product/src/openrepose/_models.py .product/pyproject.toml .product/tests/test_rig_tasks_api.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec update + license review.
2. Implementation: rewrite `_run_mediapipe` against Tasks API + model resolver.
3. Numerical-equivalence verification: pytest with side-by-side comparison on Aeri master.
4. Verification: full project suite + junit XML + lift the version pin.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_rig_tasks_api.py --junitxml=target/test-artifacts/WP-I1-014/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-014/pytest_results.xml` plus per-keypoint delta CSV vs Solutions API.
- **Claim Standard**: never mark `DONE` without junit XML evidence and the < 5px delta CSV archived in Evidence.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-014/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths (delta CSV, license review).
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: marked N/A with reason (INFRASTRUCTURE refactor; no command surface change).

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
