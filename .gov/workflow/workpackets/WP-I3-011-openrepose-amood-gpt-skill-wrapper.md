# WP-I3-011 - OpenRepose AMood GPT + Claude Skill Wrappers

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DRAFT
- **Iteration**: I3
- **Workflow Version**: 1.1
- **Packet Class**: DOCUMENTATION
- **Effort Estimate**: M
- **Linked Spec**:
  - `.gov/spec/openrepose_amood_v0_1.md`
  - `.gov/spec/openrepose_intake_v0_1.md`
  - `.gov/spec/openrepose_rules_v0_1.md`
  - `.gov/spec/openrepose_requirements_v0_1.md`
- **Linked Test Suite**: N/A
- **Linked Check Script**: `scripts/audit-repo.ps1`

## Intent

Create two dedicated OpenRepose AMood wrappers after the OpenRepose database and dispatcher command surface are fully functional: one for GPT/OpenAI use and one for Claude/Codex-style skill use. Both wrappers compose the shared global AMood full-package workflow with OpenRepose-specific storage, runtime state acknowledgement, dispatcher/inbox handoff, Postgres import, intake scoring, accepted-set audit, and workflow-index updates without forking AMood's core rules.

## Linked Workpackets

- **Predecessor(s)**: WP-I3-003, WP-I3-004, WP-I3-006, WP-I3-007, WP-I3-010
- **Successor(s)**: none
- **Blocks**: none
- **Blocked-By**: OpenRepose DB/dispatcher/AMood command path not fully functional yet
- **Related**: WP-I3-001, WP-I3-002

## Linked Requirements / Spec Sections

- `openrepose_amood_v0_1.md` / AMood package layout and command surface
- `openrepose_intake_v0_1.md` / Project, task, output, intake status, and two-stage acceptance lifecycle
- `openrepose_rules_v0_1.md` / Error citation contract and rule registry
- `openrepose_requirements_v0_1.md` / Targets, progress counters, and acceptance requirements
- `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` / Skill Conversion Block and full package contract

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | OpenAI Help | https://help.openai.com/en/articles/8554407-gpts-in-chatgpt | A custom GPT is a configured assistant with instructions, knowledge, and selected capabilities. Do not rely on two separate GPTs or skills composing at runtime for one workflow. The GPT track needs one composed OpenRepose AMood GPT. | adopt |
| 2026-05-03 | OpenAI Help | https://help.openai.com/en/articles/8554397-creating-and-editing-gpts-in-chatgpt | GPT Knowledge is limited and best treated as reference material; critical workflow rules belong in Instructions. | adopt |
| 2026-05-03 | OpenAI Help | https://help.openai.com/en/articles/11325361 | OpenAI troubleshooting guidance says rules/tone/workflow should be in Instructions, while Knowledge works best for reference data. Actions can be limited by workspace settings and configuration. | adopt |
| 2026-05-03 | OpenAI Status | https://status.openai.com/incidents/01K2Z3WTYEM0WN3EPJMY25VD13 | Custom GPT actions have had platform incidents where calls got stuck. The wrapper needs an operator-readable fallback handoff and must not claim DB import if action/dispatcher calls fail. | adopt |
| 2026-05-03 | OpenAI community / Reddit feedback | `community.openai.com` and `reddit.com` user reports reviewed 2026-05-03 | Users report Custom GPTs sometimes ignore knowledge files, drift from instructions, or need explicit prompting to search uploaded files. The OpenRepose wrapper must keep non-negotiable behavior short and duplicated in the top-level instructions, not only in Knowledge. | adapt |
| 2026-05-03 | Security research | https://arxiv.org/abs/2506.04036 and https://arxiv.org/abs/2506.00197 | Custom GPT instructions and uploaded knowledge can leak under adversarial prompting. Do not put private credentials, operator tokens, or sensitive DB connection strings into GPT instructions or knowledge. | adopt |

## Reality Boundary

- **Real Seam**: two documented OpenRepose AMood wrappers exist: a GPT/OpenAI wrapper and a Claude/Codex-style skill wrapper. Both read the AMood blueprint, use OpenRepose runtime state, write packages under `outputs/library/<project_slug>/<batch_slug>/`, and import/update state through the dispatcher when available.
- **User-Visible Win**: the operator can invoke either the GPT/OpenAI OpenRepose AMood wrapper or the Claude/Codex OpenRepose AMood skill and get the same coherent full package workflow that lands in OpenRepose instead of a standalone prompt folder.
- **Proof Target**: completed GPT wrapper instructions/knowledge/action notes, completed Claude/Codex skill wrapper files, and two dry-run transcripts showing package creation, dispatcher payloads, fallback inbox payloads, and scorecard/update behavior against a fully functional OpenRepose DB.
- **Allowed Temporary Fallbacks**: fallback-only handoff text is allowed if external GPT Actions are not available; placeholder action schemas are allowed only if clearly marked as not live.
- **Promotion Guard**: do not promote this WP until the DB/dispatcher path for AMood package import, intake output registration, soft accept/reject, accepted-set audit, and workflow-index state updates exists and has passing evidence in predecessor WPs. Do not mark this WP implemented until both the GPT/OpenAI wrapper and the Claude/Codex skill wrapper pass their dry-run acceptance transcripts.

## In Scope

- Define OpenRepose AMood wrappers as companion integration layers, not AMood forks.
- Create a concise shared hard-rules block used by both GPT/OpenAI and Claude/Codex wrappers:
  - full package only
  - read canonical AMood blueprint
  - acknowledge `adult_production_boundary` by reading runtime state
  - write under `outputs/library/<project_slug>/<batch_slug>/`
  - use dispatcher commands when available
  - fall back to `outputs/.runtime/inbox/` payloads when HTTP fails
  - never claim DB import, scoring, or audit succeeded unless the command result proves it
  - never edit `.gov/`, `.product/`, or tracked files during package runs
- Specify how each wrapper composes the global AMood blueprint with OpenRepose state, command names, package paths, and Postgres ingest.
- Track 1: GPT/OpenAI wrapper:
  - one composed GPT, not multiple GPTs
  - hard rules in Instructions
  - AMood blueprint as Knowledge
  - optional OpenRepose action schema only when the OpenRepose bridge endpoint is stable
  - no reliance on GPT memory across conversations
- Track 2: Claude/Codex wrapper:
  - local skill folder or Claude skill instructions that invoke the same global AMood skill behavior
  - OpenRepose-specific `SKILL.md` keeps only integration rules and references the canonical AMood blueprint
  - uses filesystem access and dispatcher/inbox payloads directly when available
  - no duplication of AMood package schemas except minimal hard-rule summary
- Define a dry-run acceptance transcript for a realistic adult production batch:
  - project lookup/create
  - package scaffold under `outputs/library/`
  - `init_batch_package`
  - `amood_import_tsv`
  - generated output registration
  - soft accept/reject
  - accepted-set diversity audit
  - package `INDEX.md` update
- Define fallback behavior for unavailable actions, unavailable dispatcher, and unknown I3 commands.

## Out Of Scope

- Changing the global AMood blueprint semantics.
- Creating a smaller AMood workflow.
- Product implementation of missing DB tables, migrations, dispatcher commands, or GUI surfaces.
- Queuing ComfyUI or hosted image/video runs.
- Storing credentials, DB URLs, operator tokens, or private API keys in GPT instructions, knowledge, or committed repo files.
- Editing `.gov/` or `.product/` as part of ordinary package runs after the wrapper exists.

## Expected Files Touched

### Governance (`.gov/`)

- `.gov/workflow/workpackets/WP-I3-011-openrepose-amood-gpt-skill-wrapper.md`
- `.gov/workflow/TASKBOARD.md`
- `.gov/doc/references/openrepose-amood-gpt-wrapper.md` (new, if the GPT wrapper is stored in repo governance)
- `.gov/doc/references/openrepose-amood-claude-skill-wrapper.md` (new, if the Claude/Codex wrapper is stored in repo governance)
- `.gov/doc/manual/amood-workflow.md` (only if operator-facing manual handoff changes)

### Product (`.product/`)

- N/A. If product commands are missing, stop and open a successor implementation WP instead.

### Build / Output (gitignored)

- `outputs/library/<project_slug>/<batch_slug>/` for dry-run package artifacts
- `outputs/.runtime/inbox/` for fallback dispatcher payload examples
- `target/test-artifacts/WP-I3-011/` for transcript/evidence captures

## Risks And Dependencies

- **Risk**: either wrapper becomes a fork of AMood and drifts from the canonical blueprint. **Mitigation**: both wrappers must read the canonical blueprint and keep only OpenRepose-specific integration rules locally.
- **Risk**: GPT and Claude/Codex wrappers drift from each other. **Mitigation**: maintain one shared hard-rules block and require a parity checklist before DONE.
- **Risk**: GPT Knowledge retrieval skips the blueprint. **Mitigation**: duplicate hard operational rules in GPT Instructions and require an explicit blueprint-read step before package generation.
- **Risk**: GPT Actions or OpenRepose dispatcher calls fail. **Mitigation**: produce explicit HTTP payloads and inbox fallback payloads; never claim import/scoring/audit success without a command result.
- **Risk**: users expect persistent GPT memory. **Mitigation**: all durable state lives in OpenRepose Postgres, runtime state, package `INDEX.md`, manifests, and scorecards.
- **Risk**: instruction or knowledge leakage exposes secrets. **Mitigation**: keep secrets out of instructions, knowledge files, and committed artifacts.
- **Dependency**: WP-I3-006 AMood command surface. **Owner**: assistant. **Status**: not drafted / not complete.
- **Dependency**: WP-I3-010 end-to-end EXP120 verification. **Owner**: assistant. **Status**: not drafted / not complete.

## Definition Of Done

- [ ] GPT/OpenAI OpenRepose AMood wrapper instructions exist as a repo governance document or operator-approved GPT configuration.
- [ ] Claude/Codex OpenRepose AMood skill wrapper exists as a repo governance document or operator-approved local skill folder.
- [ ] Both wrappers state clearly that they compose AMood and OpenRepose; they do not fork AMood rules.
- [ ] Both wrappers read `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` first inside OpenRepose.
- [ ] Both wrappers require runtime `adult_production_boundary` acknowledgement before dispatcher commands.
- [ ] Both wrappers write full AMood packages under `outputs/library/<project_slug>/<batch_slug>/`.
- [ ] Both wrappers define HTTP dispatcher payloads and inbox fallback payloads for package init/import.
- [ ] Both wrappers define OpenRepose intake scoring behavior using dispatcher commands as system of record.
- [ ] Both wrappers include failure language for unavailable actions, unavailable dispatcher, and unknown commands.
- [ ] GPT/OpenAI dry-run transcript proves the wrapper can restart from package `INDEX.md`, manifests, scorecard, and runtime state.
- [ ] Claude/Codex dry-run transcript proves the wrapper can restart from package `INDEX.md`, manifests, scorecard, and runtime state.
- [ ] Parity checklist confirms both wrappers share the same hard rules, package paths, dispatcher payloads, fallback behavior, and acceptance/audit requirements.
- [ ] No credentials, operator tokens, DB URLs, or private API keys are embedded in wrapper instructions or knowledge files.
- [ ] **Manual Impact**: Yes - update `amood-workflow.md` or add a linked manual note explaining when to use global AMood vs OpenRepose AMood, and noting that OpenRepose AMood has both GPT/OpenAI and Claude/Codex wrapper tracks.

## Test Coverage Plan

### Functional Flow Tests
- [ ] GPT/OpenAI dry-run: OpenRepose repo detected or supplied, blueprint resolved, runtime state read, package path selected.
- [ ] GPT/OpenAI dry-run: project lookup/create, package scaffold, init/import payloads produced.
- [ ] GPT/OpenAI dry-run: generated outputs registered, soft accepted/rejected, scorecard mirrored.
- [ ] Claude/Codex dry-run: OpenRepose repo detected, blueprint resolved, runtime state read, package path selected.
- [ ] Claude/Codex dry-run: project lookup/create, package scaffold, init/import payloads produced.
- [ ] Claude/Codex dry-run: generated outputs registered, soft accepted/rejected, scorecard mirrored.

### Code Correctness Tests
- [ ] N/A - documentation/skill wrapper only unless a successor implementation WP is opened.

### Red-Team / Abuse Tests
- [ ] GPT/OpenAI request for a standalone package inside OpenRepose still routes to `outputs/library/<project>/<batch>/`.
- [ ] Claude/Codex request for a standalone package inside OpenRepose still routes to `outputs/library/<project>/<batch>/`.
- [ ] Request to skip blueprint read is refused or corrected in both wrappers.
- [ ] Request to claim import without dispatcher/inbox result is refused in both wrappers.
- [ ] Prompt asking for credentials/tokens/DB URLs is refused in both wrappers; wrapper explains that secrets stay outside instructions and knowledge.

### Performance / Reliability Tests
- [ ] GPT/OpenAI restart test: given only package `INDEX.md`, manifests, scorecard, and runtime state, the wrapper resumes the correct next action.
- [ ] Claude/Codex restart test: given only package `INDEX.md`, manifests, scorecard, and runtime state, the wrapper resumes the correct next action.

## Rollback Plan

- Files to revert: GPT wrapper governance document/config notes and Claude/Codex skill wrapper governance document or skill folder created by this WP.
- Files to keep: package dry-run artifacts under `outputs/library/` if they contain useful operator examples.
- Recovery command: `git revert <governance-commit-hash>` for repo files; manually remove operator-local skill folder only with operator approval.

## Decisions Log

- 2026-05-03: Drafted as companion OpenRepose wrappers, not AMood forks. Reason: AMood remains the canonical package workflow; OpenRepose-specific path/state/dispatcher/DB behavior belongs in wrappers to avoid schema and scoring drift.
- 2026-05-03: Scheduled after DB/dispatcher functionality is complete. Reason: the wrapper should be tested against real command results rather than placeholder assumptions.
- 2026-05-03: Critical GPT behavior goes in Instructions, not only Knowledge. Reason: user feedback and OpenAI troubleshooting both show Knowledge retrieval is not a reliable place for non-negotiable workflow rules.
- 2026-05-03: Split the WP into two required tracks: GPT/OpenAI and Claude/Codex. Reason: both ecosystems have a global AMood skill/blueprint path, and the OpenRepose integration is not implemented until both can run the same full-package OpenRepose workflow.

## Fallback Register

- **Path**: wrapper instructions created by this WP
- **Required Label In Code/UI**: `Fallback: if OpenRepose dispatcher or GPT Actions are unavailable, emit exact HTTP and inbox payloads and do not claim import/scoring/audit success.`
- **Successor / Debt Owner**: none
- **Exit Condition To Remove**: never remove; it is permanent defensive behavior for external GPT/action reliability.

## Change Ledger

_Captured at REVIEW. Truthful summary._

- **What Became Real**: _filled at REVIEW._
- **What Remains Simulated**: _filled at REVIEW._
- **Next Blocking Real Seam**: _filled at REVIEW._

## Checkpoint Commit Plan

1. Governance kickoff commit (this WP file + taskboard row).
2. GPT/OpenAI wrapper document/config note commit after predecessors close.
3. Claude/Codex skill wrapper commit.
4. Dry-run transcripts, parity checklist, and manual update commit.

## Proof Of Implementation

- **Command Runs**: N/A until implementation; GPT/OpenAI and Claude/Codex dry-run evidence captured under `target/test-artifacts/WP-I3-011/`.
- **Proof Artifact**: `target/test-artifacts/WP-I3-011/`
- **Claim Standard**: never mark `DONE` without dry-run transcripts for both GPT/OpenAI and Claude/Codex wrappers against a fully functional OpenRepose DB/dispatcher path.

## Headless LLM Operation Compliance

N/A - documentation/skill wrapper workpacket. Both wrappers must use the existing headless command surface and must not require GUI interaction.

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects current status.
- [ ] Reality Boundary, Fallback Register, and Change Ledger are truthful.
- [ ] GPT/OpenAI dry-run evidence saved under `target/test-artifacts/WP-I3-011/`.
- [ ] Claude/Codex dry-run evidence saved under `target/test-artifacts/WP-I3-011/`.
- [ ] Parity checklist saved under `target/test-artifacts/WP-I3-011/`.
- [ ] Operator sign-off recorded in Evidence section.

## Evidence

- **Test Suite Execution**: N/A.
- **Logs**: _filled at REVIEW._
- **Screenshots / Exports**: N/A.
- **Build Artifacts**: N/A.
- **Proof Artifact**: `target/test-artifacts/WP-I3-011/`
- **Operator Sign-off**: pending.

## Progress Log

- 2026-05-03: WP drafted at DRAFT per operator request to capture OpenRepose AMood GPT/skill wrapper idea for later, after the database and dispatcher path is fully functional.
- 2026-05-03: WP revised into a two-track deliverable: GPT/OpenAI wrapper plus Claude/Codex skill wrapper. Both must work before implementation can be considered complete.
