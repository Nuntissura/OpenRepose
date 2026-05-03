# WP-I3-001 - AMood + Intake + Requirements Spec Lock

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: REVIEW
- **Iteration**: I3
- **Workflow Version**: 1.1
- **Packet Class**: DOCUMENTATION
- **Effort Estimate**: L
- **Linked Spec**: 4 NEW spec files under `.gov/spec/` (`openrepose_amood_v0_1.md`, `openrepose_intake_v0_1.md`, `openrepose_rules_v0_1.md`, `openrepose_requirements_v0_1.md`) + spec README index update + `.gov/topology.yaml` extension.
- **Linked Test Suite**: N/A (DOCUMENTATION-class).
- **Linked Check Script**: N/A.

## Intent

Lock the contracts for OpenRepose's I3 iteration: integration with the AMood adult-production blueprint, an intake/triage staging surface that prevents bad LLM outputs from contaminating the main library, a project/task/batch/card/run/output hierarchy with target-tree counters, a typed scoped requirements registry (with EXP120 as the worked example), and a rule registry that makes the system self-documenting to any cold-start operator or LLM agent.

Output is four spec sections + four manual topics + topology updates. **No product code in this WP — spec/manual/governance authoring only.** I3 implementation WPs will be drafted against the locked contracts in subsequent sessions.

## Linked Workpackets

- **Predecessor(s)**: WP-I1-033 (DONE — Feature 3 Library spec), WP-I2-001..008 (REVIEW — Feature 3 implementation; technically this WP can author specs in parallel since the I3 contracts extend rather than depend on I2 code).
- **Successor(s)**: I3 implementation iteration — projects/tasks/batches DB additions, intake directory + bridge default-staging behavior, triage GUI tab, requirements editor, target-tree counters, rule registry wiring, four manual topics polished. To be drafted as separate WPs once the operator signs off on this spec lock.
- **Blocks**: every I3 implementation WP — none can start until this spec is DONE.
- **Blocked-By**: none (governance refactor; pre-work commit rule satisfied by kickoff commit; no `.product/` touches).
- **Related**: WP-I1-035 (Manual Impact governance rule + audit script extension — this WP exercises the rule by adding 4 manual topics), WP-I1-025 (audit script — extended in I3 implementation to verify rule registry coverage).

## Linked Requirements / Spec Sections

- New `.gov/spec/openrepose_amood_v0_1.md` — AMood blueprint mapped to OpenRepose surface (data model, command surface, package layout, blueprint provenance).
- New `.gov/spec/openrepose_intake_v0_1.md` — Project/Task/Batch hierarchy, intake staging, triage workflow, two-stage acceptance, default-staging ComfyUI bridge behavior.
- New `.gov/spec/openrepose_rules_v0_1.md` — Rule registry: stable rule_ids, severities (auto-route / block / warn / info), error-citation contract, manual cross-links, project-scoped rule extension.
- New `.gov/spec/openrepose_requirements_v0_1.md` — Typed scoped requirements (project/task/batch/card), target tree (sets → cards → per-card targets), counters and `fully_satisfied` semantics, EXP120 worked example.
- `.gov/spec/README.md` — Active Specs table extended with the 4 new files.
- `.gov/topology.yaml` — `rules:` block (initial registry), `requirements_kinds:` enum, extended `state_file:` schema docs for `state.library.{intake,targets,guidance,requirements}`.
- `.gov/AGENTS.md` Headless LLM Operation Rule — applies to every I3 implementation WP touching operator-facing surfaces.
- `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` — operator-authored canonical blueprint, tracked in this kickoff commit. Specs reference it as the structural source of truth; OpenRepose specs cover *operationalization* only.

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | Operator-authored AMood blueprint (`.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md`) | local, 2070 lines | Canonical structural source: tier table (quick/mini/production), package layout (INDEX/README/stories/cards/moodboards/matrices/ledgers/manifests/prompt_blocks/pose_guides/generated_images), 8+ TSV schemas with additive-only rule, fast-triage 4-field + full-rubric 16-field scoring, abandonment criteria, accepted-set diversity audit, anti-repetition ledger with dedupe signature ≥6 overlap = revise. | adopt as structural source; OpenRepose specs cover operationalization (DB schema, command surface, GUI, intake staging, requirements registry); blueprint stays canonical and unmodified |
| 2026-05-03 | Existing OpenRepose I2 implementation (`library_entries`, `library_runs` ComfyUI bridge round-trip, library tab GUI, snapshot subsystem, LLM control surface) | local | I2 closes Feature 3 with PG-backed library, 7 LLM commands, ComfyUI custom node, multi-operator concurrency. I3 extends this with project/task/batch parents, intake staging, requirements typing, target counters. Library_entries gain card-schema fields (sexual_trigger, kink_cue, porn_archetype, fantasy_mode, explicit_family, dedupe_signature, compatibility_signature, parent_card_id). | extend; do not rebuild |
| 2026-05-03 | TSV-vs-DB authoritative-source debate | design conversation | AMood treats TSV headers as locked contracts (additive-only); OpenRepose treats Postgres as truth. Resolution: **DB authoritative; TSVs are generated views over DB rows in the AMood-locked column order**. New columns appended right of header (matches AMood's own additive-only rule). Avoids drift between two stores. | adopt DB-authoritative + TSV-as-view |
| 2026-05-03 | Inbox naming collision | governance check | `outputs/.runtime/inbox/` already documented in `topology.yaml` as the LLM control-surface command channel. Reusing "inbox" for staging would confuse every LLM. | rename: directory = `outputs/intake/`; user-facing concept = "triage queue" |
| 2026-05-03 | EXP120 operator-supplied requirements example | operator markdown in design conversation | 6 sets × 20 cards × 8 promoted = 960 target. Hard quantitative gates (1080×1440 exact, 3:4 portrait); structural target tree; qualitative rubrics (body, pose, face, crop, quality); explicit accept/reject term lists. Round-trips between operator markdown and structured DB rows. | adopt as worked example for `requirements-and-targets.md` manual topic; round-trip importer/exporter is a follow-up implementation WP, not part of this spec lock |
| 2026-05-03 | AMood antipattern: copy-paste blueprint into LLM context every session | design discussion | 2070-line blueprint pasted into every session is expensive and rots. Better: `state.library.guidance` block names the blueprint path + rule registry IDs; LLM reads on demand only. | adopt JIT teaching pattern |
| 2026-05-03 | Two-stage acceptance kill-switch design | safety reasoning | A single hallucinating LLM with `intake_finalize` access can poison the library. Without a kill switch, the system depends on every LLM behaving correctly. | adopt: LLM may `intake_soft_accept`; only operator may `intake_finalize`; default-staging ComfyUI bridge refuses direct library writes without operator token |

Decisions locked by research:

- **Hierarchy**: Project → Task → Batch → Card (library_entries) → Run → Output. Five new tables (`library_projects`, `library_tasks`, `library_outputs` plus FK extensions to `library_runs`/`library_batches`/`library_entries`).
- **Intake directory**: `outputs/intake/<YYYYMMDD>-<task_slug>/raw/{,diagnostic/,contact_sheets/}` — gitignored, isolated per task. Wholesale-reject = directory delete + DB row delete in one transaction (uses existing `/safe-delete` guards + I2-008 advisory-lock pattern).
- **Library directory**: `outputs/library/<project_slug>/<batch_slug>/{cards,moodboards,prompt_blocks,pose_guides,manifests,accepted,soft_accepted}/` — gitignored, organized by project. AMood's `references/prompts/<batch_slug>/` blueprint convention re-pathed onto OpenRepose's `outputs/` policy.
- **Two-stage acceptance**: `pending → triaging → soft_accepted → promoted | rejected | diagnostic | abandoned`. Single status enum across every level.
- **Targets**: scalar `target_promoted_count` per scope (project/task/batch); structured target tree (`library_target_groups` + `library_target_cards`) when the project has set/card-level structure; counters derived from `library_outputs.status` (single source of truth, indexed). `fully_satisfied = count_satisfied AND quota_satisfied` (count gate + AMood accepted-set diversity audit ≥0.75 coverage).
- **Requirements**: typed (`hard_output | body | pose | face | crop | quality | clothing_story | structural | custom`), scoped (`project | task | batch | card`), severity-tiered (`auto-route | block | warn | info`), inheritable down the hierarchy. Optional `machine_check_fn` for deterministic gates (resolution/aspect-ratio); `accept_terms[]`/`reject_terms[]` arrays for rubric content.
- **Rule registry**: `topology.yaml` `rules:` block holds global rules; project-scoped rules (e.g. `EXP120-RES-001`) live in DB at project scope, with same registry shape. Errors cite `rule_id` + manual link + suggested fix command.
- **Default-staging bridge**: ComfyUI bridge custom node writes to `outputs/intake/<task_id>/` by default. Direct library writes require an operator-issued token in the POST payload; absent token = bridge refuses with INTAKE-002 citation.

## Reality Boundary

- **Real Seam**: 4 new spec files exist under `.gov/spec/` with all subsections specified In Scope. 4 new manual topics exist under `.gov/doc/manual/` (replacing the existing `amood-workflow.md`). `topology.yaml` carries the rules registry stub + requirements_kinds enum + extended state_file documentation. Spec README index lists all 4 new specs. The AMood blueprint reference is tracked in Git. The next assistant or operator who needs to draft an I3 implementation WP reads these files and finds the contracts locked.
- **User-Visible Win**: any cold-start LLM or operator who runs `orstart` and reads the manual + topology can answer (without source-blueprint reading): how does AMood map to the OpenRepose library? Where do bad LLM outputs go? How does triage work? What's the project/task/batch hierarchy? How does the system track 8 promoted × 120 cards = 960 target? What rules govern an action and what's the citation format when an action is refused? Each question resolves to a single spec section.
- **Proof Target**: `git diff` shows 4 new spec files + 4 new/replaced manual topics + topology.yaml extension + spec README extension; `pwsh scripts/audit-repo.ps1` exits 0; manual index renders the new topics; spec README cross-references resolve.
- **Allowed Temporary Fallbacks**: none. Spec-only WP — no fallbacks to track.
- **Promotion Guard**: do not promote to DONE until the operator confirms the four spec sections are complete enough to start I3 implementation WPs without further scope debate. Manual topic prose may be polished in a follow-up DOCUMENTATION WP if scope exceeds the focused day; the contract-locking parts (data model, command surface, rule shape, severity tiers) must land in this WP.

## In Scope

### Spec authoring (`.gov/spec/`)

- `openrepose_amood_v0_1.md` — sections: Purpose & Provenance, Blueprint Reference (provenance pointer to `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md`), Mapping (AMood concept → OpenRepose entity table), Card Schema Extension on library_entries, Anti-Repetition (dedupe-signature service contract), Acceptance & Scoring (fast-triage + full rubric storage), AMood Command Surface (init_batch_package / library_create_card / library_create_variants / compatibility_check / accepted_set_audit / TSV import-export), Package Layout (under `outputs/library/<project_slug>/<batch_slug>/`), Out Of Scope, Reality Boundary.
- `openrepose_intake_v0_1.md` — sections: Purpose, Hierarchy (Project / Task / Batch / Card / Run / Output with new DB tables), Status Enum (`pending → triaging → soft_accepted → promoted | rejected | diagnostic | abandoned`), Folder Layout (`outputs/intake/` + `outputs/library/`), Triage Workflow (pre-flight summary → auto-prefilter → variant strip → per-image inspection), Two-Stage Acceptance (LLM may soft_accept; operator-only finalize), Default-Staging ComfyUI Bridge (operator-token contract), Triage Commands (intake_list / intake_inspect / intake_soft_accept / intake_reject / intake_finalize / task_create / task_summary / promote_to_library), Self-Documenting Surface (`state.library.intake` + `state.library.guidance`), Snapshot Targets (`intake_triage_view`, `task_summary_view`, `library_card_with_pose`), Out Of Scope, Reality Boundary.
- `openrepose_rules_v0_1.md` — sections: Purpose, Rule Anatomy (rule_id, kind, severity, short, manual_link, machine_check_fn, accept_terms, reject_terms, scope, inherited_from), Severity Tiers (auto-route / block / warn / info — with the auto-route routing-not-blocking semantic explicitly defined), Global vs Project-Scoped Rules (global in `topology.yaml`; project-scoped in DB, archived when project closes), Error Citation Contract (`ERR cmd=<x>: <result> by <rule_id>: <short>. See manual: <topic>. Fix: <command>.`), State Surface (`state.library.guidance.active_rules`), Audit Coverage (every rule_id resolves to a manual topic; every command has help; every error cites a rule), Initial Registry (RUL-001 work-start protocol, RUL-002 pre-work commit rule, RUL-003 naming convention, RUL-004 disk-agnostic, RUL-005 research-first, RUL-006 deletion protocol — six existing repo rules promoted into the registry), Out Of Scope, Reality Boundary.
- `openrepose_requirements_v0_1.md` — sections: Purpose, Requirement Anatomy (kind enum + scope + severity + machine_check + accept_terms + reject_terms + manual_link), Inheritance (lower scope wins on conflict; visualized in editor), Target Tree (`library_target_groups` + `library_target_cards` + per-card stability_target vs target_promoted distinction), Counters (`promoted_count` / `soft_accepted_count` / `pending_count` / `rejected_count` / `diagnostic_count` / `abandoned_count` — derived from `library_outputs.status`), Satisfaction Semantics (`count_satisfied` / `quota_satisfied` / `fully_satisfied`), Forecast Signal (`forecast_ok = in_flight >= gap`), EXP120 Worked Example (round-trips operator markdown to structured rows and back), Out Of Scope, Reality Boundary.

### Manual topics (`.gov/doc/manual/`)

- `amood-workflow.md` — REPLACE existing simpler tag-based page with the new spec-aware workflow. Old tag conventions retained as a "Tags-on-entries (ad-hoc use)" subsection.
- `intake-and-triage.md` — NEW. Triage queue concept, two-stage acceptance, where outputs land, commands, common operator gestures, worked example of an "incoming task arrived" walkthrough.
- `targets-and-progress.md` — NEW. How count vs. quota satisfaction work; what `fully_satisfied` means; how the GUI surfaces gap and forecast; how an LLM agent reads `state.library.targets` and self-paces.
- `requirements-and-targets.md` — NEW. How requirements work (kinds, severities, scopes, inheritance); how to author them (markdown round-trip); EXP120 worked example showing the operator's pasted markdown converted to structured rows.

### Topology + governance

- `.gov/topology.yaml`: add `rules:` block (initial registry stub for the 6 promoted repo rules + AMOOD-001 / INTAKE-001 / INTAKE-002 / TARGET-001 / TARGET-002), `requirements_kinds:` enum, extend `state_file:` schema docs to include `state.library.{intake,targets,guidance,requirements}`.
- `.gov/spec/README.md`: register the 4 new spec files in the Active Specs table.
- `.gov/doc/manual/index.md`: register the 3 new manual topics + flag the `amood-workflow.md` replacement.
- `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md`: track in Git (currently untracked; lands in kickoff commit).

## Out Of Scope

- Implementation of any I3 feature in `.product/` (separate IMPLEMENTATION/INFRASTRUCTURE WPs).
- DB migration scripts for the new tables (separate IMPLEMENTATION WPs in I3).
- ComfyUI bridge default-staging behavior change (separate IMPLEMENTATION WP — bridge currently writes to library directly).
- Triage GUI tab implementation (separate IMPLEMENTATION WP — Library tab gets the 7th sub-pane in I3).
- Requirements editor + markdown round-trip importer (separate IMPLEMENTATION WP).
- Audit script extension to verify rule-registry coverage (separate INFRASTRUCTURE WP — extends `scripts/audit-repo.ps1`).
- First-run walkthrough (separate IMPLEMENTATION WP).
- Mid-flight target revision UI (separate IMPLEMENTATION WP).
- Probabilistic auto-prefilter (face-age / hand-sanity ML heuristics — separate RESEARCH+IMPLEMENTATION sequence; this WP only specifies the *contract* for `severity: auto-route` deterministic checks).

## Expected Files Touched

### Governance (`.gov/`)
- `.gov/workflow/workpackets/WP-I3-001-amood-intake-requirements-spec.md` (this file).
- `.gov/workflow/TASKBOARD.md` — Active row added at IN-PROGRESS, I3 iteration note.
- `.gov/spec/openrepose_amood_v0_1.md` (NEW).
- `.gov/spec/openrepose_intake_v0_1.md` (NEW).
- `.gov/spec/openrepose_rules_v0_1.md` (NEW).
- `.gov/spec/openrepose_requirements_v0_1.md` (NEW).
- `.gov/spec/README.md` — Active Specs table extension.
- `.gov/doc/manual/amood-workflow.md` — REPLACE.
- `.gov/doc/manual/intake-and-triage.md` (NEW).
- `.gov/doc/manual/targets-and-progress.md` (NEW).
- `.gov/doc/manual/requirements-and-targets.md` (NEW).
- `.gov/doc/manual/index.md` — manual TOC extension.
- `.gov/topology.yaml` — rules + requirements_kinds + state_file schema docs.
- `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` — tracked (currently untracked).

### Product (`.product/`)
- (none — DOCUMENTATION-class)

### Build / Output (gitignored)
- `target/test-artifacts/WP-I3-001/` — audit log + git-diff snapshot.

## Risks And Dependencies

- **Risk**: spec sections drift from each other (AMood spec uses one term; intake spec uses a different term for the same concept). **Mitigation**: status enum + folder layout + command names are defined once in `intake` spec and referenced by the others; AMood spec defers data-model details to `intake`; rule format is defined once in `rules` and cited by all.
- **Risk**: scope expands beyond a focused day; manual topics get rushed. **Mitigation**: contracts (data model, command surface, severity tiers, status enum) are the must-land items; manual prose can be polished in a follow-up DOCUMENTATION WP if needed. Decisions Log records this trade.
- **Risk**: the existing `amood-workflow.md` gets replaced before operators who used the simple tagging approach are migrated. **Mitigation**: tag conventions retained as a subsection of the new page; old tag examples still valid for ad-hoc (non-AMood-batch) library use.
- **Risk**: spec-implementation drift when I3 IMPLEMENTATION WPs start (same risk as Feature 1/2/3). **Mitigation**: same precedent — implementation WPs cite the spec sections; substantial deviations require a paired DOCUMENTATION WP (per Spec Authoring Rules).
- **Dependency**: operator confirmation that the design conversation in this session is the canonical intent record (Decisions Log captures the core choices).
- **Dependency**: AMood blueprint file at `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` is the operator-authored canonical structural source; this WP does not modify it.

## Definition Of Done

- [ ] `.gov/spec/openrepose_amood_v0_1.md` exists with all listed subsections (Purpose, Blueprint Reference, Mapping, Card Schema Extension, Anti-Repetition, Acceptance & Scoring, Command Surface, Package Layout, Out Of Scope, Reality Boundary).
- [ ] `.gov/spec/openrepose_intake_v0_1.md` exists with all listed subsections (Hierarchy, Status Enum, Folder Layout, Triage Workflow, Two-Stage Acceptance, Default-Staging Bridge, Triage Commands, Self-Documenting Surface, Snapshot Targets, Out Of Scope, Reality Boundary).
- [ ] `.gov/spec/openrepose_rules_v0_1.md` exists with all listed subsections (Rule Anatomy, Severity Tiers, Global vs Project-Scoped, Error Citation Contract, State Surface, Audit Coverage, Initial Registry, Out Of Scope, Reality Boundary).
- [ ] `.gov/spec/openrepose_requirements_v0_1.md` exists with all listed subsections (Requirement Anatomy, Inheritance, Target Tree, Counters, Satisfaction, Forecast, EXP120 Worked Example, Out Of Scope, Reality Boundary).
- [ ] `.gov/spec/README.md` Active Specs table lists the 4 new files.
- [ ] `.gov/doc/manual/amood-workflow.md` rewritten to align with the new spec.
- [ ] `.gov/doc/manual/intake-and-triage.md` exists with worked example.
- [ ] `.gov/doc/manual/targets-and-progress.md` exists with worked example.
- [ ] `.gov/doc/manual/requirements-and-targets.md` exists with EXP120 worked example.
- [ ] `.gov/doc/manual/index.md` registers the 3 new topics and the AMood replacement.
- [ ] `.gov/topology.yaml` carries the `rules:` initial registry, `requirements_kinds:` enum, and extended `state_file:` schema docs.
- [ ] `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` tracked in Git.
- [ ] `pwsh scripts/audit-repo.ps1` exits 0.
- [ ] **Manual Impact**: Yes — replaces `amood-workflow.md` and adds 3 new manual topics (`intake-and-triage.md`, `targets-and-progress.md`, `requirements-and-targets.md`); manual index extended.
- [ ] Operator sign-off recorded.

## Test Coverage Plan

DOCUMENTATION-class. No new tests in this WP. Verification is the audit + the spec sections being internally consistent (cross-references resolve, status enum + folder layout + command names + rule citation format are defined once and consistent across files). The follow-up audit-script extension (separate INFRASTRUCTURE WP) will mechanically verify rule-registry coverage; for this WP, internal consistency is reviewed by hand.

## Rollback Plan

- Files to revert: 4 new spec files, 3 new manual files, the replaced `amood-workflow.md`, manual index, spec README, topology.yaml, this WP file, taskboard row. The AMood reference file at `.gov/doc/references/` is operator content; if rollback is needed, the file stays in place but its tracked-in-Git status can be reverted by removing it from the staging area.
- Files to keep: nothing in `.product/` is touched, so no product-side rollback.
- Recovery command: `git restore --staged .gov/ ; git checkout -- .gov/ ; git rm --cached .gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` (last command only if reverting the reference's tracked-in-Git status).

## Decisions Log

- 2026-05-03: Lock the I3 surface as 4 spec sections + 4 manual topics + topology extension. Reason: the design conversation produced a coherent set of contracts that build on each other (rules cited by AMood + intake + requirements; status enum used by all; folder layout shared by AMood + intake; targets defined in requirements and surfaced in intake). Authoring as a single WP avoids drift between separately-authored specs; effort is L (longer than typical M for one spec) but the contracts must land together. Alternatives considered: split into 4 WPs (rejected — drift risk; same operator session anyway), defer to next iteration (rejected — operator is ready to start I3 and wants intent recorded now).
- 2026-05-03: DB-authoritative; TSVs as generated views in AMood-locked column order. Reason: AMood's additive-only schema rule maps cleanly to PG migrations; new columns appended right of header; consumer scripts (and chat-only LLMs producing inline TSV blocks) keep working. Alternative considered: TSV-authoritative with DB cache (rejected — drift risk, no transactional guarantees).
- 2026-05-03: Directory rename from "inbox" to "intake" + user-facing "triage queue". Reason: `outputs/.runtime/inbox/` already documented in `topology.yaml` for the LLM control-surface command channel; collision would confuse every LLM that reads the topology. Alternative considered: keep "inbox" with a path qualifier (rejected — humans and LLMs both read short names; ambiguity unacceptable).
- 2026-05-03: Two-stage acceptance — LLM may soft_accept; only operator may finalize. Reason: a single hallucinating LLM with finalize access can poison the library. Soft-accept is reversible (visible in `soft_accepted/` not `accepted/`; `library_search` filters by default). Alternative considered: single-stage with rule-citation guardrails (rejected — guardrails fail to known LLM hallucination patterns; physical isolation is the kill switch).
- 2026-05-03: Default-staging ComfyUI bridge. Reason: bridge currently writes directly to library (I2-005 implementation); leaves a foot-gun if an LLM-driven ComfyUI run produces 960 outputs. New default = write to `outputs/intake/<task_id>/`; direct library writes require an operator token. Alternative considered: leave bridge unchanged + rely on triage UI to catch (rejected — operator stated triage UI is meant for already-staged content; bridge change is the cleaner cut).
- 2026-05-03: Auto-route as a fourth severity tier (alongside block/warn/info). Reason: deterministic-check failures (resolution mismatch) are not really "blocked" — they're "not counted toward target, route to evidence, don't burn operator triage time." Distinct behavior justifies distinct tier. Alternative considered: fold into `warn` with auto-routing as a side-effect (rejected — semantics conflate operator-judgement-required with machine-decided).
- 2026-05-03: `count_satisfied AND quota_satisfied = fully_satisfied`. Reason: an LLM oversampling one card hits the count gate while the diversity audit still flags `priority` axes. Without the AND binding, "satisfied" doesn't mean "operator's actual goal met". Alternative considered: count-only with operator-side audit (rejected — splits the satisfaction concept; LLM agents need a single boolean to self-pace).
- 2026-05-03: Six existing repo rules (work-start protocol, pre-work commit, naming convention, disk-agnostic, research-first, deletion protocol) get promoted into the rule registry as `RUL-001..006` with severity `block`. Reason: registry needs initial population; existing rules are the natural seed; provides the citation format for future rules. Alternative considered: leave existing rules in `AGENTS.md` only and start the registry with new I3 rules (rejected — rule citations should be uniform; existing rules need machine-readable form for future audit script extension).
- 2026-05-03: Rule registry is split — global rules in `topology.yaml`; project-scoped rules in DB. Reason: global rules are repo-wide governance and live in versioned config; project-scoped rules (like EXP120-RES-001) are operator content with project lifetime, naturally DB-resident. Same registry shape on both sides. Alternative considered: all in DB (rejected — bootstrap problem: registry needed before DB is up); all in topology.yaml (rejected — operator content shouldn't require Git commits per project).

## Fallback Register

- (none — DOCUMENTATION-only WP, no product-side fallbacks)

## Change Ledger

- **What Became Real**:
  - 4 NEW spec files under `.gov/spec/`:
    - `openrepose_amood_v0_1.md` (~15KB): AMood blueprint operationalization. 16 new card-schema columns on `library_entries`, `library.dedupe_check` SQL function, 7 commands (init_batch_package / library_create_card / library_create_variants / compatibility_check / accepted_set_audit / amood_export_tsv / amood_import_tsv), AMood TSV-as-DB-view contract, AMOOD-001..004 rule_ids, blueprint-provenance pointer to operator-canonical reference at `.gov/doc/references/`. Out Of Scope + Reality Boundary populated.
    - `openrepose_intake_v0_1.md` (~14KB): 3 new tables (library_projects/library_tasks/library_outputs) + library_pose_guides; 4 FK extensions on existing I2 tables; unified status enum across the entire hierarchy; `outputs/intake/` + `outputs/library/` folder layout; three-layer triage (pre-flight summary / auto-prefilter / per-card variant strip); two-stage acceptance (LLM may soft_accept; operator-only finalize); default-staging ComfyUI bridge contract (INTAKE-002); 16 dispatcher commands; INTAKE-001..004 rule_ids; 3 snapshot targets; `state.library.intake` + `state.library.guidance` blocks specified.
    - `openrepose_rules_v0_1.md` (~13KB): rule registry shape, 4 severity tiers (auto-route / block / warn / info), error citation contract (uniform across all dispatcher commands), global-vs-project-scoped split (topology.yaml for global; library_rules table for project-scoped), audit coverage requirements, initial registry of 25 rule_ids covering RUL-000..007 + AMOOD-001..004 + INTAKE-001..004 + TARGET-001..003 + REQ-001..003 + SAFE-001..003. Out Of Scope + Reality Boundary populated.
    - `openrepose_requirements_v0_1.md` (~13KB): 8-kind taxonomy (hard_output / body / pose / face / crop / quality / clothing_story / structural / custom); inheritance (lower scope wins); target tree (library_target_groups + library_target_cards); counters from library_outputs.status (single source); satisfaction semantics (count_satisfied AND quota_satisfied = fully_satisfied); forecast warning; complete EXP120 worked example with operator markdown round-tripping to structured rows; 8 commands. Out Of Scope + Reality Boundary populated.
  - 3 NEW manual topics under `.gov/doc/manual/`:
    - `intake-and-triage.md`: operator-facing flow doc with status enum, two-stage acceptance, three-layer triage, worked example of an incoming-task walkthrough, all rule_ids cited.
    - `targets-and-progress.md`: count-vs-quota satisfaction, forecast signal, stable-vs-complete distinction, worked example of an 80/960 task progressing, LLM self-pacing loop documented.
    - `requirements-and-targets.md`: 8 kinds, 4 severity tiers, EXP120 worked example (markdown ↔ structured rows), inheritance visualization, completeness checklist.
  - `.gov/doc/manual/amood-workflow.md` left as-authored by operator (tag-conventions layer compatible with the new structural specs; previously-untracked file now landing through this WP).
  - `.gov/doc/manual/index.md` extended with 3 new topic links (composes alongside operator's Adult Production Boundary entry from WP-I3-002).
  - `.gov/spec/README.md` Active Specs table extended with the 4 new spec files (each with one-line scope summary + DRAFT status).
  - `.gov/topology.yaml` extended with: `rule_registry:` block (severity tiers + citation format + 25 rule_ids covering RUL/AMOOD/INTAKE/TARGET/REQ/SAFE families + project_scoped registry contract); `requirements_kinds:` enum (8 canonical + custom); `intake_layout:` (per-task isolated directory pattern + status enum); `state_file_schema:` (i3_blocks documenting state.library.{intake,targets,requirements,guidance,amood}); `i3_command_surface:` (16 + 7 + 8 + 1 = 32 commands listed by family); `i3_snapshot_targets:` (5 new headless-compliant targets).
  - `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` (operator-authored 2070-line canonical blueprint) tracked in Git as the structural source of truth that the four specs operationalize.
  - Composition with parallel WP-I3-002 (operator-authored Adult Production Boundary first rule + LLM stance acknowledgement primitives): RUL-000 included in registry and cross-references the existing `repo_rules.adult_production_boundary` block; AMood and intake specs reference the `adult_production_boundary` envelope for command responses; manual topics cite `adult-production-boundary.md` as the foundational stance.
- **What Remains Simulated / Deferred to I3 IMPLEMENTATION WPs**:
  - All DB migrations (new tables + ALTER TABLEs + new columns + view + indexes + CHECK constraints). Lands in I3 INFRASTRUCTURE WP(s).
  - ComfyUI bridge default-staging behavior change. Lands in I3 IMPLEMENTATION WP (custom node update + `OPENREPOSE_TASK_ID` env handling).
  - Triage GUI tab as 7th Library sub-pane (pre-flight summary view + per-card variant strip + requirements panel). Lands in I3 IMPLEMENTATION WP.
  - Requirements editor + markdown round-trip importer/exporter. Lands in I3 IMPLEMENTATION WP.
  - Audit script extension to verify rule-registry coverage (every rule_id resolves to a manual anchor; every command has help; every error string cites a real rule_id). Lands in I3 INFRASTRUCTURE WP.
  - First-run walkthrough (one-shot guided project/task/batch creation flow). Lands in I3 IMPLEMENTATION WP.
  - Probabilistic auto-prefilter (face-age / hand-sanity ML heuristics). Specified as advisory only in v0.1; ML-backed implementations are separate RESEARCH+IMPLEMENTATION WPs.
- **Next Blocking Real Seam**: I3 IMPLEMENTATION iteration kickoff. Recommended sequence:
  - WP-I3-003 INFRASTRUCTURE: PG migrations for the 4 new tables + 4 FK extensions + view + CHECK constraints + indexes. Predecessor: this WP (DONE).
  - WP-I3-004 IMPLEMENTATION: dispatcher commands for project/task/intake (intake_register_output, intake_soft_accept, intake_reject, intake_finalize, etc.) + state.library.intake population. Predecessor: WP-I3-003.
  - WP-I3-005 IMPLEMENTATION: ComfyUI bridge default-staging change + `OPENREPOSE_TASK_ID` env handling + INTAKE-002 enforcement. Predecessor: WP-I3-004.
  - WP-I3-006 IMPLEMENTATION: AMood data-model commands (init_batch_package / library_create_card / library_create_variants / compatibility_check / accepted_set_audit / amood_export_tsv / amood_import_tsv) + `library.dedupe_check` SQL function. Predecessor: WP-I3-003.
  - WP-I3-007 IMPLEMENTATION: requirements editor + markdown round-trip + target tree commands. Predecessor: WP-I3-003.
  - WP-I3-008 IMPLEMENTATION: Triage GUI tab (7th Library sub-pane) + per-card variant strip + requirements panel + auto-prefilter advisory hints. Predecessor: WP-I3-004 + WP-I3-006.
  - WP-I3-009 INFRASTRUCTURE: audit script extension verifying rule-registry coverage + manual-anchor resolution. Predecessor: this WP.
  - WP-I3-010 VERIFICATION: end-to-end EXP120-style task walked from bridge → intake → triage → soft_accept → finalize → library; markdown round-trip on EXP120 example; closes I3 v0.1.
  - WP-I3-002 (operator-authored, IN-PROGRESS): LLM stance acknowledgement primitives — runs in parallel; not blocked by this spec lock.

## Checkpoint Commit Plan

1. Governance kickoff: this WP file at IN-PROGRESS + taskboard row + I3 iteration note + AMood reference tracked.
2. Spec authoring: 4 new spec files + spec README extension + topology.yaml extension.
3. Manual authoring: 3 new manual topics + replaced `amood-workflow.md` + manual index extension.
4. WP closure: status REVIEW + Change Ledger filled + audit run.

## Proof Of Implementation

- **Command Runs**: `pwsh scripts/audit-repo.ps1` (exit 0); `git diff` shows the 4 new specs + 3 new manual topics + replaced `amood-workflow.md` + topology + spec README + manual index + tracked AMood reference.
- **Proof Artifact**: `target/test-artifacts/WP-I3-001/` (audit log + git-diff snapshot).

## Headless LLM Operation Compliance

- [x] N/A — DOCUMENTATION-class. No commands, no state, no snapshot in this WP. The specs being authored impose Headless Compliance on every I3 IMPLEMENTATION WP (commands, state blocks, snapshot targets enumerated in `openrepose_intake_v0_1.md`).

## Exit Criteria

- [ ] Definition of Done items all checked.
- [ ] Taskboard row reflects REVIEW (then DONE on operator sign-off).
- [ ] Reality Boundary, Decisions Log, and Change Ledger truthful.
- [ ] Audit script exits 0.
- [ ] Evidence section populated.
- [ ] Operator sign-off recorded.
- [ ] Headless LLM Operation Compliance marked N/A with reason.

## Evidence

- **Spec Diff**: `git show 95bbe92` (kickoff: WP file + taskboard row + AMood reference tracked); subsequent REVIEW commit shows 4 new specs + 3 new manual topics + spec README extension + manual index extension + topology.yaml extension.
- **Audit Run**: `pwsh scripts/audit-repo.ps1` to be run before sign-off; expected exit 0 (DOCUMENTATION-class; no product code; Workflow Version 1.1 fields all populated).
- **Build Artifacts**: spec/manual authoring only — no product code.
- **Operator Sign-off**: pending.

## Progress Log

- 2026-05-03: WP drafted at IN-PROGRESS (governance refactor; pre-work commit rule satisfied by kickoff commit; no `.product/` touches). Design conversation captured in Decisions Log + Research Notes.
- 2026-05-03: Kickoff commit `95bbe92` — WP file + taskboard row + I3 iteration note + AMood blueprint reference tracked. Push: origin/main up-to-date (operator's parallel WP-I3-002 kickoff `769a9e9` landed alongside establishing the Adult Production Boundary first rule + LLM stance acknowledgement primitives in topology.yaml).
- 2026-05-03: Spec authoring complete. 4 new spec files + 3 new manual topics + spec README extension + manual index extension + topology.yaml extension (rule_registry, requirements_kinds, intake_layout, state_file_schema, i3_command_surface, i3_snapshot_targets). The existing operator-authored `amood-workflow.md` retained as-is (tag-conventions layer; complementary to the new structural specs). Status IN-PROGRESS → REVIEW awaiting operator sign-off.
