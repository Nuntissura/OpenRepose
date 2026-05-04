# WP-I1-037 - Multi-File Workspace Implementation

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-04
- **Last Updated**: 2026-05-04
- **Status**: REVIEW
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: XL
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` section "Multi-File Workspace"
- **Linked Test Suite**: `.product/tests/test_multi_file_workspace.py` (NEW), extensions to `.product/tests/test_command_handlers.py`, `.product/tests/test_drag_and_drop.py`, `.product/tests/test_state_file.py`, `.product/tests/test_snapshot_targets.py`
- **Linked Check Script**: `scripts/audit-repo.ps1`

## Intent

Implement the real multi-file workspace specified by WP-I1-036: multiple portrait files open in closeable tabs, each with its own rig, yaw, calibration/frame/visibility mirror, and headless command targeting. Existing single-file commands keep working by targeting the active file; new commands manage the file list.

## Linked Workpackets

- **Predecessor(s)**: WP-I1-036 DONE (spec), WP-I0-001..004 DONE.
- **Successor(s)**: polish WP for multi-row/column tab overflow if native Qt tab behavior is not enough.
- **Blocks**: future features that assume one global rig only.
- **Blocked-By**: none.
- **Related**: WP-I1-005 drag-and-drop portrait import, WP-I1-016 clear workspace, WP-I3-008 snapshot surfaces, WP-I4-001 state/library hardening.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` - Multi-File Workspace.
- `.gov/AGENTS.md` - Headless LLM Operation Rule.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-04 | Qt for Python QTabWidget docs | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTabWidget.html | Closeable/movable tabs are native via `setTabsClosable(True)` and `setMovable(True)`; use QTabWidget for the first implementation. | adopt |
| 2026-05-04 | WP-I1-036 archived spec research | `.gov/workflow/archive/WP-I1-036-multi-file-workspace-spec.md` | Spec already chose QTabWidget, `files[]` + `active_file_id`, active-file top-level mirror, `open_file`/`close_file`/`set_active_file`/`list_files`, and optional `file_id` targeting. | adopt |
| 2026-05-04 | Existing OpenRepose product architecture | local `.product/src/openrepose/commands.py`, `state.py`, `gui/main_window.py` | Current dispatcher owns one `_rig`; implementation must introduce a file-slot model without breaking existing command names. | adapt |

## Reality Boundary

- **Real Seam**: real file slots in dispatcher/state, real file tabs in GUI, real file-management commands, and real per-file command targeting. No fake tabs that re-import on every switch.
- **User-Visible Win**: operator opens multiple portraits, switches tabs instantly, and each portrait keeps its own yaw/frame/visibility/rig state.
- **Proof Target**: `open_file` three portraits, `list_files` returns three file slots, `set_active_file` changes the active mirror, existing commands affect the targeted slot, GUI shows one tab per file, drag-drop opens all acceptable images.
- **Allowed Temporary Fallbacks**: multi-column tab wrapping may fall back to native QTabWidget scroll buttons for this WP; lazy re-fit on restore is allowed by spec.
- **Promotion Guard**: do not mark REVIEW unless at least the headless command path and the GUI tab path are both implemented. Do not claim multi-column tab wrapping if it falls back to native tabs.

## In Scope

- File-slot model with stable `file_id`.
- New commands: `open_file`, `close_file`, `set_active_file`, `list_files`.
- `import_portrait` preserved as an alias for `open_file`.
- Existing per-file commands target active file by default and accept optional `file_id` where practical in this WP.
- `state.json` gains `files[]` and `active_file_id`; top-level rig/portrait/yaw mirrors active file.
- GUI file tabs with close buttons and empty drop target.
- Drag-drop opens one tab per acceptable image.
- Built-in Help manual update for shipped behavior.

## Out Of Scope

- Tab tear-off / multi-window mode.
- True multi-column custom tab bar if QTabWidget native behavior is insufficient; document fallback truthfully.
- Cross-process multi-operator file presence.
- Persisting full rig meshes to disk; reopen may re-fit from portrait path.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-037-multi-file-workspace-implementation.md`
- `.gov/workflow/TASKBOARD.md`
- `.gov/doc/manual/multi-file-workspace.md`
- `.gov/doc/manual/getting-started.md`

### Product (`.product/`)

- `.product/src/openrepose/commands.py`
- `.product/src/openrepose/state.py`
- `.product/src/openrepose/gui/main_window.py`
- `.product/src/openrepose/gui/drop_helper.py`
- `.product/src/openrepose/gui/toolbar.py` (only if toolbar state needs active-file sync)
- `.product/src/openrepose/snapshot.py` (only if optional `file_id` snapshot targeting lands in this WP)
- `.product/tests/test_multi_file_workspace.py` (NEW)
- `.product/tests/test_drag_and_drop.py`
- `.product/tests/test_state_file.py`

### Build / Output (gitignored)

- `target/test-artifacts/WP-I1-037/`
- `outputs/.runtime/state.json` during local app runs only.

## Risks And Dependencies

- **Risk**: broad dispatcher refactor can regress single-file commands. **Mitigation**: keep `import_portrait` and top-level mirrors backward-compatible.
- **Risk**: calibration/frame/visibility state already spans many modules. **Mitigation**: first implementation stores full rig slots and mirrors active-file state; deeper per-file calibration persistence can follow only if needed.
- **Risk**: simultaneous WP-I1-018 changes touch rig/serializer/render surfaces. **Mitigation**: keep multi-file workspace changes focused on ownership/routing and integrate after hand schema additions are local.

## Definition Of Done

- [x] `open_file`, `close_file`, `set_active_file`, and `list_files` are dispatcher commands.
- [x] `import_portrait` opens a file slot and remains backward-compatible.
- [x] Existing yaw/export/snapshot/dump commands operate on the active file by default.
- [x] `state.json` exposes `files[]`, `active_file_id`, and a top-level active-file mirror.
- [x] GUI shows closeable tabs for open files and an empty drop target when none are open.
- [x] Multi-file drag-drop opens one tab per acceptable image.
- [x] Built-in Help manual reflects shipped behavior, including native Qt tab-overflow fallback.
- [x] **Manual Impact**: Yes - updates `.gov/doc/manual/multi-file-workspace.md` and `.gov/doc/manual/getting-started.md` from planned/spec wording to shipped behavior.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Open three portrait files through commands; active-file mirror changes on `set_active_file`.
- [ ] Close active and non-active files; active selection remains deterministic.
- [ ] Multi-file drop accepts all acceptable images and rejects unsupported files.

### Code Correctness Tests
- [ ] `list_files` shape is stable and includes active flag, path, avatar slug, yaw, and rig status.
- [ ] Existing `set_yaw`/`export_single` routes to the active slot.
- [ ] `clear_workspace` scope is active-file only unless explicitly widened.

### Red-Team / Abuse Tests
- [ ] Unknown `file_id` returns structured error without mutating active file.
- [ ] Duplicate path opens a separate slot only if operator command explicitly requests it; otherwise reuse policy is documented.
- [ ] Closing the last file returns the app to empty state without stale rig references.

### Performance / Reliability Tests
- [ ] Switching active files does not re-run MediaPipe for already-open slots.
- [ ] State write remains atomic with `files[]` present.

## Rollback Plan

- Files to revert: product files listed above and this WP file/taskboard changes.
- Files to keep: WP-I1-036 archived spec remains valid even if this implementation is cancelled.
- Recovery command: use normal git revert on the implementation commit; do not manually delete tracked files.

## Decisions Log

- 2026-05-04: Implement as WP-I1-037 rather than reopening WP-I1-036. Reason: WP-I1-036 is already DONE as documentation/spec; rewriting it would corrupt workflow truth. Alternatives considered: mutate archived WP-I1-036, rejected.
- 2026-05-04: First implementation keeps top-level state mirrors for backward compatibility. Reason: existing LLM agents and GUI panes read the single-file shape.

## Fallback Register

- **Path**: GUI tab overflow. **Required Label In Code/UI**: `tab_overflow_native`. **Successor / Debt Owner**: future polish WP. **Exit Condition To Remove**: custom multi-row/column tab bar implemented and tested.

## Change Ledger

- 2026-05-04: Implemented real dispatcher file slots with stable `file_id`, `files[]` state mirror, new file-management commands, backward-compatible `import_portrait`, active-file routing for existing commands, GUI tab pages, close buttons, and multi-file drop behavior.
- 2026-05-04: Failed import rollback fixed so an invalid second file does not leave the failed path active.
- 2026-05-04: `test_material/` added to `.gitignore` as operator-local validation material; `.gov/topology.yaml` now declares the I1 multi-file command surface so audit help coverage recognizes `open_file`, `close_file`, `set_active_file`, and `list_files`.
- 2026-05-04: Advanced IN-PROGRESS -> REVIEW. Full-suite pytest attempt timed out; focused product/library/sample validations are clean and evidence paths are listed below.

## Checkpoint Commit Plan

1. Governance kickoff commit (this WP + WP-I1-018 promotion + taskboard + research notes).
2. Product implementation commit for command/state model.
3. Product implementation commit for GUI tabs/drop behavior.
4. Governance handoff commit with built-in Help manual and evidence pointers.

## Proof Of Implementation

- **Command Runs**: pytest targets listed above when verification is authorized.
- **Proof Artifact**: `target/test-artifacts/WP-I1-037/`
- **Claim Standard**: do not mark REVIEW without a truthful Change Ledger and evidence paths.

## Headless LLM Operation Compliance

- [x] An LLM agent can trigger file open/close/switch/list through HTTP or inbox commands.
- [x] An LLM agent can read all open files and active file from `outputs/.runtime/state.json`.
- [x] Existing snapshot targets reflect the active file; `file_id` targeting is exercised by sample snapshots.
- [x] No code path calls `raise_()`, `activateWindow()`, `showNormal()`, `setForegroundWindow()`, or equivalent.
- [x] No modal dialogs in response to LLM-originated commands.
- [x] Tests and sample-image validation cover the headless path.

## Exit Criteria

- [x] Definition of Done items all checked.
- [x] Taskboard row reflects current status.
- [x] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [x] Focused test suites executed; results saved under `target/test-artifacts/WP-I1-018-WP-I1-037/`.
- [x] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence section.
- [x] Headless LLM Operation Compliance section all items checked.

## Evidence

- **Test Suite Execution**:
  - `.\.venv\Scripts\python.exe -m compileall -q .product\src\openrepose` -> clean.
  - Focused pytest subset `test_openpose_serialize.py test_rotation.py test_drag_and_drop.py test_state_file.py test_clear_workspace.py` -> 47 passed, 1 known Windows reader-thread warning.
  - PostgreSQL library regression `test_library_entries.py test_library_commands.py` -> 30 passed in 353.44s; JUnit `target/test-artifacts/WP-I1-018-WP-I1-037/library-junit.xml`.
  - Sample library test -> 1 passed in 104.48s; JUnit `target/test-artifacts/WP-I1-018-WP-I1-037/library-sample-junit.xml`.
- **Logs**: `target/test-artifacts/WP-I1-018-WP-I1-037/sample-multifile-openpose-check.json` records 29 samples seen, 3 opened, 2 expected face-detection rejections, 3 active switches, 3 exports, 3 snapshots, and `state_files_count=3`.
- **Screenshots / Exports**: `target/test-artifacts/WP-I1-018-WP-I1-037/snapshots/01-*.png`, `02-1085406391.jpg.openpose.png`, `03-1735900734.jpg.openpose.png`; exported JSON+PNG pairs under `target/test-artifacts/WP-I1-018-WP-I1-037/exports/`.
- **Build Artifacts**: N/A.
- **Proof Artifact**: `target/test-artifacts/WP-I1-018-WP-I1-037/`
- **Full-Suite Caveat**: full pytest timed out after 60 minutes without JUnit; broad non-PostgreSQL slice timed out after 20 minutes with partial audit-test failures caused by missing topology command entries and unignored `test_material/`, both fixed in governance cleanup. Real `scripts/audit-repo.ps1` is clean.
- **Operator Sign-off**: pending.

## Progress Log

- 2026-05-04: WP initialized at IN-PROGRESS after operator requested autonomous overnight implementation. Governance kickoff commit pending before `.product/` edits.
- 2026-05-04: Product implementation pass landed for dispatcher file slots, `open_file`/`close_file`/`set_active_file`/`list_files`, active-file state mirror, GUI file tabs, multi-file drop handling, and built-in Help manual note. Validation evidence pending; WP stays IN-PROGRESS until tests/GUI proof are run.
- 2026-05-04: Focused validation passed for multi-file state/drop regressions after failed-import rollback fix: `compileall` clean; same focused pytest subset -> 47 passed, 1 known Windows reader-warning. Evidence pending under target before REVIEW.
- 2026-05-04: Sample-image multi-file validation opened 3 file slots, switched active file, exported per-file JSON+PNG, and snapshotted each OpenPose viewport; WP moved to REVIEW.
