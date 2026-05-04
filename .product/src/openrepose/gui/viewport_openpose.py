"""OpenPose preview viewport. Displays the live OpenPose-format wireframe
at the current yaw setting."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from ..render.draw_openpose import render_openpose
from ..rotation import RotatedRig
from .drop_helper import decide_drop, mime_has_acceptable_image


class ViewportOpenPose(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 400)
        self.setStyleSheet("background-color: #000;")
        self._placeholder("no rig loaded")
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
        decision = decide_drop(event.mimeData())
        if decision.path is None or self._drop_callback is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self._drop_callback(decision.path)

    def update_rig(
        self,
        rotated: RotatedRig,
        *,
        body_part_visibility: dict[str, bool] | None = None,
        marker_visibility: dict | None = None,
        frame: dict | None = None,
        canvas_border_color: str | None = None,
    ) -> None:
        """Render the rotated rig at the live state.

        WP-I1-017/029/023 fix: previously this dropped body_part_visibility,
        marker_visibility, and frame. WP-I1-032 added canvas_border_color so
        the operator-configured border outline appears in the live preview
        too (helpful when frame_scale < 1.0 makes the figure smaller than
        the canvas).
        """
        bgr = render_openpose(
            rotated,
            body_part_visibility=body_part_visibility,
            marker_visibility=marker_visibility,
            frame=frame,
            canvas_border_color=canvas_border_color,
        )
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
