# Handoff Note — 2026-05-03 — I3 Implementation Phase 2 (Sweep B)

Hello. You are the next assistant on OpenRepose. The operator is starting your session to execute **Sweep B**: WP-I3-007 (requirements editor + target tree) and WP-I3-009 (audit script extension). Both predecessors are DONE; both can be drafted to READY → IN-PROGRESS without waiting on anything else.

This note tells you the part `.\orstart` cannot. Read `orstart` output first, then come back here.

## What just landed before you arrived

**Sweep A — 12 WPs signed off DONE in one operator-granted batch on 2026-05-03.** All listed below are archived under `.gov/workflow/archive/`:

```text
WP-I1-034   calibration overview mode + drag/delete + add-marker
WP-I1-035   in-app manual + manual-impact governance rule
WP-I2-001   PostgreSQL setup + migration runner
WP-I2-002   settings extension (library config; schema 1->2)
WP-I2-003   library_entries CRUD + tags + smart-tag extractor
WP-I2-004   library LLM commands + library_search
WP-I2-005   ComfyUI bridge custom node
WP-I2-006   Library tab GUI
WP-I2-007   library snapshot targets
WP-I2-008   library multi-operator tests + setup doc          [closes I2]
WP-I3-002   LLM stance acknowledgement primitives
WP-I3-006   AMood data-model commands + dedupe service
```

**I2 iteration is CLOSED.** Feature 3 (OpenPose Library + ComfyUI bridge + PostgreSQL) is fully shipped.

**I3 status**: 5 of 10 planned WPs are DONE (WP-I3-001/002/003/004/005/006). Remaining: WP-I3-007 + WP-I3-008 + WP-I3-009 + WP-I3-010.

## Read these in this exact order

1. `.\orstart` (or `.\orstart -Brief`).
2. `.gov/AGENTS.md` — start with the **Adult Production Boundary** rule. Operator owns legal/consent; assistants do not gatekeep. Repo language stays raw, direct, technical.
3. `.gov/CODEX.md` — compact codex.
4. `.gov/topology.yaml` — pay attention to `rule_registry:`, `requirements_kinds:`, `intake_layout:`, `state_file_schema:`, `i3_command_surface:`, `i3_snapshot_targets:`.
5. **The two specs WP-I3-007 implements against:**
   - `.gov/spec/openrepose_requirements_v0_1.md` — primary spec for WP-I3-007. Locks the 8-kind taxonomy, target tree, counters, `fully_satisfied = count_satisfied AND quota_satisfied`, EXP120 worked example, markdown round-trip.
   - `.gov/spec/openrepose_rules_v0_1.md` — error citation contract; severity tiers; project-scoped rules in `library_rules` table.
6. **The original I3 implementation handoff** at `.gov/doc/handoff-2026-05-03-i3-implementation.md` — describes the 8-WP sequence WP-I3-003..010. Sweep A closed -003/-004/-005/-006; you are picking up at -007 + -009 (both have no remaining predecessors).
7. The manual topics under `.gov/doc/manual/`: `intake-and-triage.md`, `requirements-and-targets.md`, `targets-and-progress.md`, `amood-workflow.md`.

You do **not** need to re-read the operator-canonical AMood blueprint at `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` for Sweep B work. It is referenced by WP-I3-007 only insofar as the AMood diversity-audit rule (`AMOOD-001` threshold) interacts with `fully_satisfied`.

## What Sweep B does

Two parallel WPs. Pick one at a time, ship to REVIEW, then start the other. Both are predecessor-clean (WP-I3-003 DONE; WP-I3-001 DONE).

### WP-I3-007 — Requirements editor + target tree commands (IMPLEMENTATION, L)

**Goal:** an LLM agent can drop a markdown file describing the EXP120 quota plan, see DB rows materialized, render it back to markdown, and round-trip without loss.

**Spec:** `.gov/spec/openrepose_requirements_v0_1.md` is the contract. The EXP120 worked example in that spec is your test case for round-trip parsing.

**Commands to add (8 dispatcher handlers):**

```text
project_set_target_tree     create/replace library_target_groups + library_target_cards from input
project_add_requirement     append a typed scoped requirement (8 kinds + custom)
project_set_requirement     update an existing requirement
project_dump_requirements   read all project-scoped + global rules
project_render_markdown     emit the canonical markdown form (round-trip stable)
project_import_markdown     parse markdown into DB rows; lossless round-trip
target_summary              counters by group + card; fully_satisfied flag
target_recount              force a recount from library_outputs.status
```

**State block:** `state.library.targets` (tree-shaped) reflecting the active target tree.

**Tables already present** (built by WP-I3-003 migration 004):

```text
library_target_groups       id, project_id, group_slug, group_name,
                            expected_card_count, target_per_card, ordering
library_target_cards        id, group_id, card_slug, card_id (FK to library_entries),
                            target_promoted, stability_target
library_target_card_counts  VIEW: per-status counters from library_outputs
library_rules               id, scope_type, scope_id, rule_id, name, severity,
                            kind, machine_check_fn, manual, short, ...
```

**Predecessor:** WP-I3-003 (DONE). No other gates.

**Successor unblocked:** WP-I3-008 (Triage GUI tab) and WP-I3-010 (end-to-end EXP120 verification).

**Effort:** L. Markdown round-trip is the riskiest piece — write a structural test that round-trips the EXP120 example bytewise before claiming done.

### WP-I3-009 — Audit script extension (INFRASTRUCTURE, M)

**Goal:** `pwsh scripts/audit-repo.ps1` gains four new checks, all derived from the rule-registry contract:

```text
1. rule-id-resolves-manual          every rule_id in topology.yaml `rule_registry:`
                                    resolves to an existing manual anchor
                                    (.gov/doc/manual/<file>#anchor).
2. citations-cite-real-rule-ids     every error-string in product code that
                                    matches the citation regex
                                    (`ERR cmd=...: ... by <RULE_ID> ...`)
                                    cites a rule_id that exists in topology.yaml.
3. dispatcher-commands-have-help    every command in `_HANDLERS` in commands.py
                                    appears in `topology.yaml i3_command_surface:`
                                    OR is from an earlier iteration's spec.
4. project-rules-fresh              project-scoped rules in library_rules with
                                    last_validated_at older than 30 days surface
                                    as warn (not error). v0.1 ships the warning;
                                    operator-side validation cadence comes later.
```

**Predecessor:** WP-I3-001 (DONE). No code changes outside `scripts/audit-repo.ps1` and the audit-test file (if you add one).

**Spec:** `.gov/spec/openrepose_rules_v0_1.md` — citation contract.

**Effort:** M. PowerShell-side string-matching against the topology yaml is the bulk of the work. The four checks should each emit one OK/FAIL line so `audit-repo.ps1` output stays scannable.

## What is currently true (don't relitigate)

- **Schema_version is 5** after migration 005 (WP-I3-006). Tests assert `5`. Don't accidentally bump to 6 unless you ship a new migration.
- **`library/amood/` subpackage exists** with 8 modules. WP-I3-007 should not touch it; the requirements editor lives at `library/requirements/` (you create that subpackage) or directly in `commands.py` + a small `library/targets.py` module.
- **`library/citations.py` has 25 rule_ids** (RUL-000..007 + AMOOD-001..004 + INTAKE-001..004 + TARGET-001..003 + REQ-001..003 + SAFE-001..003). WP-I3-009 audit assertions read from this same registry.
- **`library/intake/projects.py` + `tasks.py` + `outputs.py`** exist (WP-I3-004). WP-I3-007 doesn't replace them; it adds the target-tree layer on top.
- **`state.library.intake` + `state.library.guidance` + `state.library.amood`** exist on `AppState`. WP-I3-007 adds `state.library.targets`. Mirror the pattern of `set_intake_state` / `set_active_amood_batch` mutators.
- **`adult_production_boundary` envelope** is on every command response (WP-I3-002). New WP-I3-007 commands inherit this automatically via `CommandResult.to_dict()`.
- **`OpenReposeIntakeError`, `OpenReposeAmoodError`** are the citation-carrying error classes. Add `OpenReposeRequirementsError(OpenReposeLibraryError)` with the same shape for WP-I3-007.

## The WP sequence (copy this for each Sweep B WP)

```text
1. Read the spec sections the WP cites.
2. Run a Research-First pass; populate the `## Research Notes` table.
3. Author WP file at `.gov/workflow/workpackets/WP-I3-NNN-<slug>.md` from
   `.gov/templates/WP_TEMPLATE.md`. Status starts at IN-PROGRESS for these.
4. Add taskboard "Active" row.
5. **Kickoff commit and push.** Stage WP file + taskboard row by name
   (do not use `git add -A`). Message: `WP-I3-NNN: kickoff — <one-liner>`.
   Push must succeed before any product file is opened.
6. Implement under `.product/` (or `scripts/` for WP-I3-009).
7. `pytest`. Save junit XML to `target/test-artifacts/WP-I3-NNN/`.
8. `pwsh scripts/audit-repo.ps1` — must exit 0.
9. Move WP to REVIEW. Update Change Ledger + Evidence sections truthfully.
   Move taskboard row from Active to Pending Review. Commit + push.
10. Hand off to operator for sign-off.
```

## Repo state on handoff

```text
branch: main, clean, in sync with origin/main
HEAD at handoff: <will be the Sweep A close-out commit>

Active iterations: I1 (winding down), I3 (Sweep B opens here)
I0 + I2: CLOSED.

REVIEW pile: empty.
Active: empty.
DRAFT: 19 (18 I1 backlog + WP-I3-011).

Tests: 583/583 passing as of WP-I3-006 + the schema-bump catch-up.
Audit: clean (4 checks).
```

## A short list of things that will trip you up

- **Markdown round-trip is the EXP120 acceptance gate.** Lossy parsing here is unacceptable; `project_export_markdown` -> `project_import_markdown` -> `project_export_markdown` must be byte-equal modulo trailing newline. Write that test first.
- **`fully_satisfied` is dual.** `count_satisfied` (`promoted_count >= target_promoted`) AND `quota_satisfied` (AMood diversity audit `realized_coverage >= 0.75` for every relevant axis). An LLM can't oversample one card and declare done.
- **CHECK constraints in migration 004** already enforce `expected_card_count > 0` and `target_per_card > 0` on `library_target_groups`. Catch the `psycopg.errors.CheckViolation` in command handlers and re-emit the canonical citation shape.
- **`library_rules.kind` enum** has 9 values: hard_output, body, pose, face, crop, quality, clothing_story, structural, custom. Use `library/citations.py`-style mirror dict if the audit script needs it; otherwise enum-validate at the command layer.
- **`library_target_card_counts` view** is the only sanctioned way to derive counters. Don't compute counts client-side from `library_outputs.status`; the view aggregates correctly across all 7 status values and was cross-tested in WP-I3-003.
- **CRLF/LF warnings on `git diff`** are normal on this Windows-host repo. Ignore them.
- **Don't introduce a new migration unless schema changes are required.** WP-I3-007 should not need one (existing schema is sufficient); WP-I3-009 definitely should not (it's audit-script only).

## What WP-I3-008 + WP-I3-010 will need next session

- **WP-I3-008** (Triage GUI tab) needs WP-I3-006 + WP-I3-007 DONE; reads `state.library.amood` + `state.library.targets`. Adds 3 snapshot targets: `intake_triage_view`, `task_summary_view`, `library_card_with_pose`. Headless-compliance verification before REVIEW.
- **WP-I3-010** (end-to-end EXP120 verification) closes I3 v0.1. Predecessors: every prior I3 WP. Single integration test that walks: project_create -> project_import_markdown(EXP120) -> task_create -> bridge dropping >=50 outputs -> auto-prefilter routes wrong-resolution -> triage queue -> soft_accept -> operator finalize -> counters update -> accepted_set_audit produces correct realized-coverage -> wholesale-reject of a separate task verifies transactional rollback.

After Sweep B, you'll have one more session to ship -008 + -010, and I3 v0.1 closes.

Good luck. The contracts are locked; the schema is in place; the dispatcher pattern is well-trodden. WP-I3-007's markdown round-trip is the only meaningful design call left.
