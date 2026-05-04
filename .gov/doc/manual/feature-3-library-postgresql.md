# Feature 3 — OpenPose library + ComfyUI coupling

The third feature is implemented and I2 is closed. Spec: `.gov/spec/openrepose_library_v0_1.md`.

Status (2026-05-04):

- **WP-I2-001 (DONE)**: PostgreSQL pool, hand-rolled migrator, initial schema (`001_library_initial.sql`), `state.library` block, `docker-compose.yml`.
- **WP-I2-002 (DONE)**: Settings v2 (`library_db_url`, `library_root`, `operator_slug`); v1 migration; Options pane Library section; redacted DSN in `dump_settings`.
- **WP-I2-003 (DONE)**: Library data layer (`openrepose.library` package): CRUD on `library_entries`, M-to-N tags, smart-tag extractor, filesystem storage layout under `outputs/library/<entry-uuid>/`.
- **WP-I2-004 (DONE)**: 7 LLM commands wired into the dispatcher (`register_library_entry`, `update_library_entry`, `delete_library_entry`, `library_search`, `get_library_entry`, `set_library_tags`, `dump_library_schema`); prompts / story_beats / notes helpers; `library_search()` Python wrapper; state.library activity tracking.
- **WP-I2-005 (DONE)**: ComfyUI bridge custom node under `.product/comfyui-bridge/` — POSTs `register_library_entry` after each image save; stdlib-only on ComfyUI side; non-blocking on POST failure.
- **WP-I2-006 (DONE)**: Library tab GUI in OpenRepose — search bar, entry list, side-by-side detail, six sub-tabs (Tags / Prompts / Story / Notes / Workflow / Metadata).
- **WP-I2-007 (DONE)**: Two snapshot targets — `library_entry` (side-by-side openpose + reference for the most recently fetched entry) and `library_search_results` (4×6 thumbnail grid of the most recent search).
- **WP-I2-008 (DONE)**: Closed I2 — multi-operator concurrency tests, 100-entry soak, `pg_dump` round-trip, and the operator setup guide at `.gov/doc/i2-library-setup.md`.

## What it does

Operator-curated library of exported OpenPose wireframes alongside the downstream production artifacts they enabled (rendered images, ComfyUI workflows, prompts, story beats, notes), backed by **PostgreSQL** for multi-operator concurrent use.

## Storage backend

- **PostgreSQL** ≥ 16 (native or via `docker compose up -d postgres`).
- **psycopg 3** Python client with `psycopg_pool` connection pool.
- Hand-rolled SQL migrations in `.product/migrations/NNN_*.sql`.

## Schema

7 tables: `library_entries`, `tags`, `entry_tags`, `prompts`, `story_beats`, `notes`, `schema_version`.

One `library_search()` SQL function combines `pg_trgm` trigram fuzzy match (titles + tags) with `tsvector` full-text search (prompts + story_beats + notes) at weighted ranks.

## Smart tags (WP-I2-003)

When an entry is registered (operator-side or via the ComfyUI bridge), the dispatcher derives **`auto:` tags** from the workflow JSON + run metadata so the operator can search for them later without manual tagging.

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

## LLM commands (WP-I2-004)

The dispatcher exposes seven library commands over the existing HTTP + inbox channels. All accept the standard `{ "command": "<name>", ... }` envelope; failures land as `{ "status": "error", "payload": { "reason": "...", "type": "OpenReposeLibraryError" } }`.

| Command | Required fields | Notes |
|---------|-----------------|-------|
| `register_library_entry` | `avatar_slug` | Either `*_path` (existing files) **or** `*` (base64 bytes) for `portrait` / `openpose_json` / `openpose_png` / `generated_image`. Optional: `comfyui_workflow`, `metadata`, `tags`, `prompts {positive, negative}`, `story_beats` (str or list), `notes` (str or list). Auto-applies smart tags. Returns `{entry_id, created_at, smart_tags}`. |
| `update_library_entry` | `entry_id` + ≥1 patch field | Acquires `SELECT … FOR UPDATE NOWAIT`. Lock contention returns a structured error containing `retry_after`; the entry is added to `state.library.locked_entries`. |
| `delete_library_entry` | `entry_id` | Cascades to tags / prompts / beats / notes via FKs. Removes the `outputs/library/<entry-uuid>/` folder. Returns `{entry_id, deleted}`. |
| `library_search` | `query` (non-empty) | Optional `limit` (default 50, max 200). Returns `{query, count, results[]}` ranked by `library_search()`. |
| `get_library_entry` | `entry_id` | Optional `include` list (`tags`, `prompts`, `story_beats`, `notes`, `workflow`, `metadata`); defaults to all but workflow / metadata. |
| `set_library_tags` | `entry_id`, `tags[]` | Optional `replace` (default false). With `replace=true`, manual tags are dropped but `auto:` tags are preserved per spec. |
| `dump_library_schema` | – | Returns `{schema_version, tables[], functions[], ddl_hash}` so an LLM agent can verify drift against source control. |

State reflection (`outputs/.runtime/state.json` → `library`):

- `last_register_at`, `last_search_query`, `last_search_count`, `last_search_at` — filled by the corresponding command handlers.
- `locked_entries` — momentary list of entries that another operator's transaction is holding; consumed by the GUI lock indicator.

## Snapshots (WP-I2-007)

The snapshot subsystem gains two new targets so an LLM agent can pull a visual artifact of the Library tab state without touching operator focus.

| Target | Source | Notes |
|--------|--------|-------|
| `library_entry` | `state.library.last_entry` (set by `get_library_entry`) | Side-by-side openpose.png + generated.png / portrait.png + a header strip with title / avatar / yaw_bin and the lock indicator. |
| `library_search_results` | `state.library.last_search_results` (set by `library_search`, top 24) | 4×6 thumbnail grid; each cell shows the entry's openpose.png (preferred) or generated.png with the title underneath. |

Both targets honor the existing snapshot rules: no `raise_/activateWindow/showNormal`; atomic write to `outputs/.runtime/snapshots/`; manifest line appended to `outputs/.runtime/snapshots.jsonl`.

## ComfyUI bridge (WP-I2-005)

`.product/comfyui-bridge/` ships a custom node — **OpenRepose Bridge (Save + Register)** — that POSTs to OpenRepose's localhost HTTP control surface (`/command` → `register_library_entry`) after each successful image save. Bundles workflow JSON + image bytes (base64) + auto-extracted prompts + smart-tag-able metadata (`model`, `sampler`, `seed`, `steps`, `cfg`, `lora`, `custom_node`) + operator-supplied tags. See `.product/comfyui-bridge/README.md` for install instructions and node-input fields.

Failures POSTing to OpenRepose log a `WARN openrepose_bridge.post_failed` to ComfyUI's console but never block image generation (per spec).

## Library tab (WP-I2-006)

The OpenRepose GUI gains a top-level **Library** tab between **Tools** and **Options**:

- **Search bar** — fuzzy match on titles + tags via `pg_trgm`; full-text on prompts / story_beats / notes via `tsvector`. Press Enter or click *Search* to run; *Refresh* re-runs the last query.
- **Entry list (left, 1/3 width)** — each row shows `<title> [<avatar>·<yaw_bin>] ·<top_tags>`. Greyed rows mean another operator currently holds the row lock (tooltip: "Locked by <operator>").
- **Detail pane (right, 2/3 width)** —
  - Header strip with title + avatar + yaw_bin + lock indicator + Delete button.
  - Side-by-side previews: openpose.png on the left, generated.png / portrait.png on the right; missing files show a labeled placeholder.
  - Six sub-tabs: **Tags** (chip view + Add / Replace), **Prompts** (latest revision shown), **Story** (beats list, newest first), **Notes** (operator notes list), **Workflow** (read-only JSON tree), **Metadata** (read-only JSON tree).
- **Import OpenPose…** — operator-triggered file picker; registers a new library entry referencing the chosen OpenPose JSON path. (LLM agents use the dispatcher commands directly.)

Every operator action issues the corresponding WP-I2-004 command, so the headless code path and the GUI code path are identical. No `raise_/activateWindow/showNormal` from any callback.

## Multi-operator

- Connection pool min_size=4, max_size=10.
- Row-level locks (`SELECT ... FOR UPDATE NOWAIT`) on entry edits.
- Optimistic concurrency (`WHERE updated_at = ...`) on bulk re-tag operations.

## Implementation tracker

WP-I2-001..008 are archived under `.gov/workflow/archive/` after operator sign-off.
