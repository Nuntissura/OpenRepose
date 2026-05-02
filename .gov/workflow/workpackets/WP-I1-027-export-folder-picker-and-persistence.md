# WP-I1-027 - Export Folder Picker And Persistence

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: READY
- **Iteration**: I1
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements (Options tab) and Feature 1 / CLI Requirements (export commands respect operator-chosen folder).
- **Linked Test Suite**: `.product/tests/test_settings_store.py` (NEW), `.product/tests/test_export_folder.py` (NEW).
- **Linked Check Script**: N/A.

## Intent

Operator selects an export folder via a folder-picker dialog from the Options tab. The selection persists across launches in a JSON settings file at `QStandardPaths.AppConfigLocation`. On launch, OpenRepose loads the saved folder; if the path no longer exists, it falls back to `~/Desktop/openrepose-output/` and creates the folder on first export. Both `export_single` and `export_batch` honor the configured folder. After this WP, the Options-tab text fields and Apply button are wired through to the dispatcher (the current behavior silently ignores them — see surfaced-bug note in the WP-I1-001 sign-off discussion).

## Linked Workpackets

- **Predecessor(s)**: WP-I0-002 (LLM control surface — export commands), WP-I0-004 (GUI / Options tab) — both DONE.
- **Successor(s)**: WP-I1-003 (broader Settings persistence — DRAFT) can pick up the rest of the OptionsPane fields once this WP lands the storage primitive.
- **Blocks**: none directly; WP-I1-013 (installer build + release) benefits from a sane default-folder behavior in the shipped binary.
- **Blocked-By**: none.
- **Related**: WP-I1-003 (overlap on the storage layer).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements / Options tab (single export folder, batch export folder).
- `.gov/spec/openrepose_v0_1.md` Feature 1 / CLI Requirements (export honors operator-chosen folder).
- `.gov/AGENTS.md` Headless LLM Operation Rule (settings file readable from disk; LLM agent can dump effective config without touching the GUI).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Qt for Python `QStandardPaths` docs | https://doc.qt.io/qtforpython-6/PySide6/QtCore/QStandardPaths.html | `AppConfigLocation` resolves to `%APPDATA%\<org>\<app>\` on Windows, `~/.config/<org>/<app>/` on Linux, `~/Library/Preferences/<org>/<app>/` on macOS. Cross-platform with no extra dep. | adopt |
| 2026-05-03 | PythonGUIs QSettings tutorial | https://www.pythonguis.com/faq/pyside6-qsettings-how-to-use-qsettings/ | `QSettings` is the conventional persistence API but stores in registry on Windows / plist on macOS — opaque to the operator. JSON file under AppConfigLocation is more inspectable and matches OpenRepose's "operator can read everything" ethos. | reject (use plain JSON file) |
| 2026-05-03 | Python `pathlib.Path.home()` | stdlib | Resolves to `%USERPROFILE%` on Windows, `$HOME` on Linux/macOS. `Path.home() / "Desktop"` is the standard cross-platform Desktop folder. Localized desktop names (e.g., German "Schreibtisch") are uncommon in practice but if absent we fall back to `Path.home()` and log a WARN. | adopt |
| 2026-05-03 | Qt `QFileDialog.getExistingDirectory` | https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QFileDialog.html | Native folder picker; non-modal in the LLM-driven path (only triggered by operator click). | adopt |

Decision: settings stored as `<AppConfigLocation>/openrepose/settings.json` (plain JSON, schema_version 1). Default export folder `~/Desktop/openrepose-output/`. Folder picker via `QFileDialog.getExistingDirectory` triggered by a "Browse..." button next to each export-folder text field on the Options tab. Path validation on launch: if the saved folder does not exist (drive removed, folder deleted, etc.), log a WARN, fall back to default, and surface the fallback in `state.json` so an LLM agent can see it.

## Reality Boundary

- **Real Seam**: a real JSON settings file at `<AppConfigLocation>/openrepose/settings.json` survives across launches; export handlers read the operator-chosen folder from `AppState.settings.export_folder` instead of the hardcoded `outputs/<avatar-slug>/...` default. Browse... button on the Options tab opens a native folder picker.
- **User-Visible Win**: operator clicks Options → Browse... → picks a folder → exports land there. Restarts the app → exports keep going to the same folder. If the operator removes the folder while OpenRepose is closed, next launch falls back to `~/Desktop/openrepose-output/` with a visible warning in the log pane.
- **Proof Target**: pytest covers (a) settings round-trip (write → read → round-trip equal); (b) launch with valid saved path → uses it; (c) launch with missing saved path → falls back to default + logs WARN; (d) export_single + export_batch honor the configured folder; (e) GUI integration: clicking Browse... and selecting a folder updates state and persists. Manual: operator picks Desktop subfolder, exports, restarts, exports again, confirms files land in the same folder.
- **Allowed Temporary Fallbacks**: none.
- **Promotion Guard**: do not promote to DONE until the operator confirms a Browse → export → restart → export cycle works on their machine.

## In Scope

- New `.product/src/openrepose/settings.py` module: `Settings` dataclass; `load()` / `save()` with atomic `.tmp` + `os.replace`; `default_export_folder()` helper returning `Path.home() / "Desktop" / "openrepose-output"`; `settings_path()` helper using `QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation) / "openrepose" / "settings.json"`.
- Settings JSON schema (v1): `{schema_version, export_folder, single_export_subdir_template, batch_export_subdir_template, ...}`. Subdir templates default to `{avatar}` (single) and `{avatar}/{run_tag}` (batch); the operator can change the subdir but the *root* is the single export folder.
- `App` constructor loads settings (or creates defaults) and exposes `app.settings` for the dispatcher and GUI.
- `_h_export_single` / `_h_export_batch` use `app.settings.export_folder / template-rendered-subdir` instead of `d.outputs_root / avatar_slug` when no `out_dir` is supplied in the command. Explicit `out_dir` in the command still wins (no behavior change for that path — covered by existing tests).
- `OptionsPane` gains a Browse... button next to each export-folder field. Apply button persists settings to disk via `app.settings.save()`. `settings_changed` signal connected in `MainWindow._wire_actions`.
- Launch-time validation: if `settings.export_folder` does not resolve to an existing folder, log a WARN, set `settings.export_folder = default_export_folder()`, and create that folder if missing.
- New `state.json` block `settings`: `{export_folder, default_used (bool), settings_path}`.
- New command `dump_settings`: returns the effective settings JSON. Read-only.

## Out Of Scope

- Persisting the rest of the OptionsPane fields (avatar slug, projection mode, log level, channel toggles, etc.). Those remain WP-I1-003's territory; this WP only ships the storage primitive + the export-folder field.
- Window geometry persistence (also WP-I1-003).
- Per-avatar export folder overrides (operator could configure later if they want; v0.1 has one global folder).
- Settings UI other than the Options tab fields (no separate Settings dialog).
- Migration from earlier schema versions (this is schema_version 1; future bumps add a migration path).

## Expected Files Touched

### Governance (`.gov/`)
- `.gov/workflow/workpackets/WP-I1-027-export-folder-picker-and-persistence.md` (this file).
- `.gov/workflow/TASKBOARD.md` — Active row added at READY when promoted.
- `.gov/spec/openrepose_v0_1.md` — small extension to Options-tab and CLI-export wording to reference the configured folder + the new `dump_settings` command.

### Product (`.product/`)
- `.product/src/openrepose/settings.py` (NEW).
- `.product/src/openrepose/state.py` — add `settings` block + `set_settings_status()` helper; update `to_dict()`.
- `.product/src/openrepose/app.py` — load settings on construction; expose `app.settings`.
- `.product/src/openrepose/commands.py` — `_h_export_single` + `_h_export_batch` honor configured folder; new `_h_dump_settings` handler registered.
- `.product/src/openrepose/gui/options.py` — Browse... buttons next to single + batch export folder fields; `_on_apply` persists via `app.settings`.
- `.product/src/openrepose/gui/main_window.py` — wire `OptionsPane.settings_changed` to `app.settings.update(...)` + persist.
- `.product/tests/test_settings_store.py` (NEW): round-trip JSON, schema validation, atomic write, default-folder helper, missing-path fallback, settings_path helper resolves under AppConfigLocation.
- `.product/tests/test_export_folder.py` (NEW): export_single + export_batch use configured folder; explicit `out_dir` still wins; `dump_settings` returns effective config.

### Build / Output (gitignored)
- `target/test-artifacts/WP-I1-027/`
- `~/Desktop/openrepose-output/` (operator's machine, created on first export if missing).

## Risks And Dependencies

- **Risk**: `QStandardPaths` requires a `QCoreApplication` instance to resolve `AppConfigLocation`. **Mitigation**: defer resolution to first use OR pass an explicit path in headless / test mode. Tests use a `tmp_path` override.
- **Risk**: localized "Desktop" folder names on non-English Windows / macOS. **Mitigation**: prefer the Qt-resolved `QStandardPaths.DesktopLocation` when available; fall back to `Path.home() / "Desktop"`; finally fall back to `Path.home()` with a logged WARN.
- **Risk**: Browse... dialog could steal focus from another app. **Mitigation**: `QFileDialog.getExistingDirectory` is triggered only by operator click on the Browse... button; never by an LLM-driven path. Add a runtime test that drives `dump_settings` + simulated settings updates while the GUI is alive and asserts no `raise_/activateWindow` calls.
- **Risk**: existing tests assume exports land under `outputs/<avatar-slug>/...`. **Mitigation**: `App` constructor still accepts `outputs_root` (back-compat for tests); when `app.settings.export_folder` is non-default it overrides; otherwise the existing default flow is preserved. The two existing export tests (`test_command_handlers.test_import_portrait_then_set_yaw_then_export_single` + `test_export_batch_default_13_angles`) should continue to pass without modification.
- **Dependency**: PySide6 QStandardPaths (already in use via PySide6).

## Definition Of Done

- [ ] `settings.py` exposes `Settings`, `load`, `save`, `default_export_folder`, `settings_path`.
- [ ] Settings JSON round-trips at `<AppConfigLocation>/openrepose/settings.json` with atomic `.tmp + os.replace`.
- [ ] `App` constructor loads settings (or creates defaults); `app.settings` is the canonical source.
- [ ] `_h_export_single` and `_h_export_batch` use `app.settings.export_folder` when no `out_dir` is supplied; explicit `out_dir` still wins.
- [ ] `dump_settings` command returns the effective settings JSON.
- [ ] `OptionsPane` has Browse... buttons; `_on_apply` persists via `app.settings.save()`; `MainWindow` wires the signal.
- [ ] Launch-time validation: missing saved path → falls back to `Path.home() / "Desktop" / "openrepose-output"` with a WARN logged.
- [ ] `state.json` `settings` block populated.
- [ ] No `raise_/activateWindow/showNormal/showMaximized` from any LLM-driven path; runtime test asserts this across 10 settings updates + dump_settings calls.
- [ ] `pytest` zero failures; full project suite still green; junit XML at `target/test-artifacts/WP-I1-027/pytest_results.xml`.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] Operator confirms manual Browse → export → restart → export cycle on their machine.

## Test Coverage Plan

### Functional Flow Tests
- [ ] Round-trip: write Settings → read → equal.
- [ ] Default export folder helper returns `Path.home() / "Desktop" / "openrepose-output"`.
- [ ] Missing saved path → fallback to default + WARN logged.
- [ ] `export_single` writes to `settings.export_folder / <avatar>/...` when no `out_dir` supplied.
- [ ] `export_batch` writes to `settings.export_folder / <avatar>/<run-tag>/...` when no `out_dir` supplied.
- [ ] Explicit `out_dir` in the command still wins (regression).

### Code Correctness Tests
- [ ] Schema validation: bad `schema_version` rejected on load.
- [ ] Atomic save: `.tmp` does not remain after success.
- [ ] `dump_settings` returns the in-memory Settings as JSON.
- [ ] `settings_path()` returns a path under `QStandardPaths.AppConfigLocation`.

### Red-Team / Abuse Tests
- [ ] Settings file with corrupt JSON → load raises a structured error and falls back to defaults.
- [ ] Saved path on a removed drive (simulate by pointing at a UUID-named non-existent path) → fallback path is used.
- [ ] No GUI string introduces a forbidden yaw phrase.

### Performance / Reliability Tests
- [ ] `Settings.load()` under 5ms on a warm filesystem (sanity, not gating).

## Rollback Plan

- Files to revert: `settings.py`, `state.py`, `app.py`, `commands.py`, `gui/options.py`, `gui/main_window.py`, the two new test files, the spec extension.
- Files to keep: a pre-existing settings.json on the operator's machine (the rollback should not delete the file; operator can manually delete if desired).
- Recovery: `git restore --staged .product/ .gov/spec/; git checkout -- .product/ .gov/spec/`.

## Decisions Log

- 2026-05-03: Plain JSON file under `AppConfigLocation` over `QSettings`. Reason: operator can inspect / edit / back up the file directly; matches the rest of the repo (state.json, calibration.json are all plain JSON).
- 2026-05-03: One global export folder + sub-templates over per-avatar folders. Reason: simpler v0.1; per-avatar overrides can ship later if requested.
- 2026-05-03: Default to `~/Desktop/openrepose-output/`. Reason: operator's request; matches expectation that exports land in a discoverable location, not buried inside the repo.

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: WP file + taskboard row.
2. Implementation: settings module + state extension + app wiring + dispatcher + dump_settings handler.
3. GUI: Options-tab Browse... buttons + main_window signal wiring.
4. Verification: pytest + junit XML + manual Browse-restart cycle.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_settings_store.py .product/tests/test_export_folder.py --junitxml=target/test-artifacts/WP-I1-027/pytest_results.xml`.
- **Proof Artifact**: `target/test-artifacts/WP-I1-027/pytest_results.xml` plus a one-line operator note confirming the manual Browse-restart cycle.
- **Claim Standard**: never mark DONE without operator confirmation of the manual cycle.

## Headless LLM Operation Compliance

- [ ] LLM agent can read effective settings via `dump_settings`.
- [ ] State reflected in `state.json` `settings` block.
- [ ] No new snapshot target needed (Options tab already grabbable as `options_pane`).
- [ ] No `raise_/activateWindow/showNormal/setForegroundWindow` from any LLM-driven path; Browse... dialog only triggered by operator click.
- [ ] No modal dialogs from LLM commands.
- [ ] Tests cover the headless path (settings persist + dispatcher honors them without launching the GUI).

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects DONE.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded (manual Browse-restart cycle confirmed).
- [ ] Headless LLM Operation Compliance: all items checked.

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at status DRAFT. Predecessors satisfied. Awaits operator promotion to READY.
- 2026-05-03: Operator approved fast-track batch. Status DRAFT -> READY. Kickoff commit follows.
