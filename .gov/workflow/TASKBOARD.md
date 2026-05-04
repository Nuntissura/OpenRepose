# OpenRepose Taskboard

Last Updated: 2026-05-04 (WP-I1-018 hand detection and WP-I1-037 multi-file workspace implementation advanced to REVIEW with sample-image/library evidence.)

Live status of all OpenRepose workpackets. Update in the same session as any workpacket transition. Rules in `.gov/workflow/README.md`. Template at `.gov/templates/WP_TEMPLATE.md`.

## Summary

- WPs in flight (READY + IN-PROGRESS): 0
- WPs pending review (REVIEW): 8 (WP-I1-003 settings commands + WP-I1-005 drag-and-drop + WP-I1-016 clear workspace; WP-I1-018 hand detection + OpenPose hand output; WP-I1-037 multi-file workspace implementation; WP-I3-009 audit-script extension; WP-I3-010 e2e EXP120 verification; WP-I4-002 orstart codex contract banner)
- WPs done (I3): 8 (WP-I3-001..008; latest sign-off adds WP-I3-007 requirements editor + target tree and WP-I3-008 triage GUI tab + snapshot targets)
- WPs done (I4): 1 (WP-I4-001 intake scale + DB hardening signed off 2026-05-04)
- WPs blocked (BLOCKED): 0
- WPs draft (DRAFT, eligible to promote): 14 (13 I1 backlog + WP-I3-011 future OpenRepose AMood GPT + Claude wrappers)
- WPs deferred (DEFERRED): 1 (WP-I1-012 garment locks)
- WPs done (I0): 4 (WP-I0-001/002/003/004) — I0 CLOSED 2026-05-02
- WPs done (I1): 15 (12 prior + WP-I1-034/035 signed off 2026-05-03 Sweep A + WP-I1-036 multi-file workspace spec signed off 2026-05-04)
- WPs done (I2): 8 (WP-I2-001..008 — Feature 3 OpenPose Library + ComfyUI bridge + PostgreSQL — I2 CLOSED 2026-05-03 Sweep A)
- WPs reserved-not-drafted: 3 (WP-I1-019/020/021 joint-manipulation chain — operator deferred to later)
- Iterations open: I1 (WP-I1-018 + WP-I1-037 REVIEW; polish bundle in REVIEW: WP-I1-003 + 005 + 016; WP-I1-036 spec DONE 2026-05-04), I3 (Sweep B in REVIEW awaiting operator sign-off across 2 WPs: WP-I3-009 + WP-I3-010), I4 (WP-I4-002 REVIEW awaiting operator sign-off; WP-I4-001 DONE 2026-05-04)

## Active

Workpackets currently progressing toward DONE.

| WP-ID | Title | Owner | Status | Class | Effort | Updated |
|-------|-------|-------|--------|-------|--------|---------|

## Pending Review

Implementation claims to be done; awaiting operator verification.

| WP-ID | Title | Owner | Class | Updated | Verify |
|-------|-------|-------|-------|---------|--------|
| WP-I1-003 | Settings persistence (set_settings + clear_settings commands; settings stayed at AppConfigLocation per kickoff-decision reversal) | assistant | IMPLEMENTATION | 2026-05-04 | 12/12 new + 43/43 existing settings-store tests = 55/55 in `target/test-artifacts/WP-I1-003/`; 119/119 polish-bundle + GUI regression; audit clean. |
| WP-I1-016 | Clear workspace command + toolbar button (next to Open) + Edit menu | assistant | IMPLEMENTATION | 2026-05-04 | 11/11 in `target/test-artifacts/WP-I1-016/`; 119/119 polish-bundle + GUI regression; audit clean. |
| WP-I1-005 | Drag-and-drop portrait import (MainWindow + both viewports; multi-file = accept first + WARN rest) | assistant | IMPLEMENTATION | 2026-05-04 | 15/15 in `target/test-artifacts/WP-I1-005/`; 119/119 polish-bundle + GUI regression; audit clean. |
| WP-I1-018 | Hand detection + OpenPose hand output | assistant | IMPLEMENTATION | 2026-05-04 | `compileall` clean; focused hand/multi-file regression 47/47 passing; PostgreSQL library regression 30/30 passing; sample-image evidence under `target/test-artifacts/WP-I1-018-WP-I1-037/` shows 0/21/42 detected hand landmarks and 63-value left/right hand arrays in each export. Full-suite pytest timed out and is recorded as residual validation risk. |
| WP-I1-037 | Multi-file workspace implementation | assistant | IMPLEMENTATION | 2026-05-04 | Sample-image validation opened 3 file slots, switched active file, exported 3 per-file JSON+PNG pairs, and snapshotted all 3 OpenPose viewports; `state_files_count=3`. Topology updated for new commands; `scripts/audit-repo.ps1` clean. |
| WP-I3-009 | Audit script extension (rule registry coverage) | assistant | INFRASTRUCTURE | 2026-05-03 | `pwsh scripts/audit-repo.ps1` clean (8 OK, 1 SKIP) on HEAD; negative test in `target/test-artifacts/WP-I3-009/`. |
| WP-I3-010 | End-to-end EXP120 verification | assistant | VERIFICATION | 2026-05-04 | 3/3 e2e tests passing in 2:47; 29/29 -006/-007 regression after the cards.py wiring fix; audit clean. Evidence in `target/test-artifacts/WP-I3-010/`. **Closes I3 v0.1 on operator sign-off.** |
| WP-I4-002 | Orstart codex contract banner | assistant | INFRASTRUCTURE | 2026-05-04 | `.\orstart -Brief` prints the new codex-as-binding-contract assistant instructions; unrelated manual edits left untouched. |

## Blocked

Cannot proceed until the named blocker resolves.

| WP-ID | Title | Owner | Blocked By | Reason | Updated |
|-------|-------|-------|------------|--------|---------|

_(none)_

## Deferred

Workpackets intentionally held out of the active draft queue.

| WP-ID | Title | Class | Reason |
|-------|-------|-------|--------|
| WP-I1-012 | Garment locks | IMPLEMENTATION | OpenPose has no garment channel; revisit only if a garment-polyline / secondary-ControlNet workflow becomes real. |

## Draft (Will Promote To Ready When Predecessors Close)

Drafted now so dependencies, scope, and contracts are settled. Status moves to READY when the named predecessor reaches DONE.

I0 closed 2026-05-02. The I0-blocking constraint on every I1 WP below is satisfied; individual WPs may now be promoted from DRAFT → READY in priority order. WPs that list a separate predecessor (e.g., `WP-I0-004` alone, `WP-I1-001 + DOCUMENTATION WP`, etc.) still need that named predecessor satisfied before promotion. Headless LLM Operation Compliance is mandatory for every IMPLEMENTATION-class WP touching operator-facing or visual features (see `.gov/AGENTS.md`).

| WP-ID | Title | Class | Effort | Priority | Headless | Predecessor |
|-------|-------|-------|--------|----------|----------|-------------|
| WP-I1-002 | Orbital camera in 3D viewport | IMPLEMENTATION | S | Polish | n/a | WP-I0-004 |
| WP-I1-004 | Extended keyboard shortcuts | IMPLEMENTATION | XS | Polish (parked: operator wants more app-usage time before defining the shortcut set) | n/a | WP-I0-004 |
| WP-I1-006 | GUI theme refinements | IMPLEMENTATION | S | Polish | n/a | WP-I0-004 |
| WP-I1-007 | Pitch / roll rotation extension | IMPLEMENTATION | M | Feature expansion | yes | I0 + DOCUMENTATION WP |
| WP-I1-008 | Alternative landmark detector research | RESEARCH | M | Investigation | n/a | I0 |
| WP-I1-009 | Identity-export profiles | IMPLEMENTATION | M | Feature expansion | yes | I0; ideally WP-I1-001 |
| WP-I1-010 | Multi-angle automation | IMPLEMENTATION | M | Feature expansion | yes | I0 |
| WP-I1-011 | Multi-subject scenes | IMPLEMENTATION | L | Feature expansion (likely I2) | yes | I0; ideally WP-I1-007 |
| WP-I1-013 | Installer build + release | INFRASTRUCTURE | M | Distribution | n/a | I0; ideally WP-I1-003 |
| WP-I1-014 | MediaPipe Tasks API migration | INFRASTRUCTURE | M | Future-proofing | n/a | I0 |
| WP-I1-015 | Floating reference portrait window | IMPLEMENTATION | S | Polish | yes | WP-I0-004; WP-I1-003 |
| WP-I1-022 | Read OpenPose JSON as alternate input | IMPLEMENTATION | M | Workflow expansion | yes | I0; composes with WP-I1-023 |
| WP-I1-024 | Synchronized viewport zoom | IMPLEMENTATION | S | Polish | n/a (GUI sync only; headless covered by WP-I1-023) | WP-I0-004; WP-I1-015; WP-I1-023 |
| WP-I3-011 | OpenRepose AMood GPT + Claude Skill Wrappers | DOCUMENTATION | M | Future integration (after DB/dispatcher/AMood command path is fully functional) | n/a (skill wrappers only) | WP-I3-003; WP-I3-004; WP-I3-006; WP-I3-007; WP-I3-010 |

## Recently Done

Last 10 workpackets to reach DONE. Files moved from `workpackets/` to `archive/`.

| WP-ID | Title | Owner | Class | Closed |
|-------|-------|-------|-------|--------|
| WP-I1-036 | Multi-file workspace spec (documentation/spec only; product implementation remains future work) | assistant | DOCUMENTATION | 2026-05-04 |
| WP-I3-008 | Triage GUI tab + 3 snapshot targets | assistant | IMPLEMENTATION | 2026-05-04 |
| WP-I3-007 | Requirements editor + target tree commands | assistant | IMPLEMENTATION | 2026-05-04 |
| WP-I4-001 | Intake scale + DB hardening | assistant | IMPLEMENTATION | 2026-05-04 |
| WP-I3-006 | AMood data-model commands + dedupe service | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I3-002 | LLM stance acknowledgement primitives | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I2-008 | Library multi-operator tests + setup doc | assistant | VERIFICATION | 2026-05-03 |
| WP-I2-007 | Library snapshot targets | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I2-006 | Library tab GUI | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I2-005 | ComfyUI bridge custom node | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I2-004 | Library LLM commands + library_search | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I2-003 | Library entries CRUD + tags + smart-tag extractor | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I2-002 | Settings extension: library config (schema 1→2) | assistant | INFRASTRUCTURE | 2026-05-03 |
| WP-I2-001 | PostgreSQL setup + migration runner | assistant | INFRASTRUCTURE | 2026-05-03 |
| WP-I1-035 | In-app manual + manual-impact governance rule | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I1-034 | Calibration overview mode + drag/delete + add-marker workflow | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I3-005 | Default-staging ComfyUI bridge | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I3-004 | Intake + project + task command surface | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I3-003 | I3 PostgreSQL schema migrations | assistant | INFRASTRUCTURE | 2026-05-03 |
| WP-I3-001 | AMood + Intake + Requirements Spec Lock | assistant | DOCUMENTATION | 2026-05-03 |
| WP-I1-028 | Calibration Tab UX (zoom + always-on overlay + spacebar pan) | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I1-031 | Tools Tab Reorganization (incl. frame slider/spinbox) | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I1-030 | Export Polish (PNG + pretty JSON + slug sanitization) | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I1-029 | Per-Marker Visibility (auto-uncheck undetected + defensive render) | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I1-033 | Feature 3 Spec (Library + ComfyUI + PostgreSQL) | assistant | DOCUMENTATION | 2026-05-03 |
| WP-I1-032 | GUI Polish Bundle | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I1-023 | Frame Reframing (Robust Rerender) | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I1-017 | Per-Body-Part Visibility Toggles | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I1-027 | Export Folder Picker And Persistence | assistant | IMPLEMENTATION | 2026-05-03 |
| WP-I0-001 | Rig And Rotation Core | assistant | IMPLEMENTATION | 2026-05-02 |
| WP-I0-002 | LLM Control Surface | assistant | IMPLEMENTATION | 2026-05-02 |
| WP-I0-003 | Snapshot Subsystem | assistant | IMPLEMENTATION | 2026-05-02 |
| WP-I0-004 | Double Viewport GUI | assistant | IMPLEMENTATION | 2026-05-02 |
| WP-I1-025 | Quarterly Governance Audit | assistant | INFRASTRUCTURE | 2026-05-02 |
| WP-I1-026 | Feature 2 Calibration Overlay Spec | assistant | DOCUMENTATION | 2026-05-02 |
| WP-I1-001 | Per-Avatar Calibration Overlay | assistant | IMPLEMENTATION | 2026-05-03 |

## Cancelled

Workpackets that will not be done. Reason recorded in the workpacket file (which still moves to `archive/`).

| WP-ID | Title | Owner | Class | Reason | Cancelled |
|-------|-------|-------|-------|--------|-----------|

_(none)_

## Iteration Notes

### I0 — Initial Scaffold (CLOSED 2026-05-02)

- Repo created 2026-05-02.
- Governance, product split, target/dist/outputs folders, orstart command, codex, agents, topology, workflow framework, and improved WP template all scaffolded.
- Spec v0.1 drafted with: yaw terminology lock, output formats, mechanical log format, LLM control surface, snapshot subsystem, operator experience guarantees, Feature 1 (3D-rig yaw exporter) GUI + CLI requirements.
- Four workpackets shipped: WP-I0-001 (rig+rotation core), WP-I0-002 (LLM control surface), WP-I0-003 (snapshot subsystem), WP-I0-004 (double viewport GUI). All four DONE on 2026-05-02.
- I0 close criterion met: operator can launch the GUI, import a frontal portrait, watch both viewports update through 13 yaw angles, export a 13-angle batch; a separate LLM agent drives the same workflow through the inbox channel without operator focus theft. 111/111 tests green at close.

### I1 — In Progress

- WP-I1-025 (Quarterly Governance Audit) shipped DONE on 2026-05-02 ahead of the rest of I1 because the audit script is infrastructure scaffolding for the workflow rules introduced this iteration.
- Workflow Version bumped to 1.1: new IMPLEMENTATION/RESEARCH WPs created from the template must carry a `## Research Notes` section. Existing 1.0 WPs grandfathered.
- WP-I1-026 (Feature 2 Calibration Overlay Spec, DOCUMENTATION) shipped DONE 2026-05-02 — locks the deformation algorithm (TPS via scipy), marker schema, calibration JSON schema, command surface, state-file shape, and snapshot target for WP-I1-001 to implement against.
- WP-I1-001 (Per-Avatar Calibration Overlay, IMPLEMENTATION, L) shipped DONE 2026-05-03. 178/178 tests passing; junit XML at `target/test-artifacts/WP-I1-001/`. GUI verification surfaced two Calibration-tab usability gaps (no zoom; no frontal mesh sanity preview) — operator approved sign-off on the basis that the spec contract + headless surface + tests are met; deferred items recorded in WP-I1-001 Fallback Register and queued as WP-I1-028.
- 2026-05-03: three follow-up WPs drafted at status DRAFT: **WP-I1-027 Export folder picker + persistence** (highest priority — fixes the bug where the OptionsPane `settings_changed` signal is unwired so pasted paths silently ignored); **WP-I1-028 Calibration zoom + frontal mesh inspector** (UX polish for WP-I1-001); **WP-I1-029 Per-marker visibility toggles** (sibling of WP-I1-017's per-body-part).
- 2026-05-03 fast-track: WP-I1-027 + WP-I1-017 + WP-I1-029 + WP-I1-023 shipped to REVIEW; viewport regression caught by operator GUI inspection and fixed in-place; suite 281/281 + 4 regression-guard tests on the polling path. Pytest now runs offscreen so windows don't flash on the operator's desktop.
- 2026-05-03 Phase 2: drafted **WP-I1-030 Export polish** (PNG output + pretty-printed JSON + avatar slug sanitization); drafted **WP-I1-031 Tools tab reorganization** (Tools top-level with Calibration / Markers / Reframer sub-tabs; also picks up operator's frame-offset-sliders + per-section reset request); expanded **WP-I1-028** scope from M → L to fold in always-on MediaPipe-detected overlay + drag-to-move + right-click-delete + new `delete_markers` headless command.
- 2026-05-03 fast-track Phase B+C: shipped **WP-I1-032 GUI polish bundle** (calibration sizing + last-portrait-folder + canvas border + colored marker rows; 295/295 passing) + **WP-I1-033 Feature 3 spec** (PostgreSQL day one, psycopg 3, hybrid trigram+tsvector search, 7 LLM commands, ComfyUI bridge). Operator signed off WP-I1-027 + WP-I1-017 + WP-I1-023 + WP-I1-032 + WP-I1-033 on 2026-05-03. WP-I1-029 rejected REVIEW → IN-PROGRESS for follow-up bug: undetected MediaPipe markers should auto-uncheck on import; defensive render to avoid stray-dot-at-origin "haywire".
- 2026-05-03 fast-track 2: shipped **WP-I1-029 fix** (auto-uncheck undetected + defensive render + Markers tab "— no detection" annotations) + **WP-I1-030 export polish** (PNG alongside JSON + pretty-printed JSON + slug sanitization) + **WP-I1-031 Tools tab reorganization** (Inspector / Tools (Calibration|Markers|Reframer) / Options / Log / Help; ReframerPane with slider+spinbox+per-section resets) + **WP-I1-028 calibration UX core** (zoom + pan + always-on MediaPipe overlay + spacebar+left-click pan per Photoshop convention). Operator signed off all 4 on 2026-05-03 (329/329 tests passing).
- 2026-05-03: **WP-I1-034** (calibration overview mode + drag-to-move + right-click-delete + `delete_markers` command + add+place workflow when no detection) and **WP-I1-035** (in-app manual under `.gov/doc/manual/` + Help tab manual browser + Manual Impact governance rule + audit script extension) both shipped to REVIEW. Operator-noted future scope: body calibration (currently face-only) — needs spec extension first.
- 2026-05-03 overnight: operator handed off the I2 sequence to the assistant for autonomous overnight execution (operator-defined order: WP-I2-002 → WP-I2-001 → WP-I2-003 → WP-I2-004 → WP-I2-005+006 parallel → WP-I2-007 → WP-I2-008). All shipped WPs land at REVIEW pending operator sign-off. **WP-I2-002** promoted DRAFT → READY → IN-PROGRESS as kickoff.

### I2 — Feature 3: OpenPose Library + ComfyUI Coupling (REVIEW 2026-05-03)

- 8 WPs shipped to REVIEW against the WP-I1-033 spec:
  - **WP-I2-001 INFRASTRUCTURE**: PostgreSQL setup + migration runner + docker-compose.
  - **WP-I2-002 INFRASTRUCTURE**: Settings schema_version 1 → 2 (library_db_url, library_root, operator_slug).
  - **WP-I2-003 IMPLEMENTATION**: library_entries + tags + entry_tags CRUD + smart-tag extractor + filesystem storage.
  - **WP-I2-004 IMPLEMENTATION**: 7 LLM commands + library_search() wrapper + prompts/story_beats/notes editing.
  - **WP-I2-005 IMPLEMENTATION**: ComfyUI bridge custom node (`.product/comfyui-bridge/`).
  - **WP-I2-006 IMPLEMENTATION**: Library tab GUI (left list + right detail + 6 sub-panes).
  - **WP-I2-007 IMPLEMENTATION**: 2 new snapshot targets.
  - **WP-I2-008 VERIFICATION**: multi-operator tests + pg_dump round-trip + operator setup doc; closes I2.
- Execution order completed: WP-I2-002 -> WP-I2-001 -> WP-I2-003 -> WP-I2-004 -> WP-I2-005 + WP-I2-006 -> WP-I2-007 -> WP-I2-008. All await operator sign-off.

### I3 — AMood + Intake + Requirements (spec lock DONE 2026-05-03)

- Operator dropped the canonical AMood blueprint at `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` (2070 lines; provider/model agnostic; tier table + package layout + 8+ TSV schemas + scoring rubric + abandonment criteria + accepted-set diversity audit + anti-repetition ledger).
- Multi-turn design conversation produced a coherent set of contracts that extend OpenRepose to operationalize the blueprint while preventing main-library contamination from raw LLM outputs.
- **WP-I3-001 (DOCUMENTATION, L)** authored 4 spec sections + 4 manual topics + topology extension as a single locked-contract bundle. Operator approved; WP is DONE and archived:
  - `openrepose_amood_v0_1.md` — AMood data model + command surface + package layout under `outputs/library/<project_slug>/<batch_slug>/`.
  - `openrepose_intake_v0_1.md` — Project / Task / Batch / Card / Run / Output hierarchy; intake staging at `outputs/intake/<task_id>/`; status enum (`pending → triaging → soft_accepted → promoted | rejected | diagnostic | abandoned`); two-stage acceptance (LLM may soft_accept; only operator may finalize); default-staging ComfyUI bridge.
  - `openrepose_rules_v0_1.md` — Rule registry (4 severity tiers: auto-route / block / warn / info), error-citation contract, global-vs-project-scoped registry split, initial registry seeded with the 6 existing repo rules promoted to RUL-001..006.
  - `openrepose_requirements_v0_1.md` — Typed scoped requirements (8 kinds: hard_output / body / pose / face / crop / quality / clothing_story / structural / custom), inheritance, target tree (sets → cards → per-card target_promoted + AMood stability_target), counters, `fully_satisfied = count_satisfied AND quota_satisfied`, EXP120 worked example.
- 4 manual topics: `amood-workflow.md` (REPLACE existing simpler tag-page), `intake-and-triage.md` (NEW), `targets-and-progress.md` (NEW), `requirements-and-targets.md` (NEW with EXP120 worked example).
- **WP-I3-002** is at REVIEW and exposes the Adult Production Boundary through LLM-facing primitives. **WP-I3-003** is READY as the first I3 implementation workpacket: PostgreSQL schema migrations. The implementation sequence is documented in `.gov/doc/handoff-2026-05-03-i3-implementation.md`.
- 2026-05-03: **WP-I3-011 OpenRepose AMood GPT + Claude Skill Wrappers** drafted at DRAFT for the future state where the OpenRepose DB, dispatcher, AMood import, intake scoring, accepted-set audit, and requirements/target commands are fully functional. It is a two-track companion integration wrapper effort, not an AMood fork; both GPT/OpenAI and Claude/Codex wrappers must work before DONE.
- 2026-05-03: **WP-I3-003 / WP-I3-004 / WP-I3-005 signed off DONE** by operator. **WP-I3-006 (AMood data-model commands + dedupe service, IMPLEMENTATION, L)** opened at IN-PROGRESS. Scope: 7 dispatcher commands (`init_batch_package`, `library_create_card`, `library_create_variants`, `compatibility_check`, `accepted_set_audit`, `amood_export_tsv`, `amood_import_tsv`), new `library/amood/` subpackage, new migration `005_i3_amood_tsv_views.sql` (10 TSV-shaped views in AMood-locked column order, schema_version 4 → 5), `state.library.amood` block, AMOOD-001 dedupe-warning surface, blueprint-template-driven package layout under `outputs/library/<project>/<batch>/`. Predecessors WP-I3-003/004/005 archived in the same kickoff commit.
- 2026-05-03: **WP-I3-006 advanced IN-PROGRESS → REVIEW**. Implementation landed: migration 005 with 10 views (`library_amood_*_v`) in locked AMood column order; `library/amood/` subpackage with 8 modules; 7 dispatcher handlers wired into `commands.py` with `OpenReposeAmoodError` propagation; `state.library.amood` block + 3 mutators on AppState. AMOOD-001 surfaces with overlap_count + matched card slug; SAFE-001/002/003 + AMOOD-004 cited from `compatibility_check`. 39 new tests (12 commands + 6 dedupe + 21 TSV) all passing against ephemeral PG; 68/68 regression-prone tests still passing after schema_version 4 → 5 bump. Manual `amood-workflow.md` extended with Commands table, AMOOD-001 citation example, and dedicated anchor sections (`#anti-repetition`, `#abandonment-criteria`, `#fast-triage`, `#safety-boundary`). Audit clean. Two FALLBACK paths recorded in WP Fallback Register (variant change-rules subset; TSV import for 6 system-generated schemas). Awaiting operator sign-off.
- 2026-05-03: **Sweep A sign-off batch — 12 WPs DONE in one operator-granted commit.** Closed: WP-I1-034 (calibration overview mode + drag/delete + add-marker), WP-I1-035 (in-app manual + manual-impact rule), the full I2 sequence WP-I2-001..008 (Feature 3 OpenPose Library + ComfyUI bridge + PostgreSQL — I2 iteration CLOSED), WP-I3-002 (stance acknowledgement primitives), WP-I3-006 (AMood data-model commands). 583/583 tests pass across the closed scope. I2 + the I3 Sweep A bundle (-002/-003/-004/-005/-006) are now archived. Sweep B (WP-I3-007 + WP-I3-009) is next; handoff doc at `.gov/doc/handoff-2026-05-03-i3-implementation-phase-2.md`.

### I4 — Intake Scale + DB Hardening (OPEN 2026-05-04)

- 2026-05-04: **WP-I4-001 Intake scale + DB hardening** opened at READY. Scope extends the existing I3 intake system rather than replacing it: bulk output registration, idempotent retries, output-level producer attribution (`source_model`, `agent_id`, `producer_run_id`, `idempotency_key`), durable file-state/file-op recovery (`storage_state` enum + outbox), transaction-boundary cleanup (data-layer helpers stop committing internally), search filtering (main `library_search` excludes pending/diagnostic/rejected/soft_accepted by default), and a 3-producer × ≥100 outputs each parallel e2e proof. Migration `006_i4_intake_scale_hardening.sql` will bump `schema_version 5 → 6`. No `.product/` implementation has started.
- 2026-05-04: **WP-I4-001 advanced IN-PROGRESS → REVIEW**. Implementation landed migration 006, producer attribution, idempotent bulk registration, durable file-op/recovery tracking, search filtering, dispatcher commands (`intake_register_outputs_bulk`, `intake_recover_audit`, `intake_recover_retry`, `intake_process_file_ops`), and audit-script topology parsing for I4 command surfaces. Proof: 17/17 scale + parallel e2e tests passing with JUnit at `target/test-artifacts/WP-I4-001/junit.xml`; 7/7 dispatcher tests passing; audit clean. Awaiting operator sign-off.
- 2026-05-04: **WP-I4-001 signed off and archived DONE**. Operator accepted the completed intake scale + DB hardening scope; active pending-review count now excludes WP-I4-001.
- 2026-05-04: **WP-I3-007, WP-I3-008, and WP-I1-036 signed off and archived DONE**. Operator accepted the completed requirements/target-tree implementation, Triage GUI + snapshot implementation, and multi-file workspace documentation/spec scope. Product implementation of true multi-file workspace remains future work.
- 2026-05-04: **WP-I1-018 and WP-I1-037 opened IN-PROGRESS for autonomous overnight work**. Research recorded before product edits. WP-I1-037 is the implementation follow-up to the signed-off WP-I1-036 spec; WP-I1-018 adds MediaPipe Tasks hand detection and OpenPose hand arrays.
- 2026-05-04: **WP-I1-018 and WP-I1-037 advanced IN-PROGRESS -> REVIEW**. Evidence includes focused pytest 47/47, PostgreSQL library regression 30/30, real sample-image database validation, three-file multi-file import/export/snapshot validation, OpenPose hand JSON array checks, visual review of hand-render snapshots, topology update for new commands, `test_material/` gitignore guard, and clean `scripts/audit-repo.ps1`. Full-suite pytest timed out and is recorded in both WPs as residual validation risk.

## Iteration Pipeline

I1 has 20 drafted workpackets, 1 deferred (WP-I1-012 garment locks), 3 reserved-not-drafted (WP-I1-019/020/021 joint manipulation — operator postponed). Once I0 closes, the operator promotes individual WPs from DRAFT → READY in priority order.

Recommended sequencing once I0 closes:

1. **WP-I1-001 calibration overlay** — directly fixes the WP-I0-003 wireframe-fidelity gap. High priority.
2. **WP-I1-016 clear workspace + WP-I1-017 per-body-part visibility** — small daily-UX wins; unblock common operator complaints.
3. **WP-I1-022 read OpenPose JSON input** — unlocks workflows that don't start from a portrait.
4. **WP-I1-023 frame reframing** — robust rerender approach; fixes portrait-bias / cropped-feet. High priority.
5. **WP-I1-003 settings persistence** — needed before WP-I1-015 reference window can persist its position.
6. **WP-I1-015 floating reference portrait window + WP-I1-024 synchronized viewport zoom** in parallel — operator's continuous-context-during-work feature.
7. **WP-I1-014 MediaPipe Tasks API migration** before any new feature WP that adds MediaPipe usage. Schedule before WP-I1-018.
8. **WP-I1-018 hand detection + OpenPose hand output** — enables DWPose hand conditioning.
9. **WP-I1-002 orbital camera, WP-I1-004 keyboard shortcuts, WP-I1-005 drag-and-drop, WP-I1-006 theme refinements** — polish, can run anytime in parallel.
10. **WP-I1-007 pitch/roll rotation** before **WP-I1-009 identity profiles** and **WP-I1-011 multi-subject scenes**.
11. **WP-I1-008 alternative landmark detector research** can run anytime; pure RESEARCH.
12. **WP-I1-010 multi-angle automation** — straightforward extension of `export_batch`.
13. **WP-I1-013 installer build + release** — when v0.1 feature set is stable.

Future iteration themes not yet drafted as workpackets:

- I2: WP-I1-019/020/021 joint manipulation chain (RESEARCH then IMPLEMENTATION). Deferred per operator.
- I2: code signing for distributables.
- I2: macOS / Linux builds.
- I2: GitHub Actions CI for automated test + build.
- I2: per-feature-group calibration mixing (extension of WP-I1-001).
- I2: animated yaw-sweep video export.
- I2: read OpenPose PNG image (reverse-engineer keypoints from rendered colors). Pure RESEARCH first.
- I2: re-scope WP-I1-012 garment locks as "garment polyline -> secondary ControlNet input" if multi-ControlNet workflow becomes a production path.

Each becomes its own workpacket when authorized.
- 2026-05-04: **WP-I1-018 + WP-I1-037 implementation pass landed**. Product files now contain hand-keypoint pipeline changes and multi-file dispatcher/GUI tab changes. WPs remain IN-PROGRESS pending syntax/test/GUI/visual evidence before REVIEW.
