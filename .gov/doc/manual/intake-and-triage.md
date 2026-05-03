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

The operator-only commands (`intake_finalize`, `promote_to_library`, `task_reject_wholesale`) require an `operator_token` field on the command payload. The token is derived from operator settings (slug + library_root) and is not exposed to the LLM control surface — the GUI session computes it; LLM agents running headlessly never see one. The DB-level CHECK constraint `lib_outputs_intake_001_two_stage_acceptance` is the actual kill switch (status='promoted' requires `finalized_by NOT NULL`); the dispatcher token gate is defense-in-depth so the LLM gets the canonical INTAKE-001 citation before the SQL even runs.

## Default intake target {#default-intake}

The ComfyUI bridge writes to `outputs/intake/<task_dir>/raw/` by default. Direct library writes require an operator-issued token. Without a task_id and without a token, the bridge refuses with `INTAKE-002` and skips the POST entirely (the image still saves to ComfyUI's normal output directory).

### Operator setup (Windows)

Before launching ComfyUI for a batch run, set the env vars in the same shell:

```powershell
# Required for the intake (default) path:
$env:OPENREPOSE_TASK_ID = "<task-uuid-from-task_create>"

# One of these binds the run to a card:
$env:OPENREPOSE_CARD_ID = "<card-uuid>"
# or:
$env:OPENREPOSE_CARD_SLUG = "SF-15"

# Optional, for ad-hoc non-batch work (legacy direct-library path):
# $env:OPENREPOSE_OPERATOR_TOKEN = "<token-from-gui-session>"

# FALLBACK v0.1, transitional only — forces legacy path even without a token:
# $env:OPENREPOSE_LEGACY_DIRECT_WRITE = "1"

python main.py  # or however you launch ComfyUI
```

POSIX equivalents (`export OPENREPOSE_TASK_ID=...`, etc.) work the same way.

### Branch table

| `OPENREPOSE_TASK_ID` | `OPENREPOSE_OPERATOR_TOKEN` | `OPENREPOSE_LEGACY_DIRECT_WRITE` | Branch | What happens |
|----------------------|-----------------------------|----------------------------------|--------|--------------|
| set                  | (any)                       | (any)                            | **intake** | bridge POSTs `intake_begin_run` once + `intake_register_output` per image; rows land at `status='pending'` |
| (unset)              | set                         | (any)                            | **legacy** | bridge POSTs `register_library_entry` with `operator_token` field |
| (unset)              | (unset)                     | `=1`                             | **legacy_fallback** | FALLBACK v0.1: legacy path even without a token; transitional |
| (unset)              | (unset)                     | (unset)                          | **refused** | bridge logs INTAKE-002 to stderr; no POST; image still saved to ComfyUI's output dir |

The bridge emits a one-line summary on stderr at every save (`openrepose-bridge: path=intake images=4 url=...`) so operators can confirm the active branch from the ComfyUI console.

### Card binding

The intake path needs a card to attach the run to. Two ways to bind:

1. `OPENREPOSE_CARD_ID` (preferred): exact UUID, no ambiguity.
2. `OPENREPOSE_CARD_SLUG`: dispatcher resolves the slug under the active task's batch via `library_entries.title`. If multiple cards share the slug under the same task, the dispatcher logs a WARN and takes the first match by `created_at`.

Without either, the intake path skips the POST and logs a hint to add one — the image still saves to disk.

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

Implemented in WP-I3-004; reachable through the existing HTTP localhost endpoint (`POST /command`) and file-watch inbox (`outputs/.runtime/inbox/`).

| Command | Caller | Required fields | Returns |
|---------|--------|-----------------|---------|
| `project_create` | LLM or operator | `slug`, `name`, optional `owner_slug` | `project` row |
| `project_list` | LLM or operator | optional `status` | `projects[]`, `count` |
| `task_create` | LLM or operator | `project_id`, `slug`, optional `expected_count`/`source`/`llm_model` | `task` row + intake dir tree |
| `task_list` | LLM or operator | optional `project_id`/`status` | `tasks[]`, `count` |
| `task_summary` | LLM or operator | `task_id` | per-status counters + warnings |
| `task_inspect` | LLM or operator | `task_id` | task row + batches + run_count |
| `intake_begin_run` | bridge / LLM | `task_id`, `card_id` or `card_slug`, optional `sampler`/`cfg`/`steps`/`seed`/`pose_guide_id`/`workflow_json` | `run` row |
| `intake_register_output` | bridge / LLM | `run_id`, `task_id`, `width`, `height`, AND either (a) `file_path` + `content_hash` OR (b) `image_b64` + `filename` (dispatcher writes bytes + computes hash) | `output` row + `auto_route` decision |
| `intake_list` | LLM or operator | optional `task_id`/`status`/`limit`/`offset` | `outputs[]`, `count` |
| `intake_inspect` | LLM or operator | `output_id` | output row + pose_guide + diagnostics |
| `intake_soft_accept` | **LLM-issuable** | `output_id`, optional `notes` | output row at `soft_accepted` |
| `intake_reject` | LLM-issuable | `output_id`, `primary_rejection_reason`, optional `notes` | output row at `rejected` (file moved to `rejected/`) |
| `intake_reroute` | LLM or operator | `output_id`, `target_status` ∈ {pending,diagnostic,rejected} | output row updated |
| `intake_finalize` | **operator-only** | `output_id`, `operator_token` | output row at `promoted` |
| `promote_to_library` | **operator-only** | `task_id`, `operator_token` | bulk-promoted ids |
| `task_reject_wholesale` | **operator-only** | `task_id`, `reason`, `operator_token` | transitioned count + deleted intake_dir |

### Worked example: LLM driving an intake flow

```json
// 1. Bridge or LLM registers each generated output:
{ "command": "intake_register_output",
  "run_id": "<uuid>", "task_id": "<uuid>",
  "file_path": "intake/20260503-T-001/raw/out-042.png",
  "content_hash": "sha256-...", "width": 1080, "height": 1440 }

// 2. LLM lists pending and inspects:
{ "command": "intake_list", "task_id": "<uuid>", "status": "pending", "limit": 50 }
{ "command": "intake_inspect", "output_id": "<output-uuid>" }

// 3. LLM may soft-accept or reject:
{ "command": "intake_soft_accept", "output_id": "<output-uuid>", "notes": "looks clean" }
{ "command": "intake_reject", "output_id": "<output-uuid>",
  "primary_rejection_reason": "anatomy_failure", "notes": "broken hands" }

// 4. Operator (only) finalizes via the GUI session, which supplies operator_token:
{ "command": "intake_finalize", "output_id": "<output-uuid>",
  "operator_token": "<gui-supplied-sha>" }
```

Every response carries the canonical `adult_production_boundary` envelope (per WP-I3-002). Errors carry `rule_id` + `citation` fields when a rule fires (e.g. INTAKE-001 on operator-only commands without a token).

### Auto-route on intake_register_output

When a project has `library_rules` rows at `severity=auto-route`, every `intake_register_output` call evaluates each rule's `machine_check_fn` against the output's `width`/`height`. On failure, the output is set to `status=diagnostic`, a `library_diagnostics` row is written, and the file is moved into `outputs/intake/<task_dir>/diagnostic/<auto_route_to>/`. Empty rule set = pass-through; the output stays `pending`. Operators can re-route with `intake_reroute` when a rule mis-detects (per `REQ-002`).

## Safety boundary {#safety-boundary}

DB CHECK constraints refuse promotion when `primary_rejection_reason ∈ {juvenile_coded, coercion_coded, hidden_camera_coded}`. No override path. Rule citations `SAFE-001`, `SAFE-002`, `SAFE-003`. This is an integrity gate at the storage layer, not an enforcement of legal/consent paperwork (the operator still owns those obligations per Adult Production Boundary).

## Triage tab {#triage-tab}

The Triage tab (added in WP-I3-008) is a read-only view of the same state surface an LLM agent reads through `state.json`. Operator triage actions stay LLM-driven in v0.1; this tab gives the operator visibility while an agent works.

Three regions, each independently snapshot-grabbable:

| Region | What it shows | State block read | Snapshot target |
|--------|---------------|------------------|-----------------|
| Project (left) | project slug + total target_promoted + promoted + gap + forecast_ok + count_satisfied + per-group rows (slug, promoted/target, stable_cards, complete_cards, expected/created cards) | `state.library.targets` | `intake_triage_view` (full tab) |
| Active task (top right) | task slug + per-status counters (pending / triaging / soft_accepted / promoted / rejected / diagnostic / abandoned / queue_depth) + forecast line | `state.library.intake` + `state.library.targets.active_task` | `task_summary_view` |
| Active card (bottom right) | card slug + target_promoted + stability_target + promoted + stable + complete + AMood batch summary + last 5 dedupe warnings | `state.library.targets.active_card` + `state.library.amood` | `library_card_with_pose` |

Snapshot invocation (LLM-side):

```json
{"command": "snapshot", "target": "task_summary_view"}
```

The dispatcher prefers a live widget grab when the GUI is up, falls back to a headless pure-OpenCV render driven by `state.library` when the GUI is down. Both paths produce the same target name and the same on-disk PNG shape, so an LLM agent never has to know which is in use.

Operator-side triage actions (click-to-soft_accept, click-to-reject, click-to-promote) are intentionally absent in v0.1; they land in a future GUI polish WP after WP-I3-010 verifies the LLM-driven path end-to-end.
