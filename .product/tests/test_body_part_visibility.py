"""Tests for per-body-part visibility toggles (WP-I1-017).

Spec: `.gov/spec/openrepose_v0_1.md` Feature 1 / OpenPose Schema Mapping
+ LLM Control Surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from openrepose.app import App
from openrepose.openpose_schema import (
    BODY_18_INDICES_BY_GROUP,
    BODY_GROUPS,
    apply_body_part_visibility,
    default_body_part_visibility,
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


def test_body_groups_complete():
    assert set(BODY_GROUPS) == {"face", "body_torso", "arms", "legs", "hands"}


def test_default_body_part_visibility_all_true():
    d = default_body_part_visibility()
    for g in BODY_GROUPS:
        assert d[g] is True


def test_apply_visibility_none_returns_inputs():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    b, f = apply_body_part_visibility(body18, face70, None)
    assert b is body18
    assert f is face70


def test_apply_visibility_all_true_returns_inputs():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    b, f = apply_body_part_visibility(
        body18, face70, default_body_part_visibility()
    )
    assert np.array_equal(b, body18)
    assert np.array_equal(f, face70)


def test_apply_visibility_face_off_zeros_face70_and_body_face_indices():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    mask = default_body_part_visibility()
    mask["face"] = False
    b, f = apply_body_part_visibility(body18, face70, mask)
    assert not f.any()
    for idx in BODY_18_INDICES_BY_GROUP["face"]:
        assert b[idx] == False  # noqa: E712
    # Non-face body indices remain visible.
    for idx in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13):
        assert b[idx] == True  # noqa: E712


def test_apply_visibility_legs_off_zeros_only_leg_indices():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    mask = default_body_part_visibility()
    mask["legs"] = False
    b, f = apply_body_part_visibility(body18, face70, mask)
    assert f.all()  # face untouched
    for idx in BODY_18_INDICES_BY_GROUP["legs"]:
        assert b[idx] == False  # noqa: E712
    for idx in (0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 14, 15, 16, 17):
        assert b[idx] == True  # noqa: E712


def test_apply_visibility_unknown_group_raises():
    body18 = np.ones((18,), dtype=bool)
    face70 = np.ones((70,), dtype=bool)
    with pytest.raises(ValueError):
        apply_body_part_visibility(body18, face70, {"made_up": False})


def test_apply_visibility_with_float_conf_array():
    """body_18_conf is float; helper must zero floats too."""
    body18 = np.ones((18,), dtype=np.float32)
    face70 = np.ones((70,), dtype=bool)
    mask = default_body_part_visibility()
    mask["arms"] = False
    b, _ = apply_body_part_visibility(body18, face70, mask)
    for idx in BODY_18_INDICES_BY_GROUP["arms"]:
        assert b[idx] == 0.0


# --- dispatcher commands ----------------------------------------------------


def test_get_body_part_visibility_returns_defaults(app: App) -> None:
    r = app.handle_command({"command": "get_body_part_visibility"})
    assert r.status == "ok"
    bpv = r.payload["body_part_visibility"]
    for g in BODY_GROUPS:
        assert bpv[g] is True


def test_set_body_part_visibility_single_flag(app: App) -> None:
    r = app.handle_command(
        {"command": "set_body_part_visibility", "legs": False}
    )
    assert r.status == "ok"
    assert r.payload["body_part_visibility"]["legs"] is False
    assert r.payload["updated"] == {"legs": False}
    # Other flags preserved.
    assert r.payload["body_part_visibility"]["face"] is True


def test_set_body_part_visibility_multiple_flags(app: App) -> None:
    r = app.handle_command(
        {
            "command": "set_body_part_visibility",
            "legs": False,
            "arms": False,
        }
    )
    assert r.status == "ok"
    assert r.payload["body_part_visibility"]["legs"] is False
    assert r.payload["body_part_visibility"]["arms"] is False


def test_set_body_part_visibility_unknown_group_rejected(app: App) -> None:
    r = app.handle_command(
        {"command": "set_body_part_visibility", "made_up": False}
    )
    assert r.status == "error"
    assert "unknown" in r.payload["reason"].lower()


def test_set_body_part_visibility_non_bool_rejected(app: App) -> None:
    r = app.handle_command(
        {"command": "set_body_part_visibility", "legs": "off"}
    )
    assert r.status == "error"
    assert "boolean" in r.payload["reason"].lower()


def test_set_body_part_visibility_empty_payload_rejected(app: App) -> None:
    r = app.handle_command({"command": "set_body_part_visibility"})
    assert r.status == "error"
    assert "at least one" in r.payload["reason"].lower()


# --- end-to-end through export ----------------------------------------------


def test_export_with_legs_off_zeros_leg_keypoints(
    app: App, aeri_master: Path
) -> None:
    """Setting legs=False should zero body_18 leg indices in the JSON."""
    app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    app.handle_command(
        {"command": "set_body_part_visibility", "legs": False}
    )
    r = app.handle_command({"command": "export_single"})
    assert r.status == "ok", r.payload
    written = Path(r.payload["files"][0])
    obj = json.loads(written.read_text(encoding="utf-8"))
    pose = obj[0]["people"][0]["pose_keypoints_2d"]
    # body_18 has 18 keypoints * 3 floats each.
    assert len(pose) == 18 * 3
    # Leg indices: 9, 10, 12, 13. Each is x, y, c → triple at i*3 to i*3+3.
    for idx in BODY_18_INDICES_BY_GROUP["legs"]:
        triple = pose[idx * 3 : idx * 3 + 3]
        assert triple == [0.0, 0.0, 0.0]
    # Non-leg body indices may be visible (assert at least one is non-zero).
    non_leg_visible = False
    for idx in (0, 1, 2, 5):
        triple = pose[idx * 3 : idx * 3 + 3]
        if any(t != 0.0 for t in triple):
            non_leg_visible = True
            break
    assert non_leg_visible, "expected at least one non-leg body keypoint visible"


def test_export_with_face_off_zeros_face_70_and_body_face_kps(
    app: App, aeri_master: Path
) -> None:
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
    r = app.handle_command({"command": "export_single"})
    assert r.status == "ok"
    obj = json.loads(Path(r.payload["files"][0]).read_text(encoding="utf-8"))
    face = obj[0]["people"][0]["face_keypoints_2d"]
    # Face: 70 keypoints * 3 floats.
    assert len(face) == 70 * 3
    # ALL face triples must be (0, 0, 0) when face is suppressed.
    for i in range(70):
        triple = face[i * 3 : i * 3 + 3]
        assert triple == [0.0, 0.0, 0.0]
    # Body face indices (nose 0, eyes 14/15, ears 16/17) also zeroed.
    pose = obj[0]["people"][0]["pose_keypoints_2d"]
    for idx in BODY_18_INDICES_BY_GROUP["face"]:
        triple = pose[idx * 3 : idx * 3 + 3]
        assert triple == [0.0, 0.0, 0.0]


def test_export_default_all_visible_is_unchanged_baseline(
    app: App, aeri_master: Path
) -> None:
    """Regression: with default state.body_part_visibility (all True), the
    exported JSON is identical to the pre-WP-I1-017 baseline. We don't
    have a stored baseline, so just assert at least one keypoint is
    non-zero in each section."""
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
    face = obj[0]["people"][0]["face_keypoints_2d"]
    assert any(v != 0.0 for v in pose)
    assert any(v != 0.0 for v in face)


def test_state_json_has_body_part_visibility_block(app: App) -> None:
    app.handle_command({"command": "dump_state"})
    state = json.loads(app.state.state_path.read_text(encoding="utf-8"))
    assert "body_part_visibility" in state
    bpv = state["body_part_visibility"]
    for g in BODY_GROUPS:
        assert bpv[g] is True
