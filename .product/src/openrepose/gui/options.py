"""Options tab. Operator-set configuration: export folder root + subdir
templates, avatar slug, log level, channel toggles."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class OptionsPane(QWidget):
    """Form-style options pane wired to operator settings persistence
    (WP-I1-027). The Apply button persists changes to disk via the App's
    Settings instance."""

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

        # Export folder root with Browse... button. Empty = use default
        # (~/Desktop/openrepose-output/).
        self.export_folder_edit = QLineEdit()
        self.export_folder_edit.setPlaceholderText(
            "blank = ~/Desktop/openrepose-output/"
        )
        self.btn_browse_export = QPushButton("Browse...")
        self.btn_browse_export.clicked.connect(self._on_browse_export)
        export_row = QHBoxLayout()
        export_row.addWidget(self.export_folder_edit, 1)
        export_row.addWidget(self.btn_browse_export)
        form.addRow(QLabel("Export folder root"), self._wrap_row(export_row))

        # Subdir templates ({avatar} and {run_tag} placeholders supported).
        self.single_export_edit = QLineEdit()
        self.single_export_edit.setText("{avatar}")
        form.addRow(QLabel("Single export subdir"), self.single_export_edit)

        self.batch_export_edit = QLineEdit()
        self.batch_export_edit.setText("{avatar}/{run_tag}")
        form.addRow(QLabel("Batch export subdir"), self.batch_export_edit)

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
                "export_folder": self.export_folder_edit.text().strip(),
                "single_export_subdir_template": self.single_export_edit.text().strip(),
                "batch_export_subdir_template": self.batch_export_edit.text().strip(),
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

    def _on_browse_export(self) -> None:
        """Open a folder picker. Triggered only by operator click on the
        Browse... button — never by an LLM-driven path."""
        current = self.export_folder_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select export folder root",
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if chosen:
            self.export_folder_edit.setText(chosen)

    def load_from_settings(self, settings) -> None:  # noqa: ANN001
        """Populate the form from a Settings instance."""
        self.export_folder_edit.setText(str(settings.export_folder or ""))
        self.single_export_edit.setText(settings.single_export_subdir_template)
        self.batch_export_edit.setText(settings.batch_export_subdir_template)
