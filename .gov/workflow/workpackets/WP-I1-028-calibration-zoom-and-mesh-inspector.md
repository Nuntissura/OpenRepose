# WP-I1-028 - Calibration Zoom And Frontal Mesh Inspector

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 2 / GUI Requirements (Calibration tab — extend with zoom + mesh inspector).
- **Linked Test Suite**: `.product/tests/test_calibration_gui.py` (extend) and `.product/tests/test_calibration_zoom.py` (NEW for the zoom-centric mapping math).
- **Linked Check Script**: N/A.

## Intent

Make the Calibration tab actually usable for marking small features on a stylized portrait. Two surfaces:
(a) **Mouse-wheel zoom + click-drag pan** on the master portrait — current full-fit display makes it hard to land a marker on a 5px feature like the outer eye corner.
(b) **Frontal mesh inspector** — a small collapsible widget showing the 3D rig's face mesh from the front (or any chosen angle). Has its own angle slider that rotates this preview only; does NOT mutate `state.yaw`, the active rig, or the OpenPose preview / export. Operator can sanity-check which detected landmark corresponds to which anatomical feature without losing their place on the active yaw.

Surfaced during WP-I1-001 GUI verification: operator confused jaw-corner markers without an independent mesh reference.

## Linked Workpackets

- **Predecessor(s)**: WP-I1-001 (Per-Avatar Calibration Overlay) — DONE 2026-05-03.
- **Successor(s)**: none planned.
- **Blocks**: none.
- **Blocked-By**: none.
- **Related**: WP-I1-002 (orbital camera in 3D viewport — independent scope; this WP's mesh inspector is a calibration helper, not a viewport feature).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` Feature 2 / GUI Requirements — extend the Calibration tab description with the zoom + mesh inspector additions.
- `.gov/AGENTS.md` Headless LLM Operation Rule — new widgets must not call focus-stealing APIs; no new commands needed (zoom + inspector are operator-side conveniences).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | PySide6 `QGraphicsView` docs | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsView.html | Replaces our current QLabel + manual coord mapping. Built-in `mapToScene()` for click → image coord. `setTransformationAnchor(AnchorUnderMouse)` for mouse-centered zoom. `setDragMode(ScrollHandDrag)` enables click-drag pan with no extra event handling. | adopt |
| 2026-05-03 | Qt Wiki "Smooth Zoom in QGraphicsView" | https://wiki.qt.io/Smooth_Zoom_In_QGraphicsView | Use `wheelEvent` with `event.angleDelta().y()` and `view.scale(factor, factor)`. Anchor-under-mouse keeps the cursor's image point fixed during zoom — the standard image-viewer UX. | adopt |
| 2026-05-03 | Existing `render/draw_3d.py` | local | The frontal mesh inspector can re-use `render_3d_viewport(rotated)` with a synthesized `RotatedRig` at any inspection angle. No new renderer needed; just construct a separate `RotatedRig` from `rig + bin_at_inspection_yaw` per refresh. | adopt |
| 2026-05-03 | PySide6 `QSlider` + `QGroupBox` collapse pattern | local stdlib knowledge | Qt has no native collapsible group; standard pattern is `QToolButton(checkable=True, arrow_type)` toggling visibility on a child container. Adequate for v0.1; no extra dep. | adopt |

Decision: replace `_ClickablePortrait(QLabel)` in `gui/calibration.py` with a `_ZoomableImageView(QGraphicsView)` that holds a `QGraphicsPixmapItem`. Mouse wheel zooms anchored under cursor; left-click + drag pans (Qt's `ScrollHandDrag`); single click in non-drag mode emits image-space (x, y) for marker placement. The mesh inspector is a new collapsible widget at the bottom of the Calibration tab using the existing `render/draw_3d.py` against a synthesized `RotatedRig` at the inspection-only yaw.

## Reality Boundary

- **Real Seam**: real `QGraphicsView`-based portrait viewer with mouse-wheel zoom + click-drag pan in the Calibration tab; real second wireframe rendering of the rig at an independent inspection yaw, displayed in a collapsible widget below the portrait. Both purely operator-facing; no LLM commands added; no spec contract change beyond GUI text.
- **User-Visible Win**: operator can zoom into the eye-outer-corner region, click precisely, see the operator marker land where they intended. They can scroll the inspector's angle slider to rotate the mesh view 0° → her-right 30 → her-right 60 to confirm which detected landmark is `jaw_corner_left` vs `jaw_corner_right` — without changing the active yaw or perturbing the OpenPose preview.
- **Proof Target**: pytest covers (a) zoom factor application + back-projection of click coords; (b) pan does not change image coords for a given click; (c) mesh inspector renders a non-empty image; (d) inspector slider does not mutate `state.yaw` or active rig; (e) collapsible widget toggles visibility. Manual: operator marks all 6 required points using zoom, exports at multiple yaw angles, confirms calibration looks right; inspector slider scans through angles without affecting export.
- **Allowed Temporary Fallbacks**: none.
- **Promotion Guard**: do not promote to DONE until the operator runs the calibration cycle with zoom enabled and confirms accurate marker placement; and confirms the inspector slider does not perturb active yaw / OpenPose preview / export output.

## In Scope

- Replace `_ClickablePortrait` in `gui/calibration.py` with `_ZoomableImageView(QGraphicsView)`. Mouse-wheel zoom anchored under cursor; click (no drag) emits image-space (x, y); left-click + drag pans. Reset-to-fit button next to the zoom area.
- Add a "Mesh inspector" collapsible widget below the portrait viewer in `gui/calibration.py`. Contents: small wireframe rendering of the rig face mesh + body skeleton; angle slider `[-90, +90]` (matches the toolbar slider's range); current angle readout.
- The inspector renders via the existing `render/draw_3d.py` `render_3d_viewport(rotated)` against a synthesized `RotatedRig` at the inspection-only angle. No state mutation: `state.yaw`, `dispatcher._rig`, OpenPose preview, and export output are untouched by inspector slider movement.
- Collapse / expand toggle (QToolButton arrow). Default expanded.
- Tests: extend `test_calibration_gui.py` with zoom + inspector cases; new `test_calibration_zoom.py` for the click-to-image-space mapping under various zoom + pan states.

## Out Of Scope

- Drag-to-move existing operator markers (defer to a separate polish WP).
- Right-click delete operator markers (defer).
- Mesh inspector with full pitch/roll (yaw only, mirroring v0.1 spec scope).
- Full rotation animation in the inspector (slider scrubs; no auto-play).
- A separate snapshot target for the inspector view (operator can grab the whole calibration_pane via `inspector_pane`-style widget grab if the WP-I0-003 widget provider is extended; not in scope here).
- Programmatic LLM control of zoom or inspector angle (operator-facing only; LLM uses commands).

## Expected Files Touched

### Governance (`.gov/`)
- `.gov/workflow/workpackets/WP-I1-028-calibration-zoom-and-mesh-inspector.md` (this file).
- `.gov/workflow/TASKBOARD.md` — Active row added at READY when promoted.
- `.gov/spec/openrepose_v0_1.md` — small extension of the Feature 2 / GUI Requirements text to mention zoom + inspector.

### Product (`.product/`)
- `.product/src/openrepose/gui/calibration.py` — replace `_ClickablePortrait` with `_ZoomableImageView`; add `_MeshInspector` collapsible widget; refactor layout; preserve existing click-to-set-marker semantics.
- `.product/tests/test_calibration_gui.py` — extend with zoom + collapse + slider-no-mutation tests.
- `.product/tests/test_calibration_zoom.py` (NEW) — focused mapping math (click coords back-project correctly under arbitrary zoom + pan).

### Build / Output (gitignored)
- `target/test-artifacts/WP-I1-028/`

## Risks And Dependencies

- **Risk**: `QGraphicsView`-based click handling may emit unintended clicks at the end of a pan drag. **Mitigation**: track press → release distance; only emit `clicked(x, y)` when the cursor moved less than ~3px between press and release.
- **Risk**: high-resolution masters in a small QGraphicsView could cause smooth-transformation artifacts. **Mitigation**: enable `setRenderHint(SmoothPixmapTransform)` on the view; cache the source pixmap.
- **Risk**: mesh inspector rendering on every refresh tick is wasteful (the inspector angle does not change during normal calibration work). **Mitigation**: only re-render the inspector when (a) the slider value changed, (b) the rig changed (re-fit / re-calibrated). Cache the last rendered image.
- **Risk**: synthesized `RotatedRig` at the inspection yaw could share state with the real RotatedRig. **Mitigation**: the inspector calls `rotate_yaw(rig, bin_obj)` separately each time; `RotatedRig` is a frozen dataclass with no shared mutable state.
- **Risk**: operator confuses inspector slider with the toolbar yaw slider and mutates the wrong one. **Mitigation**: inspector slider has a clear "INSPECT ONLY" label and lives in the collapsible widget; visually distinct color in the QSS.
- **Dependency**: existing `render/draw_3d.py`, `rotation.py`, `yaw_bin.py`. No new deps.

## Definition Of Done

- [ ] `_ZoomableImageView(QGraphicsView)` replaces `_ClickablePortrait`; mouse-wheel zoom anchored under cursor; click-drag pans; single click emits image-space coords accurately.
- [ ] `_MeshInspector` widget renders the rig at an independent yaw; slider scrubs `[-90, +90]`; collapse toggle works; `state.yaw` and active rig untouched by slider movement.
- [ ] Reset-zoom-to-fit button works.
- [ ] All existing calibration GUI tests pass; new tests added for zoom mapping + inspector independence + collapse toggle.
- [ ] No `raise_/activateWindow/showNormal/showMaximized` from any path; runtime test asserts this across 10 zoom + slider events.
- [ ] `pytest` zero failures; full project suite still green; junit XML at `target/test-artifacts/WP-I1-028/pytest_results.xml`.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] Operator confirms manual calibration cycle with zoom + inspector on the Aeri master.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Zoom in 2x, click on (100, 100) display coords → emits the correct image-space coord.
- [ ] After pan by (50, 30), click on the same display coord → emits a different image-space coord (correctly offset).
- [ ] Reset-to-fit returns view to scale=1, offset=(0,0).
- [ ] Inspector slider at +30° renders a different image than at -30° (pixel-diff > threshold).
- [ ] Inspector slider movement does NOT change `app.state.yaw["current_value_deg"]`.
- [ ] Inspector slider movement does NOT trigger an `export_single` re-render.
- [ ] Collapse toggle hides / shows the inspector widget.

### Code Correctness Tests
- [ ] Single click without movement → emits `clicked` once.
- [ ] Click + drag (movement > threshold) → does not emit `clicked` (treated as pan).
- [ ] Inspector cache: rendering twice at the same angle returns the cached image.

### Red-Team / Abuse Tests
- [ ] Wheel zoom past minimum / maximum scale clamps cleanly.
- [ ] Inspector slider at `+90` and `-90` boundaries render without crashing.
- [ ] No GUI string introduces a forbidden yaw phrase (existing grep test continues to cover this).

### Performance / Reliability Tests
- [ ] Inspector re-render under 30ms on a typical rig; not-gating.

## Rollback Plan

- Files to revert: `gui/calibration.py`, both new / extended test files, the spec extension.
- Files to keep: WP-I1-001's calibration module, snapshot, commands — unchanged by this WP.
- Recovery: `git restore --staged .product/ .gov/spec/; git checkout -- .product/ .gov/spec/`.

## Decisions Log

- 2026-05-03: `QGraphicsView` over manual QLabel transforms. Reason: Qt's mapping APIs handle the zoom + pan math correctly out of the box; less code to write, fewer bugs.
- 2026-05-03: Inspector reuses `render/draw_3d.py` over a new dedicated renderer. Reason: same rig, same wireframe semantics; consistency is more valuable than a tighter inspector-specific render.
- 2026-05-03: Inspector slider is `[-90, +90]` (yaw-only). Reason: matches v0.1 spec scope; pitch/roll inspection waits on WP-I1-007 to author the locked terminology + math.

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: WP file + taskboard row.
2. Implementation: zoomable image view + click semantics.
3. Implementation: mesh inspector + collapse toggle + slider.
4. Verification: pytest + junit XML + manual operator cycle.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_calibration_gui.py .product/tests/test_calibration_zoom.py --junitxml=target/test-artifacts/WP-I1-028/pytest_results.xml`.
- **Proof Artifact**: `target/test-artifacts/WP-I1-028/pytest_results.xml` plus an operator note confirming the manual cycle.
- **Claim Standard**: never mark DONE without operator confirmation that markers can be placed precisely under zoom AND that inspector slider motion does not affect active yaw / OpenPose preview / export output.

## Headless LLM Operation Compliance

- [ ] N/A — operator-facing GUI polish. No new commands, no new state, no new snapshot target. The Calibration tab's existing headless contract (commands per WP-I1-001) is unchanged. Add this section's items only if the operator authorizes a snapshot target for the inspector view.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects DONE.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded.
- [ ] Headless LLM Operation Compliance section reviewed (currently N/A; revisit if scope grows).

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at status DRAFT. Predecessor (WP-I1-001) DONE. Awaits operator promotion to READY.
