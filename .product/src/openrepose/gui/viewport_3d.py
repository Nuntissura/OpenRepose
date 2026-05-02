"""3D mesh viewport widget. Displays the cv2-rendered 3D wireframe diagnostic
of the rotated rig. Read-only inspection: mouse drag is reserved for a
future polish WP (orbital camera). v0.1 just shows the current rig state."""

from __future__ import annotations

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from ..render.draw_3d import render_3d_viewport
from ..rotation import RotatedRig


class Viewport3D(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 400)
        self.setStyleSheet("background-color: #202020;")
        self._placeholder("no rig loaded")

    def update_rig(self, rotated: RotatedRig) -> None:
        # Render at the rig's portrait size, then scale to widget for display.
        bgr = render_3d_viewport(rotated)
        self._show_bgr(bgr)

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
