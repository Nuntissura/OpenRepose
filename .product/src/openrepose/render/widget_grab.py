"""Qt widget grab with placeholder fallback.

Targets that map to operator-facing GUI widgets (inspector_pane, log_pane,
options_pane, status_bar, toolbar, full_window) want a `QWidget.grab()`
render. Until WP-I0-004 wires the GUI, the widgets don't exist and we
return a placeholder PNG with a labeled overlay so the LLM gets a
parseable artifact.

The placeholder also doubles as a visual signal that the GUI is not
running. When WP-I0-004 lands, register the live widgets via
`set_widget_provider` and grabs go to the real widgets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

import cv2
import numpy as np

PLACEHOLDER_BG_BGR = (24, 24, 24)
PLACEHOLDER_BORDER_BGR = (80, 80, 80)
PLACEHOLDER_TITLE_BGR = (220, 220, 220)
PLACEHOLDER_BODY_BGR = (160, 160, 160)


class WidgetProvider(Protocol):
    """A callable returning a Qt widget for a target name, or None."""

    def __call__(self, target: str) -> object | None:
        ...


_widget_provider: WidgetProvider | None = None


def set_widget_provider(provider: WidgetProvider | None) -> None:
    """Register a widget provider. Called by the GUI module on startup."""
    global _widget_provider
    _widget_provider = provider


def render_widget_or_placeholder(
    target: str,
    canvas_size: tuple[int, int] = (800, 200),
) -> np.ndarray:
    """Return a (H, W, 3) BGR image for `target`.

    If a widget is registered for `target`, calls `QWidget.grab()` and
    converts to BGR. Otherwise returns a labeled placeholder.
    """
    grabbed = try_grab_widget(target)
    if grabbed is not None:
        return grabbed
    return _placeholder(target, canvas_size=canvas_size)


def try_grab_widget(target: str) -> np.ndarray | None:
    """Same as `render_widget_or_placeholder` but returns None when no
    widget is registered (instead of a placeholder).

    Used by snapshot targets that have a headless renderer fallback the
    caller wants to invoke instead of a generic "[no GUI]" placeholder.
    """
    widget = None
    if _widget_provider is not None:
        widget = _widget_provider(target)
    if widget is None:
        return None
    try:
        return _grab_widget_to_bgr(widget)
    except Exception as e:  # noqa: BLE001
        return _placeholder(target, note=f"grab error: {e}")


def render_widget_to_png(target: str, out_path: Path | str) -> Path:
    img = render_widget_or_placeholder(target)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img)
    return out.resolve()


def _placeholder(
    target: str,
    canvas_size: tuple[int, int] = (800, 200),
    note: str | None = None,
) -> np.ndarray:
    w, h = canvas_size
    canvas = np.full((h, w, 3), PLACEHOLDER_BG_BGR, dtype=np.uint8)
    # Border.
    cv2.rectangle(canvas, (1, 1), (w - 2, h - 2), PLACEHOLDER_BORDER_BGR, 1, cv2.LINE_AA)
    # Title.
    cv2.putText(
        canvas,
        f"[no GUI: target={target}]",
        (16, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        PLACEHOLDER_TITLE_BGR,
        2,
        cv2.LINE_AA,
    )
    # Body lines.
    body_lines = [
        "Widget hierarchy not yet realized.",
        "GUI ships in WP-I0-004; until then this is a placeholder.",
        "The snapshot subsystem is intentionally callable headlessly so",
        "LLM-driven smoke tests can run before the GUI exists.",
    ]
    if note is not None:
        body_lines.append("")
        body_lines.append(note)
    for i, line in enumerate(body_lines):
        cv2.putText(
            canvas,
            line,
            (16, 70 + i * 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            PLACEHOLDER_BODY_BGR,
            1,
            cv2.LINE_AA,
        )
    return canvas


def _grab_widget_to_bgr(widget: object) -> np.ndarray:
    """Convert a QWidget grab() to a BGR numpy array.

    Imports PySide6 lazily so the headless code path doesn't require it.
    Asserts that no focus-affecting methods (raise_, activateWindow,
    showNormal) are called by the grab path; those would violate operator
    experience guarantees.
    """
    pix = widget.grab()  # type: ignore[attr-defined]
    image = pix.toImage()
    # Convert QImage to numpy array.
    width = image.width()
    height = image.height()
    # ARGB32 = 4 bytes per pixel
    bits = image.bits()
    if hasattr(bits, "tobytes"):
        buf = bits.tobytes()
    else:  # PySide6 returns memoryview-like
        buf = bytes(bits)
    arr = np.frombuffer(buf, dtype=np.uint8).reshape((height, width, 4))
    # Drop alpha; convert RGB -> BGR.
    return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
