# WP-I2-003 - Library Entries CRUD + Tags

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DONE
- **Iteration**: I2
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_library_v0_1.md` Database Schema (library_entries, tags, entry_tags) + Tag System + Storage Layout.
- **Linked Test Suite**: `.product/tests/test_library_entries.py` (NEW); `.product/tests/test_library_tags.py` (NEW).

## Intent

Implement CRUD on `library_entries` and the M-to-N `entry_tags` relation. Includes the smart-tag extractor (`auto:model:`, `auto:sampler:`, etc. from metadata + workflow JSON), the tag taxonomy helpers, and the filesystem storage layout (`outputs/library/<entry-uuid>/`). Foundation for WP-I2-004 (commands), WP-I2-005 (ComfyUI bridge), WP-I2-006 (GUI).

## Linked Workpackets

- **Predecessor(s)**: WP-I2-001 (DB pool + schema), WP-I2-002 (Settings.library_root).
- **Successor(s)**: WP-I2-004 (commands wire CRUD into LLM control surface), WP-I2-005 (ComfyUI bridge calls CRUD), WP-I2-006 (Library tab GUI).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_library_v0_1.md` library_entries / tags / entry_tags schema; Storage Layout.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | WP-I1-033 spec | local | Schema + storage layout fully locked. `library_entries.id` is UUID; tags reference by id; auto-tags prefix with `auto:`. | adopt as-is |
| 2026-05-03 | psycopg 3 Row Factories | https://www.psycopg.org/psycopg3/docs/advanced/typing.html | dict_row + class_row map result rows to dict / dataclass; use class_row(LibraryEntry) for typed access. | adopt |

## Reality Boundary

- **Real Seam**: real PostgreSQL CRUD + filesystem entries under `outputs/library/<entry-uuid>/`; real `auto:` smart tags extracted on insert.
- **User-Visible Win**: future LLM commands + GUI can register / query / update / delete library entries.
- **Proof Target**: pytest CRUD round-trips; tag insertion + dedup; smart-tag extraction from a sample workflow JSON; filesystem layout matches spec.

## In Scope

- `.product/src/openrepose/library/__init__.py` (NEW).
- `.product/src/openrepose/library/entries.py` (NEW): `LibraryEntry` dataclass; `create_entry()`, `get_entry()`, `update_entry()`, `delete_entry()` functions; row-level locks (`SELECT ... FOR UPDATE NOWAIT`) on update / delete.
- `.product/src/openrepose/library/tags.py` (NEW): `add_tag_to_entry()`, `remove_tag_from_entry()`, `set_entry_tags()` (with `replace` flag); tag dedup; smart-tag prefix `auto:` enforcement.
- `.product/src/openrepose/library/smart_tags.py` (NEW): `extract_smart_tags(metadata, workflow_json)` — returns `[auto:model:..., auto:sampler:..., auto:lora:..., auto:custom_node:..., auto:cfg:..., auto:steps:..., auto:seed:...]`.
- `.product/src/openrepose/library/storage.py` (NEW): `write_entry_files(entry_id, root, openpose_json?, openpose_png?, generated_image?, portrait?, workflow_json?)` — writes the `<entry-uuid>/` folder with whatever files are provided.
- Tests: CRUD + tag + smart-tag extraction + filesystem layout.

## Out Of Scope

- Prompts / story_beats / notes (WP-I2-004 — wired into commands but the tables created in WP-I2-001).
- LLM commands (WP-I2-004).
- ComfyUI bridge (WP-I2-005).
- Library tab GUI (WP-I2-006).
- Search (WP-I2-004).

## Definition Of Done

- [x] CRUD on library_entries works against real Postgres (pytest-postgresql fixture).
- [x] tags + entry_tags M-to-N work; tag deduplication on conflict.
- [x] smart-tag extraction produces expected `auto:` tags from a sample workflow.
- [x] Filesystem layout `outputs/library/<entry-uuid>/{openpose.json,openpose.png,generated.png,workflow.json,metadata.json,portrait.png}` created on register.
- [x] Row-level lock on update/delete; conflict raises structured error.
- [x] pytest zero failures; audit clean.
- [x] **Manual Impact**: Yes — extended `.gov/doc/manual/feature-3-library-postgresql.md` with the smart-tag extractor table (auto:model / sampler / scheduler / lora / custom_node / cfg / steps / seed) and the per-entry filesystem layout; status bullets now reflect WP-I2-001/002/003 in REVIEW.

## Headless LLM Operation Compliance

- [ ] N/A in this WP — pure data layer. Headless commands ship in WP-I2-004.

## Change Ledger

- **What Became Real**:
  - `.product/src/openrepose/library/__init__.py` — package facade exporting CRUD + tags + smart-tags + storage helpers.
  - `library/entries.py` — `LibraryEntry` dataclass; `create_entry/get_entry/list_entries/update_entry/delete_entry`. Update + delete acquire `SELECT … FOR UPDATE NOWAIT`; conflict surfaces `LibraryEntryLockedError` (preserves the structured-error contract from the spec). Update validates field whitelist, completeness, and JSONB-encodes `metadata` + `comfyui_workflow`.
  - `library/tags.py` — `add_tags/remove_tags/list_entry_tags/set_entry_tags`. Tag normalization (lowercase + strip), `INSERT … ON CONFLICT DO NOTHING` upsert, `set_entry_tags(replace=True, preserve_auto=True)` keeps `auto:` tags by default per spec.
  - `library/smart_tags.py` — `extract_smart_tags(metadata, workflow)`. Recognises ComfyUI API + editor formats. Extracts `auto:model/sampler/scheduler/lora/custom_node/cfg/steps/seed` with stable ordering and dedup. Slugifier strips unsafe chars + lowercases.
  - `library/storage.py` — `EntryFiles` dataclass; `ensure_entry_dir`, `write_entry_files` (atomic .tmp+rename for every payload; selective writing of only the fields the caller supplies), `relative_to_root` helper for the DB-stored relative paths.
  - `.gov/doc/manual/feature-3-library-postgresql.md` — updated with current implementation status + smart-tag table + storage layout sections (Manual Impact: Yes).
  - 31 new tests:
    - `test_smart_tags.py` (10) — slugifier edge cases; API + editor workflow shapes; lora dedup; metadata fallback; cfg=0 not dropped; workflow model overrides metadata model.
    - `test_library_storage.py` (7) — entry-dir creation; partial writes; atomic .tmp behavior; overwrite; relative-to-root posix output and out-of-root fallback.
    - `test_library_entries.py` (14) — CRUD round-trip, validation, list filters, update field whitelist, completeness validation, delete cascades to tags, set_entry_tags add vs replace + preserve_auto, lock collision (`LibraryEntryLockedError` from a parallel session), tag normalization + dedup.
- **What Remains Simulated**: nothing within scope. `prompts` / `story_beats` / `notes` row helpers ship in WP-I2-004 alongside the LLM commands that need them; no half-built code left.
- **Next Blocking Real Seam**: WP-I2-004 wires `register_library_entry`, `update_library_entry`, `delete_library_entry`, `library_search`, `get_library_entry`, `set_library_tags`, `dump_library_schema` against this data layer + the `LibraryPool`.

## Evidence

- **Test Suite Execution**: `pytest .product/tests --junitxml=target/test-artifacts/WP-I2-003/pytest_results.xml -q` → **437 passed** in 590s (baseline before this WP: 406 + 31 new = 437). Pre-existing Windows-only `PermissionError` warning in `test_state_write_atomic_no_par0` fixture-cleanup race is unchanged from baseline.
- **Targeted suites**: smart-tags + storage (no DB) → 17/17 in 1.07s; library_entries (DB) → 14/14 in 60s.
- **Audit**: `powershell scripts/audit-repo.ps1` → `audit-repo: OK   no violations` (160 tracked files, +7 new for this WP).
- **Operator Sign-off**: pending (operator overnight handoff).

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence.
- 2026-05-03: Implementation + tests + manual update landed; full suite 437/437; audit clean. Status → REVIEW.
