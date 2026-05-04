"""GUI layout smoke: window opens, all panes present, toolbar works."""

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
    window.resize(1280, 800)
    window.show()
    qtbot.waitExposed(window)
    yield app, window
    app.stop()


def test_window_does_not_set_show_without_activating_permanently(app_and_window) -> None:
    """First launch should come to the foreground naturally. The
    no-focus-steal contract is enforced by `test_gui_no_focus_steal` on
    LLM-driven dispatch routes, not by hiding the window on launch."""
    from PySide6.QtCore import Qt

    _app, window = app_and_window
    assert not window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)


def test_toolbar_present_with_yaw_widgets(app_and_window) -> None:
    _app, window = app_and_window
    toolbar = window._toolbar
    assert toolbar is not None
    assert toolbar.bin_combo.count() == 13
    assert toolbar.slider.minimum() == -90
    assert toolbar.slider.maximum() == 90


def test_two_viewports_exist(app_and_window) -> None:
    _app, window = app_and_window
    assert window._viewport_3d is not None
    assert window._viewport_openpose is not None


def test_dock_tabs_present(app_and_window) -> None:
    """WP-I1-031 collapsed Calibration + Markers + Reframer under Tools.
    WP-I2-006 added Library between Tools and Options.
    WP-I3-008 added Triage between Library and Options."""
    _app, window = app_and_window
    tab_titles = [window._tabs.tabText(i) for i in range(window._tabs.count())]
    assert tab_titles == [
        "Inspector",
        "Tools",
        "Library",
        "Triage",
        "Options",
        "Log",
        "Help",
    ]


def test_tools_tab_has_three_sub_tabs(app_and_window) -> None:
    _app, window = app_and_window
    tools = window._tools
    sub_titles = [tools._tabs.tabText(i) for i in range(tools._tabs.count())]
    assert sub_titles == ["Calibration", "Markers", "Reframer"]


def test_reframer_pane_has_slider_spinbox_and_resets(app_and_window) -> None:
    _app, window = app_and_window
    rf = window._reframer
    assert rf.scale_slider is not None
    assert rf.scale_spin is not None
    assert rf.offset_x_slider is not None
    assert rf.offset_x_spin is not None
    assert rf.offset_y_slider is not None
    assert rf.offset_y_spin is not None
    assert rf.btn_reset_scale is not None
    assert rf.btn_reset_offset is not None
    assert rf.btn_reset_anchor is not None
    assert rf.btn_reset_all is not None


def test_reframer_scale_slider_dispatches_set_frame_scale(
    app_and_window, qtbot
) -> None:
    app, window = app_and_window
    window._reframer.scale_slider.setValue(60)  # 0.60x
    qtbot.wait(50)
    assert app.state.frame["scale"] == 0.6


def test_reframer_offset_x_spinbox_dispatches_set_frame_offset(
    app_and_window, qtbot
) -> None:
    app, window = app_and_window
    window._reframer.offset_x_spin.setValue(50)
    qtbot.wait(50)
    assert app.state.frame["offset_x"] == 50


def test_status_bar_shows_yaw_readout(app_and_window) -> None:
    _app, window = app_and_window
    text = window._status_bar._label.text()
    assert "yaw=" in text
    assert "rig=" in text


def test_yaw_bin_dropdown_change_dispatches_command(app_and_window, qtbot) -> None:
    app, window = app_and_window
    window._toolbar.bin_combo.setCurrentText("her-left 30")
    qtbot.wait(50)
    assert app.state.yaw["current_bin"] == "her-left 30"
    assert app.state.yaw["current_value_deg"] == 30.0


def test_yaw_slider_change_dispatches_command(app_and_window, qtbot) -> None:
    app, window = app_and_window
    window._toolbar.slider.setValue(-45)
    qtbot.wait(50)
    assert app.state.yaw["current_value_deg"] == -45.0
