"""Regression tests for WP-I1-017/029/023 — the live OpenPose viewport
must reflect body_part_visibility, marker_visibility, and frame from
state, not just JSON export and snapshot.

Operator GUI inspection 2026-05-03 found that the polling loop dropped
these kwargs when calling viewport_openpose.update_rig(rotated), so
checkboxes + frame slider only affected export but not the live preview.
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
        settings_path=tmp_path / "settings.json",
    )
    window = MainWindow(app)
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.waitExposed(window)
    yield app, window
    app.stop()


def _spy_render(monkeypatch):
    """Replace render_openpose with a spy that records its kwargs."""
    captured: list[dict] = []
    from openrepose.gui import viewport_openpose as vo_mod

    real = vo_mod.render_openpose

    def spy(
        rotated,
        canvas_width=None,
        canvas_height=None,
        *,
        body_part_visibility=None,
        marker_visibility=None,
        frame=None,
        canvas_border_color=None,
    ):
        captured.append(
            {
                "body_part_visibility": body_part_visibility,
                "marker_visibility": marker_visibility,
                "frame": frame,
                "canvas_border_color": canvas_border_color,
            }
        )
        return real(
            rotated,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            body_part_visibility=body_part_visibility,
            marker_visibility=marker_visibility,
            frame=frame,
            canvas_border_color=canvas_border_color,
        )

    monkeypatch.setattr(vo_mod, "render_openpose", spy)
    return captured


def test_polling_passes_body_part_visibility_to_viewport(
    monkeypatch, app_and_window, aeri_master: Path, qtbot
) -> None:
    captured = _spy_render(monkeypatch)
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    app.handle_command(
        {"command": "set_body_part_visibility", "legs": False}
    )
    qtbot.wait(350)  # > polling interval (250ms)
    assert captured, "expected at least one viewport render"
    last = captured[-1]
    assert last["body_part_visibility"] is not None
    assert last["body_part_visibility"]["legs"] is False


def test_polling_passes_marker_visibility_to_viewport(
    monkeypatch, app_and_window, aeri_master: Path, qtbot
) -> None:
    captured = _spy_render(monkeypatch)
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    app.handle_command(
        {
            "command": "set_marker_visibility",
            "schema": "body_18",
            "index": 4,
            "visible": False,
        }
    )
    qtbot.wait(350)
    assert captured
    last = captured[-1]
    assert last["marker_visibility"] is not None
    assert last["marker_visibility"]["body_18"] == {"4": False}


def test_polling_passes_frame_to_viewport(
    monkeypatch, app_and_window, aeri_master: Path, qtbot
) -> None:
    captured = _spy_render(monkeypatch)
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    app.handle_command({"command": "set_frame_scale", "scale": 0.6})
    qtbot.wait(350)
    assert captured
    last = captured[-1]
    assert last["frame"] is not None
    assert last["frame"]["scale"] == 0.6


def test_polling_passes_all_three_blocks_combined(
    monkeypatch, app_and_window, aeri_master: Path, qtbot
) -> None:
    """All three blocks (body / marker / frame) flow through together."""
    captured = _spy_render(monkeypatch)
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    app.handle_command(
        {"command": "set_body_part_visibility", "arms": False}
    )
    app.handle_command(
        {
            "command": "set_marker_visibility",
            "schema": "face_70",
            "index": 12,
            "visible": False,
        }
    )
    app.handle_command({"command": "set_frame_scale", "scale": 1.5})
    qtbot.wait(350)
    last = captured[-1]
    assert last["body_part_visibility"]["arms"] is False
    assert last["marker_visibility"]["face_70"] == {"12": False}
    assert last["frame"]["scale"] == 1.5
