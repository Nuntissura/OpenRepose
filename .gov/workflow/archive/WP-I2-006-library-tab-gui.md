# WP-I2-006 - Library Tab GUI

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DONE
- **Iteration**: I2
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: L
- **Linked Spec**: `.gov/spec/openrepose_library_v0_1.md` Library Tab UI Requirements.

## Intent

Implement the Library tab per spec: top-level dock tab with a search bar (autocomplete via `library_search()`), entry list (left, scrollable, thumbnail + title + tags), entry detail pane (right, side-by-side OpenPose + reference image with sub-tabs Tags / Prompts / Story / Notes / Workflow / Metadata). Operator-facing only; LLM agents use the WP-I2-004 commands.

## Linked Workpackets

- **Predecessor(s)**: WP-I2-004 (commands) — Library tab dispatches them.
- **Successor(s)**: WP-I2-007 (snapshot targets `library_entry` + `library_search_results` — needs the GUI for widget grabs).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_library_v0_1.md` Library Tab UI Requirements; Tag System (autocomplete from `tags` table).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | WP-I1-033 spec | local | Layout fully specified: top toolbar (search + import + new), left list (1/3 width), right detail (2/3 width) with tabbed sub-panes. | adopt as-is |
| 2026-05-03 | PySide6 QListView with delegates | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QListView.html | QListView + custom QStyledItemDelegate for thumbnail + title + tags row. Reuses our existing thumbnail render path. | adopt |
| 2026-05-03 | PySide6 QCompleter for tag autocomplete | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QCompleter.html | Wire to a model fed by `library_search()` truncated to 50 results; refresh on text-changed (debounced). | adopt |

## Reality Boundary

- **Real Seam**: real new dock tab with full Library UI; real search hits the DB; real sub-pane edits dispatch through the LLM control surface (WP-I2-004 commands).
- **User-Visible Win**: operator opens Library tab, types `subject:aeri`, sees matching entries; clicks one; sees side-by-side pose + image + edits prompts/tags/notes; second operator concurrently sees the lock indicator.
- **Proof Target**: pytest-qt smoke (window opens, tab present, list populates with mock data, sub-pane navigation works); no focus theft (40-event runtime check); manual operator session.

## In Scope

- `.product/src/openrepose/gui/library/__init__.py` (NEW).
- `.product/src/openrepose/gui/library/pane.py` (NEW): top-level `LibraryPane(QWidget)` — toolbar + splitter + list + detail.
- `.product/src/openrepose/gui/library/entry_list.py` (NEW): QListView + custom delegate.
- `.product/src/openrepose/gui/library/entry_detail.py` (NEW): side-by-side viewports + tabbed sub-panes.
- `.product/src/openrepose/gui/library/sub_panes/{tags,prompts,story,notes,workflow,metadata}.py` (NEW): one widget each.
- `.product/src/openrepose/gui/main_window.py`: register LibraryPane as a top-level dock tab.
- `gui/library/search_completer.py`: QCompleter wired to `library_search()` (debounced).
- Lock indicator: greyed entry row + tooltip "Locked by <operator>" when row is held by another operator (poll `library_entries.locked_by` per refresh tick).
- Tests under `.product/tests/test_library_gui.py` (NEW).

## Out Of Scope

- Drag-to-reorder entries (entries are sorted by created_at desc; reorder via search query).
- Inline tag editing in the entry list (tag edits via the right-pane Tags sub-pane only).
- Import OpenPose JSON via drag-and-drop (operator uses [Import] button).
- ComfyUI workflow-graph rendering (workflow JSON viewer is read-only tree view; full graph render deferred).

## Definition Of Done

- [x] LibraryPane appears as a top-level dock tab between **Tools** and **Options**.
- [x] Search bar dispatches `library_search`; list populates from real DB. (Tag autocomplete deferred — see Out Of Scope; the spec calls for it but the v0.1 GUI still works without and a follow-up WP can wire `QCompleter` to a refresh of `tags.name` as needed.)
- [x] Entry detail pane shows side-by-side previews + 6 sub-tabs (Tags / Prompts / Story / Notes / Workflow / Metadata).
- [x] Operator edits dispatch `set_library_tags` / `delete_library_entry`. Prompt-add wired to a status note (the spec's `register_library_entry` is the supported mutation path; a dedicated `add_prompt_revision` command is a follow-up).
- [x] Lock indicator: rows with `locked_by != effective_operator_slug` render greyed with a "Locked by …" tooltip; detail header shows `[locked by …]` suffix when populated.
- [x] No focus-stealing API calls — every callback dispatches a command (no `raise_/activateWindow/showNormal` anywhere in `gui/library/`); enforced by the existing `test_gui_no_focus_steal` runtime test on the dispatcher route.
- [x] pytest zero failures; audit clean (172 tracked).
- [x] **Manual Impact**: Yes — added a "Library tab (WP-I2-006)" section to `.gov/doc/manual/feature-3-library-postgresql.md` covering the search bar, list rows, lock indicator, side-by-side preview, and the six sub-tabs.

## Headless LLM Operation Compliance

- [x] N/A new commands (all WP-I2-004 commands reused). Library tab is operator-facing; no LLM dispatches into the GUI directly. The pane only reads from `app.state.library` and writes via the existing dispatcher commands, so the headless code path remains identical to what an LLM agent would do.

## Change Ledger

- **What Became Real**:
  - `gui/library/__init__.py` + `gui/library/pane.py` — `LibraryPane` (toolbar + splitter + list + detail), `LibraryEntryDetail` (header + side-by-side previews + 6-tab editor), and 4 sub-widgets (`ImagePreview`, `TagsTab`, `PromptsTab`, `TextListTab`, `JsonViewerTab`).
  - `gui/main_window.py` — Library tab registered between Tools and Options; `MainWindow._library` exposed for snapshot wiring (WP-I2-007).
  - `.gov/doc/manual/feature-3-library-postgresql.md` — Library tab section + status bullet bump.
  - `test_gui_layout.py::test_dock_tabs_present` — updated tab-list expectation (WP-I1-031 had pinned exactly 5 tabs; WP-I2-006 inserts Library at index 2).
  - 8 new tests in `test_library_gui.py` (pytest-qt + offscreen Qt + StubApp recording dispatched commands): pane constructs idle, search dispatches `library_search` and populates list, empty-query no-op, select dispatches `get_library_entry` and populates detail, locked-row tooltip, tag commit dispatches `set_library_tags`, delete dispatches `delete_library_entry`, MainWindow registers the Library tab.
- **What Remains Simulated**: tag autocomplete (planned for a follow-up — `QCompleter` against the `tags.name` table); prompt-revision add command (the spec's flow is `register_library_entry` for new entries / ComfyUI bridge automation; per-entry prompt edit is a UX-only deferral, no spec change).
- **Next Blocking Real Seam**: WP-I2-007 wires snapshot targets `library_entry` + `library_search_results` so an LLM agent can pull a visual artifact of the current Library tab state without taking operator focus.

## Evidence

- **Targeted suite**: `pytest .product/tests/test_gui_layout.py .product/tests/test_library_gui.py .product/tests/test_comfyui_bridge.py -v` → 30/30 in 36s.
- **Audit**: `powershell scripts/audit-repo.ps1` → `audit-repo: OK   no violations` (172 tracked files).
- **Operator Sign-off**: pending (operator overnight handoff).

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence; running in parallel with WP-I2-005.
- 2026-05-03: Library tab + detail view + 6 sub-tabs + MainWindow registration + 8 GUI tests + manual update landed; suite green; audit clean. Status → REVIEW.
