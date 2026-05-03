# Intake and triage

OpenRepose stages every new generated output in an isolated **intake** directory before it touches the main library. The operator (and any LLM driving the system) reviews intake, accepts what passes requirements, and rejects the rest. This page is the operator-facing flow; the contract is in `.gov/spec/openrepose_intake_v0_1.md`.

Adult Production Boundary applies (`.gov/doc/manual/adult-production-boundary.md`): no censoring, no softening, no legal/consent gatekeeping by repo, product, or LLM assistants.

## The shape

Six levels in the hierarchy. Each rolls counters up.

```text
Project   long-lived workstream                      (e.g. "exposure-120")
  Task    one LLM execution unit (a 960-image run)   (e.g. "T-2026-05-03-01")
    Batch AMood batch_slug                            (e.g. "exp120-sf-batch-01")
      Card moodboard card                              (e.g. "SF-15")
        Run one ComfyUI generation
          Output one image file
```

A task may span one or many batches. A batch belongs to exactly one task. Cards belong to exactly one batch.

## Folder layout

Both directories are gitignored. The DB is the source of truth; folders are projections.

```text
outputs/
  intake/<YYYYMMDD>-<task_slug>/
    raw/                                       # what the bridge dropped
    diagnostic/intermediate_evidence/          # auto-routed (e.g. wrong resolution)
    contact_sheets/                            # operator helpers
    rejected/                                  # outputs rejected during triage
  library/<project_slug>/<batch_slug>/
    soft_accepted/                             # stage-1 LLM acceptances
    accepted/                                  # stage-2 finalized
    cards/ moodboards/ prompt_blocks/ pose_guides/ manifests/  (per AMood spec)
```

## Status enum

One vocabulary across every level.

```text
pending        row exists; no action yet
triaging       being inspected (operator active)
soft_accepted  LLM stage-1 accept; visible in main library tagged 'pending_operator_signoff'; library_search filters out by default
promoted       operator stage-2 finalize; counts toward target
rejected       not accepted; remains in DB for diagnostics
diagnostic     teaching artifact; never counts toward target
abandoned      card-level abandonment per AMood AMOOD-002; child outputs frozen
```

## Two-stage acceptance

The kill switch that prevents a hallucinating LLM from poisoning the library.

```text
LLM agents may issue:
  intake_soft_accept   moves output to soft_accepted/; library_search hides it by default
  intake_reject        moves output to rejected/

Operators only may issue:
  intake_finalize      promotes a soft_accepted output; counts toward target_promoted
  promote_to_library   bulk-finalize all soft_accepted in one task
```

If an LLM tries `intake_finalize` it gets:

```text
ERR cmd=intake_finalize: blocked by INTAKE-001 (two-stage acceptance):
LLM may soft_accept; only operator may finalize.
See manual: intake-and-triage#two-stage-acceptance.
Fix: emit intake_soft_accept; operator runs intake_finalize.
```

Soft-accept is reversible until finalize. After finalize, demotion is out of scope for v0.1.

## Default intake target {#default-intake}

The ComfyUI bridge writes to `outputs/intake/<task_id>/raw/` by default. Direct library writes require an operator-issued session token. Without a task_id and without a token, the bridge refuses with `INTAKE-002`.

Operators set `OPENREPOSE_TASK_ID` in the environment when launching ComfyUI for a specific batch run. The bridge embeds it on every POST.

## Three layers of triage

A 960-image task is unmanageable click-by-click. Triage runs in three layers so most outputs are decided in bulk.

### Layer 1: Pre-flight task summary {#pre-flight}

When the operator opens a task (`pending → triaging`), one screen shows:

- received vs expected count
- per-card auto-route counts (already routed by deterministic checks; skipped from the queue)
- per-card pending count (eligible for triage)
- missing pose-guide warnings
- machine-flagged obvious failures
- AMood quota progress vs target tree

If pre-flight reveals an unsalvageable batch (wrong avatar, wrong workflow), wholesale-reject the task in one click + transaction.

### Layer 2: Auto-prefilter {#auto-prefilter}

Deterministic checks (severity `auto-route`) run on every output insert. EXP120 example:

```text
EXP120-RES-001  width == 1080 AND height == 1440  fail -> diagnostic/intermediate_evidence/
EXP120-RES-002  3:4 portrait                       fail -> diagnostic/intermediate_evidence/
```

Auto-routed outputs do not count toward target, do not enter the queue, but are reversible — operator may re-route from `intermediate_evidence/` back to `pending` if the metadata was wrong.

Probabilistic checks (face-age estimator, hand sanity) are advisory hints only in v0.1: color-coded in the queue, never auto-rejecting.

### Layer 3: Per-card variant strip

For decisions the operator opens one card at a time:

- the card's pose guide (PNG + skeleton)
- 4–6 paired generated outputs side-by-side at consistent crops
- each output's auto-route + advisory status
- the per-image requirements panel
- AMood fast-triage 4 fields (adult_gate / trigger_clarity / anatomy / artifact); on pass, the full-rubric 16 fields expand
- accept/reject keystroke per output

Accept the variant when the card is producing reliably (AMood `stability_target` = 4 by default; project may set `target_promoted` higher, e.g. 8 for EXP120).

## Per-task isolation {#per-task-isolation}

Each task owns its own intake directory. Wholesale-reject is one transaction:

```text
1. delete outputs/intake/<task_id>/   (via /safe-delete; refuses to climb out of repo root)
2. delete library_outputs WHERE task_id = ...
3. set library_tasks.status = 'rejected_wholesale'
```

This is why tasks are isolated by directory and not just by tag — a bad batch is removed cleanly without touching others. Rule citation: `INTAKE-003`.

## library_search excludes pending {#library-search}

By default, `library_search` filters out outputs with `status = pending`. Add `include_pending=true` to see them. This keeps the main library view clean while triage is in progress. Rule citation: `INTAKE-004`.

## Self-documenting state

Cold-start LLM agents read `state.library.intake` and `state.library.guidance` to learn what to do. No external context required.

```json
{
  "library": {
    "intake": {
      "active_task_id": "<uuid>",
      "active_task_slug": "<slug>",
      "received_count": 960,
      "pending_count": 41,
      "soft_accepted_count": 7,
      "promoted_count": 12,
      "rejected_count": 880,
      "queue_depth": 41
    },
    "guidance": {
      "current_focus": "task T-2026-05-03-01: triage 41 pending",
      "next_valid_actions": ["intake_inspect","intake_soft_accept","intake_reject"],
      "active_rules": ["INTAKE-001","INTAKE-002","AMOOD-001"]
    }
  }
}
```

## Worked example: incoming task

1. Operator runs `task_create project_id=<exp120-id> slug=hotel-reveal-batch-01 expected_count=80 source=comfyui_bridge llm_model=opus-4.7`.
2. Operator launches ComfyUI with `OPENREPOSE_TASK_ID=<task_id>`. The 960-image run begins.
3. As outputs land, the bridge POSTs `intake_register_output`. Each row inserts with `status=pending`. EXP120-RES-001 + RES-002 auto-route the wrong-resolution outputs (≈700 of them) to `diagnostic/intermediate_evidence/` immediately.
4. Operator opens the task in the Library tab → Triage Queue sub-pane. Pre-flight shows: received=960, auto-routed=700, pending=260, missing pose guides=0.
5. Operator runs Layer 3 per-card variant strips. Accepts variants where the card is producing reliably. Soft-accepts ~80 outputs across 12 cards.
6. Operator runs `promote_to_library task_id=<task_id>`. Soft-accepted outputs move from `soft_accepted/` to `accepted/`; counters bump; scorecard rows written.
7. Counters: project 80/960 promoted, gap 880, forecast_ok=false (in_flight is 0 now since the run finished). Operator decides to start a new task.

## Commands

```text
project_create        slug, name, owner_slug -> project_id
task_create           project_id, slug, expected_count, source, llm_model -> task_id, intake_dir
task_summary          task_id -> pre-flight summary
task_inspect          task_id -> task row + linked batches + linked runs
intake_list           task_id, status filter, limit, offset -> [output rows]
intake_inspect        output_id -> output row + paired pose guide + card metadata + scorecard skeleton + requirements
intake_soft_accept    output_id [, scorecard fields] -> soft_accepted (LLM-issuable)
intake_reject         output_id, primary_rejection_reason [, notes] -> rejected (LLM-issuable)
intake_finalize       output_id -> promoted (OPERATOR-ONLY, token-gated)
promote_to_library    task_id -> bulk-finalize all soft_accepted (OPERATOR-ONLY)
intake_reroute        output_id, target_status -> auto-route reversal
task_reject_wholesale task_id, reason -> all non-terminal to rejected; intake_dir deleted (OPERATOR-ONLY)
```

## Safety boundary {#safety-boundary}

DB CHECK constraints refuse promotion when `primary_rejection_reason ∈ {juvenile_coded, coercion_coded, hidden_camera_coded}`. No override path. Rule citations `SAFE-001`, `SAFE-002`, `SAFE-003`. This is an integrity gate at the storage layer, not an enforcement of legal/consent paperwork (the operator still owns those obligations per Adult Production Boundary).
