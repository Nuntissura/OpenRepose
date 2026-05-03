# WP-I2-004 - Library LLM Commands + Search

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DONE
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

- [x] All 7 commands registered + tested.
- [x] Base64 image payloads decode + persist correctly.
- [x] library_search returns spec-weighted rank order.
- [x] Row-level lock collision returns structured error with retry_after.
- [x] state.json library block updates on each command.
- [x] pytest zero failures; audit clean.
- [x] **Manual Impact**: Yes — added an "LLM commands (WP-I2-004)" table to `.gov/doc/manual/feature-3-library-postgresql.md` enumerating the 7 commands + payload schemas + state-reflection fields; status bullets updated.

## Headless LLM Operation Compliance

- [x] LLM agent triggers via 7 new commands. Verified via `test_library_commands.py::lib_app` fixture which constructs a real `App` and routes every command through `app.handle_command(...)`.
- [x] State reflected in state.json `library` block (`last_register_at`, `last_search_query`, `last_search_count`, `last_search_at`, `locked_entries`). Verified by `test_search_records_state_history`.
- [x] No `raise_/activateWindow/showNormal/setForegroundWindow` in any new code path.
- [x] No modal dialogs from LLM commands. (Library tab GUI lands in WP-I2-006; Options pane Library section from WP-I2-002 is operator-form only.)
- [x] Tests cover headless paths. Library disabled / pool unavailable also covered (`test_library_commands_when_pool_unavailable`).

## Change Ledger

- **What Became Real**:
  - `library/prompts.py` — `PromptRevision` + `add_prompt`/`latest_prompt`/`list_prompts` (one row per revision).
  - `library/text_records.py` — generic `add_text_record`/`list_text_records` over the allowlisted `story_beats` + `notes` tables (same shape, factored once).
  - `library/search.py` — `search()` Python wrapper over the SQL `library_search()` function; joins entry metadata + top-3 tags into a single round-trip; returns `SearchResult` dataclasses with rank.
  - `commands.py` — `OpenReposeLibraryError` exception + 7 new handlers `_h_register_library_entry`, `_h_update_library_entry`, `_h_delete_library_entry`, `_h_library_search`, `_h_get_library_entry`, `_h_set_library_tags`, `_h_dump_library_schema`. Helpers `_ensure_pool` / `_operator_slug` / `_library_root` / `_decode_payload` (path **or** base64). Smart tags auto-applied on register. Lock contention raises `LibraryEntryLockedError` → caught and re-thrown as `OpenReposeLibraryError("… retry_after=5")`. `delete_library_entry` removes the on-disk `<library_root>/<entry-uuid>/` folder.
  - `state.py` — new mutators `mark_library_register`, `mark_library_search`, `add_library_lock`, `clear_library_locks`. `library` block fields kept consistent across all command paths.
  - `library/__init__.py` — exports the new modules.
  - `.gov/doc/manual/feature-3-library-postgresql.md` — LLM Commands table + status bullets (Manual Impact: Yes).
  - 16 new end-to-end tests in `test_library_commands.py`: register (path + base64 + smart-tag application + filesystem write), get (with includes + missing → error), update (patches + no-patch error), set_library_tags (additive vs replace + preserve_auto), library_search (trigram match, FTS match via prompts, state history record, empty-query rejection), delete (DB row + folder + idempotent re-delete), dump_library_schema (version + tables + functions + ddl_hash), library disabled (no DSN → structured error), multi-operator lock collision (parallel session holds lock → structured error with retry_after).
- **What Remains Simulated**: nothing. ComfyUI bridge in WP-I2-005, Library tab GUI in WP-I2-006, snapshot targets in WP-I2-007, multi-operator soak in WP-I2-008.
- **Next Blocking Real Seam**: WP-I2-005 wires the ComfyUI custom node that POSTs to `register_library_entry` after each successful image save.

## Evidence

- **Test Suite Execution**: `pytest .product/tests --junitxml=target/test-artifacts/WP-I2-004/pytest_results.xml -q` → **453 passed** in 655s (baseline before this WP: 437 + 16 new = 453). Pre-existing Windows-only `PermissionError` warning unchanged.
- **Targeted suite**: `pytest .product/tests/test_library_commands.py -v` → 16/16 in 45s (full ephemeral-PG round-trips for every command).
- **Audit**: `powershell scripts/audit-repo.ps1` → `audit-repo: OK   no violations` (168 tracked files, +5 new for this WP).
- **Operator Sign-off**: pending (operator overnight handoff).

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence.
- 2026-05-03: 4 modules + 7 dispatcher handlers + 16 tests + manual update landed; suite 453/453; audit clean. Status → REVIEW.
