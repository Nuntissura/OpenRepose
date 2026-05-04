"""End-to-end tests for the 7 library LLM commands (WP-I2-004).

Constructs a real `App` against an ephemeral PostgreSQL fixture; sends
commands through `app.handle_command`. Skipped on systems without a
Postgres binary.
"""

from __future__ import annotations

import base64
import json
import shutil
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

    library_cmd_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    library_cmd_pg = _factories.postgresql("library_cmd_proc")
else:  # pragma: no cover
    @pytest.fixture
    def library_cmd_pg():
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
def lib_app(library_cmd_pg, tmp_path: Path):
    """Construct a fully-wired App against the ephemeral DB. Yields the
    App; tears down via `app.stop()`."""
    from openrepose.app import App
    from openrepose.settings import Settings

    dsn = _to_dsn(library_cmd_pg)
    settings = Settings(
        library_db_url=dsn,
        library_root=str(tmp_path / "library"),
        operator_slug="ilja",
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
        assert app.library_pool.is_connected, "library pool failed to open"
        yield app
    finally:
        app.stop()


# ---------------------------------------------------------------------------
# register_library_entry
# ---------------------------------------------------------------------------


def test_register_returns_entry_id_and_writes_files(lib_app, tmp_path: Path):
    payload = {
        "command": "register_library_entry",
        "avatar_slug": "aeri",
        "title": "Test pose",
        "yaw_bin": "her-right-30",
        "openpose_json": base64.b64encode(b'{"version":1.3}').decode(),
        "generated_image": base64.b64encode(b"PNG bytes").decode(),
        "comfyui_workflow": {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "fluxDev_v2.safetensors"},
            },
            "2": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "dpmpp_2m", "scheduler": "karras"},
            },
        },
        "metadata": {"cfg": 7.0, "steps": 20},
        "tags": ["mood:intimate"],
        "prompts": {"positive": "studio lighting", "negative": "blurry"},
        "story_beats": "the heroine walks in",
        "notes": ["operator note 1", "operator note 2"],
    }
    r = lib_app.handle_command(payload)
    assert r.status == "ok", r.payload
    eid = r.payload["entry_id"]
    assert isinstance(eid, str) and len(eid) == 36
    smart = r.payload["smart_tags"]
    assert "auto:model:fluxdev_v2.safetensors" in smart

    # Files landed under <library_root>/<eid>/...
    lib_root = Path(lib_app.settings.library_root)
    assert (lib_root / eid / "openpose.json").exists()
    assert (lib_root / eid / "generated.png").exists()


def test_register_rejects_missing_avatar_slug(lib_app):
    r = lib_app.handle_command(
        {"command": "register_library_entry", "title": "x"}
    )
    assert r.status == "error"
    assert "avatar_slug" in r.payload["reason"]


# ---------------------------------------------------------------------------
# get_library_entry
# ---------------------------------------------------------------------------


def test_get_returns_full_entry_with_subrecords(lib_app):
    r = lib_app.handle_command(
        {
            "command": "register_library_entry",
            "avatar_slug": "aeri",
            "title": "rich",
            "tags": ["pose:0"],
            "prompts": {"positive": "p1", "negative": "n1"},
            "story_beats": ["b1", "b2"],
            "notes": "single note",
        }
    )
    eid = r.payload["entry_id"]
    g = lib_app.handle_command({"command": "get_library_entry", "entry_id": eid})
    assert g.status == "ok"
    body = g.payload
    assert body["title"] == "rich"
    assert "pose:0" in body["tags"]
    assert len(body["prompts"]) == 1
    assert body["prompts"][0]["positive"] == "p1"
    assert len(body["story_beats"]) == 2
    assert len(body["notes"]) == 1


def test_get_missing_returns_error(lib_app):
    r = lib_app.handle_command(
        {
            "command": "get_library_entry",
            "entry_id": "00000000-0000-0000-0000-000000000000",
        }
    )
    assert r.status == "error"
    assert "not found" in r.payload["reason"]


# ---------------------------------------------------------------------------
# update_library_entry
# ---------------------------------------------------------------------------


def test_update_patches_fields(lib_app):
    r = lib_app.handle_command(
        {"command": "register_library_entry", "avatar_slug": "aeri", "title": "old"}
    )
    eid = r.payload["entry_id"]
    u = lib_app.handle_command(
        {
            "command": "update_library_entry",
            "entry_id": eid,
            "title": "new",
            "completeness": "complete",
        }
    )
    assert u.status == "ok"
    assert u.payload["title"] == "new"
    assert u.payload["completeness"] == "complete"


def test_update_rejects_no_patch(lib_app):
    r = lib_app.handle_command(
        {"command": "register_library_entry", "avatar_slug": "aeri"}
    )
    eid = r.payload["entry_id"]
    u = lib_app.handle_command(
        {"command": "update_library_entry", "entry_id": eid}
    )
    assert u.status == "error"


# ---------------------------------------------------------------------------
# set_library_tags
# ---------------------------------------------------------------------------


def test_set_tags_additive(lib_app):
    r = lib_app.handle_command(
        {
            "command": "register_library_entry",
            "avatar_slug": "aeri",
            "tags": ["initial"],
        }
    )
    eid = r.payload["entry_id"]
    s = lib_app.handle_command(
        {
            "command": "set_library_tags",
            "entry_id": eid,
            "tags": ["mood:intimate", "lighting:lowkey"],
        }
    )
    assert s.status == "ok"
    assert "initial" in s.payload["tags"]
    assert "mood:intimate" in s.payload["tags"]
    assert "lighting:lowkey" in s.payload["tags"]


def test_set_tags_replace_preserves_auto(lib_app):
    r = lib_app.handle_command(
        {
            "command": "register_library_entry",
            "avatar_slug": "aeri",
            "tags": ["manual:keep"],
            "metadata": {"sampler": "euler"},  # produces auto:sampler:euler
        }
    )
    eid = r.payload["entry_id"]
    s = lib_app.handle_command(
        {
            "command": "set_library_tags",
            "entry_id": eid,
            "tags": ["replace:me"],
            "replace": True,
        }
    )
    assert s.status == "ok"
    assert "replace:me" in s.payload["tags"]
    assert "auto:sampler:euler" in s.payload["tags"]
    assert "manual:keep" not in s.payload["tags"]


# ---------------------------------------------------------------------------
# library_search
# ---------------------------------------------------------------------------


def test_search_finds_by_title_trgm(lib_app):
    lib_app.handle_command(
        {
            "command": "register_library_entry",
            "avatar_slug": "aeri",
            "title": "intimate hallway scene",
            "tags": ["mood:intimate"],
        }
    )
    r = lib_app.handle_command(
        {"command": "library_search", "query": "inimate"}
    )
    assert r.status == "ok"
    assert r.payload["count"] >= 1
    titles = {res["title"] for res in r.payload["results"]}
    assert "intimate hallway scene" in titles


def test_search_finds_via_prompt_fts(lib_app):
    lib_app.handle_command(
        {
            "command": "register_library_entry",
            "avatar_slug": "aeri",
            "title": "studio shot",
            "prompts": {"positive": "soft golden lighting", "negative": ""},
        }
    )
    r = lib_app.handle_command(
        {"command": "library_search", "query": "lighting"}
    )
    assert r.status == "ok"
    assert r.payload["count"] >= 1


def test_search_records_state_history(lib_app):
    r = lib_app.handle_command(
        {"command": "library_search", "query": "no-such-thing"}
    )
    assert r.status == "ok"
    state = json.loads(lib_app.state.state_path.read_text(encoding="utf-8"))
    lib = state["library"]
    assert lib["last_search_query"] == "no-such-thing"
    assert lib["last_search_count"] == 0
    assert lib["last_search_at"]


def test_search_rejects_empty_query(lib_app):
    r = lib_app.handle_command({"command": "library_search", "query": "  "})
    assert r.status == "error"


# ---------------------------------------------------------------------------
# delete_library_entry
# ---------------------------------------------------------------------------


def test_delete_removes_db_row_and_filesystem_folder(lib_app):
    r = lib_app.handle_command(
        {
            "command": "register_library_entry",
            "avatar_slug": "aeri",
            "openpose_json": base64.b64encode(b"{}").decode(),
        }
    )
    eid = r.payload["entry_id"]
    lib_root = Path(lib_app.settings.library_root)
    assert (lib_root / eid).exists()

    d = lib_app.handle_command(
        {"command": "delete_library_entry", "entry_id": eid}
    )
    assert d.status == "ok"
    assert d.payload["deleted"] is True
    assert not (lib_root / eid).exists()

    # Subsequent delete returns deleted=False (idempotent).
    d2 = lib_app.handle_command(
        {"command": "delete_library_entry", "entry_id": eid}
    )
    assert d2.status == "ok"
    assert d2.payload["deleted"] is False


# ---------------------------------------------------------------------------
# dump_library_schema
# ---------------------------------------------------------------------------


def test_dump_library_schema_returns_version_and_tables(lib_app):
    r = lib_app.handle_command({"command": "dump_library_schema"})
    assert r.status == "ok"
    # WP-I4-001 bumped schema_version 5 -> 6 via migration 006.
    assert r.payload["schema_version"] >= 6
    tables = set(r.payload["tables"])
    expected = {
        "schema_version",
        "library_entries",
        "tags",
        "entry_tags",
        "prompts",
        "story_beats",
        "notes",
    }
    assert expected.issubset(tables)
    assert "library_search" in r.payload["functions"]
    assert isinstance(r.payload["ddl_hash"], str)
    assert len(r.payload["ddl_hash"]) == 16


# ---------------------------------------------------------------------------
# Library disabled (no DSN)
# ---------------------------------------------------------------------------


def test_library_commands_when_pool_unavailable(tmp_path: Path):
    """An App constructed without library_db_url returns structured errors
    for library commands without crashing the rest of the dispatcher."""
    from openrepose.app import App

    app = App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
    )
    try:
        assert app.library_pool.is_connected is False
        r = app.handle_command(
            {"command": "library_search", "query": "anything"}
        )
        assert r.status == "error"
        assert "library subsystem is disabled" in r.payload["reason"]
    finally:
        app.stop()


# ---------------------------------------------------------------------------
# Multi-operator lock collision
# ---------------------------------------------------------------------------


def test_update_lock_collision_returns_structured_error(lib_app, library_cmd_pg):
    """A second connection holding the row lock makes the update command
    return a structured error rather than block forever."""
    import psycopg

    r = lib_app.handle_command(
        {"command": "register_library_entry", "avatar_slug": "aeri", "title": "t"}
    )
    eid = r.payload["entry_id"]

    dsn = _to_dsn(library_cmd_pg)
    with psycopg.connect(dsn) as a:
        with a.cursor() as cur:
            cur.execute(
                "SELECT id FROM library_entries WHERE id = %s FOR UPDATE",
                (eid,),
            )
        u = lib_app.handle_command(
            {
                "command": "update_library_entry",
                "entry_id": eid,
                "title": "conflict",
            }
        )
        assert u.status == "error"
        assert "locked" in u.payload["reason"]
        assert "retry_after" in u.payload["reason"]
        a.rollback()
