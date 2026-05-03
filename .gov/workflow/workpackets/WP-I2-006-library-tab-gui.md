# WP-I2-006 - Library Tab GUI

## Header

- **Owner**: TBD
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DRAFT
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

- [ ] LibraryPane appears as a top-level dock tab.
- [ ] Search bar + autocomplete + list populate from real DB.
- [ ] Entry detail pane shows side-by-side + 6 sub-tabs.
- [ ] Each sub-pane edit dispatches the appropriate command.
- [ ] Lock indicator shows for entries held by other operators.
- [ ] No focus-stealing API calls (runtime test on 40 search + edit events).
- [ ] pytest zero failures; audit clean.
- [ ] **Manual Impact**: Yes — `feature-3-library-postgresql.md` needs a Library Tab UI walkthrough subsection (search, list, detail, sub-tabs, lock indicator).

## Headless LLM Operation Compliance

- [x] N/A new commands (all WP-I2-004 commands reused). Library tab is operator-facing; no LLM dispatches into the GUI directly.

## Change Ledger

- (filled at REVIEW)

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
