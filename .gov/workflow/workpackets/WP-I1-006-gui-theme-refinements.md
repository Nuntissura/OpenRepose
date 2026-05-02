# WP-I1-006 - GUI Theme Refinements

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I1
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements (anti-AI-feel rules).

## Intent

Polish the dark theme: tighten spacing, fix any rendering glitches surfaced by operator use, ensure visual consistency across panes. Specifically NOT to add Material Design / soft shadows / wizard chrome — the spec rules against AI-feel still apply.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-004 must reach DONE.

## Reality Boundary

- **Real Seam**: edits to `gui/style.py` QSS sheet; small layout-margin / font-weight adjustments in widget constructors as needed.
- **User-Visible Win**: GUI feels denser and more tool-like on operator's actual desktop.
- **Proof Target**: operator-confirmed visual review of a screenshot at proper desktop resolution.

## In Scope

- QSS pass for any visual issues found during WP-I0-004 review or operator's first-day use.
- Custom font registration (bundle Inter / Roboto for cross-machine consistency, optional).
- Better disabled-state styling.
- High-DPI monitor support verification.

## Out Of Scope

- Multiple themes (light mode etc.).
- Operator-customizable colors.
- Material Design / glassmorphism / any AI-feel aesthetic — explicitly forbidden by spec.

## Headless LLM Operation Compliance

- [x] N/A — GUI cosmetic changes only; no new commands.

## Definition Of Done

- [ ] All known visual issues resolved.
- [ ] Sample screenshot at 1920x1080 matches the operator's expected look.
- [ ] No regression in widget grab fidelity.

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` — Feature 1 / GUI Requirements, anti-AI-feel rules, dense tool-style aesthetic.
- `.gov/AGENTS.md` — Headless LLM Operation Rule (cosmetic-only; no command surface).

## Linked Test Suite

- `.product/tests/test_gui_theme.py` (NEW) — QSS load test, contrast smoke checks, font-fallback coverage on offscreen Qt.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I1-006-gui-theme-refinements.md` (this file)
- `.gov/workflow/TASKBOARD.md`

### Product (`.product/`)

- `.product/src/openrepose/gui/style.py` — QSS edits, font registration, disabled-state palette.
- `.product/src/openrepose/gui/main_window.py` — small layout-margin / spacing tweaks if needed.
- `.product/tests/test_gui_theme.py` (NEW)

### Build / Output

- `target/test-artifacts/WP-I1-006/`
- Optional bundled font under `.product/src/openrepose/gui/fonts/`.

## Risks And Dependencies

- **Risk**: bundled font licensing. **Mitigation**: only ship OFL/Apache-licensed faces (Inter, Roboto, JetBrains Mono); record license file under `.product/src/openrepose/gui/fonts/LICENSE-*.txt`.
- **Risk**: theme drift toward AI-feel chrome (cards, soft shadows). **Mitigation**: every change reviewed against the spec's "no AI-feel" list; PR description must call out which rule each change supports.
- **Dependency**: WP-I0-004 must be DONE; theme rides on the existing GUI scaffold.

## Test Coverage Plan

### Functional Flow Tests
- [ ] App launches with the updated QSS without warnings.
- [ ] Disabled buttons render distinguishably from enabled.

### Code Correctness Tests
- [ ] QSS file parses cleanly (no Qt warnings).
- [ ] Bundled fonts (if any) register through `QFontDatabase` without error.
- [ ] No widget grab regression vs WP-I0-004 baseline (image diff under operator-set tolerance).

### Red-Team / Abuse Tests
- [ ] No QSS rule introduces a forbidden yaw phrase as text.
- [ ] No Material Design class names or properties (`box-shadow`, `border-radius` over 4px) in the QSS.

### Performance / Reliability Tests
- [ ] App startup time within 50ms of WP-I0-004 baseline.

## Rollback Plan

- Files to revert: `gui/style.py`, any bundled font assets, layout tweaks in `gui/main_window.py`.
- Files to keep: WP file moves to archive `CANCELLED` if rolled back.
- Recovery command: `git restore --staged .product/; git checkout -- .product/src/openrepose/gui/style.py .product/src/openrepose/gui/main_window.py .product/tests/test_gui_theme.py`

## Decisions Log

- (none yet at DRAFT stage; populate during implementation)

## Fallback Register

- (none planned at DRAFT stage)

## Change Ledger

- (filled at REVIEW)

## Checkpoint Commit Plan

1. Governance kickoff: this WP file + taskboard row.
2. Implementation: QSS edits + optional font bundle.
3. Verification: pytest results + side-by-side screenshots.

## Proof Of Implementation

- **Command Runs**: `pytest .product/tests/test_gui_theme.py --junitxml=target/test-artifacts/WP-I1-006/pytest_results.xml`
- **Proof Artifact**: `target/test-artifacts/WP-I1-006/pytest_results.xml` plus `before.png` / `after.png` widget grabs.
- **Claim Standard**: never mark `DONE` without junit XML evidence and operator-confirmed visual review at 1920x1080.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, Change Ledger truthful.
- [ ] Linked test suite executed; junit XML saved at `target/test-artifacts/WP-I1-006/pytest_results.xml`.
- [ ] Evidence section populated with concrete paths (including before/after screenshots).
- [ ] Operator sign-off recorded in Evidence.
- [ ] Headless LLM Operation Compliance: marked N/A with reason (cosmetic; no command surface).

## Evidence

- (filled at REVIEW)

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
- 2026-05-02: Enhanced with full template sections (Files Touched, Test Plan, Risks, Rollback, Exit Criteria, etc.) for session-survivability.
