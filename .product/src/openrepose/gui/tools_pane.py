"""Tools tab — wraps Calibration / Markers / Reframer in sub-tabs.

Spec: WP-I1-031 dock layout reorganization. Operator's editing tools are
grouped under one top-level Tools tab; Inspector / Options / Log / Help
remain top-level alongside.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .calibration import CalibrationPane
from .markers import MarkersPane
from .reframer import ReframerPane

if TYPE_CHECKING:
    from ..app import App


class ToolsPane(QWidget):
    """Container for the three operator editing tools."""

    def __init__(self, app: "App") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self.calibration = CalibrationPane(app)
        self.markers = MarkersPane(app)
        self.reframer = ReframerPane(app)
        self._tabs.addTab(self.calibration, "Calibration")
        self._tabs.addTab(self.markers, "Markers")
        self._tabs.addTab(self.reframer, "Reframer")
