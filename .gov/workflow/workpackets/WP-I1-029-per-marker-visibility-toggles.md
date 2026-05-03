# WP-I1-029 - Per-Marker Visibility Toggles

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: IN-PROGRESS
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / OpenPose Schema Mapping (per-keypoint suppression layer); LLM Control Surface (new commands).
- **Linked Test Suite**: `.product/tests/test_marker_visibility.py` (NEW).
- **Linked Check Script**: N/A.

## Intent

Operator can suppress individual OpenPose keypoints — not just whole body-part groups. Adds a Markers tab (or extension of an existing tab) listing every body_18 + face_70 keypoint with a checkbox; unchecked keypoints emit `[0.0, 0.0, 0.0]` in the JSON and are not drawn in the OpenPose preview. Complements (does not replace) WP-I1-017's per-body-part toggles: group flags for coarse control, per-marker for fine surgery on a specific bad detection.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-002 (LLM control surface), WP-I0-004 (GUI), WP-I0-001 (rig + serializer) — all DONE.
- **Successor(s)**: none planned.
- **Blocks**: none.
- **Blocked-By**: none. WP-I1-017 is *complementary*, not a predecessor — both can land in either order; if both are present the per-marker checks override (a marker explicitly unchecked stays off even if its group is on; a marker checked on stays on even if its group is suppressed).
- **Related**: WP-I1-017 (per-body-part visibility — coarser sibling); WP-I1-018 (hand detection, when it lands the per-marker map gains 21 hand-kp entries per hand).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` Feature 1 / OpenPose Schema Mapping — extend with per-keypoint suppression semantics.
- `.gov/spec/openrepose_v0_1.md` LLM Control Surface — register new commands.
- `.gov/AGENTS.md` Headless LLM Operation Rule — commands reachable headlessly; state mirrored; preview reflects state.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | DWPose / OpenPoseXL2 conditioning behavior | (operator-side knowledge from WP-I0-003 diagnostic + WP-I1-017 risk note) | Triples written as `[0.0, 0.0, 0.0]` in OpenPose JSON read as "absent" by ControlNet preprocessors and DWPose-trained UNets, not "occluded with low confidence". The same convention WP-I1-017 plans to use; this WP applies it at per-keypoint granularity. | adopt |
| 2026-05-03 | OpenPose body_18 + face_70 schemas | `openpose_schema.py` | Names already enumerated by index in our schema module. Per-marker UI uses these as dropdown / checkbox labels; no need for new naming. | adopt |
| 2026-05-03 | Existing per-body-part precedent (WP-I1-017 DRAFT) | `WP-I1-017-per-body-part-visibility.md` | Group-level flags. Per-marker layered on top — when both layers exist, per-marker is the authoritative override. | adopt as composition rule |

Decision: per-keypoint suppression layered as a `marker_visibility` block in `state.json` mapping `body_18` indices and `face_70` indices to bool. Suppression applied at the same point in the serializer as WP-I1-017's group flags — group result is a starting set, per-marker map then overrides individual indices. Default: all visible. The Markers tab in the GUI groups checkboxes by anatomical region (head / torso / arms / legs / face) for usability but the storage is flat by index so the spec contract is unambiguous.

## Reality Boundary

- **Real Seam**: real `marker_visibility` block in `state.json` (`{body_18: {0: true, 1: true, ...}, face_70: {0: true, ...}}`), real serializer pass that zeros suppressed triples, real OpenPose preview renderer skip for suppressed markers. Two new commands wired into the dispatcher. New Markers tab in the right dock.
- **User-Visible Win**: operator unchecks `face_70[12]` (a single bad face landmark detection); the next export emits `[0.0, 0.0, 0.0]` for that keypoint; the OpenPose preview no longer draws that dot or any line ending at it. Re-checking restores it. No restart needed.
- **Proof Target**: pytest covers (a) state round-trip; (b) suppressing one body keypoint zeros only that triple; (c) suppressing one face keypoint zeros only that triple; (d) interaction with WP-I1-017 group flags (per-marker overrides group); (e) GUI tab updates state on click. Manual: operator unchecks a noisy keypoint, exports, confirms downstream ControlNet generation behaves as expected.
- **Allowed Temporary Fallbacks**: none.
- **Promotion Guard**: do not promote to DONE until the operator confirms a per-marker uncheck → export → downstream-generation cycle on at least one bad detection.

## In Scope

- New `state.json` `marker_visibility` block: `{body_18: {<int_index>: bool, ...}, face_70: {<int_index>: bool, ...}}`. Defaults to all-true. Indices not present in the dict are treated as visible.
- Two new commands: `set_marker_visibility {schema: "body_18"|"face_70", index: int, visible: bool}` and `get_marker_visibility` (read-only).
- Bulk-set helper: `set_marker_visibility {schema, indices: [...], visible: bool}` form (operator can hide a contiguous range without 70 calls).
- Serializer `openpose_serialize.py` reads the block and zeros suppressed triples *after* WP-I1-017's group flags (per-marker is the authoritative layer).
- Preview renderer `draw_openpose.py` skips suppressed markers.
- New Markers tab in the right dock with two grouped sections (body_18, face_70). Each entry is a `<index> <name>` checkbox. Reset-all button.
- Tests: per-keypoint round-trip, single-keypoint suppression, group + per-marker interaction, GUI tab updates state, no forbidden phrases, no focus theft.

## Out Of Scope

- Per-side-only suppression at the schema level (operator unchecks individually; sides are addressed by their own indices already).
- Per-export-target visibility (single vs batch use the same flags; this WP is global state).
- Hand keypoints (out of scope until WP-I1-018 ships hand detection — the schema gains hand_21_left / hand_21_right at that point; this WP can be extended trivially when that lands).
- A separate snapshot target (existing `openpose_viewport` snapshot already reflects suppressed markers).
- Auto-detect-and-suppress noisy keypoints (a future RESEARCH WP could explore this).

## Expected Files Touched

### Governance (`.gov/`)
- `.gov/workflow/workpackets/WP-I1-029-per-marker-visibility-toggles.md` (this file).
- `.gov/workflow/TASKBOARD.md` — Active row added at READY when promoted.
- `.gov/spec/openrepose_v0_1.md` — Feature 1 / OpenPose Schema Mapping extended with per-keypoint suppression layer; LLM Control Surface gains the two new commands.

### Product (`.product/`)
- `.product/src/openrepose/state.py` — `marker_visibility` block + helpers.
- `.product/src/openrepose/commands.py` — `_h_set_marker_visibility`, `_h_get_marker_visibility` registered.
- `.product/src/openrepose/openpose_serialize.py` — apply per-marker mask after group flags.
- `.product/src/openrepose/render/draw_openpose.py` — skip suppressed markers in the preview.
- `.product/src/openrepose/gui/markers.py` (NEW) — operator-facing Markers tab.
- `.product/src/openrepose/gui/main_window.py` — wire the Markers tab into the dock.
- `.product/tests/test_marker_visibility.py` (NEW).

### Build / Output (gitignored)
- `target/test-artifacts/WP-I1-029/`

## Risks And Dependencies

- **Risk**: per-marker mask conflicts with WP-I1-017 group flags. **Mitigation**: defined precedence — group flags applied first (set / clear default visibility for the group); per-marker map then overrides individual indices. Tests cover the intersection.
- **Risk**: Markers tab with 88 checkboxes (18 + 70) is cluttered. **Mitigation**: anatomical sub-grouping (head, torso, left arm, right arm, left leg, right leg, face outline, eyes, brows, nose, mouth) with collapsible groups. Sticks to existing her-anatomy naming (no forbidden phrases).
- **Risk**: a fully-zeroed-out OpenPose JSON could crash some downstream tools. **Mitigation**: the operator has to actively uncheck most markers to reach this state; document expected behavior in the spec; do not silently filter "too few visible markers".
- **Dependency**: existing serializer + preview renderer + state machinery. WP-I1-018 (hand detection) is *not* a predecessor; per-marker for hands gets added in a follow-up commit when WP-I1-018 lands.

## Definition Of Done

- [ ] `marker_visibility` block in `state.json` (defaults to empty dicts = all visible).
- [ ] `set_marker_visibility` (single + bulk forms) and `get_marker_visibility` registered in dispatcher.
- [ ] Serializer zeros suppressed triples; preview renderer skips them.
- [ ] Markers tab functional: anatomical sub-groups + collapsible; checkboxes reflect state; reset-all button works.
- [ ] Group + per-marker interaction tests green (per-marker overrides).
- [ ] No `raise_/activateWindow/showNormal/showMaximized` from any LLM-driven path; runtime test asserts this across 30 set / unset cycles.
- [ ] `pytest` zero failures; junit XML at `target/test-artifacts/WP-I1-029/pytest_results.xml`.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] Operator confirms manual uncheck → export → downstream-generation cycle on a specific noisy keypoint.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Default state: all markers visible; serializer output unchanged from baseline.
- [ ] Suppress `body_18[0]` (nose): only that triple is zeroed.
- [ ] Suppress `face_70[12]`: only that triple is zeroed.
- [ ] Bulk-suppress `body_18 [3, 4, 6, 7]` (arms region): all four zeroed; legs / face unaffected.
- [ ] Per-marker overrides group: with WP-I1-017 `face` group OFF, an individually-checked `face_70[27]` (nose tip) is still visible.
- [ ] Per-marker overrides group: with WP-I1-017 `face` group ON, an individually-unchecked `face_70[27]` is suppressed.

### Code Correctness Tests
- [ ] state.json `marker_visibility` block matches command inputs after each set.
- [ ] Suppressed triples are byte-identical to `[0.0, 0.0, 0.0]` in the written JSON.
- [ ] No regression when block is empty (existing behavior).

### Red-Team / Abuse Tests
- [ ] Unknown schema name ("body_25", "face_120") in `set_marker_visibility`: structured ERR.
- [ ] Out-of-range index in `set_marker_visibility`: structured ERR; existing flags unchanged.
- [ ] No GUI checkbox label introduces a forbidden yaw phrase (existing grep test continues to cover this).

### Performance / Reliability Tests
- [ ] Serializer pass with all-zero mask under 5ms (sanity, not gating).

## Rollback Plan

- Files to revert: `state.py`, `commands.py`, `openpose_serialize.py`, `render/draw_openpose.py`, `gui/markers.py`, `gui/main_window.py`, the new test file, the spec extension.
- Files to keep: previously exported JSONs (loader tolerates older schema; missing `marker_visibility` block treated as all-visible).
- Recovery: `git restore --staged .product/ .gov/spec/; git checkout -- .product/ .gov/spec/`.

## Decisions Log

- 2026-05-03: Layered per-marker on top of WP-I1-017 group flags rather than replacing them. Reason: groups are the right abstraction for "drop the legs in this whole batch"; per-marker is the right abstraction for "this one face landmark is misdetected on this avatar".
- 2026-05-03: Indices stored as int keys (JSON-compatible string-int conversion at load/save boundaries) over name-based map. Reason: indices are the schema's source of truth; names are derivable. Avoids name-versioning bugs if MediaPipe / OpenPose schema names ever drift.
- 2026-05-03: Tab grouping by anatomical region for usability; flat storage by index for spec clarity.

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- **What Became Real**:
  - `openpose_schema.py`: `MARKER_SCHEMAS` (`body_18`, `face_70`), `default_marker_visibility()`, `apply_marker_visibility(body18, face70, marker_visibility)` helper. Per-marker overrides applied AFTER body-part group flags so per-marker is the authoritative layer (explicit True restores a marker even if its group is off; explicit False suppresses it even if its group is on). Accepts both int and stringified-int keys (JSON round-trip safe).
  - `openpose_serialize.py`: `serialize()` and `serialize_to_string()` accept optional `marker_visibility` kwarg; helper applied on the conf arrays after group flags.
  - `render/draw_openpose.py`: `render_openpose()` accepts `marker_visibility`; helper applied on the bool visibility arrays.
  - `state.py`: new `marker_visibility` block defaulting to `{"body_18": {}, "face_70": {}}` (empty = no overrides).
  - `commands.py`: 3 new handlers — `set_marker_visibility` (single `index` or bulk `indices` form, mutually exclusive; validates schema, visible flag, ranges), `get_marker_visibility` (read-only), `reset_marker_visibility` (clears all overrides). Export handlers + `_h_snapshot` pass `dict(state.marker_visibility)` through.
  - `snapshot.py`: signature gains `marker_visibility` kwarg threaded into `render_openpose` for `openpose_viewport` and `full_window` targets.
  - `gui/markers.py` (NEW): `MarkersPane` operator-facing tab. Two QListWidget sections (body_18 with anatomical labels; face_70 with region labels — jaw outline / right brow / outer mouth / pupils / etc.). Each item is checkable. Toggling fires `set_marker_visibility` for that single index. Reset-all button dispatches `reset_marker_visibility`. `refresh()` syncs from state without re-firing. Suppress flag prevents init-time signal storm.
  - `gui/main_window.py`: new "Markers" tab between "Calibration" and "Options". Polling timer calls `_markers.refresh()` so LLM-driven mutations update the checkboxes silently.
  - `test_marker_visibility.py` (NEW): 22 tests — schema layer (defaults, identity-fast-return, single body / face, string-key acceptance, unknown schema raises, out-of-range raises); precedence (per-marker overrides group-off; per-marker overrides group-on); dispatcher (single + bulk + unknown schema + missing visible + both-index-and-indices + out-of-range + reset); end-to-end (single body marker zeroed in JSON; per-marker restoration of one face_70 keypoint when face group is off; state.json block).
  - `test_gui_layout.py`: assertion updated for 6-tab layout.
- **What Remains Simulated / Deferred**:
  - Hand keypoints (no `hand_21_*` schema in v0.1; gated on WP-I1-018 hand detection landing).
  - Face_70 region labels are coarse (per-region, not per-keypoint anatomical name). Operator can read the index next to the label; finer naming is a polish followup.
  - Auto-detect-and-suppress noisy keypoints (future RESEARCH WP).
- **Next Blocking Real Seam**: with both layers shipped, the next visibility expansion is hand keypoints when WP-I1-018 lands.

## Checkpoint Commit Plan

1. Governance kickoff: WP file + taskboard row + spec extension.
2. Implementation: state + dispatcher + serializer + renderer.
3. GUI: Markers tab with grouped checkboxes + reset-all.
4. Verification: pytest + junit XML + group-and-per-marker interaction tests + manual operator cycle.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_marker_visibility.py --junitxml=target/test-artifacts/WP-I1-029/pytest_results.xml`.
- **Proof Artifact**: `target/test-artifacts/WP-I1-029/pytest_results.xml` plus sample JSONs at single-keypoint and group-overridden configurations.
- **Claim Standard**: never mark DONE without operator confirmation that an unchecked-keypoint export changes downstream ControlNet generation as expected.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via 2 new commands.
- [ ] State reflected in `state.json` `marker_visibility` block.
- [ ] LLM pulls visual via existing `openpose_viewport` snapshot (reflects suppressed markers).
- [ ] No `raise_/activateWindow/showNormal/setForegroundWindow` from any LLM-driven path.
- [ ] No modal dialogs from LLM commands.
- [ ] Tests cover the headless command path.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects DONE.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I1-029/pytest_results.xml` — 247 passed, 0 failed (full suite; +22 new from this WP, including 4 precedence tests against WP-I1-017 group flags).
- **Local Audit Run**: `pwsh scripts/audit-repo.ps1` exits 0.
- **Build Artifacts**: schema/serializer/renderer/snapshot/state/commands modifications; new `gui/markers.py`, new `test_marker_visibility.py`; `test_gui_layout.py` updated for 6-tab layout.
- **Operator Sign-off**: PENDING — operator to verify by opening the new Markers tab, unchecking a noisy keypoint (e.g. body_18 right_wrist or a face_70 jaw point), exporting, inspecting JSON.

## Progress Log

- 2026-05-03: WP drafted at status DRAFT. Predecessors satisfied. Intentionally a sibling of WP-I1-017 (not a successor) — both layers compose with documented precedence. Awaits operator promotion to READY.
- 2026-05-03: Operator approved fast-track batch (slot 3). Status DRAFT -> IN-PROGRESS. Implementation complete: schema helper + serializer + renderer + state + 3 commands + Markers tab + 22 tests. 247/247 passing. Audit clean. Status -> REVIEW.
- 2026-05-03: Operator GUI inspection — same regression as WP-I1-017 (viewport_openpose doesn't honor live state). Status REVIEW -> IN-PROGRESS for in-place fix bundled with WP-I1-017 + WP-I1-023.
- 2026-05-03: Regression fix landed (shared with WP-I1-017 + WP-I1-023). `viewport_openpose.update_rig()` now passes `marker_visibility`; new regression test guards the polling path. Full suite 281/281. Status IN-PROGRESS -> REVIEW.
- 2026-05-03: Operator inspection — second bug surfaced. When a portrait is imported and MediaPipe does not detect a body_18 / face_70 keypoint (visibility 0 / position at origin), the Markers tab still shows the row CHECKED. Operator expected undetected markers to start UNCHECKED. Worse: forcing an undetected marker to visible=True via per-marker override causes the renderer to draw a stray dot at (0,0) — the "haywire" symptom. Status REVIEW -> IN-PROGRESS for the in-place fix: (a) on import_portrait, populate state.marker_visibility with explicit False for any body_18 / face_70 keypoint at (0,0,0); (b) defensive render — if a marker is forced visible but its position is at the origin, treat it as not visible (no stray dot).
