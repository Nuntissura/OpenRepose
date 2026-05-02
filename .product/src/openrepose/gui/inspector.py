"""Inspector pane: read-only key/value readouts of the current app state."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..state import AppState


class InspectorPane(QWidget):
    """Live readouts driven by AppState. Polled / refreshed on each state
    change broadcast."""

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(2)

        self._fields: dict[str, QLabel] = {}
        for key in (
            "yaw_bin",
            "yaw_value",
            "axis",
            "rig_status",
            "fit_duration_ms",
            "face_landmarks",
            "body_landmarks",
            "canvas",
            "exports",
            "snapshots",
            "errors",
        ):
            value_label = QLabel("-")
            value_label.setObjectName("inspector-value")
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            key_label = QLabel(key)
            key_label.setObjectName("inspector-key")
            form.addRow(key_label, value_label)
            self._fields[key] = value_label

        layout.addLayout(form)
        layout.addSpacing(8)

        # Action buttons (each one issues a command to the dispatcher; the
        # dispatcher handles the work, the GUI does not).
        self.btn_run_format_check = QPushButton("Run format check")
        self.btn_render_single = QPushButton("Render single")
        self.btn_snapshot_3d = QPushButton("Snapshot 3D viewport")
        self.btn_snapshot_openpose = QPushButton("Snapshot OpenPose preview")
        self.btn_snapshot_full = QPushButton("Snapshot full window")
        self.btn_dump_rig = QPushButton("Dump rig")
        for btn in (
            self.btn_run_format_check,
            self.btn_render_single,
            self.btn_snapshot_3d,
            self.btn_snapshot_openpose,
            self.btn_snapshot_full,
            self.btn_dump_rig,
        ):
            layout.addWidget(btn)

        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        s = self._state.to_dict()
        rig = s["rig"]
        yaw = s["yaw"]
        self._fields["yaw_bin"].setText(yaw.get("current_bin") or "-")
        self._fields["yaw_value"].setText(f"{yaw.get('current_value_deg', 0.0):+.1f}°")
        self._fields["axis"].setText(yaw.get("axis") or "-")
        self._fields["rig_status"].setText(rig.get("status") or "-")
        self._fields["fit_duration_ms"].setText(str(rig.get("fit_duration_ms", 0)) + " ms")
        self._fields["face_landmarks"].setText(str(rig.get("face_landmark_count", 0)))
        self._fields["body_landmarks"].setText(str(rig.get("body_landmark_count", 0)))
        self._fields["canvas"].setText("-")  # populated by main_window once rig exists
        self._fields["exports"].setText(str(len(s.get("exports", []))))
        self._fields["snapshots"].setText(str(len(s.get("snapshots", []))))
        self._fields["errors"].setText(str(len(s.get("errors", []))))

    def set_canvas(self, w: int, h: int) -> None:
        self._fields["canvas"].setText(f"{w} x {h}")
