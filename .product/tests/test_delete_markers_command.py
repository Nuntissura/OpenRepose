"""Tests for the delete_markers LLM command (WP-I1-034)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openrepose.app import App
from openrepose.calibration import REQUIRED_MARKERS


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
    )


def _seed(app: App, aeri_master: Path) -> None:
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


def test_delete_markers_without_avatar_fails(app: App) -> None:
    r = app.handle_command(
        {"command": "delete_markers", "names": ["eye_outer_left"]}
    )
    assert r.status == "error"
    assert "avatar" in r.payload["reason"].lower()


def test_delete_markers_unknown_name_rejected(
    app: App, aeri_master: Path
) -> None:
    _seed(app, aeri_master)
    r = app.handle_command(
        {"command": "delete_markers", "names": ["made_up"]}
    )
    assert r.status == "error"
    assert "unknown" in r.payload["reason"].lower()


def test_delete_markers_empty_list_rejected(
    app: App, aeri_master: Path
) -> None:
    _seed(app, aeri_master)
    r = app.handle_command({"command": "delete_markers", "names": []})
    assert r.status == "error"


def test_delete_markers_missing_names_rejected(
    app: App, aeri_master: Path
) -> None:
    _seed(app, aeri_master)
    r = app.handle_command({"command": "delete_markers"})
    assert r.status == "error"


def test_delete_markers_single_removes_one(
    app: App, aeri_master: Path
) -> None:
    _seed(app, aeri_master)
    r = app.handle_command(
        {"command": "delete_markers", "names": ["eye_outer_left"]}
    )
    assert r.status == "ok"
    assert r.payload["deleted_count"] == 1
    assert r.payload["remaining"] == 5
    # Confirm via dump.
    d = app.handle_command({"command": "dump_calibration"})
    names = [m["name"] for m in d.payload["calibration"]["markers"]]
    assert "eye_outer_left" not in names
    assert len(names) == 5


def test_delete_markers_bulk_removes_multiple(
    app: App, aeri_master: Path
) -> None:
    _seed(app, aeri_master)
    r = app.handle_command(
        {
            "command": "delete_markers",
            "names": ["eye_outer_left", "mouth_corner_right", "jaw_corner_left"],
        }
    )
    assert r.status == "ok"
    assert r.payload["deleted_count"] == 3
    assert r.payload["remaining"] == 3


def test_delete_markers_no_match_is_noop(
    app: App, aeri_master: Path
) -> None:
    """Deleting a marker that's not currently in the calibration is a no-op."""
    _seed(app, aeri_master)
    r = app.handle_command(
        {"command": "delete_markers", "names": ["nose_tip"]}
    )
    assert r.status == "ok"
    assert r.payload["deleted_count"] == 0
    assert r.payload["remaining"] == 6


def test_delete_markers_with_no_existing_calibration(
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
        {"command": "delete_markers", "names": ["eye_outer_left"]}
    )
    assert r.status == "ok"
    assert r.payload["deleted_count"] == 0
    assert r.payload["remaining"] == 0
