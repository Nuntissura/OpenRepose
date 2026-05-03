# AMood prompting in the Library

AMood in OpenRepose means richer prompt and task context attached to Library entries. It is not a separate package root and not a planning document. Its job is to make large adult-production batches searchable and reviewable by project, task, workflow, prompt intent, OpenPose guide, generated image, and review result.

Use this page when operating OpenRepose or when an LLM agent is registering, searching, or reviewing Library entries. You do not need to read the long AMood reference file to use this workflow.

## Core idea

Every useful generated image should answer four questions inside the Library:

1. Which project did this belong to?
2. Which task or prompt batch produced it?
3. Which workflow/model setup generated it?
4. Which OpenPose guide, prompt requirements, and review decision went with it?

OpenRepose stores the image/OpenPose pair as a Library entry. AMood context is the structured task requirement data attached to that entry through tags, prompts, story beats, notes, workflow JSON, and metadata.

## Operator workflow

1. Create or choose a production task before generating.
2. Define the task requirements: project, task, workflow, avatar, adult target, required inclusions, avoid list, diversity axes, and acceptance gates.
3. Export or choose the OpenPose guide for the task.
4. Generate in ComfyUI with the OpenRepose Bridge enabled.
5. Register the generated image, OpenPose PNG/JSON, prompts, workflow JSON, task tags, and task requirements into the Library.
6. In the Library tab, search by project, task, workflow, avatar, yaw bin, prompt family, model, LoRA, or review result.
7. Open entries side by side to compare the OpenPose guide with the generated image and inspect the prompt/task context.
8. Record the review decision in tags and metadata so accepted, rejected, and diagnostic outputs stay searchable.

## Required task fields

Use these fields for every task-oriented entry. They may be stored in metadata and repeated in notes for human readability.

```text
project_slug:
task_slug:
workflow_slug:
task_title:
avatar_slug:
yaw_bin:
production_goal:
adult_target:
target_count:
must_include:
must_avoid:
diversity_axes:
prompt_strategy:
pose_requirements:
acceptance_gates:
known_failure_modes:
review_decision:
```

Keep slugs lowercase and hyphenated. Use OpenRepose yaw terms only: `0`, `her-left N`, `her-right N`.

## Tag conventions

Tags are the fastest way to view work by project, task, and workflow.

```text
project:<project-slug>
task:<task-slug>
workflow:<workflow-slug>
avatar:<avatar-slug>
pose:<yaw-bin>
prompt_family:<family-slug>
target:<target-slug>
variant:<variant-slug>
decision:accepted
decision:rejected
decision:diagnostic
```

Examples:

```text
project:aeri-library
task:hotel-reveal-batch-01
workflow:pony-openpose-v1
avatar:aeri
pose:her-right-30
variant:baseline
decision:accepted
```

Auto tags from the ComfyUI bridge may also appear, such as model, sampler, LoRA, seed, steps, CFG, and custom-node tags. Keep those; they make workflow-level search useful.

## Where context goes

Use the Library entry fields consistently:

| Context | Store in |
|---------|----------|
| Generated image | `generated_image` |
| OpenPose wireframe PNG | `openpose_png` |
| OpenPose keypoint JSON | `openpose_json` |
| Positive prompt | `prompts.positive` |
| Negative prompt | `prompts.negative` |
| Task requirement summary | `story_beats` |
| Review notes and failure notes | `notes` |
| Project/task/workflow IDs | `tags` and `metadata` |
| ComfyUI graph and model settings | `comfyui_workflow` and `metadata` |

The Library should be the normal place to view the relationship between the image, OpenPose guide, prompt, task, workflow, and review result.

## LLM registration pattern

An LLM agent should register entries through the command surface instead of writing database rows directly.

```json
{
  "command": "register_library_entry",
  "avatar_slug": "aeri",
  "title": "hotel reveal batch 01 baseline seed 12345",
  "yaw_bin": "her-right-30",
  "openpose_json_path": "operator-supplied-path",
  "openpose_png_path": "operator-supplied-path",
  "generated_image_path": "operator-supplied-path",
  "prompts": {
    "positive": "task-aligned positive prompt text",
    "negative": "task-aligned negative prompt text"
  },
  "story_beats": [
    "Task requirements: project=aeri-library; task=hotel-reveal-batch-01; workflow=pony-openpose-v1; production_goal=large-batch diversity test; must_include=clear adult target, matching pose guide, consistent avatar; must_avoid=blocked target, anatomy failure, identity drift."
  ],
  "notes": [
    "Review pending. Score after visual inspection."
  ],
  "tags": [
    "project:aeri-library",
    "task:hotel-reveal-batch-01",
    "workflow:pony-openpose-v1",
    "avatar:aeri",
    "pose:her-right-30",
    "variant:baseline",
    "decision:diagnostic"
  ],
  "metadata": {
    "project_slug": "aeri-library",
    "task_slug": "hotel-reveal-batch-01",
    "workflow_slug": "pony-openpose-v1",
    "production_goal": "large-batch diversity test",
    "adult_target": "operator-defined adult target",
    "target_count": 40,
    "diversity_axes": ["setting", "pose", "camera", "wardrobe", "lighting"],
    "acceptance_gates": ["adult subject", "target visible", "pose matches guide", "anatomy coherent", "identity preserved"],
    "review_decision": "diagnostic"
  }
}
```

Use real relative paths or base64 fields as supported by the command. Do not hardcode machine-specific paths into committed docs or scripts.

## LLM search patterns

Use one primary grouping term per search. For combined review work, search the task or workflow first, then inspect tags on the returned entries.

Search by task:

```json
{
  "command": "library_search",
  "query": "task:hotel-reveal-batch-01",
  "limit": 50
}
```

Search by workflow:

```json
{
  "command": "library_search",
  "query": "workflow:pony-openpose-v1",
  "limit": 50
}
```

Search by avatar:

```json
{
  "command": "library_search",
  "query": "avatar:aeri",
  "limit": 50
}
```

Search by yaw bin:

```json
{
  "command": "library_search",
  "query": "pose:her-right-30",
  "limit": 50
}
```

After a search, use `get_library_entry` to inspect prompts, story beats, notes, workflow, metadata, and file paths for the selected entry.

## Review update pattern

After visual review, update the entry so future searches know whether it worked. First update the decision tag:

```json
{
  "command": "set_library_tags",
  "entry_id": "<entry-id>",
  "replace": false,
  "tags": [
    "decision:accepted"
  ]
}
```

Then fetch the entry, merge the existing metadata locally, and write the full merged metadata object back. `update_library_entry` replaces the metadata object it receives; it does not merge nested keys for you.

```json
{
  "command": "update_library_entry",
  "entry_id": "<entry-id>",
  "metadata": {
    "project_slug": "aeri-library",
    "task_slug": "hotel-reveal-batch-01",
    "workflow_slug": "pony-openpose-v1",
    "review_decision": "accepted",
    "review_score": 4,
    "review_note": "Accepted: OpenPose guide matched, adult target readable, identity stable, no major anatomy failure."
  }
}
```

Use `decision:rejected` when the output fails the task. Use `decision:diagnostic` for outputs kept only to explain a failure mode. Detailed notes can be added at registration time through the `notes` field and read later with `get_library_entry`.

## Filesystem rule

For normal operation, browse images and OpenPose files through the Library tab. The filesystem is still useful for backup and external tools, but OpenRepose should be the operator-facing index.

Library entry files live under the configured Library root. Each entry keeps its OpenPose PNG/JSON, generated image, workflow JSON, and metadata together. The database stores portable paths relative to that root.

Do not create a separate manual AMood folder as the source of truth for active OpenRepose work. If a batch started outside OpenRepose, register its images, OpenPose files, prompts, task tags, and requirements into the Library so it becomes searchable by project, task, and workflow.

## Good entry standard

A task-ready Library entry is complete when it has:

- generated image
- OpenPose PNG and JSON, when a pose guide was used
- project, task, workflow, avatar, and yaw tags
- positive and negative prompts
- task requirement summary
- ComfyUI workflow or run metadata
- review decision tag
- review note explaining why it was accepted, rejected, or kept for diagnostics

Entries missing this context may still be useful, but they are not complete task records.

## Commands

The seven AMood-specific dispatcher commands (WP-I3-006). All return responses with the `adult_production_boundary` envelope. See `intake-and-triage.md` for the project/task layer underneath; AMood batches sit on top of that hierarchy.

| Command | LLM-issuable | Effect |
|---------|--------------|--------|
| `init_batch_package` | yes | Creates a `library_batches` row + folder layout under `outputs/library/<project_slug>/<batch_slug>/`. Idempotent: re-running reports diffs without overwriting. |
| `library_create_card` | yes | Inserts an AMood-shaped `library_entries` row. Calls `library.dedupe_check` before INSERT; emits AMOOD-001 citation when overlap >= threshold. |
| `library_create_variants` | yes | Spawns child cards with `parent_card_id` FK + `variant_label`. Default change-rules for `baseline`/`intimate`/`explicit_plus`; stub for `editorial`/`raw_cam`/`story_plus`. |
| `compatibility_check` | yes | Runs the AMood compatibility truth table; cites SAFE-001/002/003 on safety boundaries (juvenile / coercion / hidden-camera) and AMOOD-004 on moodboard hard-rejects. |
| `accepted_set_audit` | yes | Writes `library_diversity_audits` rows for the 13 amood:* tag axes; priority flag `>= 0.75 ok / 0.5..0.74 watch / < 0.5 priority`. |
| `amood_export_tsv` | yes | Returns TAB-separated text in AMood-locked column order for one of 10 view schemas. |
| `amood_import_tsv` | yes | Parses TSV in locked column order; upserts to underlying tables. v0.1 supports import for 4 hand-edited schemas (`quota_plan`, `batch_matrix`, `variant_ladder`, `anti_repetition`); 6 system-generated schemas return INFO. |

### init_batch_package example

```json
{
  "command": "init_batch_package",
  "project_slug": "exposure-120",
  "batch_slug": "hotel-robes",
  "task_id": "<uuid from task_create>",
  "tier": "production",
  "primary_explicit_family": "vulva-pussy-exposure",
  "dedupe_threshold": 6
}
```

Response includes `created` (true on first run, false on idempotent re-run), `package_path`, and `layout_diffs` (empty when the folder tree matches the canonical shape).

### library_create_card example

```json
{
  "command": "library_create_card",
  "batch_id": "<uuid>",
  "avatar_slug": "aeri",
  "slug": "hotel-robe-bed-edge",
  "sexual_trigger": "visible vulva exposure",
  "kink_cue": "self-display",
  "porn_archetype": "hotel robe reveal",
  "fantasy_mode": "casual intimate",
  "explicit_family": "vulva/pussy exposure",
  "exposure_detail": "full target visible",
  "pose_family": "bed-edge lean",
  "orientation": "three-quarter front",
  "wardrobe_state": "robe open",
  "support_object": "bed edge",
  "setting_family": "luxury hotel",
  "camera_family": "eye-level full-body",
  "palette_family": "warm hotel amber"
}
```

Response includes `card_id`, `dedupe_signature` (8-axis pipe-delimited canonical), `compatibility_signature`, `dedupe_match` (matching cards with overlap_count >= threshold), and `compatibility_warnings`. When overlap is found, the response also includes `amood_001_citation` with the canonical AMOOD-001 error shape.

### AMOOD-001 citation example

```text
ERR cmd=library_create_card: warned by AMOOD-001 (anti-repetition threshold): >= 6 axis overlap with accepted card requires revision; project-overridable.
See manual: amood-workflow.md#anti-repetition.
Fix: revise card before promoting; overlaps 7/8 with 'hotel-robe-bed-edge'; raise dedupe_threshold for the batch if intentional.
```

### TSV round-trip

The 10 TSV schemas live as DB views (migration 005) in AMood-locked column order. Export reads the view; import parses TSV in the same column order back to underlying tables. Round-trip is bytewise lossless on the 4 hand-edited schemas.

```text
quota_plan          batch-level axis-value quotas; project_id-scoped via library_target_groups
batch_matrix        per-card matrix row (43 columns); covers all blueprint card axes
variant_ladder      variant change-rule rows (parent + child cards)
anti_repetition     per-card dedupe signature + axes; ledger for batches > 24 cards
prompt_manifest     export-only; rendered from library_entries + prompts table
run_manifest        export-only; rendered from library_runs + library_outputs
review_manifest     export-only; rendered from library_scorecards + library_outputs
scorecard           export-only; rendered from library_scorecards
pose_control_guide  export-only; rendered from library_pose_guides
series_plan         export-only; rendered from library_entries.metadata 'amood:series_id'
```

Additive-only rule: future migrations may append columns on the right; never reorder, rename, or drop existing columns. The migration uses `CREATE OR REPLACE VIEW` which enforces this at the SQL layer.

## anti-repetition

Two cards in the same project that share too many dedupe-signature axes produce visually similar outputs. AMOOD-001 surfaces this as a warning (severity: `warn`) so the operator can revise before promoting.

```text
Threshold default:    6 of 8 axes overlap
Threshold range:      4..8 (per batch, on library_batches.dedupe_threshold)
Status filter:        only soft_accepted + promoted cards drive the dedupe surface
Override path:        none for v0.1; revise the card OR raise the batch threshold
```

The 8 dedupe axes are: `explicit_family | pose_family | orientation | wardrobe_state | support_object | setting_family | camera_family | palette_family`.

## abandonment-criteria

Per AMOOD-002 (warn): a card is abandonment-eligible after 12 seeds with `trigger_clarity_score < 4`, or after 8 seeds with repeated structural failure (anatomy / wardrobe / pose). Card-level abandonment writes `library_entries.abandoned_after_seeds` + `abandonment_reason`.

```text
trigger_fights_model      the trigger keeps colliding with the model's bias
pose_needs_guide          unguided pose drifts; needs explicit pose guide
wardrobe_incompatible     wardrobe mechanism doesn't read with this trigger
identity_drift            avatar identity not preserved across seeds
duplicate_scene           re-runs of the same scene aren't producing diversity
safety_boundary           SAFE-001/002/003 boundary fired (no override path)
```

## fast-triage

Per AMOOD-003 (warn): a row is rejected before the full 16-field rubric runs when any of these 4 fields fails:

```text
adult_gate_score        < 5  (must read clearly as adult)
trigger_clarity_score   < 4  (the sexual trigger must be readable)
anatomy_score           < 3  (anatomy must be coherent)
artifact_score          < 4  (no major AI artifacts)
```

Fast-triage is a CHECK constraint on `library_scorecards`: a `promote` decision is rejected at DB level when any of these scores is below the bar. The full rubric (12 more fields) only runs after fast-triage passes.

## safety-boundary

Per SAFE-001 / SAFE-002 / SAFE-003 (block, no override path): juvenile-coded, coercion-coded, or hidden-camera-coded outputs cannot be promoted. The DB enforces this with three CHECK constraints on `library_scorecards`:

```text
SAFE-001  primary_rejection_reason='juvenile_coded'  -> cannot promote
SAFE-002  primary_rejection_reason='coercion_coded'   -> cannot promote
SAFE-003  primary_rejection_reason='hidden_camera_coded' -> cannot promote
```

Card-level abandonment is the prescribed response (per AMOOD-002), not just seed-level rejection.
