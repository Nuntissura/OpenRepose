# WP-I2-002 - Settings Extension: Library Configuration

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: IN-PROGRESS
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

- [ ] `Settings.schema_version = 2` with new fields + defaults.
- [ ] v1 settings.json loads cleanly + migrates to v2.
- [ ] Options pane has Library section.
- [ ] pytest zero failures; audit clean.
- [ ] **Manual Impact**: No — operator-facing surface change is a small Library section in Options that mirrors three new persisted fields. The DB connection / library workflow itself is documented in WP-I2-001 + WP-I2-008. No new manual topic file required for this WP alone.

## Headless LLM Operation Compliance

- [x] N/A — INFRASTRUCTURE. Operator-facing GUI changes are a passive form (DB URL + library root + operator slug fields) that the operator fills in once; LLM agents read the resolved values out of `state.json` after WP-I2-001 wires the `library` block.

## Change Ledger

- (filled at REVIEW)

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence.
