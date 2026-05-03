"""End-to-end tests for the WP-I3-007 target tree commands.

Spec: `.gov/spec/openrepose_requirements_v0_1.md` § "Target Tree" + § "Counters".
Builds an `App` against an ephemeral PostgreSQL, applies all migrations,
imports a small target tree, then drives `target_summary` + `target_recount`
through the dispatcher to verify counters roll up at card / group / project
scope.
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

    targets_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    targets_pg = _factories.postgresql("targets_pg_proc")
else:  # pragma: no cover

    @pytest.fixture
    def targets_pg():
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
def app(targets_pg, tmp_path: Path):
    from openrepose.app import App
    from openrepose.settings import Settings

    dsn = _dsn(targets_pg)
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


def _ok(result) -> dict[str, Any]:  # noqa: ANN001
    d = result.to_dict()
    assert d["status"] == "ok", d
    return d["payload"]


def _err(result) -> dict[str, Any]:  # noqa: ANN001
    d = result.to_dict()
    assert d["status"] == "error", d
    return d["payload"]


def _make_project(app, *, slug: str = "exposure-120") -> dict[str, Any]:  # noqa: ANN001
    return _ok(app.handle_command(
        {"command": "project_create", "slug": slug, "name": slug.upper()}
    ))["project"]


# ---------------------------------------------------------------------------
# Target tree basics
# ---------------------------------------------------------------------------


def test_set_target_tree_seeds_groups_and_cards(app):
    project = _make_project(app)
    payload = _ok(app.handle_command({
        "command": "project_set_target_tree",
        "project_id": project["id"],
        "groups": [
            {"slug": "SF", "name": "Standing frontal", "expected_card_count": 3,
             "target_per_card": 8, "ordering": 1},
            {"slug": "SR", "name": "Standing rear", "expected_card_count": 2,
             "target_per_card": 8, "ordering": 2},
        ],
    }))
    assert payload["groups_created"] == 2
    assert payload["cards_created"] == 5  # 3 + 2

    # state.library.targets reflects the tree.
    targets = app.state.library["targets"]
    assert targets["project"]["target_promoted"] == 5 * 8  # 40
    assert len(targets["groups"]) == 2
    assert {g["slug"] for g in targets["groups"]} == {"SF", "SR"}


def test_target_summary_empty_project_is_zeros(app):
    project = _make_project(app)
    payload = _ok(app.handle_command({
        "command": "target_summary",
        "scope_type": "project",
        "scope_id": project["id"],
    }))
    summary = payload["summary"]
    assert summary["target_promoted"] == 0
    assert summary["promoted"] == 0
    assert summary["gap"] == 0
    assert summary["forecast_ok"] is True  # gap=0; in_flight>=0 trivially
    assert summary["count_satisfied"] is True


def test_target_summary_unseeded_project_has_gap(app):
    project = _make_project(app)
    _ok(app.handle_command({
        "command": "project_set_target_tree",
        "project_id": project["id"],
        "groups": [
            {"slug": "SF", "name": "SF", "expected_card_count": 2,
             "target_per_card": 4, "ordering": 1},
        ],
    }))
    payload = _ok(app.handle_command({
        "command": "target_summary",
        "scope_type": "project",
        "scope_id": project["id"],
    }))
    summary = payload["summary"]
    assert summary["target_promoted"] == 8  # 2 cards * 4
    assert summary["promoted"] == 0
    assert summary["gap"] == 8
    assert summary["forecast_ok"] is False  # in_flight 0 < gap 8
    assert summary["count_satisfied"] is False


def test_target_summary_aggregates_promoted_counts(app, tmp_path: Path):
    """Counters roll up across cards within a group."""
    project = _make_project(app)
    _ok(app.handle_command({
        "command": "project_set_target_tree",
        "project_id": project["id"],
        "groups": [
            {"slug": "G", "name": "G", "expected_card_count": 2,
             "target_per_card": 4, "ordering": 1},
        ],
    }))
    # Seed promoted + pending + rejected outputs directly via the pool so
    # this test stays focused on counter correctness (intake registration
    # path is exercised by test_intake_commands.py).
    pool = app.dispatcher.library_pool
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT tc.id, tc.card_slug "
            "FROM library_target_cards tc JOIN library_target_groups g ON g.id = tc.group_id "
            "WHERE g.project_id = %s ORDER BY tc.card_slug",
            (project["id"],),
        )
        target_cards = cur.fetchall()
        assert len(target_cards) == 2
        # Order: project (already created) → task → batch → entry → run → outputs.
        slug = f"T-{uuid4().hex[:6]}"
        cur.execute(
            "INSERT INTO library_tasks (project_id, slug, intake_dir, expected_count, status) "
            "VALUES (%s, %s, %s, 0, 'pending') RETURNING id",
            (project["id"], slug, f"/tmp/{slug}/"),
        )
        task_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO library_batches (project_id, task_id, slug, dedupe_threshold) "
            "VALUES (%s, %s, %s, 6) RETURNING id",
            (project["id"], task_id, f"batch-{uuid4().hex[:8]}"),
        )
        batch_id = cur.fetchone()[0]

        promoted_count_per_card = [3, 2]  # G-01 gets 3 promoted, G-02 gets 2
        for (target_card_id, card_slug), n_promoted in zip(
            target_cards, promoted_count_per_card, strict=False
        ):
            cur.execute(
                "INSERT INTO library_entries (avatar_slug, batch_id) "
                "VALUES (%s, %s) RETURNING id",
                ("avatar", batch_id),
            )
            entry_id = cur.fetchone()[0]
            cur.execute(
                "UPDATE library_target_cards SET card_id = %s WHERE id = %s",
                (entry_id, target_card_id),
            )
            cur.execute(
                "INSERT INTO library_runs (task_id, card_id) "
                "VALUES (%s, %s) RETURNING id",
                (task_id, entry_id),
            )
            run_id = cur.fetchone()[0]
            for _ in range(n_promoted):
                cur.execute(
                    "INSERT INTO library_outputs "
                    "(run_id, task_id, file_path, content_hash, width, height, "
                    " status, finalized_by, promoted_at) "
                    "VALUES (%s, %s, %s, %s, 1080, 1440, 'promoted', 'test', NOW())",
                    (run_id, task_id, f"/dev/null/{uuid4().hex}.png", uuid4().hex),
                )
            # One pending + one rejected per card to exercise non-promoted counters.
            cur.execute(
                "INSERT INTO library_outputs "
                "(run_id, task_id, file_path, content_hash, width, height, status) "
                "VALUES (%s, %s, %s, %s, 1080, 1440, 'pending')",
                (run_id, task_id, f"/dev/null/{uuid4().hex}.png", uuid4().hex),
            )
            cur.execute(
                "INSERT INTO library_outputs "
                "(run_id, task_id, file_path, content_hash, width, height, "
                " status, rejected_at) "
                "VALUES (%s, %s, %s, %s, 1080, 1440, 'rejected', NOW())",
                (run_id, task_id, f"/dev/null/{uuid4().hex}.png", uuid4().hex),
            )
        conn.commit()

    payload = _ok(app.handle_command({
        "command": "target_summary",
        "scope_type": "project",
        "scope_id": project["id"],
    }))
    summary = payload["summary"]
    assert summary["target_promoted"] == 8  # 2 cards * 4
    assert summary["promoted"] == 5  # 3 + 2
    assert summary["pending"] == 2  # 1 + 1
    assert summary["rejected"] == 2  # 1 + 1
    assert summary["gap"] == 3  # 8 - 5

    # Group-scope summary returns the same numbers (only one group exists).
    pool = app.dispatcher.library_pool
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM library_target_groups WHERE project_id = %s",
            (project["id"],),
        )
        gid = cur.fetchone()[0]
    gpayload = _ok(app.handle_command({
        "command": "target_summary",
        "scope_type": "group",
        "scope_id": str(gid),
    }))
    assert gpayload["summary"]["promoted"] == 5
    assert gpayload["summary"]["pending"] == 2

    # Card-scope summary on the first target card.
    pool = app.dispatcher.library_pool
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM library_target_cards "
            "WHERE group_id = %s ORDER BY card_slug LIMIT 1",
            (str(gid),),
        )
        tcid = cur.fetchone()[0]
    cpayload = _ok(app.handle_command({
        "command": "target_summary",
        "scope_type": "card",
        "scope_id": str(tcid),
    }))
    assert cpayload["summary"]["promoted"] == 3
    assert cpayload["summary"]["pending"] == 1


def test_target_recount_idempotent(app):
    """Recounting twice produces identical summaries (live VIEW, no caching)."""
    project = _make_project(app)
    _ok(app.handle_command({
        "command": "project_set_target_tree",
        "project_id": project["id"],
        "groups": [
            {"slug": "SF", "name": "SF", "expected_card_count": 1,
             "target_per_card": 4, "ordering": 1},
        ],
    }))
    a = _ok(app.handle_command({
        "command": "target_recount",
        "scope_type": "project",
        "scope_id": project["id"],
    }))
    b = _ok(app.handle_command({
        "command": "target_recount",
        "scope_type": "project",
        "scope_id": project["id"],
    }))
    assert a["summary"] == b["summary"]


def test_set_target_tree_rejects_zero_card_count(app):
    project = _make_project(app)
    payload = _err(app.handle_command({
        "command": "project_set_target_tree",
        "project_id": project["id"],
        "groups": [
            {"slug": "X", "name": "X", "expected_card_count": 0,
             "target_per_card": 4, "ordering": 1},
        ],
    }))
    assert payload["type"] == "OpenReposeRequirementsError"
    assert payload["rule_id"] == "REQ-001"


def test_set_target_tree_replaces_existing(app):
    project = _make_project(app)
    _ok(app.handle_command({
        "command": "project_set_target_tree",
        "project_id": project["id"],
        "groups": [
            {"slug": "A", "name": "A", "expected_card_count": 2,
             "target_per_card": 4, "ordering": 1},
        ],
    }))
    # Replace with a different shape.
    _ok(app.handle_command({
        "command": "project_set_target_tree",
        "project_id": project["id"],
        "groups": [
            {"slug": "B", "name": "B", "expected_card_count": 3,
             "target_per_card": 5, "ordering": 1},
        ],
    }))
    payload = _ok(app.handle_command({
        "command": "target_summary",
        "scope_type": "project",
        "scope_id": project["id"],
    }))
    assert payload["summary"]["target_promoted"] == 15  # 3 * 5
