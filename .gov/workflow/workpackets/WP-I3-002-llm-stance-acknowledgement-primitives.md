# WP-I3-002 - LLM Stance Acknowledgement Primitives

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: IN-PROGRESS
- **Iteration**: I3
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: S
- **Linked Spec**: `.gov/spec/openrepose_v0_1.md` Application-Wide Conventions / Adult Production Boundary; LLM Control Surface.
- **Linked Test Suite**: `.product/tests/test_state_file.py`; `.product/tests/test_command_handlers.py`; targeted tests added/extended in this WP.
- **Linked Check Script**: `scripts/audit-repo.ps1`

## Intent

Every LLM-facing OpenRepose entry point exposes the Adult Production Boundary before or alongside ordinary application state and command results. An LLM touching OpenRepose through state primitives, command primitives, the manual, or future API contracts sees the raw/direct adult-production stance and an explicit acknowledgement requirement.

## Linked Workpackets

- **Predecessor(s)**: WP-I1-035 (manual browser), WP-I3-001 (active documentation context; no strict block).
- **Successor(s)**: future API implementation WPs must preserve the stance field in their schema/handshake.
- **Blocks**: none.
- **Blocked-By**: none.
- **Related**: WP-I2-004 (LLM commands), WP-I2-007 (snapshot/state surfaces), WP-I3-001 (rule registry/spec lock).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_v0_1.md` / Adult Production Boundary.
- `.gov/spec/openrepose_v0_1.md` / LLM Control Surface.
- `.gov/doc/manual/adult-production-boundary.md`.
- `.gov/topology.yaml` / `repo_rules.adult_production_boundary`.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Local codebase | local `.gov/spec/openrepose_v0_1.md`, `.product/src/openrepose/state.py`, `.product/src/openrepose/commands.py` | This is a local contract/surface change, not a new dependency/model/algorithm choice. Use existing state and command primitives rather than adding a new external component. | adopt |

## Reality Boundary

- **Real Seam**: the app state/command primitive contract gains a stable adult-production stance object and acknowledgement requirement visible to LLM agents.
- **User-Visible Win**: operators can point any future LLM/API integration at the primitive contract and know the first context it sees includes the raw/direct Adult Production Boundary.
- **Proof Target**: tests assert state serialization and command responses expose the stance; `orstart -Brief` and manual link checks still show the stance first.
- **Allowed Temporary Fallbacks**: none.
- **Promotion Guard**: no implementation is complete unless the stance is produced by real app primitives, not just docs.

## In Scope

- Add one canonical stance/acknowledgement payload in product code.
- Expose that payload in `outputs/.runtime/state.json` and `dump_state`.
- Expose that payload through command responses or command schema primitives used by HTTP/inbox LLM agents.
- Update spec/manual/topology wording so future APIs preserve the same payload.
- Add focused tests for the stance payload.

## Out Of Scope

- Building a legal/compliance record system.
- Asking operators for legal or consent paperwork.
- Blocking ordinary commands until a separate database acknowledgement is stored.
- Broad API redesign beyond the smallest stable primitive needed here.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I3-002-llm-stance-acknowledgement-primitives.md`
- `.gov/workflow/TASKBOARD.md`
- `.gov/spec/openrepose_v0_1.md`
- `.gov/doc/manual/adult-production-boundary.md`
- `.gov/doc/manual/index.md`
- `.gov/topology.yaml`

### Product (`.product/`)

- `.product/src/openrepose/state.py`
- `.product/src/openrepose/commands.py`
- `.product/tests/test_state_file.py`
- `.product/tests/test_command_handlers.py`

### Build / Output (gitignored)

- `target/test-artifacts/WP-I3-002/`

## Risks And Dependencies

- **Risk**: adding a field to every command response breaks overly strict tests or clients. **Mitigation**: prefer stable additive fields under a predictable key; update tests for additive compatibility.
- **Risk**: duplicate stance strings drift. **Mitigation**: use one product constant/helper and reference it from state/commands.
- **Dependency**: none external. **Owner**: assistant. **Status**: satisfied.

## Definition Of Done

- [ ] Product code has one canonical adult-production stance payload.
- [ ] `outputs/.runtime/state.json` and `dump_state` expose the stance and acknowledgement requirement.
- [ ] LLM command responses or command schema primitives expose the stance so HTTP/inbox agents see it.
- [ ] Manual and spec explicitly say LLM primitive/API consumers must read and acknowledge the stance.
- [ ] Focused tests pass.
- [ ] Audit clean.
- [ ] **Manual Impact**: Yes - extends `adult-production-boundary.md` with primitive/API acknowledgement behavior.

## Test Coverage Plan

### Functional Flow Tests
- [ ] `dump_state` includes the adult-production stance payload.
- [ ] At least one ordinary command response includes or preserves the stance payload.

### Code Correctness Tests
- [ ] State serialization test covers the new field shape.
- [ ] Command handler test covers additive response shape.
- [ ] YAML/spec/manual checks still pass.

### Red-Team / Abuse Tests
- [ ] Confirm the stance field does not ask for legal paperwork and does not block ordinary commands.

### Performance / Reliability Tests
- [ ] N/A - static payload only.

## Rollback Plan

- Files to revert: product stance helper/state/command edits and the matching tests/spec/manual lines.
- Files to keep: prior Adult Production Boundary docs from the governance-only pass.
- Recovery command: normal git revert of this WP's implementation commit.

## Decisions Log

- 2026-05-03: Use additive primitive exposure instead of a blocking acknowledgement database. Reason: the operator wants every LLM to see and acknowledge the stance; OpenRepose should not become a compliance gate or paperwork tracker.

## Fallback Register

- None.

## Change Ledger

- **What Became Real**: pending.
- **What Remains Simulated**: pending.
- **Next Blocking Real Seam**: pending.

## Checkpoint Commit Plan

1. Governance kickoff commit (this WP + taskboard + stance docs/spec).
2. Product primitive implementation commit.
3. Verification commit if tests/evidence need separate recording.

## Proof Of Implementation

- **Command Runs**: pending.
- **Proof Artifact**: `target/test-artifacts/WP-I3-002/`
- **Claim Standard**: never mark `DONE` without linked command evidence and artifact paths.

## Headless LLM Operation Compliance

- [ ] An LLM agent can trigger this feature through the command channel (HTTP or inbox) without touching the GUI.
- [ ] An LLM agent can read this feature's state from `outputs/.runtime/state.json`.
- [ ] N/A - no new visual artifact; this is a state/command primitive contract.
- [ ] No code path in this feature calls `raise_()`, `activateWindow()`, `showNormal()`, `setForegroundWindow()`, or any equivalent.
- [ ] The feature does not display modal dialogs in response to commands originating from the LLM control surface.
- [ ] Tests cover the headless path.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [ ] Linked test suite has executed results saved under `target/test-artifacts/WP-I3-002/`.
- [ ] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence section.
- [ ] **Headless LLM Operation Compliance** section either marked `N/A` with reason, or all items checked.

## Evidence

- **Test Suite Execution**: pending.
- **Logs**: pending.
- **Screenshots / Exports**: N/A.
- **Build Artifacts**: pending.
- **Proof Artifact**: `target/test-artifacts/WP-I3-002/`
- **Operator Sign-off**: pending.

## Progress Log

- 2026-05-03: WP initialized directly at IN-PROGRESS per operator request. Product inspection/edit waits for kickoff commit and push per Work-Start Protocol.
