# WP-I2-003 - Library Entries CRUD + Tags

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: IN-PROGRESS
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

- [ ] CRUD on library_entries works against real Postgres (pytest-postgresql fixture).
- [ ] tags + entry_tags M-to-N work; tag deduplication on conflict.
- [ ] smart-tag extraction produces expected `auto:` tags from a sample workflow.
- [ ] Filesystem layout `outputs/library/<entry-uuid>/{openpose.json,openpose.png,generated.png,workflow.json,metadata.json,portrait.png}` created on register.
- [ ] Row-level lock on update/delete; conflict raises structured error.
- [ ] pytest zero failures; audit clean.
- [ ] **Manual Impact**: Yes — `feature-3-library-postgresql.md` references the entries+tags primitives; extend with operator-facing notes on the smart-tag extractor and the storage layout when this WP lands.

## Headless LLM Operation Compliance

- [ ] N/A in this WP — pure data layer. Headless commands ship in WP-I2-004.

## Change Ledger

- (filled at REVIEW)

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence.
