# WP-I1-013 - Installer Build And Release

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: INFRASTRUCTURE
- **Effort Estimate**: M
- **Linked Spec**: README + topology layout for `dist/` folder.

## Intent

Build a Windows-installable OpenRepose distributable using PyInstaller (or alternative). Produce `OpenRepose-<version>-windows.exe` (single-file or folder install) under `dist/`. CLI subcommand for build invocation so the build itself is headless. Tag the release in Git, push, attach the artifact to the GitHub release.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 must reach DONE; settings persistence (WP-I1-003) recommended so first-run UX is reasonable.

## Reality Boundary

- **Real Seam**: PyInstaller config (`build/openrepose.spec` or in `pyproject.toml`); GitHub Actions optional; manual build invocation `python -m openrepose.cli build` (or `pyinstaller build/openrepose.spec`).
- **User-Visible Win**: operator can hand someone an `.exe`; that someone can run OpenRepose without touching Python or pip.
- **Proof Target**: built `.exe` runs on a machine without Python installed; smoke test imports a portrait and exports a batch.

## In Scope

- PyInstaller spec including PySide6 + MediaPipe + opencv data files.
- Build invocation script.
- Distributable layout (icon, version metadata, license file).
- README / install instructions.
- Tagging convention: `v0.1.0`, etc.

## Out Of Scope

- Code signing (separate WP if operator wants signed binaries).
- macOS / Linux builds (Windows-first).
- Auto-update mechanism.
- App store submission.

## Risks And Dependencies

- **Risk**: PyInstaller + MediaPipe is fragile; MediaPipe ships native binaries that need explicit data-file inclusion.
- **Risk**: opencv-python and opencv-contrib-python conflict; resolve in build spec.
- **Dependency**: confirm operator's signing certificate availability if signed builds are wanted.

## Headless LLM Operation Compliance

- [x] N/A — pure INFRASTRUCTURE. Build is invoked via CLI; no GUI surface added.

## Definition Of Done

- [ ] Built `.exe` runs on a clean Windows machine.
- [ ] Smoke test (import portrait, export batch) works in the installed binary.
- [ ] `dist/OpenRepose-v0.1.0-windows.exe` produced and uploaded to GitHub release.
- [ ] Release notes drafted.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — distribution-related sections; topology entries for `dist/`.
- `.gov/AGENTS.md` — Headless LLM Operation Rule (build is CLI-driven; no GUI surface added).

## Linked Test Suite

- `.product/tests/test_installer_smoke.py` (NEW) — verifies the spec file exists and parses; full smoke is operator-driven on a clean Windows VM.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-013-installer-build-and-release.md` (this file)
- `.gov/workflow/TASKBOARD.md`
- `.gov/topology.yaml` — confirm `dist/` layout.

### Product (`.product/`)

- `.product/build/openrepose.spec` (NEW) — PyInstaller spec.
- `.product/src/openrepose/cli.py` — extend with `build` subcommand.
- `.product/pyproject.toml` — add `[project.optional-dependencies]` build group with `pyinstaller`.
- `.product/installers/icon.ico` (NEW)
- `.product/installers/version.txt` (NEW)
- `.product/installers/LICENSE.txt` (NEW)
- `.product/tests/test_installer_smoke.py` (NEW)

### Build / Output

- `dist/OpenRepose-v0.1.0-windows.exe`
- `target/test-artifacts/WP-I1-013/`

## Risks And Dependencies

- **Risk**: PyInstaller + MediaPipe is fragile; native binaries need explicit `datas=` entries. **Mitigation**: enumerate MediaPipe data files in the spec; pin a known-good MediaPipe version; smoke-run on a clean VM each release.
- **Risk**: `opencv-python` and `opencv-contrib-python` simultaneous installation breaks PyInstaller imports. **Mitigation**: pick one in `pyproject.toml`; document in the spec; CI test detects double install.
- **Dependency**: WP-I0-001..004 must be DONE; settings persistence (WP-I1-003) recommended for first-run UX; operator-supplied icon and license file.

## Test Coverage Plan

### Functional Flow Tests
- [ ] `python -m openrepose.cli build` produces `dist/OpenRepose-*.exe` with non-zero size.
- [ ] Built `.exe` launches on a clean Windows VM (no Python, no pip).
- [ ] Built `.exe` runs the same import-portrait + export-batch smoke as the source distribution.

### Code Correctness Tests
- [ ] PyInstaller spec parses without warnings.
- [ ] `pyproject.toml` build group resolves cleanly in a fresh venv.
- [ ] Version string in the built `.exe` matches `installers/version.txt` (verifiable via `Get-ItemProperty`).

### Red-Team / Abuse Tests
- [ ] Built `.exe` does not silently bundle operator credentials, `.env`, or any file outside `.product/src/openrepose/` and approved data dirs.
- [ ] Antivirus heuristic check on a sample run; if false-positive flagged, document the workaround.

### Performance / Reliability Tests
- [ ] First-launch time of the built `.exe` under 10 seconds on the operator's reference machine.
- [ ] Built `.exe` size under 600 MB.

## Rollback Plan

- Files to revert: `build/openrepose.spec`, the `build` CLI subcommand, installer assets, the new test file.
- Files to keep: existing `dist/` artifacts (operator may want to retain prior builds).
- Recovery command: `git restore --staged .product/; git checkout -- .product/build/openrepose.spec .product/src/openrepose/cli.py .product/pyproject.toml .product/installers/ .product/tests/test_installer_smoke.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row + topology adjustment.
2. Implementation: PyInstaller spec + `build` CLI subcommand + installer assets.
3. Smoke verification: clean-VM run + version stamp check.
4. Release: tag `v0.1.0`, push, attach `.exe` to the GitHub release (operator-driven).

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_installer_smoke.py --junitxml=target/test-artifacts/WP-I1-013/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-013/pytest_results.xml` plus the built `.exe` archived under that directory and a clean-VM smoke screenshot.
- **Claim Standard**: never mark `DONE` without a clean-VM smoke confirmation recorded in Evidence.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-013/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths (built `.exe`, clean-VM screenshot, release URL).
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: marked N/A with reason (INFRASTRUCTURE; CLI-driven build; no GUI surface added).

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
