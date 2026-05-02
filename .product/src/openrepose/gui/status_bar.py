"""Bottom status bar: live mechanical readouts."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar

from ..state import AppState


class StatusBar(QStatusBar):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state
        self._label = QLabel(self._format())
        self.addWidget(self._label, 1)

    def refresh(self) -> None:
        self._label.setText(self._format())

    def _format(self) -> str:
        s = self._state.to_dict()
        rig_status = s["rig"]["status"]
        yaw_bin = s["yaw"]["current_bin"]
        yaw_deg = s["yaw"]["current_value_deg"]
        last_export_at = (
            s["exports"][-1]["completed_at"] if s["exports"] else "-"
        )
        last_export_short = last_export_at.split("T")[1][:8] if "T" in last_export_at else last_export_at
        errors_n = len(s["errors"])
        return (
            f"status: rig={rig_status} | yaw={yaw_bin} ({yaw_deg:+.1f}°) | "
            f"last_export={last_export_short} | errors={errors_n}"
        )
