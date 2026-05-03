"""Operator-facing Markers tab — per-keypoint visibility toggles.

Spec: WP-I1-029. Per-marker overrides are layered on top of WP-I1-017
group flags with documented precedence (per-marker is authoritative).

Tab is operator-facing only; LLM agents use `set_marker_visibility`,
`get_marker_visibility`, and `reset_marker_visibility` commands directly.
No focus-stealing API calls; no modal dialogs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..openpose_schema import OPENPOSE_BODY_COUNT, OPENPOSE_FACE_COUNT
from ..render.draw_openpose import BODY_18_COLOR_BY_INDEX

if TYPE_CHECKING:
    from ..app import App

# Body_18 anatomical labels (from openpose_schema.py docstring).
BODY_18_NAMES: tuple[str, ...] = (
    "nose",
    "neck",
    "right_shoulder",
    "right_elbow",
    "right_wrist",
    "left_shoulder",
    "left_elbow",
    "left_wrist",
    "right_hip",
    "right_knee",
    "right_ankle",
    "left_hip",
    "left_knee",
    "left_ankle",
    "right_eye",
    "left_eye",
    "right_ear",
    "left_ear",
)

# Face_70 region labels (start_index, end_index_exclusive, label).
FACE_70_REGIONS: tuple[tuple[int, int, str], ...] = (
    (0, 17, "jaw outline"),
    (17, 22, "right brow"),
    (22, 27, "left brow"),
    (27, 31, "nose bridge"),
    (31, 36, "nose bottom"),
    (36, 42, "right eye"),
    (42, 48, "left eye"),
    (48, 60, "outer mouth"),
    (60, 68, "inner mouth"),
    (68, 70, "pupils"),
)


class MarkersPane(QWidget):
    """Two-section list of all OpenPose markers with checkable items.

    Toggle a checkbox -> dispatch set_marker_visibility immediately. Reset
    button -> dispatch reset_marker_visibility.
    """

    def __init__(self, app: "App") -> None:
        super().__init__()
        self._app = app
        self._suppress_signals = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hint = QLabel(
            "uncheck to suppress that single keypoint in exports + preview. "
            "per-marker overrides body-part group flags."
        )
        hint.setObjectName("inspector-key")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        tabs = QTabWidget()
        self._body_list = self._build_body_list()
        self._face_list = self._build_face_list()
        tabs.addTab(self._body_list, "body_18")
        tabs.addTab(self._face_list, "face_70")
        layout.addWidget(tabs, 1)

        btn_row = QHBoxLayout()
        self.btn_reset = QPushButton("Reset all (show every marker)")
        self.btn_reset.clicked.connect(self._on_reset)
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Connect after population so initial setChecked doesn't fire.
        self._body_list.itemChanged.connect(self._on_body_item_changed)
        self._face_list.itemChanged.connect(self._on_face_item_changed)

    # --- public update path ----------------------------------------------

    def refresh(self) -> None:
        """Sync checkbox state from app.state.marker_visibility."""
        mv = self._app.state.marker_visibility
        body_overrides = mv.get("body_18", {})
        face_overrides = mv.get("face_70", {})
        self._suppress_signals = True
        try:
            for i in range(OPENPOSE_BODY_COUNT):
                item = self._body_list.item(i)
                desired = body_overrides.get(str(i), True)
                state = (
                    Qt.CheckState.Checked
                    if desired
                    else Qt.CheckState.Unchecked
                )
                if item.checkState() != state:
                    item.setCheckState(state)
            for i in range(OPENPOSE_FACE_COUNT):
                item = self._face_list.item(i)
                desired = face_overrides.get(str(i), True)
                state = (
                    Qt.CheckState.Checked
                    if desired
                    else Qt.CheckState.Unchecked
                )
                if item.checkState() != state:
                    item.setCheckState(state)
        finally:
            self._suppress_signals = False

    # --- builders --------------------------------------------------------

    def _build_body_list(self) -> QListWidget:
        lw = QListWidget()
        for i in range(OPENPOSE_BODY_COUNT):
            name = BODY_18_NAMES[i] if i < len(BODY_18_NAMES) else f"index {i}"
            item = QListWidgetItem(f"{i:>2d}  {name}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            # WP-I1-032: color the row text to match the OpenPose limb color
            # so the operator can match a Markers row to the colored skeleton
            # in the live preview. BODY_18_COLOR_BY_INDEX is BGR; QColor takes
            # RGB.
            b, g, r = BODY_18_COLOR_BY_INDEX[i]
            item.setForeground(QBrush(QColor(r, g, b)))
            lw.addItem(item)
        return lw

    def _build_face_list(self) -> QListWidget:
        lw = QListWidget()
        # Pre-build a quick label lookup.
        region_label_by_idx: dict[int, str] = {}
        for start, end, label in FACE_70_REGIONS:
            for i in range(start, end):
                region_label_by_idx[i] = label
        for i in range(OPENPOSE_FACE_COUNT):
            label = region_label_by_idx.get(i, "?")
            item = QListWidgetItem(f"{i:>2d}  {label}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            lw.addItem(item)
        return lw

    # --- handlers --------------------------------------------------------

    def _on_body_item_changed(self, item: QListWidgetItem) -> None:
        if self._suppress_signals:
            return
        idx = self._body_list.row(item)
        visible = item.checkState() == Qt.CheckState.Checked
        self._app.handle_command(
            {
                "command": "set_marker_visibility",
                "schema": "body_18",
                "index": idx,
                "visible": visible,
            }
        )

    def _on_face_item_changed(self, item: QListWidgetItem) -> None:
        if self._suppress_signals:
            return
        idx = self._face_list.row(item)
        visible = item.checkState() == Qt.CheckState.Checked
        self._app.handle_command(
            {
                "command": "set_marker_visibility",
                "schema": "face_70",
                "index": idx,
                "visible": visible,
            }
        )

    def _on_reset(self) -> None:
        self._app.handle_command({"command": "reset_marker_visibility"})
        self.refresh()
