"""GUI must never steal focus or raise itself in response to LLM commands."""

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


def test_50_llm_commands_no_focus_methods_called(app_and_window, monkeypatch, qtbot) -> None:
    """Drive 50 LLM-style commands through the dispatcher with the GUI alive.

    Monkeypatch the focus-affecting QWidget / QMainWindow methods to count
    invocations. Assert zero calls during LLM-driven state changes.
    """
    from PySide6.QtWidgets import QMainWindow, QWidget

    counts = {"raise_": 0, "activateWindow": 0, "showNormal": 0, "showMaximized": 0}

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
    monkeypatch.setattr(QWidget, "activateWindow", make_counter("activateWindow"))
    monkeypatch.setattr(QWidget, "showNormal", make_counter("showNormal"))
    monkeypatch.setattr(QWidget, "showMaximized", make_counter("showMaximized"))

    app, _window = app_and_window
    for i in range(50):
        bin_label = "her-left 30" if i % 2 == 0 else "her-right 30"
        r = app.handle_command({"command": "set_yaw_bin", "bin": bin_label})
        assert r.status == "ok"
        qtbot.wait(5)

    assert counts == {
        "raise_": 0,
        "activateWindow": 0,
        "showNormal": 0,
        "showMaximized": 0,
    }, counts


def test_widget_provider_registered_after_window_construction(app_and_window) -> None:
    """The MainWindow constructor registers a widget provider so the
    snapshot subsystem can grab live widgets. Verify the provider exists
    and returns the expected widgets for the spec's 8 targets."""
    from openrepose.render.widget_grab import _widget_provider

    _app, window = app_and_window
    assert _widget_provider is not None
    for target in ("inspector_pane", "log_pane", "options_pane", "status_bar", "toolbar"):
        widget = _widget_provider(target)
        assert widget is not None, f"no widget registered for target={target!r}"


def test_snapshot_with_real_widgets_does_not_steal_focus(app_and_window, monkeypatch) -> None:
    """Pull a real Qt-widget snapshot via the dispatcher. Real `QWidget.grab()`
    is invoked; assert no focus methods called during the snapshot path."""
    from PySide6.QtWidgets import QWidget

    counts = {"raise_": 0, "activateWindow": 0}
    monkeypatch.setattr(QWidget, "raise_", lambda self: counts.__setitem__("raise_", counts["raise_"] + 1))
    monkeypatch.setattr(
        QWidget,
        "activateWindow",
        lambda self: counts.__setitem__("activateWindow", counts["activateWindow"] + 1),
    )

    app, _window = app_and_window
    for target in ("inspector_pane", "log_pane", "toolbar", "status_bar", "options_pane"):
        r = app.handle_command({"command": "snapshot", "target": target})
        assert r.status == "ok", r.payload

    assert counts == {"raise_": 0, "activateWindow": 0}
