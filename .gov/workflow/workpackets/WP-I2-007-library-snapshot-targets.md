# WP-I2-007 - Library Snapshot Targets

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: IN-PROGRESS
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

- [ ] Both targets in VALID_TARGETS.
- [ ] Both produce non-empty PNGs.
- [ ] Snapshot tests for both pass.
- [ ] No focus theft.
- [ ] pytest zero failures; audit clean.
- [ ] **Manual Impact**: Yes — `feature-3-library-postgresql.md` lists the new `library_entry` + `library_search_results` snapshot targets.

## Headless LLM Operation Compliance

- [x] Both targets exposed via existing `snapshot` command.

## Change Ledger

- (filled at REVIEW)

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence.
