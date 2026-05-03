"""End-to-end EXP120 verification (WP-I3-010 — closes I3 v0.1).

Walks the full I3 v0.1 surface against an ephemeral PostgreSQL:

    project_create
    -> project_import_markdown(EXP120 minimal)
    -> task_create
    -> init_batch_package
    -> library_create_card x N
    -> intake_begin_run
    -> 50 intake_register_output (mixed sizes)
    -> auto-prefilter routes wrong-resolution
    -> intake_soft_accept
    -> intake_finalize (operator-token gated)
    -> target_summary at every scope
    -> accepted_set_audit (shape assertion)
    -> task_reject_wholesale on a separate task -> rollback isolation

Spec: openrepose_intake_v0_1.md, openrepose_requirements_v0_1.md,
openrepose_amood_v0_1.md, openrepose_rules_v0_1.md.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

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

    e2e_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    e2e_pg = _factories.postgresql("e2e_pg_proc")
else:  # pragma: no cover

    @pytest.fixture
    def e2e_pg():
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
def app(e2e_pg, tmp_path: Path):
    from openrepose.app import App
    from openrepose.settings import Settings

    dsn = _dsn(e2e_pg)
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
    from openrepose.library.intake.tokens import expected_operator_token

    return expected_operator_token(app.settings)


def _ok(result) -> dict[str, Any]:  # noqa: ANN001
    d = result.to_dict()
    assert d["status"] == "ok", d
    return d["payload"]


def _err(result) -> dict[str, Any]:  # noqa: ANN001
    d = result.to_dict()
    assert d["status"] == "error", d
    return d["payload"]


# ---------------------------------------------------------------------------
# Minimal EXP120 markdown — small enough to keep the test fast, complete
# enough to exercise auto-route + counters.
# ---------------------------------------------------------------------------

EXP120_MD = """\
# Project: exposure-120

- name: Exposure 120
- status: active

## Sets

| slug | name | expected_card_count | target_per_card | ordering |
|------|------|---------------------|-----------------|----------|
| SF | Standing frontal exposure | 4 | 8 | 1 |

## Requirements

### EXP120-RES-001

- kind: hard_output
- severity: auto-route
- short: 1080x1440 exact
- machine_check_fn: (width = 1080 AND height = 1440)
- auto_route_to: intermediate_evidence
"""


# ---------------------------------------------------------------------------
# Full e2e test
# ---------------------------------------------------------------------------


def test_exp120_full_flow(app, tmp_path: Path) -> None:
    op_token = _operator_token(app)

    # 1. Project + EXP120 markdown.
    project = _ok(app.handle_command(
        {"command": "project_create", "slug": "exposure-120", "name": "Exposure 120"}
    ))["project"]
    payload = _ok(app.handle_command({
        "command": "project_import_markdown",
        "project_id": project["id"],
        "markdown_text": EXP120_MD,
    }))
    assert payload["groups_imported"] == 1
    assert payload["requirements_imported"] == 1

    # 2. Task + intake dir tree.
    task_payload = _ok(app.handle_command({
        "command": "task_create",
        "project_id": project["id"],
        "slug": "T-EXP120-001",
        "expected_count": 50,
    }))
    task = task_payload["task"]
    task_id = task["id"]

    # 3. AMood batch + 4 cards (one per target card slug).
    batch = _ok(app.handle_command({
        "command": "init_batch_package",
        "project_slug": "exposure-120",
        "batch_slug": "exp120-b1",
        "task_id": task_id,
        "tier": "production",
        "primary_explicit_family": "exposure",
    }))["batch"]
    batch_id = batch["id"]

    card_slugs = ["SF-01", "SF-02", "SF-03", "SF-04"]
    card_ids: dict[str, str] = {}
    for slug in card_slugs:
        card_payload = _ok(app.handle_command({
            "command": "library_create_card",
            "batch_id": batch_id,
            "avatar_slug": "test-avatar",
            "slug": slug,
            "explicit_family": "exposure",
            "pose_family": "standing",
            "orientation": "frontal",
            "wardrobe_state": "lifted",
            "support_object": "none",
            "setting_family": "studio",
            "camera_family": "eye_level",
            "palette_family": "neutral",
        }))
        card_ids[slug] = card_payload["card_id"]

    # 4. begin_run on SF-01 — gives us a run_id for the registration loop.
    run_payload = _ok(app.handle_command({
        "command": "intake_begin_run",
        "task_id": task_id,
        "card_slug": "SF-01",
    }))
    run_id = run_payload["run"]["id"]

    # 5. 50 intake_register_output: 30 at 1080x1440 (pass), 20 at 1024x1024
    #    (auto-route to intermediate_evidence).
    pass_results: list[dict[str, Any]] = []
    routed_results: list[dict[str, Any]] = []
    for i in range(50):
        is_passing = i < 30
        width, height = (1080, 1440) if is_passing else (1024, 1024)
        file_path = f"intake/{task['intake_dir'].rstrip('/')}/raw/output_{i:03d}.png"
        content_hash = uuid4().hex
        payload = _ok(app.handle_command({
            "command": "intake_register_output",
            "run_id": run_id,
            "task_id": task_id,
            "file_path": file_path,
            "content_hash": content_hash,
            "width": width,
            "height": height,
        }))
        (pass_results if is_passing else routed_results).append(payload)

    # 6. Verify auto-route correctness.
    assert len(pass_results) == 30
    assert len(routed_results) == 20
    for p in pass_results:
        assert p["auto_route"]["routed"] is False, p["auto_route"]
        assert p["output"]["status"] == "pending"
    for r in routed_results:
        assert r["auto_route"]["routed"] is True, r["auto_route"]
        assert r["auto_route"]["rule_id"] == "EXP120-RES-001"
        assert r["auto_route"]["bucket"] == "intermediate_evidence"
        assert r["output"]["status"] == "diagnostic"

    # 7. intake_list confirms the same counts via the read path.
    listing = _ok(app.handle_command({
        "command": "intake_list", "task_id": task_id, "limit": 200,
    }))
    statuses = [o["status"] for o in listing["outputs"]]
    assert statuses.count("pending") == 30
    assert statuses.count("diagnostic") == 20

    # 8. Soft-accept 4 of the 30 pending outputs.
    pending_ids = [r["output"]["id"] for r in pass_results[:4]]
    for oid in pending_ids:
        _ok(app.handle_command({
            "command": "intake_soft_accept", "output_id": oid,
        }))

    # 9. Operator finalize on the same 4 — promote to status=promoted.
    for oid in pending_ids:
        finalized = _ok(app.handle_command({
            "command": "intake_finalize",
            "output_id": oid,
            "operator_token": op_token,
        }))
        assert finalized["output"]["status"] == "promoted"
        assert finalized["output"]["finalized_by"] == "test-op"

    # 10. target_summary at project / group / card scope.
    proj_summary = _ok(app.handle_command({
        "command": "target_summary",
        "scope_type": "project",
        "scope_id": project["id"],
    }))["summary"]
    # 4 target cards × 8 promoted target = 32; we promoted 4.
    assert proj_summary["target_promoted"] == 32
    assert proj_summary["promoted"] == 4
    assert proj_summary["gap"] == 28
    # Auto-routed 20 do NOT count toward `promoted` (they're status=diagnostic).
    assert proj_summary["diagnostic"] == 20
    # Pending outputs not yet finalized count as in_flight.
    assert proj_summary["in_flight"] >= 26  # 30 - 4 = 26 still pending

    # 11. accepted_set_audit on the batch — shape assertion only.
    audit = _ok(app.handle_command({
        "command": "accepted_set_audit",
        "batch_id": batch_id,
    }))
    assert "axes" in audit
    assert isinstance(audit["axes"], list)
    assert "batch_id" in audit


def test_intake_finalize_without_token_blocks(app) -> None:
    """Negative: intake_finalize without operator_token returns INTAKE-001 citation."""
    project = _ok(app.handle_command(
        {"command": "project_create", "slug": "p", "name": "P"}
    ))["project"]
    task = _ok(app.handle_command({
        "command": "task_create",
        "project_id": project["id"],
        "slug": "T-NEG",
        "expected_count": 1,
    }))["task"]
    batch_id = _ok(app.handle_command({
        "command": "init_batch_package",
        "project_slug": "p",
        "batch_slug": "b1",
        "task_id": task["id"],
    }))["batch"]["id"]
    _ok(app.handle_command({
        "command": "library_create_card",
        "batch_id": batch_id,
        "avatar_slug": "a",
        "slug": "C-01",
        "explicit_family": "x",
        "pose_family": "x",
        "orientation": "x",
        "wardrobe_state": "x",
        "support_object": "x",
        "setting_family": "x",
        "camera_family": "x",
        "palette_family": "x",
    }))
    run_id = _ok(app.handle_command({
        "command": "intake_begin_run",
        "task_id": task["id"],
        "card_slug": "C-01",
    }))["run"]["id"]
    output_id = _ok(app.handle_command({
        "command": "intake_register_output",
        "run_id": run_id,
        "task_id": task["id"],
        "file_path": "intake/x/raw/x.png",
        "content_hash": uuid4().hex,
        "width": 1080,
        "height": 1440,
    }))["output"]["id"]
    _ok(app.handle_command({
        "command": "intake_soft_accept", "output_id": output_id,
    }))

    # Finalize WITHOUT operator_token is blocked by INTAKE-001.
    err = _err(app.handle_command({
        "command": "intake_finalize",
        "output_id": output_id,
    }))
    assert err.get("rule_id") == "INTAKE-001"
    assert "INTAKE-001" in (err.get("citation") or "")


def test_wholesale_reject_isolates_one_task(app, tmp_path: Path) -> None:
    """task_reject_wholesale on task A removes its rows; task B untouched."""
    op_token = _operator_token(app)

    project = _ok(app.handle_command(
        {"command": "project_create", "slug": "iso", "name": "Isolation"}
    ))["project"]

    def _build_task(slug: str) -> tuple[str, str, str]:
        """Create task + batch + 1 card; return (task_id, batch_id, run_id)."""
        task = _ok(app.handle_command({
            "command": "task_create",
            "project_id": project["id"],
            "slug": slug,
            "expected_count": 5,
        }))["task"]
        batch_id = _ok(app.handle_command({
            "command": "init_batch_package",
            "project_slug": "iso",
            "batch_slug": f"{slug}-batch",
            "task_id": task["id"],
        }))["batch"]["id"]
        _ok(app.handle_command({
            "command": "library_create_card",
            "batch_id": batch_id,
            "avatar_slug": "a",
            "slug": f"{slug}-CARD",
            "explicit_family": "exposure",
            "pose_family": "x",
            "orientation": "x",
            "wardrobe_state": "x",
            "support_object": "x",
            "setting_family": "x",
            "camera_family": "x",
            "palette_family": "x",
        }))
        run_id = _ok(app.handle_command({
            "command": "intake_begin_run",
            "task_id": task["id"],
            "card_slug": f"{slug}-CARD",
        }))["run"]["id"]
        return task["id"], batch_id, run_id

    task_a, _ba, run_a = _build_task("T-A")
    task_b, _bb, run_b = _build_task("T-B")

    # Register 3 outputs in each task.
    output_ids_a: list[str] = []
    output_ids_b: list[str] = []
    for i in range(3):
        oa = _ok(app.handle_command({
            "command": "intake_register_output",
            "run_id": run_a,
            "task_id": task_a,
            "file_path": f"intake/A/raw/{i}.png",
            "content_hash": uuid4().hex,
            "width": 1080, "height": 1440,
        }))["output"]
        output_ids_a.append(oa["id"])
        ob = _ok(app.handle_command({
            "command": "intake_register_output",
            "run_id": run_b,
            "task_id": task_b,
            "file_path": f"intake/B/raw/{i}.png",
            "content_hash": uuid4().hex,
            "width": 1080, "height": 1440,
        }))["output"]
        output_ids_b.append(ob["id"])

    # Wholesale reject task A.
    reject_payload = _ok(app.handle_command({
        "command": "task_reject_wholesale",
        "task_id": task_a,
        "reason": "test rejecting A",
        "operator_token": op_token,
    }))
    # Spec: per-task isolation = directory delete + DB row delete.
    assert reject_payload.get("task_id") == task_a or "task" in reject_payload

    # Documented contract (`library/intake/tasks.py wholesale_reject_task`):
    # task → status=rejected_wholesale; non-terminal outputs → status=rejected
    # (soft-delete, not row removal); intake directory removed. Per-task
    # isolation = task A's outputs all rejected, task B's outputs untouched.
    pool = app.dispatcher.library_pool
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT status, count(*) FROM library_outputs "
            "WHERE task_id = %s GROUP BY status", (task_a,),
        )
        a_status_counts = dict(cur.fetchall())
        cur.execute(
            "SELECT status, count(*) FROM library_outputs "
            "WHERE task_id = %s GROUP BY status", (task_b,),
        )
        b_status_counts = dict(cur.fetchall())
        cur.execute(
            "SELECT status FROM library_tasks WHERE id = %s", (task_a,),
        )
        a_task_status = cur.fetchone()[0]
        cur.execute(
            "SELECT status FROM library_tasks WHERE id = %s", (task_b,),
        )
        b_task_status = cur.fetchone()[0]

    # Task A: all 3 outputs flipped to 'rejected'; no outputs in any other status.
    assert a_status_counts == {"rejected": 3}, (
        f"task A outputs should all be rejected; got {a_status_counts}"
    )
    # Task B: original 3 pending outputs untouched.
    assert b_status_counts == {"pending": 3}, (
        f"task B outputs collateral-affected; got {b_status_counts}"
    )
    assert a_task_status == "rejected_wholesale"
    assert b_task_status in ("pending", "active", "triaging")  # untouched

    # Subsequent register against the rejected task is refused.
    err = _err(app.handle_command({
        "command": "intake_register_output",
        "run_id": run_a,
        "task_id": task_a,
        "file_path": "intake/A/raw/post.png",
        "content_hash": uuid4().hex,
        "width": 1080, "height": 1440,
    }))
    assert "terminal" in (err.get("reason") or "").lower()
