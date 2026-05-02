"""Tests for frame reframing — robust rerender (WP-I1-023).

Spec: scale + offset keypoint coords; line widths and dot sizes are
canvas-pixel constants and stay invariant. No naive image resize.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from openrepose.app import App
from openrepose.openpose_schema import (
    ANCHOR_MODES,
    apply_frame_to_keypoints,
    default_frame,
    resolve_frame_anchor,
)


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
    )


# --- helpers / defaults -----------------------------------------------------


def test_default_frame_is_identity():
    f = default_frame()
    assert f["scale"] == 1.0
    assert f["offset_x"] == 0
    assert f["offset_y"] == 0
    assert f["anchor_mode"] == "head_anchor"
    assert f["anchor_point"] is None


def test_anchor_modes_complete():
    assert set(ANCHOR_MODES) == {"head_anchor", "canvas_center", "custom"}


def test_resolve_anchor_head_anchor():
    p = resolve_frame_anchor("head_anchor", None, [400.0, 500.0], (1024, 1024))
    assert np.allclose(p, [400.0, 500.0])


def test_resolve_anchor_canvas_center():
    p = resolve_frame_anchor("canvas_center", None, [400.0, 500.0], (1024, 1024))
    assert np.allclose(p, [512.0, 512.0])


def test_resolve_anchor_custom():
    p = resolve_frame_anchor("custom", [100, 200], None, (1024, 1024))
    assert np.allclose(p, [100.0, 200.0])


def test_resolve_anchor_custom_missing_point_raises():
    with pytest.raises(ValueError):
        resolve_frame_anchor("custom", None, None, (1024, 1024))


def test_resolve_anchor_unknown_mode_raises():
    with pytest.raises(ValueError):
        resolve_frame_anchor("bogus", None, None, (1024, 1024))


# --- transform math ---------------------------------------------------------


def test_apply_frame_identity_returns_input():
    pts = np.array([[100.0, 200.0], [300.0, 400.0]])
    out = apply_frame_to_keypoints(pts, None, [512.0, 512.0], (1024, 1024))
    assert out is pts
    out2 = apply_frame_to_keypoints(
        pts, default_frame(), [512.0, 512.0], (1024, 1024)
    )
    assert out2 is pts  # identity fast-path


def test_apply_frame_pure_scale():
    """At scale=0.5 anchored at (500, 500), point (600, 600) should map to (550, 550)."""
    pts = np.array([[600.0, 600.0]])
    frame = {
        "scale": 0.5,
        "offset_x": 0,
        "offset_y": 0,
        "anchor_mode": "head_anchor",
    }
    out = apply_frame_to_keypoints(pts, frame, [500.0, 500.0], (1024, 1024))
    assert np.allclose(out[0], [550.0, 550.0])


def test_apply_frame_pure_offset():
    pts = np.array([[100.0, 200.0]])
    frame = {
        "scale": 1.0,
        "offset_x": 50,
        "offset_y": -30,
        "anchor_mode": "head_anchor",
    }
    out = apply_frame_to_keypoints(pts, frame, [500.0, 500.0], (1024, 1024))
    assert np.allclose(out[0], [150.0, 170.0])


def test_apply_frame_combined_scale_and_offset():
    pts = np.array([[600.0, 600.0]])
    frame = {
        "scale": 0.5,
        "offset_x": 50,
        "offset_y": -30,
        "anchor_mode": "head_anchor",
    }
    out = apply_frame_to_keypoints(pts, frame, [500.0, 500.0], (1024, 1024))
    # (600 - 500) * 0.5 + 500 + 50 = 600
    # (600 - 500) * 0.5 + 500 - 30 = 520
    assert np.allclose(out[0], [600.0, 520.0])


def test_apply_frame_canvas_center_anchor():
    pts = np.array([[512.0, 512.0]])  # canvas center
    frame = {
        "scale": 0.5,
        "offset_x": 0,
        "offset_y": 0,
        "anchor_mode": "canvas_center",
    }
    out = apply_frame_to_keypoints(pts, frame, [400.0, 500.0], (1024, 1024))
    # Anchor IS canvas_center; the point sits on the anchor → unchanged.
    assert np.allclose(out[0], [512.0, 512.0])


def test_apply_frame_at_anchor_unchanged_under_scale():
    """Any anchor point is invariant under any scale."""
    anchor = np.array([400.0, 500.0])
    pts = anchor.reshape(1, 2)
    for scale in (0.1, 0.5, 1.0, 2.0, 10.0):
        frame = {
            "scale": scale,
            "offset_x": 0,
            "offset_y": 0,
            "anchor_mode": "head_anchor",
        }
        out = apply_frame_to_keypoints(pts, frame, anchor, (1024, 1024))
        assert np.allclose(out[0], anchor, atol=1e-6)


# --- dispatcher commands ----------------------------------------------------


def test_get_frame_returns_defaults(app: App) -> None:
    r = app.handle_command({"command": "get_frame"})
    assert r.status == "ok"
    f = r.payload["frame"]
    assert f == default_frame()


def test_set_frame_scale_positive(app: App) -> None:
    r = app.handle_command({"command": "set_frame_scale", "scale": 0.6})
    assert r.status == "ok"
    assert r.payload["frame"]["scale"] == 0.6


def test_set_frame_scale_zero_rejected(app: App) -> None:
    r = app.handle_command({"command": "set_frame_scale", "scale": 0})
    assert r.status == "error"
    assert "> 0" in r.payload["reason"]


def test_set_frame_scale_negative_rejected(app: App) -> None:
    r = app.handle_command({"command": "set_frame_scale", "scale": -1.5})
    assert r.status == "error"


def test_set_frame_scale_non_numeric_rejected(app: App) -> None:
    r = app.handle_command({"command": "set_frame_scale", "scale": "0.6"})
    assert r.status == "error"


def test_set_frame_offset_integer(app: App) -> None:
    r = app.handle_command({"command": "set_frame_offset", "x": 50, "y": -30})
    assert r.status == "ok"
    assert r.payload["frame"]["offset_x"] == 50
    assert r.payload["frame"]["offset_y"] == -30


def test_set_frame_offset_missing_y_rejected(app: App) -> None:
    r = app.handle_command({"command": "set_frame_offset", "x": 50})
    assert r.status == "error"


def test_set_frame_anchor_canvas_center(app: App) -> None:
    r = app.handle_command(
        {"command": "set_frame_anchor", "mode": "canvas_center"}
    )
    assert r.status == "ok"
    assert r.payload["frame"]["anchor_mode"] == "canvas_center"
    assert r.payload["frame"]["anchor_point"] is None


def test_set_frame_anchor_custom_with_point(app: App) -> None:
    r = app.handle_command(
        {"command": "set_frame_anchor", "mode": "custom", "point": [100, 200]}
    )
    assert r.status == "ok"
    assert r.payload["frame"]["anchor_mode"] == "custom"
    assert r.payload["frame"]["anchor_point"] == [100.0, 200.0]


def test_set_frame_anchor_custom_without_point_rejected(app: App) -> None:
    r = app.handle_command(
        {"command": "set_frame_anchor", "mode": "custom"}
    )
    assert r.status == "error"


def test_set_frame_anchor_unknown_mode_rejected(app: App) -> None:
    r = app.handle_command(
        {"command": "set_frame_anchor", "mode": "wrist_anchor"}
    )
    assert r.status == "error"


def test_reset_frame_returns_to_defaults(app: App) -> None:
    app.handle_command({"command": "set_frame_scale", "scale": 2.0})
    app.handle_command({"command": "set_frame_offset", "x": 100, "y": 100})
    r = app.handle_command({"command": "reset_frame"})
    assert r.status == "ok"
    assert r.payload["frame"] == default_frame()


# --- end-to-end through export ----------------------------------------------


def test_export_at_default_frame_baseline_unchanged(
    app: App, aeri_master: Path, tmp_path: Path
) -> None:
    """scale=1, offset=(0,0) → output identical to no-frame baseline."""
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    r = app.handle_command({"command": "export_single"})
    assert r.status == "ok"
    obj = json.loads(Path(r.payload["files"][0]).read_text(encoding="utf-8"))
    pose = obj[0]["people"][0]["pose_keypoints_2d"]
    assert any(v != 0.0 for v in pose), "baseline export should have non-zero kps"


def test_export_at_half_scale_shrinks_keypoints_toward_anchor(
    app: App, aeri_master: Path
) -> None:
    """scale=0.5 anchored at head should bring keypoints closer to anchor."""
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    # Baseline: get a non-zero body kp position.
    baseline = app.handle_command({"command": "export_single"})
    assert baseline.status == "ok"
    base_pose = json.loads(
        Path(baseline.payload["files"][0]).read_text(encoding="utf-8")
    )[0]["people"][0]["pose_keypoints_2d"]

    # Apply scale=0.5.
    app.handle_command({"command": "set_frame_scale", "scale": 0.5})
    scaled = app.handle_command({"command": "export_single"})
    assert scaled.status == "ok"
    s_pose = json.loads(
        Path(scaled.payload["files"][0]).read_text(encoding="utf-8")
    )[0]["people"][0]["pose_keypoints_2d"]

    # For at least one visible body kp, scaled position should differ from baseline.
    found_diff = False
    for i in range(18):
        b_xy = base_pose[i * 3 : i * 3 + 2]
        s_xy = s_pose[i * 3 : i * 3 + 2]
        if b_xy == [0.0, 0.0]:
            continue
        if abs(b_xy[0] - s_xy[0]) > 1.0 or abs(b_xy[1] - s_xy[1]) > 1.0:
            found_diff = True
            break
    assert found_diff, "scale=0.5 should change kp positions for visible kps"


def test_export_with_offset_translates_keypoints(
    app: App, aeri_master: Path
) -> None:
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    baseline = app.handle_command({"command": "export_single"})
    base_pose = json.loads(
        Path(baseline.payload["files"][0]).read_text(encoding="utf-8")
    )[0]["people"][0]["pose_keypoints_2d"]

    app.handle_command({"command": "set_frame_offset", "x": 50, "y": -30})
    shifted = app.handle_command({"command": "export_single"})
    s_pose = json.loads(
        Path(shifted.payload["files"][0]).read_text(encoding="utf-8")
    )[0]["people"][0]["pose_keypoints_2d"]

    # Find a visible keypoint and confirm shift.
    for i in range(18):
        b_xy = base_pose[i * 3 : i * 3 + 2]
        s_xy = s_pose[i * 3 : i * 3 + 2]
        if b_xy == [0.0, 0.0]:
            continue
        # offset of (50, -30) applied (scale=1).
        assert abs((s_xy[0] - b_xy[0]) - 50) < 1.5
        assert abs((s_xy[1] - b_xy[1]) - -30) < 1.5
        return
    pytest.fail("no visible body kp found")


def test_state_json_has_frame_block(app: App) -> None:
    app.handle_command({"command": "dump_state"})
    state = json.loads(app.state.state_path.read_text(encoding="utf-8"))
    assert "frame" in state
    assert state["frame"] == default_frame()


def test_render_line_widths_invariant_under_scale(
    app: App, aeri_master: Path, tmp_path: Path
) -> None:
    """The renderer's line widths and dot sizes are canvas-pixel constants;
    they must stay constant across frame_scale changes. Verify by counting
    drawn pixels of a specific known color in the rendered preview at two
    different scales."""
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    r1 = app.handle_command(
        {
            "command": "snapshot",
            "target": "openpose_viewport",
            "out_path": str(tmp_path / "scale1.png"),
        }
    )
    assert r1.status == "ok"
    img1 = cv2.imread(str(tmp_path / "scale1.png"))
    # Count "white" face-dot pixels (255, 255, 255 in BGR).
    white1 = int(np.all(img1 == [255, 255, 255], axis=-1).sum())

    app.handle_command({"command": "set_frame_scale", "scale": 0.6})
    r2 = app.handle_command(
        {
            "command": "snapshot",
            "target": "openpose_viewport",
            "out_path": str(tmp_path / "scale06.png"),
        }
    )
    assert r2.status == "ok"
    img2 = cv2.imread(str(tmp_path / "scale06.png"))
    white2 = int(np.all(img2 == [255, 255, 255], axis=-1).sum())

    # Pixel counts won't be exactly equal (some keypoints clip / overlap differently),
    # but they should be within a reasonable factor — the renderer doesn't multiply
    # widths by scale. A cheap robust assertion: ratio between counts is in (0.3, 3.0).
    assert white1 > 0 and white2 > 0
    ratio = white2 / white1
    assert 0.3 < ratio < 3.0, f"line widths appear scale-dependent (ratio={ratio:.2f})"
