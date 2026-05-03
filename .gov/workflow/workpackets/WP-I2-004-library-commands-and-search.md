# WP-I2-004 - Library LLM Commands + Search

## Header

- **Owner**: TBD
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DRAFT
- **Iteration**: I2
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_library_v0_1.md` Command Surface (7 commands) + library_search() function + state.json `library` block.

## Intent

Wire the Feature 3 spec's 7 LLM commands into the dispatcher: `register_library_entry`, `update_library_entry`, `delete_library_entry`, `library_search`, `get_library_entry`, `set_library_tags`, `dump_library_schema`. Implements CRUD-on-prompts + story_beats + notes alongside (the schema exists; this WP wires the editing). Search uses the `library_search()` SQL function from WP-I2-001's migration (hybrid trigram + tsvector ranking).

## Linked Workpackets

- **Predecessor(s)**: WP-I2-001 (DB pool + library_search() SQL function), WP-I2-002 (Settings), WP-I2-003 (CRUD primitives).
- **Successor(s)**: WP-I2-005 (ComfyUI bridge POSTs `register_library_entry`), WP-I2-006 (Library tab GUI dispatches all 7 commands).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_library_v0_1.md` Command Surface; state.json `library` block (last_search_query / last_search_count / last_register_at / pending_writes / locked_entries).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | WP-I1-033 spec | local | All 7 commands + payload schemas locked. | adopt as-is |
| 2026-05-03 | Existing dispatcher pattern | `commands.py` | `_h_<command>(d, cmd) -> dict` + `_HANDLERS` registration. Mirror the calibration / settings command shape. | adopt |
| 2026-05-03 | psycopg 3 transactions | https://www.psycopg.org/psycopg3/docs/basic/transactions.html | `with pool.connection() as conn:` + `with conn.transaction():` for atomic CRUD. | adopt |

## Reality Boundary

- **Real Seam**: real LLM-driven library CRUD via the existing HTTP + inbox channels; real search via `library_search()` returning hybrid-ranked results.
- **User-Visible Win**: an LLM agent can `register_library_entry` (with base64 image payloads), `library_search "subject:aeri pose:her-right-30"`, `update_library_entry` (add tags), all without touching the GUI.
- **Proof Target**: pytest covers each command happy path + error paths; search rank order matches spec weights; row-level lock collision rejected with structured error.

## In Scope

- `.product/src/openrepose/library/prompts.py` (NEW), `.product/src/openrepose/library/story_beats.py` (NEW), `.product/src/openrepose/library/notes.py` (NEW): one-row-per-revision insert + read latest + read all helpers.
- `.product/src/openrepose/library/search.py` (NEW): `library_search(pool, query, limit)` wrapper around the SQL function; returns `[(entry_id, rank, top_tags, title, avatar_slug, yaw_bin), ...]`.
- `.product/src/openrepose/commands.py`: 7 new handlers `_h_register_library_entry`, `_h_update_library_entry`, `_h_delete_library_entry`, `_h_library_search`, `_h_get_library_entry`, `_h_set_library_tags`, `_h_dump_library_schema`. Base64 image payloads decoded + persisted via WP-I2-003 storage helpers. Errors raised as `OpenReposeLibraryError` (added to dispatcher catch list).
- `.product/src/openrepose/state.py`: `library` block updates on each command (`last_register_at`, `last_search_query`, `last_search_count`, `pending_writes`, `locked_entries`).
- Tests: each command + happy + error paths; multi-operator lock collision; search ranking.

## Out Of Scope

- Snapshot targets (WP-I2-007).
- ComfyUI bridge (WP-I2-005).
- Library tab GUI (WP-I2-006).
- Bulk re-tagging tooling beyond `set_library_tags` (future).

## Definition Of Done

- [ ] All 7 commands registered + tested.
- [ ] Base64 image payloads decode + persist correctly.
- [ ] library_search returns spec-weighted rank order.
- [ ] Row-level lock collision returns structured error with retry_after.
- [ ] state.json library block updates on each command.
- [ ] pytest zero failures; audit clean.

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via 7 new commands.
- [ ] State reflected in state.json `library` block.
- [ ] No raise_/activateWindow/showNormal/setForegroundWindow.
- [ ] No modal dialogs from LLM commands.
- [ ] Tests cover headless paths.

## Change Ledger

- (filled at REVIEW)

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
