"""End-to-end tests for the AMood command surface (WP-I3-006).

Spec: `.gov/spec/openrepose_amood_v0_1.md`. Drives every dispatcher
command through `App.handle_command` so the typed-error catch +
state.write + log path are exercised. Reuses the App + ephemeral PG
fixture pattern from `test_intake_commands.py`.
"""

from __future__ import annotations

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

    amood_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    amood_pg = _factories.postgresql("amood_pg_proc")
else:  # pragma: no cover

    @pytest.fixture
    def amood_pg():
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
def app(amood_pg, tmp_path: Path):
    from openrepose.app import App
    from openrepose.settings import Settings

    dsn = _dsn(amood_pg)
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
    assert "adult_production_boundary" in d
    return d["payload"]


def _err(result) -> dict[str, Any]:  # noqa: ANN001
    d = result.to_dict()
    assert d["status"] == "error", d
    assert "adult_production_boundary" in d
    return d["payload"]


def _seed_project_task(app) -> dict[str, str]:  # noqa: ANN001
    project = _ok(app.handle_command(
        {"command": "project_create", "slug": "exposure-120", "name": "Exposure 120"}
    ))["project"]
    task = _ok(app.handle_command({
        "command": "task_create",
        "project_id": project["id"],
        "slug": "T-001",
        "expected_count": 80,
    }))["task"]
    return {"project_id": project["id"], "task_id": task["id"]}


# ---------------------------------------------------------------------------
# init_batch_package
# ---------------------------------------------------------------------------


def test_init_batch_package_creates_row_and_layout(app, tmp_path: Path):
    ids = _seed_project_task(app)
    payload = _ok(app.handle_command({
        "command": "init_batch_package",
        "project_slug": "exposure-120",
        "batch_slug": "hotel-robes",
        "task_id": ids["task_id"],
        "tier": "production",
        "primary_explicit_family": "vulva-pussy-exposure",
    }))
    assert payload["created"] is True
    batch = payload["batch"]
    assert batch["slug"] == "hotel-robes"
    assert batch["tier"] == "production"
    assert batch["primary_explicit_family"] == "vulva-pussy-exposure"

    package_dir = Path(payload["package_path"])
    assert package_dir.is_dir()
    for sub in (
        "cards",
        "moodboards",
        "prompt_blocks",
        "pose_guides/openpose/png",
        "pose_guides/dwpose/json",
        "manifests",
        "matrices",
        "ledgers",
        "accepted",
        "soft_accepted",
        "stories",
    ):
        assert (package_dir / sub).is_dir(), f"missing {sub}"
    assert (package_dir / "INDEX.md").is_file()
    assert (package_dir / "README.md").is_file()

    # state.library.amood reflects the active batch.
    amood_state = app.state.library["amood"]
    assert amood_state["active_batch_slug"] == "hotel-robes"
    assert amood_state["tier"] == "production"


def test_init_batch_package_idempotent_rerun(app):
    ids = _seed_project_task(app)
    base = {
        "command": "init_batch_package",
        "project_slug": "exposure-120",
        "batch_slug": "hotel-robes",
        "task_id": ids["task_id"],
    }
    first = _ok(app.handle_command(dict(base)))
    second = _ok(app.handle_command(dict(base)))
    assert first["created"] is True
    assert second["created"] is False
    assert second["batch"]["id"] == first["batch"]["id"]
    assert second["layout_diffs"] == []


def test_init_batch_package_unknown_project_errors(app):
    ids = _seed_project_task(app)
    payload = _err(app.handle_command({
        "command": "init_batch_package",
        "project_slug": "no-such-project",
        "batch_slug": "x",
        "task_id": ids["task_id"],
    }))
    assert "no-such-project" in (payload.get("reason") or "")


# ---------------------------------------------------------------------------
# library_create_card + AMOOD-001 surface
# ---------------------------------------------------------------------------


def _create_batch(app):  # noqa: ANN001
    ids = _seed_project_task(app)
    batch = _ok(app.handle_command({
        "command": "init_batch_package",
        "project_slug": "exposure-120",
        "batch_slug": "hotel-robes",
        "task_id": ids["task_id"],
    }))["batch"]
    return ids | {"batch_id": batch["id"]}


def test_library_create_card_inserts_with_signatures(app):
    ids = _create_batch(app)
    payload = _ok(app.handle_command({
        "command": "library_create_card",
        "batch_id": ids["batch_id"],
        "avatar_slug": "aeri",
        "slug": "hotel-robe-bed-edge",
        "explicit_family": "vulva/pussy exposure",
        "pose_family": "bed-edge lean",
        "orientation": "three-quarter front",
        "wardrobe_state": "robe open",
        "support_object": "bed edge",
        "setting_family": "luxury hotel",
        "camera_family": "eye-level full-body",
        "palette_family": "warm hotel amber",
    }))
    assert payload["card_id"]
    assert payload["dedupe_signature"].count("|") == 7
    assert payload["dedupe_match"]["candidates"] == []
    assert payload["dedupe_match"]["has_overlap"] is False


def test_library_create_card_emits_amood_001_on_overlap(app):
    """A second card with all 8 axes matching a promoted card emits
    AMOOD-001 with the matching slug + overlap_count."""
    ids = _create_batch(app)
    common = {
        "command": "library_create_card",
        "batch_id": ids["batch_id"],
        "avatar_slug": "aeri",
        "explicit_family": "vulva/pussy exposure",
        "pose_family": "bed-edge lean",
        "orientation": "three-quarter front",
        "wardrobe_state": "robe open",
        "support_object": "bed edge",
        "setting_family": "luxury hotel",
        "camera_family": "eye-level full-body",
        "palette_family": "warm hotel amber",
    }
    first = _ok(app.handle_command({**common, "slug": "card-a"}))

    # Promote the first card directly via SQL (LLMs go through the
    # finalize path; this test simulates the post-promotion state).
    pool = app.library_pool
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE library_entries SET status = 'promoted' WHERE id = %s",
            (first["card_id"],),
        )
        conn.commit()

    second = _ok(app.handle_command({**common, "slug": "card-b"}))
    assert second["dedupe_match"]["has_overlap"] is True
    top = second["dedupe_match"]["candidates"][0]
    assert top["overlap_count"] == 8
    assert "amood_001_citation" in second
    assert "AMOOD-001" in second["amood_001_citation"]
    # state.library.amood records the warning.
    warnings = app.state.library["amood"]["dedupe_recent_warnings"]
    assert any(w["card_id"] == second["card_id"] for w in warnings)


# ---------------------------------------------------------------------------
# library_create_variants
# ---------------------------------------------------------------------------


def test_library_create_variants_spawns_children(app):
    ids = _create_batch(app)
    parent = _ok(app.handle_command({
        "command": "library_create_card",
        "batch_id": ids["batch_id"],
        "avatar_slug": "aeri",
        "slug": "hotel-robe-bed-edge",
        "explicit_family": "vulva/pussy exposure",
        "pose_family": "bed-edge lean",
    }))
    payload = _ok(app.handle_command({
        "command": "library_create_variants",
        "parent_card_id": parent["card_id"],
        "variants": ["intimate", "explicit_plus"],
    }))
    assert payload["count"] == 2
    labels = {c["variant_label"] for c in payload["children"]}
    assert labels == {"intimate", "explicit_plus"}
    for child in payload["children"]:
        assert child["parent_card_id"] == parent["card_id"]


def test_library_create_variants_unknown_label_errors(app):
    ids = _create_batch(app)
    parent = _ok(app.handle_command({
        "command": "library_create_card",
        "batch_id": ids["batch_id"],
        "avatar_slug": "aeri",
        "slug": "x",
        "explicit_family": "vulva/pussy exposure",
    }))
    payload = _err(app.handle_command({
        "command": "library_create_variants",
        "parent_card_id": parent["card_id"],
        "variants": ["bogus_label"],
    }))
    assert "bogus_label" in (payload.get("reason") or "")


# ---------------------------------------------------------------------------
# compatibility_check
# ---------------------------------------------------------------------------


def test_compatibility_check_passes_clean_inputs(app):
    payload = _ok(app.handle_command({
        "command": "compatibility_check",
        "sexual_trigger": "visible vulva exposure",
        "explicit_family": "vulva/pussy exposure",
        "pose_family": "bed-edge lean",
        "orientation": "three-quarter front",
        "camera_family": "eye-level full-body",
        "wardrobe_state": "robe open",
        "support_object": "bed edge",
        "palette_family": "warm hotel amber",
        "lighting_family": "warm lamp accent",
        "fantasy_mode": "casual intimate",
    }))
    assert payload["pass"] is True
    assert payload["hard_rejects"] == []


def test_compatibility_check_rejects_juvenile_coded(app):
    payload = _ok(app.handle_command({
        "command": "compatibility_check",
        "primary_rejection_reason": "juvenile_coded",
    }))
    assert payload["pass"] is False
    assert any(r["rule_id"] == "SAFE-001" for r in payload["hard_rejects"])
    assert "SAFE-001" in payload["primary_citation"]


def test_compatibility_check_rejects_camera_cant_see_target(app):
    payload = _ok(app.handle_command({
        "command": "compatibility_check",
        "explicit_family": "vulva/pussy exposure",
        "camera_family": "behind",
    }))
    assert payload["pass"] is False
    cats = {r["category"] for r in payload["hard_rejects"]}
    assert "camera-cant-see-target" in cats


# ---------------------------------------------------------------------------
# accepted_set_audit
# ---------------------------------------------------------------------------


def test_accepted_set_audit_writes_thirteen_axis_rows(app):
    """One promoted card touches 8 axes; the audit emits exactly 13
    diversity-audit rows (one per audited axis), each with a priority
    flag derived from realized_coverage."""
    ids = _create_batch(app)
    card = _ok(app.handle_command({
        "command": "library_create_card",
        "batch_id": ids["batch_id"],
        "avatar_slug": "aeri",
        "slug": "x",
        "explicit_family": "vulva/pussy exposure",
        "pose_family": "bed-edge lean",
        "orientation": "three-quarter front",
        "wardrobe_state": "robe open",
        "support_object": "bed edge",
        "setting_family": "luxury hotel",
        "camera_family": "eye-level full-body",
        "palette_family": "warm hotel amber",
    }))
    pool = app.library_pool
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE library_entries SET status = 'promoted' WHERE id = %s",
            (card["card_id"],),
        )
        conn.commit()

    payload = _ok(app.handle_command({
        "command": "accepted_set_audit",
        "batch_id": ids["batch_id"],
    }))
    assert len(payload["axes"]) == 13
    flags = {a["priority_flag"] for a in payload["axes"]}
    # Single promoted card -> every axis it touches has 1/1 = 100%
    # coverage = ok; axes it doesn't touch have 0 distinct = priority.
    assert "ok" in flags
    assert "priority" in flags

    # state.library.amood.last_audit reflects the result.
    last = app.state.library["amood"]["last_audit"]
    assert last is not None
    assert last["batch_id"] == ids["batch_id"]


# ---------------------------------------------------------------------------
# adult_production_boundary envelope on every response
# ---------------------------------------------------------------------------


def test_every_amood_command_carries_boundary_envelope(app):
    ids = _create_batch(app)
    cmds = [
        {"command": "init_batch_package",
         "project_slug": "exposure-120", "batch_slug": "x",
         "task_id": ids["task_id"]},
        {"command": "compatibility_check"},
        {"command": "amood_export_tsv",
         "schema": "batch_matrix", "batch_id": ids["batch_id"]},
    ]
    for c in cmds:
        d = app.handle_command(c).to_dict()
        assert "adult_production_boundary" in d
        assert d["adult_production_boundary"]["acknowledgement_required"] is True
