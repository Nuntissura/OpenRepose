"""WP-I1-002: GUI-only orbital camera for the 3D viewport."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, Qt

from openrepose.gui.viewport_3d import Viewport3D
from openrepose.render.draw_3d import render_3d_viewport
from openrepose.rotation import rotate_yaw
from openrepose.yaw_bin import parse_bin


def _rotated(aeri_rig):
    return rotate_yaw(aeri_rig, parse_bin("0"))


def test_render_camera_zero_matches_default(aeri_rig) -> None:
    rotated = _rotated(aeri_rig)
    baseline = render_3d_viewport(rotated)
    explicit_zero = render_3d_viewport(
        rotated,
        camera_yaw_deg=0.0,
        camera_pitch_deg=0.0,
    )
    assert np.array_equal(baseline, explicit_zero)


def test_render_camera_angle_changes_image(aeri_rig) -> None:
    rotated = _rotated(aeri_rig)
    baseline = render_3d_viewport(rotated)
    orbital = render_3d_viewport(
        rotated,
        camera_yaw_deg=35.0,
        camera_pitch_deg=20.0,
    )
    assert baseline.shape == orbital.shape
    assert not np.array_equal(baseline, orbital)


def test_viewport_drag_updates_camera_state(qtbot, aeri_rig) -> None:
    widget = Viewport3D()
    widget.resize(640, 480)
    qtbot.addWidget(widget)
    widget.update_rig(_rotated(aeri_rig))

    qtbot.mousePress(widget, Qt.MouseButton.LeftButton, pos=QPoint(100, 120))
    qtbot.mouseMove(widget, pos=QPoint(220, 40))
    qtbot.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=QPoint(220, 40))

    assert widget.camera_yaw_deg != 0.0
    assert widget.camera_pitch_deg != 0.0
    assert widget.pixmap() is not None


def test_viewport_pitch_clamps(qtbot, aeri_rig) -> None:
    widget = Viewport3D()
    widget.resize(640, 480)
    qtbot.addWidget(widget)
    widget.update_rig(_rotated(aeri_rig))

    qtbot.mousePress(widget, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
    qtbot.mouseMove(widget, pos=QPoint(100, 1000))
    qtbot.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=QPoint(100, 1000))

    assert widget.camera_pitch_deg == 89.0


def test_reset_orbital_camera_restores_zero(qtbot, aeri_rig) -> None:
    widget = Viewport3D()
    qtbot.addWidget(widget)
    widget.update_rig(_rotated(aeri_rig))
    widget.camera_yaw_deg = 25.0
    widget.camera_pitch_deg = -15.0

    widget.reset_orbital_camera()

    assert widget.camera_yaw_deg == 0.0
    assert widget.camera_pitch_deg == 0.0
