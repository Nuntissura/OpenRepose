# Feature 3 — OpenPose library + ComfyUI coupling

The third feature, **drafted but not yet implemented** (I2 iteration). Spec: `.gov/spec/openrepose_library_v0_1.md`.

## What it will do

Operator-curated library of exported OpenPose wireframes alongside the downstream production artifacts they enabled (rendered images, ComfyUI workflows, prompts, story beats, notes), backed by **PostgreSQL** for multi-operator concurrent use.

## Storage backend

- **PostgreSQL** ≥ 16 (native or via `docker compose up -d postgres`).
- **psycopg 3** Python client with `psycopg_pool` connection pool.
- Hand-rolled SQL migrations in `.product/migrations/NNN_*.sql`.

## Schema

7 tables: `library_entries`, `tags`, `entry_tags`, `prompts`, `story_beats`, `notes`, `schema_version`.

One `library_search()` SQL function combines `pg_trgm` trigram fuzzy match (titles + tags) with `tsvector` full-text search (prompts + story_beats + notes) at weighted ranks.

## ComfyUI bridge

`.product/comfyui-bridge/` ships a custom node that POSTs to OpenRepose's localhost HTTP control surface (`/command` → `register_library_entry`) after each successful image save. Bundles workflow JSON + image + prompts + smart-tags (auto-extracted from the workflow node graph).

## Multi-operator

- Connection pool min_size=4, max_size=10.
- Row-level locks (`SELECT ... FOR UPDATE NOWAIT`) on entry edits.
- Optimistic concurrency (`WHERE updated_at = ...`) on bulk re-tag operations.

## Implementation tracker

WP-I2-001..008 in `.gov/workflow/workpackets/`.
