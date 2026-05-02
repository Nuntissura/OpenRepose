"""OpenPose JSON serialization tests."""

from __future__ import annotations

import json

from openrepose.openpose_serialize import serialize, serialize_to_string
from openrepose.rig import Rig
from openrepose.rotation import rotate_yaw
from openrepose.yaw_bin import parse_bin


def test_serialize_top_level_shape(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("her-left 30"))
    payload = serialize(rotated)
    assert isinstance(payload, list)
    assert len(payload) == 1
    obj = payload[0]
    assert "people" in obj
    assert "canvas_width" in obj
    assert "canvas_height" in obj
    assert isinstance(obj["canvas_width"], int)
    assert isinstance(obj["canvas_height"], int)


def test_serialize_person_shape(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("her-left 30"))
    payload = serialize(rotated)
    p = payload[0]["people"][0]
    assert "pose_keypoints_2d" in p
    assert "face_keypoints_2d" in p
    assert "hand_left_keypoints_2d" in p
    assert "hand_right_keypoints_2d" in p


def test_serialize_keypoint_array_lengths(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("her-left 30"))
    p = serialize(rotated)[0]["people"][0]
    assert len(p["pose_keypoints_2d"]) == 18 * 3
    assert len(p["face_keypoints_2d"]) == 70 * 3
    assert p["hand_left_keypoints_2d"] is None
    assert len(p["hand_right_keypoints_2d"]) == 21 * 3
    assert all(v == 0.0 for v in p["hand_right_keypoints_2d"])


def test_serialize_canvas_defaults_to_portrait_size(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("0"))
    p = serialize(rotated)
    w, h = aeri_rig.portrait_size
    assert p[0]["canvas_width"] == w
    assert p[0]["canvas_height"] == h


def test_serialize_hidden_keypoints_zeroed(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("her-left 90"))
    p = serialize(rotated)[0]["people"][0]
    body = p["pose_keypoints_2d"]
    # At her-left 90, the anatomical-left eye should be culled.
    # Body index 15 in OpenPose body_18 is L_eye.
    L_EYE_OPENPOSE = 15
    triple = body[L_EYE_OPENPOSE * 3 : L_EYE_OPENPOSE * 3 + 3]
    assert triple == [0.0, 0.0, 0.0]


def test_serialize_to_string_is_valid_json(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("her-left 30"))
    s = serialize_to_string(rotated, indent=2)
    reloaded = json.loads(s)
    assert reloaded[0]["people"][0]["pose_keypoints_2d"]
