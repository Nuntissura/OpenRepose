"""Rigid yaw rotation behavior tests."""

from __future__ import annotations

import pytest

from openrepose.openpose_schema import (
    BODY_L_EAR,
    BODY_L_EYE,
    BODY_R_EAR,
    BODY_R_EYE,
    MP_POSE_TO_BODY18,
)
from openrepose.rig import Rig
from openrepose.rotation import rotate_yaw
from openrepose.yaw_bin import parse_bin


def _nose_x(rig: Rig) -> float:
    """Nose x as projected via OpenPose body_18 (MediaPipe Pose nose)."""
    body, conf = rig.openpose_body_18()
    return float(body[0, 0])


def test_rotate_zero_is_identity(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("0"))
    # face mesh and body kps should equal originals at 0 deg
    assert rotated.face_mesh_world.shape == aeri_rig.face_mesh.shape
    diff = rotated.face_mesh_world - aeri_rig.face_mesh
    assert abs(float(diff.max())) < 1e-3


def test_her_left_moves_nose_image_right(aeri_rig: Rig) -> None:
    base_nose_x = _nose_x(aeri_rig)
    rotated = rotate_yaw(aeri_rig, parse_bin("her-left 30"))
    # Build rotated rig as a fake Rig-like view to extract nose via mapping
    from openrepose.openpose_serialize import _project_body_18

    body18, _conf = _project_body_18(rotated.body_kps_world, rotated.body_visible)
    rotated_nose_x = float(body18[0, 0])
    assert rotated_nose_x > base_nose_x, (
        f"her-left 30 should move nose to image-right; got {base_nose_x} -> {rotated_nose_x}"
    )


def test_her_right_moves_nose_image_left(aeri_rig: Rig) -> None:
    base_nose_x = _nose_x(aeri_rig)
    rotated = rotate_yaw(aeri_rig, parse_bin("her-right 30"))
    from openrepose.openpose_serialize import _project_body_18

    body18, _conf = _project_body_18(rotated.body_kps_world, rotated.body_visible)
    rotated_nose_x = float(body18[0, 0])
    assert rotated_nose_x < base_nose_x


def test_nose_x_monotonic_in_yaw(aeri_rig: Rig) -> None:
    """Increasing her-left magnitude moves nose progressively to image-right."""
    from openrepose.openpose_serialize import _project_body_18

    xs = []
    for label in ("her-right 60", "her-right 30", "0", "her-left 30", "her-left 60"):
        rotated = rotate_yaw(aeri_rig, parse_bin(label))
        body18, _conf = _project_body_18(rotated.body_kps_world, rotated.body_visible)
        xs.append(float(body18[0, 0]))
    for i in range(1, len(xs)):
        assert xs[i] > xs[i - 1], f"non-monotonic at index {i}: {xs}"


def test_far_eye_culled_at_high_her_left(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("her-left 90"))
    # MediaPipe Pose's anatomical-left eye index in the rig:
    mp_l_eye_idx = MP_POSE_TO_BODY18[BODY_L_EYE]
    assert rotated.body_visible[mp_l_eye_idx] is False or not bool(
        rotated.body_visible[mp_l_eye_idx]
    )


def test_far_eye_culled_at_high_her_right(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("her-right 90"))
    mp_r_eye_idx = MP_POSE_TO_BODY18[BODY_R_EYE]
    assert not bool(rotated.body_visible[mp_r_eye_idx])


def test_near_eye_remains_visible_at_high_her_left(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("her-left 90"))
    mp_r_eye_idx = MP_POSE_TO_BODY18[BODY_R_EYE]
    # The near eye (anatomical right) should remain visible at her-left 90.
    if aeri_rig.body_conf[mp_r_eye_idx] > 0.3:
        assert bool(rotated.body_visible[mp_r_eye_idx])


def test_eyes_both_visible_at_low_yaw(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("her-left 30"))
    mp_l_eye_idx = MP_POSE_TO_BODY18[BODY_L_EYE]
    mp_r_eye_idx = MP_POSE_TO_BODY18[BODY_R_EYE]
    if aeri_rig.body_conf[mp_l_eye_idx] > 0.3:
        assert bool(rotated.body_visible[mp_l_eye_idx])
    if aeri_rig.body_conf[mp_r_eye_idx] > 0.3:
        assert bool(rotated.body_visible[mp_r_eye_idx])


def test_her_left_180_full_rear(aeri_rig: Rig) -> None:
    rotated = rotate_yaw(aeri_rig, parse_bin("180"))
    # At 180 deg, the head has rotated all the way around. The nose ends up
    # at roughly the same x as the pivot (since x rotates by 180 = sign flip).
    from openrepose.openpose_serialize import _project_body_18

    body18, _conf = _project_body_18(rotated.body_kps_world, rotated.body_visible)
    pivot_x = float(aeri_rig.head_anchor[0])
    nose_x = float(body18[0, 0])
    # |nose_x - pivot_x| should be small (the original lateral offset, sign-flipped).
    base_nose_x = _nose_x(aeri_rig)
    assert abs((nose_x - pivot_x) + (base_nose_x - pivot_x)) < 1e-2
