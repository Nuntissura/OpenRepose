# Feature 3 — OpenPose library + ComfyUI coupling

The third feature, **partially implemented** (I2 iteration in progress). Spec: `.gov/spec/openrepose_library_v0_1.md`.

Status (2026-05-03):

- **WP-I2-001 (REVIEW)**: PostgreSQL pool, hand-rolled migrator, initial schema (`001_library_initial.sql`), `state.library` block, `docker-compose.yml`.
- **WP-I2-002 (REVIEW)**: Settings v2 (`library_db_url`, `library_root`, `operator_slug`); v1 migration; Options pane Library section; redacted DSN in `dump_settings`.
- **WP-I2-003 (REVIEW)**: Library data layer (`openrepose.library` package): CRUD on `library_entries`, M-to-N tags, smart-tag extractor, filesystem storage layout under `outputs/library/<entry-uuid>/`.
- WP-I2-004..008 still drafted; LLM commands, ComfyUI bridge, GUI, snapshots, and verification land sequentially.

## What it will do

Operator-curated library of exported OpenPose wireframes alongside the downstream production artifacts they enabled (rendered images, ComfyUI workflows, prompts, story beats, notes), backed by **PostgreSQL** for multi-operator concurrent use.

## Storage backend

- **PostgreSQL** ≥ 16 (native or via `docker compose up -d postgres`).
- **psycopg 3** Python client with `psycopg_pool` connection pool.
- Hand-rolled SQL migrations in `.product/migrations/NNN_*.sql`.

## Schema

7 tables: `library_entries`, `tags`, `entry_tags`, `prompts`, `story_beats`, `notes`, `schema_version`.

One `library_search()` SQL function combines `pg_trgm` trigram fuzzy match (titles + tags) with `tsvector` full-text search (prompts + story_beats + notes) at weighted ranks.

## Smart tags (WP-I2-003)

When an entry is registered (operator-side or via the future ComfyUI bridge), the dispatcher derives **`auto:` tags** from the workflow JSON + run metadata so the operator can search for them later without manual tagging.

| Family | Source | Example |
|--------|--------|---------|
| `auto:model:<name>` | First `CheckpointLoaderSimple` node | `auto:model:fluxdev_v2.safetensors` |
| `auto:sampler:<name>` | First `KSampler` node `sampler_name` | `auto:sampler:dpmpp_2m` |
| `auto:scheduler:<name>` | First `KSampler` node `scheduler` | `auto:scheduler:karras` |
| `auto:lora:<name>` | Each `LoraLoader` node `lora_name` | `auto:lora:intimate-style-v3.safetensors` |
| `auto:custom_node:<class>` | Every unique node `class_type` in the workflow | `auto:custom_node:vaeloader` |
| `auto:cfg:` / `auto:steps:` / `auto:seed:` | Run metadata supplied alongside the workflow | `auto:cfg:6.5` |

Smart tags are preserved across `set_library_tags(replace=true)` so a manual re-tag does not blow away the auto-derivation. Operators that *want* the auto tags gone pass `preserve_auto=false` (Library tab UI provides a one-click toggle in WP-I2-006).

## Storage layout

Per-entry files live under the configured library root (`Settings.library_root`, defaults to `<export_folder>/library/`):

```
outputs/library/<entry-uuid>/
  portrait.png       (operator's source / reference image)
  openpose.json      (the OpenPose-format JSON)
  openpose.png       (the rendered wireframe)
  generated.png      (downstream image from ComfyUI)
  workflow.json      (a copy of the ComfyUI workflow JSON; DB also stores it as JSONB)
  metadata.json      (mirror of the DB metadata column for offline inspection)
```

Each file is written atomically (write to `*.tmp`, rename) so an in-flight registration cannot leave a half-flushed file behind. The DB stores filesystem paths relative to `library_root` for portability across drives.

## ComfyUI bridge

`.product/comfyui-bridge/` ships a custom node that POSTs to OpenRepose's localhost HTTP control surface (`/command` → `register_library_entry`) after each successful image save. Bundles workflow JSON + image + prompts + smart-tags (auto-extracted from the workflow node graph).

## Multi-operator

- Connection pool min_size=4, max_size=10.
- Row-level locks (`SELECT ... FOR UPDATE NOWAIT`) on entry edits.
- Optimistic concurrency (`WHERE updated_at = ...`) on bulk re-tag operations.

## Implementation tracker

WP-I2-001..008 in `.gov/workflow/workpackets/`.
