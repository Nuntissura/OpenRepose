"""Tests for per-marker visibility toggles (WP-I1-029).

Spec: per-marker overrides on top of WP-I1-017 group flags. Per-marker
is the authoritative layer.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from openrepose.app import App
from openrepose.openpose_schema import (
    BODY_18_INDICES_BY_GROUP,
    MARKER_SCHEMAS,
    apply_body_part_visibility,
    apply_marker_visibility,
    default_body_part_visibility,
    default_marker_visibility,
)


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
    )


# --- schema layer -----------------------------------------------------------


def test_marker_schemas_complete():
    assert set(MARKER_SCHEMAS) == {"body_18", "face_70"}


def test_default_marker_visibility_empty():
    d = default_marker_visibility()
    assert d == {"body_18": {}, "face_70": {}}


def test_apply_marker_visibility_none_returns_inputs():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    b, f = apply_marker_visibility(body18, face70, None)
    assert b is body18 and f is face70


def test_apply_marker_visibility_empty_returns_inputs():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    b, f = apply_marker_visibility(
        body18, face70, default_marker_visibility()
    )
    assert b is body18 and f is face70


def test_apply_marker_visibility_single_body_index():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    b, _ = apply_marker_visibility(
        body18, face70, {"body_18": {3: False}}
    )
    assert b[3] == False  # noqa: E712
    assert b[2] == True  # noqa: E712 - other indices unaffected


def test_apply_marker_visibility_single_face_index():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    _, f = apply_marker_visibility(
        body18, face70, {"face_70": {12: False}}
    )
    assert f[12] == False  # noqa: E712
    assert f[11] == True  # noqa: E712


def test_apply_marker_visibility_string_index_keys():
    """JSON round-trip can produce string keys (JSON object keys are strings).
    The helper must accept stringified ints."""
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    b, _ = apply_marker_visibility(
        body18, face70, {"body_18": {"4": False}}
    )
    assert b[4] == False  # noqa: E712


def test_apply_marker_visibility_unknown_schema_raises():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    with pytest.raises(ValueError):
        apply_marker_visibility(
            body18, face70, {"hand_21": {0: False}}
        )


def test_apply_marker_visibility_out_of_range_raises():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    with pytest.raises(IndexError):
        apply_marker_visibility(
            body18, face70, {"body_18": {99: False}}
        )


# --- precedence interaction with body-part group flags ----------------------


def test_per_marker_overrides_group_off():
    """face group=False suppresses face_70 entirely; per-marker face_70[27]=True
    restores that one keypoint."""
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    bpv = default_body_part_visibility()
    bpv["face"] = False
    body18, face70 = apply_body_part_visibility(body18, face70, bpv)
    assert not face70.any()  # all face suppressed
    body18, face70 = apply_marker_visibility(
        body18, face70, {"face_70": {27: True}}
    )
    assert face70[27] == True  # noqa: E712 - restored
    assert face70[26] == False  # noqa: E712 - still suppressed


def test_per_marker_overrides_group_on():
    """legs group=True; per-marker body_18[9]=False suppresses one leg keypoint."""
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    body18, face70 = apply_body_part_visibility(
        body18, face70, default_body_part_visibility()
    )
    body18, face70 = apply_marker_visibility(
        body18, face70, {"body_18": {9: False}}
    )
    assert body18[9] == False  # noqa: E712 - suppressed
    assert body18[10] == True  # noqa: E712 - other leg kp untouched


# --- dispatcher commands ----------------------------------------------------


def test_get_marker_visibility_returns_empty(app: App) -> None:
    r = app.handle_command({"command": "get_marker_visibility"})
    assert r.status == "ok"
    assert r.payload["marker_visibility"] == {"body_18": {}, "face_70": {}}


def test_set_marker_visibility_single(app: App) -> None:
    r = app.handle_command(
        {
            "command": "set_marker_visibility",
            "schema": "body_18",
            "index": 4,
            "visible": False,
        }
    )
    assert r.status == "ok"
    assert r.payload["marker_visibility"]["body_18"] == {"4": False}
    assert r.payload["updated_count"] == 1


def test_set_marker_visibility_bulk(app: App) -> None:
    r = app.handle_command(
        {
            "command": "set_marker_visibility",
            "schema": "face_70",
            "indices": [10, 20, 30],
            "visible": False,
        }
    )
    assert r.status == "ok"
    assert r.payload["marker_visibility"]["face_70"] == {
        "10": False,
        "20": False,
        "30": False,
    }
    assert r.payload["updated_count"] == 3


def test_set_marker_visibility_unknown_schema_rejected(app: App) -> None:
    r = app.handle_command(
        {
            "command": "set_marker_visibility",
            "schema": "hand_21",
            "index": 0,
            "visible": False,
        }
    )
    assert r.status == "error"
    assert "schema" in r.payload["reason"].lower()


def test_set_marker_visibility_missing_visible_rejected(app: App) -> None:
    r = app.handle_command(
        {"command": "set_marker_visibility", "schema": "body_18", "index": 4}
    )
    assert r.status == "error"
    assert "visible" in r.payload["reason"].lower()


def test_set_marker_visibility_both_index_and_indices_rejected(app: App) -> None:
    r = app.handle_command(
        {
            "command": "set_marker_visibility",
            "schema": "body_18",
            "index": 4,
            "indices": [5, 6],
            "visible": False,
        }
    )
    assert r.status == "error"
    assert "exactly one" in r.payload["reason"].lower()


def test_set_marker_visibility_out_of_range_rejected(app: App) -> None:
    r = app.handle_command(
        {
            "command": "set_marker_visibility",
            "schema": "body_18",
            "index": 99,
            "visible": False,
        }
    )
    assert r.status == "error"
    assert "out of range" in r.payload["reason"].lower()


def test_reset_marker_visibility_clears_overrides(app: App) -> None:
    app.handle_command(
        {
            "command": "set_marker_visibility",
            "schema": "body_18",
            "index": 4,
            "visible": False,
        }
    )
    r = app.handle_command({"command": "reset_marker_visibility"})
    assert r.status == "ok"
    assert r.payload["marker_visibility"] == {"body_18": {}, "face_70": {}}


# --- end-to-end through export ----------------------------------------------


def test_export_with_single_body_marker_off(
    app: App, aeri_master: Path
) -> None:
    """Suppress body_18[4] (right_wrist); only that triple should be zero."""
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    app.handle_command(
        {
            "command": "set_marker_visibility",
            "schema": "body_18",
            "index": 4,
            "visible": False,
        }
    )
    r = app.handle_command({"command": "export_single"})
    assert r.status == "ok"
    obj = json.loads(Path(r.payload["files"][0]).read_text(encoding="utf-8"))
    pose = obj[0]["people"][0]["pose_keypoints_2d"]
    assert pose[4 * 3 : 4 * 3 + 3] == [0.0, 0.0, 0.0]
    # Other body indices may still be visible.


def test_per_marker_overrides_face_group_off(
    app: App, aeri_master: Path
) -> None:
    """With face group=off and face_70[4]=on, that one face kp is visible."""
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    app.handle_command(
        {"command": "set_body_part_visibility", "face": False}
    )
    app.handle_command(
        {
            "command": "set_marker_visibility",
            "schema": "face_70",
            "index": 30,
            "visible": True,
        }
    )
    r = app.handle_command({"command": "export_single"})
    assert r.status == "ok"
    obj = json.loads(Path(r.payload["files"][0]).read_text(encoding="utf-8"))
    face = obj[0]["people"][0]["face_keypoints_2d"]
    # face_70[30] should be non-zero (restored); others zero.
    triple_30 = face[30 * 3 : 30 * 3 + 3]
    assert triple_30 != [0.0, 0.0, 0.0]
    triple_29 = face[29 * 3 : 29 * 3 + 3]
    assert triple_29 == [0.0, 0.0, 0.0]


def test_state_json_has_marker_visibility_block(app: App) -> None:
    app.handle_command({"command": "dump_state"})
    state = json.loads(app.state.state_path.read_text(encoding="utf-8"))
    assert "marker_visibility" in state
    assert state["marker_visibility"] == {"body_18": {}, "face_70": {}}
