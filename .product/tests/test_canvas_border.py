"""Tests for the canvas-border outline option (WP-I1-032).

Spec: render_openpose accepts a `canvas_border_color` kwarg; when set, draws
a 2px rectangle around the canvas perimeter so the operator can see the
export bounds when frame_scale shrinks the figure.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from openrepose.app import App
from openrepose.openpose_schema import OPENPOSE_BODY_COUNT
from openrepose.render.draw_openpose import (
    BODY_18_COLOR_BY_INDEX,
    _hex_to_bgr,
)


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
    )


# --- color helpers ----------------------------------------------------------


def test_hex_to_bgr_white():
    assert _hex_to_bgr("#ffffff") == (255, 255, 255)


def test_hex_to_bgr_red():
    assert _hex_to_bgr("#ff0000") == (0, 0, 255)


def test_hex_to_bgr_no_hash():
    assert _hex_to_bgr("00ff00") == (0, 255, 0)


def test_hex_to_bgr_empty_returns_none():
    assert _hex_to_bgr("") is None
    assert _hex_to_bgr(None) is None


def test_hex_to_bgr_invalid_returns_none():
    assert _hex_to_bgr("not a color") is None
    assert _hex_to_bgr("#zz1122") is None


# --- BODY_18_COLOR_BY_INDEX -------------------------------------------------


def test_body_18_color_by_index_length():
    assert len(BODY_18_COLOR_BY_INDEX) == OPENPOSE_BODY_COUNT


def test_body_18_color_by_index_all_tuples():
    for c in BODY_18_COLOR_BY_INDEX:
        assert isinstance(c, tuple)
        assert len(c) == 3
        for v in c:
            assert 0 <= int(v) <= 255


# --- renderer draws border --------------------------------------------------


def test_render_with_white_border_draws_white_perimeter(
    app: App, aeri_master: Path, tmp_path: Path
):
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    out_path = tmp_path / "with_border.png"
    r = app.handle_command(
        {
            "command": "snapshot",
            "target": "openpose_viewport",
            "out_path": str(out_path),
        }
    )
    assert r.status == "ok", r.payload
    img = cv2.imread(str(out_path))
    h, w = img.shape[:2]
    # Top row should have at least one white pixel (border).
    top_white = np.all(img[0:2, :] == [255, 255, 255], axis=-1).sum()
    bottom_white = np.all(img[h - 2 : h, :] == [255, 255, 255], axis=-1).sum()
    assert top_white > 0, "expected white border pixels along the top"
    assert bottom_white > 0, "expected white border pixels along the bottom"


def test_render_without_border_no_perimeter_white(
    app: App, aeri_master: Path, tmp_path: Path
):
    """Setting canvas_border_color to empty string disables the border."""
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    app.settings.update(canvas_border_color="")
    out_path = tmp_path / "no_border.png"
    r = app.handle_command(
        {
            "command": "snapshot",
            "target": "openpose_viewport",
            "out_path": str(out_path),
        }
    )
    assert r.status == "ok"
    img = cv2.imread(str(out_path))
    h, w = img.shape[:2]
    # The very top row should be all-black (no border).
    top_row = img[0, :]
    assert (top_row == [0, 0, 0]).all(), "no border expected when color is empty"


def test_render_with_invalid_border_skips_border(
    app: App, aeri_master: Path, tmp_path: Path
):
    """Invalid color string → no border drawn (no crash)."""
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    app.settings.update(canvas_border_color="not-a-color")
    out_path = tmp_path / "invalid_border.png"
    r = app.handle_command(
        {
            "command": "snapshot",
            "target": "openpose_viewport",
            "out_path": str(out_path),
        }
    )
    assert r.status == "ok"
    img = cv2.imread(str(out_path))
    top_row = img[0, :]
    assert (top_row == [0, 0, 0]).all()
