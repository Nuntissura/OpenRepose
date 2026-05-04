"""Tests for the drag-and-drop portrait import (WP-I1-005).

Covers the drop-helper validation directly (cheap unit tests) plus
end-to-end drop simulation through the GUI widgets via pytest-qt's
synthetic QDropEvent / QDragEnterEvent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from openrepose.app import App
from openrepose.gui.drop_helper import decide_drop, mime_has_acceptable_image


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
        run_migrations=False,
    )


def _mime_for(*paths: Path) -> QMimeData:
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    return md


# --- drop_helper unit tests ----------------------------------------------


def test_decide_drop_accepts_png(aeri_master: Path):
    md = _mime_for(aeri_master)
    decision = decide_drop(md)
    assert decision.path == aeri_master
    assert decision.ignored == []
    assert decision.reason is None


def test_decide_drop_accepts_jpg(tmp_path: Path):
    fake_jpg = tmp_path / "x.jpg"
    fake_jpg.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    md = _mime_for(fake_jpg)
    decision = decide_drop(md)
    assert decision.path == fake_jpg


def test_decide_drop_rejects_non_image(tmp_path: Path):
    txt = tmp_path / "notes.txt"
    txt.write_text("hello", encoding="utf-8")
    decision = decide_drop(_mime_for(txt))
    assert decision.path is None
    assert "no image file" in (decision.reason or "")


def test_decide_drop_rejects_lnk_shell_link(tmp_path: Path):
    lnk = tmp_path / "shortcut.lnk"
    lnk.write_bytes(b"L\x00\x00\x00\x01\x14\x02\x00")  # plausible-ish lnk header
    decision = decide_drop(_mime_for(lnk))
    assert decision.path is None


def test_decide_drop_rejects_missing_file(tmp_path: Path):
    decision = decide_drop(_mime_for(tmp_path / "does_not_exist.png"))
    assert decision.path is None


def test_decide_drop_multi_file_picks_first_image_logs_rest(
    aeri_master: Path, tmp_path: Path
):
    txt = tmp_path / "notes.txt"
    txt.write_text("hello", encoding="utf-8")
    second = tmp_path / "second.png"
    second.write_bytes(b"\x89PNG\r\n\x1a\n")
    decision = decide_drop(_mime_for(aeri_master, second, txt))
    assert decision.path == aeri_master
    assert sorted(decision.ignored) == sorted(["second.png", "notes.txt"])


def test_decide_drop_empty_mime():
    md = QMimeData()
    decision = decide_drop(md)
    assert decision.path is None
    assert "no local file paths" in (decision.reason or "")


def test_mime_has_acceptable_image_quick_check(aeri_master: Path, tmp_path: Path):
    assert mime_has_acceptable_image(_mime_for(aeri_master)) is True
    assert mime_has_acceptable_image(_mime_for(tmp_path / "x.txt")) is False
    assert mime_has_acceptable_image(QMimeData()) is False


# --- end-to-end via Main Window ------------------------------------------


def _drop_on(widget, mime_data) -> None:
    """Synthesize a Qt QDropEvent on the given widget. We bypass
    QDragEnterEvent — the drop handler does its own validation and pytest-qt
    cannot reliably synthesize the full DnD lifecycle on Windows."""
    pos = QPointF(widget.rect().center())
    event = QDropEvent(
        pos,
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.dropEvent(event)


def test_drop_on_main_window_dispatches_import(qtbot, app: App, aeri_master: Path):
    from openrepose.gui.main_window import MainWindow

    win = MainWindow(app)
    qtbot.addWidget(win)

    _drop_on(win, _mime_for(aeri_master))

    assert app.state.rig["status"] == "ok"
    assert app.state.portrait == str(aeri_master)
    assert app.state.avatar_slug  # non-empty


def test_drop_on_viewport_3d_forwards_to_main_window(
    qtbot, app: App, aeri_master: Path
):
    from openrepose.gui.main_window import MainWindow

    win = MainWindow(app)
    qtbot.addWidget(win)

    _drop_on(win._viewport_3d, _mime_for(aeri_master))

    assert app.state.rig["status"] == "ok"
    assert app.state.portrait == str(aeri_master)


def test_drop_on_openpose_viewport_forwards_to_main_window(
    qtbot, app: App, aeri_master: Path
):
    from openrepose.gui.main_window import MainWindow

    win = MainWindow(app)
    qtbot.addWidget(win)

    _drop_on(win._viewport_openpose, _mime_for(aeri_master))

    assert app.state.rig["status"] == "ok"


def test_drop_non_image_does_not_import(qtbot, app: App, tmp_path: Path):
    from openrepose.gui.main_window import MainWindow

    win = MainWindow(app)
    qtbot.addWidget(win)

    txt = tmp_path / "notes.txt"
    txt.write_text("hello", encoding="utf-8")
    _drop_on(win, _mime_for(txt))

    assert app.state.rig["status"] == "none"
    assert app.state.portrait is None


def test_drop_multi_file_imports_first_only(
    qtbot, app: App, aeri_master: Path, tmp_path: Path
):
    from openrepose.gui.main_window import MainWindow

    win = MainWindow(app)
    qtbot.addWidget(win)

    second = tmp_path / "second.png"
    second.write_bytes(b"\x89PNG\r\n\x1a\n")
    _drop_on(win, _mime_for(aeri_master, second))

    assert app.state.portrait == str(aeri_master)


def test_drop_persists_last_portrait_dir(qtbot, app: App, aeri_master: Path):
    from openrepose.gui.main_window import MainWindow

    win = MainWindow(app)
    qtbot.addWidget(win)

    _drop_on(win, _mime_for(aeri_master))

    assert app.settings.last_portrait_dir == str(aeri_master.parent)


def test_filename_with_forbidden_yaw_phrase_imports_normally(
    qtbot, app: App, tmp_path: Path
):
    """Forbidden yaw phrases in path data must not crash the import; the
    rule applies to source/docs/labels, not arbitrary external file names.
    Filename is just data."""
    src = tmp_path / "image-left-side-portrait.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n")
    from openrepose.gui.main_window import MainWindow

    win = MainWindow(app)
    qtbot.addWidget(win)

    _drop_on(win, _mime_for(src))

    # Import was attempted (might succeed or fail rig fit on the dummy
    # PNG bytes); the contract is "no crash + no GUI text echoes the
    # phrase". State portrait reflects the path either way iff fit ran.
    # We assert no crash happened by reaching this line.
    assert win is not None
