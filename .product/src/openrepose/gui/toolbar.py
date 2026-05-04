"""Top toolbar: file actions, yaw bin dropdown, yaw slider, direction arrow,
export buttons."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QToolBar,
    QWidget,
)

from ..yaw_bin import direction_arrow, parse_bin, signed_deg_to_bin, standard_13_angle_bins


class Toolbar(QToolBar):
    """Top toolbar.

    Signals (all emit user-driven changes; programmatic state changes use
    setters that block signals).
    """

    open_clicked = Signal()
    clear_workspace_clicked = Signal()   # WP-I1-016
    reload_clicked = Signal()
    yaw_bin_changed = Signal(str)        # new bin label
    yaw_value_changed = Signal(float)    # new degree value (slider drag)
    export_single_clicked = Signal()
    export_batch_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMovable(False)
        self.setIconSize(self.iconSize())  # keep default

        # Open / Clear / Reload. WP-I1-016 placed Clear immediately next
        # to Open (operator request) so the destructive workspace action
        # sits visually paired with its constructive sibling.
        btn_open = QPushButton("Open")
        btn_open.clicked.connect(self.open_clicked.emit)
        self.addWidget(btn_open)

        self.btn_clear_workspace = QPushButton("Clear workspace")
        self.btn_clear_workspace.setToolTip(
            "Drop the active document's rig, reset yaw to 0, blank the "
            "viewports. Settings, log, and other documents are untouched."
        )
        self.btn_clear_workspace.clicked.connect(
            self.clear_workspace_clicked.emit
        )
        self.addWidget(self.btn_clear_workspace)

        btn_reload = QPushButton("Reload")
        btn_reload.clicked.connect(self.reload_clicked.emit)
        self.addWidget(btn_reload)

        self.addSeparator()

        # Yaw bin dropdown.
        self.bin_combo = QComboBox()
        for label in standard_13_angle_bins():
            self.bin_combo.addItem(label)
        self.bin_combo.currentTextChanged.connect(self._on_bin_changed)
        self.addWidget(QLabel("yaw_bin"))
        self.addWidget(self.bin_combo)

        # Yaw slider (-90 .. +90, integer degrees).
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(-90)
        self.slider.setMaximum(90)
        self.slider.setValue(0)
        self.slider.setMinimumWidth(260)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.addWidget(self.slider)

        # Live yaw readout + direction arrow.
        self.value_label = QLabel("  0°")
        self.value_label.setMinimumWidth(60)
        self.value_label.setObjectName("inspector-value")
        self.addWidget(self.value_label)

        self.arrow_label = QLabel(" ")
        self.arrow_label.setMinimumWidth(28)
        self.arrow_label.setObjectName("inspector-value")
        self.addWidget(self.arrow_label)

        self.addSeparator()

        btn_export_single = QPushButton("Export single")
        btn_export_single.clicked.connect(self.export_single_clicked.emit)
        self.addWidget(btn_export_single)

        btn_export_batch = QPushButton("Export batch (13)")
        btn_export_batch.clicked.connect(self.export_batch_clicked.emit)
        self.addWidget(btn_export_batch)

        self._suppress_emit = False

    # --- signal-emitting handlers ---------------------------------------

    def _on_bin_changed(self, label: str) -> None:
        if self._suppress_emit:
            return
        self.yaw_bin_changed.emit(label)
        # Sync slider to bin value.
        bin_obj = parse_bin(label)
        self._suppress_emit = True
        try:
            self.slider.setValue(int(round(bin_obj.signed_deg)))
            self.value_label.setText(f"{int(round(bin_obj.signed_deg)):+4d}°")
            self.arrow_label.setText(direction_arrow(bin_obj))
        finally:
            self._suppress_emit = False

    def _on_slider_changed(self, value: int) -> None:
        if self._suppress_emit:
            return
        self.value_label.setText(f"{value:+4d}°")
        self.arrow_label.setText(direction_arrow(float(value)))
        self.yaw_value_changed.emit(float(value))

    # --- programmatic setters (don't emit) ------------------------------

    def set_state(self, value_deg: float, bin_label: str) -> None:
        self._suppress_emit = True
        try:
            self.slider.setValue(int(round(value_deg)))
            self.value_label.setText(f"{int(round(value_deg)):+4d}°")
            self.arrow_label.setText(direction_arrow(value_deg))
            idx = self.bin_combo.findText(bin_label)
            if idx >= 0:
                self.bin_combo.setCurrentIndex(idx)
        finally:
            self._suppress_emit = False
