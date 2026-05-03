# Targets and progress

OpenRepose tracks operator-declared output targets at every level of the project hierarchy. Counters are derived from `library_outputs.status` (single source of truth). Both operator and LLM read the same numbers. Contract is in `.gov/spec/openrepose_requirements_v0_1.md`.

Adult Production Boundary applies (`.gov/doc/manual/adult-production-boundary.md`).

## What targets do

A target is the operator's declaration of how many promoted outputs are expected. Without targets, an LLM-driven loop has no terminating condition and the operator has no progress signal.

```text
project target  "I want 200 promoted images for this project."
task target     "This 960-image run should yield 80 promoted."
batch target    "Per-AMood-batch yield."
card target     "AMood stability_target (default 4) plus optional project override (e.g. 8 for EXP120)."
```

Targets are independent declarations at each level. Counters do roll up (project_promoted = Σ task_promoted = Σ Σ batch_promoted = …). Targets do not auto-roll-up — operator sets them where they are most useful.

`target_promoted_count = NULL` at any level means "no target set; no progress bar; no satisfaction gate." Targets are optional; AMood acceptance gates and abandonment criteria still apply per output.

## Counters

Derived from `library_outputs.status`. Same names at every level:

```text
pending_count        rows with status='pending'
triaging_count       status='triaging'
soft_accepted_count  status='soft_accepted'
promoted_count       status='promoted'        <- counts toward target
rejected_count       status='rejected'
diagnostic_count     status='diagnostic'      <- never counts
abandoned_count      status='abandoned'

gap            = max(0, target_promoted_count - promoted_count)
in_flight      = pending_count + triaging_count + soft_accepted_count
forecast_ok    = in_flight >= gap
```

## Stable vs. complete {#stable-vs-complete}

Two completion concepts on every card. Both visible.

```text
stable     promoted_count >= stability_target  (AMood blueprint default 4)
complete   promoted_count >= target_promoted   (project-set; EXP120 sets 8)
```

A card can be stable but incomplete — producing reliably, but the operator wants more variants. AMood's `stability_target` says the card is producing; the project's `target_promoted` says the operator's goal is met. Rule citation: `TARGET-003`.

## Satisfaction {#fully-satisfied}

```text
count_satisfied  = gap == 0
quota_satisfied  = AMood accepted-set diversity audit (every axis realized_coverage >= 0.75)
fully_satisfied  = count_satisfied AND quota_satisfied
```

`fully_satisfied` is the boolean an LLM agent reads to self-pace. Without the AND binding, an LLM can oversample one card and call it done while the diversity audit still flags `priority` axes. Rule citation: `TARGET-001`.

## Forecast warning {#forecast}

```text
forecast_ok = (in_flight >= gap)
```

When `forecast_ok = false`, the gap cannot close from current intake. Both GUI and `state.library.targets` flag it. Surface this early to the operator — don't wait until end of triage to discover the run was under-sized.

Possible causes:
- Operator over-targeted (revise target down)
- LLM under-seeded (LLM should generate more cards)
- Excessive auto-routing (check requirements; resolution mismatch)

Rule citation: `TARGET-002`.

## State surface

LLM agents and GUI both read `state.library.targets` (tree-shaped):

```json
{
  "library": {
    "targets": {
      "project": {
        "slug": "exposure-120",
        "target_promoted": 960, "promoted": 47,
        "gap": 913, "in_flight": 87, "forecast_ok": false,
        "count_satisfied": false, "quota_satisfied": false, "fully_satisfied": false
      },
      "groups": [
        {"slug": "SF", "name": "Standing frontal pussy exposure",
         "target_promoted": 160, "promoted": 24, "gap": 136,
         "stable_cards": 1, "complete_cards": 0,
         "expected_cards": 20, "created_cards": 18}
      ],
      "active_task": {
        "task_id": "T-2026-05-03-01",
        "target_promoted": 80, "promoted": 12, "soft_accepted": 7,
        "pending": 41, "rejected": 880, "gap": 68,
        "in_flight": 48, "forecast_ok": false, "satisfied": false
      },
      "active_card": {
        "card_id": "<uuid>", "slug": "SF-15",
        "stability_target": 4, "target_promoted": 8,
        "promoted": 2, "stable": false, "complete": false
      }
    }
  }
}
```

LLM self-pacing loop:

```text
while not state.library.targets.active_task.satisfied
  and not abandonment_triggered:
    generate next seed
    register via intake_register_output
```

## Worked example: 80/960 task progressing

Task `T-2026-05-03-01` in project `exposure-120` started at `target_promoted=80`, `received_count=0`.

Hour 1: ComfyUI dropped 200 outputs. EXP120-RES-001 auto-routed 150 (wrong resolution). 50 pending. State:

```text
target=80 promoted=0 soft_accepted=0 pending=50 in_flight=50 gap=80 forecast_ok=false
```

Operator triages 50 pending. Soft-accepts 4 across 2 cards. Rejects the rest.

```text
target=80 promoted=0 soft_accepted=4 pending=0 in_flight=4 gap=80 forecast_ok=false
```

Operator runs `promote_to_library task_id=<id>`:

```text
target=80 promoted=4 soft_accepted=0 pending=0 in_flight=0 gap=76 forecast_ok=false
```

Forecast-ok=false alerts the operator: at this rate the LLM needs many more seeds. Operator decides whether to seed more or to revise the target down.

Hours 2–6: LLM continues generating in 4 more bridge sessions. Pattern repeats. Eventually:

```text
target=80 promoted=80 soft_accepted=0 pending=0 in_flight=0 gap=0 forecast_ok=true count_satisfied=true
```

Run `accepted_set_audit` (AMood) to check `quota_satisfied`. If realized_coverage on every axis ≥ 0.75 → `fully_satisfied=true`, task `complete`. Else: priority axes flagged for the next batch.

## Commands

```text
target_summary       scope_id, scope_type ('project'|'task'|'batch'|'card') -> {target, promoted, gap, in_flight, forecast_ok, count_satisfied, quota_satisfied, fully_satisfied}
target_recount       scope_id, scope_type -> rebuild materialized counters
project_set_target_tree  project_id, groups[] -> structured target tree (sets → cards)
accepted_set_audit   batch_id (or project_id) -> per-axis realized coverage + priority flags
```

## Mid-flight target revision

Operator decides to drop the project target from 200 to 150:

```text
project_update slug=exposure-120 target_promoted=150
```

`gap` recomputes. If `promoted >= target`, `count_satisfied` flips to true. No special command needed — targets are just columns.
