"""Functional + correctness + abuse-case tests for WP-I4-001.

Spec: `.gov/spec/openrepose_intake_v0_1.md`
      "I4 Scale + DB Hardening Extension".

Covers the bulk intake / storage / recovery contract end-to-end at
the data-layer level (no dispatcher). Concurrent-producer behavior
via threading lives in test_e2e_parallel_intake.py.

Skips cleanly when no system Postgres / pytest-postgresql is
available, mirroring the I3 migration test pattern.
"""

from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from openrepose.db.migrator import Migrator
from openrepose.library.intake import (
    BULK_BATCH_MAX_DEFAULT,
    BulkIntakeError,
    enqueue_file_op,
    process_pending_file_ops,
    record_event,
    recover_audit,
    recover_retry,
    register_outputs_bulk,
    set_storage_state,
)
from openrepose.library.intake.storage import diagnostic_dst_path, reject_dst_path
from openrepose.library.search import search

# ---------------------------------------------------------------------------
# pytest-postgresql wiring (mirrors test_db_migrator_i4.py).
# ---------------------------------------------------------------------------

PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass


if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    intake_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    intake_pg = _factories.postgresql("intake_pg_proc")
else:  # pragma: no cover

    @pytest.fixture
    def intake_pg():
        pytest.skip(
            "pytest-postgresql or system pg_ctl unavailable; "
            "skipping I4 scale + hardening tests"
        )


def _dsn(pg_conn) -> str:  # noqa: ANN001
    info = pg_conn.info
    parts = [
        f"host={info.host}",
        f"port={info.port}",
        f"user={info.user}",
        f"dbname={info.dbname}",
    ]
    if getattr(info, "password", ""):
        parts.append(f"password={info.password}")
    return " ".join(parts)


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / ".product" / "migrations"


pytestmark = pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres / pytest-postgresql",
)


def _seed_minimal(conn) -> dict:  # noqa: ANN001
    """Insert one project + task + batch + card + run; return the IDs."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_projects (slug, name, owner_slug) "
            "VALUES ('exp120', 'Exposure 120', 'op') RETURNING id"
        )
        project_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO library_tasks (project_id, slug, intake_dir, expected_count) "
            "VALUES (%s, 'T-001', 'intake/T-001/', 300) RETURNING id",
            (project_id,),
        )
        task_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO library_batches (project_id, task_id, slug) "
            "VALUES (%s, %s, 'B-001') RETURNING id",
            (project_id, task_id),
        )
        batch_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO library_entries (avatar_slug, title, batch_id, status, "
            "                             dedupe_signature, compatibility_signature) "
            "VALUES ('aeri', 'SF-15', %s, 'pending', "
            "        'pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm', "
            "        'standing|frontal|hotel') RETURNING id",
            (batch_id,),
        )
        card_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO library_runs (card_id, task_id) "
            "VALUES (%s, %s) RETURNING id",
            (card_id, task_id),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return {
        "project_id": project_id,
        "task_id": task_id,
        "batch_id": batch_id,
        "card_id": card_id,
        "run_id": run_id,
    }


def _make_payload(
    n: int,
    *,
    prefix: str = "p",
    width: int = 1080,
    height: int = 1440,
) -> list[dict[str, Any]]:
    return [
        {
            "file_path": f"intake/T-001/raw/{prefix}_{i:04d}.png",
            "content_hash": f"h-{prefix}-{i:04d}",
            "width": width,
            "height": height,
            "idempotency_key": f"{prefix}-{i:04d}",
            "producer_run_id": f"{prefix}-run",
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Functional flow tests
# ---------------------------------------------------------------------------


def test_bulk_register_inserts_100_pending_outputs(intake_pg):
    """Single-run bulk registration creates 100 pending outputs with
    full producer attribution and `received_count` updated by 100."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        result = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            source_model="sdxl-base-1.0",
            outputs=_make_payload(100, prefix="A"),
        )

        assert result.inserted_count == 100
        assert len(result.duplicates) == 0
        assert len(result.rejected) == 0

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM library_outputs "
                "WHERE task_id = %s AND status = 'pending' "
                "  AND storage_state = 'raw' "
                "  AND agent_id = 'agent-1' AND source_model = 'sdxl-base-1.0'",
                (str(ids["task_id"]),),
            )
            assert cur.fetchone()[0] == 100

            cur.execute(
                "SELECT received_count FROM library_tasks WHERE id = %s",
                (str(ids["task_id"]),),
            )
            assert cur.fetchone()[0] == 100

            # Each row got a 'register' event.
            cur.execute(
                "SELECT COUNT(*) FROM library_output_events "
                "WHERE event_type = 'register' AND actor = 'agent-1'"
            )
            assert cur.fetchone()[0] == 100


def test_bulk_register_idempotent_retry_creates_zero_new_rows(intake_pg):
    """A second bulk call with the same idempotency keys returns each
    existing row in `duplicates`. Zero new rows. `received_count` is
    not double-incremented."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        payload = _make_payload(50, prefix="R")

        first = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=payload,
        )
        assert first.inserted_count == 50

        second = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=payload,
        )
        assert second.inserted_count == 0
        assert len(second.duplicates) == 50
        # Every duplicate result references an existing row id.
        assert all(d["existing_output_id"] for d in second.duplicates)
        # And content_hash matches because we resubmitted identical payloads.
        assert all(d["content_hash_match"] for d in second.duplicates)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM library_outputs WHERE task_id = %s",
                (str(ids["task_id"]),),
            )
            assert cur.fetchone()[0] == 50

            cur.execute(
                "SELECT received_count FROM library_tasks WHERE id = %s",
                (str(ids["task_id"]),),
            )
            assert cur.fetchone()[0] == 50


def test_bulk_register_in_request_duplicate_keys_normalized(intake_pg):
    """Duplicate idempotency keys WITHIN one request: first wins,
    later duplicates land in `rejected`."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        payload = _make_payload(3, prefix="D")
        # Inject a duplicate key at index 3 (re-uses key "D-0001").
        payload.append(
            {
                "file_path": "intake/T-001/raw/dupe.png",
                "content_hash": "h-dupe",
                "width": 1080,
                "height": 1440,
                "idempotency_key": "D-0001",
                "producer_run_id": "D-run",
            }
        )

        result = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=payload,
        )
        assert result.inserted_count == 3
        assert len(result.rejected) == 1
        assert result.rejected[0]["reason"] == "duplicate_idempotency_key_in_request"
        assert result.rejected[0]["rule_id"] == "INTAKE-005"


def test_bulk_register_oversized_request_rejected_pre_write(intake_pg):
    """INTAKE-008: a request above bulk_batch_max is rejected before any DB write."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        payload = _make_payload(BULK_BATCH_MAX_DEFAULT + 1, prefix="X")

        with pytest.raises(BulkIntakeError) as ei:
            register_outputs_bulk(
                conn,
                task_id=ids["task_id"],
                run_id=ids["run_id"],
                project_id=ids["project_id"],
                agent_id="agent-1",
                outputs=payload,
            )
        assert "INTAKE-008" in str(ei.value)
        # No partial write.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM library_outputs WHERE task_id = %s",
                (str(ids["task_id"]),),
            )
            assert cur.fetchone()[0] == 0


def test_bulk_register_validation_failure_lands_in_rejected_not_aborts(intake_pg):
    """A row with width=0 (validation failure) lands in `rejected` and
    the rest of the bulk continues."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        good = _make_payload(5, prefix="G")
        bad = {
            "file_path": "intake/T-001/raw/bad.png",
            "content_hash": "h-bad",
            "width": 0,
            "height": 1440,
            "idempotency_key": "BAD-1",
        }
        payload = good + [bad]

        result = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=payload,
        )
        assert result.inserted_count == 5
        assert len(result.rejected) == 1
        assert "validation_failed" in result.rejected[0]["reason"]


def test_bulk_register_uniqueness_scoped_per_agent(intake_pg):
    """Same idempotency_key under two different agent_ids does not collide."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        payload = _make_payload(10, prefix="K")

        a1 = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=payload,
        )
        a2 = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-2",
            outputs=payload,
        )
        assert a1.inserted_count == 10
        assert a2.inserted_count == 10
        # Distinct rows.
        a1_ids = {d["output_id"] for d in a1.inserted}
        a2_ids = {d["output_id"] for d in a2.inserted}
        assert not (a1_ids & a2_ids)


# ---------------------------------------------------------------------------
# Auto-route in bulk mode
# ---------------------------------------------------------------------------


def test_bulk_register_auto_route_lands_failing_rows_in_diagnostic(intake_pg):
    """A project rule that requires width=1080 routes 720x800 outputs
    to diagnostic. Bulk registration handles them correctly."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        # Insert a project-scope auto-route rule: must be 1080x1440.
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO library_rules "
                "(rule_id, scope_type, scope_id, name, short, severity, "
                " machine_check_fn, auto_route_to) "
                "VALUES ('EXP120-RES-001', 'project', %s, 'resolution gate', "
                "        '1080x1440 required', 'auto-route', "
                "        '(width = 1080 AND height = 1440)', "
                "        'intermediate_evidence')",
                (str(ids["project_id"]),),
            )
        conn.commit()

        # 5 good (1080x1440) + 3 bad (720x800).
        good = _make_payload(5, prefix="G")
        bad = _make_payload(3, prefix="B", width=720, height=800)

        result = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=good + bad,
        )
        assert result.inserted_count == 5
        assert len(result.diagnostic) == 3
        assert all(
            d["auto_route_bucket"] == "intermediate_evidence"
            for d in result.diagnostic
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM library_outputs "
                "WHERE task_id = %s AND status = 'diagnostic' "
                "  AND storage_state = 'diagnostic'",
                (str(ids["task_id"]),),
            )
            assert cur.fetchone()[0] == 3

            # Each diagnostic row also got a file-op outbox row.
            cur.execute(
                "SELECT COUNT(*) FROM library_file_ops "
                "WHERE op_type = 'move' AND status = 'pending' "
                "  AND dst_path LIKE '%%/intermediate_evidence/%%'"
            )
            assert cur.fetchone()[0] == 3

            # And an auto_route lifecycle event.
            cur.execute(
                "SELECT COUNT(*) FROM library_output_events "
                "WHERE event_type = 'auto_route'"
            )
            assert cur.fetchone()[0] == 3


# ---------------------------------------------------------------------------
# Storage / file-op outbox round-trip with a temp outputs root
# ---------------------------------------------------------------------------


def test_file_op_outbox_executes_pending_moves(intake_pg, tmp_path):
    """Manually enqueue a move file-op, populate the source on disk,
    run process_pending_file_ops, verify the file moved + the row
    advanced to 'done' + library_outputs.file_path updated."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        outputs_root = tmp_path / "outputs"
        intake_dir = outputs_root / "intake" / "T-001" / "raw"
        intake_dir.mkdir(parents=True)
        src_rel = "intake/T-001/raw/p_0001.png"
        (outputs_root / src_rel).write_bytes(b"\x89PNG fake")

        bulk = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=[
                {
                    "file_path": src_rel,
                    "content_hash": "h-1",
                    "width": 1080,
                    "height": 1440,
                    "idempotency_key": "p-1",
                }
            ],
        )
        output_id = bulk.inserted[0]["output_id"]

        # Manually enqueue a move into rejected/.
        dst_rel = reject_dst_path(src_rel)
        assert dst_rel == "intake/T-001/rejected/p_0001.png"
        enqueue_file_op(
            conn,
            output_id=output_id,
            op_type="move",
            src_path=src_rel,
            dst_path=dst_rel,
        )
        conn.commit()

        counters = process_pending_file_ops(
            conn,
            outputs_root=outputs_root,
            claimed_by="worker-1",
            limit=10,
        )
        assert counters == {"claimed": 1, "done": 1, "failed": 0}

        # The file moved on disk.
        assert not (outputs_root / src_rel).exists()
        assert (outputs_root / dst_rel).exists()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, file_path FROM library_outputs WHERE id = %s",
                (output_id,),
            )
            status, file_path = cur.fetchone()
            assert file_path == dst_rel

            cur.execute(
                "SELECT status, attempt_count, completed_at FROM library_file_ops "
                "WHERE output_id = %s",
                (output_id,),
            )
            op_status, attempt_count, completed_at = cur.fetchone()
            assert op_status == "done"
            assert attempt_count == 1
            assert completed_at is not None


def test_file_op_failure_marks_row_failed_and_storage_state(intake_pg, tmp_path):
    """A move whose source does not exist fails. The row is marked
    'failed', library_outputs.storage_state -> 'file_op_failed', and
    a 'file_op_failed' lifecycle event is recorded."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()

        src_rel = "intake/T-001/raw/missing.png"
        bulk = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=[
                {
                    "file_path": src_rel,
                    "content_hash": "h-m",
                    "width": 1080,
                    "height": 1440,
                    "idempotency_key": "m-1",
                }
            ],
        )
        output_id = bulk.inserted[0]["output_id"]

        # Enqueue a move whose source does not exist on disk.
        dst_rel = reject_dst_path(src_rel)
        enqueue_file_op(
            conn,
            output_id=output_id,
            op_type="move",
            src_path=src_rel,
            dst_path=dst_rel,
        )
        conn.commit()

        counters = process_pending_file_ops(
            conn,
            outputs_root=outputs_root,
            claimed_by="worker-1",
            limit=10,
        )
        assert counters == {"claimed": 1, "done": 0, "failed": 1}

        with conn.cursor() as cur:
            cur.execute(
                "SELECT storage_state FROM library_outputs WHERE id = %s",
                (output_id,),
            )
            assert cur.fetchone()[0] == "file_op_failed"

            cur.execute(
                "SELECT status, last_error FROM library_file_ops "
                "WHERE output_id = %s",
                (output_id,),
            )
            op_status, last_error = cur.fetchone()
            assert op_status == "failed"
            assert "src_missing" in (last_error or "")

            cur.execute(
                "SELECT COUNT(*) FROM library_output_events "
                "WHERE output_id = %s AND event_type = 'file_op_failed'",
                (output_id,),
            )
            assert cur.fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Recovery / audit
# ---------------------------------------------------------------------------


def test_recover_audit_reports_failed_and_pending_file_ops(intake_pg, tmp_path):
    """Audit surfaces failed ops + pending ops + missing files."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        outputs_root = tmp_path / "outputs"
        outputs_root.mkdir()

        bulk = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=_make_payload(2, prefix="A"),
        )
        output_a, output_b = bulk.inserted[0]["output_id"], bulk.inserted[1]["output_id"]

        # Force one row into 'missing' state (simulating recovery audit
        # discovering a deleted file).
        set_storage_state(conn, output_id=output_a, new_storage_state="missing")

        # Enqueue + run a file op for the second row that will fail.
        enqueue_file_op(
            conn,
            output_id=output_b,
            op_type="move",
            src_path="intake/T-001/raw/A_0001.png",
            dst_path="intake/T-001/rejected/A_0001.png",
        )
        conn.commit()
        process_pending_file_ops(
            conn, outputs_root=outputs_root, claimed_by="worker-1",
        )

        # Enqueue another op left pending.
        enqueue_file_op(
            conn,
            output_id=output_b,
            op_type="delete",
            src_path="intake/T-001/raw/leftover.png",
        )
        conn.commit()

        audit = recover_audit(conn, task_id=ids["task_id"])
        assert any(m["output_id"] == output_a for m in audit.missing_files)
        assert len(audit.failed_file_ops) >= 1
        assert all(o["op_type"] in {"move", "delete"} for o in audit.failed_file_ops)
        assert len(audit.pending_file_ops) >= 1
        assert all(o["op_type"] in {"move", "delete"} for o in audit.pending_file_ops)


def test_recover_retry_advances_failed_op_to_done_when_repaired(intake_pg, tmp_path):
    """After repairing the underlying cause (creating the missing
    source file), recover_retry advances the file-op to 'done' and
    library_outputs.storage_state recovers from 'file_op_failed' to
    the spec-mapped state for the row's status."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        outputs_root = tmp_path / "outputs"
        intake_dir = outputs_root / "intake" / "T-001" / "raw"
        intake_dir.mkdir(parents=True)

        bulk = register_outputs_bulk(
            conn,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=_make_payload(1, prefix="R"),
        )
        output_id = bulk.inserted[0]["output_id"]

        # Enqueue and fail a move (no source file yet).
        src_rel = "intake/T-001/raw/R_0000.png"
        dst_rel = reject_dst_path(src_rel)
        file_op_id = enqueue_file_op(
            conn,
            output_id=output_id,
            op_type="move",
            src_path=src_rel,
            dst_path=dst_rel,
        )
        conn.commit()
        process_pending_file_ops(
            conn, outputs_root=outputs_root, claimed_by="worker-1",
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT storage_state FROM library_outputs WHERE id = %s",
                (output_id,),
            )
            assert cur.fetchone()[0] == "file_op_failed"

        # Repair: create the source file, then retry.
        (outputs_root / src_rel).write_bytes(b"\x89PNG fake")
        result = recover_retry(
            conn,
            file_op_id=file_op_id,
            outputs_root=outputs_root,
            actor="op",
        )
        assert result["status"] == "done"

        with conn.cursor() as cur:
            cur.execute(
                "SELECT storage_state, file_path FROM library_outputs WHERE id = %s",
                (output_id,),
            )
            storage_state, file_path = cur.fetchone()
            # status='pending' -> spec-mapped storage_state='raw'.
            assert storage_state == "raw"
            assert file_path == dst_rel
        assert (outputs_root / dst_rel).exists()


# ---------------------------------------------------------------------------
# Search filter (INTAKE-009)
# ---------------------------------------------------------------------------


def test_search_default_excludes_pending_intake_rows(intake_pg):
    """A staging row (batch_id set, status='pending') is hidden by
    default; visible with include_staging=True."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)
        # The seeded card itself is batch_id-set + status='pending';
        # also insert a card with batch_id NULL (legacy) for contrast.
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO library_entries (avatar_slug, title, status, "
                "                             dedupe_signature, "
                "                             compatibility_signature) "
                "VALUES ('aeri', 'legacy direct entry', 'pending', '', '') "
                "RETURNING id"
            )
            legacy_id = cur.fetchone()[0]
        conn.commit()

        # Default: legacy (batch_id IS NULL) visible; staging (batch_id +
        # pending) hidden.
        results = search(conn, "entry")
        ids_in_results = {str(r.entry_id) for r in results}
        assert str(legacy_id) in ids_in_results

        # Search by avatar 'SF-15' -> staging row, hidden by default.
        staging_results = search(conn, "SF-15")
        staging_ids = {str(r.entry_id) for r in staging_results}
        assert str(ids["card_id"]) not in staging_ids

        # include_staging=True surfaces it.
        staging_results_inc = search(conn, "SF-15", include_staging=True)
        staging_ids_inc = {str(r.entry_id) for r in staging_results_inc}
        assert str(ids["card_id"]) in staging_ids_inc


def test_search_status_filter_overrides_default(intake_pg):
    """An explicit status_filter takes precedence over the default
    intake-staging exclusion."""
    import psycopg

    with psycopg.connect(_dsn(intake_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(conn)

        # Promote the seeded card.
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE library_entries SET status = 'promoted' WHERE id = %s",
                (str(ids["card_id"]),),
            )
        conn.commit()

        # status_filter=['pending'] returns nothing (the card is now
        # promoted, no pending rows match).
        nothing = search(conn, "SF-15", status_filter=["pending"])
        assert all(str(r.entry_id) != str(ids["card_id"]) for r in nothing)

        # status_filter=['promoted'] surfaces the promoted card.
        only_promoted = search(conn, "SF-15", status_filter=["promoted"])
        assert any(str(r.entry_id) == str(ids["card_id"]) for r in only_promoted)


# ---------------------------------------------------------------------------
# SKIP LOCKED claim semantics
# ---------------------------------------------------------------------------


def test_skip_locked_claim_disjoint_between_workers(intake_pg):
    """Two workers calling claim_pending_file_ops at the same time see
    disjoint sets. Verified by holding worker-1's transaction open
    while worker-2 claims."""
    import psycopg

    from openrepose.library.intake.storage import (
        claim_pending_file_ops,
        complete_file_op,
    )

    dsn = _dsn(intake_pg)

    with psycopg.connect(dsn) as setup:
        Migrator(setup, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed_minimal(setup)
        bulk = register_outputs_bulk(
            setup,
            task_id=ids["task_id"],
            run_id=ids["run_id"],
            project_id=ids["project_id"],
            agent_id="agent-1",
            outputs=_make_payload(10, prefix="L"),
        )
        for item in bulk.inserted:
            enqueue_file_op(
                setup,
                output_id=item["output_id"],
                op_type="move",
                src_path=f"intake/T-001/raw/{item['idempotency_key']}.png",
                dst_path=f"intake/T-001/rejected/{item['idempotency_key']}.png",
            )
        setup.commit()

    # Two independent connections claim concurrently.
    barrier = threading.Barrier(2)
    claims: dict[str, list[str]] = {}

    def worker(name: str) -> None:
        with psycopg.connect(dsn) as c:
            barrier.wait()
            rows = claim_pending_file_ops(c, claimed_by=name, limit=10)
            claims[name] = [r["file_op_id"] for r in rows]
            # Don't commit -- hold the lock to verify disjointness.
            time.sleep(0.4)
            for r in rows:
                complete_file_op(c, file_op_id=r["file_op_id"], success=True)
            c.commit()

    t1 = threading.Thread(target=worker, args=("worker-1",))
    t2 = threading.Thread(target=worker, args=("worker-2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    a = set(claims["worker-1"])
    b = set(claims["worker-2"])
    assert not (a & b), f"workers must see disjoint sets: overlap={a & b}"
    assert len(a) + len(b) == 10


# ---------------------------------------------------------------------------
# Path computation helpers
# ---------------------------------------------------------------------------


def test_reject_dst_path_basic(intake_pg):
    assert reject_dst_path("intake/T-001/raw/p.png") == "intake/T-001/rejected/p.png"
    assert reject_dst_path("intake/T-x/diagnostic/foo/p.png") == (
        "intake/T-x/rejected/p.png"
    )
    assert reject_dst_path("notintake/raw/p.png") is None
    assert reject_dst_path("intake/raw") is None


def test_diagnostic_dst_path_basic(intake_pg):
    assert diagnostic_dst_path("intake/T-1/raw/p.png", bucket="intermediate") == (
        "intake/T-1/diagnostic/intermediate/p.png"
    )
    assert diagnostic_dst_path("intake/T-1/raw/p.png", bucket="") is None
    assert diagnostic_dst_path("notintake/p.png", bucket="x") is None
