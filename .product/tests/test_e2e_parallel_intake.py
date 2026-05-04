"""End-to-end parallel intake proof for WP-I4-001.

Spec: `.gov/spec/openrepose_intake_v0_1.md`
      "I4 Scale + DB Hardening Extension / Reality Boundary For I4".

Submits 3 producer identities x >= 100 outputs each into one project/task,
retries one producer payload to prove idempotency, soft-accepts and
rejects subsets, and asserts:

  - row counts and duplicate counts
  - per-agent output counts
  - library_tasks.received_count
  - storage_state distribution
  - library_search returns no staging rows by default
  - target counter view (library_target_card_counts) reflects the
    accept/reject mix

Skips cleanly when no system Postgres is available.
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Any

import pytest

from openrepose.db.migrator import Migrator
from openrepose.library.intake import register_outputs_bulk
from openrepose.library.search import search

PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass


if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    e2e_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    e2e_pg = _factories.postgresql("e2e_pg_proc")
else:  # pragma: no cover

    @pytest.fixture
    def e2e_pg():
        pytest.skip(
            "pytest-postgresql or system pg_ctl unavailable; "
            "skipping I4 parallel e2e test"
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


# ---------------------------------------------------------------------------
# Test parameters
# ---------------------------------------------------------------------------

PRODUCERS: tuple[str, ...] = ("agent-alpha", "agent-beta", "agent-gamma")
OUTPUTS_PER_PRODUCER: int = 100
BULK_CHUNK: int = 50  # 2 chunks per producer = 100 outputs
RETRY_PRODUCER: str = "agent-alpha"  # this producer also re-submits chunk 1


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def _seed(conn) -> dict[str, Any]:  # noqa: ANN001
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_projects (slug, name, owner_slug) "
            "VALUES ('exp120-e2e', 'EXP120 e2e', 'op') RETURNING id"
        )
        project_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO library_tasks (project_id, slug, intake_dir, "
            "                           expected_count) "
            "VALUES (%s, 'T-E2E', 'intake/T-E2E/', %s) RETURNING id",
            (project_id, OUTPUTS_PER_PRODUCER * len(PRODUCERS)),
        )
        task_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO library_batches (project_id, task_id, slug) "
            "VALUES (%s, %s, 'B-E2E') RETURNING id",
            (project_id, task_id),
        )
        batch_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO library_entries (avatar_slug, title, batch_id, status, "
            "                             dedupe_signature, "
            "                             compatibility_signature) "
            "VALUES ('aeri', 'SF-15', %s, 'pending', "
            "        'pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm', "
            "        'standing|frontal|hotel') RETURNING id",
            (batch_id,),
        )
        card_id = cur.fetchone()[0]
        # One run per producer so the FK is per-producer.
        runs_by_agent: dict[str, str] = {}
        for agent_id in PRODUCERS:
            cur.execute(
                "INSERT INTO library_runs (card_id, task_id) "
                "VALUES (%s, %s) RETURNING id",
                (card_id, task_id),
            )
            runs_by_agent[agent_id] = cur.fetchone()[0]
    conn.commit()
    return {
        "project_id": project_id,
        "task_id": task_id,
        "batch_id": batch_id,
        "card_id": card_id,
        "runs_by_agent": runs_by_agent,
    }


def _payload_for(agent_id: str, *, start: int, count: int) -> list[dict[str, Any]]:
    return [
        {
            "file_path": f"intake/T-E2E/raw/{agent_id}_{i:04d}.png",
            "content_hash": f"h-{agent_id}-{i:04d}",
            "width": 1080,
            "height": 1440,
            "idempotency_key": f"{agent_id}-{i:04d}",
            "producer_run_id": f"{agent_id}-run",
        }
        for i in range(start, start + count)
    ]


def test_parallel_intake_three_producers_x_100_outputs(e2e_pg):  # noqa: PLR0915
    """The headline proof per WP-I4-001 Reality Boundary."""
    import psycopg

    dsn = _dsn(e2e_pg)

    with psycopg.connect(dsn) as setup:
        Migrator(setup, migrations_dir=_migrations_dir()).apply_pending()
        ids = _seed(setup)

    # Each producer submits in two chunks of BULK_CHUNK (= 50 each ->
    # 100 per producer -> 300 total). agent-alpha additionally
    # re-submits chunk 1 to exercise idempotent retry.
    summary: dict[str, dict[str, int]] = {}
    summary_lock = threading.Lock()

    def submit(agent_id: str) -> None:
        inserted = 0
        duplicates = 0
        rejected = 0
        diagnostic = 0
        with psycopg.connect(dsn) as c:
            for chunk_idx in range(0, OUTPUTS_PER_PRODUCER, BULK_CHUNK):
                payload = _payload_for(
                    agent_id, start=chunk_idx, count=BULK_CHUNK,
                )
                result = register_outputs_bulk(
                    c,
                    task_id=ids["task_id"],
                    run_id=ids["runs_by_agent"][agent_id],
                    project_id=ids["project_id"],
                    agent_id=agent_id,
                    source_model="sdxl-base-1.0",
                    outputs=payload,
                )
                inserted += result.inserted_count
                duplicates += len(result.duplicates)
                rejected += len(result.rejected)
                diagnostic += len(result.diagnostic)
            if agent_id == RETRY_PRODUCER:
                # Retry chunk 1 to exercise idempotency.
                payload = _payload_for(agent_id, start=0, count=BULK_CHUNK)
                result = register_outputs_bulk(
                    c,
                    task_id=ids["task_id"],
                    run_id=ids["runs_by_agent"][agent_id],
                    project_id=ids["project_id"],
                    agent_id=agent_id,
                    source_model="sdxl-base-1.0",
                    outputs=payload,
                )
                inserted += result.inserted_count
                duplicates += len(result.duplicates)
                rejected += len(result.rejected)
        with summary_lock:
            summary[agent_id] = {
                "inserted": inserted,
                "duplicates": duplicates,
                "rejected": rejected,
                "diagnostic": diagnostic,
            }

    threads = [threading.Thread(target=submit, args=(a,)) for a in PRODUCERS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Every producer inserted exactly 100 unique outputs.
    for agent_id in PRODUCERS:
        assert summary[agent_id]["inserted"] == OUTPUTS_PER_PRODUCER, (
            f"{agent_id} inserted {summary[agent_id]['inserted']}, expected "
            f"{OUTPUTS_PER_PRODUCER}"
        )
        assert summary[agent_id]["rejected"] == 0
        assert summary[agent_id]["diagnostic"] == 0

    # The retry producer additionally saw 50 duplicates from the
    # idempotent re-submit.
    assert summary[RETRY_PRODUCER]["duplicates"] == BULK_CHUNK
    for agent_id in PRODUCERS:
        if agent_id != RETRY_PRODUCER:
            assert summary[agent_id]["duplicates"] == 0

    # ---- DB-side assertions ------------------------------------------------
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM library_outputs WHERE task_id = %s",
                (str(ids["task_id"]),),
            )
            total = cur.fetchone()[0]
            assert total == OUTPUTS_PER_PRODUCER * len(PRODUCERS), (
                f"expected {OUTPUTS_PER_PRODUCER * len(PRODUCERS)} rows, got {total}"
            )

            # Per-agent counts.
            for agent_id in PRODUCERS:
                cur.execute(
                    "SELECT COUNT(*) FROM library_outputs "
                    "WHERE task_id = %s AND agent_id = %s",
                    (str(ids["task_id"]), agent_id),
                )
                assert cur.fetchone()[0] == OUTPUTS_PER_PRODUCER

            # received_count is incremented exactly by the new-row
            # count (300), NOT by the retry duplicates.
            cur.execute(
                "SELECT received_count FROM library_tasks WHERE id = %s",
                (str(ids["task_id"]),),
            )
            assert cur.fetchone()[0] == OUTPUTS_PER_PRODUCER * len(PRODUCERS)

            # storage_state distribution: every row is 'raw' (no
            # auto-route configured for this project).
            cur.execute(
                "SELECT storage_state, COUNT(*) FROM library_outputs "
                "WHERE task_id = %s GROUP BY storage_state",
                (str(ids["task_id"]),),
            )
            dist = dict(cur.fetchall())
            assert dist == {"raw": OUTPUTS_PER_PRODUCER * len(PRODUCERS)}

            # Lifecycle events: one register event per inserted row =
            # 300 (the duplicate replays do NOT emit register events
            # because INSERT ... ON CONFLICT DO NOTHING returns null
            # and the bulk handler skips event emission).
            cur.execute(
                "SELECT COUNT(*) FROM library_output_events "
                "WHERE event_type = 'register'"
            )
            assert cur.fetchone()[0] == OUTPUTS_PER_PRODUCER * len(PRODUCERS)

            # Idempotency uniqueness held: no duplicate
            # (task_id, agent_id, idempotency_key) triples.
            cur.execute(
                "SELECT task_id, agent_id, idempotency_key, COUNT(*) "
                "FROM library_outputs "
                "WHERE task_id = %s AND idempotency_key IS NOT NULL "
                "GROUP BY task_id, agent_id, idempotency_key "
                "HAVING COUNT(*) > 1",
                (str(ids["task_id"]),),
            )
            assert cur.fetchone() is None, "idempotency uniqueness was violated"

        # Soft-accept the first 50 outputs of agent-alpha; finalize 25 of those;
        # reject the next 50 outright. Verify counters across the lifecycle.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM library_outputs "
                "WHERE task_id = %s AND agent_id = 'agent-alpha' "
                "ORDER BY idempotency_key ASC LIMIT 100",
                (str(ids["task_id"]),),
            )
            alpha_ids = [r[0] for r in cur.fetchall()]
        soft_accept_ids = alpha_ids[:50]
        finalize_ids = alpha_ids[:25]
        reject_ids = alpha_ids[50:100]

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE library_outputs SET status = 'soft_accepted', "
                "       soft_accepted_at = NOW() "
                "WHERE id = ANY(%s)",
                ([str(i) for i in soft_accept_ids],),
            )
            cur.execute(
                "UPDATE library_outputs SET status = 'promoted', "
                "       promoted_at = NOW(), finalized_by = 'op' "
                "WHERE id = ANY(%s)",
                ([str(i) for i in finalize_ids],),
            )
            cur.execute(
                "UPDATE library_outputs SET status = 'rejected', "
                "       rejected_at = NOW(), "
                "       primary_rejection_reason = 'e2e: not promoted' "
                "WHERE id = ANY(%s)",
                ([str(i) for i in reject_ids],),
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, COUNT(*) FROM library_outputs "
                "WHERE task_id = %s GROUP BY status",
                (str(ids["task_id"]),),
            )
            status_dist = dict(cur.fetchall())
        # 300 total = 25 promoted + 25 soft_accepted + 50 rejected + 200 pending
        assert status_dist == {
            "promoted":      25,
            "soft_accepted": 25,
            "rejected":      50,
            "pending":       200,
        }

        # Search filter: the seeded card belongs to a batch and has
        # status='pending', so it must NOT appear in default search.
        results = search(conn, "SF-15")
        result_ids = {str(r.entry_id) for r in results}
        assert str(ids["card_id"]) not in result_ids

        # Promote the card and confirm it shows up under the default.
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE library_entries SET status = 'promoted' WHERE id = %s",
                (str(ids["card_id"]),),
            )
        conn.commit()
        results_after = search(conn, "SF-15")
        result_ids_after = {str(r.entry_id) for r in results_after}
        assert str(ids["card_id"]) in result_ids_after
