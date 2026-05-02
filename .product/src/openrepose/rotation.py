"""Rigid yaw rotation of a Rig about the vertical y-axis.

The rotation is rigid: the rig is treated as a single 3D object and rotated
about a vertical axis through its head anchor. The same rotation applies to
all face mesh vertices and all body keypoints. Pitch and roll are out of scope
for v0.1.

Convention:
    Positive signed_deg = her-left N = avatar rotates to her own left.
        Result: nose moves toward the +x edge of the frame; her anatomical
        right side faces camera.
    Negative signed_deg = her-right N = avatar rotates to her own right.
        Result: nose moves toward the -x edge of the frame; her anatomical
        left side faces camera.

Coordinate system (right-handed):
    +x = positive screen-x (right edge of frame)
    +y = positive screen-y (bottom of frame)
    +z = into screen (away from camera)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .openpose_schema import (
    BODY_L_EAR,
    BODY_L_EYE,
    BODY_R_EAR,
    BODY_R_EYE,
)
from .rig import Rig
from .yaw_bin import YawBin

# Default visibility cull thresholds (degrees of |yaw|).
EYE_CULL_DEG_DEFAULT = 65.0
EAR_CULL_DEG_DEFAULT = 80.0

# Default face surface-normal margin: a face landmark is visible if its
# rotated outward-normal has z < margin (toward camera). margin > 0 lets
# silhouette landmarks pass cleanly.
FACE_NORMAL_MARGIN_DEFAULT = 0.15


@dataclass(frozen=True)
class RotatedRig:
    """Output of `rotate_yaw`. Holds rotated 3D, projected 2D, and visibility."""

    yaw: YawBin

    # Rig metadata copied from the source rig.
    portrait_size: tuple[int, int]
    head_anchor_world: np.ndarray  # (3,) original (un-rotated) head anchor

    # Face: 478 mesh after rotation.
    face_mesh_world: np.ndarray  # (478, 3)
    face_mesh_visible: np.ndarray  # (478,) bool

    # Body: 33 MediaPipe Pose after rotation.
    body_kps_world: np.ndarray  # (33, 3)
    body_visible: np.ndarray  # (33,) bool


def rotate_yaw(
    rig: Rig,
    yaw: YawBin,
    *,
    eye_cull_deg: float = EYE_CULL_DEG_DEFAULT,
    ear_cull_deg: float = EAR_CULL_DEG_DEFAULT,
    face_normal_margin: float = FACE_NORMAL_MARGIN_DEFAULT,
) -> RotatedRig:
    """Rigidly rotate `rig` by `yaw` about the vertical y-axis through head_anchor."""
    angle_deg = yaw.signed_deg
    cos_a = math.cos(math.radians(angle_deg))
    sin_a = math.sin(math.radians(angle_deg))

    cx = float(rig.head_anchor[0])
    cz = float(rig.head_anchor[2])

    face_world = _yaw_points(rig.face_mesh, cx, cz, cos_a, sin_a)
    body_world = _yaw_points(rig.body_kps, cx, cz, cos_a, sin_a)

    face_visible = _face_visibility(
        rig.face_mesh,
        rig.head_anchor,
        cos_a,
        sin_a,
        margin=face_normal_margin,
    )

    body_visible = _body_visibility(
        rig.body_conf,
        signed_deg=angle_deg,
        eye_cull_deg=eye_cull_deg,
        ear_cull_deg=ear_cull_deg,
    )

    return RotatedRig(
        yaw=yaw,
        portrait_size=rig.portrait_size,
        head_anchor_world=rig.head_anchor.copy(),
        face_mesh_world=face_world,
        face_mesh_visible=face_visible,
        body_kps_world=body_world,
        body_visible=body_visible,
    )


def _yaw_points(
    points_xyz: np.ndarray, cx: float, cz: float, cos_a: float, sin_a: float
) -> np.ndarray:
    """Apply the y-axis rotation `[cos -sin; sin cos]` in the (x, z) plane.

    new_x = cx + dx*cos - dz*sin
    new_z = cz + dx*sin + dz*cos

    With +x at the right edge of the frame and +z into the screen, positive
    `signed_deg` (cos, sin via math.cos/math.sin of positive radians) takes
    -z (toward camera) toward +x. I.e., positive yaw moves the nose toward
    the +x edge of the frame, which we label `her-left N` per project
    convention.
    """
    out = points_xyz.copy()
    dx = points_xyz[:, 0] - cx
    dz = points_xyz[:, 2] - cz
    out[:, 0] = cx + dx * cos_a - dz * sin_a
    out[:, 2] = cz + dx * sin_a + dz * cos_a
    return out


def _face_visibility(
    face_xyz: np.ndarray,
    head_anchor_xyz: np.ndarray,
    cos_a: float,
    sin_a: float,
    margin: float,
) -> np.ndarray:
    """Per-landmark visibility from rotated outward-normal direction.

    Approximates each face landmark's surface normal as
    (landmark - head_anchor) normalized. Rotates that direction vector and
    checks the z component. A landmark is visible when its rotated normal's
    z component is < margin (i.e., points toward the camera, with margin > 0
    letting silhouette landmarks pass cleanly).

    The head anchor is the body neck (synthesized) or fallback nose. Using
    the neck as the anchor places the normal field in a reasonable position;
    the body neck sits below the face plane, so most face landmarks have
    forward-pointing (-z) normals at 0 deg.
    """
    delta = face_xyz - head_anchor_xyz
    norms = np.linalg.norm(delta, axis=1, keepdims=True) + 1e-6
    normals = delta / norms
    rotated_z = normals[:, 0] * sin_a + normals[:, 2] * cos_a
    return rotated_z < margin


def _body_visibility(
    body_conf: np.ndarray,
    signed_deg: float,
    eye_cull_deg: float,
    ear_cull_deg: float,
) -> np.ndarray:
    """Per-keypoint visibility for the 33 MediaPipe Pose body keypoints.

    Symmetric pair culling:
      her-left yaw past eye_cull_deg  -> cull anatomical-left eye (BODY_L_EYE)
      her-right yaw past eye_cull_deg -> cull anatomical-right eye (BODY_R_EYE)
      her-left yaw past ear_cull_deg  -> cull anatomical-left ear (BODY_L_EAR)
      her-right yaw past ear_cull_deg -> cull anatomical-right ear (BODY_R_EAR)

    All other keypoints stay visible iff their original confidence is > 0.3.
    """
    visible = body_conf > 0.3

    # NOTE: this function operates on the 33-keypoint MediaPipe Pose array.
    # The OpenPose body_18 indices BODY_L_EYE etc. are *not* the same as
    # MediaPipe Pose indices for those features. We import the MP_POSE_TO_BODY18
    # map and apply culls to the corresponding MP indices.
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


def project_to_2d(
    points_world: np.ndarray,
    canvas_size: tuple[int, int] | None = None,
    *,
    mode: str = "orthographic",
) -> np.ndarray:
    """Project (N, 3) world points to (N, 2) image coordinates.

    `mode='orthographic'` is the default for v0.1. `mode='perspective'` is
    available with a sensible default focal length but not exposed by the
    current CLI; reserved for a future spec extension.
    """
    if mode != "orthographic":
        raise NotImplementedError(
            f"project_to_2d mode={mode!r} not implemented in v0.1; only 'orthographic' is supported."
        )
    if canvas_size is not None:
        # Orthographic at the rig's native pixel scale: x and y are already
        # in canvas pixel units; canvas_size is informational here.
        _ = canvas_size
    return points_world[:, :2].copy()
