# OpenRepose Intake & Triage Spec — v0.1

Version: v0.1 (DRAFT)
Authored by: WP-I3-001 (DOCUMENTATION)
Spec scope: project/task/batch hierarchy, intake staging, triage workflow, two-stage acceptance, default-staging ComfyUI bridge behavior.

This spec locks the contracts for I3 implementation WPs that build the staging surface. It composes with `openrepose_amood_v0_1.md` (data shape) and `openrepose_requirements_v0_1.md` (target tracking). Adult Production Boundary applies (`.gov/topology.yaml` `repo_rules.adult_production_boundary`).

## Purpose

A single LLM run can produce hundreds to thousands of generated images. Most of those outputs do not meet the operator's hard requirements (resolution, body type, pose, framing). Without a staging gate, raw outputs land directly in the main library and corrupt search, target counters, and accepted sets faster than the operator can clean them.

The intake surface solves this with three guarantees:

1. **Physical isolation.** Raw outputs land in `outputs/intake/<task_id>/` — a directory separate from the main library. Wholesale-reject = directory delete + DB row delete in one transaction.
2. **Two-stage acceptance.** LLMs may issue `intake_soft_accept`; only operators may issue `intake_finalize`. A single hallucinating LLM cannot poison the main library.
3. **Self-documenting surface.** Any cold-start LLM or operator reads `state.library.intake` + the manual topic `intake-and-triage.md` and can drive the triage queue without external context.

The default-staging ComfyUI bridge (specified below) makes intake the only path for new outputs. Direct library writes require an operator-issued token.

## Hierarchy

Six levels. Each level rolls counters up from the level below.

```text
Project   long-lived workstream                          library_projects
  Task    one LLM execution unit (a "960-image run")     library_tasks
    Batch AMood batch_slug (1 quota plan, 1 matrix)      library_batches
      Card moodboard card                                 library_entries (with AMood card-schema fields per amood spec)
        Run one ComfyUI generation invocation             library_runs
          Output one generated image file                 library_outputs
```

A task may span one or many batches. A batch belongs to exactly one task. A card belongs to exactly one batch. A run may produce multiple outputs (when the workflow generates a contact sheet); each output is a row.

### New tables

```sql
CREATE TABLE library_projects (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text UNIQUE NOT NULL,
  name        text NOT NULL,
  status      text NOT NULL CHECK (status IN ('active','paused','closed')),
  owner_slug  text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  closed_at   timestamptz
);

CREATE TABLE library_tasks (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      uuid NOT NULL REFERENCES library_projects(id) ON DELETE CASCADE,
  slug            text NOT NULL,
  source          text,                                       -- 'comfyui_bridge' | 'manual_import' | 'orchestrator' | ...
  llm_model       text,                                       -- free text identifier of the producing agent
  expected_count  int,                                        -- operator declares: "this run should produce N outputs"
  received_count  int NOT NULL DEFAULT 0,                     -- maintained by intake on each output insert
  status          text NOT NULL CHECK (status IN ('pending','triaging','complete','rejected_wholesale','aborted')),
  intake_dir      text NOT NULL,                              -- relative path under outputs/intake/
  summary_json    jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  finalized_at    timestamptz,
  UNIQUE (project_id, slug)
);

CREATE TABLE library_outputs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id          uuid NOT NULL REFERENCES library_runs(id) ON DELETE CASCADE,
  task_id         uuid NOT NULL REFERENCES library_tasks(id) ON DELETE CASCADE,
  file_path       text NOT NULL,                              -- relative; intake_dir or library accepted/soft_accepted dir
  content_hash    text NOT NULL,                              -- sha256, for dedup + broken-link detection
  width           int  NOT NULL,
  height          int  NOT NULL,
  status          text NOT NULL CHECK (status IN ('pending','triaging','soft_accepted','promoted','rejected','diagnostic','abandoned')),
  primary_rejection_reason text,                              -- AMood enum + project-scoped reasons
  soft_accepted_at timestamptz,
  promoted_at     timestamptz,
  rejected_at     timestamptz,
  finalized_by    text,                                       -- operator slug; populated only on stage-2 finalize
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT promotion_requires_operator CHECK (
    status <> 'promoted' OR finalized_by IS NOT NULL
  )
);

CREATE INDEX idx_library_outputs_status_pending ON library_outputs(task_id) WHERE status IN ('pending','triaging');
CREATE INDEX idx_library_outputs_status_softacc ON library_outputs(task_id) WHERE status = 'soft_accepted';
CREATE INDEX idx_library_outputs_content_hash   ON library_outputs(content_hash);
```

### FK extensions on existing I2 tables

```sql
ALTER TABLE library_runs     ADD COLUMN task_id uuid REFERENCES library_tasks(id);
ALTER TABLE library_runs     ADD COLUMN pose_guide_id uuid REFERENCES library_pose_guides(id);
ALTER TABLE library_batches  ADD COLUMN task_id uuid NOT NULL REFERENCES library_tasks(id);
ALTER TABLE library_batches  ADD COLUMN project_id uuid NOT NULL REFERENCES library_projects(id);
```

`library_pose_guides` is added by the same migration (paired pose PNG + JSON; FK from runs); details in this section's `Pose Guide Pairing` subsection below.

## Status Enum

A single enum across every level. One vocabulary in DB, GUI labels, manual prose, and command names.

```text
pending          row exists; no operator/LLM action yet
triaging         row is currently being inspected (operator active in queue)
soft_accepted    LLM-issued stage-1 accept; visible in main library tagged 'pending_operator_signoff'; library_search filters out by default
promoted         operator stage-2 finalize; fully accepted; counts toward target_promoted; appears in library_search
rejected         not accepted; remains in DB for diagnostics; file moved to <intake>/rejected/
diagnostic       kept as a teaching artifact; never counts toward target; file moved to <intake>/diagnostic/
abandoned        card-level abandonment per AMood AMOOD-002; child outputs no longer eligible for promotion
```

Allowed transitions:

```text
pending       -> triaging | rejected | diagnostic
triaging      -> soft_accepted | rejected | diagnostic
soft_accepted -> promoted (operator only) | rejected (operator only)
promoted      -> (terminal in v0.1; un-promote requires explicit demote command — out of scope)
rejected      -> (terminal)
diagnostic    -> (terminal)
abandoned     -> (terminal at card level; output rows under abandoned card become terminal pending)
```

Wholesale-reject of a task transitions all its outputs from any non-terminal state to `rejected` in one transaction and deletes the intake directory.

## Folder Layout

```text
outputs/
  intake/                                  gitignored; per-task isolated
    <YYYYMMDD>-<task_slug>/
      raw/                                 what the bridge or LLM dropped
      diagnostic/                          auto-flagged failures (auto-route severity)
      diagnostic/intermediate_evidence/    project-defined auto-route bucket (e.g. wrong resolution per EXP120-RES-001)
      contact_sheets/                      operator-generated triage helpers
      task_manifest.tsv                    DB-projection mirror; AMood-locked column order
      task.json                            DB-row mirror; recoverable
      rejected/                            outputs the operator/LLM rejected (kept for audit)
  library/                                 accepted + promoted artifacts; gitignored
    <project_slug>/
      <batch_slug>/
        ... (per openrepose_amood_v0_1.md package layout)
        soft_accepted/                     stage-1 LLM acceptances awaiting operator finalize
        accepted/                          stage-2 finalized outputs
  .runtime/                                unchanged from I2 (state, snapshots, command inbox)
```

Both `intake/` and `library/` are gitignored. The DB is the source of truth; folders are projections regenerable from DB rows.

## Triage Workflow

Three layers, designed so the operator does not face 960 individual click-decisions.

### Layer 1: Pre-flight Task Summary

When a task transitions `pending → triaging` (operator opens the queue), a one-screen summary renders:

- received vs expected count (`received_count / expected_count`)
- per-card auto-route counts (deterministic checks already routed to `diagnostic/intermediate_evidence/`)
- per-card pending count (eligible for triage)
- missing pose-guide warnings (runs with no `pose_guide_id`)
- missing prompt-manifest-row warnings
- machine-flagged obvious failures (auto-route severity)
- AMood quota progress vs target tree

Operator can wholesale-reject the task at this point if pre-flight reveals unsalvageable batch (e.g., wrong avatar, wrong workflow). One transaction, one click.

### Layer 2: Auto-prefilter

Deterministic checks (severity `auto-route`) run on every output insert. EXP120 examples:

```text
EXP120-RES-001  width == 1080 AND height == 1440  fail -> route to diagnostic/intermediate_evidence/
EXP120-RES-002  abs(width/height - 0.75) < 0.001  fail -> route to diagnostic/intermediate_evidence/
```

Auto-routed outputs do **not** count toward target_promoted, do **not** appear in the triage queue by default, but are reversible: the operator may re-route from `diagnostic/intermediate_evidence/` back to `pending` if a metadata bug mis-detected the file.

Probabilistic checks (face-age estimator, hand-sanity classifier) are advisory hints only in v0.1: color-coded in the triage view, never auto-routing. ML-backed auto-rejection is a future RESEARCH+IMPLEMENTATION WP.

### Layer 3: Per-card variant strip

For triage decisions the operator opens one card at a time. The view shows:

- the card's pose guide (PNG + skeleton)
- 4–6 paired generated outputs side-by-side at consistent crops (face crop / hands / target anatomy)
- each output's auto-route + advisory-hint status
- the per-image requirements panel (per `openrepose_requirements_v0_1.md`)
- AMood fast-triage 4 fields (adult_gate / trigger_clarity / anatomy / artifact) inline
- on fast-triage pass: full-rubric 16 fields expand
- accept/reject keystroke per output

The operator accepts the variant (multiple outputs at once) when the card is producing reliably. AMood `stability_target` (default 4) gates the card's `stable` flag; `target_promoted` (project-set, e.g. 8 for EXP120) gates `complete` flag.

## Two-Stage Acceptance

```text
LLM agents may issue:
  intake_soft_accept       output_id -> status soft_accepted
                           file moved: outputs/intake/<task_id>/raw/X.png -> outputs/library/<project>/<batch>/soft_accepted/X.png
                           library_search filters by default; explicit include_pending=true to see
  intake_reject            output_id -> status rejected
                           file moved to outputs/intake/<task_id>/rejected/

Operators only may issue:
  intake_finalize          output_id -> status promoted
                           file moved: soft_accepted/ -> accepted/
                           scorecard row written if not already present
                           target counters bumped
  promote_to_library       batch operator-only; finalizes all soft_accepted in one task

LLM agents that attempt intake_finalize receive:
  ERR cmd=intake_finalize: blocked by INTAKE-001 (two-stage acceptance).
  LLM agents may not finalize. See manual: intake-and-triage#two-stage-acceptance.
  Fix: emit intake_soft_accept; operator runs intake_finalize.
```

Operator authentication for finalize: presence of an operator-issued session token in the command payload. The token is generated at GUI session start and is not LLM-readable. Tokens are scoped to the GUI process; an LLM running headlessly never sees one.

Soft-accept is reversible. Operator may un-soft-accept (move back to triaging) until finalize. After finalize, only an explicit `library_demote` command (out of scope for v0.1) reverses it.

## Default-Staging ComfyUI Bridge

The I2 ComfyUI bridge custom node (`.product/comfyui-bridge/`) currently writes directly into the library on `register_library_entry`. I3 changes the default destination.

```text
default behavior (no operator token in payload):
  bridge POSTs intake_register_output:
    task_id:        the active task (operator-set in bridge config or LLM-supplied)
    file_path:      relative to outputs/intake/<task_id>/raw/
    metadata:       prompt, pose_guide_id, run params (sampler, cfg, steps, seed, ...)
    width, height
  effect: library_outputs row inserted with status='pending'; auto-route checks fire
  
direct library write (operator token supplied):
  bridge POSTs register_library_entry directly (existing I2 path)
  use case: operator using ComfyUI for ad-hoc non-batch work; bypasses intake intentionally

without task_id and without operator token:
  bridge refuses with citation:
  ERR INTAKE-002 (default intake target). ComfyUI bridge writes to intake unless operator token allows direct library.
  Fix: set OPENREPOSE_TASK_ID environment variable or ask operator for direct-write token.
```

The bridge custom node is updated to read `OPENREPOSE_TASK_ID` from environment and embed it in every POST. Operators set this when starting ComfyUI for a specific batch run.

## Triage Commands

All commands return responses with `adult_production_boundary` envelope (per WP-I3-002).

```text
project_create     slug, name, owner_slug -> project_id
project_list       (optional filter status) -> [projects with counters]

task_create        project_id, slug, expected_count, source, llm_model -> task_id, intake_dir
task_list          (optional status filter) -> [tasks with received/expected/gap]
task_summary       task_id -> pre-flight summary (counters, warnings, requirements pass/fail summary)
task_inspect       task_id -> task row + linked batches + linked runs

intake_list        task_id, status filter, limit, offset -> [output rows]
intake_inspect     output_id -> output row + paired pose guide path + card metadata + scorecard skeleton + requirements panel
intake_soft_accept output_id [, scorecard fields] -> status soft_accepted; LLM-issuable
intake_reject      output_id, primary_rejection_reason [, notes] -> status rejected; LLM-issuable
intake_finalize    output_id -> status promoted; OPERATOR-ONLY (token-gated)
promote_to_library task_id -> bulk-finalize all soft_accepted; OPERATOR-ONLY

task_reject_wholesale task_id, reason -> all non-terminal outputs to rejected; intake_dir deleted via /safe-delete; OPERATOR-ONLY

intake_register_output  task_id, file_path, metadata, width, height -> output_id; ComfyUI bridge entrypoint
intake_reroute          output_id, target_status ('pending'|'diagnostic'|'rejected') -> status update; auto-route reversal path
```

## Self-Documenting Surface

State block:

```json
{
  "library": {
    "intake": {
      "active_task_id": "<uuid or null>",
      "active_task_slug": "<slug>",
      "received_count": 960,
      "pending_count": 41,
      "soft_accepted_count": 7,
      "promoted_count": 12,
      "rejected_count": 880,
      "diagnostic_count": 20,
      "current_card_id": "<uuid or null>",
      "queue_depth": 41
    },
    "guidance": {
      "current_focus": "task T-2026-05-03-01: triage 41 pending",
      "next_valid_actions": ["intake_inspect", "intake_soft_accept", "intake_reject"],
      "active_rules": ["INTAKE-001", "INTAKE-002", "AMOOD-001"],
      "manual_index": ".gov/doc/manual/index.md",
      "topic_pointers": {
        "intake": ".gov/doc/manual/intake-and-triage.md",
        "amood":  ".gov/doc/manual/amood-workflow.md"
      }
    }
  }
}
```

The `guidance` block is capped ~20 lines. Deeper detail is reachable via the manual links. Per `openrepose_rules_v0_1.md`, rule_ids cited in `active_rules` resolve to manual topic anchors.

## Snapshot Targets

Three new headless-compliant snapshot targets:

```text
intake_triage_view        renders the current triage screen (queue + selected output + variant strip)
task_summary_view         renders the pre-flight task summary
library_card_with_pose    renders any card detail with paired pose guide (also used by amood spec)
```

All follow snapshot-subsystem rules (no `raise_()`, no focus theft).

## Pose Guide Pairing

A new table holds pose guides as first-class artifacts.

```sql
CREATE TABLE library_pose_guides (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  guide_type   text NOT NULL CHECK (guide_type IN ('openpose','dwpose','depth','canny','segmentation','mask')),
  png_path     text NOT NULL,
  json_path    text NOT NULL,
  source_path  text,                         -- e.g. originating frontal portrait
  content_hash text NOT NULL,                -- sha256 of (png + json) for broken-link detection
  card_id      uuid REFERENCES library_entries(id),
  batch_id     uuid REFERENCES library_batches(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (content_hash)
);

CREATE INDEX idx_library_pose_guides_card  ON library_pose_guides(card_id)  WHERE card_id  IS NOT NULL;
CREATE INDEX idx_library_pose_guides_batch ON library_pose_guides(batch_id) WHERE batch_id IS NOT NULL;
```

The yaw exporter (Feature 1) registers a pose guide on every PNG+JSON export. Triage view fetches both file paths from `library_runs.pose_guide_id` rather than name-matching. Broken-link detection compares the on-disk file hash against `content_hash` and surfaces warnings in the Library tab.

## Rule Citations

```text
INTAKE-001   two-stage acceptance: LLM may soft_accept; only operator may finalize     severity: block
INTAKE-002   default intake target: ComfyUI bridge writes to intake without operator token  severity: block
INTAKE-003   per-task isolation: wholesale reject = directory delete + DB row delete in one transaction  severity: info
INTAKE-004   library_search excludes status='pending' by default (explicit include_pending=true to see)   severity: info
```

## Out Of Scope For v0.1

- ML-backed auto-prefilter (probabilistic adult-gate, hand-sanity, anatomy classifiers).
- Library demotion / un-promote (`library_demote` command).
- Cross-task output deduplication via content_hash beyond same-task.
- Multi-machine intake sharing (single-machine-Postgres scope; multi-machine is a future spec).
- Streaming bridge mode where the LLM watches `intake_register_output` events live (v0.1 is poll-based via `intake_list`).
- Operator override of CHECK constraints (juvenile/coercive/hidden-camera promotion is impossible at DB level; no override path).

## Reality Boundary For v0.1

- **Real Seam**: 3 new tables (`library_projects`, `library_tasks`, `library_outputs`), 1 supporting table (`library_pose_guides`), 4 FK extensions on existing tables, 16 new dispatcher commands, default-staging bridge change, four rule_ids in registry (INTAKE-001..004), unified status enum across the entire hierarchy, 3 new snapshot targets, `state.library.intake` + `state.library.guidance` blocks.
- **User-Visible Win**: an LLM running a 960-image task drops outputs into intake by default; operator opens GUI, sees pre-flight summary, runs auto-prefilter (deterministic checks already done), iterates through per-card variant strips, soft-accepts and finalizes; bad task can be wholesale-rejected in one click + transaction; main library never contaminates.
- **Proof Target**: I3 IMPLEMENTATION WPs cite this spec by anchor; pytest covers two-stage CHECK constraint, wholesale-reject transactional rollback, advisory-lock under concurrent intake registrations (uses I2-008 pattern); end-to-end test runs a 50-output mock task through bridge → intake → triage → soft_accept → finalize → library; library_search filters pending by default with passing `include_pending=true`.
- **Allowed Temporary Fallbacks**: probabilistic auto-prefilter is advisory only; bridge default-staging migration may keep the direct-write path for one I3 IMPLEMENTATION WP cycle behind an `OPENREPOSE_LEGACY_DIRECT_WRITE=1` flag, removed in the next WP. Mark with FALLBACK comments per Workflow Version 1.1.
- **Promotion Guard**: do not declare intake v0.1 stable until: (a) operator processes one full EXP120-style task end-to-end (bridge → triage → finalize) with all 4 layers exercised, (b) `task_reject_wholesale` correctly rolls back ≥100 outputs in one transaction without orphan files, (c) auto-route reversal path tested with a deliberately mis-detected metadata case.
