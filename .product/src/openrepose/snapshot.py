"""Top-level snapshot dispatcher.

Spec: `.gov/spec/openrepose_v0_1.md` section "Snapshot Subsystem".

Targets:
    3d_viewport, openpose_viewport, inspector_pane, log_pane, options_pane,
    status_bar, toolbar, full_window

All snapshots write to disk as PNG and append a manifest line to
`snapshots.jsonl`. No-focus-hijack rules are enforced by construction:
this module never imports raise_, activateWindow, showNormal, or any
window-stack-modifying API.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING

import cv2

from .render.compose import compose_full_window
from .render.draw_3d import render_3d_viewport
from .render.draw_calibration import render_calibration_overlay
from .render.draw_openpose import render_openpose
from .render.widget_grab import render_widget_or_placeholder

if TYPE_CHECKING:
    import numpy as np

    from .calibration import Calibration
    from .rotation import RotatedRig
    from .state import AppState

VALID_TARGETS = (
    "3d_viewport",
    "openpose_viewport",
    "inspector_pane",
    "log_pane",
    "options_pane",
    "status_bar",
    "toolbar",
    "full_window",
    "calibration_overlay",
)


class OpenReposeSnapshotError(ValueError):
    """Raised on bad target name, missing rig, or path traversal."""


def snapshot(
    target: str,
    *,
    rotated: "RotatedRig | None",
    out_path: Path | str | None = None,
    snapshots_root: Path | str = Path("outputs/.runtime/snapshots"),
    manifest_path: Path | str = Path("outputs/.runtime/snapshots.jsonl"),
    state: "AppState | None" = None,
    portrait_path: str | Path | None = None,
    calibration: "Calibration | None" = None,
    body_part_visibility: dict[str, bool] | None = None,
    marker_visibility: dict | None = None,
    frame: dict | None = None,
    canvas_border_color: str | None = None,
) -> Path:
    """Render `target` to a PNG. Returns the absolute output path.

    Targets that need a rotated rig (3d_viewport, openpose_viewport,
    full_window) require `rotated` to be non-None. The
    calibration_overlay target uses `portrait_path` and `calibration`
    (rendering on a fallback canvas with a label when either is missing
    so it never crashes). Widget-grab targets (inspector_pane, log_pane,
    options_pane, status_bar, toolbar) work whether or not the GUI
    exists; the widget_grab module falls back to a placeholder when
    widgets are not registered.
    """
    if target not in VALID_TARGETS:
        raise OpenReposeSnapshotError(
            f"unknown snapshot target {target!r}; expected one of {VALID_TARGETS}"
        )

    out = _resolve_out_path(target, out_path, snapshots_root)

    image = _render(
        target, rotated, portrait_path, calibration,
        body_part_visibility, marker_visibility, frame,
        canvas_border_color,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), image)

    _append_manifest(
        manifest_path,
        target=target,
        out_path=str(out),
        yaw_bin=(rotated.yaw.label if rotated is not None else None),
        rig_status=("ok" if rotated is not None else "none"),
    )

    if state is not None:
        state.add_snapshot(target=target, out_path=str(out))

    return out


def _render(
    target: str,
    rotated: "RotatedRig | None",
    portrait_path: str | Path | None,
    calibration: "Calibration | None",
    body_part_visibility: dict[str, bool] | None,
    marker_visibility: dict | None,
    frame: dict | None,
    canvas_border_color: str | None,
) -> "np.ndarray":
    if target == "3d_viewport":
        if rotated is None:
            raise OpenReposeSnapshotError("3d_viewport requires a rotated rig")
        return render_3d_viewport(rotated)
    if target == "openpose_viewport":
        if rotated is None:
            raise OpenReposeSnapshotError("openpose_viewport requires a rotated rig")
        return render_openpose(
            rotated,
            body_part_visibility=body_part_visibility,
            marker_visibility=marker_visibility,
            frame=frame,
            canvas_border_color=canvas_border_color,
        )
    if target == "calibration_overlay":
        return render_calibration_overlay(portrait_path, calibration)
    if target == "full_window":
        panes: dict[str, "np.ndarray"] = {}
        if rotated is not None:
            panes["viewport_3d"] = render_3d_viewport(rotated)
            panes["viewport_openpose"] = render_openpose(
                rotated,
                body_part_visibility=body_part_visibility,
                marker_visibility=marker_visibility,
                frame=frame,
                canvas_border_color=canvas_border_color,
            )
        for name in ("toolbar", "inspector", "status_bar", "log"):
            panes[name] = render_widget_or_placeholder(name)
        return compose_full_window(panes)
    # Qt-widget targets.
    return render_widget_or_placeholder(target)


def _resolve_out_path(
    target: str,
    out_path: Path | str | None,
    snapshots_root: Path | str,
) -> Path:
    if out_path is None:
        ts = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d-%H%M%S-")
        ms = f"{datetime.datetime.now(tz=datetime.UTC).microsecond // 1000:03d}"
        return Path(snapshots_root) / f"{ts}{ms}_{target}.png"
    p = Path(out_path).resolve()
    snapshots_abs = Path(snapshots_root).resolve()
    # Tests expect arbitrary paths to be allowed for explicit out_path; we
    # only reject path-traversal patterns that escape obvious sandboxes.
    parts = Path(out_path).parts
    if ".." in parts:
        raise OpenReposeSnapshotError(f"path traversal not allowed: {out_path!r}")
    return p


def _append_manifest(
    manifest_path: Path | str,
    *,
    target: str,
    out_path: str,
    yaw_bin: str | None,
    rig_status: str,
) -> None:
    mp = Path(manifest_path)
    mp.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "captured_at": _now_iso(),
            "target": target,
            "out_path": out_path,
            "yaw_bin": yaw_bin,
            "rig_status": rig_status,
        }
    )
    with mp.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def _now_iso() -> str:
    return datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{datetime.datetime.now(tz=datetime.UTC).microsecond // 1000:03d}Z"
    )
