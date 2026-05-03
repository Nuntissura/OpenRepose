"""pg_dump + pg_restore round-trip (WP-I2-008).

Closes the spec promotion guard:
"pg_dump + restore round-trip preserves all entries + tags + prompts +
story_beats + notes verbatim".

Uses the system `pg_dump` / `pg_restore` binaries (the same install
that pytest-postgresql is already using). Skipped on systems without
them.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PG_AVAILABLE = (
    shutil.which("pg_ctl") is not None
    and shutil.which("pg_dump") is not None
    and shutil.which("pg_restore") is not None
)
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass


pytestmark = pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres / pg_dump / pg_restore",
)


if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    dump_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    dump_pg = _factories.postgresql("dump_pg_proc")
else:  # pragma: no cover
    @pytest.fixture
    def dump_pg():
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


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def test_pg_dump_round_trip_preserves_entries_tags_prompts(dump_pg, tmp_path: Path):
    import psycopg

    from openrepose.db.migrator import Migrator
    from openrepose.library import (
        add_prompt,
        add_tags,
        add_text_record,
        create_entry,
        get_entry,
        list_entry_tags,
        list_prompts,
        list_text_records,
    )

    repo_root = Path(__file__).resolve().parent.parent.parent
    migrations_dir = repo_root / ".product" / "migrations"
    info = dump_pg.info
    src_dsn = _to_dsn(dump_pg)

    # Seed: migrate + insert a representative spread of records.
    seed_records: dict[str, dict[str, list[str]]] = {}
    with psycopg.connect(src_dsn) as conn:
        Migrator(conn, migrations_dir=migrations_dir).apply_pending()
        for slug in ("aeri", "bee", "cara"):
            e = create_entry(conn, avatar_slug=slug, title=f"{slug}-master")
            add_tags(conn, e.id, [f"avatar:{slug}", "mood:intimate"])
            add_prompt(conn, e.id, positive=f"{slug} positive", negative="blurry")
            add_text_record(conn, "story_beats", e.id, body=f"beat for {slug}")
            add_text_record(conn, "notes", e.id, body=f"note about {slug}")
            seed_records[str(e.id)] = {
                "tags": list_entry_tags(conn, e.id),
                "prompts_positive": [p.positive for p in list_prompts(conn, e.id)],
                "story": [r.body for r in list_text_records(conn, "story_beats", e.id)],
                "notes": [r.body for r in list_text_records(conn, "notes", e.id)],
            }
        conn.commit()

    # Dump to a custom-format archive.
    dump_path = tmp_path / "library.dump"
    _run([
        "pg_dump",
        f"--host={info.host}",
        f"--port={info.port}",
        f"--username={info.user}",
        "--no-password",
        "--format=custom",
        f"--file={dump_path}",
        info.dbname,
    ])
    assert dump_path.exists() and dump_path.stat().st_size > 0

    # Drop & recreate the DB on the same cluster.
    fresh_db = info.dbname + "_restored"
    with psycopg.connect(
        host=info.host,
        port=info.port,
        user=info.user,
        dbname="postgres",
        autocommit=True,
    ) as admin:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{fresh_db}"')
            cur.execute(f'CREATE DATABASE "{fresh_db}"')

    _run([
        "pg_restore",
        f"--host={info.host}",
        f"--port={info.port}",
        f"--username={info.user}",
        "--no-password",
        f"--dbname={fresh_db}",
        str(dump_path),
    ])

    # Verify every seed record is back, intact.
    restored_dsn = (
        f"host={info.host} port={info.port} user={info.user} dbname={fresh_db}"
    )
    with psycopg.connect(restored_dsn) as conn:
        for eid, expect in seed_records.items():
            assert get_entry(conn, eid) is not None, f"missing {eid}"
            assert sorted(list_entry_tags(conn, eid)) == sorted(expect["tags"])
            assert (
                [p.positive for p in list_prompts(conn, eid)]
                == expect["prompts_positive"]
            )
            assert (
                [r.body for r in list_text_records(conn, "story_beats", eid)]
                == expect["story"]
            )
            assert (
                [r.body for r in list_text_records(conn, "notes", eid)]
                == expect["notes"]
            )
