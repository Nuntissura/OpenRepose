# WP-I4-002 - Orstart Codex Contract Banner

## Header

- **Owner**: `assistant`
- **Date Opened**: `2026-05-04`
- **Last Updated**: `2026-05-04`
- **Status**: `IN-PROGRESS`
- **Iteration**: `I4`
- **Workflow Version**: `1.1`
- **Packet Class**: `INFRASTRUCTURE`
- **Effort Estimate**: `XS`
- **Linked Spec**: `N/A`
- **Linked Test Suite**: `N/A`
- **Linked Check Script**: `N/A`

## Intent

Make the `.\orstart` startup banner explicitly tell assistants to read `.gov/CODEX.md`, treat it as binding repo context, and follow its rules and instructions before advising or editing.

## Linked Workpackets

- **Predecessor(s)**: `none`
- **Successor(s)**: `none`
- **Blocks**: `none`
- **Blocked-By**: `none`
- **Related**: `WP-I3-002`, `WP-I1-035`

## Linked Requirements / Spec Sections

- `.gov/AGENTS.md` / Required Startup Context
- `.gov/CODEX.md` / Authority Map

## Research Notes

No external research required. This is a wording-only infrastructure change to the local startup banner; it introduces no dependency, model, algorithm, or external behavior.

## Reality Boundary

- **Real Seam**: `scripts/orstart.ps1` emits an explicit assistant instruction that `.gov/CODEX.md` must be read and treated as binding project context.
- **User-Visible Win**: A fresh assistant running `.\orstart` sees the codex obligation in the banner before the printed file sections.
- **Proof Target**: `.\orstart -Brief` output contains the new instruction text.
- **Allowed Temporary Fallbacks**: none.
- **Promotion Guard**: Do not move to REVIEW until `.\orstart -Brief` proves the text is printed.

## In Scope

- Update the startup banner wording in `scripts/orstart.ps1`.
- Run `.\orstart -Brief` and verify the new wording is visible.
- Update this workpacket and the taskboard for the status transition.

## Out Of Scope

- Changing the codex content.
- Changing product runtime behavior.
- Changing root `AGENTS.md` linkage.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I4-002-orstart-codex-contract-banner.md`
- `.gov/workflow/TASKBOARD.md`

### Product / Infrastructure

- `scripts/orstart.ps1`

### Build / Output (gitignored)

- `target/test-artifacts/WP-I4-002/` (optional proof capture if needed)

## Risks And Dependencies

- **Risk**: Banner wording becomes ambiguous or too verbose. **Mitigation**: Keep it to two direct startup-instruction lines.
- **Dependency**: PowerShell runtime for `.\orstart -Brief`. **Owner**: assistant. **Status**: satisfied.

## Definition Of Done

- [ ] `.\orstart -Brief` prints an explicit instruction to read `.gov/CODEX.md`.
- [ ] `.\orstart -Brief` states that `.gov/CODEX.md` is binding project context and its rules/instructions must be followed.
- [ ] `git status --short` reviewed; unrelated pre-existing manual edits remain untouched.
- [ ] **Manual Impact**: `No - startup banner wording only; no operator-facing application manual surface changes.`

## Test Coverage Plan

N/A for this XS infrastructure wording change. Runtime proof is `.\orstart -Brief`.

## Rollback Plan

- Files to revert: `scripts/orstart.ps1`, `.gov/workflow/workpackets/WP-I4-002-orstart-codex-contract-banner.md`, `.gov/workflow/TASKBOARD.md`
- Files to keep: unrelated operator edits under `.gov/doc/manual/`
- Recovery command: use a normal corrective commit; do not reset unrelated dirty files.

## Decisions Log

- `2026-05-04`: Use a dedicated `WP-I4-002` because changing `scripts/orstart.ps1` is infrastructure/product-side work under the repo's Work-Start Protocol. Alternatives considered: editing only `.gov/AGENTS.md`, rejected because the operator asked what `orstart` tells assistants.

## Fallback Register

None.

## Change Ledger

- **What Became Real**: pending.
- **What Remains Simulated**: none.
- **Next Blocking Real Seam**: pending.

## Checkpoint Commit Plan

1. Governance kickoff commit with this workpacket and taskboard row.
2. Startup banner implementation commit.
3. REVIEW handoff commit with proof noted.

## Proof Of Implementation

- **Command Runs**: pending.
- **Proof Artifact**: pending.
- **Claim Standard**: never mark `DONE` without linked command evidence and artifact paths.

## Headless LLM Operation Compliance

N/A - startup banner wording only; no operator-facing or visually interactive application feature is added.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [ ] Evidence section populated with concrete command output summary.
- [ ] Operator sign-off recorded before DONE.
- [ ] **Headless LLM Operation Compliance** marked N/A with reason.

## Evidence

- **Test Suite Execution**: pending.
- **Logs**: pending.
- **Screenshots / Exports**: N/A.
- **Build Artifacts**: N/A.
- **Proof Artifact**: pending.
- **Operator Sign-off**: pending.

## Progress Log

- `2026-05-04`: WP initialized at IN-PROGRESS so the startup banner patch can proceed after kickoff commit and push.
