"""CRUD on `library_entries` against an ephemeral PostgreSQL (WP-I2-003).

Skipped on systems without `pg_ctl`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from openrepose.library import (
    LibraryEntry,
    LibraryEntryError,
    LibraryEntryLockedError,
    add_tags,
    create_entry,
    delete_entry,
    get_entry,
    list_entries,
    list_entry_tags,
    set_entry_tags,
    update_entry,
)

PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover - import guard
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

    entries_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    entries_pg = _factories.postgresql("entries_pg_proc")
else:  # pragma: no cover
    @pytest.fixture
    def entries_pg():
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


@pytest.fixture
def migrated_conn(entries_pg):
    """Yield a psycopg connection against an entries_pg DB with migrations applied."""
    import psycopg

    from openrepose.db.migrator import Migrator

    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"

    dsn = _to_dsn(entries_pg)
    conn = psycopg.connect(dsn)
    try:
        Migrator(conn, migrations_dir=migrations_dir).apply_pending()
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CRUD round-trip
# ---------------------------------------------------------------------------


def test_create_round_trip(migrated_conn):
    entry = create_entry(
        migrated_conn,
        avatar_slug="aeri",
        title="Initial pose",
        yaw_bin="her-right-30",
        portrait_path="aeri/portrait.png",
        openpose_json_path="aeri/openpose.json",
        metadata={"source": "test"},
        created_by="test-op",
    )
    migrated_conn.commit()

    assert isinstance(entry, LibraryEntry)
    assert entry.avatar_slug == "aeri"
    assert entry.title == "Initial pose"
    assert entry.yaw_bin == "her-right-30"
    assert entry.metadata == {"source": "test"}
    assert entry.completeness == "partial"
    assert entry.created_by == "test-op"
    assert entry.created_at is not None
    assert entry.updated_at is not None

    fetched = get_entry(migrated_conn, entry.id)
    assert fetched is not None
    assert fetched.id == entry.id
    assert fetched.title == "Initial pose"


def test_create_requires_avatar_slug(migrated_conn):
    with pytest.raises(LibraryEntryError):
        create_entry(migrated_conn, avatar_slug="")


def test_create_validates_completeness(migrated_conn):
    with pytest.raises(LibraryEntryError):
        create_entry(
            migrated_conn, avatar_slug="aeri", completeness="bogus"
        )


def test_get_returns_none_for_missing_id(migrated_conn):
    from uuid import uuid4

    assert get_entry(migrated_conn, uuid4()) is None


def test_list_entries_filters_and_orders(migrated_conn):
    a = create_entry(migrated_conn, avatar_slug="aeri", yaw_bin="0")
    b = create_entry(migrated_conn, avatar_slug="aeri", yaw_bin="her-right-30")
    c = create_entry(migrated_conn, avatar_slug="bee", yaw_bin="0")
    migrated_conn.commit()

    only_aeri = list_entries(migrated_conn, avatar_slug="aeri")
    assert {e.id for e in only_aeri} == {a.id, b.id}

    only_zero = list_entries(migrated_conn, yaw_bin="0")
    assert {e.id for e in only_zero} == {a.id, c.id}

    # All three returned (created_at ties in one transaction so we can't
    # assert a deterministic intra-tx order; test the set membership).
    all_entries = list_entries(migrated_conn)
    assert {e.id for e in all_entries} >= {a.id, b.id, c.id}


def test_update_patches_only_supplied_fields(migrated_conn):
    e = create_entry(migrated_conn, avatar_slug="aeri", title="orig")
    migrated_conn.commit()

    updated = update_entry(
        migrated_conn,
        e.id,
        operator_slug="test-op",
        title="updated",
        completeness="complete",
        metadata={"k": "v"},
    )
    migrated_conn.commit()

    assert updated.title == "updated"
    assert updated.completeness == "complete"
    assert updated.metadata == {"k": "v"}
    assert updated.locked_by == "test-op"
    # avatar_slug untouched.
    assert updated.avatar_slug == "aeri"
    # updated_at advanced.
    assert updated.updated_at >= e.updated_at


def test_update_rejects_unknown_or_immutable_fields(migrated_conn):
    e = create_entry(migrated_conn, avatar_slug="aeri")
    migrated_conn.commit()

    with pytest.raises(LibraryEntryError):
        update_entry(migrated_conn, e.id, created_at="2026-01-01")
    with pytest.raises(LibraryEntryError):
        update_entry(migrated_conn, e.id, bogus="x")


def test_update_with_no_patch_raises(migrated_conn):
    e = create_entry(migrated_conn, avatar_slug="aeri")
    migrated_conn.commit()
    with pytest.raises(LibraryEntryError):
        update_entry(migrated_conn, e.id)


def test_delete_returns_true_then_false(migrated_conn):
    e = create_entry(migrated_conn, avatar_slug="aeri")
    migrated_conn.commit()
    assert delete_entry(migrated_conn, e.id) is True
    migrated_conn.commit()
    assert delete_entry(migrated_conn, e.id) is False


def test_delete_cascades_to_entry_tags(migrated_conn):
    e = create_entry(migrated_conn, avatar_slug="aeri")
    add_tags(migrated_conn, e.id, ["pose:0", "mood:intimate"])
    migrated_conn.commit()
    assert sorted(list_entry_tags(migrated_conn, e.id)) == [
        "mood:intimate",
        "pose:0",
    ]
    delete_entry(migrated_conn, e.id)
    migrated_conn.commit()
    # No tags left.
    assert list_entry_tags(migrated_conn, e.id) == []


# ---------------------------------------------------------------------------
# Row locking
# ---------------------------------------------------------------------------


def test_update_lock_collision_raises_locked_error(entries_pg):
    """Two parallel sessions: A holds the row lock, B trying to UPDATE
    surfaces `LibraryEntryLockedError`."""
    import psycopg

    from openrepose.db.migrator import Migrator

    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"

    dsn = _to_dsn(entries_pg)
    with psycopg.connect(dsn) as setup:
        Migrator(setup, migrations_dir=migrations_dir).apply_pending()
        e = create_entry(setup, avatar_slug="aeri", title="t")
        setup.commit()

    with psycopg.connect(dsn) as a, psycopg.connect(dsn) as b:
        # A holds the lock by selecting FOR UPDATE in an open transaction.
        with a.cursor() as cur_a:
            cur_a.execute(
                "SELECT id FROM library_entries WHERE id = %s FOR UPDATE",
                (str(e.id),),
            )
        # B's update_entry must fail fast (NOWAIT).
        with pytest.raises(LibraryEntryLockedError):
            update_entry(b, e.id, operator_slug="op-b", title="conflict")
        a.rollback()  # release the lock


# ---------------------------------------------------------------------------
# set_entry_tags additive vs. replace + auto-tag preservation
# ---------------------------------------------------------------------------


def test_set_entry_tags_replace_preserves_auto_tags_by_default(migrated_conn):
    e = create_entry(migrated_conn, avatar_slug="aeri")
    add_tags(migrated_conn, e.id, ["mood:intimate", "auto:model:flux"])
    migrated_conn.commit()

    result = set_entry_tags(
        migrated_conn,
        e.id,
        ["pose:her-right-30", "lighting:lowkey"],
        replace=True,
    )
    migrated_conn.commit()
    # Manual `mood:intimate` is gone; auto: tag stays.
    assert "mood:intimate" not in result
    assert "auto:model:flux" in result
    assert "pose:her-right-30" in result
    assert "lighting:lowkey" in result


def test_set_entry_tags_replace_with_preserve_auto_false_drops_auto(migrated_conn):
    e = create_entry(migrated_conn, avatar_slug="aeri")
    add_tags(migrated_conn, e.id, ["auto:model:flux", "manual:keep"])
    migrated_conn.commit()
    result = set_entry_tags(
        migrated_conn,
        e.id,
        ["new:tag"],
        replace=True,
        preserve_auto=False,
    )
    migrated_conn.commit()
    assert "new:tag" in result
    assert "auto:model:flux" not in result
    assert "manual:keep" not in result


def test_add_tags_dedupes_and_normalizes(migrated_conn):
    e = create_entry(migrated_conn, avatar_slug="aeri")
    add_tags(migrated_conn, e.id, ["MOOD:Intimate", "  mood:intimate  ", "POSE:0"])
    migrated_conn.commit()
    tags = list_entry_tags(migrated_conn, e.id)
    assert "mood:intimate" in tags
    assert "pose:0" in tags
    assert tags.count("mood:intimate") == 1
