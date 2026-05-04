"""Dispatcher-level tests for the four I4 commands (WP-I4-001).

Spec: `.gov/spec/openrepose_intake_v0_1.md`
      "I4 Scale + DB Hardening Extension".

Verifies wiring through `App.handle_command`:
  - intake_register_outputs_bulk
  - intake_recover_audit
  - intake_recover_retry
  - intake_process_file_ops

Skips cleanly when no system Postgres is available.
"""

from __future__ import annotations

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

    intake_disp_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    intake_disp_pg = _factories.postgresql("intake_disp_proc")
else:  # pragma: no cover
    @pytest.fixture
    def intake_disp_pg():
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
def disp_app(intake_disp_pg, tmp_path: Path):
    """Wired App against the ephemeral DB."""
    from openrepose.app import App
    from openrepose.settings import Settings

    dsn = _to_dsn(intake_disp_pg)
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
# Helpers
# ---------------------------------------------------------------------------


def _create_project_task_run(disp_app) -> dict[str, str]:  # noqa: ANN001
    """Create one project, one task, one batch, one card, one run via
    the dispatcher path. Returns a dict of IDs the tests use."""
    r = disp_app.handle_command(
        {
            "command": "project_create",
            "slug": "exp120-disp",
            "name": "EXP120 disp",
            "owner_slug": "ilja",
        }
    )
    assert r.status == "ok", r.payload
    project_id = r.payload["project"]["id"]

    r = disp_app.handle_command(
        {
            "command": "task_create",
            "project_id": project_id,
            "slug": "T-DISP",
            "expected_count": 100,
            "source": "test",
            "llm_model": "synthetic",
        }
    )
    assert r.status == "ok", r.payload
    task_id = r.payload["task"]["id"]

    # Create a batch + card directly via the pool so we have a parent
    # for library_runs (init_batch_package needs richer data than this
    # quick smoke test wants to provide).
    pool = disp_app.library_pool
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO library_batches (project_id, task_id, slug) "
                "VALUES (%s, %s, 'B-DISP') RETURNING id",
                (project_id, task_id),
            )
            batch_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO library_entries "
                "(avatar_slug, title, batch_id, status, "
                " dedupe_signature, compatibility_signature) "
                "VALUES ('aeri', 'SF-15', %s, 'pending', "
                "        'pussy|standing|frontal|robe-open|bed-edge|hotel|"
                "eye-level|warm', "
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
        "batch_id": str(batch_id),
        "card_id": str(card_id),
        "run_id": str(run_id),
    }


def _payload(n: int, *, prefix: str = "p") -> list[dict]:
    return [
        {
            "file_path": f"intake/T-DISP/raw/{prefix}_{i:04d}.png",
            "content_hash": f"h-{prefix}-{i:04d}",
            "width": 1080,
            "height": 1440,
            "idempotency_key": f"{prefix}-{i:04d}",
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# intake_register_outputs_bulk
# ---------------------------------------------------------------------------


def test_dispatcher_bulk_registers_50_outputs(disp_app):
    ids = _create_project_task_run(disp_app)
    r = disp_app.handle_command(
        {
            "command": "intake_register_outputs_bulk",
            "task_id": ids["task_id"],
            "run_id": ids["run_id"],
            "agent_id": "agent-1",
            "source_model": "sdxl-base-1.0",
            "outputs": _payload(50, prefix="A"),
        }
    )
    assert r.status == "ok", r.payload
    assert len(r.payload["inserted"]) == 50
    assert r.payload["duplicates"] == []
    assert r.payload["rejected"] == []
    assert r.payload["diagnostic"] == []


def test_dispatcher_bulk_idempotent_retry_returns_duplicates(disp_app):
    ids = _create_project_task_run(disp_app)
    payload = _payload(20, prefix="R")

    first = disp_app.handle_command(
        {
            "command": "intake_register_outputs_bulk",
            "task_id": ids["task_id"],
            "run_id": ids["run_id"],
            "agent_id": "agent-1",
            "outputs": payload,
        }
    )
    assert first.status == "ok"
    assert len(first.payload["inserted"]) == 20

    second = disp_app.handle_command(
        {
            "command": "intake_register_outputs_bulk",
            "task_id": ids["task_id"],
            "run_id": ids["run_id"],
            "agent_id": "agent-1",
            "outputs": payload,
        }
    )
    assert second.status == "ok"
    assert second.payload["inserted"] == []
    assert len(second.payload["duplicates"]) == 20


def test_dispatcher_bulk_oversized_returns_error_with_intake_008(disp_app):
    ids = _create_project_task_run(disp_app)
    huge = _payload(201, prefix="X")

    r = disp_app.handle_command(
        {
            "command": "intake_register_outputs_bulk",
            "task_id": ids["task_id"],
            "run_id": ids["run_id"],
            "agent_id": "agent-1",
            "outputs": huge,
        }
    )
    assert r.status == "error"
    assert "INTAKE-008" in r.payload["reason"]


def test_dispatcher_bulk_missing_task_id_rejected(disp_app):
    ids = _create_project_task_run(disp_app)
    r = disp_app.handle_command(
        {
            "command": "intake_register_outputs_bulk",
            "run_id": ids["run_id"],
            "agent_id": "agent-1",
            "outputs": _payload(1, prefix="X"),
        }
    )
    assert r.status == "error"
    assert "task_id" in r.payload["reason"]


# ---------------------------------------------------------------------------
# intake_recover_audit
# ---------------------------------------------------------------------------


def test_dispatcher_recover_audit_returns_empty_after_clean_bulk(disp_app):
    ids = _create_project_task_run(disp_app)
    disp_app.handle_command(
        {
            "command": "intake_register_outputs_bulk",
            "task_id": ids["task_id"],
            "run_id": ids["run_id"],
            "agent_id": "agent-1",
            "outputs": _payload(5, prefix="C"),
        }
    )
    r = disp_app.handle_command(
        {"command": "intake_recover_audit", "task_id": ids["task_id"]}
    )
    assert r.status == "ok"
    payload = r.payload
    assert payload["missing_files"] == []
    assert payload["pending_file_ops"] == []
    assert payload["failed_file_ops"] == []
    assert payload["storage_state_mismatches"] == []


# ---------------------------------------------------------------------------
# intake_process_file_ops
# ---------------------------------------------------------------------------


def test_dispatcher_process_file_ops_no_op_when_outbox_empty(disp_app):
    r = disp_app.handle_command({"command": "intake_process_file_ops"})
    assert r.status == "ok"
    assert r.payload == {"claimed": 0, "done": 0, "failed": 0}


# ---------------------------------------------------------------------------
# intake_recover_retry
# ---------------------------------------------------------------------------


def test_dispatcher_recover_retry_rejects_missing_file_op_id(disp_app):
    r = disp_app.handle_command({"command": "intake_recover_retry"})
    assert r.status == "error"
    assert "file_op_id" in r.payload["reason"]
