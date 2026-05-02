"""Pure-numpy 3D wireframe renderer for the rig viewport.

Avoids pyrender / OpenGL dependencies. The "3D viewport" snapshot for the
LLM is a wireframe rendering of the rotated rig as seen from the camera,
plus optional inspector overlays. It does not attempt photorealistic mesh
rendering — the goal is a clear visual diagnostic.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..openpose_schema import map_face_mesh_to_openpose
from ..openpose_serialize import _project_body_18
from ..rotation import RotatedRig

# Visual style: light gray background, dark face mesh, colored body skeleton,
# orange head-anchor pivot marker, monospace overlay text.
BACKGROUND_BGR = (32, 32, 32)
FACE_DOT_BGR = (180, 180, 180)
FACE_DOT_RADIUS = 1
BODY_LINE_BGR = (60, 200, 255)
BODY_LINE_THICKNESS = 2
PIVOT_BGR = (0, 165, 255)
TEXT_BGR = (220, 220, 220)
SUBTEXT_BGR = (140, 140, 140)


def render_3d_viewport(
    rotated: RotatedRig,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
) -> np.ndarray:
    """Render the rotated rig as a wireframe diagnostic image.

    Layout:
        - face mesh dots (light gray)
        - body skeleton (orange)
        - head anchor / rotation pivot dot (orange)
        - text overlay: yaw bin, signed_deg, portrait size, axis
    """
    w, h = rotated.portrait_size
    if canvas_width is None:
        canvas_width = w
    if canvas_height is None:
        canvas_height = h

    canvas = np.full((int(canvas_height), int(canvas_width), 3), BACKGROUND_BGR, dtype=np.uint8)

    # Face mesh: draw all visible 478 landmarks as dots.
    face = rotated.face_mesh_world
    visible = rotated.face_mesh_visible
    for i in range(face.shape[0]):
        if not visible[i]:
            continue
        p = (int(round(face[i, 0])), int(round(face[i, 1])))
        cv2.circle(canvas, p, FACE_DOT_RADIUS, FACE_DOT_BGR, -1, lineType=cv2.LINE_AA)

    # Body skeleton lines (using the openpose-mapped 18 + visibility from 33).
    body18, _conf18 = _project_body_18(rotated.body_kps_world, rotated.body_visible)
    body18_visible = (np.abs(body18) > 0).any(axis=1)

    from .draw_openpose import LIMB_PAIRS  # reuse pair definitions

    for a, b in LIMB_PAIRS:
        if not body18_visible[a] or not body18_visible[b]:
            continue
        pa = (int(round(body18[a, 0])), int(round(body18[a, 1])))
        pb = (int(round(body18[b, 0])), int(round(body18[b, 1])))
        cv2.line(canvas, pa, pb, BODY_LINE_BGR, BODY_LINE_THICKNESS, lineType=cv2.LINE_AA)

    # Head anchor pivot.
    pivot = rotated.head_anchor_world
    cv2.circle(
        canvas,
        (int(round(pivot[0])), int(round(pivot[1]))),
        6,
        PIVOT_BGR,
        -1,
        lineType=cv2.LINE_AA,
    )

    # Text overlay (top-left corner).
    yaw = rotated.yaw
    lines = [
        f"3D viewport (rig in rotated state)",
        f"yaw_bin    {yaw.label}",
        f"signed_deg {yaw.signed_deg:+.1f}",
        f"axis       y",
        f"canvas     {canvas_width}x{canvas_height}",
        f"face_kps   {int(rotated.face_mesh_visible.sum())}/{rotated.face_mesh_visible.shape[0]} visible",
        f"body_kps   {int(rotated.body_visible.sum())}/{rotated.body_visible.shape[0]} visible",
    ]
    for i, text in enumerate(lines):
        color = TEXT_BGR if i == 0 else SUBTEXT_BGR
        cv2.putText(
            canvas,
            text,
            (16, 28 + i * 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            1,
            cv2.LINE_AA,
        )

    return canvas


def render_3d_viewport_to_png(
    rotated: RotatedRig,
    out_path: Path | str,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
) -> Path:
    img = render_3d_viewport(rotated, canvas_width=canvas_width, canvas_height=canvas_height)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img)
    return out.resolve()
