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
    frame_scale_changed = Signal(float)
    frame_offset_changed = Signal(int, int)
    frame_anchor_changed = Signal(str)
    frame_reset_clicked = Signal()
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

        # Frame reframing (WP-I1-023). Scale slider + offset spinboxes +
        # anchor mode dropdown + reset button. Each control fires its own
        # signal immediately; main_window dispatches the matching command.
        self.frame_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_scale_slider.setMinimum(30)   # represents 0.30x
        self.frame_scale_slider.setMaximum(200)  # represents 2.00x
        self.frame_scale_slider.setValue(100)    # 1.00x
        self.frame_scale_slider.valueChanged.connect(
            lambda v: self.frame_scale_changed.emit(v / 100.0)
        )
        self.frame_scale_label = QLabel("scale 1.00x")
        self.frame_scale_label.setObjectName("inspector-value")
        self.frame_scale_slider.valueChanged.connect(
            lambda v: self.frame_scale_label.setText(f"scale {v / 100.0:.2f}x")
        )
        scale_row = QHBoxLayout()
        scale_row.addWidget(self.frame_scale_slider, 1)
        scale_row.addWidget(self.frame_scale_label)
        form.addRow(QLabel("Frame scale"), self._wrap_row(scale_row))

        self.frame_offset_x = QSpinBox()
        self.frame_offset_x.setRange(-2048, 2048)
        self.frame_offset_x.setValue(0)
        self.frame_offset_y = QSpinBox()
        self.frame_offset_y.setRange(-2048, 2048)
        self.frame_offset_y.setValue(0)

        def _on_offset_changed(_v=None):
            self.frame_offset_changed.emit(
                self.frame_offset_x.value(), self.frame_offset_y.value()
            )

        self.frame_offset_x.valueChanged.connect(_on_offset_changed)
        self.frame_offset_y.valueChanged.connect(_on_offset_changed)
        offset_row = QHBoxLayout()
        offset_row.addWidget(QLabel("x"))
        offset_row.addWidget(self.frame_offset_x)
        offset_row.addWidget(QLabel("y"))
        offset_row.addWidget(self.frame_offset_y)
        offset_row.addStretch(1)
        form.addRow(QLabel("Frame offset (px)"), self._wrap_row(offset_row))

        self.frame_anchor_combo = QComboBox()
        self.frame_anchor_combo.addItems(["head_anchor", "canvas_center"])
        self.frame_anchor_combo.currentTextChanged.connect(
            self.frame_anchor_changed.emit
        )
        anchor_row = QHBoxLayout()
        anchor_row.addWidget(self.frame_anchor_combo, 1)
        self.btn_frame_reset = QPushButton("Reset frame")
        self.btn_frame_reset.clicked.connect(self.frame_reset_clicked.emit)
        anchor_row.addWidget(self.btn_frame_reset)
        form.addRow(QLabel("Frame anchor"), self._wrap_row(anchor_row))

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

    def load_frame(self, frame: dict) -> None:  # noqa: ANN001
        """Sync frame controls from state without firing signals."""
        scale_int = int(round(float(frame.get("scale", 1.0)) * 100))
        scale_int = max(30, min(200, scale_int))
        self.frame_scale_slider.blockSignals(True)
        self.frame_scale_slider.setValue(scale_int)
        self.frame_scale_label.setText(f"scale {scale_int / 100.0:.2f}x")
        self.frame_scale_slider.blockSignals(False)
        self.frame_offset_x.blockSignals(True)
        self.frame_offset_x.setValue(int(frame.get("offset_x", 0)))
        self.frame_offset_x.blockSignals(False)
        self.frame_offset_y.blockSignals(True)
        self.frame_offset_y.setValue(int(frame.get("offset_y", 0)))
        self.frame_offset_y.blockSignals(False)
        mode = frame.get("anchor_mode", "head_anchor")
        if mode in ("head_anchor", "canvas_center"):
            self.frame_anchor_combo.blockSignals(True)
            self.frame_anchor_combo.setCurrentText(mode)
            self.frame_anchor_combo.blockSignals(False)
