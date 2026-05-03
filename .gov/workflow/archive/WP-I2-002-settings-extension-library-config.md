# WP-I2-002 - Settings Extension: Library Configuration

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DONE
- **Iteration**: I2
- **Workflow Version**: 1.1
- **Packet Class**: INFRASTRUCTURE
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_library_v0_1.md` Storage Layout (`Settings.library_db_url`, `Settings.library_root`, `Settings.operator_slug`).
- **Linked Test Suite**: extend `.product/tests/test_settings_store.py`.

## Intent

Bump `Settings` schema_version 1 → 2 to add `library_db_url`, `library_root` (default `<export_folder>/library/`), and `operator_slug` (default = OS username). Migration-safe: schema_version 1 settings.json files load with defaults applied for the new fields. Required by WP-I2-001 (DB pool needs the URL) and the rest of I2.

## Linked Workpackets

- **Predecessor(s)**: WP-I1-027 (Settings primitive — DONE 2026-05-03), WP-I1-033 (Feature 3 spec — DONE).
- **Successor(s)**: WP-I2-001 reads these settings.
- **Blocks**: WP-I2-001 (technically can land in either order; this WP is simpler so should land first).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_library_v0_1.md` Storage Layout (Settings extension).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | WP-I1-027 Settings primitive | `.gov/workflow/archive/WP-I1-027-export-folder-picker-and-persistence.md` | Settings is JSON at `QStandardPaths.AppConfigLocation`. Schema_version field already exists; bump to 2 with backward-compatible defaults. | adopt |
| 2026-05-03 | Migration pattern | local | When schema_version < SETTINGS_SCHEMA_VERSION, `load()` patches defaults for new fields and re-saves. Old settings files keep working. | adopt |

## Reality Boundary

- **Real Seam**: real `Settings` v2 with the three new fields; real migration from v1 → v2 on load.
- **User-Visible Win**: operator's existing settings.json loads cleanly post-upgrade; new fields available in Options + dispatcher.
- **Proof Target**: pytest covers v1→v2 migration; default values; round-trip; unknown-version still raises.

## In Scope

- `settings.py`: bump SETTINGS_SCHEMA_VERSION to 2; add `library_db_url: str = ""`, `library_root: str = ""`, `operator_slug: str = ""` fields; `update()` accepts them; `load()` migrates v1 → v2 by patching defaults + re-saving; `to_dict()` emits.
- `gui/options.py`: new "Library" section: DB URL field (with mask for password), Library root + Browse..., Operator slug field. Apply triggers `settings.update(...)`.
- Tests for the three new fields + v1→v2 migration.

## Out Of Scope

- DB pool wiring (WP-I2-001).
- Library tab GUI (WP-I2-006).

## Definition Of Done

- [x] `Settings.schema_version = 2` with new fields + defaults.
- [x] v1 settings.json loads cleanly + migrates to v2.
- [x] Options pane has Library section.
- [x] pytest zero failures; audit clean.
- [x] **Manual Impact**: No — operator-facing surface change is a small Library section in Options that mirrors three new persisted fields. The DB connection / library workflow itself is documented in WP-I2-001 + WP-I2-008. No new manual topic file required for this WP alone.

## Headless LLM Operation Compliance

- [x] N/A — INFRASTRUCTURE. Operator-facing GUI changes are a passive form (DB URL + library root + operator slug fields) that the operator fills in once; LLM agents read the resolved values out of `state.json` after WP-I2-001 wires the `library` block.

## Change Ledger

- **What Became Real**:
  - `settings.py` bumped `SETTINGS_SCHEMA_VERSION` from 1 to 2; added three persisted fields (`library_db_url`, `library_root`, `operator_slug`); added `resolved_library_root()`, `effective_operator_slug()`, `redacted_db_url()` helpers; rewrote `load()` to migrate older schema_versions forward in place (defaults patched in + re-saved at the current version) and to raise only on schema_version > current.
  - `gui/options.py` gained a Library section (DB URL field with password echo mode, Library root + Browse..., Operator slug). `_on_apply` emits the new keys; `load_from_settings()` populates them.
  - `gui/main_window.py` `_on_settings_changed` now persists the three new fields alongside the existing ones.
  - `commands.py` `_h_dump_settings` now redacts `library_db_url` (`postgresql://user:***@host/db`) so an LLM agent reading the dump cannot exfiltrate the password; also returns `resolved_library_root` and `effective_operator_slug`.
  - 19 new tests in `test_settings_store.py` (schema constant, defaults, to_dict + roundtrip + update for the new fields, v1→v2 migration in place, resolved/effective helpers, redaction utility); 3 new tests in `test_export_folder.py` (dump_settings redaction + resolved-fields exposure + empty-URL handling).
- **What Remains Simulated**: nothing — this WP only touches the Settings primitive + form + dispatcher dump; no live DB. The dispatcher does not yet use `library_db_url` (that's WP-I2-001).
- **Next Blocking Real Seam**: WP-I2-001 reads `Settings.library_db_url`, opens a `psycopg_pool.ConnectionPool`, applies migrations, and reflects `library` block in `state.json`.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I2-002/pytest_results.xml` (full run after settings change, 383 passed; one pre-existing Windows-only `PermissionError` warning in `test_state_write_atomic_no_par0` fixture-cleanup race, unchanged from baseline).
- **Targeted run**: `pytest .product/tests/test_settings_store.py .product/tests/test_export_folder.py -v` → 53 passed in 4.46s.
- **Audit**: `powershell scripts/audit-repo.ps1` → `audit-repo: OK   no violations` (153 tracked files).
- **Operator Sign-off**: pending (operator overnight handoff).

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence.
- 2026-05-03: Implementation + tests landed; all 383 tests pass; audit clean. Status → REVIEW.
