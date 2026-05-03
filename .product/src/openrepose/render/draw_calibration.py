"""Render the `calibration_overlay` snapshot target.

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 2 / Snapshot Target".
Shows the master portrait with operator markers (bright, large) overlaid
on MediaPipe-detected positions (dim, small), connected by a thin line for
visual diff.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..calibration import Calibration

PORTRAIT_FALLBACK_BGR = (32, 32, 32)
MEDIAPIPE_DOT_BGR = (90, 90, 90)
MEDIAPIPE_DOT_RADIUS = 4
OPERATOR_RING_BGR = (40, 200, 255)
OPERATOR_RING_RADIUS = 12
OPERATOR_RING_THICKNESS = 2
LINK_BGR = (40, 200, 255)
LABEL_BGR = (220, 220, 220)
LABEL_OFFSET_PX = (14, 6)


def render_calibration_overlay(
    portrait_path: str | Path | None,
    calibration: Calibration | None,
    *,
    fallback_size: tuple[int, int] = (1024, 1024),
    detected_positions: dict[str, tuple[float, float]] | None = None,
) -> np.ndarray:
    """Render the overlay as a BGR image.

    `portrait_path` is the master; if missing or unreadable, render on a
    dark canvas of `fallback_size` so the snapshot still produces a
    non-empty image. `calibration` is the active record; operator markers
    render as bright rings on top of MediaPipe positions.

    WP-I1-028: `detected_positions` (anatomical name → MediaPipe-detected
    pixel coord) is rendered as dim dots ALWAYS, even before any operator
    marker is placed. Operator can see where MediaPipe thinks each feature
    is and decide whether to override.
    """
    canvas = _load_portrait_or_canvas(portrait_path, fallback_size)

    # WP-I1-028: always-on detected dots. Drawn first so operator markers
    # render on top.
    if detected_positions:
        for name, (mx, my) in detected_positions.items():
            mp = (int(round(mx)), int(round(my)))
            cv2.circle(
                canvas, mp, MEDIAPIPE_DOT_RADIUS, MEDIAPIPE_DOT_BGR, -1, cv2.LINE_AA
            )
            label_pos = (mp[0] + 8, mp[1] - 8)
            cv2.putText(
                canvas,
                name,
                label_pos,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                MEDIAPIPE_DOT_BGR,
                1,
                cv2.LINE_AA,
            )

    if calibration is None or not calibration.markers:
        if not detected_positions:
            cv2.putText(
                canvas,
                "no calibration markers + no rig loaded",
                (16, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                LABEL_BGR,
                1,
                cv2.LINE_AA,
            )
        else:
            cv2.putText(
                canvas,
                "auto-detected positions shown — click to place operator marker",
                (16, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                LABEL_BGR,
                1,
                cv2.LINE_AA,
            )
        return canvas

    for m in calibration.markers:
        mp = (
            int(round(m.mediapipe_xy[0])),
            int(round(m.mediapipe_xy[1])),
        )
        op = (
            int(round(m.operator_xy[0])),
            int(round(m.operator_xy[1])),
        )
        cv2.circle(
            canvas, mp, MEDIAPIPE_DOT_RADIUS, MEDIAPIPE_DOT_BGR, -1, cv2.LINE_AA
        )
        cv2.circle(
            canvas,
            op,
            OPERATOR_RING_RADIUS,
            OPERATOR_RING_BGR,
            OPERATOR_RING_THICKNESS,
            cv2.LINE_AA,
        )
        cv2.line(canvas, mp, op, LINK_BGR, 1, cv2.LINE_AA)
        label_pos = (
            op[0] + LABEL_OFFSET_PX[0],
            op[1] + LABEL_OFFSET_PX[1],
        )
        cv2.putText(
            canvas,
            m.name,
            label_pos,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            LABEL_BGR,
            1,
            cv2.LINE_AA,
        )

    cv2.putText(
        canvas,
        f"calibration: {calibration.completeness} "
        f"({calibration.marker_count} markers)",
        (16, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        LABEL_BGR,
        1,
        cv2.LINE_AA,
    )
    return canvas


def _load_portrait_or_canvas(
    portrait_path: str | Path | None,
    fallback_size: tuple[int, int],
) -> np.ndarray:
    if portrait_path:
        p = Path(portrait_path)
        if p.exists():
            img = cv2.imread(str(p), cv2.IMREAD_COLOR)
            if img is not None:
                return img
    w, h = fallback_size
    canvas = np.full((h, w, 3), PORTRAIT_FALLBACK_BGR, dtype=np.uint8)
    cv2.putText(
        canvas,
        "no portrait loaded",
        (16, h // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (140, 140, 140),
        1,
        cv2.LINE_AA,
    )
    return canvas
