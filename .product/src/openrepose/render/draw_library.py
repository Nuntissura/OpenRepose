"""Render Library snapshot targets to OpenCV BGR images.

Spec: `.gov/spec/openrepose_library_v0_1.md` Snapshot Targets.

Two outputs:
  * `render_library_entry(entry, library_root)` — side-by-side
    openpose.png + generated.png / portrait.png for one entry. Missing
    files render a labeled placeholder so the snapshot path never
    crashes.
  * `render_library_search_results(results, library_root)` — 4x6 grid
    of thumbnails from the most recent search results. Empty list
    renders a labeled "no results" placeholder.

Pure OpenCV / numpy; no Qt imports so the snapshot subsystem can run
headless (CLI / serve) without the GUI loaded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

PLACEHOLDER_BG = (40, 47, 56)  # near-black blue-grey, BGR
PLACEHOLDER_FG = (180, 200, 210)
ENTRY_PANEL_W = 540
ENTRY_PANEL_H = 540
GRID_COLS = 4
GRID_ROWS = 6
GRID_CELL_W = 240
GRID_CELL_H = 200
GRID_PADDING = 8


def _placeholder(width: int, height: int, label: str) -> np.ndarray:
    img = np.full((height, width, 3), PLACEHOLDER_BG, dtype=np.uint8)
    text = label or "(no image)"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.55
    thickness = 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    x = max(8, (width - tw) // 2)
    y = max(th + 8, (height + th) // 2)
    cv2.putText(img, text, (x, y), font, scale, PLACEHOLDER_FG, thickness, cv2.LINE_AA)
    return img


def _read_or_placeholder(path: Path | None, *, width: int, height: int, label: str) -> np.ndarray:
    if path is None:
        return _placeholder(width, height, label)
    if not path.exists():
        return _placeholder(width, height, f"{label} missing")
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        return _placeholder(width, height, f"{label} unreadable")
    return _fit_into(img, width, height)


def _fit_into(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """Letterbox the image into a `width x height` canvas (BGR)."""
    h, w = img.shape[:2]
    if h == 0 or w == 0:
        return _placeholder(width, height, "(empty image)")
    scale = min(width / w, height / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.full((height, width, 3), PLACEHOLDER_BG, dtype=np.uint8)
    x = (width - nw) // 2
    y = (height - nh) // 2
    canvas[y : y + nh, x : x + nw] = resized
    return canvas


def _resolve(rel_or_abs: str | None, library_root: Path | str) -> Path | None:
    if not rel_or_abs:
        return None
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p
    return Path(library_root) / p


def _label_strip(width: int, height: int, text: str) -> np.ndarray:
    strip = np.full((height, width, 3), (24, 28, 34), dtype=np.uint8)
    cv2.putText(
        strip,
        text[: max(1, width // 8)],
        (8, height - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        PLACEHOLDER_FG,
        1,
        cv2.LINE_AA,
    )
    return strip


def render_library_entry(
    entry: dict[str, Any] | None,
    library_root: Path | str,
) -> np.ndarray:
    """Side-by-side composition: openpose preview (left) + reference /
    generated image (right) + a thin label strip across the top."""
    if entry is None:
        full = _placeholder(
            ENTRY_PANEL_W * 2 + 4, ENTRY_PANEL_H + 32, "library_entry: no entry selected"
        )
        return full

    label = (
        f"{(entry.get('title') or 'untitled')}  ·  "
        f"{(entry.get('avatar_slug') or '—')}  ·  "
        f"{(entry.get('yaw_bin') or '—')}"
    )
    locked = entry.get("locked_by")
    if locked:
        label += f"  [locked by {locked}]"

    op_path = _resolve(entry.get("openpose_png_path"), library_root)
    ref_path = _resolve(
        entry.get("generated_image_path") or entry.get("portrait_path"),
        library_root,
    )

    left = _read_or_placeholder(op_path, width=ENTRY_PANEL_W, height=ENTRY_PANEL_H, label="openpose.png")
    right = _read_or_placeholder(ref_path, width=ENTRY_PANEL_W, height=ENTRY_PANEL_H, label="generated.png / portrait.png")
    top = _label_strip(ENTRY_PANEL_W * 2 + 4, 32, label)

    middle = np.full((ENTRY_PANEL_H, 4, 3), PLACEHOLDER_BG, dtype=np.uint8)
    bottom = np.hstack([left, middle, right])
    return np.vstack([top, bottom])


def render_library_search_results(
    results: list[dict[str, Any]] | None,
    library_root: Path | str,
) -> np.ndarray:
    """4x6 grid of thumbnails. Each cell shows the entry's openpose.png
    (preferred) or generated.png / portrait.png with the title underneath.
    Empty input renders a labeled placeholder."""
    rows = GRID_ROWS
    cols = GRID_COLS
    cell_w, cell_h = GRID_CELL_W, GRID_CELL_H
    pad = GRID_PADDING
    full_w = cols * cell_w + (cols + 1) * pad
    full_h = rows * cell_h + (rows + 1) * pad + 32

    if not results:
        return _placeholder(full_w, full_h, "library_search_results: no entries")

    canvas = np.full((full_h, full_w, 3), (18, 22, 28), dtype=np.uint8)

    title = f"library_search_results: {len(results)} entries"
    cv2.putText(
        canvas,
        title,
        (pad, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        PLACEHOLDER_FG,
        1,
        cv2.LINE_AA,
    )

    for i, entry in enumerate(results[: rows * cols]):
        r, c = divmod(i, cols)
        x = pad + c * (cell_w + pad)
        y = 32 + pad + r * (cell_h + pad)
        thumb_h = cell_h - 24
        thumb = _read_or_placeholder(
            _resolve(
                entry.get("openpose_png_path")
                or entry.get("generated_image_path")
                or entry.get("portrait_path"),
                library_root,
            ),
            width=cell_w,
            height=thumb_h,
            label=str(entry.get("title") or "(thumb)")[:18],
        )
        canvas[y : y + thumb_h, x : x + cell_w] = thumb

        label = str(entry.get("title") or entry.get("entry_id") or "(?)")
        cv2.putText(
            canvas,
            label[:24],
            (x + 4, y + cell_h - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            PLACEHOLDER_FG,
            1,
            cv2.LINE_AA,
        )

    return canvas
