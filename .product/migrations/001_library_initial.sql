-- WP-I2-001 / Spec: .gov/spec/openrepose_library_v0_1.md "Database Schema".
--
-- OpenRepose Library initial schema (PostgreSQL >= 16).
--
-- This file is applied verbatim by .product/src/openrepose/db/migrator.py
-- inside a single transaction. The migrator wraps the file with an
-- advisory lock so concurrent OpenRepose instances cannot apply this
-- migration twice. After successful execution the migrator inserts a row
-- into schema_version.

-- Required extensions.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Schema version tracking. The migrator reads MAX(version) at startup,
-- runs every NNN_*.sql file with NNN > current_max in order, and inserts
-- a row here at end of each migration's transaction.
CREATE TABLE IF NOT EXISTS schema_version (
    version       INT PRIMARY KEY,
    applied_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One library entry = one pose + image set + metadata.
CREATE TABLE library_entries (
    id                   UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    avatar_slug          TEXT         NOT NULL,
    title                TEXT         NOT NULL DEFAULT '',
    yaw_bin              TEXT,
    portrait_path        TEXT,
    openpose_json_path   TEXT,
    openpose_png_path    TEXT,
    generated_image_path TEXT,
    comfyui_workflow     JSONB,
    metadata             JSONB        NOT NULL DEFAULT '{}'::jsonb,
    completeness         TEXT         NOT NULL DEFAULT 'partial',
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by           TEXT,
    locked_by            TEXT
);

CREATE INDEX library_entries_avatar_idx ON library_entries (avatar_slug);
CREATE INDEX library_entries_yaw_idx ON library_entries (yaw_bin);
CREATE INDEX library_entries_metadata_gin ON library_entries USING GIN (metadata);
CREATE INDEX library_entries_workflow_gin ON library_entries USING GIN (comfyui_workflow);

-- Tags. Free-form text; namespace prefix is convention (`namespace:value`).
CREATE TABLE tags (
    id          SERIAL       PRIMARY KEY,
    name        TEXT         NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX tags_name_trgm_idx ON tags USING GIN (name gin_trgm_ops);

-- Many-to-many entries <-> tags.
CREATE TABLE entry_tags (
    entry_id  UUID  NOT NULL REFERENCES library_entries(id) ON DELETE CASCADE,
    tag_id    INT   NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

CREATE INDEX entry_tags_tag_idx ON entry_tags (tag_id);

-- Prompt history (positive + negative; one row per change).
CREATE TABLE prompts (
    id          SERIAL       PRIMARY KEY,
    entry_id    UUID         NOT NULL REFERENCES library_entries(id) ON DELETE CASCADE,
    positive    TEXT         NOT NULL DEFAULT '',
    negative    TEXT         NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by  TEXT,
    search_doc  TSVECTOR
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(positive, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(negative, '')), 'B')
        ) STORED
);

CREATE INDEX prompts_search_idx ON prompts USING GIN (search_doc);
CREATE INDEX prompts_entry_idx  ON prompts (entry_id);

-- Story beats.
CREATE TABLE story_beats (
    id          SERIAL       PRIMARY KEY,
    entry_id    UUID         NOT NULL REFERENCES library_entries(id) ON DELETE CASCADE,
    body        TEXT         NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by  TEXT,
    search_doc  TSVECTOR
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(body, ''))) STORED
);

CREATE INDEX story_beats_search_idx ON story_beats USING GIN (search_doc);
CREATE INDEX story_beats_entry_idx  ON story_beats (entry_id);

-- Operator notes.
CREATE TABLE notes (
    id          SERIAL       PRIMARY KEY,
    entry_id    UUID         NOT NULL REFERENCES library_entries(id) ON DELETE CASCADE,
    body        TEXT         NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by  TEXT,
    search_doc  TSVECTOR
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(body, ''))) STORED
);

CREATE INDEX notes_search_idx ON notes USING GIN (search_doc);
CREATE INDEX notes_entry_idx  ON notes (entry_id);

-- library_search(): hybrid trigram + tsvector ranking. Returns up to 200
-- (entry_id, rank) rows ordered DESC. Per spec weights:
--   title       0.40
--   tags max    0.30
--   prompts     0.20
--   story_beats 0.05
--   notes       0.05
CREATE OR REPLACE FUNCTION library_search(query TEXT)
RETURNS TABLE (entry_id UUID, rank REAL) AS $$
    SELECT e.id AS entry_id,
        (
            COALESCE(similarity(e.title, query), 0) * 0.4
            + COALESCE(
                (SELECT MAX(similarity(t.name, query))
                 FROM entry_tags et JOIN tags t ON t.id = et.tag_id
                 WHERE et.entry_id = e.id),
                0
              ) * 0.3
            + COALESCE(
                (SELECT MAX(ts_rank(p.search_doc, plainto_tsquery('english', query)))
                 FROM prompts p WHERE p.entry_id = e.id),
                0
              ) * 0.2
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
    WHERE e.title % query
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
