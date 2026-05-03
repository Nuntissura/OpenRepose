"""Multi-operator concurrency verification (WP-I2-008).

Closes the spec's "Multi-Operator Concurrency" promotion guard for v0.1
of Feature 3:

  * Two LibraryPool clients sharing a DB; row-level NOWAIT lock from
    one fails the other's update with `LibraryEntryLockedError`.
  * `pg_advisory_lock` serializes parallel migrator runs (no double-apply).
  * Two operators interleaving register + tag mutations on different
    rows do not interfere.

Skipped on systems without a Postgres binary.
"""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

import pytest

PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass


pytestmark = pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres / pytest-postgresql",
)


if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    multi_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    multi_pg = _factories.postgresql("multi_pg_proc")
else:  # pragma: no cover
    @pytest.fixture
    def multi_pg():
        pytest.skip("no Postgres")


def _to_dsn(pg_conn) -> str:  # noqa: ANN001
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


# ---------------------------------------------------------------------------
# Two LibraryPool clients sharing a DB — simulates two OpenRepose
# instances against the same library.
# ---------------------------------------------------------------------------


def test_two_pools_share_database(multi_pg, tmp_path: Path):
    import psycopg

    from openrepose.db.migrator import Migrator
    from openrepose.db.pool import LibraryPool
    from openrepose.library import create_entry, get_entry

    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"
    dsn = _to_dsn(multi_pg)

    # Bootstrap: apply migrations once.
    with psycopg.connect(dsn) as conn:
        Migrator(conn, migrations_dir=migrations_dir).apply_pending()

    pool_a = LibraryPool(dsn, min_size=1, max_size=2)
    pool_b = LibraryPool(dsn, min_size=1, max_size=2)
    pool_a.open()
    pool_b.open()
    try:
        # Operator A inserts an entry; Operator B reads it back.
        with pool_a.connection() as conn_a:
            entry = create_entry(conn_a, avatar_slug="aeri", title="from-A")
            conn_a.commit()
        with pool_b.connection() as conn_b:
            fetched = get_entry(conn_b, entry.id)
            assert fetched is not None
            assert fetched.title == "from-A"
    finally:
        pool_a.close()
        pool_b.close()


def test_lock_collision_between_pools(multi_pg, tmp_path: Path):
    """A holds the row lock; B's update_entry must raise
    LibraryEntryLockedError without blocking forever (NOWAIT)."""
    import psycopg

    from openrepose.db.migrator import Migrator
    from openrepose.library import (
        LibraryEntryLockedError,
        create_entry,
        update_entry,
    )

    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"
    dsn = _to_dsn(multi_pg)

    with psycopg.connect(dsn) as setup:
        Migrator(setup, migrations_dir=migrations_dir).apply_pending()
        e = create_entry(setup, avatar_slug="aeri", title="contested")
        setup.commit()

    with psycopg.connect(dsn) as a, psycopg.connect(dsn) as b:
        with a.cursor() as cur_a:
            cur_a.execute(
                "SELECT id FROM library_entries WHERE id = %s FOR UPDATE",
                (str(e.id),),
            )
        with pytest.raises(LibraryEntryLockedError):
            update_entry(b, e.id, operator_slug="op-b", title="conflict")
        a.rollback()


# ---------------------------------------------------------------------------
# Migrator advisory lock under parallel start — proves a second
# OpenRepose instance starting concurrently waits + sees zero pending
# migrations after the first instance commits.
# ---------------------------------------------------------------------------


def test_advisory_lock_prevents_double_apply(multi_pg):
    import psycopg

    from openrepose.db.migrator import Migrator

    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"
    dsn = _to_dsn(multi_pg)

    apply_results: dict[str, list[int]] = {}

    def _try_apply(label: str) -> None:
        with psycopg.connect(dsn) as conn:
            apply_results[label] = Migrator(
                conn, migrations_dir=migrations_dir
            ).apply_pending()

    t1 = threading.Thread(target=_try_apply, args=("a",))
    t2 = threading.Thread(target=_try_apply, args=("b",))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert not t1.is_alive() and not t2.is_alive(), (
        "advisory lock did not release within deadline"
    )

    total_applied = (apply_results.get("a") or []) + (apply_results.get("b") or [])
    # Migration version 1 must appear *exactly once* across both threads —
    # no double-apply even though both raced.
    assert total_applied.count(1) == 1


# ---------------------------------------------------------------------------
# Interleaved per-operator activity on different rows — proves the lock
# strategy does not falsely block independent writers.
# ---------------------------------------------------------------------------


def test_interleaved_writes_on_different_rows(multi_pg):
    import psycopg

    from openrepose.db.migrator import Migrator
    from openrepose.library import (
        add_tags,
        create_entry,
        list_entry_tags,
    )

    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"
    dsn = _to_dsn(multi_pg)

    with psycopg.connect(dsn) as setup:
        Migrator(setup, migrations_dir=migrations_dir).apply_pending()

    results: dict[str, str] = {}

    def _writer(slug: str, label: str) -> None:
        try:
            with psycopg.connect(dsn) as conn:
                e = create_entry(conn, avatar_slug=slug, title=f"{label}-row")
                add_tags(conn, e.id, [f"by:{label}", f"slug:{slug}"])
                conn.commit()
                results[label] = str(e.id)
        except Exception as exc:  # noqa: BLE001
            results[label] = f"err: {exc}"

    threads = [
        threading.Thread(target=_writer, args=("aeri", "op1")),
        threading.Thread(target=_writer, args=("bee", "op2")),
        threading.Thread(target=_writer, args=("cara", "op3")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive()

    assert all(not v.startswith("err") for v in results.values()), results
    assert len({v for v in results.values()}) == 3  # three distinct entry ids

    with psycopg.connect(dsn) as conn:
        for label, eid in results.items():
            tags = list_entry_tags(conn, eid)
            assert f"by:{label}" in tags
