"""Options tab. Operator-set configuration: export folder root + subdir
templates, avatar slug, log level, channel toggles."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class OptionsPane(QWidget):
    """Form-style options pane wired to operator settings persistence
    (WP-I1-027). The Apply button persists changes to disk via the App's
    Settings instance."""

    settings_changed = Signal(dict)
    body_part_visibility_changed = Signal(str, bool)
    canvas_border_color_changed = Signal(str)

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

        # Canvas border (WP-I1-032). Visible outline drawn on the OpenPose
        # canvas perimeter so the operator can see the export bounds even
        # when frame_scale shrinks the figure away from the edges.
        from PySide6.QtGui import QColor

        self._canvas_border_color = "#ffffff"
        self.btn_canvas_border = QPushButton("Pick color...")
        self.canvas_border_swatch = QLabel("    ")
        self.canvas_border_swatch.setFixedWidth(40)
        self.canvas_border_swatch.setStyleSheet(
            f"background-color: {self._canvas_border_color}; border: 1px solid #444;"
        )
        self.btn_canvas_border.clicked.connect(self._on_pick_canvas_border)
        border_row = QHBoxLayout()
        border_row.addWidget(self.canvas_border_swatch)
        border_row.addWidget(self.btn_canvas_border)
        border_row.addStretch(1)
        form.addRow(QLabel("Canvas border"), self._wrap_row(border_row))

        # Frame controls live in the Tools tab → Reframer sub-pane (WP-I1-031).

        # Per-body-part visibility (WP-I1-017). Each checkbox fires
        # set_body_part_visibility immediately on toggle.
        self.body_part_checks: dict[str, QCheckBox] = {}
        bpv_row = QHBoxLayout()
        for group in ("face", "body_torso", "arms", "legs", "hands"):
            cb = QCheckBox(group)
            cb.setChecked(True)
            cb.toggled.connect(
                lambda checked, g=group: self.body_part_visibility_changed.emit(
                    g, bool(checked)
                )
            )
            self.body_part_checks[group] = cb
            bpv_row.addWidget(cb)
        bpv_row.addStretch(1)
        form.addRow(QLabel("Body part visibility"), self._wrap_row(bpv_row))

        # Library configuration (WP-I2-002). Empty `library_db_url` keeps
        # the library subsystem dormant; the rest of the app continues to
        # work. `library_root` blank resolves to <export_folder>/library/.
        # `operator_slug` blank resolves to the OS username at runtime.
        self.library_db_url_edit = QLineEdit()
        self.library_db_url_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.library_db_url_edit.setPlaceholderText(
            "blank = library disabled (no DB connection)"
        )
        self.library_db_url_edit.setToolTip(
            "PostgreSQL DSN, e.g. postgresql://user:pass@localhost:5432/openrepose"
        )
        form.addRow(QLabel("Library DB URL"), self.library_db_url_edit)

        self.library_root_edit = QLineEdit()
        self.library_root_edit.setPlaceholderText("blank = <export_folder>/library/")
        self.btn_browse_library = QPushButton("Browse...")
        self.btn_browse_library.clicked.connect(self._on_browse_library_root)
        lib_row = QHBoxLayout()
        lib_row.addWidget(self.library_root_edit, 1)
        lib_row.addWidget(self.btn_browse_library)
        form.addRow(QLabel("Library root"), self._wrap_row(lib_row))

        self.operator_slug_edit = QLineEdit()
        self.operator_slug_edit.setPlaceholderText("blank = OS username")
        form.addRow(QLabel("Operator slug"), self.operator_slug_edit)

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
                "library_db_url": self.library_db_url_edit.text().strip(),
                "library_root": self.library_root_edit.text().strip(),
                "operator_slug": self.operator_slug_edit.text().strip(),
                "http_enabled": self.http_check.isChecked(),
                "http_port": self.http_port_edit.text().strip(),
                "inbox_enabled": self.inbox_check.isChecked(),
                "log_level": self.log_level_combo.currentText(),
                "clean_on_close": self.clean_on_close_check.isChecked(),
            }
        )

    def _on_browse_library_root(self) -> None:
        """Operator-triggered folder picker for the library root. Never
        fired by an LLM-driven path (no command surface entry exists for
        opening file dialogs)."""
        current = self.library_root_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select library root folder",
            current,
            QFileDialog.Option.ShowDirsOnly,
        )
        if chosen:
            self.library_root_edit.setText(chosen)

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
        self.library_db_url_edit.setText(str(getattr(settings, "library_db_url", "") or ""))
        self.library_root_edit.setText(str(getattr(settings, "library_root", "") or ""))
        self.operator_slug_edit.setText(str(getattr(settings, "operator_slug", "") or ""))

    def load_body_part_visibility(self, bpv: dict) -> None:  # noqa: ANN001
        """Sync checkboxes from state without firing the toggled signal."""
        for group, cb in self.body_part_checks.items():
            cb.blockSignals(True)
            cb.setChecked(bool(bpv.get(group, True)))
            cb.blockSignals(False)

    def load_canvas_border_color(self, color: str) -> None:
        """Sync the swatch + cached color from a Settings instance."""
        self._canvas_border_color = color or "#ffffff"
        self.canvas_border_swatch.setStyleSheet(
            f"background-color: {self._canvas_border_color}; border: 1px solid #444;"
        )

    def _on_pick_canvas_border(self) -> None:
        """Open QColorDialog (operator-triggered only). Emits new color."""
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog

        initial = QColor(self._canvas_border_color or "#ffffff")
        chosen = QColorDialog.getColor(
            initial, self, "Pick canvas border color"
        )
        if not chosen.isValid():
            return
        hex_str = chosen.name()  # "#rrggbb"
        self.load_canvas_border_color(hex_str)
        self.canvas_border_color_changed.emit(hex_str)

    # Frame controls moved to ReframerPane in WP-I1-031; load_frame / signal
    # set live there now.
