# OpenRepose Spec - Feature 3: OpenPose Library + ComfyUI Coupling

**Spec file:** `openrepose_library_v0_1.md`
**Status:** DRAFT
**Authored by:** WP-I1-033 (Feature 3 spec).
**Implementation:** I2 iteration WPs (not yet drafted).
**Companion specs:** `openrepose_v0_1.md` (Features 1 + 2; cross-cutting application contract).

---

## Purpose

OpenRepose's first two features ship rigs and calibrated wireframes. Feature 3 adds an **operator-curated library** of those wireframes alongside the downstream production artifacts they enabled (rendered images, ComfyUI workflows, prompts, story beats, notes), backed by a **PostgreSQL** database for multi-operator concurrent use.

The library answers two operator questions that Features 1 + 2 cannot:

1. *"Which exported pose did I use for this generated image, and what prompt / workflow / settings produced it?"*
2. *"Show me every pose tagged `subject:aeri`, `pose:her-right-30`, `mood:intimate` so I can pick one to reuse."*

The library couples bidirectionally with **ComfyUI**: a custom node `comfyui-openrepose-bridge` shipped under `.product/comfyui-bridge/` POSTs to OpenRepose's existing localhost HTTP control surface (`/command` endpoint, `register_library_entry`) on every successful image generation, bundling the workflow JSON + final image + tags + metadata. The library entry then has the round-trip: pose → workflow → image, all queryable.

PostgreSQL is the storage backend (operator decision, locked at WP-I1-033 spec sign-off). Multi-model / multi-operator concurrent edits are a day-one requirement.

## Inputs

The library accepts these inputs per entry:

- **OpenPose JSON** — the `*.json` export from OpenRepose Feature 1 (or any compatible OpenPose-format JSON; format-validated on import).
- **OpenPose PNG** — the rendered wireframe alongside the JSON (WP-I1-030 ships PNG export; ingested as bytes / file).
- **Source / reference image** — optional; the master portrait that produced the rig. Stored as a path to the original or a copy under the library tree.
- **Generated image** — the downstream image produced by the ComfyUI workflow that consumed the OpenPose. Stored as bytes / file under the library tree.
- **ComfyUI workflow JSON** — the full ComfyUI workflow node graph. Stored verbatim as a JSONB column.
- **Prompts** — the positive + negative prompts. Plain text, full-text indexed.
- **Story beats** — short paragraph(s) describing the narrative beat this image serves. Plain text, full-text indexed.
- **Notes** — operator's free-form notes about the entry. Plain text, full-text indexed.
- **Tags** — short labels with optional namespace prefixes (`subject:aeri`, `pose:her-right-30`, `mood:intimate`, `lighting:lowkey`). Free-form; new tags created on first use; trigram-indexed for fuzzy search.
- **Metadata** — operator-supplied or workflow-extracted: model name, sampler, seed, steps, cfg, lora list, custom node list. Stored as a JSONB column for forward compatibility.

Inputs may arrive via:

- **GUI** — operator imports a previously exported pose + image pair via the Library tab.
- **LLM control surface** — `register_library_entry` command (full payload).
- **ComfyUI bridge** — automatic POST from the custom node after each successful image save.

Required fields: at least one of (OpenPose JSON, generated image, source image). All other fields optional. Entries with only one of the three are tagged `partial:metadata-only`.

## Database Schema

PostgreSQL ≥ 16. Required extensions: `pg_trgm` (fuzzy search), `uuid-ossp` (UUID generation), `unaccent` (search normalization).

```sql
-- Schema version for migration tracking.
CREATE TABLE schema_version (
    version       INT      PRIMARY KEY,
    applied_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One library entry = one pose + image set + metadata.
CREATE TABLE library_entries (
    id             UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    avatar_slug    TEXT         NOT NULL,
    title          TEXT         NOT NULL DEFAULT '',
    yaw_bin        TEXT,
    portrait_path  TEXT,
    openpose_json_path  TEXT,
    openpose_png_path   TEXT,
    generated_image_path TEXT,
    comfyui_workflow    JSONB,
    metadata       JSONB        NOT NULL DEFAULT '{}'::jsonb,
    completeness   TEXT         NOT NULL DEFAULT 'partial',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by     TEXT,
    locked_by      TEXT
);

CREATE INDEX library_entries_avatar_idx ON library_entries (avatar_slug);
CREATE INDEX library_entries_yaw_idx ON library_entries (yaw_bin);
CREATE INDEX library_entries_metadata_gin ON library_entries USING GIN (metadata);
CREATE INDEX library_entries_workflow_gin ON library_entries USING GIN (comfyui_workflow);

-- Tags. Free-form text; namespace prefix is convention (`namespace:value`).
CREATE TABLE tags (
    id        SERIAL  PRIMARY KEY,
    name      TEXT    NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX tags_name_trgm_idx ON tags USING GIN (name gin_trgm_ops);

-- Many-to-many: entries <-> tags.
CREATE TABLE entry_tags (
    entry_id  UUID    NOT NULL REFERENCES library_entries(id) ON DELETE CASCADE,
    tag_id    INT     NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

CREATE INDEX entry_tags_tag_idx ON entry_tags (tag_id);

-- Prompt history (positive + negative; one row per change).
CREATE TABLE prompts (
    id          SERIAL    PRIMARY KEY,
    entry_id    UUID      NOT NULL REFERENCES library_entries(id) ON DELETE CASCADE,
    positive    TEXT      NOT NULL DEFAULT '',
    negative    TEXT      NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by  TEXT,
    search_doc  TSVECTOR
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(positive, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(negative, '')), 'B')
        ) STORED
);

CREATE INDEX prompts_search_idx ON prompts USING GIN (search_doc);
CREATE INDEX prompts_entry_idx ON prompts (entry_id);

-- Story beats.
CREATE TABLE story_beats (
    id          SERIAL    PRIMARY KEY,
    entry_id    UUID      NOT NULL REFERENCES library_entries(id) ON DELETE CASCADE,
    body        TEXT      NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by  TEXT,
    search_doc  TSVECTOR
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(body, ''))) STORED
);

CREATE INDEX story_beats_search_idx ON story_beats USING GIN (search_doc);
CREATE INDEX story_beats_entry_idx ON story_beats (entry_id);

-- Operator notes.
CREATE TABLE notes (
    id          SERIAL    PRIMARY KEY,
    entry_id    UUID      NOT NULL REFERENCES library_entries(id) ON DELETE CASCADE,
    body        TEXT      NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by  TEXT,
    search_doc  TSVECTOR
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(body, ''))) STORED
);

CREATE INDEX notes_search_idx ON notes USING GIN (search_doc);
CREATE INDEX notes_entry_idx ON notes (entry_id);

-- Hybrid library_search() function: combines pg_trgm fuzzy on tags + titles
-- with tsvector full-text on prompts / story_beats / notes. Returns
-- (entry_id, rank) ordered by rank DESC.
CREATE OR REPLACE FUNCTION library_search(query TEXT)
RETURNS TABLE (entry_id UUID, rank REAL) AS $$
    SELECT e.id AS entry_id,
        (
            -- Title fuzzy match weight 0.4.
            COALESCE(similarity(e.title, query), 0) * 0.4
            -- Tag fuzzy match (max similarity across tags) weight 0.3.
            + COALESCE(
                (SELECT MAX(similarity(t.name, query))
                 FROM entry_tags et JOIN tags t ON t.id = et.tag_id
                 WHERE et.entry_id = e.id),
                0
              ) * 0.3
            -- Full-text on prompts weight 0.2.
            + COALESCE(
                (SELECT MAX(ts_rank(p.search_doc, plainto_tsquery('english', query)))
                 FROM prompts p WHERE p.entry_id = e.id),
                0
              ) * 0.2
            -- Full-text on story_beats + notes weight 0.1.
            + COALESCE(
                (SELECT MAX(ts_rank(s.search_doc, plainto_tsquery('english', query)))
                 FROM story_beats s WHERE s.entry_id = e.id),
                0
              ) * 0.05
            + COALESCE(
                (SELECT MAX(ts_rank(n.search_doc, plainto_tsquery('english', query)))
                 FROM notes n WHERE n.entry_id = e.id),
                0
              ) * 0.05
        )::REAL AS rank
    FROM library_entries e
    WHERE e.title % query  -- trigram fast-path
       OR EXISTS (SELECT 1 FROM entry_tags et JOIN tags t ON t.id = et.tag_id
                  WHERE et.entry_id = e.id AND t.name % query)
       OR EXISTS (SELECT 1 FROM prompts p WHERE p.entry_id = e.id
                  AND p.search_doc @@ plainto_tsquery('english', query))
       OR EXISTS (SELECT 1 FROM story_beats s WHERE s.entry_id = e.id
                  AND s.search_doc @@ plainto_tsquery('english', query))
       OR EXISTS (SELECT 1 FROM notes n WHERE n.entry_id = e.id
                  AND n.search_doc @@ plainto_tsquery('english', query))
    ORDER BY rank DESC
    LIMIT 200;
$$ LANGUAGE SQL STABLE;
```

Schema lives at `.product/migrations/001_library_initial.sql` (created by I2 implementation WPs). `schema_version` table is read on app startup; pending migrations run automatically.

Migration tooling: hand-rolled ordered SQL files (`NNN_<slug>.sql`). No Alembic / SQLAlchemy unless schema churn warrants it later.

## Storage Layout

Binary blobs (PNGs, generated images, source portraits) live on the **filesystem**, not as PostgreSQL BLOBs. The DB stores only paths. Reasons: operator can browse / back up files directly; PostgreSQL BLOBs are awkward to inspect; filesystem matches the rest of OpenRepose's outputs (`outputs/` already filesystem-based).

Layout under the configured library root (default `outputs/library/`):

```text
outputs/library/
  <entry-uuid>/
    portrait.png             (operator's source / reference image, copy)
    openpose.json            (the OpenPose-format JSON)
    openpose.png             (the rendered wireframe)
    generated.png            (the downstream image from ComfyUI)
    workflow.json            (a copy of the ComfyUI workflow JSON; DB also stores it as JSONB)
    metadata.json            (mirror of the DB metadata column for offline inspection)
```

The `<entry-uuid>` matches `library_entries.id`. Operator can browse `outputs/library/` directly; each subfolder is self-contained.

`library_entries.openpose_json_path` etc. store paths relative to the library root for portability. The library root itself is configured via `Settings.library_root` (defaults to `<export_folder>/library/`).

Library root + DB connection settings are stored under the existing `Settings` (extending WP-I1-027 schema_version 2):

```json
{
  "schema_version": 2,
  "library_root": "C:/Users/Operator/Desktop/openrepose-output/library/",
  "library_db_url": "postgresql://openrepose:openrepose@localhost:5432/openrepose"
}
```

## Tag System

Tags are short labels stored in the `tags` table. Conventions:

- **Free-form** — operator creates a new tag by using it; no upfront taxonomy enforcement.
- **Namespaced** — convention is `namespace:value`. Common namespaces (recommendations, not enforcement):
  - `subject:<avatar-slug>` — which avatar.
  - `pose:<yaw-bin>` — which yaw bin (`pose:her-right-30`, `pose:0`).
  - `mood:<adjective>` — `intimate`, `confrontational`, `playful`, `vulnerable`.
  - `lighting:<style>` — `lowkey`, `highkey`, `golden-hour`, `harsh`.
  - `composition:<framing>` — `closeup`, `bust`, `full-body`.
  - `act:<n>` — story-act ordering.
- **Smart tags** — derived tags computed by the dispatcher from metadata: `model:<model-name>`, `sampler:<sampler>`, `lora:<lora-name>`, `node:<custom-node-name>`. Smart tags are auto-applied on `register_library_entry` from the `metadata` column / workflow JSON; they prefix with `auto:` so the operator can distinguish from manual tags (e.g. `auto:model:flux-dev`).
- **Fuzzy search** — the `tags.name` column has a GIN trigram index (`pg_trgm`). The `library_search()` function and the GUI tag autocomplete both use trigram similarity. Tolerates typos: `inimate` matches `intimate` at similarity ~0.6.
- **Bulk re-tag** — bulk operations (e.g. add `auto:model:flux-dev` to all 200 entries from a workflow export) use optimistic concurrency on `library_entries.updated_at`; conflicts resolved by re-fetching + retrying.

## Library Tab UI Requirements

A new top-level dock tab **Library** (alongside Inspector / Tools / Options / Log / Help; positioned per WP-I1-031 reorganization).

Layout (operator-side; LLM agents use commands):

- **Top toolbar row**: search bar (with smart-tag autocomplete via `library_search()`), `[Refresh]`, `[Import OpenPose...]`, `[New entry from current rig]`, `[Library settings...]` (DB URL + library root).
- **Left pane** (1/3 width): scrollable entry list. Each row shows a thumbnail (generated image or openpose.png), title, avatar slug, yaw bin, top 3 tags. Selectable.
- **Right pane** (2/3 width): selected entry detail with **side-by-side OpenPose preview + reference image** (replacing the 3D / OpenPose view layout of Inspector for this tab). Below the side-by-side: tabbed sub-panes:
  - `Tags` — chip editor with autocomplete from `tags` table; smart tags read-only (greyed).
  - `Prompts` — positive + negative editors; copy / paste buttons; revision dropdown.
  - `Story` — story_beats editor (multi-paragraph).
  - `Notes` — free-form notes.
  - `Workflow` — ComfyUI workflow JSON viewer (read-only tree view; copy-to-clipboard).
  - `Metadata` — JSON viewer (read-only).
- **Status bar (entry-level)**: completeness flag, locked_by (if another operator holds the row lock), last edit timestamp + author.

The Library tab is operator-facing. LLM agents use the command surface below.

No `raise_/activateWindow/showNormal/setForegroundWindow` from any code path. No modal dialogs in response to LLM-driven commands; operator-side imports may use `QFileDialog` (operator-triggered only, allowed).

## Command Surface

The LLM Control Surface gains the following commands (HTTP and inbox channels accept all):

- `register_library_entry` — payload `{avatar_slug, title?, yaw_bin?, portrait_path?, openpose_json_path? | openpose_json?, openpose_png_path? | openpose_png?, generated_image_path? | generated_image?, comfyui_workflow?, metadata?, prompts?, story_beats?, notes?, tags?[]}`. Either supply paths to existing files OR base64-encoded bytes. Returns `{entry_id, created_at}`. Auto-applies smart tags from `metadata` + `comfyui_workflow`.
- `update_library_entry` — payload `{entry_id, ...patch}`. Patch fields override existing. Acquires row-level lock (`SELECT ... FOR UPDATE`); fails with structured error if another operator holds it.
- `delete_library_entry` — payload `{entry_id}`. Cascades to tags, prompts, story_beats, notes; removes the `outputs/library/<entry-uuid>/` folder.
- `library_search` — payload `{query: str, limit?: int = 50}`. Returns `[{entry_id, title, avatar_slug, yaw_bin, rank, top_tags: [...]}]`.
- `get_library_entry` — payload `{entry_id, include?: ["prompts", "story_beats", "notes", "workflow", "metadata"]}`. Returns the full entry (or specified subset).
- `set_library_tags` — payload `{entry_id, tags: [str, ...], replace?: bool = false}`. With `replace=false`, additive; with `replace=true`, replaces the entire tag set (excluding smart tags; smart tags stay).
- `dump_library_schema` — read-only, returns the current schema version + DDL hash for verification.

All commands non-interactive. No modal dialogs from any LLM-triggered path.

## ComfyUI Bridge / Custom Node Contract

Ships under `.product/comfyui-bridge/` as a self-contained ComfyUI custom node folder. Operator copies (or symlinks) the folder into their ComfyUI installation's `custom_nodes/` directory.

The custom node is named **OpenRepose Bridge** (`comfyui-openrepose-bridge`). It hooks into ComfyUI's image-save pipeline (via the standard `SaveImage` node extension pattern, as established by `SaveImageWithMetaData`, `comfy-image-saver`, etc.) and POSTs to OpenRepose's existing localhost HTTP control surface after each successful save.

**Contract (HTTP POST to `http://localhost:8765/command`):**

```json
{
  "command": "register_library_entry",
  "avatar_slug": "<from operator-supplied node input>",
  "title": "<filename or operator string>",
  "yaw_bin": "<auto-extracted from openpose JSON if present>",
  "openpose_json": "<base64; bytes of the OpenPose JSON used>",
  "openpose_png": "<base64; bytes of the OpenPose PNG used>",
  "generated_image": "<base64; bytes of the just-saved image>",
  "comfyui_workflow": <full workflow JSON object>,
  "metadata": {
    "model": "<from CheckpointLoaderSimple node>",
    "sampler": "<from KSampler node>",
    "seed": <int>,
    "steps": <int>,
    "cfg": <float>,
    "lora": [<list of LoraLoader names>],
    "custom_node": [<list of all node class_types in workflow>]
  },
  "prompts": {
    "positive": "<from positive CLIPTextEncode node>",
    "negative": "<from negative CLIPTextEncode node>"
  },
  "tags": [<operator-supplied tags from a OpenReposeBridge node input>]
}
```

**Compatibility:** target ComfyUI ≥ 0.3.65 (tracking the SaveImageWithMetaDataUniversal precedent). Pinned in the node's metadata; if the operator's ComfyUI is older, the node refuses to load with a clear error message.

**Auth:** localhost-only for v0.1. The HTTP channel binds to 127.0.0.1; no token required since the channel is on the operator's own machine. Multi-machine setup (operator's ComfyUI on a separate workstation) is out of scope for v0.1.

**Errors:** if the POST fails (OpenRepose not running, port unreachable), the custom node logs a WARN to ComfyUI's console but does NOT block image generation. Operator can retry via a manual `[Re-register last image]` button on the OpenReposeBridge node.

## Multi-Operator Concurrency

Multiple models / operators concurrently editing the library is the day-one use case. Strategy:

- **Connection pooling** — `psycopg_pool.ConnectionPool` (sync) at `min_size=4, max_size=10` per OpenRepose instance.
- **Row-level locking on edits** — `update_library_entry` and `delete_library_entry` acquire `SELECT ... FOR UPDATE NOWAIT` on the target row. If another operator holds the lock, the command fails with `{status: "error", reason: "entry locked by <other_operator>", retry_after: 5}`. The GUI shows a "Locked" indicator on entries currently held.
- **Optimistic concurrency on bulk ops** — `set_library_tags` (in bulk-replace mode), library re-tagging operations, and other multi-row updates use `WHERE updated_at = <last_seen_updated_at>`; the dispatcher refetches on conflict and retries up to 3 times before surfacing an error.
- **Author tracking** — `library_entries.created_by` and `<table>.created_by` columns store an operator slug (set via `Settings.operator_slug` or auto-derived from OS username). Used for the Locked-by indicator and for filtering.
- **Read consistency** — reads are non-blocking (default `READ COMMITTED` isolation); list / search results may include rows being edited (the editing operator's pending changes are visible only to that operator's session until commit).
- **Schema migrations** — applied at startup; only one OpenRepose instance applies a migration (advisory lock `pg_advisory_lock(<schema_migration_lock_id>)` ensures serialization). Other instances wait or restart after the migration completes.

## State File Reflection

`outputs/.runtime/state.json` gains a `library` block:

```json
{
  "library": {
    "connected": true,
    "db_url_redacted": "postgresql://openrepose:***@localhost:5432/openrepose",
    "schema_version": 2,
    "operator_slug": "ilja",
    "last_search_query": "subject:aeri pose:her-right-30",
    "last_search_count": 17,
    "last_search_at": "2026-05-03T19:33:11.000Z",
    "last_register_at": "2026-05-03T19:31:08.000Z",
    "pending_writes": 0,
    "locked_entries": []
  }
}
```

When the DB is unreachable, `connected: false` and a WARN appears in the log; library commands return structured errors but the rest of OpenRepose continues to function.

## Snapshot Targets

Two new targets:

- **`library_entry`** — renders the side-by-side OpenPose preview + reference image for the currently-selected entry to a PNG. If no entry is selected, falls back to a labeled placeholder ("no entry selected").
- **`library_search_results`** — renders a thumbnail grid of the current search results (top 24 entries, 4×6 grid; thumbnail = generated image or openpose.png).

Both targets respect the existing snapshot subsystem rules: no `raise_/activateWindow`, no focus theft, atomic write, manifest entry.

## Out Of Scope For Feature 3 v0.1

- Cloud sync / multi-machine sharing (single workstation + local-network ComfyUI only).
- Embedding-based semantic search (text-only via tsvector + pg_trgm; vector search via pgvector deferred).
- Video keypoints / pose sequences (still images only).
- Image versioning beyond simple replace (one generated image per entry; replace = overwrites).
- Authentication / per-operator permissions (all operators share the same library).
- Library import/export (entries are PostgreSQL-resident; backup is `pg_dump` + filesystem copy of `outputs/library/`).
- Library replication / sync to a remote PostgreSQL.
- Auto-organizing entries into folders / projects (single flat library; tags are the organizational layer).

## Reality Boundary For Feature 3 v0.1

- **Real Seam**: real PostgreSQL database (operator runs `docker-compose up postgres` or installs PostgreSQL ≥ 16; runs `001_library_initial.sql`); real `psycopg_pool` connection pool inside the dispatcher; real Library tab in the GUI; real ComfyUI custom node POSTing to the localhost HTTP channel after image generation; real entries written to `outputs/library/<entry-uuid>/` + indexed in PostgreSQL.
- **User-Visible Win**: operator generates an image in ComfyUI using an OpenPose exported from OpenRepose; the image, workflow, prompts, and metadata land in the library automatically. Operator searches `subject:aeri pose:her-right-30` in the Library tab; sees a list of every entry matching; clicks one to see the side-by-side pose + image with all prompts / story beats / notes. A second operator on the same workstation simultaneously edits a different entry without conflict; trying to edit the same entry surfaces a "Locked by <other>" message.
- **Proof Target**: pytest covers schema migrations, register / update / delete / search dispatcher commands, multi-operator lock collision (two pool clients, one acquires lock, second gets structured error), ComfyUI bridge POST end-to-end (mock the HTTP receiver), trigram fuzzy search ("inimate" matches "intimate"), full-text search (search "lighting" matches a story beat with "low-key lighting"). Manual: operator runs ComfyUI with the custom node installed, generates an image, sees the entry appear in the Library tab; runs a search; opens an entry from a parallel operator session and sees the lock indicator.
- **Allowed Temporary Fallbacks**: smart tags can fail to extract from non-standard ComfyUI workflow shapes; the entry still registers but with `auto:smart-tag-extraction-failed:1` so the operator can re-extract later. ComfyUI bridge HTTP failure logs WARN but does not block image save.
- **Promotion Guard**: do not promote Feature 3 spec from `DRAFT` to `STABLE` until: (a) at least 3 operators have used the library concurrently for one focused work session without lock-collision UX problems; (b) ComfyUI bridge survives at least 100 round-trips without dropped registrations; (c) `pg_dump` + restore round-trip preserves all entries + tags + prompts + story_beats + notes verbatim.

## I4 Multi-Operator Concurrency Hardening (OPEN — WP-I4-001)

Extension layered on top of v0.1 concurrency. v0.1 stays stable; this section adds the contract pieces that surface when multiple LLM/worker producers and operators load the library simultaneously. The detailed schema and command shapes live in `openrepose_intake_v0_1.md` "I4 Scale + DB Hardening Extension"; this section is the library-side companion.

### `library_search` Default Filtering

`library_search` excludes intake-staging rows from the main library view by default. Without this, multi-producer load contaminates the operator's primary discovery surface with `pending`, `soft_accepted`, `diagnostic`, and `rejected` entries.

- Default `status_filter`: `['promoted']`.
- Explicit opt-in: `include_staging=true` (adds the staging statuses) or `status_filter=[<allowlist>]` (full override).
- Legacy I2 entries with `status='promoted'` (set as the default on the I3 migration) remain visible without `include_legacy=true`. Pre-I3 rows with NULL status (none expected after migration 002, but defended) require `include_legacy=true`.
- Rule citation `INTAKE-009` (severity `info`) explains the default behavior in the response when `include_staging` is unset and the result count differs from the unfiltered count.

### Bulk Insert + Idempotency

The bulk producer path (`intake_register_outputs_bulk`) uses PostgreSQL `INSERT ... ON CONFLICT (task_id, agent_id, idempotency_key) DO NOTHING RETURNING ...` to make retries safe at the DB level rather than via pre-read / insert race patterns. `content_hash` remains dedup evidence (warn-level), not the sole identity key.

### Triage Claim Semantics

Concurrent triage workers claim batches of `pending` outputs with `SELECT ... FOR UPDATE SKIP LOCKED` so two workers see disjoint sets without blocking. Claims hold for the transaction lifetime; the worker either advances rows to a terminal state and commits, or rolls back and the rows return to `pending`.

### Transaction Ownership

Data-layer helpers under `library/` and `library/intake/` MUST NOT call `connection.commit()` or `connection.rollback()`. Transaction boundaries belong to command/service handlers. WP-I4-001 audits the touched modules and converts internal commits to caller-owned commits; broader cleanup is follow-up WP scope.

### File-Operation Outbox

Every status transition that needs a filesystem effect (move on soft_accept / promote, move on auto-route, delete on wholesale-reject) writes a `library_file_ops` row in the same DB transaction as the status update. The filesystem op runs after commit; failure leaves a retryable DB state with `library_outputs.storage_state='file_op_failed'`. There are no silent stale `file_path`s.

### Schema Bump

Migration `006_i4_intake_scale_hardening.sql` adds the columns and tables above and bumps `schema_version` from `5` to `6`. The migration applies cleanly from a fresh DB and from an I3-current DB.
