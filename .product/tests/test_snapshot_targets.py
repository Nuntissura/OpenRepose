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


# ---------------------------------------------------------------------------
# WP-I3-008 — Triage snapshot targets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target",
    ["intake_triage_view", "task_summary_view", "library_card_with_pose"],
)
def test_triage_snapshot_targets_work_without_rig(app: App, target: str) -> None:
    """Triage targets are state-driven; no rig required."""
    r = app.handle_command({"command": "snapshot", "target": target})
    assert r.status == "ok", r.payload
    out = Path(r.payload["out_path"])
    assert out.exists()
    assert out.stat().st_size > 100


def test_triage_snapshot_reflects_intake_state(app: App) -> None:
    """task_summary_view should be larger / different bytes when state has data."""
    r1 = app.handle_command({"command": "snapshot", "target": "task_summary_view"})
    out1 = Path(r1.payload["out_path"])
    bytes_empty = out1.read_bytes()

    app.state.set_intake_state(
        active_task_id="11111111-2222-3333-4444-555555555555",
        active_task_slug="T-EXP120-001",
        pending_count=12,
        promoted_count=4,
        queue_depth=12,
    )
    r2 = app.handle_command({"command": "snapshot", "target": "task_summary_view"})
    out2 = Path(r2.payload["out_path"])
    bytes_seeded = out2.read_bytes()
    assert bytes_empty != bytes_seeded, "task_summary_view did not reflect intake state"


def test_triage_snapshot_explicit_card(app: App, tmp_path: Path) -> None:
    """library_card_with_pose accepts an explicit triage_card payload."""
    card = {
        "slug": "SF-15", "card_id": "abc123", "target_promoted": 8,
        "stability_target": 4, "promoted": 2, "stable": False, "complete": False,
    }
    # Direct call into the snapshot module so we can pass triage_card directly.
    from openrepose.snapshot import snapshot

    out = snapshot(
        target="library_card_with_pose",
        rotated=None,
        triage_card=card,
        triage_pose_path=None,
        snapshots_root=tmp_path / "snaps",
        manifest_path=tmp_path / "manifest.jsonl",
    )
    assert out.exists()
    assert out.stat().st_size > 100


def test_triage_snapshot_unknown_target_rejected(app: App) -> None:
    r = app.handle_command({"command": "snapshot", "target": "triage_typo"})
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
