"""Tests for the AMood Python-side dedupe wrapper (WP-I3-006).

The SQL-level `library.dedupe_check` function is exercised by
`test_db_migrator_i3.py`; this file exercises the
`library.amood.dedupe.check_card_pre_insert` Python wrapper that the
dispatcher calls through `library_create_card`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from openrepose.library.amood import compose_signature
from openrepose.library.amood.dedupe import (
    DEDUPE_AXIS_COUNT,
    DedupeInputError,
    check_card_pre_insert,
)


PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass


if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    amood_dedupe_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    amood_dedupe_pg = _factories.postgresql("amood_dedupe_pg_proc")
else:  # pragma: no cover

    @pytest.fixture
    def amood_dedupe_pg():
        pytest.skip("no system Postgres / pytest-postgresql")


pytestmark = pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres / pytest-postgresql",
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


def _seed_minimal(conn):  # noqa: ANN001
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_projects (slug, name, owner_slug) "
            "VALUES ('p', 'P', 'op') RETURNING id"
        )
        project_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO library_tasks (project_id, slug, intake_dir) "
            "VALUES (%s, 't', 't/') RETURNING id",
            (project_id,),
        )
        task_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO library_batches (project_id, task_id, slug) "
            "VALUES (%s, %s, 'b') RETURNING id",
            (project_id, task_id),
        )
        batch_id = cur.fetchone()[0]
    conn.commit()
    return project_id, batch_id


def _seed_card(conn, batch_id, slug, signature, status="promoted"):  # noqa: ANN001
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_entries "
            "(avatar_slug, title, batch_id, status, dedupe_signature, "
            " compatibility_signature) "
            "VALUES ('aeri', %s, %s, %s, %s, '') RETURNING id",
            (slug, batch_id, status, signature),
        )
        return cur.fetchone()[0]


def test_compose_signature_canonical_eight_axes():
    sig = compose_signature(
        explicit_family="pussy",
        pose_family="standing",
        orientation="frontal",
        wardrobe_state="robe-open",
        support_object="bed-edge",
        setting_family="hotel",
        camera_family="eye-level",
        palette_family="warm",
    )
    assert sig.count("|") == DEDUPE_AXIS_COUNT - 1
    assert sig == "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm"


def test_compose_signature_pipe_in_axis_value_is_sanitized():
    """Pipe in an axis value collides with the delimiter; substituted
    with '/' so round-trip never collides accidentally."""
    sig = compose_signature(explicit_family="a|b")
    assert sig.startswith("a/b|")


def test_check_card_pre_insert_rejects_wrong_axis_count(amood_dedupe_pg):
    import psycopg

    from openrepose.db.migrator import Migrator

    with psycopg.connect(_dsn(amood_dedupe_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        project_id, _ = _seed_minimal(conn)
        with pytest.raises(DedupeInputError):
            check_card_pre_insert(
                conn,
                project_id=project_id,
                dedupe_signature="too|few|axes",
            )


def test_check_card_pre_insert_returns_overlap_at_threshold(amood_dedupe_pg):
    import psycopg

    from openrepose.db.migrator import Migrator

    with psycopg.connect(_dsn(amood_dedupe_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        project_id, batch_id = _seed_minimal(conn)
        # Existing accepted card with a known signature.
        full_match = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm"
        seven_match = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|cool"
        five_match = "pussy|standing|frontal|robe-open|bed-edge|park|low|cool"
        _seed_card(conn, batch_id, "C8", full_match, status="promoted")
        _seed_card(conn, batch_id, "C7", seven_match, status="promoted")
        _seed_card(conn, batch_id, "C5", five_match, status="promoted")

        match = check_card_pre_insert(
            conn,
            project_id=project_id,
            dedupe_signature=full_match,
            threshold=6,
        )
    assert match.has_overlap is True
    slugs = {c.candidate_slug for c in match.candidates}
    assert slugs == {"C8", "C7"}
    assert match.candidates[0].overlap_count == 8


def test_check_card_pre_insert_threshold_higher_filters_partial(amood_dedupe_pg):
    import psycopg

    from openrepose.db.migrator import Migrator

    with psycopg.connect(_dsn(amood_dedupe_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        project_id, batch_id = _seed_minimal(conn)
        seven_match = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|cool"
        _seed_card(conn, batch_id, "C7", seven_match, status="promoted")

        full = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm"
        match = check_card_pre_insert(
            conn,
            project_id=project_id,
            dedupe_signature=full,
            threshold=8,
        )
    assert match.has_overlap is False


def test_check_card_pre_insert_excludes_pending_status(amood_dedupe_pg):
    """Cards with status='pending' (or any non-accepted/promoted) must not
    drive the dedupe surface — only soft_accepted/promoted compete."""
    import psycopg

    from openrepose.db.migrator import Migrator

    with psycopg.connect(_dsn(amood_dedupe_pg)) as conn:
        Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()
        project_id, batch_id = _seed_minimal(conn)
        full = "pussy|standing|frontal|robe-open|bed-edge|hotel|eye-level|warm"
        _seed_card(conn, batch_id, "C-pending", full, status="pending")

        match = check_card_pre_insert(
            conn,
            project_id=project_id,
            dedupe_signature=full,
            threshold=6,
        )
    assert match.has_overlap is False
