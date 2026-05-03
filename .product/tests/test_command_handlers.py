"""End-to-end command handler tests against the real rig pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openrepose.app import App


@pytest.fixture
def app(tmp_path: Path) -> App:
    export_root = tmp_path / "exports"
    export_root.mkdir()
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"schema_version": 2, "export_folder": str(export_root)}),
        encoding="utf-8",
    )
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=settings_path,
    )


def test_unknown_command_returns_error(app: App) -> None:
    r = app.handle_command({"command": "nonexistent"})
    assert r.status == "error"
    assert "unknown" in r.payload["reason"].lower()
    envelope = r.to_dict()
    assert envelope["adult_production_boundary"]["acknowledgement_required"] is True
    assert "legal" in envelope["adult_production_boundary"]["operator_responsibility"]


def test_import_portrait_then_set_yaw_then_export_single(app: App, aeri_master: Path) -> None:
    r = app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    assert r.status == "ok", r.payload
    assert r.payload["face_landmark_count"] == 478

    r = app.handle_command({"command": "set_yaw_bin", "bin": "her-left 30"})
    assert r.status == "ok"
    assert r.payload["bin"] == "her-left 30"
    assert r.payload["value_deg"] == 30.0

    r = app.handle_command({"command": "export_single"})
    assert r.status == "ok", r.payload
    files = r.payload["files"]
    # WP-I1-030: export_single now writes both .json and .png.
    assert len(files) == 2
    written = next(Path(f) for f in files if f.endswith(".json"))
    assert written.exists()
    obj = json.loads(written.read_text(encoding="utf-8"))
    assert len(obj[0]["people"][0]["pose_keypoints_2d"]) == 18 * 3


def test_export_batch_default_13_angles(app: App, aeri_master: Path) -> None:
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    r = app.handle_command({"command": "export_batch"})
    assert r.status == "ok"
    files = r.payload["files"]
    # WP-I1-030: 13 JSONs + 13 PNGs + 1 manifest.
    assert len(files) == 27
    assert any("manifest.json" in f for f in files)


def test_forbidden_yaw_phrase_in_command_rejected(app: App, aeri_master: Path) -> None:
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    r = app.handle_command({"command": "set_yaw_bin", "bin": "image-right 30"})
    assert r.status == "error"
    assert "forbidden" in r.payload["reason"].lower()


def test_export_without_portrait_fails(app: App) -> None:
    r = app.handle_command({"command": "export_single"})
    assert r.status == "error"
    assert "portrait" in r.payload["reason"].lower()


def test_state_file_reflects_command_progress(app: App, aeri_master: Path) -> None:
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    state = json.loads(app.state.state_path.read_text(encoding="utf-8"))
    assert state["rig"]["status"] == "ok"
    assert state["portrait"] == str(aeri_master)
    assert state["avatar_slug"] == "aeri"
    assert state["last_command"]["command"] == "import_portrait"
    assert state["last_command"]["status"] == "ok"


def test_snapshot_without_rig_fails_for_viewport_targets(app: App) -> None:
    """3D and OpenPose viewport targets need a rig; widget targets do not.
    Updated in WP-I0-003: snapshot is now real, but viewport targets need rig."""
    r = app.handle_command({"command": "snapshot", "target": "3d_viewport"})
    assert r.status == "error"
    assert "rotated rig" in r.payload["reason"].lower()


def test_dump_state_writes_file(app: App) -> None:
    r = app.handle_command({"command": "dump_state"})
    assert r.status == "ok"
    assert r.payload["adult_production_boundary"]["acknowledgement_required"] is True
    out = Path(r.payload["out_path"])
    assert out.exists()
    parsed = json.loads(out.read_text(encoding="utf-8"))
    assert parsed["version"] == "0.1"
    assert parsed["adult_production_boundary"]["acknowledgement_required"] is True


def test_clear_outputs_scope_validation(app: App) -> None:
    r = app.handle_command({"command": "clear_outputs", "scope": "bogus"})
    assert r.status == "error"
    r = app.handle_command({"command": "clear_outputs", "scope": "all"})
    assert r.status == "ok"
