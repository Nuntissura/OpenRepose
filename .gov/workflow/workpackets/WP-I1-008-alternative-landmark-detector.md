# WP-I1-008 - Alternative Landmark Detector Research + Benchmark

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: RESEARCH (split into a follow-up IMPLEMENTATION WP if results justify)
- **Effort Estimate**: M
- **Linked Spec**: future spec section "Alternative landmark detector".

## Intent

Investigate landmark detectors that may track stylized features (oversized eyes, extra-wide thin mouths, narrow jaws) better than MediaPipe FaceMesh. Run each candidate against the WP-I0-003 diagnostic on the Aeri master and quantify fidelity. Output a written recommendation; if any candidate clearly outperforms FaceMesh AND has acceptable license terms, open a follow-up IMPLEMENTATION WP to wire it in as a selectable detector.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 (foundation), WP-I0-003 (the diagnostic that motivated this).
- **Related**: WP-I1-001 calibration overlay (parallel mitigation; if a better detector lands, calibration may need fewer markers).

## Reality Boundary

- **Real Seam**: install each candidate detector in a sandboxed venv, run on the Aeri master, measure mouth/face_width ratio, eye/face_width ratio, mouth-extends-past-eyes boolean against the master prompt's intended values.
- **User-Visible Win**: a written recommendation in `.gov/doc/landmark_detector_benchmark_<date>.md` with per-detector quantitative scores and license summaries.
- **Proof Target**: the report exists and includes ALL of: dlib 68-point + iris, FaceMesh (baseline), one or two newer candidates (e.g., insightface, FaceSync), and a license review for each.

## In Scope

- Sandboxed install + minimal-glue invocation of each candidate.
- Standard test set: at minimum the Aeri master plus 2-3 other stylized faces from operator-authorized portraits.
- Quantitative table: mouth/face ratio, eye/face ratio, jaw outline RMS error vs operator marks.
- License + commercial-use review per candidate.
- Recommendation: which (if any) to wire into OpenRepose as a selectable detector.

## Out Of Scope

- Actually wiring a new detector — that's a follow-up WP if results justify.
- Training a custom landmark model.

## Headless LLM Operation Compliance

- [x] N/A — pure RESEARCH. No product code change. The follow-up IMPLEMENTATION WP (if opened) will satisfy the rule via a `set_landmark_detector` command and a snapshot for visual A/B.

## Definition Of Done

- [ ] Benchmark report saved at `.gov/doc/landmark_detector_benchmark_<date>.md`.
- [ ] Quantitative table for at least 4 candidates.
- [ ] License notes per candidate.
- [ ] Recommendation block.
- [ ] If recommendation is "wire candidate X", open follow-up IMPLEMENTATION WP.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Future Spec Areas / Alternative landmark detector placeholder; the WP-I0-003 wireframe-fidelity diagnostic motivates this RESEARCH.
- `.gov/AGENTS.md` — Headless LLM Operation Rule (RESEARCH WP; no product code change. Any follow-up IMPLEMENTATION WP will satisfy the rule).

## Linked Test Suite

- `.product/tests/test_landmark_detector_benchmark.py` (NEW) — runs each candidate detector on the operator-authorized fixture set, records the metrics, asserts all candidates produced numeric output without crashing.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-008-alternative-landmark-detector.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/doc/landmark_detector_benchmark_2026-05-02.md` (NEW report)

### Product (`.product/`)

- `.product/tests/test_landmark_detector_benchmark.py` (NEW)
- `.product/tests/fixtures/landmark_benchmark/` (NEW — operator-authorized stylized portraits)

### Build / Output

- `target/test-artifacts/WP-I1-008/per_detector/` — per-candidate JSON metrics + overlay PNGs.
- `target/test-artifacts/WP-I1-008/summary_table.csv` — quantitative table.

## Risks And Dependencies

- **Risk**: candidate detectors have incompatible licensing (commercial-use restrictions, attribution requirements). **Mitigation**: write a license summary per candidate before installing; reject any detector whose license blocks operator's intended use.
- **Risk**: candidate dependencies pollute the main venv. **Mitigation**: install each candidate in an isolated venv under `target/sandbox-<detector>/`; never modify the main `.venv`.
- **Dependency**: WP-I0-003 diagnostic methodology + Aeri master fixture; operator authorization for any extra fixture portraits.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Each candidate produces a non-empty landmark set on the fixture portraits.
- [ ] Quantitative metrics (mouth/face_width ratio, eye/face_width ratio, jaw RMS error) computed for every (detector, fixture) pair.

### Code Correctness Tests
- [ ] Metric computation is deterministic across runs (same input -> same output).
- [ ] CSV summary matches the per-detector JSON files.

### Red-Team / Abuse Tests
- [ ] No fixture portrait carrying a forbidden yaw phrase in metadata or filename ends up in committed assets.
- [ ] Sandboxed venvs do not leak into the main project's `pip list`.

### Performance / Reliability Tests
- [ ] Each candidate's runtime per portrait recorded in the summary; outliers > 30s flagged for the recommendation block.

## Rollback Plan

- Files to revert: WP file moves to archive `CANCELLED`; benchmark report deleted; sandbox venvs purged.
- Files to keep: any fixture portraits the operator wants to retain for future WPs.
- Recovery command: `git restore --staged .gov/ .product/; git checkout -- .gov/doc/landmark_detector_benchmark_2026-05-02.md; rm -rf target/sandbox-*`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + benchmark report skeleton.
2. Implementation: per-detector sandbox + metric computation + benchmark runner.
3. Verification: pytest + summary CSV + recommendation block in report.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_landmark_detector_benchmark.py --junitxml=target/test-artifacts/WP-I1-008/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-008/pytest_results.xml` + `summary_table.csv` + `.gov/doc/landmark_detector_benchmark_2026-05-02.md`.
- **Claim Standard**: never mark `DONE` without the report containing per-detector quantitative scores, license notes, and an explicit recommendation block.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-008/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths (report, summary CSV, per-detector overlays).
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: marked N/A with reason (pure RESEARCH; no product code change).

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
