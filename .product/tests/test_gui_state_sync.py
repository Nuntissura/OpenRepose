"""GUI <-> AppState bidirectional sync."""

from __future__ import annotations

from pathlib import Path

import pytest


pytest.importorskip("pytestqt")


@pytest.fixture
def app_and_window(qtbot, tmp_path: Path):
    from openrepose.app import App
    from openrepose.gui.main_window import MainWindow

    app = App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
    )
    window = MainWindow(app)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    yield app, window
    app.stop()


def test_llm_command_updates_gui_widgets(app_and_window, qtbot) -> None:
    """LLM-driven set_yaw_bin should reflect in the toolbar slider and bin
    dropdown after the polling timer ticks."""
    app, window = app_and_window
    app.handle_command({"command": "set_yaw_bin", "bin": "her-right 45"})
    qtbot.wait(400)  # let the 250ms poll fire
    assert window._toolbar.slider.value() == -45
    assert window._toolbar.bin_combo.currentText() == "her-right 45"


def test_operator_slider_drag_updates_state(app_and_window, qtbot) -> None:
    """Operator slider movement updates AppState (i.e., bidirectional)."""
    app, window = app_and_window
    window._toolbar.slider.setValue(60)
    qtbot.wait(50)
    assert app.state.yaw["current_value_deg"] == 60.0
    assert app.state.yaw["current_bin"] == "her-left 60"


def test_inspector_reflects_rig_status_after_import(app_and_window, qtbot, aeri_master: Path) -> None:
    app, window = app_and_window
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    qtbot.wait(400)
    assert window._inspector._fields["rig_status"].text() == "ok"
    assert int(window._inspector._fields["face_landmarks"].text()) == 478


def test_status_bar_reflects_yaw_changes(app_and_window, qtbot) -> None:
    app, window = app_and_window
    app.handle_command({"command": "set_yaw_bin", "bin": "her-left 75"})
    qtbot.wait(400)
    assert "her-left 75" in window._status_bar._label.text()
