"""Dispatcher tests for the four calibration commands.

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 2: Per-Avatar
Calibration Overlay" / Command Surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openrepose.app import App
from openrepose.calibration import REQUIRED_MARKERS, calibration_path


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
    )


# --- guards on missing avatar / rig -----------------------------------------


def test_set_calibration_points_without_avatar_fails(app: App) -> None:
    r = app.handle_command(
        {
            "command": "set_calibration_points",
            "markers": [
                {
                    "name": "eye_outer_left",
                    "operator_xy": [100, 200],
                    "mediapipe_xy": [110, 210],
                }
            ],
        }
    )
    assert r.status == "error"
    assert "avatar" in r.payload["reason"].lower()


def test_dump_calibration_without_avatar_fails(app: App) -> None:
    r = app.handle_command({"command": "dump_calibration"})
    assert r.status == "error"
    assert "avatar" in r.payload["reason"].lower()


def test_clear_calibration_without_avatar_fails(app: App) -> None:
    r = app.handle_command({"command": "clear_calibration"})
    assert r.status == "error"
    assert "avatar" in r.payload["reason"].lower()


def test_get_calibration_status_returns_defaults_without_avatar(
    app: App,
) -> None:
    r = app.handle_command({"command": "get_calibration_status"})
    assert r.status == "ok"
    assert r.payload["completeness"] == "none"
    assert r.payload["marker_count"] == 0
    assert r.payload["active_avatar"] is None


# --- end-to-end through import_portrait + aeri master -----------------------


def test_set_dump_clear_cycle_with_real_rig(
    app: App, aeri_master: Path
) -> None:
    """Full cycle: import → set 6 markers → dump (sees them) → clear (gone)."""
    r = app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    assert r.status == "ok", r.payload

    # Set six required markers; let the dispatcher derive mediapipe_xy
    # from the rig (we omit the field).
    payload_markers = [
        {"name": name, "operator_xy": [100.0 + i * 10, 200.0]}
        for i, name in enumerate(REQUIRED_MARKERS)
    ]
    r = app.handle_command(
        {
            "command": "set_calibration_points",
            "markers": payload_markers,
            "merge": False,
        }
    )
    assert r.status == "ok", r.payload
    assert r.payload["marker_count"] == 6
    assert r.payload["completeness"] == "complete"
    assert r.payload["missing_required"] == []

    # JSON written to conventional path.
    cal_p = calibration_path(app.outputs_root, "aeri")
    assert cal_p.exists()
    data = json.loads(cal_p.read_text(encoding="utf-8"))
    assert data["completeness"] == "complete"
    assert len(data["markers"]) == 6

    # Dump returns the calibration content.
    r = app.handle_command({"command": "dump_calibration"})
    assert r.status == "ok", r.payload
    assert r.payload["present"] is True
    assert r.payload["calibration"]["completeness"] == "complete"
    assert len(r.payload["calibration"]["markers"]) == 6

    # Status mirrors state.calibration.
    r = app.handle_command({"command": "get_calibration_status"})
    assert r.status == "ok"
    assert r.payload["completeness"] == "complete"
    assert r.payload["marker_count"] == 6
    assert r.payload["active_avatar"] == "aeri"
    assert r.payload["field_cached"] is True

    # Clear deletes the JSON and resets status.
    r = app.handle_command({"command": "clear_calibration"})
    assert r.status == "ok", r.payload
    assert r.payload["deleted"] is True
    assert not cal_p.exists()

    r = app.handle_command({"command": "get_calibration_status"})
    assert r.payload["completeness"] == "none"
    assert r.payload["marker_count"] == 0


def test_dump_calibration_when_none_present(
    app: App, aeri_master: Path
) -> None:
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    r = app.handle_command({"command": "dump_calibration"})
    assert r.status == "ok"
    assert r.payload["present"] is False
    assert r.payload["calibration"] is None


# --- merge vs replace -------------------------------------------------------


def test_merge_true_keeps_existing_markers(
    app: App, aeri_master: Path
) -> None:
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    # Seed with 6 markers.
    seed = [
        {"name": name, "operator_xy": [100.0 + i * 10, 200.0]}
        for i, name in enumerate(REQUIRED_MARKERS)
    ]
    app.handle_command(
        {"command": "set_calibration_points", "markers": seed, "merge": False}
    )
    # Update only one marker with merge=True.
    r = app.handle_command(
        {
            "command": "set_calibration_points",
            "markers": [{"name": "eye_outer_left", "operator_xy": [400, 400]}],
            "merge": True,
        }
    )
    assert r.status == "ok"
    assert r.payload["marker_count"] == 6
    assert r.payload["completeness"] == "complete"


def test_merge_false_replaces_existing_markers(
    app: App, aeri_master: Path
) -> None:
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    seed = [
        {"name": name, "operator_xy": [100.0 + i * 10, 200.0]}
        for i, name in enumerate(REQUIRED_MARKERS)
    ]
    app.handle_command(
        {"command": "set_calibration_points", "markers": seed, "merge": False}
    )
    r = app.handle_command(
        {
            "command": "set_calibration_points",
            "markers": [{"name": "eye_outer_left", "operator_xy": [400, 400]}],
            "merge": False,
        }
    )
    assert r.status == "ok"
    assert r.payload["marker_count"] == 1
    assert r.payload["completeness"] == "partial"


# --- validation -------------------------------------------------------------


def test_unknown_marker_name_rejected(app: App, aeri_master: Path) -> None:
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    r = app.handle_command(
        {
            "command": "set_calibration_points",
            "markers": [
                {"name": "made_up", "operator_xy": [100, 200]},
            ],
        }
    )
    assert r.status == "error"
    assert "unknown" in r.payload["reason"].lower()


def test_set_calibration_requires_markers_list(
    app: App, aeri_master: Path
) -> None:
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    r = app.handle_command({"command": "set_calibration_points"})
    assert r.status == "error"
    assert "markers" in r.payload["reason"].lower()


def test_marker_missing_operator_xy_rejected(
    app: App, aeri_master: Path
) -> None:
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    r = app.handle_command(
        {
            "command": "set_calibration_points",
            "markers": [{"name": "eye_outer_left"}],
        }
    )
    assert r.status == "error"
    assert "operator_xy" in r.payload["reason"]


# --- import auto-loads existing calibration ---------------------------------


def test_import_portrait_auto_loads_existing_calibration(
    app: App, aeri_master: Path
) -> None:
    # First import: write a calibration.
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    seed = [
        {"name": name, "operator_xy": [100.0 + i * 10, 200.0]}
        for i, name in enumerate(REQUIRED_MARKERS)
    ]
    app.handle_command(
        {"command": "set_calibration_points", "markers": seed, "merge": False}
    )

    # Re-import the same portrait; calibration should auto-load.
    r = app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    assert r.status == "ok"

    r = app.handle_command({"command": "get_calibration_status"})
    assert r.payload["completeness"] == "complete"
    assert r.payload["marker_count"] == 6
    assert r.payload["field_cached"] is True


# --- state file reflection --------------------------------------------------


def test_state_json_has_calibration_block(app: App) -> None:
    """Even with no avatar, the state.json `calibration` block is present
    with default values per spec."""
    app.handle_command({"command": "dump_state"})
    state = json.loads(app.state.state_path.read_text(encoding="utf-8"))
    assert "calibration" in state
    cb = state["calibration"]
    assert cb["completeness"] == "none"
    assert cb["marker_count"] == 0
    assert cb["missing_required"] == []
    assert cb["field_cached"] is False
    assert cb["active_avatar"] is None
    assert cb["loaded_from"] is None
    assert cb["last_dump_at"] is None


def test_dump_calibration_marks_last_dump_at(
    app: App, aeri_master: Path
) -> None:
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    seed = [
        {"name": name, "operator_xy": [100.0 + i * 10, 200.0]}
        for i, name in enumerate(REQUIRED_MARKERS)
    ]
    app.handle_command(
        {"command": "set_calibration_points", "markers": seed, "merge": False}
    )

    r0 = app.handle_command({"command": "get_calibration_status"})
    assert r0.payload["last_dump_at"] is None

    app.handle_command({"command": "dump_calibration"})

    r1 = app.handle_command({"command": "get_calibration_status"})
    assert r1.payload["last_dump_at"] is not None
