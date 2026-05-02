"""GUI tests for the Calibration tab.

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 2 / GUI Requirements".
"""

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


def test_calibration_tab_present(app_and_window) -> None:
    _app, window = app_and_window
    titles = [
        window._tabs.tabText(i) for i in range(window._tabs.count())
    ]
    assert "Calibration" in titles


def test_calibration_pane_has_all_marker_names_in_dropdown(
    app_and_window,
) -> None:
    from openrepose.calibration import OPTIONAL_MARKERS, REQUIRED_MARKERS

    _app, window = app_and_window
    pane = window._calibration
    items = [
        pane._marker_combo.itemText(i)
        for i in range(pane._marker_combo.count())
    ]
    assert items == list(REQUIRED_MARKERS) + list(OPTIONAL_MARKERS)


def test_calibration_pane_completeness_default_none(app_and_window) -> None:
    _app, window = app_and_window
    text = window._calibration._completeness.text().lower()
    assert "none" in text


def test_calibration_pane_buttons_present(app_and_window) -> None:
    _app, window = app_and_window
    pane = window._calibration
    assert pane.btn_save is not None
    assert pane.btn_clear is not None
    assert pane.btn_redetect is not None


def test_calibration_pane_click_without_avatar_is_noop(app_and_window) -> None:
    """No active avatar -> portrait click silently no-ops; no error, no
    state change."""
    app, window = app_and_window
    pane = window._calibration
    pane._on_portrait_clicked(100, 200)
    assert app.state.calibration["completeness"] == "none"
    assert app.state.calibration["marker_count"] == 0


def test_calibration_pane_click_after_import_records_marker(
    app_and_window, aeri_master: Path, qtbot
) -> None:
    """Click on portrait while a portrait is loaded should fire
    set_calibration_points and update state.calibration."""
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    pane = window._calibration
    pane._marker_combo.setCurrentText("eye_outer_left")
    pane._on_portrait_clicked(412, 487)
    qtbot.wait(20)
    assert app.state.calibration["marker_count"] >= 1
    assert app.state.calibration["active_avatar"] == "aeri"
    # The completeness will be 'partial' since only 1 of 6 required is set.
    assert app.state.calibration["completeness"] == "partial"


def test_calibration_pane_clear_button_resets_state(
    app_and_window, aeri_master: Path, qtbot
) -> None:
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    pane = window._calibration
    pane._on_portrait_clicked(100, 200)
    qtbot.wait(20)
    assert app.state.calibration["marker_count"] >= 1

    pane._on_clear()
    qtbot.wait(20)
    assert app.state.calibration["marker_count"] == 0
    assert app.state.calibration["completeness"] == "none"


def test_calibration_pane_clicks_do_not_call_focus_apis(
    app_and_window, aeri_master: Path, monkeypatch, qtbot
) -> None:
    """Drive 10 calibration clicks and assert zero raise_/activateWindow/
    showNormal/showMaximized invocations (matches the project-wide
    no-focus-steal contract enforced by test_gui_no_focus_steal)."""
    from PySide6.QtWidgets import QWidget

    counts = {
        "raise_": 0,
        "activateWindow": 0,
        "showNormal": 0,
        "showMaximized": 0,
    }
    real = {
        "raise_": QWidget.raise_,
        "activateWindow": QWidget.activateWindow,
        "showNormal": QWidget.showNormal,
        "showMaximized": QWidget.showMaximized,
    }

    def make_counter(name: str):
        def wrapper(self):  # noqa: ANN001
            counts[name] += 1
            return real[name](self)

        return wrapper

    monkeypatch.setattr(QWidget, "raise_", make_counter("raise_"))
    monkeypatch.setattr(
        QWidget, "activateWindow", make_counter("activateWindow")
    )
    monkeypatch.setattr(QWidget, "showNormal", make_counter("showNormal"))
    monkeypatch.setattr(
        QWidget, "showMaximized", make_counter("showMaximized")
    )

    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    pane = window._calibration
    for i in range(10):
        pane._marker_combo.setCurrentIndex(i % pane._marker_combo.count())
        pane._on_portrait_clicked(100 + i * 10, 200 + i * 10)
        qtbot.wait(5)
    pane._on_clear()
    qtbot.wait(5)

    assert counts == {
        "raise_": 0,
        "activateWindow": 0,
        "showNormal": 0,
        "showMaximized": 0,
    }, counts


def test_calibration_pane_no_modal_dialog_apis_in_source() -> None:
    """Source check: spec forbids modal dialogs in response to LLM commands.
    Operator-side click handlers also avoid modals (we use the log pane for
    confirmations)."""
    src_path = (
        Path(__file__).parent.parent
        / "src"
        / "openrepose"
        / "gui"
        / "calibration.py"
    )
    src = src_path.read_text(encoding="utf-8")
    for forbidden in (
        "QMessageBox",
        ".exec(",
        ".exec_(",
    ):
        assert forbidden not in src, (
            f"{forbidden} found in gui/calibration.py"
        )
