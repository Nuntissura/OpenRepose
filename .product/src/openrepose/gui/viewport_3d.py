"""3D mesh viewport widget. Displays the cv2-rendered 3D wireframe diagnostic
of the rotated rig. Read-only inspection: mouse drag is reserved for a
future polish WP (orbital camera). v0.1 just shows the current rig state."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import cv2
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from ..render.draw_3d import render_3d_viewport
from ..rotation import RotatedRig
from .drop_helper import decide_multi_drop, mime_has_acceptable_image


class Viewport3D(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 400)
        self.setStyleSheet("background-color: #202020;")
        self._placeholder("no rig loaded")
        self.camera_yaw_deg = 0.0
        self.camera_pitch_deg = 0.0
        self._dragging_camera = False
        self._last_drag_pos: QPointF | None = None
        self._last_rotated: RotatedRig | None = None
        self.setToolTip(
            "Left-drag orbits the 3D inspection camera only; rig yaw/export are unchanged."
        )
        # WP-I1-005: viewport accepts portrait drops; MainWindow installs
        # the callback that does the actual import dispatch.
        self.setAcceptDrops(True)
        self._drop_callback: Callable[[Path], None] | None = None

    def set_drop_callback(self, cb: Callable[[Path], None]) -> None:
        self._drop_callback = cb

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if mime_has_acceptable_image(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if mime_has_acceptable_image(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt API)
        decision = decide_multi_drop(event.mimeData())
        if not decision.paths or self._drop_callback is None:
            event.ignore()
            return
        event.acceptProposedAction()
        for path in decision.paths:
            self._drop_callback(path)

    def update_rig(self, rotated: RotatedRig) -> None:
        self._last_rotated = rotated
        # Render at the rig's portrait size, then scale to widget for display.
        bgr = render_3d_viewport(
            rotated,
            camera_yaw_deg=self.camera_yaw_deg,
            camera_pitch_deg=self.camera_pitch_deg,
        )
        self._show_bgr(bgr)

    def reset_orbital_camera(self) -> None:
        self.camera_yaw_deg = 0.0
        self.camera_pitch_deg = 0.0
        if self._last_rotated is not None:
            self.update_rig(self._last_rotated)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton and self._last_rotated is not None:
            self._dragging_camera = True
            self._last_drag_pos = event.position()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if (
            self._dragging_camera
            and self._last_drag_pos is not None
            and self._last_rotated is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            pos = event.position()
            delta = pos - self._last_drag_pos
            self._last_drag_pos = pos
            self.camera_yaw_deg += float(delta.x()) * 0.35
            self.camera_pitch_deg = max(
                -89.0,
                min(89.0, self.camera_pitch_deg + float(delta.y()) * 0.35),
            )
            self.update_rig(self._last_rotated)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton and self._dragging_camera:
            self._dragging_camera = False
            self._last_drag_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _show_bgr(self, bgr) -> None:
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pix)

    def _placeholder(self, msg: str) -> None:
        self.setText(f"[3D viewport: {msg}]")
        self.setStyleSheet(
            "background-color: #202020; color: #888; padding: 12px; font-family: Consolas, monospace;"
        )
