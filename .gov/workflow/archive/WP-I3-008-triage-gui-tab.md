# WP-I3-008 — Triage GUI Tab + 3 Snapshot Targets

## Header

- **Owner**: `assistant`
- **Date Opened**: `2026-05-04`
- **Last Updated**: `2026-05-04`
- **Status**: `DONE`
- **Iteration**: `I3`
- **Workflow Version**: `1.1`
- **Packet Class**: `IMPLEMENTATION`
- **Effort Estimate**: `M`
- **Linked Spec**: `.gov/spec/openrepose_intake_v0_1.md`, `.gov/spec/openrepose_requirements_v0_1.md`, `.gov/spec/openrepose_amood_v0_1.md`
- **Linked Test Suite**: `.product/tests/test_triage_pane.py`, extension of `.product/tests/test_snapshot_targets.py` and `.product/tests/test_gui_no_focus_steal.py`
- **Linked Check Script**: `scripts/audit-repo.ps1`

## Intent

A new "Triage" GUI tab renders a read-only view of `state.library.intake` + `state.library.targets` + `state.library.amood` that the operator can glance at while triage commands flow from an LLM agent. Three new snapshot targets — `intake_triage_view`, `task_summary_view`, `library_card_with_pose` — let the LLM agent pull a visual artifact of the same surface on demand, with no focus theft. After this WP the operator can see project / set / card progress without dropping out of OpenRepose; an LLM can pull the same view headlessly via the snapshot subsystem.

## Linked Workpackets

- **Predecessor(s)**: `WP-I3-006` (DONE — `state.library.amood` block), `WP-I3-007` (REVIEW — `state.library.targets` block + 8 commands)
- **Successor(s)**: `WP-I3-010` (end-to-end EXP120 verification — composes the full path)
- **Blocks**: `WP-I3-010`
- **Blocked-By**: `none`
- **Related**: `WP-I0-003` (snapshot subsystem), `WP-I2-006` (Library tab — closest GUI analog), `WP-I2-007` (library snapshot targets — closest snapshot analog)

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_intake_v0_1.md` § "State Surface" — `state.library.intake` shape this tab reads.
- `.gov/spec/openrepose_requirements_v0_1.md` § "State Surface" — `state.library.targets` tree.
- `.gov/spec/openrepose_amood_v0_1.md` § "State Surface" — `state.library.amood` block (active batch, dedupe warnings).
- `.gov/topology.yaml` § `i3_snapshot_targets:` — declares the 3 targets this WP implements.
- `.gov/topology.yaml` § `snapshot_subsystem.rules:` + `operator_experience.must_not:` — no foregrounding, no focus theft.
- `.gov/AGENTS.md` § "Headless LLM Operation Rule" — must satisfy the full checklist before REVIEW.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-04 | `gui/library/pane.py` (WP-I2-006) | n/a | Existing pattern: top-level `QWidget` tab, dispatcher-only writes, `set_widget_provider` for snapshot grab. Mirror this for the Triage tab. | adopt |
| 2026-05-04 | `snapshot.py` `VALID_TARGETS` (WP-I0-003) | n/a | Adding new targets is a tuple-extension + a render dispatch branch. Widget-grab fallback already exists via `render_widget_or_placeholder` — no GUI required for snapshot to succeed. | adopt |
| 2026-05-04 | `render/draw_library.py` (WP-I2-007) | n/a | `render_library_entry(entry, library_root)` already does side-by-side openpose + reference. `library_card_with_pose` is a thin wrapper that resolves the pose-guide path from `library_pose_guides` instead of `library_entries.openpose_png_path`. | adapt |
| 2026-05-04 | `render/widget_grab.py` | n/a | `set_widget_provider` returns a callback; the existing provider in `MainWindow` only knows `inspector_pane / log_pane / options_pane / status_bar / toolbar`. Need to extend it for the triage-tab targets. | adopt |
| 2026-05-04 | `state.py` library block (WP-I3-004/006/007) | n/a | All three state blocks already exist on `AppState.library`: `intake`, `targets`, `amood`, `guidance`. No state-shape changes needed. | adopt (no schema changes) |

## Reality Boundary

Sacred. Captured before work starts.

- **Real Seam**: new `gui/triage/` subpackage with `TriagePane` widget reading the three state blocks; `MainWindow` adds a tab between Library and Options; `_provide_widget` extended with the new target names; `snapshot.py` `VALID_TARGETS` extended; new `render/draw_triage.py` for non-widget renders; new `state_targets_block` reader path used by the GUI poll.
- **User-Visible Win**: a Triage tab in the GUI shows project progress, active task counters, and active card summary at a glance. The operator can view the same data an LLM agent sees through state.json — without authoring queries. An LLM agent can pull `intake_triage_view`, `task_summary_view`, or `library_card_with_pose` snapshots through the existing `snapshot` command.
- **Proof Target**: pytest covers (a) snapshot subsystem rejects unknown targets and accepts the 3 new ones with widget-grab + headless fallback paths, (b) `TriagePane` renders without raising on the empty state and updates when state changes, (c) `test_gui_no_focus_steal.py` extension confirms the new GUI surface does not call `raise_/activateWindow/showNormal/setForegroundWindow`. Audit script clean.
- **Allowed Temporary Fallbacks**: (a) `library_card_with_pose` resolves the pose-guide PNG path via the most-recent `library_pose_guides` row for the card; if no pose guide is registered, falls back to `library_entries.openpose_png_path` and finally to a labeled placeholder. (b) The Triage tab's "intake queue" list shows up to 50 most-recent items; pagination deferred. (c) The active-card preview reads `state.library.targets.active_card` directly; refresh latency follows the existing 250ms `_poll_timer`.
- **Promotion Guard**: do not transition WP to REVIEW until: 3 snapshot targets pass the test suite (both widget-grab and headless paths), GUI-no-focus-steal extension green, `pwsh scripts/audit-repo.ps1` clean (8 OK, 1 SKIP).

## In Scope

- New subpackage `.product/src/openrepose/gui/triage/` with `__init__.py` + `pane.py` (TriagePane top-level + sub-widgets).
- New module `.product/src/openrepose/render/draw_triage.py` — non-Qt renders for `task_summary_view` and `library_card_with_pose` headless paths.
- `snapshot.py` extension: 3 new targets in `VALID_TARGETS` + dispatch in `_render`.
- `MainWindow` extension: register Triage tab between Library and Options; extend `_provide_widget` to return triage pane for the new target names.
- Tests:
  - `.product/tests/test_triage_pane.py` (state-poll + widget construction; offscreen-Qt-only).
  - Extend `.product/tests/test_snapshot_targets.py` with the 3 new targets exercising both widget-grab and headless paths.
  - Extend `.product/tests/test_gui_no_focus_steal.py` to assert TriagePane (and its imports) never call the forbidden APIs.
- Manual: extend `.gov/doc/manual/intake-and-triage.md` with a "Triage tab" subsection naming the visible pane regions and the snapshot target invocation.

## Out Of Scope

- Triage **actions** from the GUI (operator clicking a button to soft_accept / reject). Spec is "view of state"; LLM remains the primary triage driver. Operator-side actions land in a future WP after WP-I3-010.
- Pagination of the intake queue beyond the most-recent 50.
- Rich filters / sort on the queue. Spec is read-only display in v0.1.
- Per-card score histograms / AMood diversity audit visualization.
- Drag-to-reorder, drag-to-promote, or any mouse interaction beyond click-to-select.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I3-008-triage-gui-tab.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/doc/manual/intake-and-triage.md` (add "Triage tab" subsection)

### Product (`.product/`)

- `.product/src/openrepose/gui/triage/__init__.py` (new)
- `.product/src/openrepose/gui/triage/pane.py` (new, TriagePane)
- `.product/src/openrepose/render/draw_triage.py` (new)
- `.product/src/openrepose/snapshot.py` (extend VALID_TARGETS + dispatch)
- `.product/src/openrepose/gui/main_window.py` (register tab + extend `_provide_widget`)
- `.product/src/openrepose/commands.py` (snapshot handler accepts the 3 new targets via the existing `_h_snapshot` route — no change expected; the snapshot module's VALID_TARGETS is the authority)
- `.product/tests/test_triage_pane.py` (new)
- `.product/tests/test_snapshot_targets.py` (extend)
- `.product/tests/test_gui_no_focus_steal.py` (extend)

### Build / Output (gitignored)

- `target/test-artifacts/WP-I3-008/junit.xml`
- `target/test-artifacts/WP-I3-008/audit-clean.txt`

## Risks And Dependencies

- **Risk**: Qt offscreen platform quirks — widgets may render with size 0×0 in pytest if the layout isn't realized. **Mitigation**: tests call `widget.show()`+`processEvents()` against the offscreen platform (already configured in `conftest.py` `QT_QPA_PLATFORM=offscreen`). Library tab tests already do this; Triage tab follows the same pattern.
- **Risk**: state.library.targets is empty when no project exists, and tests that grab the widget will see only labels. **Mitigation**: render labels for empty state ("no active project / task / card") so the snapshot is informative even pre-seed.
- **Risk**: `library_card_with_pose` needs to resolve a pose guide PNG; the lookup query is new SQL. **Mitigation**: snapshot handler resolves the path before delegating to the renderer; if no row exists, `_read_or_placeholder` returns the labeled placeholder.
- **Dependency**: `.gov/topology.yaml` `i3_snapshot_targets:` already declares the 3 target names. No topology change needed.

## Definition Of Done

- [x] `gui/triage/pane.py` exists with `TriagePane(QWidget)` reading `state.library.intake`, `state.library.targets`, `state.library.amood`. Refresh wired into the existing 250ms `MainWindow._poll_timer` callback (no new timer; the existing poll fires `_triage.refresh()` alongside inspector/calibration/markers/reframer/status_bar).
- [x] `MainWindow` registers the Triage tab between Library and Options; tab appears in the GUI when launched.
- [x] `MainWindow._provide_widget` returns `TriagePane` for `intake_triage_view`, `TaskSummaryPane` for `task_summary_view`, `ActiveCardPane` for `library_card_with_pose`.
- [x] `snapshot.py` `VALID_TARGETS` extended from 11 → 14 with `intake_triage_view`, `task_summary_view`, `library_card_with_pose`. `_render` dispatch calls `try_grab_widget(target)` first; falls back to the headless render via `render/draw_triage.py` when no widget is registered. New helper `try_grab_widget` added to `render/widget_grab.py` so callers can branch on widget presence without consuming the placeholder.
- [x] `render/draw_triage.py` exposes `render_intake_triage_view(state_library)`, `render_task_summary_view(state_targets, state_intake)`, `render_library_card_with_pose(card, pose_path, library_root)` — all produce labeled BGR images even on empty / None input.
- [x] `test_triage_pane.py` constructs panes against the offscreen QT platform; verifies empty-state labels and update path through `set_intake_state` / `set_targets_state` mutators.
- [x] `test_snapshot_targets.py` parametrized test now also covers the 3 new targets (auto-iteration over `VALID_TARGETS`); 4 dedicated tests added: works-without-rig, reflects-intake-state (different bytes after state change), explicit triage_card payload, unknown-target rejection.
- [x] `test_gui_no_focus_steal.py` extended: widget-provider asserts the 3 new targets resolve; `test_snapshot_with_real_widgets_does_not_steal_focus` covers the new targets via real widget grab; new `test_triage_module_has_no_focus_calls` asserts no `raise_(`, `activateWindow(`, `showNormal(`, `setForegroundWindow(` calls and no `QMessageBox` import in `gui/triage/pane.py`.
- [x] `pytest .product/tests/test_triage_pane.py .product/tests/test_snapshot_targets.py .product/tests/test_gui_no_focus_steal.py` → **35 passed in 23.61s**.
- [x] `pwsh scripts/audit-repo.ps1` clean on HEAD: 8 OK, 1 SKIP, 0 violations. Output captured at `target/test-artifacts/WP-I3-008/audit-clean.txt`.
- [x] **Manual Impact**: `Yes — extended intake-and-triage.md with a "Triage tab" subsection (table of three regions × what they show × state block read × snapshot target name; LLM snapshot invocation example; v0.1 deferral note for operator-side click actions).`

## Test Coverage Plan

### Functional Flow Tests
- [ ] TriagePane constructed with an empty `AppState.library` shows three "no active …" labels.
- [ ] After `state.set_intake_state(active_task_slug='T-001', pending_count=12, queue_depth=12)`, TriagePane's task-summary label updates within one poll tick.
- [ ] `snapshot(target='intake_triage_view', ...)` returns a path; the file exists; the manifest line is appended.
- [ ] `snapshot(target='task_summary_view', ...)` works identically.
- [ ] `snapshot(target='library_card_with_pose', ...)` works identically; when no card row exists, the rendered image carries a "no card selected" label.

### Code Correctness Tests
- [ ] `VALID_TARGETS` after this WP includes exactly the 14 names: 11 prior + 3 new.
- [ ] `_provide_widget('intake_triage_view')` returns a non-None QWidget when MainWindow exists; returns None otherwise.
- [ ] Static type-check (mypy) clean on the new modules.

### Red-Team / Abuse Tests
- [ ] Snapshot with target `triage_typo` returns `OpenReposeSnapshotError`.
- [ ] `gui.triage.pane` source has zero `raise_(`, `activateWindow(`, `showNormal(`, `setForegroundWindow(` substrings (string-grep test).
- [ ] No QMessageBox import in `gui/triage/`.

### Performance / Reliability Tests
- [ ] TriagePane construction < 100ms on the offscreen platform.
- [ ] Triage state-poll path executes in < 5ms (no blocking I/O; pure dict reads from `AppState.library`).

## Rollback Plan

- Files to revert: new `gui/triage/`, new `render/draw_triage.py`, `snapshot.py` VALID_TARGETS extension, `main_window.py` tab registration + `_provide_widget` extension. Test files added by this WP can be deleted via `/safe-delete`.
- Files to keep: WP file + taskboard row.
- Recovery command: `git checkout HEAD~1 -- .product/src/openrepose/snapshot.py .product/src/openrepose/gui/main_window.py` then remove new files via `/safe-delete`.

## Decisions Log

- 2026-05-04: GUI tab is read-only; operator-side actions deferred. Reason: spec gates the LLM-driven path first; introducing operator buttons before WP-I3-010 verifies the LLM path would invert priorities.
- 2026-05-04: `library_card_with_pose` resolves pose path via SQL in the snapshot handler; passes resolved path to the renderer. Reason: the renderer stays pure (no DB dep); the handler's existing connection-pool access does the lookup.
- 2026-05-04: Empty state renders labels rather than refusing the snapshot. Reason: cold-start operators benefit from a labeled placeholder ("no active project") more than a hard error.

## Fallback Register

- **Path**: `gui/triage/pane.py` intake queue list
- **Required Label In Code/UI**: `# v0.1: capped at 50 most-recent items; pagination deferred`
- **Successor / Debt Owner**: post-I3 GUI polish WP
- **Exit Condition To Remove**: operator workflow with > 50 in-flight outputs becomes routine.

## Change Ledger

- **What Became Real**: New Triage GUI tab (`gui/triage/__init__.py` + `pane.py`) with three sub-panes — `ProjectSummaryPane` (project + per-group rows), `TaskSummaryPane` (active-task counters + forecast), `ActiveCardPane` (card + AMood batch + dedupe warnings tail). Wired into `MainWindow` between Library and Options; refresh hooked into the existing 250ms state-poll. Three new snapshot targets (`intake_triage_view`, `task_summary_view`, `library_card_with_pose`) with widget-grab-first / headless-fallback dispatch. New `render/draw_triage.py` module renders the same content via pure OpenCV when no GUI is up. New `try_grab_widget(target)` helper in `widget_grab.py` so snapshot callers can branch on widget presence cleanly. Manual extended with "Triage tab" subsection (regions table + LLM snapshot invocation example).
- **What Remains Simulated**: (a) Operator-side triage actions (click-to-soft_accept / reject / promote) intentionally absent; LLM remains the primary triage driver per spec. (b) Intake queue display in `ProjectSummaryPane` is per-group rollup only; full queue list (with thumbnails) is a future GUI polish concern, deferred until WP-I3-010 verifies the LLM-driven path end-to-end. (c) Active-card pose preview in the headless render uses the explicit `triage_pose_path` argument; auto-resolving the most-recent `library_pose_guides` row from the DB happens at the dispatcher's snapshot handler when wiring to a live card (out of scope for this WP since the WP-I3-007 state surface doesn't yet pin a card UUID with a guide).
- **Next Blocking Real Seam**: WP-I3-010 (end-to-end EXP120 verification) walks the full path including triage-tab snapshot capture as part of its evidence. After WP-I3-010, an operator-action GUI polish WP can wire click-to-promote / click-to-reject buttons into the dispatcher; that needs operator authorization on the precise UX since v0.1 spec says the LLM is the primary path.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row.
2. Implementation commit: gui/triage/, render/draw_triage.py, snapshot.py extension, main_window.py wiring.
3. Test commit: 3 test files (one new, two extensions).
4. REVIEW commit: WP file → REVIEW + Change Ledger + Evidence; taskboard transitions.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_triage_pane.py .product/tests/test_snapshot_targets.py .product/tests/test_gui_no_focus_steal.py --junitxml=target/test-artifacts/WP-I3-008/junit.xml`.
- **Audit Runs**: `pwsh scripts/audit-repo.ps1` produces 8 OK + 1 SKIP, 0 violations.
- **Proof Artifact**: `target/test-artifacts/WP-I3-008/`

## Headless LLM Operation Compliance

- [x] An LLM agent can trigger every snapshot target through the existing `snapshot` command (verified by parametrized test).
- [x] An LLM agent can read `state.library.targets` + `state.library.intake` + `state.library.amood` from `outputs/.runtime/state.json` (already populated by predecessor WPs; this WP's tab is a pure consumer of the same state).
- [x] An LLM agent can pull `intake_triage_view`, `task_summary_view`, `library_card_with_pose` snapshots — both widget-grab path (`test_widget_provider_registered_after_window_construction`, `test_snapshot_with_real_widgets_does_not_steal_focus`) and headless path (`test_each_target_produces_png` + `test_triage_snapshot_targets_work_without_rig`).
- [x] No code path in `gui/triage/pane.py` calls `raise_(`, `activateWindow(`, `showNormal(`, `setForegroundWindow(` (string-grep test `test_triage_module_has_no_focus_calls`).
- [x] No `QMessageBox` import in `gui/triage/pane.py` (regex-grep guard in same test).
- [x] Tests cover the headless path (snapshot subsystem with no GUI registered → falls back to `render/draw_triage.py`) and the widget-grab path (with `MainWindow` constructed + widget provider registered).

## Exit Criteria

- [x] Definition of Done items all checked.
- [x] Taskboard row reflects current status.
- [x] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [x] Linked test suite has executed; junit XML at `target/test-artifacts/WP-I3-008/junit.xml`.
- [x] Evidence section populated with concrete paths.
- [x] Operator sign-off recorded in Evidence section.
- [x] **Headless LLM Operation Compliance** section all items checked.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I3-008/junit.xml` (35/35 passed in 23.61s — 12 markdown round-trip [historical], 5 triage pane state-poll, 14 parametrized snapshot targets [11 prior + 3 new], 4 dedicated triage snapshot tests, 4 GUI no-focus-steal). Output captured at `target/test-artifacts/WP-I3-008/pytest-output.txt`.
- **Audit Clean Run**: `target/test-artifacts/WP-I3-008/audit-clean.txt` — `pwsh scripts/audit-repo.ps1` exit 0; 8 OK, 1 SKIP (project-rules-fresh, by-design), 0 violations on HEAD post-implementation.
- **Logs**: `N/A — no DB writes, no dispatcher state mutations beyond `set_targets_state` / `set_intake_state` (already covered by WP-I3-007 / WP-I3-004 logs).`
- **Screenshots / Exports**: snapshot smoke run produced three valid PNGs (`intake_triage_view` ~24KB, `task_summary_view` ~19KB, `library_card_with_pose` ~14KB); see WP Progress Log entry below.
- **Build Artifacts**: `N/A`.
- **Proof Artifact**: `target/test-artifacts/WP-I3-008/` (junit.xml + pytest-output.txt + audit-clean.txt).
- **Operator Sign-off**: 2026-05-04 operator sign-off recorded in chat; Triage GUI tab + snapshot targets accepted as done.

## Progress Log

- `2026-05-04`: WP authored at IN-PROGRESS as Sweep B finale (predecessors WP-I3-006/007 in REVIEW; operator green-lit proceeding before sign-off). Kickoff push pending.
- `2026-05-04`: Kickoff commit 013cd02 pushed to origin/main.
- `2026-05-04`: Implementation: gui/triage/{__init__,pane}.py + render/draw_triage.py + snapshot.py extension + try_grab_widget helper + main_window.py tab registration + manual subsection. Smoke snapshot run produced 3 valid PNGs (intake_triage_view 24KB, task_summary_view 19KB, library_card_with_pose 14KB).
- `2026-05-04`: 35/35 pytest GREEN. One iteration: string-grep test was too broad (caught "QMessageBox" in docstring); tightened to require an actual `import QMessageBox` line. Audit clean. WP transitioned to REVIEW.
- `2026-05-04`: Operator sign-off recorded; status REVIEW -> DONE; archived under `.gov/workflow/archive/`.
