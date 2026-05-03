"""Tests for openrepose.db.migrator (WP-I2-001).

Two layers:
  - Pure unit tests for migration discovery / sort logic — always run.
  - Integration tests that apply the real `001_library_initial.sql`
    against an ephemeral Postgres cluster — skipped when pytest-postgresql
    cannot start one (no Postgres binary available, etc.).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from openrepose.db.migrator import (
    LIBRARY_MIGRATION_LOCK_ID,
    Migration,
    MigrationApplyError,
    Migrator,
    discover_migrations,
)

# ---------------------------------------------------------------------------
# Optional pytest-postgresql fixture wiring. We declare a `library_pg`
# fixture that yields a ready connection against a fresh DB each test.
# Tests that need a real DB declare `library_pg` as a parameter and will
# skip cleanly when the binary is not available.
# ---------------------------------------------------------------------------

PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover - import guard
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass


if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    # NOTE: pytest-postgresql 8 ships `postgres_options` defaults that
    # wrap argument values in single quotes (`log_destination='stderr'`).
    # Postgres on Windows treats the quotes as part of the value and
    # rejects with `FATAL: invalid value for parameter`. Pass an
    # unquoted form so the cluster boots on any platform.
    library_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    library_pg = _factories.postgresql("library_pg_proc")
else:  # pragma: no cover - exercised on environments without Postgres
    @pytest.fixture
    def library_pg():
        pytest.skip(
            "pytest-postgresql or system pg_ctl unavailable; "
            "skipping live-DB migration tests"
        )


def _to_psycopg_dsn(pg_conn) -> str:  # noqa: ANN001
    """Build a psycopg DSN string from a pytest-postgresql connection
    info object. pytest-postgresql 8 uses a `psycopg.Connection` directly,
    so we read `info` for host/user/dbname/port."""
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
# Pure unit tests (no DB)
# ---------------------------------------------------------------------------


def test_discover_returns_empty_for_missing_dir(tmp_path: Path):
    assert discover_migrations(tmp_path / "no-such") == []


def test_discover_sorts_by_numeric_version(tmp_path: Path):
    (tmp_path / "010_ten.sql").write_text("--", encoding="utf-8")
    (tmp_path / "002_two.sql").write_text("--", encoding="utf-8")
    (tmp_path / "001_one.sql").write_text("--", encoding="utf-8")

    migrations = discover_migrations(tmp_path)
    assert [m.version for m in migrations] == [1, 2, 10]
    assert [m.slug for m in migrations] == ["one", "two", "ten"]


def test_discover_skips_unmatched_files(tmp_path: Path):
    (tmp_path / "001_one.sql").write_text("--", encoding="utf-8")
    (tmp_path / "README.md").write_text("notes", encoding="utf-8")
    (tmp_path / "no-prefix.sql").write_text("--", encoding="utf-8")
    (tmp_path / "abc_letters.sql").write_text("--", encoding="utf-8")

    migrations = discover_migrations(tmp_path)
    assert [m.version for m in migrations] == [1]


def test_discover_raises_on_duplicate_version(tmp_path: Path):
    (tmp_path / "001_first.sql").write_text("--", encoding="utf-8")
    (tmp_path / "001_second.sql").write_text("--", encoding="utf-8")

    with pytest.raises(MigrationApplyError):
        discover_migrations(tmp_path)


def test_discover_real_initial_migration_present():
    """The shipped initial migration is discoverable from .product/migrations/."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"
    migrations = discover_migrations(migrations_dir)
    assert any(m.version == 1 for m in migrations), (
        f"001_library_initial.sql not found under {migrations_dir}"
    )
    initial = [m for m in migrations if m.version == 1][0]
    assert initial.slug == "library_initial"


def test_migration_dataclass_reads_sql(tmp_path: Path):
    p = tmp_path / "001_x.sql"
    p.write_text("SELECT 1;", encoding="utf-8")
    m = Migration(version=1, slug="x", path=p)
    assert m.read_sql() == "SELECT 1;"


def test_advisory_lock_id_is_stable_constant():
    """Locking id must never change between releases or two instances
    can race the same migration. Pin it here."""
    assert LIBRARY_MIGRATION_LOCK_ID == 0x0FEED053


# ---------------------------------------------------------------------------
# Integration tests (require a live Postgres)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres / pytest-postgresql",
)
def test_apply_initial_migration_creates_all_tables(library_pg, tmp_path: Path):
    """Apply 001_library_initial.sql against a fresh DB; verify every
    table + the library_search() function exists."""
    import psycopg

    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"

    dsn = _to_psycopg_dsn(library_pg)
    with psycopg.connect(dsn) as conn:
        migrator = Migrator(conn, migrations_dir=migrations_dir)
        applied = migrator.apply_pending()
        assert applied == [1]

        # Idempotent re-apply: no further work.
        assert migrator.apply_pending() == []
        assert migrator.current_version() == 1

        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "ORDER BY table_name"
            )
            tables = {row[0] for row in cur.fetchall()}
            for required in (
                "schema_version",
                "library_entries",
                "tags",
                "entry_tags",
                "prompts",
                "story_beats",
                "notes",
            ):
                assert required in tables, f"missing table {required}"

            # library_search() function exists and returns rows for an
            # empty DB (zero rows is fine).
            cur.execute("SELECT * FROM library_search('test') LIMIT 1")
            cur.fetchall()  # may be empty


@pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres / pytest-postgresql",
)
def test_advisory_lock_serializes_concurrent_applies(library_pg):
    """Open two connections, hold the advisory lock on the first, and
    confirm the second cannot acquire it without waiting. Uses the
    non-blocking `pg_try_advisory_lock` to avoid a deadlock in the test."""
    import psycopg

    dsn = _to_psycopg_dsn(library_pg)
    with psycopg.connect(dsn) as a, psycopg.connect(dsn) as b:
        with a.cursor() as cur_a:
            cur_a.execute(
                "SELECT pg_advisory_lock(%s)", (LIBRARY_MIGRATION_LOCK_ID,)
            )
        a.commit()
        with b.cursor() as cur_b:
            cur_b.execute(
                "SELECT pg_try_advisory_lock(%s)",
                (LIBRARY_MIGRATION_LOCK_ID,),
            )
            row = cur_b.fetchone()
        assert row == (False,), "second session must not acquire held lock"

        # release on a so b can take it
        with a.cursor() as cur_a:
            cur_a.execute(
                "SELECT pg_advisory_unlock(%s)",
                (LIBRARY_MIGRATION_LOCK_ID,),
            )
        a.commit()


@pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres / pytest-postgresql",
)
def test_pg_trgm_extension_enables_fuzzy_match(library_pg):
    """After 001 runs, the `tags.name % query` operator works (proves
    pg_trgm extension was actually created)."""
    import psycopg

    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"

    dsn = _to_psycopg_dsn(library_pg)
    with psycopg.connect(dsn) as conn:
        Migrator(conn, migrations_dir=migrations_dir).apply_pending()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tags (name) VALUES (%s)", ("intimate",))
            conn.commit()
            # Use the trigram similarity function explicitly to avoid the
            # `%` operator clashing with psycopg's parameter placeholder.
            cur.execute(
                "SELECT name FROM tags WHERE similarity(name, %s) > 0.4",
                ("inimate",),
            )
            rows = cur.fetchall()
        assert any(r[0] == "intimate" for r in rows)
