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
    QLabel,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QWidget,
)

from ..app import App
from ..render.widget_grab import set_widget_provider
from ..rotation import rotate_yaw
from ..yaw_bin import parse_bin, signed_deg_to_bin, standard_13_angle_bins
from .drop_helper import decide_multi_drop, mime_has_acceptable_image
from .help_pane import HelpPane
from .inspector import InspectorPane
from .library import LibraryPane
from .log_pane import LogPane
from .options import OptionsPane
from .status_bar import StatusBar
from .tools_pane import ToolsPane
from .style import DARK_QSS
from .toolbar import Toolbar
from .triage import TriagePane
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

        # WP-I1-005: drop targets are MainWindow + both viewports.
        # Viewports forward via the same _import_portrait_path entry point
        # so there is one canonical handler.
        self.setAcceptDrops(True)
        self._viewport_3d.set_drop_callback(self._import_portrait_path)
        self._viewport_openpose.set_drop_callback(self._import_portrait_path)

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

        # WP-I1-016: Edit menu hosts the Clear workspace action; the
        # toolbar button next to Open is the primary operator surface.
        edit_menu = menu.addMenu("&Edit")
        self.act_clear_workspace = QAction("&Clear workspace", self)
        self.act_clear_workspace.setStatusTip(
            "Drop the active document's rig and blank the viewports."
        )
        self.act_clear_workspace.triggered.connect(self._on_clear_workspace)
        edit_menu.addAction(self.act_clear_workspace)

    def _build_central_widget(self) -> None:
        # Toolbar.
        self._toolbar = Toolbar(self)
        self.addToolBar(self._toolbar)

        # Multi-file workspace (WP-I1-037): file tabs own viewport pairs.
        self._file_pages: dict[str, tuple[QWidget, Viewport3D, ViewportOpenPose]] = {}
        self._syncing_file_tabs = False
        self._file_tabs = QTabWidget()
        self._file_tabs.setTabsClosable(True)
        self._file_tabs.setMovable(True)
        self._file_tabs.tabCloseRequested.connect(self._on_file_tab_close_requested)
        self._file_tabs.currentChanged.connect(self._on_file_tab_changed)
        empty_page, self._viewport_3d, self._viewport_openpose = self._create_file_page("__empty__")
        self._file_tabs.addTab(empty_page, "Drop portrait")

        # Right dock with tabs.
        self._tabs = QTabWidget()
        self._inspector = InspectorPane(self._app.state)
        self._options = OptionsPane()
        self._log_pane = LogPane(self._app.log)
        self._help_pane = HelpPane()
        # WP-I1-031: editing tools (Calibration, Markers, Reframer) live
        # under a single Tools top-level tab as sub-tabs. Keep direct
        # references on MainWindow for existing tests + state-poll path.
        self._tools = ToolsPane(self._app)
        self._calibration = self._tools.calibration
        self._markers = self._tools.markers
        self._reframer = self._tools.reframer
        self._library = LibraryPane(self._app)
        # WP-I3-008: Triage tab between Library and Options.
        self._triage = TriagePane(self._app.state)
        self._tabs.addTab(self._inspector, "Inspector")
        self._tabs.addTab(self._tools, "Tools")
        self._tabs.addTab(self._library, "Library")
        self._tabs.addTab(self._triage, "Triage")
        self._tabs.addTab(self._options, "Options")
        self._tabs.addTab(self._log_pane, "Log")
        self._tabs.addTab(self._help_pane, "Help")

        # Outer layout.
        outer = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(self._file_tabs)
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
        self._toolbar.clear_workspace_clicked.connect(self._on_clear_workspace)
        self._toolbar.reload_clicked.connect(self._on_reload)
        self._toolbar.yaw_bin_changed.connect(self._on_yaw_bin_changed)
        self._toolbar.yaw_value_changed.connect(self._on_yaw_value_changed)
        self._toolbar.export_single_clicked.connect(self._on_export_single)
        self._toolbar.export_batch_clicked.connect(self._on_export_batch)

        # Options pane -> persistent settings + per-body-part.
        self._options.load_from_settings(self._app.settings)
        self._options.load_body_part_visibility(self._app.state.body_part_visibility)
        self._options.settings_changed.connect(self._on_settings_changed)
        self._options.body_part_visibility_changed.connect(
            self._on_body_part_visibility_changed
        )

        # WP-I1-031: Reframer pane (Tools tab → Reframer sub-tab) hosts the
        # frame scale + offset + anchor controls. Wire to dispatcher.
        self._reframer.load_frame(self._app.state.frame)
        self._reframer.frame_scale_changed.connect(
            lambda s: self._app.handle_command(
                {"command": "set_frame_scale", "scale": float(s)}
            )
        )
        self._reframer.frame_offset_changed.connect(
            lambda x, y: self._app.handle_command(
                {"command": "set_frame_offset", "x": int(x), "y": int(y)}
            )
        )
        self._reframer.frame_anchor_changed.connect(
            lambda mode: self._app.handle_command(
                {"command": "set_frame_anchor", "mode": str(mode)}
            )
        )
        self._reframer.frame_reset_clicked.connect(
            lambda: self._app.handle_command({"command": "reset_frame"})
        )
        # Per-section resets (WP-I1-031 operator request).
        self._reframer.reset_scale_clicked.connect(
            lambda: self._app.handle_command(
                {"command": "set_frame_scale", "scale": 1.0}
            )
        )
        self._reframer.reset_offset_clicked.connect(
            lambda: self._app.handle_command(
                {"command": "set_frame_offset", "x": 0, "y": 0}
            )
        )
        self._reframer.reset_anchor_clicked.connect(
            lambda: self._app.handle_command(
                {"command": "set_frame_anchor", "mode": "head_anchor"}
            )
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


    # --- multi-file workspace ------------------------------------------

    def _create_file_page(
        self, file_id: str
    ) -> tuple[QWidget, Viewport3D, ViewportOpenPose]:
        page = QWidget()
        page.setProperty("file_id", file_id)
        view3d = Viewport3D()
        view_openpose = ViewportOpenPose()
        view3d.set_drop_callback(self._import_portrait_path)
        view_openpose.set_drop_callback(self._import_portrait_path)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(view3d)
        split.addWidget(view_openpose)
        split.setSizes([480, 480])
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(split)
        self._file_pages[file_id] = (page, view3d, view_openpose)
        return page, view3d, view_openpose

    def _tab_file_id(self, index: int) -> str | None:
        widget = self._file_tabs.widget(index)
        if widget is None:
            return None
        raw = widget.property("file_id")
        return str(raw) if raw else None

    def _sync_file_tabs(self, state_dict: dict) -> None:
        files = list(state_dict.get("files") or [])
        active_file_id = state_dict.get("active_file_id")
        wanted = [str(f.get("file_id")) for f in files if f.get("file_id")]
        wanted_set = set(wanted)
        self._syncing_file_tabs = True
        try:
            # Remove stale real tabs and the empty tab when files exist.
            for i in range(self._file_tabs.count() - 1, -1, -1):
                fid = self._tab_file_id(i)
                if fid == "__empty__" and files:
                    self._file_tabs.removeTab(i)
                    continue
                if fid and fid != "__empty__" and fid not in wanted_set:
                    self._file_tabs.removeTab(i)
                    self._file_pages.pop(fid, None)

            if not files:
                if "__empty__" not in self._file_pages:
                    page, _, _ = self._create_file_page("__empty__")
                    self._file_tabs.addTab(page, "Drop portrait")
                elif self._file_tabs.count() == 0:
                    self._file_tabs.addTab(self._file_pages["__empty__"][0], "Drop portrait")
                self._file_tabs.setCurrentIndex(0)
            else:
                for item in files:
                    fid = str(item.get("file_id"))
                    if fid not in self._file_pages:
                        page, _, _ = self._create_file_page(fid)
                        label = str(item.get("avatar_slug") or Path(str(item.get("path", "portrait"))).stem)
                        self._file_tabs.addTab(page, label[:32])
                    else:
                        page = self._file_pages[fid][0]
                        idx = self._file_tabs.indexOf(page)
                        if idx >= 0:
                            label = str(item.get("avatar_slug") or Path(str(item.get("path", "portrait"))).stem)
                            self._file_tabs.setTabText(idx, label[:32])
                if active_file_id in self._file_pages:
                    idx = self._file_tabs.indexOf(self._file_pages[str(active_file_id)][0])
                    if idx >= 0 and idx != self._file_tabs.currentIndex():
                        self._file_tabs.setCurrentIndex(idx)

            current_fid = self._tab_file_id(self._file_tabs.currentIndex())
            if current_fid and current_fid in self._file_pages:
                _, self._viewport_3d, self._viewport_openpose = self._file_pages[current_fid]
        finally:
            self._syncing_file_tabs = False

    def _on_file_tab_close_requested(self, index: int) -> None:
        fid = self._tab_file_id(index)
        if fid and fid != "__empty__":
            self._app.handle_command({"command": "close_file", "file_id": fid})

    def _on_file_tab_changed(self, index: int) -> None:
        if self._syncing_file_tabs:
            return
        fid = self._tab_file_id(index)
        if fid and fid != "__empty__" and fid != self._app.state.active_file_id:
            self._app.handle_command({"command": "set_active_file", "file_id": fid})

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
            # WP-I3-008 — Triage tab + sub-panes.
            "intake_triage_view": self._triage,
            "task_summary_view": self._triage.task_summary_pane,
            "library_card_with_pose": self._triage.active_card_pane,
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
        self._import_portrait_path(path)

    def _import_portrait_path(self, path: str | Path) -> None:
        """Shared portrait-import path used by File→Open, drag-and-drop
        on MainWindow, and drag-and-drop forwarded from the viewports.
        Picks the slug from OptionsPane (or sanitizes from filename),
        dispatches `import_portrait`, persists the parent folder."""
        from ..util.slugify import sanitize_avatar_slug

        path_str = str(path)
        slug = (
            self._options.avatar_slug_edit.text().strip()
            or sanitize_avatar_slug(Path(path_str).stem)
        )
        self._app.handle_command(
            {"command": "import_portrait", "path": path_str, "avatar_slug": slug}
        )
        try:
            self._app.settings.update(last_portrait_dir=str(Path(path_str).parent))
        except Exception:  # noqa: BLE001
            self._app.log.warn(
                "settings.last_portrait_dir.persist_failed",
                reason="settings.update raised",
            )

    # WP-I1-005: drag-and-drop portrait import.

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if mime_has_acceptable_image(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if mime_has_acceptable_image(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt API)
        decision = decide_multi_drop(event.mimeData())
        if not decision.paths:
            self._app.log.warn(
                "import.drop_rejected",
                reason=decision.reason or "unknown",
                ignored=",".join(decision.ignored) if decision.ignored else "",
            )
            event.ignore()
            return
        if decision.ignored:
            self._app.log.warn(
                "import.drop_partial",
                reason="accepted image files; rejected unsupported entries",
                accepted=",".join(p.name for p in decision.paths),
                ignored=",".join(decision.ignored),
            )
        event.acceptProposedAction()
        for path in decision.paths:
            self._import_portrait_path(path)

    def _on_clear_workspace(self) -> None:
        """Toolbar / Edit menu → dispatch the headless clear_workspace
        command. No confirmation dialog (the action is operator-explicit;
        WP-I1-016 In Scope rules out a modal)."""
        self._app.handle_command({"command": "clear_workspace"})

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
            library_db_url=payload.get("library_db_url", ""),
            library_root=payload.get("library_root", ""),
            operator_slug=payload.get("operator_slug", ""),
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
        self._sync_file_tabs(s)
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
        # Sync reframer pane (LLM commands can mutate state.frame).
        self._reframer.load_frame(self._app.state.frame)
        # WP-I3-008 — Triage tab reads state.library.intake / targets / amood.
        self._triage.refresh()
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
