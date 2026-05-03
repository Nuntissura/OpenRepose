# WP-I1-036 - Multi-File Workspace Spec (Tabs + Per-File State + Drag-Drop Import)

## Header

- **Owner**: TBD
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DRAFT
- **Iteration**: I1 (spec) → I3+ (implementation)
- **Workflow Version**: 1.1
- **Packet Class**: DOCUMENTATION
- **Effort Estimate**: M (spec authoring); the **implementation** WP that follows will be XL.
- **Linked Spec**: extends `.gov/spec/openrepose_v0_1.md` with a new "Multi-File Workspace" section between Feature 1 and "Project-Wide Principle: Headless LLM Operation".
- **Linked Test Suite**: N/A (spec authoring only).

## Intent

Author the canonical contract for OpenRepose's **multi-file workspace**. Operator's stated need:

- Files (each with a 3D mesh + OpenPose viewer) open in **tabs in the left/file side** of the app. The right side stays the information / tool surface (Inspector, Tools, Options, Log, Help).
- **Drag-and-drop a file onto either viewer** imports it and opens a new tab.
- Multiple files: tabs add to the right; **when no more horizontal space, a new column** of tabs appears.
- **X marker on each tab** to close.
- **Per-file persistent state**: switching tabs loads that file's calibration, frame, body-part visibility, marker visibility, etc. — operator's manipulations are tied to the file.
- **Empty state**: when no file is open, the file area shows a big "drop file here" target.

This is a major architectural change. Currently `dispatcher._rig` holds a single rig and global `state.calibration` / `state.frame` / etc. apply to it. The multi-file workspace requires:

- A **per-file state model** (each open file has its own portrait + rig + calibration + visibility + frame).
- A **dispatcher refactor** so existing commands operate on the **active file** (and new commands manage the file list / active tab).
- A **GUI layout refactor** with a file-tab widget on the left replacing the current center 3D + OpenPose split.

Output of this WP is the spec section that locks the contract. **No product code in this WP — spec only.** Implementation lands in a follow-up WP-I1-037 (or split across several).

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 (DONE), WP-I1-001 (DONE — calibration is per-avatar; this WP makes it per-file). Most other v0.1 features must be re-examined per-file vs global.
- **Successor(s)**: WP-I1-037+ (Multi-file workspace IMPLEMENTATION iteration). Cannot start until this WP is DONE.
- **Blocks**: WP-I1-037+ implementation; any future feature that adds new state should be drafted with multi-file in mind.
- **Blocked-By**: none.
- **Related**: WP-I2-006 (Library tab GUI — also touches dock layout; library tab stays right-side).

## Linked Requirements / Spec Sections

- New section "Multi-File Workspace" in `.gov/spec/openrepose_v0_1.md`.
- `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements — update to reference the new file-tab layout.
- `.gov/spec/openrepose_v0_1.md` LLM Control Surface — list new file-management commands.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | PySide6 QMdiArea / QTabWidget | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTabWidget.html | QTabWidget is the standard pattern for multi-file MDI in Qt apps. Tabs reorder + close via close-button (`setTabsClosable(True)`). For wrap-to-new-column, `setUsesScrollButtons(False)` + a flow layout above QTabWidget. | adopt QTabWidget for v0.1; flow-to-column behavior may be deferred to polish |
| 2026-05-03 | Qt drag-and-drop | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#dragEnterEvent | Standard `dragEnterEvent` / `dropEvent` overrides on the viewer widget. Accept image MIME types (`text/uri-list` filtered to `.png` / `.jpg`). | adopt |
| 2026-05-03 | Existing dispatcher | local `commands.py` | Single `_rig` reference. Refactor candidate: `_rigs: dict[file_id, Rig]` + `_active_file_id`. Each command operates on the active file unless an explicit `file_id` payload field is supplied. State.json grows a `files: [...]` array + `active_file_id`. | adopt |
| 2026-05-03 | Existing state.json shape | local `state.py` | Currently single-file state at top level (portrait, calibration, frame, marker_visibility, etc.). Spec must decide: keep top-level (mirror of active file) AND add `files: [...]` array OR migrate ALL per-file fields under `files: [{file_id, portrait, calibration, ...}, ...]`. Backward-compat for LLM agents reading state.json matters. | spec to decide |
| 2026-05-03 | Existing per-avatar calibration JSON at outputs/<slug>/calibration.json | local | Naturally fits per-file (one file = one avatar). No schema change to calibration.json itself. | adopt |
| 2026-05-03 | Operator's mental model | this session | Tabs + drag-drop + per-tab state matches how Photoshop, browsers, and most multi-file apps work. Familiar UX. | adopt |

Decisions to lock in the spec:

- **Tab widget**: QTabWidget (closeable tabs) for v0.1. Multi-row / column wrap deferred to polish if not native.
- **Drop zone**: when zero files open, show a centered "Drop a portrait here" placeholder (QLabel + dashed border) covering the file area. Drop accepts PNG/JPG.
- **Per-file state model**: state.json gains `files: [{file_id: uuid, portrait: str, avatar_slug: str, rig_status: str, calibration: dict, frame: dict, body_part_visibility: dict, marker_visibility: dict, detected_markers: dict, ...}, ...]` + `active_file_id`. Top-level fields (portrait, calibration, frame, etc.) become a MIRROR of the active file's state for backward compatibility with v0.1 LLM agents.
- **Dispatcher commands**: existing commands (`set_yaw`, `export_single`, `set_calibration_points`, `set_frame_*`, `set_body_part_visibility`, `set_marker_visibility`, etc.) operate on the active file by default; an optional `file_id` payload field targets a specific file. New commands: `open_file`, `close_file`, `set_active_file`, `list_files`.
- **Persistence**: `state.json` `files` array survives across launches when `Settings.persist_workspace = true` (default). On launch, OpenRepose re-imports each file (re-runs MediaPipe) and restores its per-file state from the saved blocks.
- **GUI layout**: replace the central QSplitter's left pane (currently the two viewports) with a `FileTabsPane` containing a closeable QTabWidget. Each tab hosts the 3D + OpenPose viewports for one file.
- **Drag-drop**: drop on the viewer area imports + opens a new tab. Drop on an existing tab's viewer is also accepted (opens new tab; doesn't replace).
- **Backwards compatibility**: existing v0.1 single-file workflow degrades cleanly — when only 1 file is open, the experience matches today's. v0.1 LLM agents reading state.json see the active file's state mirrored at the top level.

## Reality Boundary

- **Real Seam**: a real new spec section in `.gov/spec/openrepose_v0_1.md` locking the multi-file contract. WP-I1-037+ implementation can build against it without further scope debate.
- **User-Visible Win**: the next assistant who picks up the multi-file implementation reads the spec, knows the per-file state shape, the dispatcher refactor target, the GUI layout, the drag-drop semantics. No further research-first pass needed.
- **Proof Target**: `git diff` shows the new spec section with all subsections. Audit clean. Implementation WP can cite the spec section verbatim.
- **Allowed Temporary Fallbacks**: none (DOCUMENTATION-only).
- **Promotion Guard**: do not promote to DONE until the operator confirms the spec section locks the contract they envisioned (especially the persistence model + state.json backward compatibility).

## In Scope

Author a new "## Multi-File Workspace" section in `.gov/spec/openrepose_v0_1.md` (between Feature 1's "Reality Boundary For v0.1" and "## Feature 2") with subsections:

1. **Purpose** — operator productivity: edit multiple avatars / portraits in one session without losing state.
2. **File model** — what constitutes a "file" (portrait + derived rig + per-file state).
3. **Per-file state shape** — exhaustive list of state fields that move from global → per-file.
4. **State.json layout (v2)** — `files: [...]` + `active_file_id`; top-level fields mirror the active file for backward compatibility.
5. **GUI layout** — file-tab widget on the left replacing the central viewports; right dock unchanged.
6. **Drag-and-drop import** — accepted MIME types, drop targets, how new tab is created.
7. **Tab management** — close button (X), tab reorder, multi-column wrap (or deferred-polish note).
8. **Empty state** — "Drop a portrait here" placeholder when no files are open.
9. **LLM Command Surface** — new commands `open_file`, `close_file`, `set_active_file`, `list_files`; existing commands gain optional `file_id` parameter; default = active file.
10. **Persistence** — `Settings.persist_workspace` (default true); re-import on launch; degraded behavior if a file path no longer exists.
11. **Snapshot targets** — existing targets (`3d_viewport`, `openpose_viewport`, `full_window`, `calibration_overlay`) operate on the active file by default; optional `file_id` payload selects a specific file.
12. **Multi-operator Concurrency** — file-level locks for cross-operator simultaneous edits (interaction with WP-I1-033 Feature 3 library locks).
13. **Out Of Scope For v0.1** — multi-monitor tab splitting, drag-and-drop reordering across columns (initial implementation may be ordered list only).
14. **Reality Boundary** — what's real, user-visible win, proof target, fallbacks, promotion guard.

## Out Of Scope

- Implementation of any code (separate IMPLEMENTATION WPs in the I1-037+ chain).
- Tab tear-off / multi-window mode.
- Multi-monitor support.
- Drag-and-drop reordering of tabs across columns.
- Auto-save of open files between sessions (re-import is the model; explicit Save would be a polish WP).

## Expected Files Touched

### Governance
- `.gov/workflow/workpackets/WP-I1-036-multi-file-workspace-spec.md` (this file).
- `.gov/workflow/TASKBOARD.md`.
- `.gov/spec/openrepose_v0_1.md` — new "## Multi-File Workspace" section + small updates to Feature 1 / GUI Requirements + LLM Control Surface to reference it.

### Product
- (none — DOCUMENTATION-only)

### Build / Output
- `target/test-artifacts/WP-I1-036/` (audit log + git-diff snapshot).

## Risks And Dependencies

- **Risk**: spec underspecifies the LLM-agent backward compatibility, breaking existing v0.1 agents that read state.json. **Mitigation**: spec explicitly requires top-level fields to MIRROR the active file's state.
- **Risk**: persistence of files-across-launches re-runs MediaPipe on every file — slow startup if operator has 10 files open. **Mitigation**: spec allows lazy re-fit (re-fit on first switch-to-tab) as a permitted optimization in implementation.
- **Risk**: per-file calibration vs the existing per-AVATAR calibration JSON may collide if two open files share an avatar slug. **Mitigation**: spec resolves — calibration.json is per-AVATAR (current behavior); per-file state holds a CACHED copy that syncs from disk on file open.
- **Risk**: spec authoring runs ahead of the operator's actual mental model. **Mitigation**: operator review at REVIEW; can revise pre-promotion.
- **Dependency**: none external; this is documentation work.

## Definition Of Done

- [ ] `.gov/spec/openrepose_v0_1.md` contains a new "## Multi-File Workspace" section with all 14 subsections listed In Scope.
- [ ] Per-file state shape enumerated with explicit field list.
- [ ] state.json v2 layout documented (top-level mirrors active file for backward compat).
- [ ] At least 4 new LLM commands enumerated (`open_file`, `close_file`, `set_active_file`, `list_files`) with payload + return schemas.
- [ ] Persistence semantics + lazy-re-fit allowance documented.
- [ ] Snapshot targets behavior documented.
- [ ] Multi-operator interaction with WP-I1-033 library locks resolved.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] Operator sign-off recorded.
- [ ] **Manual Impact**: Yes — adds a new "Multi-File Workspace" topic file under `.gov/doc/manual/` summarizing the operator workflow + new commands. Created in this WP.

## Test Coverage Plan

DOCUMENTATION-class. No new tests. Verification is the audit + spec internal consistency.

## Rollback Plan

- Files to revert: `.gov/spec/openrepose_v0_1.md`, this WP file, taskboard row.
- Recovery: `git restore --staged .gov/; git checkout -- .gov/`.

## Decisions Log

- 2026-05-03: per-file state via state.json `files: [...]` array + active_file_id mirror at top-level. Reason: backward compatibility with v0.1 LLM agents that read state.portrait / state.calibration / state.frame directly.
- 2026-05-03: existing commands target the active file by default; optional `file_id` for explicit targeting. Reason: minimum disruption to existing LLM agents; explicit targeting available when needed.
- 2026-05-03: per-AVATAR calibration JSON stays as-is; per-file state holds a cached copy. Reason: operator's mental model is "one calibration per avatar"; multiple open files of the same avatar share one calibration on disk.
- 2026-05-03: spec authored as a section in openrepose_v0_1.md (not a separate file). Reason: it's a cross-cutting addition affecting Feature 1's GUI + Command Surface; lives next to them. v0.2 of the spec may split if it grows.

## Fallback Register

- (none planned at DRAFT stage; DOCUMENTATION-only)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: WP file + taskboard row.
2. Spec authoring: new "## Multi-File Workspace" section + updates to Feature 1 / GUI Requirements + LLM Control Surface references; new manual topic file.
3. WP closure: status REVIEW + Change Ledger.

## Proof Of Implementation

- **Command Runs**: `pwsh scripts/audit-repo.ps1` (exit 0); `git diff` shows the new spec section + manual topic.
- **Proof Artifact**: `target/test-artifacts/WP-I1-036/` (audit log).

## Headless LLM Operation Compliance

- [x] N/A — DOCUMENTATION-class. The spec being authored will impose Headless Compliance on every WP-I1-037+ IMPLEMENTATION WP.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects DONE.
- [ ] Reality Boundary truthful.
- [ ] Audit script exits 0.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded.

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at status DRAFT. Operator surfaced the multi-file workspace need during 2026-05-03 GUI inspection. Authoring deferred to next session per operator request ("i will start a new session to implement this" referring to I2 work; this WP fits naturally alongside I2 in a fresh session).
