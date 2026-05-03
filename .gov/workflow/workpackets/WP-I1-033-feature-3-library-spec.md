# WP-I1-033 - Feature 3 Spec: OpenPose Library + ComfyUI Coupling + PostgreSQL DB

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: READY
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: DOCUMENTATION
- **Effort Estimate**: L
- **Linked Spec**: NEW `.gov/spec/openrepose_library_v0_1.md` + roadmap reference in `.gov/spec/openrepose_v0_1.md` + index update in `.gov/spec/README.md`.
- **Linked Test Suite**: N/A (DOCUMENTATION-class).
- **Linked Check Script**: N/A.

## Intent

Author the canonical contract for **Feature 3: OpenPose Library + ComfyUI Coupling**. Locks: PostgreSQL as the storage backend (operator-confirmed multi-operator from day one), psycopg 3 as the client, the database schema, the storage layout (binary blobs vs filesystem), tag taxonomy + fuzzy search architecture, the Library Tab UI surface, the LLM command surface, the ComfyUI custom-node bridge contract, the multi-operator concurrency model. Output is a complete spec section that an implementation iteration (I2+) can build against without further scope debate. **No product code in this WP — spec authoring only.**

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 (DONE), WP-I1-001 (DONE — operator-marked overlay precedent for tag/marker UX).
- **Successor(s)**: WP-I2-001..N (Feature 3 implementation iteration — postgres setup, schema migration, library tab UI, LLM commands, ComfyUI custom node, fuzzy search, multi-operator coordination). All gated on this spec being DONE.
- **Blocks**: every Feature 3 implementation WP — none can start until this spec is DONE.
- **Blocked-By**: none.
- **Related**: WP-I1-027 (Settings persistence — pattern reused for DB connection settings), WP-I1-022 (Read OpenPose JSON as alternate input — natural import path for the library).

## Linked Requirements / Spec Sections

- New `.gov/spec/openrepose_library_v0_1.md` — full Feature 3 contract.
- `.gov/spec/openrepose_v0_1.md` — extend Iteration Roadmap to point at Feature 3.
- `.gov/spec/README.md` — register the new spec file in the Active Specs table.
- `.gov/topology.yaml` — add `feature_3:` block under `terminology:` (no new locked terminology beyond tag/folder names).
- `.gov/AGENTS.md` Headless LLM Operation Rule — Feature 3 commands must be reachable headlessly.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | psycopg vs asyncpg comparison (fernandoarteaga.dev, Tiger Data, Leapcell) | https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/ ; https://www.tigerdata.com/blog/psycopg2-vs-psycopg3-performance-benchmark | psycopg 3 is the modern Pythonic client: dual sync/async API, Row Factories that map results to dataclasses / Pydantic models, native psycopg_pool for connection management. asyncpg is ~5x faster but async-only — not needed for OpenRepose's dispatcher, which is sync-first (pytest uses sync fixtures). | adopt **psycopg 3** for the dual API |
| 2026-05-03 | Tiger Data Top PostgreSQL Drivers for Python | https://www.tigerdata.com/learn/top-postgresql-drivers-for-python | Confirms psycopg 3 as the Python-PostgreSQL standard going into 2026. SQLAlchemy on top of psycopg if/when ORM-level features are needed. | adopt psycopg 3 directly; defer SQLAlchemy unless the schema grows complex enough to warrant it |
| 2026-05-03 | PostgreSQL Full-Text Search docs | https://www.postgresql.org/docs/current/textsearch.html | `tsvector` + `tsquery` + GIN index is the standard full-text path. `setweight` lets prompts get weight A, story beats B, notes C, etc. `ts_rank` for relevance scoring. | adopt for prompt / story-beat / notes search |
| 2026-05-03 | PostgreSQL pg_trgm extension | https://dev.to/talemul/fuzzy-string-matching-in-postgresql-with-pgtrgm-trigram-search-tutorial-2hc6 ; https://www.aapelivuorinen.com/blog/2021/02/24/postgres-text-search/ | `pg_trgm` enables trigram-based fuzzy matching with `%` operator + GIN index. Good for tag matching + title fuzziness where typos are common. Combine with full-text via UNION or a hybrid scoring function. | adopt for tags + fuzzy title search |
| 2026-05-03 | ComfyUI workflow + metadata custom nodes (SaveImageWithMetaData, image-saver, Crystools) | https://github.com/nkchocoai/ComfyUI-SaveImageWithMetaData ; https://github.com/alexopus/ComfyUI-Image-Saver ; https://github.com/giriss/comfy-image-saver | Standard pattern: ComfyUI custom node hooks into the save-image step, captures workflow JSON from the node graph + extracted metadata, writes alongside the PNG. For OpenRepose round-trip: bundle a custom node that POSTs to OpenRepose's existing HTTP control surface (`/command`) with `register_library_entry` payload (workflow JSON + PNG bytes + tags + optional notes). | adopt — POST-back via existing HTTP channel; no new transport |
| 2026-05-03 | ComfyUI workflow concept docs | https://docs.comfy.org/development/core-concepts/workflow | ComfyUI workflows are stored as JSON natively + embedded in PNG metadata via PNGInfo. Both surfaces are accessible from a custom node. | adopt — store both as separate columns (JSON column + PNG bytes column / path) |
| 2026-05-03 | Existing OpenRepose HTTP channel (`channels/http.py`) | local | Already a localhost HTTP endpoint receiving JSON commands. Extending it with `register_library_entry` (multipart-or-base64-encoded image + metadata) is straightforward; no new server stack needed. | adopt |
| 2026-05-03 | psycopg_pool docs | https://www.psycopg.org/psycopg3/docs/advanced/pool.html | Built-in pool with health checks. Default min_size=4, max_size=10 — fine for multi-operator on a single workstation; tune later. | adopt |
| 2026-05-03 | Alembic vs hand-rolled migrations | community knowledge | For a single-target schema with infrequent changes, hand-rolled SQL `migrations/NNN_description.sql` files are simpler than Alembic and don't pull in SQLAlchemy. Adopt later if schema churn warrants. | adopt hand-rolled migrations for v0.1; revisit if needed |

Decisions locked by research:

- **Client**: psycopg 3 (`psycopg[binary]`).
- **Connection pooling**: `psycopg_pool.ConnectionPool` (sync) for the dispatcher.
- **Search**: `tsvector` + GIN for prompts / story_beats / notes (full-text); `pg_trgm` + GIN for tags + titles (fuzzy). Hybrid scoring via SQL function `library_search(query)` returning `(entry_id, rank)`.
- **Migrations**: hand-rolled SQL files `.product/migrations/NNN_<slug>.sql`; small migrator runs on app startup if `schema_version` table is behind.
- **ComfyUI bridge**: ship a custom node `comfyui-openrepose-bridge` (separate folder under `.product/comfyui-bridge/`) that POSTs to `http://localhost:8765/command` with `register_library_entry`.
- **Image storage**: filesystem (`outputs/library/<entry-uuid>.png`) with DB column storing relative path; not BLOB columns. Reason: PostgreSQL BLOBs work but are awkward for backup / inspection; filesystem is operator-readable and standard. DB stores metadata + path.
- **Multi-operator concurrency**: row-level locks via `SELECT ... FOR UPDATE` on edits; optimistic concurrency on bulk re-tagging (timestamp-based conflict detection).

## Reality Boundary

- **Real Seam**: a real new spec file `.gov/spec/openrepose_library_v0_1.md` exists with the full Feature 3 contract. Spec README's Active Specs table lists it. `openrepose_v0_1.md`'s Iteration Roadmap points to Feature 3. WP-I2-001+ implementation WPs can be drafted against this spec without further scope ambiguity.
- **User-Visible Win**: the next assistant who picks up Feature 3 implementation reads `openrepose_library_v0_1.md`, knows: which DB client to use (psycopg 3), what the schema looks like, what the LLM commands are, what the ComfyUI custom node does, where images live, how multi-operator works. No further research-first pass needed.
- **Proof Target**: `git diff` shows the new spec file with all 13 sections (Purpose, Inputs, Database Schema, Storage Layout, Tag System, Library Tab UI, Command Surface, ComfyUI Bridge, Multi-Operator Concurrency, State File Reflection, Snapshot Targets, Out Of Scope, Reality Boundary); `pwsh scripts/audit-repo.ps1` exits 0; spec README + roadmap cross-references in place.
- **Allowed Temporary Fallbacks**: none.
- **Promotion Guard**: do not promote to DONE until the operator confirms the spec is complete enough to start the I2 implementation iteration without ambiguity.

## In Scope

- Author `.gov/spec/openrepose_library_v0_1.md` — 13 subsections matching Feature 1/2 depth:
  1. Purpose
  2. Inputs (OpenPose JSON, OpenPose PNG, prompts, story beats, notes, tags, ComfyUI workflow JSON, source image)
  3. Database Schema (entries, tags, entry_tags, prompts, story_beats, notes, comfyui_workflows, schema_version, with PostgreSQL DDL outline)
  4. Storage Layout (filesystem under `outputs/library/<entry-uuid>/`; DB stores paths + metadata)
  5. Tag System (taxonomy: free-form tags + namespace prefixes like `subject:aeri`, `pose:her-right-30`, `mood:intimate`; fuzzy search via `pg_trgm`; full-text search via `tsvector` for prompts / story_beats / notes; hybrid `library_search()` SQL function)
  6. Library Tab UI Requirements (side-by-side OpenPose preview + reference image; tag editor; prompt / story-beat / notes panes; search bar with smart-tag autocomplete; entry list with thumbnails; ComfyUI workflow JSON viewer)
  7. Command Surface — new commands: `register_library_entry`, `update_library_entry`, `delete_library_entry`, `library_search`, `get_library_entry`, `set_library_tags`, `dump_library_schema`
  8. ComfyUI Bridge / Custom Node Contract (`.product/comfyui-bridge/` — custom node that POSTs to OpenRepose `/command` after image generation; payload schema; error handling; auth: localhost-only for v0.1)
  9. Multi-Operator Concurrency (psycopg pool, row-level locks on edits, optimistic concurrency on bulk operations, conflict resolution UX)
  10. State File Reflection (`state.library` block: connected, last_search_query, last_search_count, pending_writes)
  11. Snapshot Targets (`library_entry`, `library_search_results`)
  12. Out Of Scope For Feature 3 v0.1 (cloud sync, multi-machine sharing, embedding-based semantic search, video keypoints, image versioning beyond simple replace)
  13. Reality Boundary For Feature 3 v0.1
- Update `.gov/spec/openrepose_v0_1.md` Iteration Roadmap with a Feature 3 entry pointing at the new spec file and the I2 implementation iteration.
- Update `.gov/spec/README.md` Active Specs table to register `openrepose_library_v0_1.md`.

## Out Of Scope

- Implementation of Feature 3 (separate IMPLEMENTATION-class WPs in I2+).
- DB setup automation / installer changes (separate INFRASTRUCTURE WP in I2).
- ComfyUI custom node implementation (separate IMPLEMENTATION WP in I2; this WP just locks the contract).
- Migration scripts (this WP describes the schema; the migration files live under `.product/migrations/` and ship in I2 implementation WPs).

## Expected Files Touched

### Governance (`.gov/`)
- `.gov/workflow/workpackets/WP-I1-033-feature-3-library-spec.md` (this file).
- `.gov/workflow/TASKBOARD.md` — Active row at READY when promoted.
- `.gov/spec/openrepose_library_v0_1.md` (NEW).
- `.gov/spec/openrepose_v0_1.md` — Iteration Roadmap extension.
- `.gov/spec/README.md` — Active Specs table extension.

### Product (`.product/`)
- (none — DOCUMENTATION-class)

### Build / Output (gitignored)
- `target/test-artifacts/WP-I1-033/` — audit log + git-diff snapshot.

## Risks And Dependencies

- **Risk**: spec gets it wrong on the schema and Feature 3 impl WPs need to revise. **Mitigation**: schema is a starting point; v0.2 of the library spec will be opened by the first I2 impl WP if changes are needed (versioned per the Spec Authoring Rules).
- **Risk**: PostgreSQL setup adds operator burden (install postgres, create user, run migrations). **Mitigation**: spec includes a "Local Development Setup" subsection with a `docker-compose.yml` snippet so operator can run postgres in a container without installing it system-wide.
- **Risk**: ComfyUI custom node compatibility breaks across ComfyUI versions. **Mitigation**: spec pins target ComfyUI version range (e.g., `>=0.3.65` per the SaveImageWithMetaDataUniversal precedent) and isolates the custom node to a separate folder so updates are localized.
- **Dependency**: Operator confirms PostgreSQL on day one (confirmed 2026-05-03).

## Definition Of Done

- [ ] `.gov/spec/openrepose_library_v0_1.md` exists with all 13 subsections.
- [ ] DB schema includes: `library_entries`, `tags`, `entry_tags` (M-to-N), `prompts`, `story_beats`, `notes`, `comfyui_workflows`, `schema_version`.
- [ ] DB schema includes a `library_search(query text)` SQL function combining `tsvector` + `pg_trgm`.
- [ ] LLM Command Surface lists at least 7 commands (per In Scope).
- [ ] ComfyUI Bridge subsection enumerates the custom node's POST payload schema.
- [ ] Multi-Operator Concurrency subsection names the locking strategy (row-level + optimistic).
- [ ] `.gov/spec/openrepose_v0_1.md` Iteration Roadmap references Feature 3.
- [ ] `.gov/spec/README.md` Active Specs table includes the new file.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] Operator sign-off recorded.

## Test Coverage Plan

DOCUMENTATION-class. No new tests. Verification is the audit + the spec being internally consistent (cross-references resolve, no contradictions with Feature 1/2).

## Rollback Plan

- Files to revert: `.gov/spec/openrepose_library_v0_1.md`, `.gov/spec/openrepose_v0_1.md`, `.gov/spec/README.md`, this WP file, taskboard row.
- Recovery: `git restore --staged .gov/; git checkout -- .gov/`.

## Decisions Log

- 2026-05-03: PostgreSQL from day one (operator's call). SQLite-with-migration-path was offered as an alternative; operator wants multi-model concurrency from the start.
- 2026-05-03: psycopg 3 over asyncpg / SQLAlchemy. Reason: dual sync/async API matches the dispatcher's sync nature; Row Factories give Pydantic-friendly object mapping; mature `psycopg_pool`. SQLAlchemy can be added later if the ORM benefits become significant.
- 2026-05-03: Hybrid search — `tsvector` + GIN for full-text on prompt / story_beat / notes; `pg_trgm` + GIN for fuzzy on tags + titles. Single `library_search()` SQL function combines both with weighted ranking.
- 2026-05-03: Filesystem storage (paths in DB) over BLOBs. Reason: operator can browse / back up files directly; PostgreSQL BLOBs are awkward to inspect.
- 2026-05-03: ComfyUI bridge POSTs to existing localhost HTTP control surface. Reason: no new transport; existing dispatcher commands are the right pattern; auth is implicit (localhost-only).

## Fallback Register

- (none planned at DRAFT/READY stage; DOCUMENTATION-only)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file at READY + WP-I1-032 promotion + taskboard row.
2. Spec authoring: new `openrepose_library_v0_1.md` + roadmap reference + README index update.
3. WP closure: status REVIEW + Change Ledger.

## Proof Of Implementation

- **Command Runs**: `pwsh scripts/audit-repo.ps1` (exit 0); `git diff` shows the new spec file.
- **Proof Artifact**: `target/test-artifacts/WP-I1-033/` (audit log + git diff snapshot).

## Headless LLM Operation Compliance

- [x] N/A — DOCUMENTATION-class. No commands, no state, no snapshot. The spec being authored will impose Headless Compliance on every Feature 3 IMPLEMENTATION WP.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects DONE.
- [ ] Reality Boundary truthful.
- [ ] Audit script exits 0.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded.

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted directly at READY (operator authorized parallel work alongside WP-I1-032). Research-First pass complete. Spec authoring follows the WP-I1-032 implementation in this session.
