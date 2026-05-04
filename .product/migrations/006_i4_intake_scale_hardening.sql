-- WP-I4-001 / Spec: .gov/spec/openrepose_intake_v0_1.md
--                   "I4 Scale + DB Hardening Extension"
--                   .gov/spec/openrepose_library_v0_1.md
--                   "I4 Multi-Operator Concurrency Hardening"
--
-- I4 intake scale + DB hardening. Layered on top of the I3 intake schema
-- (migrations 002 + 003 + 004 + 005). Adds:
--
--   1. Producer-attribution columns on library_outputs:
--        source_model, agent_id, producer_run_id, idempotency_key.
--      Uniqueness for safe retry: UNIQUE (task_id, agent_id, idempotency_key).
--      content_hash remains warn-level dedup evidence, not the sole identity.
--
--   2. storage_state column on library_outputs (decoupled from semantic status).
--      A row's `status` describes the lifecycle (pending -> soft_accepted ->
--      promoted -> ...); `storage_state` describes where the file actually
--      lives (raw / diagnostic / rejected / soft_accepted / accepted /
--      missing / file_op_failed). The two are decoupled because PostgreSQL
--      transactions and filesystem moves cannot share a transaction manager.
--
--   3. library_output_events: append-only lifecycle audit. Every transition
--      writes a row inside the same DB transaction. Recovery reconstructs
--      lost intent by replay.
--
--   4. library_file_ops: durable file-operation outbox. Move/delete is
--      enqueued in the same transaction as the status change. A separate
--      worker (or the dispatcher inline, bounded by attempt cap) executes
--      the filesystem op and updates this row. Failure leaves a retryable
--      DB state -- no silent stale paths.
--
-- CHECK constraint names embed rule_ids so WP-I3-009 audit can verify
-- "every CHECK constraint that triggers a rejection cites a real rule_id"
-- by constraint-name regex.

-- ---------------------------------------------------------------------
-- 1. Producer attribution + idempotency columns on library_outputs
-- ---------------------------------------------------------------------
ALTER TABLE library_outputs
    ADD COLUMN source_model    TEXT,
    ADD COLUMN agent_id        TEXT,
    ADD COLUMN producer_run_id TEXT,
    ADD COLUMN idempotency_key TEXT;

-- Producer-supplied retry key, scoped per (task_id, agent_id).
-- A retried bulk request returns the existing row in `duplicates`; zero
-- new rows are created. Partial-NULL keys (missing agent_id or
-- idempotency_key) are not subject to this uniqueness constraint --
-- only fully-attributed retries are dedup-protected.
CREATE UNIQUE INDEX library_outputs_idempotency_uk
    ON library_outputs (task_id, agent_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND agent_id IS NOT NULL;

-- Helper index for "all outputs from agent X on task T" queries.
CREATE INDEX library_outputs_agent_idx
    ON library_outputs (task_id, agent_id)
    WHERE agent_id IS NOT NULL;

-- ---------------------------------------------------------------------
-- 2. storage_state on library_outputs
--    Decoupled from semantic `status`. Default 'raw' for new rows;
--    backfilled from existing status for legacy rows below.
-- ---------------------------------------------------------------------
ALTER TABLE library_outputs
    ADD COLUMN storage_state TEXT NOT NULL DEFAULT 'raw'
        CONSTRAINT lib_outputs_intake_006_storage_state_enum
            CHECK (storage_state IN
                ('raw','diagnostic','rejected','soft_accepted','accepted','missing','file_op_failed'));

-- Backfill: for rows that already exist (I3-current DB), align
-- storage_state with current status so the migration is non-disruptive.
-- The map matches the happy-path coupling described in the spec.
UPDATE library_outputs
SET storage_state = CASE status
    WHEN 'pending'        THEN 'raw'
    WHEN 'triaging'       THEN 'raw'
    WHEN 'soft_accepted'  THEN 'soft_accepted'
    WHEN 'promoted'       THEN 'accepted'
    WHEN 'rejected'       THEN 'rejected'
    WHEN 'diagnostic'     THEN 'diagnostic'
    WHEN 'abandoned'      THEN 'rejected'
    ELSE 'raw'
END;

-- Helper index for recovery audit: surface rows that need attention.
CREATE INDEX library_outputs_storage_state_idx
    ON library_outputs (storage_state)
    WHERE storage_state IN ('missing','file_op_failed');

-- ---------------------------------------------------------------------
-- 3. library_output_events   append-only lifecycle audit
-- ---------------------------------------------------------------------
CREATE TABLE library_output_events (
    id                  UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    output_id           UUID         NOT NULL REFERENCES library_outputs(id) ON DELETE CASCADE,
    event_type          TEXT         NOT NULL,
    from_status         TEXT,
    to_status           TEXT,
    from_storage_state  TEXT,
    to_storage_state    TEXT,
    actor               TEXT         NOT NULL,
    payload_json        JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT library_output_events_type_enum
        CHECK (event_type IN
            ('register','soft_accept','reject','finalize',
             'auto_route','reroute','wholesale_reject',
             'storage_transition','file_op_failed','recover'))
);

CREATE INDEX library_output_events_output_idx ON library_output_events (output_id);
CREATE INDEX library_output_events_type_idx   ON library_output_events (event_type);
CREATE INDEX library_output_events_created_idx ON library_output_events (created_at);

-- ---------------------------------------------------------------------
-- 4. library_file_ops   durable file-operation outbox
--    Moves and deletes that need to happen on disk. A worker claims rows
--    with FOR UPDATE SKIP LOCKED, executes the filesystem op, then
--    marks the row done or failed.
-- ---------------------------------------------------------------------
CREATE TABLE library_file_ops (
    id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    output_id       UUID         NOT NULL REFERENCES library_outputs(id) ON DELETE CASCADE,
    op_type         TEXT         NOT NULL,
    src_path        TEXT         NOT NULL,
    dst_path        TEXT,
    status          TEXT         NOT NULL DEFAULT 'pending',
    attempt_count   INT          NOT NULL DEFAULT 0,
    last_error      TEXT,
    claimed_at      TIMESTAMPTZ,
    claimed_by      TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    CONSTRAINT library_file_ops_op_type_enum
        CHECK (op_type IN ('move','delete')),
    CONSTRAINT library_file_ops_status_enum
        CHECK (status IN ('pending','in_flight','done','failed')),
    CONSTRAINT library_file_ops_dst_path_required
        CHECK (op_type <> 'move' OR dst_path IS NOT NULL)
);

CREATE INDEX library_file_ops_pending_idx
    ON library_file_ops (created_at)
    WHERE status IN ('pending','in_flight');

CREATE INDEX library_file_ops_output_idx ON library_file_ops (output_id);

-- ---------------------------------------------------------------------
-- 5. Convenience view: outputs paired with their latest file-op row
--    Used by intake_recover_audit to surface rows whose last file op
--    failed or is still pending.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW library_outputs_with_latest_file_op_v AS
SELECT
    o.id                         AS output_id,
    o.task_id,
    o.run_id,
    o.status,
    o.storage_state,
    o.file_path,
    o.agent_id,
    o.idempotency_key,
    fo.id                        AS file_op_id,
    fo.op_type                   AS file_op_type,
    fo.status                    AS file_op_status,
    fo.attempt_count             AS file_op_attempt_count,
    fo.last_error                AS file_op_last_error,
    fo.created_at                AS file_op_created_at,
    fo.completed_at              AS file_op_completed_at
FROM library_outputs o
LEFT JOIN LATERAL (
    SELECT *
    FROM library_file_ops
    WHERE output_id = o.id
    ORDER BY created_at DESC
    LIMIT 1
) fo ON TRUE;
