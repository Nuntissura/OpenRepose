"""Options tab. Operator-set configuration: export folders, avatar slug,
log level, channel toggles. v0.1 keeps it concrete and dense."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class OptionsPane(QWidget):
    """Pure form-style options pane; v0.1 has no persistence yet (settings
    survive only for the running session). Persistence ships in a polish WP."""

    settings_changed = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)

        self.avatar_slug_edit = QLineEdit()
        self.avatar_slug_edit.setPlaceholderText("e.g. aeri")
        form.addRow(QLabel("Avatar slug"), self.avatar_slug_edit)

        self.run_tag_edit = QLineEdit()
        self.run_tag_edit.setPlaceholderText("e.g. 2026-05-02_run01 (auto if blank)")
        form.addRow(QLabel("Run tag"), self.run_tag_edit)

        # Single export folder (operator can use {avatar} and {run_tag} placeholders).
        self.single_export_edit = QLineEdit()
        self.single_export_edit.setText("outputs/{avatar}/")
        form.addRow(QLabel("Single export folder"), self.single_export_edit)

        self.batch_export_edit = QLineEdit()
        self.batch_export_edit.setText("outputs/{avatar}/{run_tag}/")
        form.addRow(QLabel("Batch export folder"), self.batch_export_edit)

        self.angles_edit = QLineEdit()
        self.angles_edit.setPlaceholderText("comma-separated; blank = standard 13")
        form.addRow(QLabel("Default batch angles"), self.angles_edit)

        # Projection mode.
        self.proj_combo = QComboBox()
        self.proj_combo.addItems(["orthographic", "perspective"])
        form.addRow(QLabel("Projection mode"), self.proj_combo)

        self.focal_edit = QLineEdit("1024")
        form.addRow(QLabel("Focal length (perspective)"), self.focal_edit)

        # Output canvas mode.
        self.canvas_match_check = QCheckBox("Match input portrait dimensions")
        self.canvas_match_check.setChecked(True)
        form.addRow(QLabel("Output canvas"), self.canvas_match_check)

        # OpenPose schema (read-only label).
        schema_label = QLabel("body_18 + face_70 + hands_off (locked for v0.1)")
        form.addRow(QLabel("OpenPose schema"), schema_label)

        # LLM control surface toggles.
        self.http_check = QCheckBox("Enable HTTP localhost channel")
        self.http_port_edit = QLineEdit("8765")
        http_row = QHBoxLayout()
        http_row.addWidget(self.http_check)
        http_row.addWidget(QLabel("port"))
        http_row.addWidget(self.http_port_edit)
        form.addRow(QLabel("LLM HTTP channel"), self._wrap_row(http_row))

        self.inbox_check = QCheckBox("Enable file-watch inbox at outputs/.runtime/inbox/")
        form.addRow(QLabel("LLM file-watch inbox"), self.inbox_check)

        # Log level filter.
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DBG", "OK", "WARN", "ERR"])
        self.log_level_combo.setCurrentText("OK")
        form.addRow(QLabel("Log level filter"), self.log_level_combo)

        # Clean outputs on close.
        self.clean_on_close_check = QCheckBox("Clean outputs/ on close")
        form.addRow(QLabel("Cleanup"), self.clean_on_close_check)

        layout.addLayout(form)
        layout.addSpacing(8)
        self.btn_apply = QPushButton("Apply settings")
        self.btn_apply.clicked.connect(self._on_apply)
        layout.addWidget(self.btn_apply)
        layout.addStretch(1)

    def _wrap_row(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _on_apply(self) -> None:
        self.settings_changed.emit(
            {
                "avatar_slug": self.avatar_slug_edit.text().strip(),
                "run_tag": self.run_tag_edit.text().strip(),
                "single_export_folder": self.single_export_edit.text().strip(),
                "batch_export_folder": self.batch_export_edit.text().strip(),
                "angles": self.angles_edit.text().strip(),
                "projection_mode": self.proj_combo.currentText(),
                "focal_length": self.focal_edit.text().strip(),
                "canvas_match_input": self.canvas_match_check.isChecked(),
                "http_enabled": self.http_check.isChecked(),
                "http_port": self.http_port_edit.text().strip(),
                "inbox_enabled": self.inbox_check.isChecked(),
                "log_level": self.log_level_combo.currentText(),
                "clean_on_close": self.clean_on_close_check.isChecked(),
            }
        )
