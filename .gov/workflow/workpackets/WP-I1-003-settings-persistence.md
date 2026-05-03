# WP-I1-003 - Settings Persistence

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Status**: IN-PROGRESS
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements (Options tab fields) — add persistence rule.

## Intent

Persist OptionsPane settings (avatar slug, run tag, export folders, projection mode, channel toggles, log level, etc.) to `outputs/.runtime/settings.json` so settings survive across launches. Same runtime-surface neighbourhood as `state.json`, `inbox/`, `processed/`, and the snapshot manifest. Currently each launch starts with defaults. Recorded as a documented fallback in WP-I0-004.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-004 must reach DONE.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-04 | Local codebase | `.product/src/openrepose/state.py`, `.product/src/openrepose/commands.py`, `.product/src/openrepose/gui/options.py`, `.product/src/openrepose/snapshot.py` | The runtime-surface pattern (`outputs/.runtime/state.json`, snapshots, inbox/processed) is already established. Adding `settings.json` next to it follows the existing convention; no new external dependency required. | adopt |
| 2026-05-04 | Qt for Python (PySide6) docs | https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSettings.html | `QSettings` is the platform-native settings store (registry on Windows, plist on macOS, INI on Linux). Rejected: ties the file location to per-user OS app-data, breaks the disk-agnostic + repo-portable runtime surface this project uses. JSON-on-disk under `outputs/.runtime/` matches the rest of the surface and is LLM-readable without extra parsing. | reject |

## Reality Boundary

- **Real Seam**: write `OptionsPane` field state to `outputs/.runtime/settings.json` on Apply; read on app construction; apply to OptionsPane widgets and to `App` defaults.
- **User-Visible Win**: operator sets options once, closes the app, reopens — options are restored. LLM agent can read/write the same file via new commands `dump_settings`, `set_settings`, `clear_settings`.
- **Proof Target**: pytest opens app, sets options, closes, reopens, asserts options restored.

## In Scope

- Settings file format JSON. Schema validated.
- `OptionsPane.load_from_file()` and `save_to_file()`.
- Three new dispatcher commands.
- Tests: round-trip; partial load (missing keys default sensibly); corrupted file falls back to defaults with WARN.

## Out Of Scope

- Per-avatar settings (settings are app-wide; per-avatar customization belongs to calibration WP).
- Encrypted settings (no secrets in this file).

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via `dump_settings`, `set_settings`, `clear_settings`.
- [ ] State reflected in `state.json` (current settings hash) and in dedicated `settings.json` file.
- [ ] LLM pulls visual via `snapshot {target: "options_pane"}` (existing target).
- [ ] No focus theft / modal dialogs from LLM commands.
- [ ] Tests cover the headless command path.

## Definition Of Done

- [ ] OptionsPane state survives app restart.
- [ ] 3 new commands work; tests cover them.
- [ ] Full project suite green.
- [ ] Manual Impact: Yes — extends `feature-1-yaw-exporter.md` with the settings-persistence behaviour and the 3 new headless commands.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / GUI Requirements (Options tab fields), LLM Control Surface (new commands).
- `.gov/AGENTS.md` — Headless LLM Operation Rule (settings reachable through `dump_settings`, `set_settings`, `clear_settings`).

## Linked Test Suite

- `.product/tests/test_settings_persistence.py` (NEW) — round-trip, partial-load, corrupt-file fallback.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-003-settings-persistence.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md` — add settings-persistence rule to GUI Requirements / Options tab.

### Product (`.product/`)

- `.product/src/openrepose/state.py` — add `settings_path()` helper.
- `.product/src/openrepose/commands.py` — register `dump_settings`, `set_settings`, `clear_settings`.
- `.product/src/openrepose/gui/options.py` — `load_from_file()` + `save_to_file()` + Apply hook.
- `.product/src/openrepose/app.py` — read settings on construction, apply to `OptionsPane` + defaults.
- `.product/tests/test_settings_persistence.py` (NEW)

### Build / Output

- `outputs/.runtime/settings.json` (gitignored runtime artifact)
- `target/test-artifacts/WP-I1-003/`

## Risks And Dependencies

- **Risk**: corrupt or partially-written `settings.json` could brick first-run. **Mitigation**: schema validate on load; on parse error, log WARN, rename the bad file to `settings.json.broken-<timestamp>`, fall back to defaults.
- **Risk**: schema drift across versions. **Mitigation**: include a `schema_version` field; load path tolerates older versions by filling defaults for newer keys.
- **Dependency**: WP-I0-004 (OptionsPane + AppState wiring) must be DONE.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Set 3 options, click Apply, kill the app, reopen — options restored.
- [ ] LLM `set_settings` writes the file; `dump_settings` returns the same payload.
- [ ] `clear_settings` resets to defaults and removes the file.

### Code Correctness Tests
- [ ] Round-trip: `load(save(x)) == x` for the full settings schema.
- [ ] Partial load: missing keys fill from defaults without error.
- [ ] Corrupt file: bad JSON renamed to `.broken`, defaults loaded, WARN logged.

### Red-Team / Abuse Tests
- [ ] `set_settings` with unknown keys: rejected with structured ERR; existing file untouched.
- [ ] `set_settings` while OptionsPane has unsaved edits: documented precedence (last-write-wins or merge — decide in implementation).

### Performance / Reliability Tests
- [ ] Load + apply on app construction is < 100ms.

## Rollback Plan

- Files to revert: `state.py`, `commands.py`, `gui/options.py`, `app.py`, the new test file.
- Files to keep: existing `outputs/.runtime/state.json` (unrelated to this change).
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/state.py .product/src/openrepose/commands.py .product/src/openrepose/gui/options.py .product/src/openrepose/app.py .product/tests/test_settings_persistence.py`

## Decisions Log

- 2026-05-04 (kickoff): settings file lives at `outputs/.runtime/settings.json`, NOT in a per-user OS app-data directory. Reason: the rest of the LLM-readable runtime surface lives there; settings travel with the repo on disk-agnostic moves; matches operator-stated preference.

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + spec section.
2. Implementation: state helper + dispatcher commands + OptionsPane I/O.
3. GUI wiring: Apply button writes; app construction reads.
4. Verification: pytest results + junit XML.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_settings_persistence.py --junitxml=target/test-artifacts/WP-I1-003/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-003/pytest_results.xml` plus a sample `settings.json` snapshot.
- **Claim Standard**: never mark `DONE` without junit XML evidence and a manual restart-cycle confirmation.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-003/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
- 2026-05-04: Promoted DRAFT → IN-PROGRESS as part of polish bundle (with WP-I1-005 + WP-I1-016). Workflow Version bumped 1.0 → 1.1; Manual Impact line added; settings location frozen to `outputs/.runtime/settings.json`.
