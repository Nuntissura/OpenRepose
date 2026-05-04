"""WP-I1-010: per-angle metadata in export_batch manifests."""

from __future__ import annotations

import json
from pathlib import Path

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


def _manifest_from_response(response) -> dict:
    manifest = next(Path(f) for f in response.payload["files"] if Path(f).name == "manifest.json")
    return json.loads(manifest.read_text(encoding="utf-8"))


def test_export_batch_accepts_aligned_metadata_list(
    app: App, aeri_master: Path, tmp_path: Path
) -> None:
    _import_aeri(app, aeri_master)
    r = app.handle_command(
        {
            "command": "export_batch",
            "out_dir": str(tmp_path / "batch-list"),
            "angles": ["0", "her-left 15", "her-right 15"],
            "per_angle_metadata": [
                {"prompt_slug": "base", "seed": 1001},
                None,
                {"prompt_slug": "right-a", "unknown_operator_key": "kept"},
            ],
        }
    )
    assert r.status == "ok", r.payload
    assert r.payload["per_angle_metadata_count"] == 2
    manifest = _manifest_from_response(r)
    assert manifest["angles"] == ["0", "her-left 15", "her-right 15"]
    assert manifest["per_angle_metadata"] == {
        "0": {"prompt_slug": "base", "seed": 1001},
        "her-right 15": {"prompt_slug": "right-a", "unknown_operator_key": "kept"},
    }

    state = json.loads(app.state.state_path.read_text(encoding="utf-8"))
    latest = state["exports"][-1]
    assert latest["per_angle_metadata_count"] == 2
    assert latest["per_angle_metadata"]["0"]["seed"] == 1001


def test_export_batch_accepts_metadata_mapping(
    app: App, aeri_master: Path, tmp_path: Path
) -> None:
    _import_aeri(app, aeri_master)
    r = app.handle_command(
        {
            "command": "export_batch",
            "out_dir": str(tmp_path / "batch-map"),
            "angles": ["0", "her-left 15", "her-right 15"],
            "per_angle_metadata": {
                "her-left 15": {"prompt_slug": "left-a", "controlnet_strength": 0.8},
                "0": {"workflow_slug": "base-workflow"},
            },
        }
    )
    assert r.status == "ok", r.payload
    manifest = _manifest_from_response(r)
    assert manifest["per_angle_metadata"] == {
        "0": {"workflow_slug": "base-workflow"},
        "her-left 15": {"prompt_slug": "left-a", "controlnet_strength": 0.8},
    }


def test_export_batch_rejects_metadata_length_mismatch_before_write(
    app: App, aeri_master: Path, tmp_path: Path
) -> None:
    _import_aeri(app, aeri_master)
    out_dir = tmp_path / "bad-length"
    r = app.handle_command(
        {
            "command": "export_batch",
            "out_dir": str(out_dir),
            "angles": ["0", "her-left 15"],
            "per_angle_metadata": [{"prompt_slug": "only-one"}],
        }
    )
    assert r.status == "error"
    assert "length" in r.payload["reason"]
    assert not out_dir.exists()


def test_export_batch_rejects_large_metadata_before_write(
    app: App, aeri_master: Path, tmp_path: Path
) -> None:
    _import_aeri(app, aeri_master)
    out_dir = tmp_path / "too-large"
    r = app.handle_command(
        {
            "command": "export_batch",
            "out_dir": str(out_dir),
            "angles": ["0"],
            "per_angle_metadata": [{"notes": "x" * 1_000_001}],
        }
    )
    assert r.status == "error"
    assert "exceeds" in r.payload["reason"]
    assert not out_dir.exists()


def test_export_batch_rejects_mapping_key_outside_angles(
    app: App, aeri_master: Path, tmp_path: Path
) -> None:
    _import_aeri(app, aeri_master)
    out_dir = tmp_path / "bad-key"
    r = app.handle_command(
        {
            "command": "export_batch",
            "out_dir": str(out_dir),
            "angles": ["0"],
            "per_angle_metadata": {"her-left 15": {"prompt_slug": "not-exported"}},
        }
    )
    assert r.status == "error"
    assert "not present in angles" in r.payload["reason"]
    assert not out_dir.exists()
