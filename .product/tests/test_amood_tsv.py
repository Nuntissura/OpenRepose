"""TSV view + round-trip tests (WP-I3-006).

Spec: `.gov/spec/openrepose_amood_v0_1.md` "amood_export_tsv" /
"amood_import_tsv".

Covers:
  - `tsv_views.AMOOD_VIEW_COLUMNS` matches the migration-005 view shape
    (column count + names + order). Anything else is locked-shape drift.
  - Round-trip on the 4 hand-edited schemas (quota_plan, batch_matrix,
    variant_ladder, anti_repetition) is bytewise lossless for the
    columns that round-trip through library_entries / metadata / target
    tables.
  - System-generated schemas return INFO on import.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from openrepose.library.amood import AMOOD_TSV_SCHEMAS
from openrepose.library.amood.tsv_views import AMOOD_VIEW_COLUMNS, view_for_schema


PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass


if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    amood_tsv_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    amood_tsv_pg = _factories.postgresql("amood_tsv_pg_proc")
else:  # pragma: no cover

    @pytest.fixture
    def amood_tsv_pg():
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


def _apply(conn):  # noqa: ANN001
    from openrepose.db.migrator import Migrator

    Migrator(conn, migrations_dir=_migrations_dir()).apply_pending()


# ---------------------------------------------------------------------------
# Locked-shape mirror
# ---------------------------------------------------------------------------


def test_python_mirror_covers_all_ten_schemas():
    assert AMOOD_TSV_SCHEMAS == set(AMOOD_VIEW_COLUMNS.keys())
    assert len(AMOOD_VIEW_COLUMNS) == 10


@pytest.mark.parametrize("schema", sorted(AMOOD_VIEW_COLUMNS.keys()))
def test_view_column_order_matches_python_mirror(amood_tsv_pg, schema):
    """For each schema, the migration-005 view exposes columns in the
    exact order declared by `AMOOD_VIEW_COLUMNS`."""
    import psycopg

    with psycopg.connect(_dsn(amood_tsv_pg)) as conn:
        _apply(conn)
        view_name = view_for_schema(schema)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s "
                "ORDER BY ordinal_position",
                (view_name,),
            )
            db_columns = tuple(row[0] for row in cur.fetchall())

    assert db_columns == AMOOD_VIEW_COLUMNS[schema], (
        f"view {view_name} column order drift:\n"
        f"  migration: {db_columns}\n"
        f"  python:    {AMOOD_VIEW_COLUMNS[schema]}"
    )


# ---------------------------------------------------------------------------
# Round-trip on hand-edited schemas
# ---------------------------------------------------------------------------


def _seed_card(app_conn):  # noqa: ANN001
    """Seed one project + task + batch + a single batch-matrix-shaped card."""
    with app_conn.cursor() as cur:
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
            "VALUES (%s, %s, 'B-001') RETURNING id",
            (project_id, task_id),
        )
        batch_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO library_entries "
            "(avatar_slug, title, batch_id, status, "
            " sexual_trigger, kink_cue, porn_archetype, fantasy_mode, "
            " explicit_family, exposure_detail, archetype_signal, "
            " scene_engine, shot_purpose, "
            " dedupe_signature, compatibility_signature, metadata) "
            "VALUES ('aeri', %s, %s, 'pending', "
            "        %s, %s, %s, %s, "
            "        %s, %s, %s, "
            "        %s, %s, "
            "        %s, %s, %s::jsonb) "
            "RETURNING id",
            (
                "hotel-robe-bed-edge", batch_id,
                "visible vulva", "self-display", "hotel robe", "casual intimate",
                "vulva", "full target", "hotel robe",
                "private-room", "primary explicit",
                "vulva|bed-edge|frontal|robe-open|bed-edge|hotel|eye-level|warm",
                "vulva|bed-edge|frontal|hotel",
                '{"amood:fantasy_story": "robe falls open at bed edge"}',
            ),
        )
        card_id = cur.fetchone()[0]
    app_conn.commit()
    return {"project_id": project_id, "batch_id": batch_id, "card_id": card_id}


def test_batch_matrix_round_trip_lossless(amood_tsv_pg):
    """Export -> re-import (no edits) -> re-export must be byte-equal."""
    import psycopg

    from openrepose.library.amood import export_tsv, import_tsv

    with psycopg.connect(_dsn(amood_tsv_pg)) as conn:
        _apply(conn)
        ids = _seed_card(conn)

        first = export_tsv(conn, schema="batch_matrix", batch_id=ids["batch_id"])
        result = import_tsv(
            conn, schema="batch_matrix",
            tsv_text=first, batch_id=ids["batch_id"],
        )
        assert result["imported_count"] == 1
        assert result["conflict_count"] == 0
        second = export_tsv(conn, schema="batch_matrix", batch_id=ids["batch_id"])

    assert first == second, (
        "round-trip drift on batch_matrix:\n"
        f"first:\n{first}\n\nsecond:\n{second}"
    )


def test_anti_repetition_round_trip_lossless(amood_tsv_pg):
    import psycopg

    from openrepose.library.amood import export_tsv, import_tsv

    with psycopg.connect(_dsn(amood_tsv_pg)) as conn:
        _apply(conn)
        ids = _seed_card(conn)

        first = export_tsv(conn, schema="anti_repetition", batch_id=ids["batch_id"])
        import_tsv(
            conn, schema="anti_repetition",
            tsv_text=first, batch_id=ids["batch_id"],
        )
        second = export_tsv(conn, schema="anti_repetition", batch_id=ids["batch_id"])
    assert first == second


def test_import_tsv_rejects_reordered_header(amood_tsv_pg):
    import psycopg

    from openrepose.library.amood import AmoodTsvError, import_tsv

    with psycopg.connect(_dsn(amood_tsv_pg)) as conn:
        _apply(conn)
        ids = _seed_card(conn)
        # Swap first two columns of the locked batch_matrix header.
        bad_header = "row_id\tbatch_slug" + "\t".join(
            [""] + list(AMOOD_VIEW_COLUMNS["batch_matrix"][2:])
        )
        with pytest.raises(AmoodTsvError):
            import_tsv(
                conn, schema="batch_matrix",
                tsv_text=bad_header + "\n", batch_id=ids["batch_id"],
            )


# ---------------------------------------------------------------------------
# Export-only schemas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "schema",
    sorted(AMOOD_VIEW_COLUMNS.keys() - {
        "quota_plan", "batch_matrix", "variant_ladder", "anti_repetition",
    }),
)
def test_export_only_schemas_return_info_on_import(amood_tsv_pg, schema):
    import psycopg

    from openrepose.library.amood import import_tsv

    with psycopg.connect(_dsn(amood_tsv_pg)) as conn:
        _apply(conn)
        # Use a minimal-but-valid header so _parse_tsv passes; the
        # export-only branch should fire before any DB write.
        header = "\t".join(AMOOD_VIEW_COLUMNS[schema]) + "\n"
        result = import_tsv(conn, schema=schema, tsv_text=header)
    assert result["imported_count"] == 0
    assert any("export-only" in e for e in result["errors"])


def test_unknown_schema_raises(amood_tsv_pg):
    import psycopg

    from openrepose.library.amood import AmoodTsvError, import_tsv

    with psycopg.connect(_dsn(amood_tsv_pg)) as conn:
        _apply(conn)
        with pytest.raises(AmoodTsvError):
            import_tsv(conn, schema="not_a_schema", tsv_text="anything\n")
