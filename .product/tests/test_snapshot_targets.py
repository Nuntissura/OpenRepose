"""Snapshot subsystem: every named target produces a valid PNG."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openrepose.app import App
from openrepose.snapshot import VALID_TARGETS


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
    )


@pytest.mark.parametrize("target", list(VALID_TARGETS))
def test_each_target_produces_png(app: App, aeri_master: Path, target: str) -> None:
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    r = app.handle_command({"command": "snapshot", "target": target})
    assert r.status == "ok", r.payload
    out = Path(r.payload["out_path"])
    assert out.exists()
    assert out.stat().st_size > 100, f"PNG suspiciously small: {out.stat().st_size}"


def test_unknown_target_rejected(app: App, aeri_master: Path) -> None:
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    r = app.handle_command({"command": "snapshot", "target": "nonexistent"})
    assert r.status == "error"


def test_manifest_jsonl_has_one_line_per_snapshot(app: App, aeri_master: Path) -> None:
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    for target in ("3d_viewport", "openpose_viewport", "inspector_pane"):
        app.handle_command({"command": "snapshot", "target": target})

    manifest = app.outputs_root / ".runtime" / "snapshots.jsonl"
    assert manifest.exists()
    lines = manifest.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    for line in lines:
        obj = json.loads(line)
        assert "captured_at" in obj
        assert "target" in obj
        assert "out_path" in obj


def test_state_records_snapshot_paths(app: App, aeri_master: Path) -> None:
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    app.handle_command({"command": "snapshot", "target": "3d_viewport"})
    state = app.state.to_dict()
    assert len(state["snapshots"]) == 1
    assert state["snapshots"][0]["target"] == "3d_viewport"
    assert Path(state["snapshots"][0]["out_path"]).exists()


def test_widget_targets_work_without_rig(app: App) -> None:
    """Widget-grab targets must be callable with no rig (placeholder render)."""
    for target in ("inspector_pane", "log_pane", "options_pane", "status_bar", "toolbar"):
        r = app.handle_command({"command": "snapshot", "target": target})
        assert r.status == "ok", r.payload


def test_viewport_targets_require_rig(app: App) -> None:
    for target in ("3d_viewport", "openpose_viewport"):
        r = app.handle_command({"command": "snapshot", "target": target})
        assert r.status == "error"


def test_full_window_includes_viewports_when_rig_loaded(app: App, aeri_master: Path) -> None:
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    r = app.handle_command({"command": "snapshot", "target": "full_window"})
    assert r.status == "ok"
    out = Path(r.payload["out_path"])
    # The composed canvas is 1280x800 per LAYOUT.
    import cv2

    img = cv2.imread(str(out))
    assert img is not None
    assert img.shape[0] == 800
    assert img.shape[1] == 1280
