"""Native OpenPose-format wireframe renderer.

Takes a `RotatedRig` (the output of `rotation.rotate_yaw`) and produces a
PNG image in the format OpenPose / DWPose / ControlNet OpenPose models
expect: black background, body skeleton drawn with the standard OpenPose
limb color spec, face landmarks as small white dots.

This is a standalone renderer; OpenRepose does not depend on ComfyUI's
`RenderPeopleKps` to draw OpenPose previews.
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from ..openpose_schema import (
    BODY_L_EAR,
    BODY_L_EYE,
    BODY_L_SHOULDER,
    BODY_NECK,
    BODY_NOSE,
    BODY_R_EAR,
    BODY_R_EYE,
    BODY_R_SHOULDER,
    MP_POSE_TO_BODY18,
    apply_body_part_visibility,
    apply_frame_to_keypoints,
    apply_marker_visibility,
    map_face_mesh_to_openpose,
)
from ..openpose_serialize import _project_body_18
from ..rotation import RotatedRig

# OpenPose body_18 limb pairs. Each tuple is (idx_a, idx_b).
LIMB_PAIRS: tuple[tuple[int, int], ...] = (
    (1, 2),    # neck -> r_shoulder
    (1, 5),    # neck -> l_shoulder
    (2, 3),    # r_shoulder -> r_elbow
    (3, 4),    # r_elbow -> r_wrist
    (5, 6),    # l_shoulder -> l_elbow
    (6, 7),    # l_elbow -> l_wrist
    (1, 8),    # neck -> r_hip
    (8, 9),    # r_hip -> r_knee
    (9, 10),   # r_knee -> r_ankle
    (1, 11),   # neck -> l_hip
    (11, 12),  # l_hip -> l_knee
    (12, 13),  # l_knee -> l_ankle
    (1, 0),    # neck -> nose
    (0, 14),   # nose -> r_eye
    (14, 16),  # r_eye -> r_ear
    (0, 15),   # nose -> l_eye
    (15, 17),  # l_eye -> l_ear
)

# Standard OpenPose limb colors (BGR). One per LIMB_PAIRS entry.
LIMB_COLORS_BGR: tuple[tuple[int, int, int], ...] = (
    (0, 0, 255),     # red
    (0, 85, 255),
    (0, 170, 255),
    (0, 255, 255),   # yellow
    (0, 255, 170),
    (0, 255, 85),
    (0, 255, 0),     # green
    (85, 255, 0),
    (170, 255, 0),
    (255, 255, 0),   # cyan
    (255, 170, 0),
    (255, 85, 0),
    (255, 0, 0),     # blue
    (255, 0, 85),
    (255, 0, 170),
    (255, 0, 255),   # magenta
    (170, 0, 255),
)

KEYPOINT_COLOR_BGR = (255, 255, 255)
FACE_DOT_COLOR_BGR = (255, 255, 255)
LIMB_LINE_THICKNESS = 4
KEYPOINT_RADIUS = 4
FACE_DOT_RADIUS = 1
CANVAS_BORDER_THICKNESS = 2


def _build_body_18_color_by_index() -> tuple[tuple[int, int, int], ...]:
    """Per-keypoint BGR color derived from LIMB_PAIRS + LIMB_COLORS_BGR.

    For each body_18 index, returns the color of the first limb that
    includes it (limb-pair iteration order matches OpenPose convention).
    Used by the GUI Markers tab (WP-I1-032) so body_18 row text matches
    the limb color in the rendered preview.
    """
    from ..openpose_schema import OPENPOSE_BODY_COUNT

    colors: list[tuple[int, int, int] | None] = [None] * OPENPOSE_BODY_COUNT
    for limb_idx, (a, b) in enumerate(LIMB_PAIRS):
        color = LIMB_COLORS_BGR[limb_idx]
        if colors[a] is None:
            colors[a] = color
        if colors[b] is None:
            colors[b] = color
    fallback = (255, 255, 255)
    return tuple(c if c is not None else fallback for c in colors)


BODY_18_COLOR_BY_INDEX: tuple[tuple[int, int, int], ...] = (
    _build_body_18_color_by_index()
)


def _hex_to_bgr(color: str | None) -> tuple[int, int, int] | None:
    """`#rrggbb` (or `rrggbb`) -> (b, g, r). Returns None on empty / invalid."""
    if not color:
        return None
    s = color.strip().lstrip("#")
    if len(s) != 6:
        return None
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
    except ValueError:
        return None
    return (b, g, r)


def render_openpose(
    rotated: RotatedRig,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    *,
    body_part_visibility: dict[str, bool] | None = None,
    marker_visibility: dict | None = None,
    frame: dict | None = None,
    canvas_border_color: str | None = None,
) -> np.ndarray:
    """Render the rotated rig as an OpenPose-style wireframe.

    Returns a (H, W, 3) BGR uint8 numpy array with a black background.
    `body_part_visibility` (WP-I1-017) suppresses entire body-part groups
    in the preview the same way the serializer suppresses them in JSON.
    """
    w, h = rotated.portrait_size
    if canvas_width is None:
        canvas_width = w
    if canvas_height is None:
        canvas_height = h

    canvas = np.zeros((int(canvas_height), int(canvas_width), 3), dtype=np.uint8)

    # Body skeleton.
    body18, _conf18 = _project_body_18(rotated.body_kps_world, rotated.body_visible)
    body18_visible = (np.abs(body18) > 0).any(axis=1)

    # Face visibility (also masked by body_part_visibility group "face").
    face70 = map_face_mesh_to_openpose(rotated.face_mesh_world)
    face70_visible = _face_visibility_from_478(rotated.face_mesh_visible)

    # Apply per-body-part visibility mask (WP-I1-017), then per-marker
    # overrides (WP-I1-029) — per-marker is authoritative.
    body18_visible, face70_visible = apply_body_part_visibility(
        body18_visible, face70_visible, body_part_visibility
    )
    body18_visible, face70_visible = apply_marker_visibility(
        body18_visible, face70_visible, marker_visibility
    )

    # WP-I1-029 defensive: even if a per-marker override forces visible=True
    # on a keypoint that MediaPipe never detected (coord at the origin),
    # do not draw a stray dot at (0, 0). The Markers tab's "no detection"
    # indicator + the auto-uncheck-on-import logic in commands.py keep
    # this case rare; this is the last-line safety net.
    body18_at_origin = (np.abs(body18) < 1.0).all(axis=1)
    body18_visible = body18_visible & ~body18_at_origin

    # Frame reframing (WP-I1-023): scale + offset coords; line widths and
    # dot sizes are canvas-pixel constants and stay invariant.
    head_anchor_xy = (
        rotated.head_anchor[:2]
        if hasattr(rotated, "head_anchor") and rotated.head_anchor is not None
        else None
    )
    body18 = apply_frame_to_keypoints(
        body18, frame, head_anchor_xy, (canvas_width, canvas_height)
    )
    face70_xy = apply_frame_to_keypoints(
        face70[:, :2].astype(np.float64),
        frame,
        head_anchor_xy,
        (canvas_width, canvas_height),
    )

    # Same defensive check on face_70 — if FaceMesh wasn't detected the
    # coords are zeros; do not draw stray face dots at origin.
    face70_at_origin = (np.abs(face70_xy) < 1.0).all(axis=1)
    face70_visible = face70_visible & ~face70_at_origin

    for (a, b), color in zip(LIMB_PAIRS, LIMB_COLORS_BGR, strict=True):
        if not body18_visible[a] or not body18_visible[b]:
            continue
        pa = (int(round(body18[a, 0])), int(round(body18[a, 1])))
        pb = (int(round(body18[b, 0])), int(round(body18[b, 1])))
        cv2.line(canvas, pa, pb, color, LIMB_LINE_THICKNESS, lineType=cv2.LINE_AA)

    # Body keypoint dots.
    for i in range(body18.shape[0]):
        if not body18_visible[i]:
            continue
        p = (int(round(body18[i, 0])), int(round(body18[i, 1])))
        cv2.circle(canvas, p, KEYPOINT_RADIUS, KEYPOINT_COLOR_BGR, -1, lineType=cv2.LINE_AA)

    # Face landmarks as small white dots.
    for i in range(face70_xy.shape[0]):
        if not face70_visible[i]:
            continue
        p = (int(round(face70_xy[i, 0])), int(round(face70_xy[i, 1])))
        cv2.circle(canvas, p, FACE_DOT_RADIUS, FACE_DOT_COLOR_BGR, -1, lineType=cv2.LINE_AA)

    # Canvas border outline (WP-I1-032). Skipped if color is None / invalid;
    # the operator chooses the color via Options. Drawn last so it sits on
    # top of any keypoints clipped at the canvas edge.
    border_bgr = _hex_to_bgr(canvas_border_color)
    if border_bgr is not None:
        cv2.rectangle(
            canvas,
            (0, 0),
            (int(canvas_width) - 1, int(canvas_height) - 1),
            border_bgr,
            CANVAS_BORDER_THICKNESS,
            cv2.LINE_AA,
        )

    return canvas


def render_openpose_to_png(
    rotated: RotatedRig,
    out_path: Path | str,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
) -> Path:
    """Render and save to PNG. Returns the absolute output path."""
    img = render_openpose(rotated, canvas_width=canvas_width, canvas_height=canvas_height)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img)
    return out.resolve()


def _face_visibility_from_478(face_visible_478: np.ndarray) -> np.ndarray:
    """Map (478,) visibility to (70,) visibility via the OpenPose index map."""
    from ..openpose_schema import MP_FACEMESH_TO_OPENPOSE_70

    out = np.zeros((70,), dtype=bool)
    n = face_visible_478.shape[0]
    for op_idx, mp_idx in enumerate(MP_FACEMESH_TO_OPENPOSE_70):
        if 0 <= mp_idx < n:
            out[op_idx] = bool(face_visible_478[mp_idx])
    return out
