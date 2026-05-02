"""Operator-facing Calibration tab.

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 2 / GUI Requirements".

Master portrait display with click-to-place reference markers, anatomical-name
dropdown, MediaPipe-detected positions shown in dim color, completeness
indicator, Save / Clear buttons. The tab is operator-facing only; LLM agents
use the four `*_calibration*` commands directly.

LLM Headless contract:
- No `raise_()`, `activateWindow()`, `showNormal()`, or `setForegroundWindow()`
  call in any code path.
- No modal dialogs in response to LLM-driven calibration changes; the polling
  loop in `MainWindow` re-renders the overlay silently.
- All operator clicks issue dispatcher commands; the GUI never bypasses the
  command surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..calibration import (
    OPTIONAL_MARKERS,
    REQUIRED_MARKERS,
    Calibration,
    calibration_path,
)
from ..calibration import load as load_calibration
from ..render.draw_calibration import render_calibration_overlay

if TYPE_CHECKING:
    from ..app import App

ALL_MARKER_NAMES_ORDERED: tuple[str, ...] = REQUIRED_MARKERS + OPTIONAL_MARKERS


class _ClickablePortrait(QLabel):
    """QLabel that emits image-space (x, y) on left-click."""

    clicked = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._image_size: tuple[int, int] = (0, 0)
        self._displayed_size: tuple[int, int] = (0, 0)
        self._displayed_offset: tuple[int, int] = (0, 0)

    def set_overlay(
        self,
        bgr: np.ndarray,
        image_size: tuple[int, int],
    ) -> None:
        """Show the rendered overlay scaled to fit the label.

        Tracks the displayed size + offset so click coords can be back-projected
        to original image space.
        """
        self._image_size = image_size
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        # ascontiguousarray makes the QImage stable; without it, slicing can
        # produce non-contiguous memory and Qt sees stride mismatches.
        rgb = np.ascontiguousarray(rgb)
        qimg = QImage(
            rgb.data,
            w,
            h,
            rgb.strides[0],
            QImage.Format.Format_RGB888,
        ).copy()
        pix = QPixmap.fromImage(qimg)
        scaled = pix.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self._displayed_size = (scaled.width(), scaled.height())
        # Center inside the label widget.
        ox = max(0, (self.width() - scaled.width()) // 2)
        oy = max(0, (self.height() - scaled.height()) // 2)
        self._displayed_offset = (ox, oy)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._image_size == (0, 0) or self._displayed_size == (0, 0):
            return
        click = event.position()
        ox, oy = self._displayed_offset
        dx = click.x() - ox
        dy = click.y() - oy
        dw, dh = self._displayed_size
        if dx < 0 or dy < 0 or dx >= dw or dy >= dh:
            return
        iw, ih = self._image_size
        ix = int(round(dx * iw / dw))
        iy = int(round(dy * ih / dh))
        ix = max(0, min(iw - 1, ix))
        iy = max(0, min(ih - 1, iy))
        self.clicked.emit(ix, iy)


class CalibrationPane(QWidget):
    """Operator-facing calibration tab.

    The pane is an idempotent view over `App.state` + the per-avatar
    calibration JSON. Refresh is driven by the `MainWindow` polling timer; no
    timers or workers live in this widget.
    """

    def __init__(self, app: "App") -> None:
        super().__init__()
        self._app = app

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top row: marker selector + completeness.
        top = QHBoxLayout()
        marker_label = QLabel("active marker:")
        marker_label.setObjectName("inspector-key")
        self._marker_combo = QComboBox()
        self._marker_combo.addItems(ALL_MARKER_NAMES_ORDERED)
        self._completeness = QLabel("calibration: none")
        self._completeness.setObjectName("inspector-value")
        top.addWidget(marker_label)
        top.addWidget(self._marker_combo, 1)
        top.addStretch(1)
        top.addWidget(self._completeness)
        layout.addLayout(top)

        # Portrait display with overlay.
        self._portrait = _ClickablePortrait()
        self._portrait.clicked.connect(self._on_portrait_clicked)
        layout.addWidget(self._portrait, 1)

        # Bottom row: action buttons.
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_clear = QPushButton("Clear")
        self.btn_redetect = QPushButton("Re-detect")
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_redetect)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Status / hint label.
        self._hint = QLabel(
            "click on portrait to place the active marker. each click writes "
            "calibration.json immediately."
        )
        self._hint.setObjectName("inspector-key")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self.btn_save.clicked.connect(self._on_save)
        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_redetect.clicked.connect(self._on_redetect)

        self.refresh()

    # --- public update path (called by MainWindow polling) ---------------

    def refresh(self) -> None:
        """Render the portrait + current calibration overlay."""
        cal = self._load_active_calibration()
        portrait_path = self._app.state.portrait
        bgr = render_calibration_overlay(portrait_path, cal)
        h, w = bgr.shape[:2]
        self._portrait.set_overlay(bgr, image_size=(w, h))

        completeness = "none"
        marker_count = 0
        if cal is not None:
            completeness = cal.completeness
            marker_count = cal.marker_count
        self._completeness.setText(
            f"calibration: {completeness} ({marker_count} markers)"
        )

    # --- operator action handlers ----------------------------------------

    def _on_portrait_clicked(self, x: int, y: int) -> None:
        avatar = self._app.state.avatar_slug
        if not avatar:
            return  # no portrait loaded; click is a no-op
        marker = self._marker_combo.currentText()
        self._app.handle_command(
            {
                "command": "set_calibration_points",
                "markers": [
                    {"name": marker, "operator_xy": [x, y]},
                ],
                "merge": True,
            }
        )
        self.refresh()

    def _on_save(self) -> None:
        # set_calibration_points already persists on every click; Save is a
        # confirmation hook (dump current calibration so the operator can see
        # the state in the log pane).
        if not self._app.state.avatar_slug:
            return
        self._app.handle_command({"command": "dump_calibration"})
        self.refresh()

    def _on_clear(self) -> None:
        if not self._app.state.avatar_slug:
            return
        self._app.handle_command({"command": "clear_calibration"})
        self.refresh()

    def _on_redetect(self) -> None:
        portrait = self._app.state.portrait
        avatar = self._app.state.avatar_slug
        if not portrait or not avatar:
            return
        self._app.handle_command(
            {
                "command": "import_portrait",
                "path": portrait,
                "avatar_slug": avatar,
            }
        )
        self.refresh()

    # --- internals -------------------------------------------------------

    def _load_active_calibration(self) -> Calibration | None:
        avatar = self._app.state.avatar_slug
        if not avatar:
            return None
        return load_calibration(
            calibration_path(self._app.dispatcher.outputs_root, avatar)
        )
