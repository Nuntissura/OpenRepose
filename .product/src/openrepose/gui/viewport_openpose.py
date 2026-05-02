"""OpenPose preview viewport. Displays the live OpenPose-format wireframe
at the current yaw setting."""

from __future__ import annotations

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from ..render.draw_openpose import render_openpose
from ..rotation import RotatedRig


class ViewportOpenPose(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 400)
        self.setStyleSheet("background-color: #000;")
        self._placeholder("no rig loaded")

    def update_rig(self, rotated: RotatedRig) -> None:
        bgr = render_openpose(rotated)
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
        self.setText(f"[openpose preview: {msg}]")
        self.setStyleSheet(
            "background-color: #000; color: #888; padding: 12px; font-family: Consolas, monospace;"
        )
