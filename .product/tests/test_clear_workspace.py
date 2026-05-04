"""Tests for the clear_workspace dispatcher command + GUI hook
(WP-I1-016).

Scope per WP: ACTIVE document only. Today there is one document so
clearing the workspace clears everything; the contract is written this
way so multi-file (WP-I1-036) lands without breaking semantics.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openrepose.app import App


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
        run_migrations=False,
    )


def _import(app: App, aeri_master: Path) -> None:
    r = app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    assert r.status == "ok", r.payload


# --- happy path ------------------------------------------------------------


def test_clear_workspace_drops_rig_yaw_portrait(app: App, aeri_master: Path):
    _import(app, aeri_master)
    # Move yaw off zero so we can prove the reset.
    r = app.handle_command({"command": "set_yaw_bin", "bin": "her-left 30"})
    assert r.status == "ok", r.payload
    assert app.state.rig["status"] == "ok"
    assert app.state.portrait == str(aeri_master)
    assert app.state.avatar_slug == "aeri"

    r = app.handle_command({"command": "clear_workspace"})

    assert r.status == "ok", r.payload
    assert r.payload["cleared"] is True
    assert app.state.rig["status"] == "none"
    assert app.state.yaw["current_bin"] == "0"
    assert app.state.yaw["current_value_deg"] == 0.0
    assert app.state.portrait is None
    assert app.state.avatar_slug is None
    assert app.dispatcher._rig is None


def test_clear_workspace_state_json_written(app: App, aeri_master: Path):
    _import(app, aeri_master)
    app.handle_command({"command": "clear_workspace"})

    state_doc = json.loads(app.state.state_path.read_text(encoding="utf-8"))
    assert state_doc["rig"]["status"] == "none"
    assert state_doc["yaw"]["current_bin"] == "0"
    assert state_doc["portrait"] is None
    assert state_doc["avatar_slug"] is None


def test_clear_workspace_then_reimport_succeeds(app: App, aeri_master: Path):
    _import(app, aeri_master)
    app.handle_command({"command": "clear_workspace"})
    # Re-import after clear must work normally.
    _import(app, aeri_master)
    assert app.state.rig["status"] == "ok"
    assert app.dispatcher._rig is not None


def test_clear_workspace_when_already_empty(app: App):
    """Idempotent: calling clear on an empty workspace is a no-op success,
    not an error."""
    r = app.handle_command({"command": "clear_workspace"})
    assert r.status == "ok", r.payload
    assert app.state.rig["status"] == "none"
    assert app.state.portrait is None


# --- isolation: settings / visibility / calibration / log untouched --------


def test_clear_workspace_preserves_settings(app: App, aeri_master: Path, tmp_path: Path):
    target = tmp_path / "operator-exports"
    target.mkdir()
    app.settings.update(
        export_folder=str(target),
        operator_slug="ilja",
        canvas_border_color="#abcdef",
    )
    _import(app, aeri_master)
    app.handle_command({"command": "clear_workspace"})

    assert app.settings.export_folder == str(target)
    assert app.settings.operator_slug == "ilja"
    assert app.settings.canvas_border_color == "#abcdef"


def test_clear_workspace_preserves_body_part_visibility(
    app: App, aeri_master: Path
):
    _import(app, aeri_master)
    app.handle_command(
        {"command": "set_body_part_visibility", "hands": False}
    )
    assert app.state.body_part_visibility["hands"] is False

    app.handle_command({"command": "clear_workspace"})
    assert app.state.body_part_visibility["hands"] is False


def test_clear_workspace_preserves_log_lines(app: App, aeri_master: Path):
    import datetime as _dt

    _import(app, aeri_master)
    log_path = app.log.log_dir / (
        "openrepose-" + _dt.date.today().isoformat().replace("-", "") + ".log"
    )
    before_size = log_path.stat().st_size if log_path.exists() else 0

    app.handle_command({"command": "clear_workspace"})

    assert log_path.exists()
    after_size = log_path.stat().st_size
    # Log only grows; clear_workspace appends "workspace.clear" and
    # cmd.completed lines.
    assert after_size > before_size


def test_clear_outputs_semantics_unchanged_after_clear(
    app: App, aeri_master: Path
):
    """clear_outputs purges the export/snapshot/error arrays only — must
    NOT touch rig/yaw/portrait. Sibling test of clear_workspace's contract."""
    _import(app, aeri_master)
    app.handle_command({"command": "set_yaw_bin", "bin": "her-right 15"})
    rig_status_before = app.state.rig["status"]
    yaw_bin_before = app.state.yaw["current_bin"]
    portrait_before = app.state.portrait

    app.handle_command({"command": "clear_outputs"})

    assert app.state.rig["status"] == rig_status_before
    assert app.state.yaw["current_bin"] == yaw_bin_before
    assert app.state.portrait == portrait_before


# --- response envelope ----------------------------------------------------


def test_clear_workspace_response_carries_stance(app: App):
    r = app.handle_command({"command": "clear_workspace"})
    envelope = r.to_dict()
    assert envelope["adult_production_boundary"]["acknowledgement_required"] is True


# --- GUI hook -------------------------------------------------------------


def test_toolbar_clear_workspace_button_exists_and_dispatches(
    qtbot, app: App, aeri_master: Path
):
    """Toolbar button + Edit menu action both wire to the headless command.
    Tested via signal capture so we don't depend on a live timer or render."""
    from openrepose.gui.main_window import MainWindow

    # Avoid focus theft during the test (GUI is headless via offscreen
    # platform configured by conftest).
    win = MainWindow(app)
    qtbot.addWidget(win)

    _import(app, aeri_master)
    app.handle_command({"command": "set_yaw_bin", "bin": "her-left 30"})
    assert app.state.rig["status"] == "ok"

    # Simulate the toolbar button click.
    win._toolbar.btn_clear_workspace.click()

    assert app.state.rig["status"] == "none"
    assert app.state.yaw["current_bin"] == "0"
    assert app.state.portrait is None


def test_edit_menu_clear_workspace_action_dispatches(
    qtbot, app: App, aeri_master: Path
):
    from openrepose.gui.main_window import MainWindow

    win = MainWindow(app)
    qtbot.addWidget(win)

    _import(app, aeri_master)
    win.act_clear_workspace.trigger()

    assert app.state.rig["status"] == "none"
    assert app.state.portrait is None
