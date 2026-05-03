"""Tests for WP-I1-030: PNG output alongside JSON, pretty-printed JSON."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import pytest

from openrepose.app import App


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
    )


def _import_aeri(app: App, aeri_master: Path) -> None:
    r = app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    assert r.status == "ok", r.payload


# --- PNG output -------------------------------------------------------------


def test_export_single_writes_both_json_and_png(
    app: App, aeri_master: Path
) -> None:
    _import_aeri(app, aeri_master)
    r = app.handle_command({"command": "export_single"})
    assert r.status == "ok"
    files = [Path(f) for f in r.payload["files"]]
    assert len(files) == 2
    extensions = {f.suffix for f in files}
    assert extensions == {".json", ".png"}
    json_file = next(f for f in files if f.suffix == ".json")
    png_file = next(f for f in files if f.suffix == ".png")
    assert json_file.exists()
    assert png_file.exists()
    # PNG decodes + non-empty.
    img = cv2.imread(str(png_file))
    assert img is not None
    assert img.shape[0] > 0 and img.shape[1] > 0


def test_export_batch_writes_png_per_angle(
    app: App, aeri_master: Path
) -> None:
    _import_aeri(app, aeri_master)
    r = app.handle_command({"command": "export_batch"})
    assert r.status == "ok"
    files = [Path(f) for f in r.payload["files"]]
    # 13 JSONs + 13 PNGs + 1 manifest.
    assert len(files) == 27
    json_files = [f for f in files if f.suffix == ".json" and "manifest" not in f.name]
    png_files = [f for f in files if f.suffix == ".png"]
    assert len(json_files) == 13
    assert len(png_files) == 13
    # Each JSON has a matching PNG (same stem, different suffix).
    json_stems = {f.with_suffix("").name for f in json_files}
    png_stems = {f.with_suffix("").name for f in png_files}
    assert json_stems == png_stems


def test_png_decodes_for_each_angle(
    app: App, aeri_master: Path
) -> None:
    _import_aeri(app, aeri_master)
    r = app.handle_command({"command": "export_batch"})
    pngs = [Path(f) for f in r.payload["files"] if f.endswith(".png")]
    for p in pngs:
        img = cv2.imread(str(p))
        assert img is not None, f"failed to decode {p.name}"
        assert img.shape[0] > 0 and img.shape[1] > 0


# --- pretty JSON ------------------------------------------------------------


def test_export_single_json_is_pretty_printed(
    app: App, aeri_master: Path
) -> None:
    _import_aeri(app, aeri_master)
    r = app.handle_command({"command": "export_single"})
    json_file = next(Path(f) for f in r.payload["files"] if f.endswith(".json"))
    text = json_file.read_text(encoding="utf-8")
    # Pretty-printed = contains newlines + indentation.
    assert "\n" in text, "JSON should contain newlines (pretty-printed)"
    assert "  " in text, "JSON should contain 2-space indentation"
    # Round-trips cleanly.
    parsed = json.loads(text)
    assert parsed[0]["people"][0]["pose_keypoints_2d"]


def test_export_batch_json_is_pretty_printed(
    app: App, aeri_master: Path
) -> None:
    _import_aeri(app, aeri_master)
    r = app.handle_command({"command": "export_batch"})
    json_files = [
        Path(f)
        for f in r.payload["files"]
        if f.endswith(".json") and "manifest" not in f
    ]
    for jf in json_files:
        text = jf.read_text(encoding="utf-8")
        assert "\n" in text
        assert "  " in text
