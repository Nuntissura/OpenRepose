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
) -> np.ndarray:
    """Render the overlay as a BGR image.

    `portrait_path` is the master; if missing or unreadable, render on a
    dark canvas of `fallback_size` so the snapshot still produces a
    non-empty image. `calibration` is the active record; if None or empty,
    the portrait is rendered with a "no calibration markers" label so the
    operator can see the baseline.
    """
    canvas = _load_portrait_or_canvas(portrait_path, fallback_size)

    if calibration is None or not calibration.markers:
        cv2.putText(
            canvas,
            "no calibration markers",
            (16, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
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
