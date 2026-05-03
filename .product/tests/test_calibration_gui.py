"""GUI tests for the Calibration tab.

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 2 / GUI Requirements".
"""

from __future__ import annotations

from pathlib import Path

import pytest


pytest.importorskip("pytestqt")


@pytest.fixture
def app_and_window(qtbot, tmp_path: Path):
    from openrepose.app import App
    from openrepose.gui.main_window import MainWindow

    app = App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
    )
    window = MainWindow(app)
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.waitExposed(window)
    yield app, window
    app.stop()


def test_calibration_tab_present(app_and_window) -> None:
    """WP-I1-031: Calibration is a sub-tab of Tools (no longer top-level)."""
    _app, window = app_and_window
    top_titles = [
        window._tabs.tabText(i) for i in range(window._tabs.count())
    ]
    assert "Tools" in top_titles
    sub_titles = [
        window._tools._tabs.tabText(i)
        for i in range(window._tools._tabs.count())
    ]
    assert "Calibration" in sub_titles


def test_markers_body_18_rows_colored_per_openpose_limb(
    app_and_window,
) -> None:
    """WP-I1-032: each body_18 row in the Markers tab must be colored to
    match the OpenPose limb color of that keypoint."""
    from PySide6.QtGui import QColor

    from openrepose.openpose_schema import OPENPOSE_BODY_COUNT
    from openrepose.render.draw_openpose import BODY_18_COLOR_BY_INDEX

    _app, window = app_and_window
    body_list = window._markers._body_list
    assert body_list.count() == OPENPOSE_BODY_COUNT
    for i in range(OPENPOSE_BODY_COUNT):
        item = body_list.item(i)
        b, g, r = BODY_18_COLOR_BY_INDEX[i]
        expected = QColor(r, g, b)
        actual = item.foreground().color()
        assert actual.red() == expected.red()
        assert actual.green() == expected.green()
        assert actual.blue() == expected.blue()


def test_calibration_pane_has_all_marker_names_in_dropdown(
    app_and_window,
) -> None:
    """WP-I1-034 update: dropdown now leads with placeholder + Overview
    entries, then the 10 anatomical names."""
    from openrepose.calibration import OPTIONAL_MARKERS, REQUIRED_MARKERS
    from openrepose.gui.calibration import (
        DROPDOWN_OVERVIEW,
        DROPDOWN_PLACEHOLDER,
    )

    _app, window = app_and_window
    pane = window._calibration
    items = [
        pane._marker_combo.itemText(i)
        for i in range(pane._marker_combo.count())
    ]
    expected = (
        [DROPDOWN_PLACEHOLDER, DROPDOWN_OVERVIEW]
        + list(REQUIRED_MARKERS)
        + list(OPTIONAL_MARKERS)
    )
    assert items == expected


def test_calibration_pane_completeness_default_none(app_and_window) -> None:
    _app, window = app_and_window
    text = window._calibration._completeness.text().lower()
    assert "none" in text


def test_calibration_pane_buttons_present(app_and_window) -> None:
    _app, window = app_and_window
    pane = window._calibration
    assert pane.btn_save is not None
    assert pane.btn_clear is not None
    assert pane.btn_redetect is not None


def test_calibration_pane_click_without_avatar_is_noop(app_and_window) -> None:
    """No active avatar -> portrait click silently no-ops; no error, no
    state change."""
    app, window = app_and_window
    pane = window._calibration
    pane._on_portrait_clicked(100, 200)
    assert app.state.calibration["completeness"] == "none"
    assert app.state.calibration["marker_count"] == 0


def test_calibration_pane_click_after_import_records_marker(
    app_and_window, aeri_master: Path, qtbot
) -> None:
    """Click on portrait while a portrait is loaded AND a single marker is
    selected fires set_calibration_points and updates state.calibration."""
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    pane = window._calibration
    # WP-I1-034: dropdown defaults to placeholder; pick a single marker
    # before clicking.
    pane._marker_combo.setCurrentText("eye_outer_left")
    pane._on_portrait_clicked(412, 487)
    qtbot.wait(20)
    assert app.state.calibration["marker_count"] >= 1
    assert app.state.calibration["active_avatar"] == "aeri"
    # The completeness will be 'partial' since only 1 of 6 required is set.
    assert app.state.calibration["completeness"] == "partial"


def test_calibration_pane_clear_button_resets_state(
    app_and_window, aeri_master: Path, qtbot
) -> None:
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    pane = window._calibration
    # WP-I1-034: pick a marker first; placeholder is a no-op on click.
    pane._marker_combo.setCurrentText("eye_outer_left")
    pane._on_portrait_clicked(100, 200)
    qtbot.wait(20)
    assert app.state.calibration["marker_count"] >= 1

    pane._on_clear()
    qtbot.wait(20)
    assert app.state.calibration["marker_count"] == 0
    assert app.state.calibration["completeness"] == "none"


def test_calibration_pane_clicks_do_not_call_focus_apis(
    app_and_window, aeri_master: Path, monkeypatch, qtbot
) -> None:
    """Drive 10 calibration clicks and assert zero raise_/activateWindow/
    showNormal/showMaximized invocations (matches the project-wide
    no-focus-steal contract enforced by test_gui_no_focus_steal)."""
    from PySide6.QtWidgets import QWidget

    counts = {
        "raise_": 0,
        "activateWindow": 0,
        "showNormal": 0,
        "showMaximized": 0,
    }
    real = {
        "raise_": QWidget.raise_,
        "activateWindow": QWidget.activateWindow,
        "showNormal": QWidget.showNormal,
        "showMaximized": QWidget.showMaximized,
    }

    def make_counter(name: str):
        def wrapper(self):  # noqa: ANN001
            counts[name] += 1
            return real[name](self)

        return wrapper

    monkeypatch.setattr(QWidget, "raise_", make_counter("raise_"))
    monkeypatch.setattr(
        QWidget, "activateWindow", make_counter("activateWindow")
    )
    monkeypatch.setattr(QWidget, "showNormal", make_counter("showNormal"))
    monkeypatch.setattr(
        QWidget, "showMaximized", make_counter("showMaximized")
    )

    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    pane = window._calibration
    for i in range(10):
        pane._marker_combo.setCurrentIndex(i % pane._marker_combo.count())
        pane._on_portrait_clicked(100 + i * 10, 200 + i * 10)
        qtbot.wait(5)
    pane._on_clear()
    qtbot.wait(5)

    assert counts == {
        "raise_": 0,
        "activateWindow": 0,
        "showNormal": 0,
        "showMaximized": 0,
    }, counts


def test_calibration_portrait_sizehint_constrained(app_and_window) -> None:
    """WP-I1-032 regression: switching to Calibration must NOT make the
    portrait widget report a sizeHint wider than the dock cap, otherwise
    activating the tab would grow the dock width to the master portrait's
    natural pixel width. WP-I1-028 keeps the same constraint after
    swapping the QLabel for QGraphicsView."""
    _app, window = app_and_window
    portrait = window._calibration._portrait
    hint = portrait.sizeHint()
    assert hint.width() <= portrait.DOCK_WIDTH_CAP, (
        f"portrait sizeHint width {hint.width()} exceeds dock cap "
        f"{portrait.DOCK_WIDTH_CAP}"
    )


def test_calibration_portrait_is_zoomable_graphics_view(app_and_window) -> None:
    """WP-I1-028: the portrait widget is now a QGraphicsView with zoom
    bounds set."""
    from openrepose.gui.calibration import _ZoomableImageView

    _app, window = app_and_window
    portrait = window._calibration._portrait
    assert isinstance(portrait, _ZoomableImageView)
    assert portrait.MIN_ZOOM > 0
    assert portrait.MAX_ZOOM > portrait.MIN_ZOOM


def test_calibration_pane_has_reset_zoom_button(app_and_window) -> None:
    """WP-I1-028: Reset zoom button next to Save / Clear / Re-detect."""
    _app, window = app_and_window
    assert window._calibration.btn_reset_zoom is not None


def test_calibration_view_pan_via_spacebar_left_click(
    app_and_window,
) -> None:
    """WP-I1-028: Photoshop-convention pan = hold spacebar + left-click drag.
    Middle-mouse pan removed (operator preference)."""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QGraphicsView

    _app, window = app_and_window
    view = window._calibration._portrait
    # Default: NoDrag.
    assert view.dragMode() == QGraphicsView.DragMode.NoDrag
    # Press space -> ScrollHandDrag.
    press = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier
    )
    view.keyPressEvent(press)
    assert view.dragMode() == QGraphicsView.DragMode.ScrollHandDrag
    # Release space -> NoDrag again.
    release = QKeyEvent(
        QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier
    )
    view.keyReleaseEvent(release)
    assert view.dragMode() == QGraphicsView.DragMode.NoDrag


def test_calibration_pane_marker_dropdown_starts_with_placeholder(
    app_and_window,
) -> None:
    """WP-I1-034: dropdown defaults to '— pick one —' placeholder; the
    second entry is the Overview mode; then the 10 anatomical names."""
    from openrepose.gui.calibration import (
        ALL_MARKER_NAMES_ORDERED,
        DROPDOWN_OVERVIEW,
        DROPDOWN_PLACEHOLDER,
    )

    _app, window = app_and_window
    combo = window._calibration._marker_combo
    assert combo.itemText(0) == DROPDOWN_PLACEHOLDER
    assert combo.itemText(1) == DROPDOWN_OVERVIEW
    items = [combo.itemText(i) for i in range(2, combo.count())]
    assert items == list(ALL_MARKER_NAMES_ORDERED)
    assert combo.currentText() == DROPDOWN_PLACEHOLDER


def test_calibration_pane_click_with_placeholder_selected_is_noop(
    app_and_window, aeri_master: Path, qtbot
) -> None:
    """WP-I1-034: with the dropdown on the placeholder, clicking the
    portrait must NOT place a marker."""
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    window._calibration._on_portrait_clicked(412, 487)
    qtbot.wait(20)
    # No marker created.
    assert app.state.calibration["marker_count"] == 0


def test_calibration_pane_drag_dispatches_set_calibration_points(
    app_and_window, aeri_master: Path, qtbot
) -> None:
    """WP-I1-034: marker_dragged → set_calibration_points (merge=true) for
    that marker at the new position."""
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    # Place a marker so it exists to drag.
    app.handle_command(
        {
            "command": "set_calibration_points",
            "markers": [
                {
                    "name": "eye_outer_left",
                    "operator_xy": [100, 200],
                }
            ],
            "merge": True,
        }
    )
    # Simulate drag end.
    window._calibration._on_marker_dragged("eye_outer_left", 555, 666)
    qtbot.wait(20)
    d = app.handle_command({"command": "dump_calibration"})
    markers = d.payload["calibration"]["markers"]
    el = next(m for m in markers if m["name"] == "eye_outer_left")
    assert el["operator_xy"] == [555.0, 666.0]


def test_calibration_pane_right_click_dispatches_delete_markers(
    app_and_window, aeri_master: Path, qtbot
) -> None:
    """WP-I1-034: marker_right_clicked → delete_markers."""
    app, window = app_and_window
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    app.handle_command(
        {
            "command": "set_calibration_points",
            "markers": [
                {"name": "eye_outer_left", "operator_xy": [100, 200]},
                {"name": "eye_outer_right", "operator_xy": [300, 200]},
            ],
            "merge": True,
        }
    )
    window._calibration._on_marker_right_clicked("eye_outer_left")
    qtbot.wait(20)
    d = app.handle_command({"command": "dump_calibration"})
    names = [m["name"] for m in d.payload["calibration"]["markers"]]
    assert "eye_outer_left" not in names
    assert "eye_outer_right" in names


def test_calibration_view_hit_test_marker(app_and_window) -> None:
    """WP-I1-034: _hit_test_marker returns the name of the closest marker
    within MARKER_HIT_RADIUS_PX, else None."""
    from PySide6.QtCore import QPointF

    _app, window = app_and_window
    view = window._calibration._portrait
    view.set_marker_positions(
        [("eye_outer_left", 100.0, 200.0), ("mouth_corner_right", 300.0, 400.0)],
        draggable_names={"eye_outer_left", "mouth_corner_right"},
    )
    # Within radius of the first marker.
    pt = QPointF(102.0, 201.0)
    assert view._hit_test_marker(pt) == "eye_outer_left"
    # Far from any marker.
    pt = QPointF(800.0, 800.0)
    assert view._hit_test_marker(pt) is None


def test_calibration_pane_compute_detected_positions_uses_rig(
    app_and_window, aeri_master: Path, qtbot
) -> None:
    """WP-I1-028: _compute_detected_positions returns a dict keyed by
    marker name, with image-space positions from the rig's raw face mesh.
    Empty when no rig is loaded."""
    app, window = app_and_window
    pane = window._calibration
    # No rig → None.
    assert pane._compute_detected_positions() is None
    # Load rig.
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    qtbot.wait(20)
    detected = pane._compute_detected_positions()
    assert detected is not None
    assert len(detected) >= 6  # at least the 6 required markers
    for name, (x, y) in detected.items():
        assert isinstance(name, str)
        assert x >= 0 and y >= 0


def test_calibration_pane_no_modal_dialog_apis_in_source() -> None:
    """Source check: spec forbids modal dialogs in response to LLM commands.
    Operator-side click handlers also avoid modals (we use the log pane for
    confirmations)."""
    src_path = (
        Path(__file__).parent.parent
        / "src"
        / "openrepose"
        / "gui"
        / "calibration.py"
    )
    src = src_path.read_text(encoding="utf-8")
    for forbidden in (
        "QMessageBox",
        ".exec(",
        ".exec_(",
    ):
        assert forbidden not in src, (
            f"{forbidden} found in gui/calibration.py"
        )
