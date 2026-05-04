"""Rigid yaw rotation of a Rig about the vertical y-axis."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .openpose_schema import BODY_L_EAR, BODY_L_EYE, BODY_R_EAR, BODY_R_EYE
from .rig import Rig
from .yaw_bin import YawBin

EYE_CULL_DEG_DEFAULT = 65.0
EAR_CULL_DEG_DEFAULT = 80.0
FACE_NORMAL_MARGIN_DEFAULT = 0.15


@dataclass(frozen=True)
class RotatedRig:
    """Output of `rotate_yaw`. Holds rotated 3D and visibility."""

    yaw: YawBin
    portrait_size: tuple[int, int]
    head_anchor_world: np.ndarray
    face_mesh_world: np.ndarray
    face_mesh_visible: np.ndarray
    body_kps_world: np.ndarray
    body_visible: np.ndarray
    hand_left_world: np.ndarray = field(default_factory=lambda: np.zeros((21, 3), dtype=np.float32))
    hand_left_visible: np.ndarray = field(default_factory=lambda: np.zeros((21,), dtype=bool))
    hand_right_world: np.ndarray = field(default_factory=lambda: np.zeros((21, 3), dtype=np.float32))
    hand_right_visible: np.ndarray = field(default_factory=lambda: np.zeros((21,), dtype=bool))


def rotate_yaw(
    rig: Rig,
    yaw: YawBin,
    *,
    eye_cull_deg: float = EYE_CULL_DEG_DEFAULT,
    ear_cull_deg: float = EAR_CULL_DEG_DEFAULT,
    face_normal_margin: float = FACE_NORMAL_MARGIN_DEFAULT,
) -> RotatedRig:
    angle_deg = yaw.signed_deg
    cos_a = math.cos(math.radians(angle_deg))
    sin_a = math.sin(math.radians(angle_deg))
    cx = float(rig.head_anchor[0])
    cz = float(rig.head_anchor[2])

    face_world = _yaw_points(rig.face_mesh, cx, cz, cos_a, sin_a)
    body_world = _yaw_points(rig.body_kps, cx, cz, cos_a, sin_a)
    hand_left_world = _yaw_points(rig.hand_left_kps, cx, cz, cos_a, sin_a)
    hand_right_world = _yaw_points(rig.hand_right_kps, cx, cz, cos_a, sin_a)

    face_visible = _face_visibility(rig.face_mesh, rig.head_anchor, cos_a, sin_a, margin=face_normal_margin)
    body_visible = _body_visibility(rig.body_conf, signed_deg=angle_deg, eye_cull_deg=eye_cull_deg, ear_cull_deg=ear_cull_deg)

    return RotatedRig(
        yaw=yaw,
        portrait_size=rig.portrait_size,
        head_anchor_world=rig.head_anchor.copy(),
        face_mesh_world=face_world,
        face_mesh_visible=face_visible,
        body_kps_world=body_world,
        body_visible=body_visible,
        hand_left_world=hand_left_world,
        hand_left_visible=rig.hand_left_conf > 0.3,
        hand_right_world=hand_right_world,
        hand_right_visible=rig.hand_right_conf > 0.3,
    )


def _yaw_points(points_xyz: np.ndarray, cx: float, cz: float, cos_a: float, sin_a: float) -> np.ndarray:
    out = points_xyz.copy()
    if out.size == 0:
        return out
    dx = points_xyz[:, 0] - cx
    dz = points_xyz[:, 2] - cz
    out[:, 0] = cx + dx * cos_a - dz * sin_a
    out[:, 2] = cz + dx * sin_a + dz * cos_a
    return out


def _face_visibility(face_xyz: np.ndarray, head_anchor_xyz: np.ndarray, cos_a: float, sin_a: float, margin: float) -> np.ndarray:
    delta = face_xyz - head_anchor_xyz
    norms = np.linalg.norm(delta, axis=1, keepdims=True) + 1e-6
    normals = delta / norms
    rotated_z = normals[:, 0] * sin_a + normals[:, 2] * cos_a
    return rotated_z < margin


def _body_visibility(body_conf: np.ndarray, signed_deg: float, eye_cull_deg: float, ear_cull_deg: float) -> np.ndarray:
    visible = body_conf > 0.3
    from .openpose_schema import MP_POSE_TO_BODY18
    if signed_deg > eye_cull_deg:
        mp_idx = MP_POSE_TO_BODY18[BODY_L_EYE]
        if mp_idx >= 0:
            visible[mp_idx] = False
    elif signed_deg < -eye_cull_deg:
        mp_idx = MP_POSE_TO_BODY18[BODY_R_EYE]
        if mp_idx >= 0:
            visible[mp_idx] = False
    if signed_deg > ear_cull_deg:
        mp_idx = MP_POSE_TO_BODY18[BODY_L_EAR]
        if mp_idx >= 0:
            visible[mp_idx] = False
    elif signed_deg < -ear_cull_deg:
        mp_idx = MP_POSE_TO_BODY18[BODY_R_EAR]
        if mp_idx >= 0:
            visible[mp_idx] = False
    return visible


def project_to_2d(points_world: np.ndarray, canvas_size: tuple[int, int] | None = None, *, mode: str = "orthographic") -> np.ndarray:
    if mode != "orthographic":
        raise NotImplementedError(f"project_to_2d mode={mode!r} not implemented in v0.1; only 'orthographic' is supported.")
    if canvas_size is not None:
        _ = canvas_size
    return points_world[:, :2].copy()
