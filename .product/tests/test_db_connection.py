"""Tests for openrepose.db.pool (WP-I2-001).

Live-DB tests require a system Postgres (pytest-postgresql); they skip
otherwise. Pure unit tests that don't need a server always run.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from openrepose.db.pool import LibraryPool, LibraryPoolError, _redact

PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover - import guard
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass


if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    # See test_db_migrator.py for the rationale: avoid the single-quoted
    # default postgres_options that break on Windows.
    pool_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    pool_pg = _factories.postgresql("pool_pg_proc")
else:  # pragma: no cover
    @pytest.fixture
    def pool_pg():
        pytest.skip("no system Postgres / pytest-postgresql")


def _to_psycopg_dsn(pg_conn) -> str:  # noqa: ANN001
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
# Pure unit (no DB)
# ---------------------------------------------------------------------------


def test_pool_with_empty_dsn_is_unconfigured():
    p = LibraryPool("")
    assert p.is_configured is False
    assert p.is_open is False
    assert p.is_connected is False
    assert p.schema_version() == 0
    assert p.dsn == ""


def test_pool_with_whitespace_dsn_is_unconfigured():
    p = LibraryPool("   ")
    assert p.is_configured is False
    assert p.is_open is False


def test_pool_with_dsn_is_configured_but_not_yet_open():
    p = LibraryPool("postgresql://x:y@h/d")
    assert p.is_configured is True
    assert p.is_open is False
    assert p.is_connected is False


def test_pool_open_with_empty_dsn_is_noop():
    """Operator hasn't set library_db_url; open() must not raise."""
    p = LibraryPool("")
    p.open()  # no exception
    assert p.is_open is False


def test_pool_open_with_bad_dsn_raises_library_pool_error():
    """Bad DSN must surface as `LibraryPoolError`, leave `is_open=False`,
    and record an `open_error`. We pass a tiny `open_timeout` so the test
    is not blocked by psycopg_pool's 30s default."""
    p = LibraryPool(
        "postgresql://nouser:nopass@127.0.0.1:1/none",
        min_size=1,
        max_size=1,
        open_timeout=2.0,
    )
    with pytest.raises(LibraryPoolError):
        p.open()
    assert p.is_open is False
    assert p.open_error is not None


def test_redact_helper_masks_password():
    assert (
        _redact("postgresql://user:secret@host:5432/db")
        == "postgresql://user:***@host:5432/db"
    )


def test_redact_helper_passes_through_no_password():
    assert _redact("postgresql://localhost/db") == "postgresql://localhost/db"


# ---------------------------------------------------------------------------
# Integration (needs Postgres)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres",
)
def test_pool_open_health_check_against_real_db(pool_pg):
    dsn = _to_psycopg_dsn(pool_pg)
    p = LibraryPool(dsn, min_size=1, max_size=2)
    p.open()
    try:
        assert p.is_open is True
        assert p.is_connected is True
        # schema_version table doesn't exist yet on a fresh DB.
        assert p.schema_version() == 0

        with p.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone() == (1,)
    finally:
        p.close()
        assert p.is_open is False


@pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres",
)
def test_app_boots_with_live_db_and_runs_migrations(pool_pg, tmp_path: Path):
    """End-to-end: construct an `App` with `library_db_url` pointing at
    the ephemeral DB; verify the migrator runs and `state.library`
    reflects connected=true / schema_version=5 (001 + I3 trio 002/003/004 + AMood views 005)."""
    import json

    from openrepose.app import App
    from openrepose.settings import Settings

    dsn = _to_psycopg_dsn(pool_pg)

    # Seed a settings.json so App picks up the DSN at construction.
    settings = Settings(
        library_db_url=dsn,
        operator_slug="test-op",
        settings_path=tmp_path / "settings.json",
    )
    settings.save()

    app = App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
    )
    try:
        # Pool is connected and migrations ran.
        assert app.library_pool.is_open is True
        assert app.library_pool.is_connected is True
        assert app.library_pool.schema_version() >= 6  # WP-I4-001: bumped 5 -> 6
        # state.json reflects the library block.
        state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        lib = state.get("library", {})
        assert lib.get("connected") is True
        assert lib.get("configured") is True
        assert lib.get("schema_version") >= 6  # WP-I4-001: bumped 5 -> 6
        assert lib.get("operator_slug") == "test-op"
        assert lib.get("db_url_redacted")  # non-empty (redacted form)
    finally:
        app.stop()


@pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres",
)
def test_pool_schema_version_after_migration(pool_pg):
    """After applying every shipped migration, schema_version() reads
    the highest version number on disk. Currently 6 after WP-I4-001
    landed migration 006."""
    import psycopg

    from openrepose.db.migrator import Migrator

    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"

    dsn = _to_psycopg_dsn(pool_pg)
    p = LibraryPool(dsn, min_size=1, max_size=2)
    p.open()
    try:
        # Apply migration via a separate connection.
        with psycopg.connect(dsn) as conn:
            Migrator(conn, migrations_dir=migrations_dir).apply_pending()
        assert p.schema_version() >= 6  # WP-I4-001 baseline
    finally:
        p.close()
