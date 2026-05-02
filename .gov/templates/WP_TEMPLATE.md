# WP-<ITERATION>-<NNN> - <TITLE>

## Header

- **Owner**: `<operator | assistant slug>`
- **Date Opened**: `YYYY-MM-DD`
- **Last Updated**: `YYYY-MM-DD`
- **Status**: `DRAFT | READY | IN-PROGRESS | BLOCKED | REVIEW | DONE | CANCELLED`
- **Iteration**: `I0..In | All`
- **Workflow Version**: `1.1`
- **Packet Class**: `RESEARCH | SCAFFOLD | IMPLEMENTATION | VERIFICATION | DOCUMENTATION | INFRASTRUCTURE`
- **Effort Estimate**: `XS | S | M | L | XL`
- **Linked Spec**: `.gov/spec/<spec-file>.md` (or `N/A`)
- **Linked Test Suite**: `.gov/workflow/test_suites/<file>.md` (or `N/A`)
- **Linked Check Script**: `.gov/workflow/checks/<file>.ps1` (or `N/A`)

## Intent

_1-3 sentence outcome statement. What does the world look like after this workpacket is DONE? Concrete, not aspirational._

## Linked Workpackets

- **Predecessor(s)**: `<WP-IDs that must be DONE first>` (or `none`)
- **Successor(s)**: `<WP-IDs that depend on this>` (or `none`)
- **Blocks**: `<WP-IDs that cannot start until this is DONE>` (or `none`)
- **Blocked-By**: `<WP-IDs currently blocking this>` (or `none`)
- **Related**: `<WP-IDs for context only, no strict dependency>` (or `none`)

## Linked Requirements / Spec Sections

- `<spec-section-or-REQ-id>`
- `<spec-section-or-REQ-id>`

## Research Notes

Required for IMPLEMENTATION / RESEARCH classes; optional for SCAFFOLD / VERIFICATION / DOCUMENTATION / INFRASTRUCTURE that does not introduce a new dependency, model, or algorithm.

Capture what was found before scope was locked. Keep entries dated. Update Reality Boundary or DoD in the same commit if research changes the chosen approach.

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| `YYYY-MM-DD` | `<github / hugging face / civit ai / arxiv / vendor docs / forum>` | `<url>` | `<one-line summary>` | `adopt | adapt | reject | watch` |

Sources to consider, in order of preference:

1. Official library / vendor docs (MediaPipe, ControlNet, PySide6, OpenCV, etc.).
2. GitHub repos — issues, READMEs, releases, code search.
3. Hugging Face — model cards, discussions, leaderboards.
4. Civit AI — model pages, version notes, reviews.
5. Vendor and university research papers — arXiv, vendor research blogs.
6. Forums, Discord summaries, blog posts when they contain concrete settings or evidence.

If the research concluded "the existing approach is correct, no better alternative found," log that explicitly with the sources checked and the date.

## Reality Boundary

Sacred. Captured before work starts. Do not rewrite after the fact.

- **Real Seam**: _Which part of reality this workpacket actually changes._
- **User-Visible Win**: _What the operator will see different after this workpacket._
- **Proof Target**: _Which command output, file, or artifact proves the change is real._
- **Allowed Temporary Fallbacks**: _Stubs, mocks, or sample data acceptable during this workpacket._
- **Promotion Guard**: _Explicit condition under which fallbacks must be removed._

## In Scope

- `<item>`
- `<item>`

## Out Of Scope

- `<item>`
- `<item>`

## Expected Files Touched

Group by repo split.

### Governance (`.gov/`)

- `.gov/workflow/workpackets/<this-wp>.md`
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/<spec>.md` (if contract changed)

### Product (`.product/`)

- `.product/src/openrepose/<module>.py`
- `.product/tests/test_<module>.py`

### Build / Output (gitignored)

- `target/test-artifacts/<this-wp>/`
- `outputs/<this-wp>/` (only if the workpacket genuinely produces app outputs)

## Risks And Dependencies

- **Risk**: `<description>`. **Mitigation**: `<plan>`.
- **Dependency**: `<external library, model file, license, hardware>`. **Owner**: `<operator | assistant>`. **Status**: `<satisfied | pending>`.

## Definition Of Done

Concrete checklist. Each item must be testable. No vague items.

- [ ] `<concrete checkbox>`
- [ ] `<concrete checkbox>`
- [ ] `<concrete checkbox>`

## Test Coverage Plan

_Required for VERIFICATION and IMPLEMENTATION classes. Optional for SCAFFOLD / RESEARCH / DOCUMENTATION._

### Functional Flow Tests
- [ ] _Golden flow case_
- [ ] _Edge cases_

### Code Correctness Tests
- [ ] _Unit tests_
- [ ] _Integration tests_
- [ ] _Static analysis (lint, type, schema)_

### Red-Team / Abuse Tests
- [ ] _Forbidden inputs rejected_
- [ ] _Misuse scenarios documented_

### Performance / Reliability Tests
- [ ] _Performance budget if applicable_
- [ ] _Recovery / offline behavior if applicable_

## Rollback Plan

_If implementation fails after partial work, how do we revert without losing operator work?_

- Files to revert: `<paths>`
- Files to keep: `<paths and reason>`
- Recovery command: `<git command or other action>`

## Decisions Log

Running record of choices made during the workpacket. Append-only.

- `YYYY-MM-DD`: _Decision_. _Reason_. _Alternatives considered_.

## Fallback Register

If any temporary fallback is in use during the workpacket, log it here.

- **Path**: `<file:line or module>`
- **Required Label In Code/UI**: `<text marker>`
- **Successor / Debt Owner**: `<WP-ID or operator>`
- **Exit Condition To Remove**: `<concrete condition>`

## Change Ledger

Captured at REVIEW time. Truthful summary.

- **What Became Real**: _What concretely changed._
- **What Remains Simulated**: _What still uses fallbacks or stubs._
- **Next Blocking Real Seam**: _What the next workpacket would need to make real._

## Checkpoint Commit Plan

Recommended (not enforced). Helps keep history navigable.

1. Governance kickoff commit (workpacket file + taskboard row).
2. Implementation commit(s) in `.product/`.
3. Verification commit (test results, evidence pointers).

## Proof Of Implementation

- **Command Runs**: `<command>` produces output at `<path>`.
- **Proof Artifact**: `target/test-artifacts/<this-wp>/`
- **Claim Standard**: never mark `DONE` without linked command evidence and artifact paths.

## Headless LLM Operation Compliance

_Required for any IMPLEMENTATION-class workpacket that adds an operator-facing or visually interactive feature. Mark `N/A — non-visual change` with a brief reason if the WP touches no GUI / visual surface (e.g., pure infrastructure or back-end refactor)._

- [ ] An LLM agent can trigger this feature through the command channel (HTTP or inbox) without touching the GUI.
- [ ] An LLM agent can read this feature's state from `outputs/.runtime/state.json` (or a documented additional state file).
- [ ] An LLM agent can pull a visual artifact of this feature via the snapshot subsystem (existing target or a new one declared here).
- [ ] No code path in this feature calls `raise_()`, `activateWindow()`, `showNormal()`, `setForegroundWindow()`, or any equivalent.
- [ ] The feature does not display modal dialogs in response to commands originating from the LLM control surface.
- [ ] Tests cover the headless path as well as (or instead of) the GUI path.

## Exit Criteria

All items checked before transitioning to `DONE`.

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [ ] Linked test suite has executed results saved under `target/test-artifacts/<this-wp>/`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence section.
- [ ] **Headless LLM Operation Compliance** section either marked `N/A` with reason, or all items checked.

## Evidence

- **Test Suite Execution**: `<path or N/A>`
- **Logs**: `<path or N/A>`
- **Screenshots / Exports**: `<path or N/A>`
- **Build Artifacts**: `<path under target/ or dist/>`
- **Proof Artifact**: `target/test-artifacts/<this-wp>/`
- **Operator Sign-off**: `<YYYY-MM-DD: APPROVED by operator | rejection note>`

## Progress Log

Append-only. One line per significant event.

- `YYYY-MM-DD`: WP initialized.
