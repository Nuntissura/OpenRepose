# WP-I1-026 - Feature 2 Calibration Overlay Spec

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Last Updated**: 2026-05-02
- **Status**: DONE
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: DOCUMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` — extends with new top-level "Feature 2: Per-Avatar Calibration Overlay" section between Feature 1 and the "Project-Wide Principle: Headless LLM Operation" section.
- **Linked Test Suite**: N/A (DOCUMENTATION-class)
- **Linked Check Script**: N/A

## Intent

Promote the one-line calibration-overlay placeholder in the I1 roadmap (`openrepose_v0_1.md` ~line 402) to a full Feature 2 spec block matching the depth of Feature 1: purpose, inputs, marker schema, deformation algorithm, application flow, persistence, GUI requirements, command surface, state-file reflection, snapshot target, out of scope, reality boundary. Locks the deformation algorithm choice (thin-plate spline via `scipy.interpolate.RBFInterpolator`), the marker vocabulary, the calibration JSON schema, and the four LLM commands so WP-I1-001 can implement against a stable contract without further spec churn.

## Linked Workpackets

- **Predecessor(s)**: I0 chain (DONE 2026-05-02). Feature 1 spec is the structural reference.
- **Successor(s)**: WP-I1-001 (Per-Avatar Calibration Overlay, IMPLEMENTATION). Cannot start until this WP is DONE.
- **Blocks**: WP-I1-001.
- **Blocked-By**: none.
- **Related**: WP-I1-009 (identity-export profiles — composes naturally with calibrated rigs); I2 theme "per-feature-group calibration mixing" (extension of this feature).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — new "Feature 2: Per-Avatar Calibration Overlay" section authored.
- `.gov/AGENTS.md` — Headless LLM Operation Rule (calibration commands, state block, and snapshot target must be reachable headlessly).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-02 | scikit-image stable docs (TPS) | https://scikit-image.org/docs/stable/auto_examples/transform/plot_tps_deformation.html | `ThinPlateSplineTransform.from_estimate(dst, src)` — clean coord-pair API. Documented for non-linear smooth warps; recommended over piecewise-affine which shows triangle-edge artifacts. | adapt (use the algorithm via scipy to avoid new direct dep) |
| 2026-05-02 | scikit-image PiecewiseAffineTransform docs | https://scikit-image.org/docs/stable/auto_examples/transform/plot_piecewise_affine.html | Delaunay-based; visible C0 discontinuities at triangle edges. Standard caution for face warping where artifacts on cheek/jaw boundaries are highly visible. | reject as primary |
| 2026-05-02 | Khanhha TPS warping notes | https://khanhha.github.io/posts/Thin-Plate-Splines-Warping/ | TPS naturally decomposes into global affine + local non-affine; the non-affine bending energy is the smoothness penalty. Edge over-shoot is real with sparse control points; mitigated by adding implicit anchor points on the image perimeter so far-from-marked regions stay near identity. | adopt clamping strategy |
| 2026-05-02 | Wikipedia TPS | https://en.wikipedia.org/wiki/Thin_plate_spline | Confirms math. 2D RBF kernel `phi(r) = r^2 log(r)`. Standard everywhere. | adopt |
| 2026-05-02 | scipy `RBFInterpolator` | https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.RBFInterpolator.html | `kernel="thin_plate_spline"` available; minimum 3 control points (rank deficiency below). Already pulled in transitively via mediapipe. Ideal for coord-only landmark transform — no source-image warp needed. | adopt as backend |

Decision: lock the deformation algorithm to thin-plate spline applied to landmark **coordinates only** (not source-image pixels) via `scipy.interpolate.RBFInterpolator(kernel="thin_plate_spline")`. Edge stability is provided by 4 implicit corner clamp points the operator does not see. Avoids adding scikit-image as a direct dep and keeps the math identical to the published TPS literature.

## Reality Boundary

- **Real Seam**: a real Markdown spec section exists in `openrepose_v0_1.md` between the existing Feature 1 block and the "Project-Wide Principle: Headless LLM Operation" section, locking the deformation algorithm, marker schema, calibration JSON schema, GUI surface, command set, state-file shape, and snapshot target for WP-I1-001 to implement against. The roadmap entry on line ~402 cross-references the new section.
- **User-Visible Win**: the next assistant who picks up WP-I1-001 reads the Feature 2 spec, copies the marker schema and command set into the implementation, and does not need to research deformation algorithms again.
- **Proof Target**: `git diff` shows a new "## Feature 2: Per-Avatar Calibration Overlay" section in the spec; the I1 roadmap entry cross-references it; `pwsh scripts/audit-repo.ps1` exits 0 (the new WP is at Workflow Version 1.1 and is DOCUMENTATION-class, so Research Notes are not audited but are present anyway).
- **Allowed Temporary Fallbacks**: none.
- **Promotion Guard**: none — DOCUMENTATION-only WP, no fallbacks shipped.

## In Scope

- Insert a new "## Feature 2: Per-Avatar Calibration Overlay" section in `.gov/spec/openrepose_v0_1.md` between Feature 1's "Reality Boundary For v0.1" subsection and "## Project-Wide Principle: Headless LLM Operation". Subsections (mirrors Feature 1 depth): Purpose, Inputs, Marker Schema, Deformation Algorithm, Application Flow, Persistence, GUI Requirements, Command Surface, State File Reflection, Snapshot Target, Out Of Scope For v0.1, Reality Boundary For v0.1.
- Update the I1 roadmap entry for WP-I1-001 (currently a one-liner on `openrepose_v0_1.md` ~line 402) to cross-reference the new Feature 2 section.

## Out Of Scope

- Implementation of any code under `.product/`. That is WP-I1-001's responsibility.
- Editing WP-I1-001's existing field text. WP-I1-001 stays at DRAFT after this WP closes; it will be promoted by the operator when ready, and the next assistant aligns field names from the spec at that point.
- 3D calibration, animated calibration, per-feature-group mixing, cross-avatar reuse, source-image warping — explicitly listed as Out Of Scope inside the new spec section.

## Expected Files Touched

### Governance (`.gov/`)
- `.gov/workflow/workpackets/WP-I1-026-feature-2-calibration-spec.md` (this WP) → archived to `.gov/workflow/archive/` on close.
- `.gov/workflow/TASKBOARD.md` — Active row added at READY, then moved to Recently Done on close.
- `.gov/spec/openrepose_v0_1.md` — new Feature 2 section + roadmap cross-reference.

### Product (`.product/`)
- (none)

### Build / Output
- (none)

## Risks And Dependencies

- **Risk**: spec text drifts from what WP-I1-001 wants to implement, forcing back-and-forth. **Mitigation**: spec is permissive about marker-set extension (operator skipping a feature group is allowed) and locks only the algorithm + JSON schema + command names, not internal data structures.
- **Risk**: scipy's `RBFInterpolator` API changes in a future version. **Mitigation**: spec names the algorithm (TPS) and the kernel string, not the import path; WP-I1-001 implementation can wrap it.
- **Dependency**: none external; uses existing transitive scipy.

## Definition Of Done

- [ ] `.gov/spec/openrepose_v0_1.md` contains a new "## Feature 2: Per-Avatar Calibration Overlay" section between Feature 1's last subsection and "## Project-Wide Principle: Headless LLM Operation".
- [ ] The new section has all 12 subsections listed In Scope.
- [ ] The I1 roadmap entry for WP-I1-001 cross-references the new section by anchor.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0 on the live tree.
- [ ] `pytest` zero failures (no behavior changed; documentation-only WP).
- [ ] Operator sign-off recorded in Evidence.

## Test Coverage Plan

DOCUMENTATION-class. No new tests. Verification is the audit + a clean pytest run.

### Functional Flow Tests
- N/A
### Code Correctness Tests
- N/A
### Red-Team / Abuse Tests
- N/A
### Performance / Reliability Tests
- N/A

## Rollback Plan

- Files to revert: `.gov/spec/openrepose_v0_1.md`, this WP file, taskboard row.
- Recovery: `git restore .gov/spec/openrepose_v0_1.md .gov/workflow/TASKBOARD.md` and `git rm` the archived WP file if applicable.

## Decisions Log

- 2026-05-02: Lock deformation algorithm to TPS via `scipy.interpolate.RBFInterpolator(kernel="thin_plate_spline")`. Reason: smoother than PiecewiseAffine for sparse control points; coordinate-only transform avoids image-warp cost; no new direct dep (scipy is already present transitively via mediapipe). Alternatives considered: scikit-image `ThinPlateSplineTransform` (rejected: new direct dep), OpenCV `createThinPlateSplineShapeTransformer` (rejected: awkward API for coord-only use case), hand-rolled TPS (rejected: scipy is well-tested and faster to maintain).
- 2026-05-02: Marker schema uses anatomical names (`eye_outer_left`, etc.) anchored to the her-anatomy convention. Reason: consistent with the yaw lock; predictable to operators; no left/right ambiguity. Alternatives: numeric IDs (rejected: opaque), MediaPipe landmark indices (rejected: leaks implementation detail and breaks if MediaPipe model versions shift indices).
- 2026-05-02: 4 implicit corner clamp points add stability at the image perimeter without operator action. Reason: TPS over-shoots near sparse control points; corner clamps prevent runaway deformation in unmarked regions (especially the body region, which is far from the face-region marks).

## Fallback Register

- (none — DOCUMENTATION WP)

## Change Ledger

- **What Became Real**: a new "## Feature 2: Per-Avatar Calibration Overlay" section landed in `.gov/spec/openrepose_v0_1.md` between Feature 1's "Reality Boundary For v0.1" and "## Project-Wide Principle: Headless LLM Operation". 12 subsections (Purpose, Inputs, Marker Schema, Deformation Algorithm, Application Flow, Persistence, GUI Requirements, Command Surface, State File Reflection, Snapshot Target, Out Of Scope For v0.1, Reality Boundary For v0.1) match the depth of Feature 1. The deformation algorithm is locked to TPS via `scipy.interpolate.RBFInterpolator(kernel="thin_plate_spline")` operating on landmark coordinates only (no source-image warp). The marker vocabulary is fixed to 6 required + 4 optional anatomical names anchored to the her-anatomy convention. The calibration JSON schema is locked at `schema_version: 1`. The four LLM commands (`set_calibration_points`, `dump_calibration`, `clear_calibration`, `get_calibration_status`) are enumerated. The state-file `calibration` block is enumerated. The `calibration_overlay` snapshot target is declared. The I1 roadmap entry for WP-I1-001 was updated to cross-reference the new section and to include the fourth command (`get_calibration_status`) which the original placeholder line was missing.
- **What Remains Simulated**: nothing — DOCUMENTATION-only WP, no fallbacks shipped. The spec section itself notes that `partial` calibrations (missing required markers) default to MediaPipe positions for those markers; that fallback path is part of the locked contract, not a temporary one.
- **Next Blocking Real Seam**: WP-I1-001 (IMPLEMENTATION) can now start — its DOCUMENTATION predecessor is satisfied. WP-I1-001's existing field text (Reality Boundary, Definition of Done, Files Touched) was authored before this spec section existed and may need a small alignment pass when the operator promotes WP-I1-001 to READY; the spec is the canonical source.

## Checkpoint Commit Plan

Single bundled commit (governance-confined; Work-Start Protocol exempt): WP file at READY + taskboard row + spec extension + WP closure (status DONE, archive, taskboard row -> Recently Done).

## Proof Of Implementation

- **Command Runs**: `pwsh scripts/audit-repo.ps1` (exit 0); `git diff` shows the new spec section.
- **Proof Artifact**: `target/test-artifacts/WP-I1-026/` (audit log only — no code, no pytest artifacts beyond the existing suite).
- **Claim Standard**: never mark DONE without operator sign-off and clean audit.

## Headless LLM Operation Compliance

- [x] N/A — DOCUMENTATION-class, no operator-facing surface, no commands, no state, no snapshot. The spec section being authored will itself impose Headless Compliance requirements on WP-I1-001's implementation (commands, state block, snapshot target enumerated in the spec).

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects DONE.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Audit script exits 0.
- [ ] pytest zero failures.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded.
- [ ] Headless LLM Operation Compliance marked N/A with reason.

## Evidence

- **Spec Diff**: `git show <commit> -- .gov/spec/openrepose_v0_1.md` shows the new "## Feature 2: Per-Avatar Calibration Overlay" section (12 subsections) plus the I1 roadmap cross-reference update.
- **Audit Run**: `pwsh scripts/audit-repo.ps1` exits 0 on the live tree post-commit.
- **Test Suite Execution**: full `pytest` run remains green (no product code changed; documentation-only WP).
- **Build Artifacts**: none beyond the spec edit.
- **Proof Artifact**: `target/test-artifacts/WP-I1-026/` (audit log + git-diff snapshot if archived).
- **Operator Sign-off**: 2026-05-02: APPROVED by operator after reading the new Feature 2 spec section and the TPS-via-scipy algorithm choice. WP-I1-001 authorized to start.

## Progress Log

- 2026-05-02: WP drafted at READY status (DOCUMENTATION-class, governance-confined; Work-Start Protocol exempt). Research-First pass complete (TPS via scipy locked).
- 2026-05-02: Spec extension authored. New "Feature 2: Per-Avatar Calibration Overlay" section added between Feature 1's last subsection and the Project-Wide Principle section. I1 roadmap entry for WP-I1-001 updated to cross-reference the new section and include the fourth command. Status READY -> REVIEW awaiting operator sign-off on the spec wording and TPS-via-scipy algorithm choice.
- 2026-05-02: Operator sign-off APPROVED. Status REVIEW -> DONE. WP archived to `.gov/workflow/archive/`. WP-I1-001 unblocked.
