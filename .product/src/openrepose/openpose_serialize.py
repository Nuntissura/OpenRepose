"""Serialize a RotatedRig to OpenPose-format JSON."""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from .openpose_schema import (
    MP_POSE_TO_BODY18,
    OPENPOSE_BODY_COUNT,
    OPENPOSE_FACE_COUNT,
    OPENPOSE_HAND_COUNT,
    apply_body_part_visibility,
    apply_frame_to_keypoints,
    apply_marker_visibility,
    map_face_mesh_to_openpose,
)
from .rotation import RotatedRig


def serialize(
    rotated: RotatedRig,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    *,
    body_part_visibility: dict[str, bool] | None = None,
    marker_visibility: dict | None = None,
    frame: dict | None = None,
) -> dict[str, Any]:
    w, h = rotated.portrait_size
    canvas_w = canvas_width if canvas_width is not None else w
    canvas_h = canvas_height if canvas_height is not None else h

    face_70 = map_face_mesh_to_openpose(rotated.face_mesh_world)
    face_visible_70 = _project_visibility(rotated.face_mesh_visible)
    body_18, body_18_conf = _project_body_18(rotated.body_kps_world, rotated.body_visible)

    body_18_conf, face_visible_70 = apply_body_part_visibility(body_18_conf, face_visible_70, body_part_visibility)
    body_18_conf, face_visible_70 = apply_marker_visibility(body_18_conf, face_visible_70, marker_visibility)

    hands_visible = True if body_part_visibility is None else bool(body_part_visibility.get("hands", True))
    hand_left_conf = rotated.hand_left_visible.astype(np.float32) if hands_visible else np.zeros((OPENPOSE_HAND_COUNT,), dtype=np.float32)
    hand_right_conf = rotated.hand_right_visible.astype(np.float32) if hands_visible else np.zeros((OPENPOSE_HAND_COUNT,), dtype=np.float32)

    head_anchor_xy = rotated.head_anchor_world[:2]
    body_18 = apply_frame_to_keypoints(body_18, frame, head_anchor_xy, (canvas_w, canvas_h))
    face_70_xy = apply_frame_to_keypoints(face_70[:, :2], frame, head_anchor_xy, (canvas_w, canvas_h))
    hand_left_xy = apply_frame_to_keypoints(rotated.hand_left_world[:, :2], frame, head_anchor_xy, (canvas_w, canvas_h))
    hand_right_xy = apply_frame_to_keypoints(rotated.hand_right_world[:, :2], frame, head_anchor_xy, (canvas_w, canvas_h))

    return [
        {
            "people": [
                {
                    "pose_keypoints_2d": _flatten_with_visibility(body_18, body_18_conf),
                    "face_keypoints_2d": _flatten_with_visibility(face_70_xy, face_visible_70.astype(np.float32)),
                    "hand_left_keypoints_2d": _flatten_with_visibility(hand_left_xy, hand_left_conf),
                    "hand_right_keypoints_2d": _flatten_with_visibility(hand_right_xy, hand_right_conf),
                }
            ],
            "canvas_height": int(canvas_h),
            "canvas_width": int(canvas_w),
        }
    ]


def serialize_to_string(
    rotated: RotatedRig,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    *,
    indent: int | None = None,
    body_part_visibility: dict[str, bool] | None = None,
    marker_visibility: dict | None = None,
    frame: dict | None = None,
) -> str:
    return json.dumps(serialize(rotated, canvas_width=canvas_width, canvas_height=canvas_height, body_part_visibility=body_part_visibility, marker_visibility=marker_visibility, frame=frame), indent=indent, ensure_ascii=False)


def _project_visibility(face_visible_478: np.ndarray) -> np.ndarray:
    from .openpose_schema import MP_FACEMESH_TO_OPENPOSE_70
    out = np.zeros((OPENPOSE_FACE_COUNT,), dtype=bool)
    n = face_visible_478.shape[0]
    for op_idx, mp_idx in enumerate(MP_FACEMESH_TO_OPENPOSE_70):
        if 0 <= mp_idx < n:
            out[op_idx] = bool(face_visible_478[mp_idx])
    return out


def _project_body_18(body_kps_world: np.ndarray, body_visible_33: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    body_18 = np.zeros((OPENPOSE_BODY_COUNT, 2), dtype=np.float32)
    body_18_conf = np.zeros((OPENPOSE_BODY_COUNT,), dtype=np.float32)
    n = body_kps_world.shape[0]
    for op_idx, mp_idx in enumerate(MP_POSE_TO_BODY18):
        if mp_idx == -1:
            continue
        if 0 <= mp_idx < n and body_visible_33[mp_idx]:
            body_18[op_idx] = body_kps_world[mp_idx, :2]
            body_18_conf[op_idx] = 1.0
    from .openpose_schema import BODY_L_SHOULDER, BODY_NECK, BODY_R_SHOULDER
    l_mp = MP_POSE_TO_BODY18[BODY_L_SHOULDER]
    r_mp = MP_POSE_TO_BODY18[BODY_R_SHOULDER]
    if 0 <= l_mp < n and body_visible_33[l_mp] and 0 <= r_mp < n and body_visible_33[r_mp]:
        body_18[BODY_NECK] = 0.5 * (body_kps_world[l_mp, :2] + body_kps_world[r_mp, :2])
        body_18_conf[BODY_NECK] = 1.0
    return body_18, body_18_conf


def _flatten_with_visibility(xy: np.ndarray, conf: np.ndarray) -> list[float]:
    out: list[float] = []
    for i in range(xy.shape[0]):
        c = float(conf[i])
        if c <= 0.0:
            out.extend((0.0, 0.0, 0.0))
        else:
            out.extend((float(xy[i, 0]), float(xy[i, 1]), c))
    return out
