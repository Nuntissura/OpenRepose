# WP-I2-001 - PostgreSQL Setup + Migration Runner

## Header

- **Owner**: TBD
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DRAFT
- **Iteration**: I2
- **Workflow Version**: 1.1
- **Packet Class**: INFRASTRUCTURE
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_library_v0_1.md` Database Schema + Storage Layout + State File Reflection (`library` block).
- **Linked Test Suite**: `.product/tests/test_db_migrator.py` (NEW); `.product/tests/test_db_connection.py` (NEW).
- **Linked Check Script**: N/A.

## Intent

Stand up the PostgreSQL backend the Feature 3 spec locks. Ship: a `docker-compose.yml` for one-command local Postgres, a hand-rolled SQL migration runner, the initial schema (`001_library_initial.sql`) per spec, and the dispatcher's connection-pool wiring (psycopg 3 + psycopg_pool). After this WP closes, every subsequent I2 WP can assume a live, schema-matched DB.

## Linked Workpackets

- **Predecessor(s)**: WP-I1-033 (Feature 3 spec — DONE 2026-05-03).
- **Successor(s)**: WP-I2-002 through WP-I2-008 — all I2 implementation WPs depend on this DB primitive.
- **Blocks**: every other I2 WP.
- **Related**: WP-I1-027 (Settings primitive — extended in WP-I2-002 to add `library_db_url` + `library_root` + `operator_slug`).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_library_v0_1.md` — Database Schema (PostgreSQL ≥ 16, pg_trgm + uuid-ossp + unaccent extensions, 7 tables + library_search() function); Storage Layout (filesystem under `outputs/library/`); state.json `library` block (connected, schema_version, db_url_redacted).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | WP-I1-033 spec Research Notes | `.gov/workflow/archive/WP-I1-033-feature-3-library-spec.md` | All foundational research (psycopg 3 vs asyncpg, pg_trgm + tsvector, hand-rolled migrations) is locked in the Feature 3 spec. This WP implements per the spec. | adopt as-is |
| 2026-05-03 | psycopg 3 docs — connection pool | https://www.psycopg.org/psycopg3/docs/advanced/pool.html | `psycopg_pool.ConnectionPool(conninfo, min_size, max_size, open=True)`. Defaults reasonable; `min_size=4, max_size=10` per the spec. | adopt |
| 2026-05-03 | docker-compose.yml for postgres | community standard | `image: postgres:16-alpine`, expose 5432, mount data volume, set POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB env. Operator runs `docker compose up -d postgres`. | adopt |

## Reality Boundary

- **Real Seam**: real PostgreSQL container running locally; real psycopg_pool inside the dispatcher; real `001_library_initial.sql` applied; real `state.library.connected = true` reflected in state.json.
- **User-Visible Win**: operator runs `docker compose up -d postgres` (or has Postgres installed natively), launches OpenRepose, sees the Library indicator in the status bar / state.json show "connected: true, schema_version: 1". No library functionality yet; that's WP-I2-002+.
- **Proof Target**: pytest covers (a) migrator detects current schema_version; (b) applies pending migrations in order; (c) advisory-lock prevents two instances racing; (d) connection pool opens / health-checks against a real Postgres (test fixture spins up one via `pytest-postgresql` or docker); (e) dispatcher sets `state.library.connected` correctly.
- **Allowed Temporary Fallbacks**: if `library_db_url` is empty, the dispatcher logs WARN and sets `state.library.connected = false` — Library commands return structured errors but the rest of OpenRepose works. Operator can run rig + export without DB.
- **Promotion Guard**: do not promote until pytest-postgresql round-trip passes AND operator confirms a fresh `docker compose up` + OpenRepose launch reaches `connected: true`.

## In Scope

- New `.product/migrations/001_library_initial.sql` — full schema per spec (extensions, 7 tables, library_search() function, indexes).
- New `.product/src/openrepose/db/__init__.py` — package marker.
- New `.product/src/openrepose/db/pool.py` — `LibraryPool` thin wrapper around `psycopg_pool.ConnectionPool`; lazy-open; reconnect logic; `is_connected` + `schema_version` properties.
- New `.product/src/openrepose/db/migrator.py` — discovers `.product/migrations/*.sql` (sorted by NNN prefix); reads `schema_version` table; applies pending in transaction; uses `pg_advisory_lock(<library_migration_lock_id>)` to serialize across instances.
- `app.py`: construct `LibraryPool` after Settings load; if `library_db_url` set, open + run migrator; reflect on `state.library`.
- `state.py`: new `library` block (per spec).
- `commands.py`: `LibraryPool` accessible to library handlers (added in WP-I2-004); not used yet here. Add `dispatcher.pool` reference.
- `docker-compose.yml` (NEW, repo root): postgres:16-alpine service.
- Tests: migrator round-trip on temp Postgres (use `pytest-postgresql` ephemeral cluster fixture); pool open/close; advisory-lock collision.

## Out Of Scope

- CRUD on library_entries / tags / etc. (WP-I2-002+).
- Library tab GUI (WP-I2-006).
- ComfyUI bridge (WP-I2-005).
- Schema upgrade migrations beyond `001_library_initial.sql` (added by future WPs as needed).
- Multi-machine Postgres (localhost only in v0.1).

## Expected Files Touched

### Governance
- `.gov/workflow/workpackets/WP-I2-001-postgres-setup-and-migrator.md` (this file).
- `.gov/workflow/TASKBOARD.md`.

### Product
- `pyproject.toml` — add `psycopg[binary]>=3.2` and `psycopg_pool>=3.2`.
- `docker-compose.yml` (NEW, repo root).
- `.product/src/openrepose/db/__init__.py` (NEW).
- `.product/src/openrepose/db/pool.py` (NEW).
- `.product/src/openrepose/db/migrator.py` (NEW).
- `.product/migrations/001_library_initial.sql` (NEW).
- `.product/src/openrepose/state.py` — add `library` block.
- `.product/src/openrepose/app.py` — wire pool + migrator.
- `.product/src/openrepose/commands.py` — add `dispatcher.pool` reference.
- `.product/tests/test_db_migrator.py` (NEW).
- `.product/tests/test_db_connection.py` (NEW).

### Build / Output
- `target/test-artifacts/WP-I2-001/`.

## Risks And Dependencies

- **Risk**: pytest-postgresql adds a dev dep; operator must install. **Mitigation**: pin in `pyproject.toml` `[project.optional-dependencies] dev`; document in README.
- **Risk**: schema migrations on shared DB block other instances. **Mitigation**: advisory-lock + clear log messages; migrations are infrequent.
- **Dependency**: PostgreSQL ≥ 16 available (operator-installed or via docker-compose).

## Definition Of Done

- [ ] `docker-compose.yml` brings up Postgres 16 with one command.
- [ ] `001_library_initial.sql` applies cleanly to a fresh DB; creates all 7 tables + `library_search()` function + extensions + indexes.
- [ ] Migrator detects `schema_version`, applies pending in order, advisory-locks against parallel runs.
- [ ] LibraryPool opens against a live DB; `is_connected` + `schema_version` populated.
- [ ] state.json `library` block reflects connected status + schema_version.
- [ ] Empty `library_db_url` does not crash the app; logs WARN; state shows connected=false.
- [ ] pytest zero failures; junit XML at `target/test-artifacts/WP-I2-001/`.
- [ ] Audit clean.
- [ ] Operator confirms fresh docker-compose + OpenRepose launch reaches connected=true.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Apply migrations from empty: schema_version becomes 1.
- [ ] Re-apply when current: no-op.
- [ ] Pool opens + executes a SELECT 1.

### Code Correctness Tests
- [ ] Pool.is_connected reflects actual DB state.
- [ ] Migrator advisory-lock prevents parallel application.

### Red-Team / Abuse Tests
- [ ] Empty library_db_url: WARN + connected=false; no crash.
- [ ] Bad library_db_url: structured error, connected=false.

## Rollback Plan

- Revert migrations (no down-migrations in v0.1; operator drops DB and re-applies).
- Files: per Expected Files Touched.

## Decisions Log

- 2026-05-03: psycopg 3 + psycopg_pool sync, hand-rolled SQL migrations. Per WP-I1-033 spec decisions.

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: WP file + taskboard + spec cross-reference.
2. Implementation: db/pool.py + db/migrator.py + 001_library_initial.sql + docker-compose.yml + state extension.
3. Verification: pytest + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_db_*.py --junitxml=target/test-artifacts/WP-I2-001/pytest_results.xml`.

## Headless LLM Operation Compliance

- [x] N/A — INFRASTRUCTURE WP. State reflection exists (`state.library.connected`); no operator-facing GUI surface added in this WP.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects DONE.
- [ ] Audit clean.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded.

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at status DRAFT. First WP of the I2 implementation iteration. Predecessor WP-I1-033 spec DONE.
