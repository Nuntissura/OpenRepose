# WP-I2-007 - Library Snapshot Targets

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DONE
- **Iteration**: I2
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_library_v0_1.md` Snapshot Targets.

## Intent

Add the two new snapshot targets per spec: `library_entry` (selected entry's side-by-side pose + reference image) and `library_search_results` (4×6 thumbnail grid of current search results). Both honor existing snapshot subsystem rules (no focus theft, atomic write, manifest entry).

## Linked Workpackets

- **Predecessor(s)**: WP-I2-004 (search returns entries to render); WP-I2-006 (Library tab provides the live widgets).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_library_v0_1.md` Snapshot Targets.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Existing snapshot subsystem | `snapshot.py`, `render/draw_*.py` | Pattern: add target to VALID_TARGETS; add `_render` branch; pass needed kwargs through dispatcher. | adopt |

## Reality Boundary

- **Real Seam**: two new snapshot targets producing PNGs under `outputs/.runtime/snapshots/`.
- **User-Visible Win**: LLM agent can `snapshot {target: "library_entry"}` to grab the currently-selected entry's preview, or `snapshot {target: "library_search_results"}` for a thumbnail grid of the last search.

## In Scope

- `.product/src/openrepose/render/draw_library.py` (NEW): `render_library_entry(entry)` + `render_library_search_results(entries)`.
- `snapshot.py`: add to VALID_TARGETS + `_render` dispatch.
- `commands.py`: `_h_snapshot` resolves entry / results from current state.
- `state.py`: `library.last_search_results: list[dict]` for the snapshot to read.
- Tests.

## Out Of Scope

- Per-entry snapshot subscription (LLM polls instead).
- High-res renders (uses existing canvas size conventions).

## Definition Of Done

- [x] Both targets in `VALID_TARGETS`.
- [x] Both produce non-empty PNGs (tested unit + integration).
- [x] Snapshot tests for both pass (9/9 in `test_library_snapshots.py`).
- [x] No focus theft — pure OpenCV / numpy renderers; no Qt imports in `render/draw_library.py`; the snapshot subsystem itself already enforces no-focus-hijack rules.
- [x] pytest zero failures; audit clean (180 tracked).
- [x] **Manual Impact**: Yes — added a "Snapshots (WP-I2-007)" subsection to `.gov/doc/manual/feature-3-library-postgresql.md` listing both targets + their state-source + non-focus rules; status bullets updated.

## Headless LLM Operation Compliance

- [x] Both targets exposed via the existing `snapshot` command.
- [x] State reflected: `state.library.last_entry` (set by `get_library_entry`) and `state.library.last_search_results` (set by `library_search`, capped at 24).
- [x] No focus-stealing API in any new code path (pure OpenCV rendering).
- [x] No modal dialogs from snapshot commands.
- [x] Tests cover the headless dispatcher path end-to-end.

## Change Ledger

- **What Became Real**:
  - `render/draw_library.py` — `render_library_entry(entry, library_root)` and `render_library_search_results(results, library_root)`. Pure OpenCV/numpy. Side-by-side composition (left openpose.png + right generated/portrait.png + 32-pixel header strip with title / avatar / yaw_bin / [locked-by]); 4×6 letterboxed thumbnail grid for search results. Missing files render labeled placeholders so the path never crashes.
  - `snapshot.py` — extended `VALID_TARGETS` with `library_entry` + `library_search_results`; added optional `library_entry`, `library_search_results`, `library_root` kwargs to `snapshot()`; routed both through `_render`.
  - `state.py` — `library` block gains `last_search_results` (list, capped at 24 per the snapshot grid) and `last_entry` (dict | None). New mutators `mark_library_entry_view()` and the extended `mark_library_search(results=…)`.
  - `commands.py` — `_h_library_search` now records the truncated result list into state; `_h_get_library_entry` records the fetched payload; `_h_snapshot` resolves the new library targets from state and passes the library root to the snapshot subsystem.
  - `.gov/doc/manual/feature-3-library-postgresql.md` — Snapshots subsection enumerates both targets + sources (Manual Impact: Yes).
  - 9 new tests in `test_library_snapshots.py`: 7 pure renderer tests (placeholder, real-files composition, missing-file resilience, locked-label, no-results placeholder, grid dimensions, VALID_TARGETS membership) + 2 dispatcher round-trips against ephemeral PG (snapshot command for both targets writes a non-empty PNG that loads via OpenCV).
- **What Remains Simulated**: nothing. All eight I2 WPs ship the contract the spec locks; only WP-I2-008 (verification + setup doc) remains.
- **Next Blocking Real Seam**: WP-I2-008 — multi-operator stress + pg_dump round-trip + the operator setup doc; closes I2.

## Evidence

- **Targeted suite**: `pytest .product/tests/test_library_snapshots.py -v` → 9/9 in 40s (incl. ephemeral-PG dispatcher round-trip for both targets).
- **Full suite**: `pytest .product/tests --junitxml=target/test-artifacts/WP-I2-007/pytest_results.xml -q` → **483 passed** in 850s (baseline before this WP: 472 + 9 new + 2 from existing snapshot/state coverage = 483; one pre-existing Windows-only `PermissionError` warning unchanged).
- **Audit**: `powershell scripts/audit-repo.ps1` → `audit-repo: OK   no violations` (180 tracked files).
- **Operator Sign-off**: pending (operator overnight handoff).

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence.
- 2026-05-03: Renderers + snapshot wiring + state extension + 9 tests + manual update landed; suite 483/483; audit clean. Status → REVIEW.
