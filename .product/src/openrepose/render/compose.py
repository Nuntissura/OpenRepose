"""Composite snapshot for the `full_window` target.

Composes child-pane snapshots into a single full-window image with a
toolbar row across the top, a 3D viewport + OpenPose preview in the
middle, an inspector / log / options dock on the right, and a status bar
on the bottom.

Used by `snapshot.snapshot()` when target == "full_window". Composition
is desktop-grab-free: we render each pane independently and paste them
at fixed layout coordinates.
"""

from __future__ import annotations

import cv2
import numpy as np

# Reference layout (matches the GUI in WP-I0-004 spec).
LAYOUT = {
    "canvas": (1280, 800),
    "toolbar": (0, 0, 1280, 60),       # x, y, w, h
    "viewport_3d": (0, 60, 480, 600),
    "viewport_openpose": (480, 60, 480, 600),
    "inspector": (960, 60, 320, 600),
    "status_bar": (0, 660, 1280, 40),
    "log": (0, 700, 1280, 100),
}

BACKGROUND_BGR = (16, 16, 16)
PANE_BORDER_BGR = (60, 60, 60)


def compose_full_window(panes: dict[str, np.ndarray]) -> np.ndarray:
    """Composite child pane images into the full_window layout.

    `panes` is a dict mapping target name -> BGR numpy array. Missing
    panes are rendered as labeled empty boxes. Each input image is
    resized to fit its layout slot (preserving content; no aspect-ratio
    correction since the panes are placeholders / wireframes).
    """
    cw, ch = LAYOUT["canvas"]
    canvas = np.full((ch, cw, 3), BACKGROUND_BGR, dtype=np.uint8)

    for name, rect in LAYOUT.items():
        if name == "canvas":
            continue
        x, y, w, h = rect
        pane = panes.get(name)
        if pane is None:
            slot = _empty_pane(name, w, h)
        else:
            slot = cv2.resize(pane, (w, h), interpolation=cv2.INTER_AREA)
        canvas[y : y + h, x : x + w] = slot
        cv2.rectangle(canvas, (x, y), (x + w - 1, y + h - 1), PANE_BORDER_BGR, 1, cv2.LINE_AA)

    return canvas


def _empty_pane(label: str, w: int, h: int) -> np.ndarray:
    pane = np.full((h, w, 3), (24, 24, 24), dtype=np.uint8)
    cv2.putText(
        pane,
        f"[empty: {label}]",
        (12, max(20, h // 2)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (140, 140, 140),
        1,
        cv2.LINE_AA,
    )
    return pane
