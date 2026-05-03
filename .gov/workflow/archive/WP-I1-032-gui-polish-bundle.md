# WP-I1-032 - GUI Polish Bundle

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DONE
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements; Feature 2 / GUI Requirements (Calibration tab sizing constraint).
- **Linked Test Suite**: extend `.product/tests/test_gui_layout.py` + `.product/tests/test_settings_store.py`; new `.product/tests/test_canvas_border.py`.
- **Linked Check Script**: N/A.

## Intent

Bundle four small UX fixes surfaced during operator GUI inspection on 2026-05-03. Each is XS-S on its own; bundled because they all touch GUI / settings layers and shipping them as one PR is cleaner than four:

1. **Calibration tab grows the dock width** when activated. The portrait QLabel takes the pixmap's natural size as its sizeHint, which propagates up the layout. Fix: constrain the size policy / override sizeHint / use `setScaledContents(True)`.
2. **Remember last opened portrait folder** so File→Open defaults to it on next launch. Persist `last_portrait_dir` in the existing `Settings` (extends WP-I1-027's primitive).
3. **Reframer canvas border** — when frame_scale < 1.0, the figure shrinks against a black background and the canvas edges are invisible. Add a configurable canvas-border outline (default white, color picker in Options).
4. **Body-marker text color** in the Markers tab — color each `body_18` row text with the corresponding `LIMB_COLORS_BGR` entry from the OpenPose schema so the operator can match a row to the colored skeleton in the preview.

## Linked Workpackets

- **Predecessor(s)**: WP-I1-027 (Settings primitive — REVIEW), WP-I1-001 (Calibration tab — DONE), WP-I1-029 (Markers tab — REVIEW), WP-I1-023 (Frame controls — REVIEW), WP-I0-004 (GUI / dock layout — DONE).
- **Successor(s)**: WP-I1-031 (Tools tab reorganization) is independent but may want to land after this so the colored marker text + canvas border are already in place.
- **Blocks**: none.
- **Blocked-By**: ideally WP-I1-027 DONE first (extending its Settings primitive); acceptable to ship while WP-I1-027 is still in REVIEW since the schema_version stays 1.
- **Related**: WP-I1-028 expanded scope (Calibration tab UX) — overlaps on the calibration sizing fix; WP-I1-028 will pick the constrained sizing up unchanged.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements — extend with canvas-border outline option in Options tab.
- `.gov/spec/openrepose_v0_1.md` Feature 2 / GUI Requirements — note the Calibration tab dock-width constraint.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Qt `QLabel.setScaledContents` + sizeHint | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QLabel.html | A QLabel with a pixmap reports the pixmap's natural size as its sizeHint unless `setScaledContents(True)` is set or sizeHint is overridden. Setting setScaledContents(True) lets the pixmap stretch to the widget's geometry; combined with `setMinimumSize` + an Expanding size policy, the widget no longer dictates the parent's size. | adopt |
| 2026-05-03 | Qt `QFileDialog.getOpenFileName` initial directory | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QFileDialog.html | `getOpenFileName(parent, caption, dir, filter)` accepts the initial directory as the third positional. Currently we pass `""`; passing `settings.last_portrait_dir` makes the dialog open at the last-used location. | adopt |
| 2026-05-03 | Qt `QColorDialog` | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QColorDialog.html | Standard color picker via `QColorDialog.getColor()`. Operator-only path (no LLM trigger), so no focus-theft concerns. | adopt for the canvas-border color option |
| 2026-05-03 | OpenPose body_18 limb colors | local `render/draw_openpose.py` `LIMB_COLORS_BGR` | Existing 17-entry tuple of BGR colors keyed by LIMB_PAIRS index. Per-marker color = the color of the limb that ENDS at that marker (or the first limb that includes it). For markers that aren't a limb endpoint (e.g., neck = limb (1,2)/(1,5) etc.) we use the first connected limb's color. | adopt — derive a `BODY_18_COLOR_BY_INDEX` from `LIMB_PAIRS` + `LIMB_COLORS_BGR` |

Decision: 4 fixes bundled. Settings extension reuses WP-I1-027's primitive (no schema_version bump — `last_portrait_dir` is an optional new field with default `""`). Canvas border default white; color stored in settings (`canvas_border_color: "#ffffff"`).

## Reality Boundary

- **Real Seam**:
  - `gui/calibration.py` `_ClickablePortrait` calls `setScaledContents(True)` + tighter size policy so activating the tab no longer expands the dock width.
  - `settings.py` `Settings` gains `last_portrait_dir: str = ""` and `canvas_border_color: str = "#ffffff"`.
  - `gui/main_window.py` `_on_open` passes `settings.last_portrait_dir` as the initial dir; on success persists `Path(path).parent`.
  - `render/draw_openpose.py` `render_openpose` accepts a `canvas_border_color` kwarg and draws a 2px rectangle outline around the canvas perimeter. Threading through dispatcher + snapshot + viewport.
  - `gui/options.py` adds a "Canvas border" QPushButton-with-color-swatch + `QColorDialog` integration; signal `canvas_border_color_changed`.
  - `gui/markers.py` colors each body_18 list item text via `BODY_18_COLOR_BY_INDEX` (derived from existing `LIMB_PAIRS` + `LIMB_COLORS_BGR`).
- **User-Visible Win**:
  - Switching to Calibration no longer grows the GUI window; dock width stays where the operator put it.
  - File→Open opens at the last-used folder.
  - When frame_scale < 1.0, a thin white (or operator-configured) outline shows the canvas edges.
  - Markers tab body_18 entries are colored to match the OpenPose skeleton colors — operator can visually match a row to the limb in the preview.
- **Proof Target**: pytest covers (a) Calibration sizeHint constrained; (b) settings round-trip with `last_portrait_dir` + `canvas_border_color`; (c) `render_openpose` draws the border rectangle; (d) Markers tab item text color matches `BODY_18_COLOR_BY_INDEX`. Manual: operator switches to Calibration tab and confirms no window grow; opens portrait, restarts, opens portrait again — dialog opens at the same folder; sets frame_scale=0.6 and sees a visible outline; inspects Markers tab and sees colored body_18 rows.
- **Allowed Temporary Fallbacks**: none.
- **Promotion Guard**: do not promote to DONE until operator confirms all four fixes work end-to-end in a real GUI session.

## In Scope

- `gui/calibration.py` — sizing fix on `_ClickablePortrait` (setScaledContents + size policy + sizeHint constraint).
- `settings.py` — add `last_portrait_dir`, `canvas_border_color` fields with defaults; extend `update()` valid keys; surface on `to_dict()`.
- `gui/main_window.py` — `_on_open` reads + writes `last_portrait_dir`; pass `canvas_border_color` to viewport on poll.
- `render/draw_openpose.py` — accept `canvas_border_color` kwarg; draw 2px rectangle around canvas (skip if color is `None` / empty).
- `commands.py` — export handlers + snapshot dispatcher pass `canvas_border_color` from `app.settings`.
- `snapshot.py` — `snapshot()` signature gains `canvas_border_color` kwarg; threaded into `render_openpose`.
- `gui/viewport_openpose.py` — `update_rig` accepts `canvas_border_color` kwarg.
- `gui/options.py` — Canvas border color picker (QPushButton with color-swatch + `QColorDialog`); `canvas_border_color_changed(str)` signal.
- `openpose_schema.py` — derive `BODY_18_COLOR_BY_INDEX` (read-only constant computed from `LIMB_PAIRS` + `LIMB_COLORS_BGR`).
- `gui/markers.py` — color each body_18 item text via `BODY_18_COLOR_BY_INDEX`.
- Tests: extend `test_settings_store.py` with the two new fields; new `test_canvas_border.py` for renderer + dispatcher path; extend `test_calibration_gui.py` with the dock-sizing assertion; extend `test_calibration_gui.py` or `test_gui_layout.py` with marker color assertion.

## Out Of Scope

- Per-export-target border (single + batch share the same border color setting).
- Multi-color border (e.g., gradient); single solid color only.
- Canvas border for the calibration overlay snapshot (it already has a portrait background; no need).
- Configurable border thickness (default 2px in v0.1).
- Last-used folder for OTHER pickers (export folder Browse... has its own state via Settings.export_folder; calibration save/load doesn't use a picker).

## Expected Files Touched

### Governance (`.gov/`)
- `.gov/workflow/workpackets/WP-I1-032-gui-polish-bundle.md` (this file).
- `.gov/workflow/TASKBOARD.md` — Active row at READY.
- `.gov/spec/openrepose_v0_1.md` — small extension to Options tab + Calibration tab notes.

### Product (`.product/`)
- `.product/src/openrepose/settings.py`
- `.product/src/openrepose/openpose_schema.py`
- `.product/src/openrepose/render/draw_openpose.py`
- `.product/src/openrepose/snapshot.py`
- `.product/src/openrepose/commands.py`
- `.product/src/openrepose/gui/calibration.py`
- `.product/src/openrepose/gui/main_window.py`
- `.product/src/openrepose/gui/options.py`
- `.product/src/openrepose/gui/viewport_openpose.py`
- `.product/src/openrepose/gui/markers.py`
- `.product/tests/test_settings_store.py` (extend)
- `.product/tests/test_canvas_border.py` (NEW)
- `.product/tests/test_calibration_gui.py` (extend)

### Build / Output (gitignored)
- `target/test-artifacts/WP-I1-032/`

## Risks And Dependencies

- **Risk**: setScaledContents(True) on the calibration portrait could distort aspect ratio. **Mitigation**: portrait scaled with `KeepAspectRatio` already; setScaledContents(True) + the existing scaled QPixmap call keeps aspect; the win is sizeHint not following the pixmap.
- **Risk**: canvas border color persists across launches; if operator changes it accidentally, exports change. **Mitigation**: documented in Options; default white; operator can read state.json to verify.
- **Risk**: BODY_18_COLOR_BY_INDEX derivation picks a color for the neck (idx 1) that's the first limb's color (1,2)→red, but the neck is connected to multiple limbs. **Mitigation**: document the rule; it's cosmetic.
- **Dependency**: WP-I1-027 (Settings primitive) is in REVIEW; this WP extends it. If WP-I1-027 is rejected back to IN-PROGRESS, this WP rebases.

## Definition Of Done

- [ ] Calibration tab activation does not grow the dock width (regression test asserts `_calibration._portrait.sizeHint().width()` is bounded).
- [ ] `Settings.last_portrait_dir` round-trips; File→Open defaults to it; persists across App instances.
- [ ] `Settings.canvas_border_color` round-trips; default `"#ffffff"`.
- [ ] `render_openpose(rotated, canvas_border_color="#ffffff")` draws a visible 2px white rectangle around the canvas perimeter.
- [ ] Dispatcher + snapshot + viewport thread `canvas_border_color` from `app.settings` so single + batch exports + live preview all show the border.
- [ ] Options pane has a Canvas border color button that opens QColorDialog; color persists via `Settings.update()`.
- [ ] Markers tab body_18 rows are text-colored per `BODY_18_COLOR_BY_INDEX`.
- [ ] No `raise_/activateWindow/showNormal/showMaximized` from any LLM-driven path.
- [ ] `pytest` zero failures; full project suite still green; junit XML at `target/test-artifacts/WP-I1-032/pytest_results.xml`.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] Operator confirms each fix in a real GUI session.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Settings round-trip with `last_portrait_dir` + `canvas_border_color`.
- [ ] `_ClickablePortrait` sizeHint width <= dock max width after pixmap set.
- [ ] `render_openpose` with `canvas_border_color="#ffffff"` writes white pixels along the canvas border.
- [ ] `render_openpose` with `canvas_border_color=None` does not write a border.
- [ ] export_single PNG (after WP-I1-030 lands; until then JSON only) includes the border in the rendered PNG.
- [ ] Markers tab body_18 item text color matches `BODY_18_COLOR_BY_INDEX[i]`.

### Code Correctness Tests
- [ ] `BODY_18_COLOR_BY_INDEX` length is 18.
- [ ] Settings update with unknown field still raises (existing test).
- [ ] File→Open with empty `last_portrait_dir` falls back gracefully (no crash).

### Red-Team / Abuse Tests
- [ ] `last_portrait_dir` pointing at a removed drive: `getOpenFileName` opens at the user's home; no crash.
- [ ] Invalid color string in `canvas_border_color`: render skips border + logs WARN; no crash.
- [ ] No GUI string introduces a forbidden yaw phrase.

### Performance / Reliability Tests
- [ ] Border drawing adds < 1ms per render.

## Rollback Plan

- Files to revert: per Expected Files Touched.
- Files to keep: existing settings.json (the new fields are optional with defaults).
- Recovery: `git restore --staged .product/ .gov/spec/; git checkout -- .product/ .gov/spec/`.

## Decisions Log

- 2026-05-03: Bundle four fixes into one WP. Reason: each is XS; bundling reduces governance overhead and matches the operator's "fast-track" preference.
- 2026-05-03: Canvas border color stored in settings (operator-configurable). Reason: operator explicitly asked for color choice; settings persistence already exists via WP-I1-027.
- 2026-05-03: BODY_18_COLOR_BY_INDEX derived from existing LIMB_PAIRS + LIMB_COLORS_BGR. Reason: avoids hardcoding a duplicate color table; rule = first limb that includes the index gets that limb's color.
- 2026-05-03: Default border color white. Reason: visible against the OpenPose black background; operator can change in Options.

## Fallback Register

- (none planned at READY stage)

## Change Ledger

- **What Became Real**:
  - `settings.py`: `Settings` gains `last_portrait_dir: str = ""` and `canvas_border_color: str = "#ffffff"` fields. `to_dict()` / `update()` / `load()` updated. Backward compatible (defaults applied when loading older settings.json).
  - `gui/calibration.py`: `_ClickablePortrait` overrides `sizeHint()` and `minimumSizeHint()` to return constant small sizes (DOCK_WIDTH_CAP=320 x 360); size policy switched from Expanding/Expanding to Ignored/Expanding so the dock width is no longer dictated by the master portrait pixmap. Fixes the calibration-tab-grow regression.
  - `gui/main_window.py`: `_on_open` reads `settings.last_portrait_dir` for the QFileDialog initial directory; on success persists the chosen folder via `settings.update(last_portrait_dir=...)`. Errors swallowed with a WARN so a failed-persist doesn't break the import flow.
  - `render/draw_openpose.py`: `BODY_18_COLOR_BY_INDEX` derived from existing `LIMB_PAIRS` + `LIMB_COLORS_BGR` (color of first limb that includes each keypoint). `_hex_to_bgr()` helper. `render_openpose()` accepts `canvas_border_color` kwarg; draws a 2px rectangle around the canvas perimeter when color is valid; skips when None / empty / invalid.
  - `snapshot.py`: signature gains `canvas_border_color` kwarg threaded into `render_openpose` for `openpose_viewport` + `full_window`.
  - `commands.py`: `_h_snapshot` reads `app.settings.canvas_border_color` and passes to `do_snapshot`. (Note: PNG output alongside JSON in `_h_export_*` is WP-I1-030's job; this WP only adds the kwarg plumbing.)
  - `gui/viewport_openpose.py`: `update_rig` accepts `canvas_border_color` kwarg; threaded into `render_openpose` so live preview reflects the operator's chosen border color.
  - `gui/main_window.py`: state-poll loop passes `app.settings.canvas_border_color` to `_viewport_openpose.update_rig`.
  - `gui/options.py`: new "Canvas border" row with a color swatch + "Pick color..." button that opens `QColorDialog` (operator-triggered only). New `canvas_border_color_changed(str)` signal; `load_canvas_border_color()` syncs from Settings on construction.
  - `gui/main_window.py`: connects `canvas_border_color_changed` to `app.settings.update(canvas_border_color=...)`.
  - `gui/markers.py`: each body_18 list item's text foreground is set to `QBrush(QColor(*BODY_18_COLOR_BY_INDEX[i]))` (BGR→RGB conversion). Operator can match a row to the colored skeleton in the live preview.
  - Tests: extended `test_settings_store.py` (3 new tests for last_portrait_dir + canvas_border_color round-trip / defaults / update). New `test_canvas_border.py` (12 tests: hex→BGR helper edge cases, BODY_18_COLOR_BY_INDEX shape + values, end-to-end render with white border / empty color / invalid color). Extended `test_calibration_gui.py` with `test_calibration_portrait_sizehint_constrained` (regression guard for the dock-grow bug) and `test_markers_body_18_rows_colored_per_openpose_limb`. Fixed `test_viewport_openpose_live_state.py` spy signature to accept the new `canvas_border_color` kwarg.
- **What Remains Simulated / Deferred**:
  - PNG output alongside JSON on export — WP-I1-030 (still DRAFT).
  - Configurable border thickness — out of scope; default 2px.
  - Multi-color border (gradient / dashed) — out of scope.
  - Last-used folder for OTHER pickers (only File→Open portrait remembered; export folder Browse uses Settings.export_folder which is its own field).
- **Next Blocking Real Seam**: WP-I1-030 (export PNG + pretty JSON + slug sanitization) is the next sensible polish; WP-I1-031 (Tools tab reorganization) is also unblocked.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + WP-I1-033 + taskboard rows.
2. Implementation: settings extension + sizing fix + canvas border + colored marker text.
3. Verification: pytest + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_settings_store.py .product/tests/test_canvas_border.py .product/tests/test_calibration_gui.py --junitxml=target/test-artifacts/WP-I1-032/pytest_results.xml`.
- **Proof Artifact**: `target/test-artifacts/WP-I1-032/pytest_results.xml`.

## Headless LLM Operation Compliance

- [x] N/A — operator-facing GUI polish + settings extension. No new commands beyond the existing `dump_settings` (which already returns the full Settings dict). No new state blocks (settings block extends in-place). No new snapshot target. The canvas-border setting flows through the existing snapshot + export paths so an LLM agent's snapshot reflects the operator's chosen border color.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects DONE.
- [ ] Reality Boundary truthful.
- [ ] Linked test suite executed; junit XML saved.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I1-032/pytest_results.xml` — 295 passed, 0 failed (full suite; +14 new from this WP).
- **Local Audit Run**: `pwsh scripts/audit-repo.ps1` exits 0.
- **Build Artifacts**: edits to `settings.py`, `render/draw_openpose.py`, `snapshot.py`, `commands.py`, `gui/calibration.py`, `gui/main_window.py`, `gui/options.py`, `gui/viewport_openpose.py`, `gui/markers.py`; new `test_canvas_border.py`; extensions to `test_settings_store.py`, `test_calibration_gui.py`, `test_viewport_openpose_live_state.py`.
- **Operator Sign-off**: 2026-05-03: APPROVED ("WP-I1-032 working"). Follow-up enhancement requested separately: frame offsets should be sliders + spinboxes + per-section reset (folded into WP-I1-031 Tools tab scope, which extracts ReframerPane).

## Progress Log

- 2026-05-03: WP drafted directly at READY. Operator authorized "polish bundle first" so kickoff commit follows immediately. Operator surfaced 4 issues during GUI inspection earlier this session; this WP bundles them.
- 2026-05-03: Implementation complete. All four fixes landed: calibration sizing fix (sizeHint override + Ignored size policy), last_portrait_dir + canvas_border_color settings persistence, render_openpose canvas border + dispatch + viewport plumbing, Markers tab body_18 colored text. 295/295 passing. Audit clean. Status IN-PROGRESS -> REVIEW.
