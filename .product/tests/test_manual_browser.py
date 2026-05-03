"""Tests for the in-app manual browser (WP-I1-035)."""

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
        settings_path=tmp_path / "settings.json",
    )
    window = MainWindow(app)
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.waitExposed(window)
    yield app, window
    app.stop()


def test_help_pane_finds_manual_root(app_and_window) -> None:
    """The help pane resolves the manual root by walking up from its own
    file location."""
    _app, window = app_and_window
    help_pane = window._help_pane
    assert help_pane._manual_root is not None
    assert help_pane._manual_root.exists()
    assert help_pane._manual_root.name == "manual"


def test_help_pane_lists_manual_topics(app_and_window) -> None:
    """Topic list contains at least the index + 5 starter topics."""
    _app, window = app_and_window
    help_pane = window._help_pane
    items = [
        help_pane._topic_list.item(i).text()
        for i in range(help_pane._topic_list.count())
    ]
    # Stripped of .md extension and dashes converted to spaces.
    # Index always first.
    assert items[0] == "index"
    assert "getting started" in items
    assert "feature 1 yaw exporter" in items
    assert "feature 2 calibration overlay" in items
    assert "feature 3 library postgresql" in items
    assert "keyboard shortcuts" in items


def test_help_pane_loads_index_by_default(app_and_window) -> None:
    """On open the viewer renders the index.md content."""
    _app, window = app_and_window
    help_pane = window._help_pane
    text = help_pane._viewer.toPlainText()
    assert "OpenRepose Manual" in text


def test_help_pane_no_focus_steal_apis() -> None:
    """help_pane.py source must not call focus-stealing APIs."""
    src_path = (
        Path(__file__).parent.parent
        / "src"
        / "openrepose"
        / "gui"
        / "help_pane.py"
    )
    src = src_path.read_text(encoding="utf-8")
    for forbidden in (
        "raise_(",
        "activateWindow(",
        "showNormal(",
        "setForegroundWindow(",
        "showMaximized(",
    ):
        assert forbidden not in src, (
            f"{forbidden} found in gui/help_pane.py"
        )
