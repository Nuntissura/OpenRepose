"""OpenRepose main window. Wires toolbar, two viewports, tabbed dock, status
bar, and the snapshot-subsystem widget provider so the GUI's widgets are
grabbable by an LLM agent without operator focus theft.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QWidget,
)

from ..app import App
from ..render.widget_grab import set_widget_provider
from ..rotation import rotate_yaw
from ..yaw_bin import parse_bin, signed_deg_to_bin, standard_13_angle_bins
from .calibration import CalibrationPane
from .help_pane import HelpPane
from .inspector import InspectorPane
from .log_pane import LogPane
from .markers import MarkersPane
from .options import OptionsPane
from .status_bar import StatusBar
from .style import DARK_QSS
from .toolbar import Toolbar
from .viewport_3d import Viewport3D
from .viewport_openpose import ViewportOpenPose


class MainWindow(QMainWindow):
    """Operator-facing main window. The GUI is purely a view over the
    `App.state` that the LLM control surface drives. Operator clicks issue
    the same dispatcher commands an LLM would; `App.state` is the single
    source of truth.
    """

    def __init__(self, app: App, *, with_tray: bool = False) -> None:
        super().__init__()
        self._app = app
        self.setWindowTitle("OpenRepose")
        self.setStyleSheet(DARK_QSS)
        # Operator-triggered first show is allowed to come to front (the
        # operator explicitly ran the launch command). After that, never
        # raise/activate from any LLM-driven code path. The Headless
        # Verification Checklist + the test_gui_no_focus_steal suite enforce
        # this contract on every dispatcher route.

        self._build_menu()
        self._build_central_widget()
        self._build_status_bar()
        self._wire_actions()

        # Register widget provider so the snapshot subsystem can grab live
        # widgets when this window is visible. Widgets are realized during
        # construction so QWidget.grab() works even if the window is later
        # minimized.
        set_widget_provider(self._provide_widget)

        # Periodically poll AppState changes so LLM-driven commands also
        # refresh GUI readouts.
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(250)
        self._poll_timer.timeout.connect(self._on_state_poll)
        self._poll_timer.start()

        # Initial sync.
        self._on_state_poll()

    # --- construction ----------------------------------------------------

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        act_open = QAction("&Open portrait...", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self._on_open)
        file_menu.addAction(act_open)

        act_export_single = QAction("Export &single", self)
        act_export_single.setShortcut(QKeySequence("Ctrl+E"))
        act_export_single.triggered.connect(self._on_export_single)
        file_menu.addAction(act_export_single)

        act_export_batch = QAction("Export &batch (13)", self)
        act_export_batch.setShortcut(QKeySequence("Ctrl+Shift+E"))
        act_export_batch.triggered.connect(self._on_export_batch)
        file_menu.addAction(act_export_batch)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

    def _build_central_widget(self) -> None:
        # Toolbar.
        self._toolbar = Toolbar(self)
        self.addToolBar(self._toolbar)

        # Two-pane center.
        self._viewport_3d = Viewport3D()
        self._viewport_openpose = ViewportOpenPose()
        center_split = QSplitter(Qt.Orientation.Horizontal)
        center_split.addWidget(self._viewport_3d)
        center_split.addWidget(self._viewport_openpose)
        center_split.setSizes([480, 480])

        # Right dock with tabs.
        self._tabs = QTabWidget()
        self._inspector = InspectorPane(self._app.state)
        self._options = OptionsPane()
        self._log_pane = LogPane(self._app.log)
        self._help_pane = HelpPane()
        self._calibration = CalibrationPane(self._app)
        self._markers = MarkersPane(self._app)
        self._tabs.addTab(self._inspector, "Inspector")
        self._tabs.addTab(self._calibration, "Calibration")
        self._tabs.addTab(self._markers, "Markers")
        self._tabs.addTab(self._options, "Options")
        self._tabs.addTab(self._log_pane, "Log")
        self._tabs.addTab(self._help_pane, "Help")

        # Outer layout.
        outer = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(center_split)
        outer.addWidget(self._tabs)
        outer.setSizes([960, 320])

        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(outer)
        self.setCentralWidget(wrapper)

    def _build_status_bar(self) -> None:
        self._status_bar = StatusBar(self._app.state)
        self.setStatusBar(self._status_bar)

    def _wire_actions(self) -> None:
        # Toolbar -> dispatcher commands.
        self._toolbar.open_clicked.connect(self._on_open)
        self._toolbar.reload_clicked.connect(self._on_reload)
        self._toolbar.yaw_bin_changed.connect(self._on_yaw_bin_changed)
        self._toolbar.yaw_value_changed.connect(self._on_yaw_value_changed)
        self._toolbar.export_single_clicked.connect(self._on_export_single)
        self._toolbar.export_batch_clicked.connect(self._on_export_batch)

        # Options pane -> persistent settings + per-body-part + frame.
        self._options.load_from_settings(self._app.settings)
        self._options.load_body_part_visibility(self._app.state.body_part_visibility)
        self._options.load_frame(self._app.state.frame)
        self._options.settings_changed.connect(self._on_settings_changed)
        self._options.body_part_visibility_changed.connect(
            self._on_body_part_visibility_changed
        )
        self._options.frame_scale_changed.connect(
            lambda s: self._app.handle_command(
                {"command": "set_frame_scale", "scale": float(s)}
            )
        )
        self._options.frame_offset_changed.connect(
            lambda x, y: self._app.handle_command(
                {"command": "set_frame_offset", "x": int(x), "y": int(y)}
            )
        )
        self._options.frame_anchor_changed.connect(
            lambda mode: self._app.handle_command(
                {"command": "set_frame_anchor", "mode": str(mode)}
            )
        )
        self._options.frame_reset_clicked.connect(
            lambda: self._app.handle_command({"command": "reset_frame"})
        )

        # WP-I1-032: canvas border color persists via Settings.
        self._options.load_canvas_border_color(
            self._app.settings.canvas_border_color
        )
        self._options.canvas_border_color_changed.connect(
            lambda hex_str: self._app.settings.update(
                canvas_border_color=str(hex_str)
            )
        )

        # Inspector buttons -> dispatcher commands.
        self._inspector.btn_render_single.clicked.connect(self._on_export_single)
        self._inspector.btn_snapshot_3d.clicked.connect(
            lambda: self._app.handle_command({"command": "snapshot", "target": "3d_viewport"})
        )
        self._inspector.btn_snapshot_openpose.clicked.connect(
            lambda: self._app.handle_command({"command": "snapshot", "target": "openpose_viewport"})
        )
        self._inspector.btn_snapshot_full.clicked.connect(
            lambda: self._app.handle_command({"command": "snapshot", "target": "full_window"})
        )
        self._inspector.btn_dump_rig.clicked.connect(
            lambda: self._app.handle_command({"command": "dump_rig"})
        )

    # --- snapshot widget provider ---------------------------------------

    def _provide_widget(self, target: str) -> object | None:
        """Snapshot subsystem calls this to retrieve the live widget for a
        target name. Returning None falls back to the placeholder render.

        Supports both the long target names used by direct snapshot commands
        (`inspector_pane`, `log_pane`, `options_pane`) and the short names
        used by the `full_window` compose layout (`inspector`, `log`,
        `options`).
        """
        return {
            "inspector_pane": self._inspector,
            "inspector": self._inspector,
            "log_pane": self._log_pane,
            "log": self._log_pane,
            "options_pane": self._options,
            "options": self._options,
            "status_bar": self._status_bar,
            "toolbar": self._toolbar,
        }.get(target)

    # --- operator actions (each dispatches into App, never bypasses) ----

    def _on_open(self) -> None:
        # WP-I1-032: open at the last-used portrait folder if remembered.
        initial_dir = self._app.settings.last_portrait_dir or ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open portrait",
            initial_dir,
            "Image files (*.png *.jpg *.jpeg)",
        )
        if not path:
            return
        slug = self._options.avatar_slug_edit.text().strip() or Path(path).stem
        self._app.handle_command(
            {"command": "import_portrait", "path": path, "avatar_slug": slug}
        )
        # Persist the chosen folder for next launch.
        try:
            self._app.settings.update(last_portrait_dir=str(Path(path).parent))
        except Exception:  # noqa: BLE001
            # Don't let a settings-persist hiccup break the import flow.
            self._app.log.warn(
                "settings.last_portrait_dir.persist_failed",
                reason="settings.update raised",
            )

    def _on_reload(self) -> None:
        portrait = self._app.state.portrait
        slug = self._app.state.avatar_slug
        if not portrait or not slug:
            return
        self._app.handle_command(
            {"command": "import_portrait", "path": portrait, "avatar_slug": slug}
        )

    def _on_yaw_bin_changed(self, label: str) -> None:
        self._app.handle_command({"command": "set_yaw_bin", "bin": label})

    def _on_yaw_value_changed(self, value_deg: float) -> None:
        self._app.handle_command({"command": "set_yaw", "value_deg": value_deg})

    def _on_export_single(self) -> None:
        self._app.handle_command({"command": "export_single"})

    def _on_export_batch(self) -> None:
        self._app.handle_command({"command": "export_batch"})

    def _on_body_part_visibility_changed(self, group: str, visible: bool) -> None:
        """Operator toggled a body-part group checkbox; dispatch the command."""
        self._app.handle_command(
            {"command": "set_body_part_visibility", group: visible}
        )

    def _on_settings_changed(self, payload: dict) -> None:
        """Persist operator-changed settings to disk + refresh state.json."""
        self._app.settings.update(
            export_folder=payload.get("export_folder", ""),
            single_export_subdir_template=payload.get(
                "single_export_subdir_template", "{avatar}"
            ),
            batch_export_subdir_template=payload.get(
                "batch_export_subdir_template", "{avatar}/{run_tag}"
            ),
        )
        resolved, default_used = (
            self._app.settings.export_folder_resolved_with_fallback_flag()
        )
        self._app.state.set_settings_status(
            export_folder=str(resolved),
            default_used=default_used,
            settings_path=str(self._app.settings.settings_path),
        )
        self._app.state.write()
        self._app.log.ok(
            "settings.update",
            export_folder=str(resolved),
            default_used=default_used,
        )

    # --- state -> GUI sync ----------------------------------------------

    def _on_state_poll(self) -> None:
        s = self._app.state.to_dict()
        # Update toolbar (suppress emit; programmatic).
        self._toolbar.set_state(
            s["yaw"]["current_value_deg"],
            s["yaw"]["current_bin"],
        )
        # Update inspector.
        self._inspector.refresh()
        # Update calibration tab (re-renders the overlay if the active
        # calibration changed via LLM command or operator click).
        self._calibration.refresh()
        # Sync markers tab from state (LLM commands can mutate it too).
        self._markers.refresh()
        # Update status bar.
        self._status_bar.refresh()
        # Render viewports if a rig is loaded.
        rig = self._app.dispatcher.rig
        if rig is not None:
            try:
                bin_obj = parse_bin(s["yaw"]["current_bin"])
            except Exception:  # noqa: BLE001
                bin_obj = signed_deg_to_bin(s["yaw"]["current_value_deg"])
            rotated = rotate_yaw(rig, bin_obj)
            self._viewport_3d.update_rig(rotated)
            self._viewport_openpose.update_rig(
                rotated,
                body_part_visibility=dict(self._app.state.body_part_visibility),
                marker_visibility={
                    k: dict(v)
                    for k, v in self._app.state.marker_visibility.items()
                },
                frame=dict(self._app.state.frame),
                canvas_border_color=self._app.settings.canvas_border_color,
            )
            self._inspector.set_canvas(rig.portrait_size[0], rig.portrait_size[1])
