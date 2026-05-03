"""End-to-end tests for the WP-I3-007 requirements editor commands.

Spec: `.gov/spec/openrepose_requirements_v0_1.md` § "Requirement Anatomy",
"Inheritance" (REQ-001), "Commands". Drives `project_add_requirement`,
`project_set_requirement`, `project_dump_requirements`,
`project_render_markdown`, `project_import_markdown` through the dispatcher.
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

    reqs_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    reqs_pg = _factories.postgresql("reqs_pg_proc")
else:  # pragma: no cover

    @pytest.fixture
    def reqs_pg():
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
def app(reqs_pg, tmp_path: Path):
    from openrepose.app import App
    from openrepose.settings import Settings

    dsn = _dsn(reqs_pg)
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
# CRUD basics
# ---------------------------------------------------------------------------


def test_add_requirement_writes_project_scoped_rule(app):
    project = _make_project(app)
    payload = _ok(app.handle_command({
        "command": "project_add_requirement",
        "project_id": project["id"],
        "rule_id": "EXP120-RES-001",
        "name": "Resolution",
        "short": "1080x1440 exact",
        "severity": "auto-route",
        "kind": "hard_output",
        "machine_check_fn": "(width = 1080 AND height = 1440)",
        "auto_route_to": "intermediate_evidence",
    }))
    rule = payload["rule"]
    assert rule["rule_id"] == "EXP120-RES-001"
    assert rule["scope_type"] == "project"
    assert rule["severity"] == "auto-route"
    assert rule["kind"] == "hard_output"


def test_add_requirement_rejects_global_family_rule_id(app):
    """Project-scoped rules cannot collide with the global registry."""
    project = _make_project(app)
    payload = _err(app.handle_command({
        "command": "project_add_requirement",
        "project_id": project["id"],
        "rule_id": "RUL-999",
        "name": "Bad",
        "short": "should be rejected",
        "severity": "warn",
        "kind": "custom",
    }))
    assert payload["type"] == "OpenReposeRequirementsError"
    assert payload["rule_id"] == "REQ-001"
    assert "global" in payload["reason"].lower() or "reserved" in payload["reason"].lower()


def test_add_requirement_rejects_invalid_kind(app):
    project = _make_project(app)
    payload = _err(app.handle_command({
        "command": "project_add_requirement",
        "project_id": project["id"],
        "rule_id": "EXP120-X-001",
        "name": "X",
        "short": "x",
        "severity": "warn",
        "kind": "nonexistent_kind",
    }))
    assert payload["type"] == "OpenReposeRequirementsError"
    assert "kind must be" in payload["reason"]


def test_add_requirement_rejects_invalid_severity(app):
    project = _make_project(app)
    payload = _err(app.handle_command({
        "command": "project_add_requirement",
        "project_id": project["id"],
        "rule_id": "EXP120-X-001",
        "name": "X",
        "short": "x",
        "severity": "maybe",
        "kind": "body",
    }))
    assert payload["type"] == "OpenReposeRequirementsError"


def test_dump_requirements_returns_project_scope(app):
    project = _make_project(app)
    _ok(app.handle_command({
        "command": "project_add_requirement",
        "project_id": project["id"],
        "rule_id": "EXP120-BODY-001",
        "name": "Body", "short": "body", "severity": "warn", "kind": "body",
    }))
    _ok(app.handle_command({
        "command": "project_add_requirement",
        "project_id": project["id"],
        "rule_id": "EXP120-POSE-001",
        "name": "Pose", "short": "pose", "severity": "warn", "kind": "pose",
    }))
    payload = _ok(app.handle_command({
        "command": "project_dump_requirements",
        "project_id": project["id"],
        "scope_type": "project",
        "scope_id": project["id"],
    }))
    assert payload["count"] == 2
    rule_ids = {r["rule_id"] for r in payload["rules"]}
    assert rule_ids == {"EXP120-BODY-001", "EXP120-POSE-001"}


# ---------------------------------------------------------------------------
# Inheritance: lower scope wins (REQ-001)
# ---------------------------------------------------------------------------


def test_card_scope_overrides_project_scope(app):
    project = _make_project(app)
    # Project-scope rule.
    _ok(app.handle_command({
        "command": "project_add_requirement",
        "project_id": project["id"],
        "rule_id": "EXP120-CROP-001",
        "name": "Crop", "short": "no joint crops",
        "severity": "warn", "kind": "crop",
    }))

    # Create a target tree so we have a target_card to attach the override to.
    _ok(app.handle_command({
        "command": "project_set_target_tree",
        "project_id": project["id"],
        "groups": [
            {"slug": "SF", "name": "SF", "expected_card_count": 1,
             "target_per_card": 4, "ordering": 1},
        ],
    }))
    pool = app.dispatcher.library_pool
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM library_target_cards "
            "WHERE group_id = (SELECT id FROM library_target_groups WHERE project_id = %s) "
            "LIMIT 1",
            (project["id"],),
        )
        target_card_id = cur.fetchone()[0]

    # Card-scope override of the same rule_id.
    _ok(app.handle_command({
        "command": "project_set_requirement",
        "project_id": project["id"],
        "rule_id": "EXP120-CROP-001",
        "scope_type": "card",
        "scope_id": str(target_card_id),
        "name": "Crop (override)",
        "short": "lower-leg crop allowed when clean",
        "severity": "warn",
        "kind": "crop",
    }))

    payload = _ok(app.handle_command({
        "command": "project_dump_requirements",
        "project_id": project["id"],
        "scope_type": "card",
        "scope_id": str(target_card_id),
        "rule_id": "EXP120-CROP-001",
    }))
    assert payload["count"] == 2
    # First entry is most-specific scope (card).
    assert payload["rules"][0]["scope_type"] == "card"
    assert payload["rules"][0]["short"] == "lower-leg crop allowed when clean"
    # Second entry is the inherited project-scope rule.
    assert payload["rules"][1]["scope_type"] == "project"
    assert payload["rules"][1]["short"] == "no joint crops"


# ---------------------------------------------------------------------------
# Markdown round-trip via dispatcher
# ---------------------------------------------------------------------------


_EXP120_MD = """\
# Project: exposure-120

- name: Exposure 120
- status: active

## Sets

| slug | name | expected_card_count | target_per_card | ordering |
|------|------|---------------------|-----------------|----------|
| SF | Standing frontal | 2 | 4 | 1 |

## Requirements

### EXP120-CLOTH-001

- kind: clothing_story
- severity: block
- short: Reveal must be clothing-mediated; full nude rejects.
- accept_terms: lifted, pulled_aside, opened
"""


def test_import_then_render_markdown_byte_stable_via_dispatcher(app):
    project = _make_project(app, slug="exposure-120")
    _ok(app.handle_command({
        "command": "project_import_markdown",
        "project_id": project["id"],
        "markdown_text": _EXP120_MD,
    }))
    rendered = _ok(app.handle_command({
        "command": "project_render_markdown",
        "project_id": project["id"],
    }))["markdown"]
    assert rendered == _EXP120_MD


def test_import_markdown_replaces_existing_project_scope_rules(app):
    project = _make_project(app, slug="exposure-120")
    # Pre-existing project-scope rule that's NOT in the markdown.
    _ok(app.handle_command({
        "command": "project_add_requirement",
        "project_id": project["id"],
        "rule_id": "EXP120-OBSOLETE-001",
        "name": "Obsolete", "short": "should be removed by import",
        "severity": "info", "kind": "custom",
    }))
    _ok(app.handle_command({
        "command": "project_import_markdown",
        "project_id": project["id"],
        "markdown_text": _EXP120_MD,
    }))
    payload = _ok(app.handle_command({
        "command": "project_dump_requirements",
        "project_id": project["id"],
        "scope_type": "project",
        "scope_id": project["id"],
    }))
    rule_ids = {r["rule_id"] for r in payload["rules"]}
    assert "EXP120-OBSOLETE-001" not in rule_ids
    assert "EXP120-CLOTH-001" in rule_ids


def test_import_markdown_rejects_malformed(app):
    project = _make_project(app)
    payload = _err(app.handle_command({
        "command": "project_import_markdown",
        "project_id": project["id"],
        "markdown_text": "not a project at all",
    }))
    assert payload["type"] == "OpenReposeRequirementsError"
    assert "parse failed" in payload["reason"]


def test_render_markdown_on_empty_project_renders_skeleton(app):
    project = _make_project(app, slug="empty-proj")
    rendered = _ok(app.handle_command({
        "command": "project_render_markdown",
        "project_id": project["id"],
    }))["markdown"]
    expected = """\
# Project: empty-proj
"""
    assert rendered.startswith(expected)
    assert "## Sets" in rendered
    assert "## Requirements" in rendered
