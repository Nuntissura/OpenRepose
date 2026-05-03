# WP-I3-002 - LLM Stance Acknowledgement Primitives

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: REVIEW
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
- `.product/src/openrepose/channels/http.py`
- `.product/src/openrepose/channels/inbox.py`
- `.product/tests/test_state_file.py`
- `.product/tests/test_command_handlers.py`
- `.product/tests/test_http_channel.py`
- `.product/tests/test_inbox_channel.py`

### Build / Output (gitignored)

- `target/test-artifacts/WP-I3-002/`

## Risks And Dependencies

- **Risk**: adding a field to every command response breaks overly strict tests or clients. **Mitigation**: prefer stable additive fields under a predictable key; update tests for additive compatibility.
- **Risk**: duplicate stance strings drift. **Mitigation**: use one product constant/helper and reference it from state/commands.
- **Dependency**: none external. **Owner**: assistant. **Status**: satisfied.

## Definition Of Done

- [x] Product code has one canonical adult-production stance payload.
- [x] `outputs/.runtime/state.json` and `dump_state` expose the stance and acknowledgement requirement.
- [x] LLM command responses or command schema primitives expose the stance so HTTP/inbox agents see it.
- [x] Manual and spec explicitly say LLM primitive/API consumers must read and acknowledge the stance.
- [x] Focused tests pass.
- [x] Audit clean.
- [x] **Manual Impact**: Yes - extends `adult-production-boundary.md` with primitive/API acknowledgement behavior.

## Test Coverage Plan

### Functional Flow Tests
- [x] `dump_state` includes the adult-production stance payload.
- [x] At least one ordinary command response includes or preserves the stance payload.

### Code Correctness Tests
- [x] State serialization test covers the new field shape.
- [x] Command handler test covers additive response shape.
- [x] YAML/spec/manual checks still pass.

### Red-Team / Abuse Tests
- [x] Confirm the stance field does not ask for legal paperwork and does not block ordinary commands.

### Performance / Reliability Tests
- [x] N/A - static payload only.

## Rollback Plan

- Files to revert: product stance helper/state/command edits and the matching tests/spec/manual lines.
- Files to keep: prior Adult Production Boundary docs from the governance-only pass.
- Recovery command: normal git revert of this WP's implementation commit.

## Decisions Log

- 2026-05-03: Use additive primitive exposure instead of a blocking acknowledgement database. Reason: the operator wants every LLM to see and acknowledge the stance; OpenRepose should not become a compliance gate or paperwork tracker.

## Fallback Register

- None.

## Change Ledger

- **What Became Real**: `adult_production_boundary` is now emitted by the real product primitives: `AppState.to_dict()`, `state.json`, `dump_state`, `CommandResult.to_dict()`, HTTP command responses, HTTP malformed/non-localhost error envelopes, inbox processed command results, and inbox malformed-JSON error results. Focused tests cover all LLM-facing paths changed here.
- **What Remains Simulated**: nothing in this WP's scope. Future APIs still need to preserve the same object when they are implemented.
- **Next Blocking Real Seam**: future API/schema WPs must include `adult_production_boundary` in their handshake/schema tests.

## Checkpoint Commit Plan

1. Governance kickoff commit (this WP + taskboard + stance docs/spec).
2. Product primitive implementation commit.
3. Verification commit if tests/evidence need separate recording.

## Proof Of Implementation

- **Command Runs**: `.\\.venv\\Scripts\\python.exe -m pytest .product/tests/test_state_file.py .product/tests/test_command_handlers.py .product/tests/test_http_channel.py .product/tests/test_inbox_channel.py --junitxml=target/test-artifacts/WP-I3-002/pytest_results.xml -q`
- **Proof Artifact**: `target/test-artifacts/WP-I3-002/`
- **Claim Standard**: never mark `DONE` without linked command evidence and artifact paths.

## Headless LLM Operation Compliance

- [x] An LLM agent can trigger this feature through the command channel (HTTP or inbox) without touching the GUI.
- [x] An LLM agent can read this feature's state from `outputs/.runtime/state.json`.
- [x] N/A - no new visual artifact; this is a state/command primitive contract.
- [x] No code path in this feature calls `raise_()`, `activateWindow()`, `showNormal()`, `setForegroundWindow()`, or any equivalent.
- [x] The feature does not display modal dialogs in response to commands originating from the LLM control surface.
- [x] Tests cover the headless path.

## Exit Criteria

- [x] Definition of Done items all checked.
- [x] Taskboard row reflects current status.
- [x] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [x] Linked test suite has executed results saved under `target/test-artifacts/WP-I3-002/`.
- [x] Evidence section populated with concrete paths.
- [ ] Operator sign-off recorded in Evidence section.
- [x] **Headless LLM Operation Compliance** section either marked `N/A` with reason, or all items checked.

## Evidence

- **Test Suite Execution**: `target/test-artifacts/WP-I3-002/pytest_results.xml` - 24 passed in 10.97s. One pre-existing Windows `PermissionError` warning from `test_state_write_atomic_no_partial` reader thread remains unchanged.
- **Logs**: pytest stdout in this session; junit XML at proof artifact path.
- **Screenshots / Exports**: N/A.
- **Build Artifacts**: N/A.
- **Proof Artifact**: `target/test-artifacts/WP-I3-002/`
- **Operator Sign-off**: pending.

## Progress Log

- 2026-05-03: WP initialized directly at IN-PROGRESS per operator request. Product inspection/edit waits for kickoff commit and push per Work-Start Protocol.
- 2026-05-03: Kickoff commit `769a9e9` pushed to `origin/main` before product inspection/edit.
- 2026-05-03: Product implementation complete. Added canonical stance payload in `state.py`; exposed it through state, command envelopes, HTTP responses, and inbox responses. Focused tests 24/24 passing with one pre-existing Windows state-read warning. Status IN-PROGRESS -> REVIEW.
