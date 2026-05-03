"""End-to-end tests for the intake + project + task command surface
(WP-I3-004).

Spec: `.gov/spec/openrepose_intake_v0_1.md`. Builds an `App` against an
ephemeral PostgreSQL, applies all four migrations (001 + I3 trio), and
drives every dispatcher command through the public `App.handle_command`
path so the dispatcher's typed-error catch + state.write + log path are
all exercised.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

import pytest

PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass

if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    intake_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    intake_pg = _factories.postgresql("intake_pg_proc")
else:  # pragma: no cover

    @pytest.fixture
    def intake_pg():
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


@pytest.fixture
def app(intake_pg, tmp_path: Path):
    """Construct an `App` wired to the ephemeral DB. Migrations run
    automatically on first connection."""
    from openrepose.app import App
    from openrepose.settings import Settings

    dsn = _dsn(intake_pg)
    settings = Settings(
        library_db_url=dsn,
        operator_slug="test-op",
        library_root=str(tmp_path / "library"),
        settings_path=tmp_path / "settings.json",
    )
    settings.save()
    a = App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
    )
    yield a
    a.stop()


def _operator_token(app) -> str:  # noqa: ANN001
    """Compute the v0.1 operator token from the app's settings."""
    from openrepose.library.intake.tokens import expected_operator_token

    return expected_operator_token(app.settings)


def _ok(result) -> dict[str, Any]:  # noqa: ANN001
    """Assert dispatch succeeded; return the payload."""
    d = result.to_dict()
    assert d["status"] == "ok", d
    assert "adult_production_boundary" in d
    return d["payload"]


def _err(result) -> dict[str, Any]:  # noqa: ANN001
    """Assert dispatch failed; return the payload."""
    d = result.to_dict()
    assert d["status"] == "error", d
    assert "adult_production_boundary" in d
    return d["payload"]


# ---------------------------------------------------------------------------
# Project + task happy path
# ---------------------------------------------------------------------------


def test_project_create_and_list(app):
    payload = _ok(app.handle_command(
        {"command": "project_create", "slug": "exposure-120", "name": "Exposure 120"}
    ))
    assert payload["project"]["slug"] == "exposure-120"
    assert payload["project"]["status"] == "active"
    assert payload["project"]["owner_slug"] == "test-op"

    payload = _ok(app.handle_command({"command": "project_list"}))
    assert payload["count"] == 1
    assert payload["projects"][0]["slug"] == "exposure-120"


def test_task_create_makes_intake_dir_tree(app, tmp_path: Path):
    p = _ok(app.handle_command(
        {"command": "project_create", "slug": "exposure-120", "name": "Exposure 120"}
    ))["project"]
    payload = _ok(app.handle_command({
        "command": "task_create",
        "project_id": p["id"],
        "slug": "T-001",
        "expected_count": 80,
    }))
    task = payload["task"]
    assert task["slug"] == "T-001"
    assert task["intake_dir"].endswith("-T-001/")
    base = tmp_path / "outputs" / "intake" / task["intake_dir"]
    for sub in ("raw", "diagnostic", "contact_sheets", "rejected"):
        assert (base / sub).is_dir(), f"missing intake subdir {sub}"


def test_task_create_writes_intake_state(app):
    project = _ok(app.handle_command(
        {"command": "project_create", "slug": "exposure-120", "name": "Exposure 120"}
    ))["project"]
    _ok(app.handle_command({
        "command": "task_create",
        "project_id": project["id"],
        "slug": "T-001",
    }))
    intake_state = app.state.library["intake"]
    assert intake_state["active_task_slug"] == "T-001"
    assert intake_state["received_count"] == 0
    assert intake_state["queue_depth"] == 0


# ---------------------------------------------------------------------------
# intake_register_output (no auto-route rules)
# ---------------------------------------------------------------------------


def _seed_project_task_run(app) -> dict[str, str]:  # noqa: ANN001
    """Common fixture: project + task + a library_runs row + a card row.

    Returns ids needed for downstream tests."""
    project = _ok(app.handle_command(
        {"command": "project_create", "slug": "exposure-120", "name": "Exposure 120"}
    ))["project"]
    task = _ok(app.handle_command({
        "command": "task_create",
        "project_id": project["id"],
        "slug": "T-001",
        "expected_count": 80,
    }))["task"]

    # Seed a card (library_entries row) with batch_id so the run FK resolves.
    pool = app.library_pool
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_batches (project_id, task_id, slug) "
            "VALUES (%s, %s, 'B-001') RETURNING id",
            (project["id"], task["id"]),
        )
        batch_id = str(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO library_entries (avatar_slug, title, batch_id, status, "
            "                             dedupe_signature, compatibility_signature) "
            "VALUES ('aeri', 'SF-15', %s, 'pending', "
            "        'pussy|standing|frontal|robe|bed|hotel|eye|warm', '') "
            "RETURNING id",
            (batch_id,),
        )
        card_id = str(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO library_runs (card_id, task_id) VALUES (%s, %s) RETURNING id",
            (card_id, task["id"]),
        )
        run_id = str(cur.fetchone()[0])
        conn.commit()
    return {
        "project_id": project["id"],
        "task_id": task["id"],
        "batch_id": batch_id,
        "card_id": card_id,
        "run_id": run_id,
    }


def _make_dummy_file(app, intake_dir_rel: str, name: str) -> str:  # noqa: ANN001
    """Write a small file under outputs/intake/<task_slug>/raw/. Returns
    the relative path under outputs_root."""
    raw_dir = Path(app.outputs_root) / "intake" / intake_dir_rel.rstrip("/") / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    f = raw_dir / name
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + (name.encode("utf-8") * 10))
    rel = f.relative_to(Path(app.outputs_root))
    return str(rel).replace("\\", "/")


def test_intake_register_output_no_rules_stays_pending(app):
    ids = _seed_project_task_run(app)
    intake_dir = (
        _ok(app.handle_command({"command": "task_summary", "task_id": ids["task_id"]}))[
            "summary"
        ]
        .get("task_slug")
    )
    # Reach the actual intake_dir from the DB rather than re-deriving.
    with app.library_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT intake_dir FROM library_tasks WHERE id = %s", (ids["task_id"],)
        )
        intake_dir = cur.fetchone()[0]
    file_rel = _make_dummy_file(app, intake_dir, "out-001.png")

    h = hashlib.sha256(file_rel.encode("utf-8")).hexdigest()
    payload = _ok(app.handle_command({
        "command": "intake_register_output",
        "run_id": ids["run_id"],
        "task_id": ids["task_id"],
        "file_path": file_rel,
        "content_hash": h,
        "width": 1080,
        "height": 1440,
    }))
    assert payload["output"]["status"] == "pending"
    assert payload["auto_route"]["routed"] is False

    # state.library.intake reflects 1 received, 1 pending.
    intake_state = app.state.library["intake"]
    assert intake_state["received_count"] == 1
    assert intake_state["pending_count"] == 1


def test_intake_register_output_with_auto_route_rule_routes_to_diagnostic(app):
    ids = _seed_project_task_run(app)
    # Manually insert a project-scope severity=auto-route rule (WP-I3-007 will
    # populate via requirements editor; here we test the scaffolding).
    with app.library_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_rules "
            "(rule_id, scope_type, scope_id, name, short, severity, "
            " machine_check_fn, auto_route_to, kind) "
            "VALUES ('EXP120-RES-001', 'project', %s, '1080x1440 exact', "
            "        '1080x1440 exact', 'auto-route', "
            "        '(SELECT width FROM params) = 1080 AND (SELECT height FROM params) = 1440', "
            "        'intermediate_evidence', 'hard_output')",
            (ids["project_id"],),
        )
        conn.commit()
        cur.execute(
            "SELECT intake_dir FROM library_tasks WHERE id = %s", (ids["task_id"],)
        )
        intake_dir = cur.fetchone()[0]

    file_rel = _make_dummy_file(app, intake_dir, "out-bad-res.png")
    h = hashlib.sha256(file_rel.encode("utf-8")).hexdigest()

    payload = _ok(app.handle_command({
        "command": "intake_register_output",
        "run_id": ids["run_id"],
        "task_id": ids["task_id"],
        "file_path": file_rel,
        "content_hash": h,
        "width": 1024,    # wrong resolution
        "height": 1536,
    }))
    assert payload["output"]["status"] == "diagnostic"
    assert payload["auto_route"]["routed"] is True
    assert payload["auto_route"]["rule_id"] == "EXP120-RES-001"
    assert payload["auto_route"]["bucket"] == "intermediate_evidence"

    # File moved out of raw/ into diagnostic/intermediate_evidence/.
    moved = (
        Path(app.outputs_root)
        / "intake"
        / intake_dir
        / "diagnostic"
        / "intermediate_evidence"
        / "out-bad-res.png"
    )
    assert moved.exists(), f"file not moved: {moved}"
    assert not (Path(app.outputs_root) / file_rel).exists(), "source still present"


# ---------------------------------------------------------------------------
# Two-stage acceptance: LLM may soft_accept; only operator may finalize
# ---------------------------------------------------------------------------


def _register_output(app, ids: dict[str, str], suffix: str = "a") -> str:  # noqa: ANN001
    with app.library_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT intake_dir FROM library_tasks WHERE id = %s", (ids["task_id"],)
        )
        intake_dir = cur.fetchone()[0]
    file_rel = _make_dummy_file(app, intake_dir, f"out-{suffix}.png")
    h = hashlib.sha256(file_rel.encode("utf-8")).hexdigest()
    payload = _ok(app.handle_command({
        "command": "intake_register_output",
        "run_id": ids["run_id"],
        "task_id": ids["task_id"],
        "file_path": file_rel,
        "content_hash": h,
        "width": 1080,
        "height": 1440,
    }))
    return payload["output"]["id"]


def test_intake_soft_accept_llm_issuable(app):
    ids = _seed_project_task_run(app)
    output_id = _register_output(app, ids)

    payload = _ok(app.handle_command({
        "command": "intake_soft_accept",
        "output_id": output_id,
    }))
    assert payload["output"]["status"] == "soft_accepted"
    assert payload["output"]["soft_accepted_at"] is not None


def test_intake_finalize_blocked_without_operator_token(app):
    ids = _seed_project_task_run(app)
    output_id = _register_output(app, ids)
    _ok(app.handle_command({"command": "intake_soft_accept", "output_id": output_id}))

    err_payload = _err(app.handle_command({
        "command": "intake_finalize",
        "output_id": output_id,
    }))
    assert err_payload["rule_id"] == "INTAKE-001"
    citation = err_payload["citation"]
    assert "INTAKE-001" in citation
    assert "two-stage acceptance" in citation
    assert "intake-and-triage" in citation


def test_intake_finalize_blocked_with_bogus_token(app):
    ids = _seed_project_task_run(app)
    output_id = _register_output(app, ids)
    _ok(app.handle_command({"command": "intake_soft_accept", "output_id": output_id}))

    err_payload = _err(app.handle_command({
        "command": "intake_finalize",
        "output_id": output_id,
        "operator_token": "deadbeef" * 8,
    }))
    assert err_payload["rule_id"] == "INTAKE-001"


def test_intake_finalize_succeeds_with_operator_token(app):
    ids = _seed_project_task_run(app)
    output_id = _register_output(app, ids)
    _ok(app.handle_command({"command": "intake_soft_accept", "output_id": output_id}))

    token = _operator_token(app)
    payload = _ok(app.handle_command({
        "command": "intake_finalize",
        "output_id": output_id,
        "operator_token": token,
    }))
    assert payload["output"]["status"] == "promoted"
    assert payload["output"]["finalized_by"] == "test-op"


# ---------------------------------------------------------------------------
# Reject + reroute
# ---------------------------------------------------------------------------


def test_intake_reject_moves_file_to_rejected(app):
    ids = _seed_project_task_run(app)
    output_id = _register_output(app, ids, suffix="r1")

    payload = _ok(app.handle_command({
        "command": "intake_reject",
        "output_id": output_id,
        "primary_rejection_reason": "anatomy_failure",
        "notes": "broken hands",
    }))
    assert payload["output"]["status"] == "rejected"
    assert payload["output"]["primary_rejection_reason"] == "anatomy_failure"

    with app.library_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT intake_dir FROM library_tasks WHERE id = %s", (ids["task_id"],)
        )
        intake_dir = cur.fetchone()[0]
    rejected_dir = Path(app.outputs_root) / "intake" / intake_dir / "rejected"
    assert any(rejected_dir.glob("out-r1.png")), f"file not in rejected/: {rejected_dir}"


def test_intake_reroute_diagnostic_back_to_pending(app):
    ids = _seed_project_task_run(app)
    output_id = _register_output(app, ids, suffix="rr")
    # Manually mark the row as diagnostic to simulate a prior auto-route.
    with app.library_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE library_outputs SET status = 'diagnostic' WHERE id = %s",
            (output_id,),
        )
        conn.commit()

    payload = _ok(app.handle_command({
        "command": "intake_reroute",
        "output_id": output_id,
        "target_status": "pending",
    }))
    assert payload["output"]["status"] == "pending"


# ---------------------------------------------------------------------------
# Wholesale reject
# ---------------------------------------------------------------------------


def test_task_reject_wholesale_rolls_back_outputs_and_deletes_intake_dir(app):
    ids = _seed_project_task_run(app)
    output_ids = [
        _register_output(app, ids, suffix=f"w{i}") for i in range(5)
    ]
    # mix in a soft_accepted one to verify it also flips to rejected.
    _ok(app.handle_command({"command": "intake_soft_accept", "output_id": output_ids[2]}))

    token = _operator_token(app)
    err_no_token = _err(app.handle_command({
        "command": "task_reject_wholesale",
        "task_id": ids["task_id"],
        "reason": "wrong avatar",
    }))
    assert err_no_token["rule_id"] == "INTAKE-001"

    payload = _ok(app.handle_command({
        "command": "task_reject_wholesale",
        "task_id": ids["task_id"],
        "reason": "wrong avatar",
        "operator_token": token,
    }))
    assert payload["transitioned_count"] == 5
    assert payload["status"] == "rejected_wholesale"

    # All outputs are now rejected.
    payload = _ok(app.handle_command({
        "command": "intake_list",
        "task_id": ids["task_id"],
        "status": "rejected",
    }))
    assert payload["count"] == 5

    # intake_dir is gone.
    with app.library_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT intake_dir, status FROM library_tasks WHERE id = %s",
            (ids["task_id"],),
        )
        intake_dir, status = cur.fetchone()
    assert status == "rejected_wholesale"
    assert not (Path(app.outputs_root) / "intake" / intake_dir).exists()


# ---------------------------------------------------------------------------
# Bulk promote
# ---------------------------------------------------------------------------


def test_promote_to_library_bulk_promotes_soft_accepted(app):
    ids = _seed_project_task_run(app)
    soft_ids = []
    for i in range(3):
        output_id = _register_output(app, ids, suffix=f"sa{i}")
        _ok(app.handle_command({"command": "intake_soft_accept", "output_id": output_id}))
        soft_ids.append(output_id)
    # one stays pending and must NOT be promoted.
    pending_id = _register_output(app, ids, suffix="px")

    err_payload = _err(app.handle_command({
        "command": "promote_to_library",
        "task_id": ids["task_id"],
    }))
    assert err_payload["rule_id"] == "INTAKE-001"

    token = _operator_token(app)
    payload = _ok(app.handle_command({
        "command": "promote_to_library",
        "task_id": ids["task_id"],
        "operator_token": token,
    }))
    assert payload["count"] == 3
    assert set(payload["promoted_ids"]) == set(soft_ids)

    # The pending one is unchanged.
    detail = _ok(app.handle_command(
        {"command": "intake_inspect", "output_id": pending_id}
    ))
    assert detail["output"]["status"] == "pending"


# ---------------------------------------------------------------------------
# task_summary + intake_list filter
# ---------------------------------------------------------------------------


def test_task_summary_counters_match_outputs(app):
    ids = _seed_project_task_run(app)
    pending = [_register_output(app, ids, suffix=f"p{i}") for i in range(3)]
    soft_ones = [_register_output(app, ids, suffix=f"s{i}") for i in range(2)]
    for o in soft_ones:
        _ok(app.handle_command({"command": "intake_soft_accept", "output_id": o}))
    rejected = _register_output(app, ids, suffix="rj")
    _ok(app.handle_command({
        "command": "intake_reject",
        "output_id": rejected,
        "primary_rejection_reason": "bad",
    }))

    payload = _ok(app.handle_command(
        {"command": "task_summary", "task_id": ids["task_id"]}
    ))
    s = payload["summary"]
    assert s["received_count"] == 6
    assert s["pending_count"] == 3
    assert s["soft_accepted_count"] == 2
    assert s["rejected_count"] == 1
    assert s["promoted_count"] == 0


def test_intake_list_status_filter(app):
    ids = _seed_project_task_run(app)
    _register_output(app, ids, suffix="p1")
    soft = _register_output(app, ids, suffix="s1")
    _ok(app.handle_command({"command": "intake_soft_accept", "output_id": soft}))

    payload = _ok(app.handle_command({
        "command": "intake_list",
        "task_id": ids["task_id"],
        "status": "soft_accepted",
    }))
    assert payload["count"] == 1
    assert payload["outputs"][0]["status"] == "soft_accepted"


# ---------------------------------------------------------------------------
# Citation-shape regression on every operator-only command
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command,extra",
    [
        ("intake_finalize", {"output_id": "00000000-0000-0000-0000-000000000000"}),
        ("promote_to_library", {"task_id": "00000000-0000-0000-0000-000000000000"}),
        ("task_reject_wholesale", {"task_id": "00000000-0000-0000-0000-000000000000",
                                   "reason": "no"}),
    ],
)
def test_operator_only_commands_cite_intake_001(app, command, extra):
    payload = _err(app.handle_command({"command": command, **extra}))
    assert payload["rule_id"] == "INTAKE-001"
    citation = payload["citation"]
    assert citation.startswith(f"ERR cmd={command}:")
    assert "INTAKE-001" in citation
    assert "See manual: intake-and-triage" in citation
    assert "Fix:" in citation


# ---------------------------------------------------------------------------
# State surface regression
# ---------------------------------------------------------------------------


def test_register_output_updates_state_intake_block(app):
    ids = _seed_project_task_run(app)
    _register_output(app, ids, suffix="st1")
    _register_output(app, ids, suffix="st2")
    intake_state = app.state.library["intake"]
    assert intake_state["received_count"] == 2
    assert intake_state["pending_count"] == 2
    assert intake_state["queue_depth"] == 2
    assert intake_state["active_task_id"] == ids["task_id"]


def test_guidance_block_caps_active_rules(app):
    """active_rules should cap at 20 entries even if commands try to
    push more (defense against bloat per spec)."""
    app.state.set_guidance(
        current_focus="x",
        next_valid_actions=["a"],
        active_rules=[f"FAKE-{i:03d}" for i in range(40)],
    )
    rules = app.state.library["guidance"]["active_rules"]
    assert len(rules) == 20
    # Last 20 retained.
    assert rules[0] == "FAKE-020"
    assert rules[-1] == "FAKE-039"
