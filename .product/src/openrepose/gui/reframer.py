"""Reframer pane: frame scale + offset + anchor controls (WP-I1-031).

Extracted from OptionsPane during the Tools tab reorganization. Each control
is a slider + numeric spinbox pair so the operator can either drag for
visual feedback or type a precise value. Per-section reset buttons + a
global Reset button.

Operator-facing only; LLM agents drive the same set_frame_* / reset_frame
commands directly via the dispatcher.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..app import App

# Slider integer ranges (sliders are int-only; we map 100x for scale).
SCALE_SLIDER_MIN = 30   # 0.30x
SCALE_SLIDER_MAX = 200  # 2.00x
SCALE_DEFAULT = 100     # 1.00x
OFFSET_RANGE = 2048


class ReframerPane(QWidget):
    """Frame scale + offset + anchor controls.

    Signals fire on user interaction (operator dragged a slider OR typed in a
    spinbox). Programmatic state sync via load_frame() blocks the signals.
    """

    frame_scale_changed = Signal(float)
    frame_offset_changed = Signal(int, int)
    frame_anchor_changed = Signal(str)
    frame_reset_clicked = Signal()
    # Per-section reset signals — main_window dispatches the right command.
    reset_scale_clicked = Signal()
    reset_offset_clicked = Signal()
    reset_anchor_clicked = Signal()

    def __init__(self, app: "App") -> None:
        super().__init__()
        self._app = app
        self._suppress = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        hint = QLabel(
            "frame controls scale + offset the wireframe within the canvas. "
            "line widths stay constant. live preview updates immediately."
        )
        hint.setObjectName("inspector-key")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Scale row.
        layout.addWidget(QLabel("Scale"))
        scale_row = QHBoxLayout()
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setMinimum(SCALE_SLIDER_MIN)
        self.scale_slider.setMaximum(SCALE_SLIDER_MAX)
        self.scale_slider.setValue(SCALE_DEFAULT)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.30, 2.00)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setDecimals(2)
        self.scale_spin.setValue(1.00)
        self.btn_reset_scale = QPushButton("Reset")
        scale_row.addWidget(self.scale_slider, 1)
        scale_row.addWidget(self.scale_spin)
        scale_row.addWidget(self.btn_reset_scale)
        layout.addLayout(scale_row)

        # Offset X row.
        layout.addWidget(QLabel("Offset X (pixels)"))
        ox_row = QHBoxLayout()
        self.offset_x_slider = QSlider(Qt.Orientation.Horizontal)
        self.offset_x_slider.setMinimum(-OFFSET_RANGE)
        self.offset_x_slider.setMaximum(OFFSET_RANGE)
        self.offset_x_slider.setValue(0)
        self.offset_x_spin = QSpinBox()
        self.offset_x_spin.setRange(-OFFSET_RANGE, OFFSET_RANGE)
        self.offset_x_spin.setValue(0)
        self.btn_reset_offset = QPushButton("Reset XY")
        ox_row.addWidget(self.offset_x_slider, 1)
        ox_row.addWidget(self.offset_x_spin)
        ox_row.addWidget(self.btn_reset_offset)
        layout.addLayout(ox_row)

        # Offset Y row (no per-row reset; Reset XY above clears both).
        layout.addWidget(QLabel("Offset Y (pixels)"))
        oy_row = QHBoxLayout()
        self.offset_y_slider = QSlider(Qt.Orientation.Horizontal)
        self.offset_y_slider.setMinimum(-OFFSET_RANGE)
        self.offset_y_slider.setMaximum(OFFSET_RANGE)
        self.offset_y_slider.setValue(0)
        self.offset_y_spin = QSpinBox()
        self.offset_y_spin.setRange(-OFFSET_RANGE, OFFSET_RANGE)
        self.offset_y_spin.setValue(0)
        oy_row.addWidget(self.offset_y_slider, 1)
        oy_row.addWidget(self.offset_y_spin)
        oy_row.addStretch(1)
        layout.addLayout(oy_row)

        # Anchor row.
        anchor_row = QHBoxLayout()
        anchor_row.addWidget(QLabel("Anchor"))
        self.anchor_combo = QComboBox()
        self.anchor_combo.addItems(["head_anchor", "canvas_center"])
        self.btn_reset_anchor = QPushButton("Reset")
        anchor_row.addWidget(self.anchor_combo, 1)
        anchor_row.addWidget(self.btn_reset_anchor)
        layout.addLayout(anchor_row)

        # Global reset.
        layout.addSpacing(8)
        self.btn_reset_all = QPushButton("Reset frame (all)")
        layout.addWidget(self.btn_reset_all)
        layout.addStretch(1)

        # Wire slider <-> spinbox bidirectional binding (programmatic sync
        # blocks signals so we don't double-fire).
        self.scale_slider.valueChanged.connect(self._on_scale_slider)
        self.scale_spin.valueChanged.connect(self._on_scale_spin)
        self.offset_x_slider.valueChanged.connect(self._on_offset_x_slider)
        self.offset_x_spin.valueChanged.connect(self._on_offset_x_spin)
        self.offset_y_slider.valueChanged.connect(self._on_offset_y_slider)
        self.offset_y_spin.valueChanged.connect(self._on_offset_y_spin)
        self.anchor_combo.currentTextChanged.connect(
            self._on_anchor_changed
        )

        self.btn_reset_scale.clicked.connect(self.reset_scale_clicked.emit)
        self.btn_reset_offset.clicked.connect(self.reset_offset_clicked.emit)
        self.btn_reset_anchor.clicked.connect(self.reset_anchor_clicked.emit)
        self.btn_reset_all.clicked.connect(self.frame_reset_clicked.emit)

    # --- public sync path -----------------------------------------------

    def load_frame(self, frame: dict) -> None:  # noqa: ANN001
        """Sync controls from state.frame without firing signals."""
        self._suppress = True
        try:
            scale_int = int(round(float(frame.get("scale", 1.0)) * 100))
            scale_int = max(SCALE_SLIDER_MIN, min(SCALE_SLIDER_MAX, scale_int))
            self.scale_slider.blockSignals(True)
            self.scale_slider.setValue(scale_int)
            self.scale_slider.blockSignals(False)
            self.scale_spin.blockSignals(True)
            self.scale_spin.setValue(scale_int / 100.0)
            self.scale_spin.blockSignals(False)

            ox = int(frame.get("offset_x", 0))
            oy = int(frame.get("offset_y", 0))
            for w, v in (
                (self.offset_x_slider, ox),
                (self.offset_x_spin, ox),
                (self.offset_y_slider, oy),
                (self.offset_y_spin, oy),
            ):
                w.blockSignals(True)
                w.setValue(v)
                w.blockSignals(False)

            mode = frame.get("anchor_mode", "head_anchor")
            if mode in ("head_anchor", "canvas_center"):
                self.anchor_combo.blockSignals(True)
                self.anchor_combo.setCurrentText(mode)
                self.anchor_combo.blockSignals(False)
        finally:
            self._suppress = False

    # --- internal handlers ---------------------------------------------

    def _on_scale_slider(self, value: int) -> None:
        if self._suppress:
            return
        self._suppress = True
        try:
            self.scale_spin.setValue(value / 100.0)
        finally:
            self._suppress = False
        self.frame_scale_changed.emit(value / 100.0)

    def _on_scale_spin(self, value: float) -> None:
        if self._suppress:
            return
        self._suppress = True
        try:
            self.scale_slider.setValue(int(round(value * 100)))
        finally:
            self._suppress = False
        self.frame_scale_changed.emit(float(value))

    def _on_offset_x_slider(self, value: int) -> None:
        if self._suppress:
            return
        self._suppress = True
        try:
            self.offset_x_spin.setValue(value)
        finally:
            self._suppress = False
        self.frame_offset_changed.emit(value, self.offset_y_spin.value())

    def _on_offset_x_spin(self, value: int) -> None:
        if self._suppress:
            return
        self._suppress = True
        try:
            self.offset_x_slider.setValue(value)
        finally:
            self._suppress = False
        self.frame_offset_changed.emit(value, self.offset_y_spin.value())

    def _on_offset_y_slider(self, value: int) -> None:
        if self._suppress:
            return
        self._suppress = True
        try:
            self.offset_y_spin.setValue(value)
        finally:
            self._suppress = False
        self.frame_offset_changed.emit(self.offset_x_spin.value(), value)

    def _on_offset_y_spin(self, value: int) -> None:
        if self._suppress:
            return
        self._suppress = True
        try:
            self.offset_y_slider.setValue(value)
        finally:
            self._suppress = False
        self.frame_offset_changed.emit(self.offset_x_spin.value(), value)

    def _on_anchor_changed(self, mode: str) -> None:
        if self._suppress:
            return
        self.frame_anchor_changed.emit(str(mode))
