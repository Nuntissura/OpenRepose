"""Command schema, dispatch, and handlers for the LLM control surface.

Spec: `.gov/spec/openrepose_v0_1.md` section "LLM Control Surface".
"""

from __future__ import annotations

import datetime
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .log import Logger
from .openpose_serialize import serialize_to_string
from .rig import OpenReposeRigFitError, Rig
from .rotation import rotate_yaw
from .state import AppState
from .yaw_bin import (
    OpenReposeForbiddenTerminologyError,
    OpenReposeYawBinError,
    parse_bin,
    standard_13_angle_bins,
)


class OpenReposeCommandError(ValueError):
    """Raised when a command is malformed or rejected."""


@dataclass(frozen=True)
class CommandResult:
    """Structured response for one command. Always JSON-serializable."""

    command: str
    status: str  # "ok" | "error"
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "status": self.status,
            "payload": dict(self.payload),
        }


class CommandDispatcher:
    """Single entry point for all LLM-driven commands.

    Holds the shared `AppState`, the active `Rig` (if a portrait is loaded),
    and a `Logger`. All command handlers serialize through `_lock` so
    concurrent requests don't race on rig state. Snapshot subsystem ships
    in WP-I0-003; until then `snapshot` returns a structured error.
    """

    def __init__(
        self,
        state: AppState,
        log: Logger,
        *,
        outputs_root: Path | str = Path("outputs"),
        snapshot_handler: object | None = None,
    ) -> None:
        self.state = state
        self.log = log
        self.outputs_root = Path(outputs_root)
        self._lock = threading.Lock()
        self._rig: Rig | None = None
        self._snapshot_handler = snapshot_handler  # set by WP-I0-003 wiring

    # --- public ----------------------------------------------------------

    def dispatch(self, command_dict: dict[str, Any]) -> CommandResult:
        cmd = command_dict.get("command")
        if not isinstance(cmd, str) or not cmd:
            raise OpenReposeCommandError("missing or empty 'command' field")
        self.log.dbg("cmd.received", command=cmd)
        self.state.begin_command(cmd)
        self.state.write()
        try:
            handler = _HANDLERS.get(cmd)
            if handler is None:
                raise OpenReposeCommandError(f"unknown command: {cmd!r}")
            with self._lock:
                payload = handler(self, command_dict)
            self.state.end_command(status="ok")
            self.state.write()
            self.log.ok("cmd.completed", command=cmd, status="ok")
            return CommandResult(command=cmd, status="ok", payload=payload)
        except (
            OpenReposeCommandError,
            OpenReposeRigFitError,
            OpenReposeForbiddenTerminologyError,
            OpenReposeYawBinError,
            FileNotFoundError,
            NotImplementedError,
        ) as e:
            self.state.add_error(level="ERR", op=f"cmd.{cmd}", reason=str(e))
            self.state.end_command(status="error")
            self.state.write()
            self.log.err(f"cmd.{cmd}", reason=str(e))
            return CommandResult(
                command=cmd,
                status="error",
                payload={"reason": str(e), "type": type(e).__name__},
            )
        except Exception as e:
            # Catch-all for typed errors raised from downstream subsystems
            # (e.g. OpenReposeSnapshotError). Surfaces as a structured error
            # rather than crashing the dispatcher loop.
            self.state.add_error(level="ERR", op=f"cmd.{cmd}", reason=str(e))
            self.state.end_command(status="error")
            self.state.write()
            self.log.err(f"cmd.{cmd}", reason=str(e))
            return CommandResult(
                command=cmd,
                status="error",
                payload={"reason": str(e), "type": type(e).__name__},
            )

    @property
    def rig(self) -> Rig | None:
        return self._rig


# --- handlers (registered in _HANDLERS at module bottom) --------------------


def _h_import_portrait(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    path = cmd.get("path")
    avatar_slug = cmd.get("avatar_slug")
    if not isinstance(path, str) or not path:
        raise OpenReposeCommandError("import_portrait requires 'path'")
    if avatar_slug is not None and (
        not isinstance(avatar_slug, str) or not avatar_slug
    ):
        raise OpenReposeCommandError("avatar_slug must be a non-empty string")
    p = Path(path)
    d.state.set_portrait(str(p), avatar_slug=avatar_slug)
    d.state.set_rig(status="fitting")
    d.state.write()
    d.log.ok("rig.fitting", portrait=str(p), avatar_slug=avatar_slug or "")

    rig = Rig.from_portrait(p)
    d._rig = rig

    # Compute openpose-mapped counts for the state snapshot.
    face_70 = rig.openpose_face_70()
    body_18, _conf_18 = rig.openpose_body_18()
    face_visible = int((face_70[:, 0] != 0).sum() + (face_70[:, 1] != 0).sum() > 0)
    # Approximate visible: count non-(0,0) rows.
    import numpy as np

    face_visible_count = int(np.count_nonzero(np.any(face_70[:, :2] != 0, axis=1)))
    body_visible_count = int(np.count_nonzero(np.any(body_18[:, :2] != 0, axis=1)))

    d.state.set_rig(
        status="ok",
        fit_duration_ms=rig.fit_metrics.fit_duration_ms,
        face_landmark_count=rig.fit_metrics.face_landmark_count,
        body_landmark_count=rig.fit_metrics.body_landmark_count,
        face_visible_in_openpose=face_visible_count,
        body_visible_in_openpose=body_visible_count,
    )
    d.state.write()
    d.log.ok(
        "rig.fit",
        portrait=str(p),
        face=rig.fit_metrics.face_landmark_count,
        body=rig.fit_metrics.body_landmark_count,
        t_ms=rig.fit_metrics.fit_duration_ms,
        body_partial=rig.fit_metrics.body_partial,
    )
    return {
        "portrait": str(p),
        "avatar_slug": avatar_slug,
        "fit_duration_ms": rig.fit_metrics.fit_duration_ms,
        "face_landmark_count": rig.fit_metrics.face_landmark_count,
        "body_landmark_count": rig.fit_metrics.body_landmark_count,
        "body_partial": rig.fit_metrics.body_partial,
        "body_partial_missing": list(rig.fit_metrics.body_partial_missing),
    }


def _h_set_yaw(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    raw = cmd.get("value_deg")
    if not isinstance(raw, (int, float)):
        raise OpenReposeCommandError("set_yaw requires numeric 'value_deg'")
    value = float(raw)
    if value < -180.0 or value > 180.0:
        raise OpenReposeCommandError(f"value_deg out of range: {value}")
    from .yaw_bin import signed_deg_to_bin

    bin_obj = signed_deg_to_bin(value)
    d.state.set_yaw(value_deg=value, bin_label=bin_obj.label)
    d.state.write()
    d.log.ok("yaw.set", value_deg=value, bin=bin_obj.label)
    return {"value_deg": value, "bin": bin_obj.label}


def _h_set_yaw_bin(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    bin_label = cmd.get("bin")
    if not isinstance(bin_label, str) or not bin_label:
        raise OpenReposeCommandError("set_yaw_bin requires 'bin'")
    bin_obj = parse_bin(bin_label)
    d.state.set_yaw(value_deg=bin_obj.signed_deg, bin_label=bin_obj.label)
    d.state.write()
    d.log.ok("yaw.set_bin", bin=bin_obj.label, signed_deg=bin_obj.signed_deg)
    return {"value_deg": bin_obj.signed_deg, "bin": bin_obj.label}


def _h_export_single(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    if d._rig is None:
        raise OpenReposeCommandError("no portrait loaded; send import_portrait first")
    bin_label = d.state.yaw["current_bin"]
    bin_obj = parse_bin(bin_label)
    avatar_slug = d.state.avatar_slug or "unknown"
    out_dir_raw = cmd.get("out_dir")
    if isinstance(out_dir_raw, str) and out_dir_raw:
        out_dir = Path(out_dir_raw)
    else:
        out_dir = d.outputs_root / avatar_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_bin = bin_obj.label.replace(" ", "-")
    out_json = out_dir / f"{avatar_slug}_yaw_{safe_bin}.json"

    rotated = rotate_yaw(d._rig, bin_obj)
    payload = serialize_to_string(rotated, indent=None)
    out_json.write_text(payload + "\n", encoding="utf-8")

    d.state.add_export(type_="single", out_dir=str(out_dir), files=[str(out_json)])
    d.state.write()
    d.log.ok(
        "export.single",
        avatar_slug=avatar_slug,
        bin=bin_obj.label,
        out=str(out_json),
    )
    return {"out_dir": str(out_dir), "files": [str(out_json)], "bin": bin_obj.label}


def _h_export_batch(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    if d._rig is None:
        raise OpenReposeCommandError("no portrait loaded; send import_portrait first")
    avatar_slug = d.state.avatar_slug or "unknown"
    angles = cmd.get("angles")
    if angles is None:
        angles = standard_13_angle_bins()
    if not isinstance(angles, list) or not all(isinstance(a, str) for a in angles):
        raise OpenReposeCommandError("angles must be a list of bin strings")

    out_dir_raw = cmd.get("out_dir")
    if isinstance(out_dir_raw, str) and out_dir_raw:
        out_dir = Path(out_dir_raw)
    else:
        run_tag = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        out_dir = d.outputs_root / avatar_slug / run_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for label in angles:
        bin_obj = parse_bin(label)  # validates each label
        safe_bin = bin_obj.label.replace(" ", "-")
        out_json = out_dir / f"{avatar_slug}_yaw_{safe_bin}.json"
        rotated = rotate_yaw(d._rig, bin_obj)
        payload = serialize_to_string(rotated, indent=None)
        out_json.write_text(payload + "\n", encoding="utf-8")
        written.append(str(out_json))

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "avatar_slug": avatar_slug,
                "portrait": d.state.portrait,
                "angles": angles,
                "files": written,
                "completed_at": _now_iso(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    written.append(str(manifest_path))

    d.state.add_export(type_="batch", out_dir=str(out_dir), files=written)
    d.state.write()
    d.log.ok(
        "export.batch",
        avatar_slug=avatar_slug,
        angles=len(angles),
        out_dir=str(out_dir),
    )
    return {"out_dir": str(out_dir), "files": written, "angles": angles}


def _h_snapshot(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    target = cmd.get("target")
    if not isinstance(target, str) or not target:
        raise OpenReposeCommandError("snapshot requires 'target'")
    out_path = cmd.get("out_path")

    # Build the rotated rig at the current yaw if a rig is loaded; viewport
    # snapshots need it. Widget-grab targets work without a rig.
    rotated = None
    if d._rig is not None:
        bin_obj = parse_bin(d.state.yaw["current_bin"])
        rotated = rotate_yaw(d._rig, bin_obj)

    from .snapshot import snapshot as do_snapshot

    snapshots_root = d.outputs_root / ".runtime" / "snapshots"
    manifest_path = d.outputs_root / ".runtime" / "snapshots.jsonl"
    out = do_snapshot(
        target,
        rotated=rotated,
        out_path=out_path,
        snapshots_root=snapshots_root,
        manifest_path=manifest_path,
        state=d.state,
    )
    d.log.ok("viewport.snapshot", target=target, out=str(out))
    return {"target": target, "out_path": str(out)}


def _h_dump_rig(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    if d._rig is None:
        raise OpenReposeCommandError("no rig loaded; send import_portrait first")
    out_path_raw = cmd.get("out_path")
    if isinstance(out_path_raw, str) and out_path_raw:
        out_path = Path(out_path_raw)
    else:
        ts = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%dT%H%M%S")
        out_path = (
            d.outputs_root / ".runtime" / f"rig_dump_{ts}.json"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rig = d._rig
    payload = {
        "portrait_size": list(rig.portrait_size),
        "head_anchor": rig.head_anchor.tolist(),
        "fit_metrics": {
            "portrait_path": rig.fit_metrics.portrait_path,
            "portrait_width": rig.fit_metrics.portrait_width,
            "portrait_height": rig.fit_metrics.portrait_height,
            "face_landmark_count": rig.fit_metrics.face_landmark_count,
            "body_landmark_count": rig.fit_metrics.body_landmark_count,
            "fit_duration_ms": rig.fit_metrics.fit_duration_ms,
            "body_partial": rig.fit_metrics.body_partial,
            "body_partial_missing": list(rig.fit_metrics.body_partial_missing),
        },
        "face_mesh_shape": list(rig.face_mesh.shape),
        "body_kps_shape": list(rig.body_kps.shape),
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    d.log.ok("rig.dump", out=str(out_path))
    return {"out_path": str(out_path)}


def _h_dump_state(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    out_path_raw = cmd.get("out_path")
    if isinstance(out_path_raw, str) and out_path_raw:
        out_path = Path(out_path_raw)
    else:
        ts = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%dT%H%M%S")
        out_path = d.outputs_root / ".runtime" / f"state_dump_{ts}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(d.state.to_dict(), indent=2), encoding="utf-8")
    d.log.ok("state.dump", out=str(out_path))
    return {"out_path": str(out_path)}


def _h_clear_outputs(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    scope = cmd.get("scope", "all")
    if scope not in ("snapshots", "exports", "all"):
        raise OpenReposeCommandError(f"unknown clear scope: {scope!r}")
    if scope in ("snapshots", "all"):
        d.state.snapshots.clear()
    if scope in ("exports", "all"):
        d.state.exports.clear()
    d.state.write()
    d.log.ok("state.clear", scope=scope)
    return {"scope": scope}


def _now_iso() -> str:
    return datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{datetime.datetime.now(tz=datetime.UTC).microsecond // 1000:03d}Z"
    )


_HANDLERS = {
    "import_portrait": _h_import_portrait,
    "set_yaw": _h_set_yaw,
    "set_yaw_bin": _h_set_yaw_bin,
    "export_single": _h_export_single,
    "export_batch": _h_export_batch,
    "snapshot": _h_snapshot,
    "dump_rig": _h_dump_rig,
    "dump_state": _h_dump_state,
    "clear_outputs": _h_clear_outputs,
}
