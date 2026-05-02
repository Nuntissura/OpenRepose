"""Tests for the `calibration_overlay` snapshot target.

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 2 / Snapshot Target".
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from openrepose.app import App
from openrepose.calibration import REQUIRED_MARKERS, Calibration, Marker
from openrepose.render.draw_calibration import render_calibration_overlay
from openrepose.snapshot import VALID_TARGETS, snapshot


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
    )


def _calibration_with_six_markers() -> Calibration:
    return Calibration(
        avatar_slug="aeri",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=tuple(
            Marker(
                name=n,
                operator_xy=(150.0 + i * 80, 200.0 + (i % 2) * 30),
                mediapipe_xy=(140.0 + i * 80, 200.0 + (i % 2) * 30),
            )
            for i, n in enumerate(REQUIRED_MARKERS)
        ),
        created_at="",
        updated_at="",
    )


# --- target registration ----------------------------------------------------


def test_calibration_overlay_in_valid_targets():
    assert "calibration_overlay" in VALID_TARGETS


# --- direct renderer --------------------------------------------------------


def test_render_with_no_portrait_no_calibration_returns_canvas():
    img = render_calibration_overlay(None, None, fallback_size=(640, 480))
    assert img.shape == (480, 640, 3)
    assert img.dtype == np.uint8


def test_render_with_calibration_no_portrait_draws_markers():
    cal = _calibration_with_six_markers()
    img = render_calibration_overlay(None, cal, fallback_size=(1024, 1024))
    assert img.shape == (1024, 1024, 3)
    # Some non-background pixels should exist where markers were drawn.
    bg_mask = np.all(img == [32, 32, 32], axis=-1)
    assert (~bg_mask).any(), "no marker pixels drawn"


def test_render_with_real_portrait_uses_image(
    aeri_master: Path,
):
    cal = _calibration_with_six_markers()
    img = render_calibration_overlay(aeri_master, cal)
    real = cv2.imread(str(aeri_master), cv2.IMREAD_COLOR)
    assert img.shape == real.shape  # canvas size matches portrait


def test_render_missing_portrait_falls_back_to_canvas(tmp_path: Path):
    bogus = tmp_path / "no-such.png"
    img = render_calibration_overlay(bogus, None, fallback_size=(800, 600))
    assert img.shape == (600, 800, 3)


# --- through snapshot dispatcher --------------------------------------------


def test_snapshot_calibration_overlay_no_rig_no_calibration(tmp_path: Path):
    out = snapshot(
        "calibration_overlay",
        rotated=None,
        snapshots_root=tmp_path / "snaps",
        manifest_path=tmp_path / "manifest.jsonl",
    )
    assert out.exists()
    img = cv2.imread(str(out), cv2.IMREAD_COLOR)
    assert img is not None


def test_snapshot_calibration_overlay_with_calibration(tmp_path: Path):
    cal = _calibration_with_six_markers()
    out = snapshot(
        "calibration_overlay",
        rotated=None,
        snapshots_root=tmp_path / "snaps",
        manifest_path=tmp_path / "manifest.jsonl",
        calibration=cal,
    )
    assert out.exists()
    img = cv2.imread(str(out), cv2.IMREAD_COLOR)
    assert img is not None


# --- end-to-end through dispatcher ------------------------------------------


def test_snapshot_calibration_overlay_after_set_calibration(
    app: App, aeri_master: Path
):
    """Full flow: import → set 6 markers → snapshot calibration_overlay."""
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    seed = [
        {"name": name, "operator_xy": [150.0 + i * 60, 200.0 + (i % 2) * 30]}
        for i, name in enumerate(REQUIRED_MARKERS)
    ]
    app.handle_command(
        {"command": "set_calibration_points", "markers": seed, "merge": False}
    )
    r = app.handle_command(
        {"command": "snapshot", "target": "calibration_overlay"}
    )
    assert r.status == "ok", r.payload
    out_path = Path(r.payload["out_path"])
    assert out_path.exists()
    img = cv2.imread(str(out_path), cv2.IMREAD_COLOR)
    assert img is not None
    real = cv2.imread(str(aeri_master), cv2.IMREAD_COLOR)
    assert img.shape == real.shape


def test_snapshot_calibration_overlay_without_calibration(
    app: App, aeri_master: Path
):
    """Snapshot before any calibration is set still produces an image
    (renders portrait + 'no calibration markers' label)."""
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    r = app.handle_command(
        {"command": "snapshot", "target": "calibration_overlay"}
    )
    assert r.status == "ok", r.payload
    out_path = Path(r.payload["out_path"])
    assert out_path.exists()


# --- no focus theft ---------------------------------------------------------


def test_render_does_not_call_focus_apis():
    """Source check: draw_calibration must not import or call focus-stealing
    APIs (raise_, activateWindow, showNormal, setForegroundWindow)."""
    src_path = (
        Path(__file__).parent.parent
        / "src"
        / "openrepose"
        / "render"
        / "draw_calibration.py"
    )
    src = src_path.read_text(encoding="utf-8")
    for forbidden in (
        "raise_",
        "activateWindow",
        "showNormal",
        "setForegroundWindow",
    ):
        assert forbidden not in src, (
            f"{forbidden} found in render/draw_calibration.py"
        )
