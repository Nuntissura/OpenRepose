"""Operator-facing Calibration tab.

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 2 / GUI Requirements".

Master portrait display with click-to-place reference markers, anatomical-name
dropdown, MediaPipe-detected positions shown in dim color, completeness
indicator, Save / Clear buttons. The tab is operator-facing only; LLM agents
use the four `*_calibration*` commands directly.

LLM Headless contract:
- No `raise_()`, `activateWindow()`, `showNormal()`, or `setForegroundWindow()`
  call in any code path.
- No modal dialogs in response to LLM-driven calibration changes; the polling
  loop in `MainWindow` re-renders the overlay silently.
- All operator clicks issue dispatcher commands; the GUI never bypasses the
  command surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..calibration import (
    MEDIAPIPE_FACEMESH_INDEX_BY_MARKER,
    OPTIONAL_MARKERS,
    REQUIRED_MARKERS,
    Calibration,
    calibration_path,
)
from ..calibration import load as load_calibration
from ..render.draw_calibration import render_calibration_overlay

if TYPE_CHECKING:
    from ..app import App

ALL_MARKER_NAMES_ORDERED: tuple[str, ...] = REQUIRED_MARKERS + OPTIONAL_MARKERS

# WP-I1-034: marker dropdown sentinel entries.
DROPDOWN_PLACEHOLDER = "— pick one —"
DROPDOWN_OVERVIEW = "Overview (drag any marker)"


class _ZoomableImageView(QGraphicsView):
    """QGraphicsView with mouse-wheel zoom + click-drag pan + click-to-place.

    WP-I1-028 (replaces WP-I1-001's `_ClickablePortrait`):
    - Mouse wheel zooms anchored under the cursor.
    - Middle-mouse drag pans (Qt's ScrollHandDrag).
    - Single left-click (no movement past `CLICK_THRESHOLD_PX`) emits the
      click in image-space coordinates so the operator can place markers
      precisely under arbitrary zoom + pan.

    WP-I1-032 sizing constraint preserved: sizeHint is bounded so the
    Calibration tab does not grow the dock width.
    """

    clicked = Signal(int, int)
    marker_dragged = Signal(str, int, int)  # name, image_x, image_y
    marker_right_clicked = Signal(str)  # name

    DOCK_WIDTH_CAP = 320
    MIN_ZOOM = 0.1
    MAX_ZOOM = 8.0
    ZOOM_STEP = 1.15
    CLICK_THRESHOLD_PX = 4
    MARKER_HIT_RADIUS_PX = 14

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._image_size: tuple[int, int] = (0, 0)
        self._press_pos: QPoint | None = None
        self._space_held = False
        # WP-I1-034: marker hit-detection state.
        # _marker_positions: list of (name, image_x, image_y) for operator
        # markers that should be hit-tested. Set via set_marker_positions().
        # _draggable_names: subset of names that can be dragged in the
        # current mode. Empty = none draggable.
        self._marker_positions: list[tuple[str, float, float]] = []
        self._draggable_names: set[str] = set()
        self._dragging_marker: str | None = None
        self._drag_start_scene: QPoint | None = None
        self.setRenderHint(self.renderHints())  # default
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(360)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #111;")
        # Receive key events for the spacebar-pan gesture (WP-I1-028 fix).
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def sizeHint(self):  # noqa: D401, ANN201
        from PySide6.QtCore import QSize

        return QSize(self.DOCK_WIDTH_CAP, 360)

    def minimumSizeHint(self):  # noqa: ANN201
        from PySide6.QtCore import QSize

        return QSize(120, 240)

    def set_overlay(
        self,
        bgr: np.ndarray,
        image_size: tuple[int, int],
    ) -> None:
        """Replace the rendered overlay. Preserves the operator's current
        zoom + pan when the image_size matches (so toggling markers on a
        loaded portrait does not reset zoom)."""
        self._image_size = image_size
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb)
        qimg = QImage(
            rgb.data,
            w,
            h,
            rgb.strides[0],
            QImage.Format.Format_RGB888,
        ).copy()
        pix = QPixmap.fromImage(qimg)
        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pix)
            self._scene.setSceneRect(0, 0, w, h)
            # Initial fit-to-view.
            self.fitInView(
                self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio
            )
        else:
            self._pixmap_item.setPixmap(pix)

    def reset_zoom(self) -> None:
        """Fit pixmap to view (used by an external Reset button)."""
        if self._pixmap_item is not None:
            self.fitInView(
                self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio
            )

    def set_marker_positions(
        self,
        positions: list[tuple[str, float, float]],
        draggable_names: set[str],
    ) -> None:
        """WP-I1-034: tell the view which operator markers exist + which
        of them are draggable in the current mode. Used for hit-testing on
        mouse events. Visual rendering still happens via the cv2 pixmap;
        these positions are only for drag / right-click detection.
        """
        self._marker_positions = list(positions)
        self._draggable_names = set(draggable_names)

    def _hit_test_marker(self, scene_pt) -> str | None:  # noqa: ANN001
        """Return the name of a marker within MARKER_HIT_RADIUS of
        scene_pt, or None. Hit radius is in scene (image) units, so a
        zoomed-in view doesn't make hit-testing easier or harder."""
        sx, sy = scene_pt.x(), scene_pt.y()
        for name, mx, my in self._marker_positions:
            if (sx - mx) ** 2 + (sy - my) ** 2 <= self.MARKER_HIT_RADIUS_PX ** 2:
                return name
        return None

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: D401
        if self._pixmap_item is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = self.ZOOM_STEP if delta > 0 else 1 / self.ZOOM_STEP
        # Clamp cumulative zoom to [MIN_ZOOM, MAX_ZOOM].
        current = self.transform().m11()
        new_scale = current * factor
        if new_scale < self.MIN_ZOOM or new_scale > self.MAX_ZOOM:
            return
        self.scale(factor, factor)

    def keyPressEvent(self, event):  # noqa: ANN001
        """Spacebar-pan gesture (Photoshop convention): hold space + left-click
        + drag to pan. Spacebar alone shows the open-hand cursor as a hint."""
        if (
            event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
            and not self._space_held
        ):
            self._space_held = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):  # noqa: ANN001
        if (
            event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
            and self._space_held
        ):
            self._space_held = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.viewport().unsetCursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton and not self._space_held:
            # WP-I1-034: right-click hit-tests against operator markers and
            # emits marker_right_clicked. Suppress the default context menu.
            scene_pt = self.mapToScene(event.pos())
            name = self._hit_test_marker(scene_pt)
            if name is not None:
                self.marker_right_clicked.emit(name)
                event.accept()
                return
        if event.button() == Qt.MouseButton.LeftButton and not self._space_held:
            self._press_pos = event.pos()
            # WP-I1-034: if the press is on a draggable marker, enter
            # drag mode for that marker.
            if self._image_size != (0, 0) and self._pixmap_item is not None:
                scene_pt = self.mapToScene(event.pos())
                name = self._hit_test_marker(scene_pt)
                if name is not None and name in self._draggable_names:
                    self._dragging_marker = name
                    self._drag_start_scene = scene_pt
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._press_pos is not None
            and not self._space_held
        ):
            release_pos = event.pos()
            dx = release_pos.x() - self._press_pos.x()
            dy = release_pos.y() - self._press_pos.y()
            self._press_pos = None
            moved_far = (
                abs(dx) > self.CLICK_THRESHOLD_PX
                or abs(dy) > self.CLICK_THRESHOLD_PX
            )

            # WP-I1-034 drag end: if we were dragging a marker AND the
            # cursor actually moved, fire marker_dragged.
            if self._dragging_marker is not None:
                if moved_far:
                    scene_pt = self.mapToScene(release_pos)
                    iw, ih = self._image_size
                    ix = max(0, min(iw - 1, int(round(scene_pt.x()))))
                    iy = max(0, min(ih - 1, int(round(scene_pt.y()))))
                    self.marker_dragged.emit(self._dragging_marker, ix, iy)
                self._dragging_marker = None
                self._drag_start_scene = None
                super().mouseReleaseEvent(event)
                return

            # Plain click → marker placement (when no drag).
            if moved_far:
                super().mouseReleaseEvent(event)
                return
            if self._image_size == (0, 0) or self._pixmap_item is None:
                super().mouseReleaseEvent(event)
                return
            scene_pt = self.mapToScene(release_pos)
            iw, ih = self._image_size
            ix = int(round(scene_pt.x()))
            iy = int(round(scene_pt.y()))
            if 0 <= ix < iw and 0 <= iy < ih:
                self.clicked.emit(ix, iy)
        super().mouseReleaseEvent(event)


class CalibrationPane(QWidget):
    """Operator-facing calibration tab.

    The pane is an idempotent view over `App.state` + the per-avatar
    calibration JSON. Refresh is driven by the `MainWindow` polling timer; no
    timers or workers live in this widget.
    """

    def __init__(self, app: "App") -> None:
        super().__init__()
        self._app = app

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top row: marker selector + completeness.
        # WP-I1-034: dropdown defaults to a "— pick one —" placeholder + an
        # "Overview" entry that makes ALL markers draggable. Single-marker
        # entries restrict drag to that one + still allow click-to-place.
        top = QHBoxLayout()
        marker_label = QLabel("active marker:")
        marker_label.setObjectName("inspector-key")
        self._marker_combo = QComboBox()
        self._marker_combo.addItem(DROPDOWN_PLACEHOLDER)
        self._marker_combo.addItem(DROPDOWN_OVERVIEW)
        self._marker_combo.addItems(ALL_MARKER_NAMES_ORDERED)
        self._marker_combo.currentTextChanged.connect(self._on_marker_changed)
        self._completeness = QLabel("calibration: none")
        self._completeness.setObjectName("inspector-value")
        top.addWidget(marker_label)
        top.addWidget(self._marker_combo, 1)
        top.addStretch(1)
        top.addWidget(self._completeness)
        layout.addLayout(top)

        # Portrait display with zoom + pan (WP-I1-028).
        self._portrait = _ZoomableImageView()
        self._portrait.clicked.connect(self._on_portrait_clicked)
        # WP-I1-034: drag + right-click signals.
        self._portrait.marker_dragged.connect(self._on_marker_dragged)
        self._portrait.marker_right_clicked.connect(
            self._on_marker_right_clicked
        )
        layout.addWidget(self._portrait, 1)

        # Bottom row: action buttons.
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_clear = QPushButton("Clear")
        self.btn_redetect = QPushButton("Re-detect")
        self.btn_reset_zoom = QPushButton("Reset zoom")
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_redetect)
        btn_row.addWidget(self.btn_reset_zoom)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        self.btn_reset_zoom.clicked.connect(self._portrait.reset_zoom)

        # Status / hint label.
        self._hint = QLabel(
            "click on portrait to place the active marker. each click writes "
            "calibration.json immediately."
        )
        self._hint.setObjectName("inspector-key")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self.btn_save.clicked.connect(self._on_save)
        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_redetect.clicked.connect(self._on_redetect)

        self.refresh()

    # --- public update path (called by MainWindow polling) ---------------

    def refresh(self) -> None:
        """Render the portrait + current calibration overlay.

        WP-I1-028: passes detected_positions so the always-on dim MediaPipe
        dots render even before the operator places any operator marker.
        WP-I1-034: also feeds the operator-marker positions to the
        ZoomableImageView so it can hit-test for drag + right-click;
        draggable subset depends on the dropdown selection (Overview = all,
        single marker name = just that one, placeholder = none).
        """
        cal = self._load_active_calibration()
        portrait_path = self._app.state.portrait
        detected = self._compute_detected_positions()
        bgr = render_calibration_overlay(
            portrait_path, cal, detected_positions=detected
        )
        h, w = bgr.shape[:2]
        self._portrait.set_overlay(bgr, image_size=(w, h))

        # WP-I1-034: feed marker positions + draggable filter.
        marker_positions: list[tuple[str, float, float]] = []
        if cal is not None:
            for m in cal.markers:
                marker_positions.append(
                    (m.name, float(m.operator_xy[0]), float(m.operator_xy[1]))
                )
        active = self._marker_combo.currentText()
        if active == DROPDOWN_OVERVIEW:
            draggable = {n for n, _, _ in marker_positions}
        elif active in ALL_MARKER_NAMES_ORDERED:
            draggable = {active}
        else:
            draggable = set()
        self._portrait.set_marker_positions(marker_positions, draggable)

        completeness = "none"
        marker_count = 0
        if cal is not None:
            completeness = cal.completeness
            marker_count = cal.marker_count
        self._completeness.setText(
            f"calibration: {completeness} ({marker_count} markers)"
        )

    def _compute_detected_positions(self) -> dict[str, tuple[float, float]] | None:
        """Build {marker_name: (x, y)} from the active rig's raw_face_mesh
        + canonical FaceMesh indices. Returns None when no rig loaded."""
        rig = self._app.dispatcher.rig
        if rig is None:
            return None
        src = (
            rig.raw_face_mesh
            if rig.raw_face_mesh is not None
            else rig.face_mesh
        )
        if src is None or src.shape[0] == 0:
            return None
        out: dict[str, tuple[float, float]] = {}
        for name, idx in MEDIAPIPE_FACEMESH_INDEX_BY_MARKER.items():
            if 0 <= idx < src.shape[0]:
                out[name] = (float(src[idx, 0]), float(src[idx, 1]))
        return out

    # --- operator action handlers ----------------------------------------

    def _on_marker_changed(self, name: str) -> None:
        """Refresh draggable marker set when the dropdown selection changes."""
        self.refresh()

    def _on_portrait_clicked(self, x: int, y: int) -> None:
        avatar = self._app.state.avatar_slug
        if not avatar:
            return  # no portrait loaded; click is a no-op
        marker = self._marker_combo.currentText()
        # WP-I1-034: placeholder + Overview do not place a marker on click.
        # In Overview, drag is the editing model; click is a no-op so the
        # operator doesn't accidentally drop a marker for "the wrong name".
        if marker not in ALL_MARKER_NAMES_ORDERED:
            return

        # WP-I1-034 add+place workflow: when the marker is undetected
        # (state.detected_markers reports False for its corresponding
        # face_70 / body_18 index, OR there's no rig yet), the click
        # stores both operator_xy AND mediapipe_xy as the operator's
        # picked point. The dispatcher is the source of truth for
        # mediapipe_xy normally — supplying it here overrides.
        explicit_mp_xy: list[int] | None = None
        rig = self._app.dispatcher.rig
        if rig is None:
            explicit_mp_xy = [x, y]
        else:
            from ..calibration import MEDIAPIPE_FACEMESH_INDEX_BY_MARKER

            idx = MEDIAPIPE_FACEMESH_INDEX_BY_MARKER.get(marker)
            face = (
                rig.raw_face_mesh
                if rig.raw_face_mesh is not None
                else rig.face_mesh
            )
            if (
                idx is None
                or idx >= face.shape[0]
                or (
                    abs(float(face[idx, 0])) < 1.0
                    and abs(float(face[idx, 1])) < 1.0
                )
            ):
                # No detection at this MediaPipe index — operator-supplied.
                explicit_mp_xy = [x, y]

        marker_payload: dict = {
            "name": marker,
            "operator_xy": [x, y],
        }
        if explicit_mp_xy is not None:
            marker_payload["mediapipe_xy"] = explicit_mp_xy
        self._app.handle_command(
            {
                "command": "set_calibration_points",
                "markers": [marker_payload],
                "merge": True,
            }
        )
        self.refresh()

    def _on_marker_dragged(self, name: str, x: int, y: int) -> None:
        """WP-I1-034: drag end → set_calibration_points (merge=true) for
        that marker at the new position."""
        avatar = self._app.state.avatar_slug
        if not avatar or name not in ALL_MARKER_NAMES_ORDERED:
            return
        self._app.handle_command(
            {
                "command": "set_calibration_points",
                "markers": [{"name": name, "operator_xy": [x, y]}],
                "merge": True,
            }
        )
        self.refresh()

    def _on_marker_right_clicked(self, name: str) -> None:
        """WP-I1-034: right-click on operator marker → delete_markers."""
        avatar = self._app.state.avatar_slug
        if not avatar:
            return
        self._app.handle_command(
            {"command": "delete_markers", "names": [name]}
        )
        self.refresh()

    def _on_save(self) -> None:
        # set_calibration_points already persists on every click; Save is a
        # confirmation hook (dump current calibration so the operator can see
        # the state in the log pane).
        if not self._app.state.avatar_slug:
            return
        self._app.handle_command({"command": "dump_calibration"})
        self.refresh()

    def _on_clear(self) -> None:
        if not self._app.state.avatar_slug:
            return
        self._app.handle_command({"command": "clear_calibration"})
        self.refresh()

    def _on_redetect(self) -> None:
        portrait = self._app.state.portrait
        avatar = self._app.state.avatar_slug
        if not portrait or not avatar:
            return
        self._app.handle_command(
            {
                "command": "import_portrait",
                "path": portrait,
                "avatar_slug": avatar,
            }
        )
        self.refresh()

    # --- internals -------------------------------------------------------

    def _load_active_calibration(self) -> Calibration | None:
        avatar = self._app.state.avatar_slug
        if not avatar:
            return None
        return load_calibration(
            calibration_path(self._app.dispatcher.outputs_root, avatar)
        )
