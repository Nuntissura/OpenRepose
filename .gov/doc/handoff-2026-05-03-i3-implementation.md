# Handoff Note — 2026-05-03 — I3 Implementation

Hello. You are the next assistant on OpenRepose. The operator is starting your session to implement the I3 iteration: AMood + Intake + Requirements. This note is the part `.\orstart` cannot tell you. Read `orstart` output first, then come back here.

## What just landed before you arrived

Two spec-lock workpackets shipped today (2026-05-03) and are now DONE:

- **WP-I3-001 (DOCUMENTATION, L)** — locks four spec contracts and three new manual topics for the I3 iteration. Operator approved.
- **WP-I3-002 (IMPLEMENTATION, S)** — operator-authored. Establishes the **Adult Production Boundary** as the first repo rule and exposes `adult_production_boundary` acknowledgement primitives in `state.json`, `dump_state`, command envelopes, HTTP responses, and inbox processed results. 24 tests. Operator approved.

The I3 iteration is now unblocked. Implementation WPs land against locked contracts; do not relitigate them.

## Read these in this exact order

1. `.\orstart` (or `.\orstart -Brief`).
2. `.gov/AGENTS.md` — start with the **Adult Production Boundary** rule at the top. Repo + product + LLM assistants do not censor adult production language and do not enforce legal/consent paperwork. Operator owns those obligations. Keep your work raw, technical, direct.
3. `.gov/CODEX.md` — compact codex.
4. `.gov/topology.yaml` — pay particular attention to the new `rule_registry:`, `requirements_kinds:`, `intake_layout:`, `state_file_schema:`, `i3_command_surface:`, and `i3_snapshot_targets:` blocks added by WP-I3-001.
5. The four I3 spec files in order:
   - `.gov/spec/openrepose_intake_v0_1.md` — start here. It defines the hierarchy (Project / Task / Batch / Card / Run / Output) and the unified status enum that the other three specs build on.
   - `.gov/spec/openrepose_rules_v0_1.md` — the 4 severity tiers + citation contract. You will cite rules in every error message.
   - `.gov/spec/openrepose_requirements_v0_1.md` — typed scoped requirements + target tree. The EXP120 worked example is your test case for round-trip parsing.
   - `.gov/spec/openrepose_amood_v0_1.md` — AMood blueprint operationalization, sits on top of intake.
6. The four manual topics under `.gov/doc/manual/`: `amood-workflow.md`, `intake-and-triage.md`, `targets-and-progress.md`, `requirements-and-targets.md`.
7. **Operator-canonical AMood blueprint** at `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` (2070 lines). You do **not** modify this. It is the structural source of truth that the four specs operationalize. Read it on demand only — do not paste it into every session.

Predecessor history: WP-I1-033 (DONE) authored the Feature 3 library spec. WP-I2-001..008 (REVIEW awaiting operator sign-off) implemented Feature 3 (PostgreSQL library, ComfyUI bridge, Library tab GUI, snapshot targets, multi-operator soak tests). I3 extends I2 — it does not rebuild it.

## Recommended implementation sequence

Eight WPs against the locked specs, in dependency order. Draft them as you reach each one (do not pre-draft all 8 — let the operator promote one at a time per the work-start protocol).

1. **WP-I3-003 INFRASTRUCTURE — PG migrations.** New tables: `library_projects`, `library_tasks`, `library_outputs`, `library_pose_guides`, `library_target_groups`, `library_target_cards`, `library_rules`, `library_scorecards`, `library_diagnostics`, `library_diversity_audits`. ALTER TABLE on `library_entries` for the 16 AMood card-schema columns. ALTER TABLE on `library_runs` and `library_batches` for FK extensions. Indexes (trigram on `dedupe_signature`, status partials on `library_outputs`). View `library_target_card_counts`. CHECK constraints (promotion requires operator finalize; safety boundaries SAFE-001/002/003). The `library.dedupe_check` SQL function. **Predecessor: WP-I3-001 (DONE).**

2. **WP-I3-004 IMPLEMENTATION — intake + project + task command surface.** Dispatcher commands per `openrepose_intake_v0_1.md`: project_create, project_list, task_create, task_list, task_summary, task_inspect, intake_register_output (bridge entrypoint), intake_list, intake_inspect, intake_soft_accept, intake_reject, intake_finalize (operator-only, token-gated), intake_reroute, promote_to_library, task_reject_wholesale. Wire `state.library.intake` and `state.library.guidance` blocks. CHECK constraint INTAKE-001 fail must produce the exact error citation shape from `openrepose_rules_v0_1.md`. **Predecessor: WP-I3-003.**

3. **WP-I3-005 IMPLEMENTATION — default-staging ComfyUI bridge change.** Update `.product/comfyui-bridge/` custom node to write to `outputs/intake/<task_id>/raw/` by default. Read `OPENREPOSE_TASK_ID` from environment. Refuse direct library writes without operator token (cite `INTAKE-002`). The legacy direct-write path may remain behind `OPENREPOSE_LEGACY_DIRECT_WRITE=1` for one WP cycle, then removed. **Predecessor: WP-I3-004.**

4. **WP-I3-006 IMPLEMENTATION — AMood data-model commands + dedupe service.** init_batch_package, library_create_card, library_create_variants, compatibility_check, accepted_set_audit, amood_export_tsv, amood_import_tsv. Implement TSVs as DB views in AMood-locked column order (additive-only). Wire `state.library.amood` block. **Predecessor: WP-I3-003.**

5. **WP-I3-007 IMPLEMENTATION — requirements editor + target tree commands.** project_set_target_tree, project_add_requirement, project_set_requirement, project_dump_requirements, project_render_markdown, project_import_markdown, target_summary, target_recount. Markdown round-trip importer/exporter test case is the EXP120 worked example in `.gov/spec/openrepose_requirements_v0_1.md` — round-trip must be lossless. Wire `state.library.targets` block (tree-shaped). **Predecessor: WP-I3-003.**

6. **WP-I3-008 IMPLEMENTATION — Triage GUI tab.** Add 7th sub-pane to the Library tab. Pre-flight task summary view, per-card variant strip with paired pose-guide rendering, requirements panel, AMood fast-triage 4 fields + full rubric 16 fields. Snapshot targets `intake_triage_view`, `task_summary_view`, `library_card_with_pose`. Headless-compliance verification checklist before REVIEW. **Predecessors: WP-I3-004 + WP-I3-006.**

7. **WP-I3-009 INFRASTRUCTURE — audit script extension.** Extend `scripts/audit-repo.ps1` to verify: every rule_id in `topology.yaml rule_registry:` resolves to a manual anchor; every dispatcher command has a help string; every error-string-with-citation-shape cites a real rule_id; project-scoped rules in `library_rules` have `last_validated_at` set within 30 days (warn only). **Predecessor: WP-I3-001 (DONE).**

8. **WP-I3-010 VERIFICATION — end-to-end EXP120 walkthrough.** Closes I3 v0.1. End-to-end test: project_create exposure-120 → project_import_markdown with the EXP120 example → task_create with expected_count → ComfyUI bridge dropping ≥50 outputs → auto-prefilter routes wrong-resolution → triage queue exercised through soft_accept → operator finalize → counters update correctly → accepted_set_audit produces correct realized-coverage numbers → wholesale-reject of a separate task verifies transactional rollback. **Predecessor: all prior I3 WPs.**

## What you must NOT relitigate

The design conversation that produced WP-I3-001 was extensive. These decisions are locked. If you think one is wrong, open a new DOCUMENTATION-class WP to revise the spec; do not silently deviate during implementation.

- **DB-authoritative; TSVs as views.** Not the other way around. AMood's additive-only schema rule maps to PG migrations: append columns; never reorder, rename, or delete.
- **Directory naming: `outputs/intake/`, not "inbox".** Inbox already exists for the LLM control-surface command channel.
- **Two-stage acceptance: LLM may soft_accept; only operator may finalize.** This is the kill switch against library poisoning by hallucinating LLMs. Operator-token gate is enforced at the dispatcher AND at the DB level (CHECK constraint).
- **Default-staging ComfyUI bridge.** Direct library writes from the bridge require an operator token. Without one, the bridge writes to intake.
- **`auto-route` is its own severity tier.** Distinct from block/warn/info. Routes deterministic-check failures to evidence buckets without counting toward target.
- **`fully_satisfied = count_satisfied AND quota_satisfied`.** Not just count. An LLM oversampling one card cannot declare done while the AMood diversity audit still flags priority axes.
- **Six existing repo rules promoted to RUL-001..006 + RUL-000 (Adult Production Boundary) + RUL-007 (Manual Impact).** Initial rule registry seeded in `topology.yaml`.
- **Project-scoped rules live in DB; global rules live in `topology.yaml`.** Same shape; commands and GUI see one logical registry.
- **Markdown round-trip is non-optional for the requirements editor.** Operator drops markdown → DB rows → renders back to markdown. Diff before save = trust. EXP120 is the test case.
- **Probabilistic auto-prefilter is advisory only in v0.1.** No ML-backed auto-rejection. Color-coded hints only. ML models are a separate RESEARCH+IMPLEMENTATION sequence later.
- **Card has two completion concepts.** `stable` when promoted >= stability_target (AMood, default 4); `complete` when promoted >= target_promoted (project-set, e.g. 8 for EXP120). Display both.
- **Card-level abandonment, not just seed-level, on safety-boundary triggers.** Per AMood AMOOD-002 + SAFE-001/002/003. DB CHECK enforces.

## The seven repo rules (read AGENTS.md for full bodies)

- **RUL-000 Adult Production Boundary** — repo, product, and LLM assistants do not censor adult production language and do not enforce legal/consent paperwork. The operator owns legal compliance.
- **RUL-001 Work-Start Protocol** — no `.product/` edit without WP at READY/IN-PROGRESS + taskboard row + kickoff push first. Governance refactors confined to `.gov/` are exempt.
- **RUL-002 Pre-Work Commit Rule** — `git add` specific files (never `-A`/`.`) + commit + push BEFORE opening any `.product/` file in the editor.
- **RUL-003 Naming Convention** — no spaces in any committed path. kebab-case for docs/WPs, snake_case for Python.
- **RUL-004 Disk-Agnostic** — no hardcoded absolute paths.
- **RUL-005 Research-First** — research before non-trivial features; record findings with date + source URL + verdict in the WP `## Research Notes` table.
- **RUL-006 Deletion Protocol** — only `/safe-delete` (Claude side) or `scripts/safe-delete.ps1` (operator side). Never manual `rm`/`Remove-Item` on tracked files.
- **RUL-007 Manual Impact** — every IMPLEMENTATION-class WP at Workflow Version 1.1+ has a `Manual Impact:` line in DoD. Yes/No/N/A (bug fix); audit-enforced.

## The proven WP sequence (copy this for every I3 WP)

1. Read the spec sections the WP cites. For I3 implementation that is one or more of `openrepose_intake_v0_1.md`, `openrepose_rules_v0_1.md`, `openrepose_requirements_v0_1.md`, `openrepose_amood_v0_1.md`.
2. **Research-First pass.** Update WP `## Research Notes` table.
3. WP DRAFT → READY. Add taskboard "Active" row.
4. **Kickoff commit and push.** Stage WP file + taskboard row by name (do not use `git add -A`). Message format: `WP-I3-NNN: kickoff — <one-liner>`. Push must succeed before step 5.
5. Move WP to IN-PROGRESS. Implement under `.product/` (or `scripts/`).
6. Run `pytest`. Save junit XML to `target/test-artifacts/WP-I3-NNN/`.
7. Run `pwsh scripts/audit-repo.ps1`. Must exit 0 before push.
8. Move WP to REVIEW. Update Change Ledger + Evidence sections truthfully — even if unflattering. Move taskboard row from Active to Pending Review. Commit + push.
9. Wait for operator sign-off. On approval, move WP to DONE; archive WP file with `git mv` to `.gov/workflow/archive/`; move taskboard row to Recently Done.
10. Operator may reject REVIEW back to IN-PROGRESS with notes. Address; do not delete the unflattering Change Ledger entries.

## State of the tree on handoff

```text
branch: main
HEAD: dd35036 + close-out commit (this handoff + WP-I3-001 archive move)

I3 specs DONE: WP-I3-001 (DOCUMENTATION) + WP-I3-002 (IMPLEMENTATION).

I2 still at REVIEW: WP-I2-001..008. Operator has not yet signed off.
You can implement I3 against the I2 codebase as it stands at REVIEW —
the I2 sequence is functionally complete; sign-off is pending operator
verification, not technical issues.

I1 backlog: 21 drafted WPs, 1 deferred (WP-I1-012), 3 reserved-not-drafted
(WP-I1-019/020/021). Do not pull from these unless the operator explicitly
authorizes; I3 is the operator's stated focus.

Untracked at handoff time: nothing intentional. If `git status` shows
unexpected dirty state on arrival, ask the operator before doing anything.
```

## A short list of things that will trip you up

- **`outputs/.runtime/inbox/` is the LLM command channel.** Do not reuse "inbox" for staging. The new staging directory is `outputs/intake/<task_id>/`.
- **CRLF/LF warnings on `git diff`** are normal on this Windows-host repo. Ignore them; the actual file content is unchanged.
- **`amood-workflow.md` already exists** as a tag-conventions layer (operator-authored). Your I3 implementation work does not replace it. The new manual topics (`intake-and-triage.md`, `targets-and-progress.md`, `requirements-and-targets.md`) provide the structural backbone underneath.
- **The AMood blueprint at `.gov/doc/references/`** is operator-canonical. You do not modify it. If a real production batch exposes a blueprint gap, the assistant amends the OpenRepose spec; the operator decides whether to amend the blueprint Changelog.
- **State.json and command responses include `adult_production_boundary` envelope.** WP-I3-002 wired this — your new commands must include it too. Look at how WP-I3-002 implemented it (commit `4521823`) and follow the pattern.
- **Two pushed commits the operator did not sign off on yet** (WP-I2-001..008). These are technically REVIEW state; the I2 code is on disk and tested but the workflow says you should not declare them DONE until operator says so. You can build on them; just don't archive them.

Good luck. The contracts are locked; you are free to implement.
