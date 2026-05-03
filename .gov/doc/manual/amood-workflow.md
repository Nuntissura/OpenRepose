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
