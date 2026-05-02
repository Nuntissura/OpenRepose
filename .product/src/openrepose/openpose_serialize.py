"""Serialize a RotatedRig to OpenPose-format JSON.

Output schema matches what ComfyUI's `RenderPeopleKps` (from
`comfyui-controlnet-aux`) consumes and what OpenPoseXL2 ControlNet was
trained on:

    [
      {
        "people": [
          {
            "pose_keypoints_2d": [x, y, c, ... 18 triples],
            "face_keypoints_2d": [x, y, c, ... 70 triples],
            "hand_left_keypoints_2d":  null,
            "hand_right_keypoints_2d": [0.0, ... 21 triples (suppressed)]
          }
        ],
        "canvas_height": <int>,
        "canvas_width":  <int>
      }
    ]

Hidden keypoints render as (0.0, 0.0, 0.0) so RenderPeopleKps suppresses
them. Visible keypoints render with confidence 1.0.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from .openpose_schema import (
    MP_POSE_TO_BODY18,
    OPENPOSE_BODY_COUNT,
    OPENPOSE_FACE_COUNT,
    apply_body_part_visibility,
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
) -> dict[str, Any]:
    """Serialize one RotatedRig to the OpenPose people-array JSON shape.

    Returns the top-level list (length 1). Caller can `json.dumps` it directly.

    canvas_width / canvas_height default to the source portrait dimensions.
    """
    w, h = rotated.portrait_size
    canvas_w = canvas_width if canvas_width is not None else w
    canvas_h = canvas_height if canvas_height is not None else h

    face_70 = map_face_mesh_to_openpose(rotated.face_mesh_world)
    face_visible_478 = rotated.face_mesh_visible
    face_visible_70 = _project_visibility(face_visible_478)

    body_18, body_18_conf = _project_body_18(
        rotated.body_kps_world,
        rotated.body_visible,
    )

    # Apply per-body-part visibility mask (WP-I1-017) first, then per-marker
    # overrides (WP-I1-029) on top — per-marker is the authoritative layer
    # so an explicit True restores a keypoint even if its group is off.
    body_18_conf, face_visible_70 = apply_body_part_visibility(
        body_18_conf, face_visible_70, body_part_visibility
    )
    body_18_conf, face_visible_70 = apply_marker_visibility(
        body_18_conf, face_visible_70, marker_visibility
    )

    pose_kps_flat = _flatten_with_visibility(body_18, body_18_conf)
    face_kps_flat = _flatten_with_visibility(face_70[:, :2], face_visible_70.astype(np.float32))

    payload = [
        {
            "people": [
                {
                    "pose_keypoints_2d": pose_kps_flat,
                    "face_keypoints_2d": face_kps_flat,
                    "hand_left_keypoints_2d": None,
                    "hand_right_keypoints_2d": [0.0] * (21 * 3),
                }
            ],
            "canvas_height": int(canvas_h),
            "canvas_width": int(canvas_w),
        }
    ]
    return payload


def serialize_to_string(
    rotated: RotatedRig,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    *,
    indent: int | None = None,
    body_part_visibility: dict[str, bool] | None = None,
    marker_visibility: dict | None = None,
) -> str:
    """Convenience: serialize then `json.dumps`."""
    return json.dumps(
        serialize(
            rotated,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            body_part_visibility=body_part_visibility,
            marker_visibility=marker_visibility,
        ),
        indent=indent,
        ensure_ascii=False,
    )


# --- internals ---------------------------------------------------------------


def _project_visibility(face_visible_478: np.ndarray) -> np.ndarray:
    """Return a (70,) bool array of visibility for the OpenPose-mapped subset."""
    from .openpose_schema import MP_FACEMESH_TO_OPENPOSE_70

    out = np.zeros((OPENPOSE_FACE_COUNT,), dtype=bool)
    n = face_visible_478.shape[0]
    for op_idx, mp_idx in enumerate(MP_FACEMESH_TO_OPENPOSE_70):
        if 0 <= mp_idx < n:
            out[op_idx] = bool(face_visible_478[mp_idx])
    return out


def _project_body_18(
    body_kps_world: np.ndarray, body_visible_33: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Map MediaPipe Pose 33 -> OpenPose body_18 with confidences.

    Confidence is 1.0 if the source MP keypoint is in `body_visible_33`,
    else 0.0. The synthesized neck (op_idx 1) takes the AND of the two
    shoulder visibilities.
    """
    body_18 = np.zeros((OPENPOSE_BODY_COUNT, 2), dtype=np.float32)
    body_18_conf = np.zeros((OPENPOSE_BODY_COUNT,), dtype=np.float32)

    n = body_kps_world.shape[0]
    for op_idx, mp_idx in enumerate(MP_POSE_TO_BODY18):
        if mp_idx == -1:
            continue
        if 0 <= mp_idx < n and body_visible_33[mp_idx]:
            body_18[op_idx] = body_kps_world[mp_idx, :2]
            body_18_conf[op_idx] = 1.0

    # Synthesized neck (op_idx 1): mean of shoulders if both visible.
    from .openpose_schema import BODY_L_SHOULDER, BODY_NECK, BODY_R_SHOULDER

    l_mp = MP_POSE_TO_BODY18[BODY_L_SHOULDER]
    r_mp = MP_POSE_TO_BODY18[BODY_R_SHOULDER]
    if (
        0 <= l_mp < n and body_visible_33[l_mp]
        and 0 <= r_mp < n and body_visible_33[r_mp]
    ):
        body_18[BODY_NECK] = 0.5 * (body_kps_world[l_mp, :2] + body_kps_world[r_mp, :2])
        body_18_conf[BODY_NECK] = 1.0

    return body_18, body_18_conf


def _flatten_with_visibility(xy: np.ndarray, conf: np.ndarray) -> list[float]:
    """Flatten (N, 2) xy + (N,) conf into [x, y, c, x, y, c, ...] zeroing
    hidden rows fully (so RenderPeopleKps doesn't draw a hidden landmark
    even with non-zero coords)."""
    out: list[float] = []
    n = xy.shape[0]
    for i in range(n):
        c = float(conf[i])
        if c <= 0.0:
            out.extend((0.0, 0.0, 0.0))
        else:
            out.extend((float(xy[i, 0]), float(xy[i, 1]), c))
    return out
