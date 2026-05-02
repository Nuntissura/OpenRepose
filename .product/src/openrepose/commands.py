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

from .calibration import (
    ALL_MARKER_NAMES,
    MEDIAPIPE_FACEMESH_INDEX_BY_MARKER,
    Calibration,
    Marker,
    OpenReposeCalibrationError,
    calibration_path,
    load as load_calibration,
    save as save_calibration,
)
from .log import Logger
from .openpose_schema import BODY_GROUPS, MARKER_SCHEMAS, default_marker_visibility
from .openpose_serialize import serialize_to_string
from .rig import OpenReposeRigFitError, Rig
from .rotation import rotate_yaw
from .settings import (
    OpenReposeSettingsError,
    Settings,
    render_subdir,
)
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
        settings: "Settings | None" = None,
    ) -> None:
        self.state = state
        self.log = log
        self.outputs_root = Path(outputs_root)
        self.settings = settings  # operator-configured paths; None = legacy default
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
            OpenReposeCalibrationError,
            OpenReposeSettingsError,
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

    # Auto-load per-avatar calibration if one exists for this avatar slug.
    # Spec "Application Flow": calibration is applied during Rig.from_portrait
    # before rotation. When no calibration JSON exists, the rig pipeline is
    # equivalent to the identity field.
    cal = None
    cal_loaded_from: str | None = None
    if avatar_slug:
        cal_p = calibration_path(d.outputs_root, avatar_slug)
        cal = load_calibration(cal_p)
        if cal is not None:
            cal_loaded_from = str(cal_p)

    rig = Rig.from_portrait(p, calibration=cal)
    d._rig = rig
    _refresh_calibration_state(
        d.state,
        active_avatar=avatar_slug,
        calibration=cal,
        loaded_from=cal_loaded_from,
    )

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
    elif d.settings is not None:
        root = d.settings.resolved_export_folder()
        subdir = render_subdir(
            d.settings.single_export_subdir_template,
            avatar=avatar_slug,
            run_tag="",
        )
        out_dir = root / subdir
    else:
        out_dir = d.outputs_root / avatar_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_bin = bin_obj.label.replace(" ", "-")
    out_json = out_dir / f"{avatar_slug}_yaw_{safe_bin}.json"

    rotated = rotate_yaw(d._rig, bin_obj)
    payload = serialize_to_string(
        rotated,
        indent=None,
        body_part_visibility=dict(d.state.body_part_visibility),
        marker_visibility=_copy_marker_visibility(d.state.marker_visibility),
    )
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
        if d.settings is not None:
            root = d.settings.resolved_export_folder()
            subdir = render_subdir(
                d.settings.batch_export_subdir_template,
                avatar=avatar_slug,
                run_tag=run_tag,
            )
            out_dir = root / subdir
        else:
            out_dir = d.outputs_root / avatar_slug / run_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    bpv = dict(d.state.body_part_visibility)
    mv = _copy_marker_visibility(d.state.marker_visibility)
    for label in angles:
        bin_obj = parse_bin(label)  # validates each label
        safe_bin = bin_obj.label.replace(" ", "-")
        out_json = out_dir / f"{avatar_slug}_yaw_{safe_bin}.json"
        rotated = rotate_yaw(d._rig, bin_obj)
        payload = serialize_to_string(
            rotated,
            indent=None,
            body_part_visibility=bpv,
            marker_visibility=mv,
        )
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
    portrait_path = d.state.portrait
    calibration = d._rig.calibration if d._rig is not None else None
    out = do_snapshot(
        target,
        rotated=rotated,
        out_path=out_path,
        snapshots_root=snapshots_root,
        manifest_path=manifest_path,
        state=d.state,
        portrait_path=portrait_path,
        calibration=calibration,
        body_part_visibility=dict(d.state.body_part_visibility),
        marker_visibility=_copy_marker_visibility(d.state.marker_visibility),
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


# --- calibration handlers ----------------------------------------------------


def _refresh_calibration_state(
    state: AppState,
    *,
    active_avatar: str | None,
    calibration: Calibration | None,
    loaded_from: str | None,
) -> None:
    """Mirror the active calibration onto state.calibration."""
    if calibration is None:
        state.set_calibration_status(
            active_avatar=active_avatar,
            completeness="none",
            marker_count=0,
            missing_required=(),
            field_cached=False,
            loaded_from=None,
        )
    else:
        state.set_calibration_status(
            active_avatar=active_avatar,
            completeness=calibration.completeness,
            marker_count=calibration.marker_count,
            missing_required=calibration.missing_required,
            field_cached=calibration.completeness != "none",
            loaded_from=loaded_from,
        )


def _h_set_calibration_points(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Update operator marker positions for the active avatar.

    Payload (per spec):
        markers: [{name, operator_xy: [x, y], mediapipe_xy?: [x, y]}, ...]
        merge:   bool (default True). True: supplied markers update / insert;
                 existing markers not in the payload are kept. False: payload
                 replaces the entire marker set.

    When `mediapipe_xy` is omitted on a marker, the dispatcher derives it
    from the active rig's raw FaceMesh detection at the canonical landmark
    index for that anatomical name.
    """
    avatar_slug = d.state.avatar_slug
    if not avatar_slug:
        raise OpenReposeCommandError(
            "set_calibration_points requires an active avatar (send "
            "import_portrait with avatar_slug first)"
        )
    raw_markers = cmd.get("markers")
    if not isinstance(raw_markers, list):
        raise OpenReposeCommandError(
            "set_calibration_points requires 'markers' as a list"
        )
    merge = cmd.get("merge", True)
    if not isinstance(merge, bool):
        raise OpenReposeCommandError("'merge' must be a boolean")

    # Source for derived mediapipe_xy lookups.
    rig = d._rig
    raw_face: Any = None
    if rig is not None:
        raw_face = (
            rig.raw_face_mesh if rig.raw_face_mesh is not None else rig.face_mesh
        )

    parsed: list[Marker] = []
    for i, raw in enumerate(raw_markers):
        if not isinstance(raw, dict):
            raise OpenReposeCommandError(f"marker {i} must be an object")
        name = raw.get("name")
        if name not in ALL_MARKER_NAMES:
            raise OpenReposeCommandError(
                f"marker {i} has unknown name {name!r}; allowed: "
                f"{sorted(ALL_MARKER_NAMES)}"
            )
        op_xy = raw.get("operator_xy")
        if not (isinstance(op_xy, list) and len(op_xy) == 2):
            raise OpenReposeCommandError(
                f"marker {i} requires 'operator_xy' as [x, y]"
            )
        mp_xy_raw = raw.get("mediapipe_xy")
        if mp_xy_raw is None:
            if raw_face is None:
                raise OpenReposeCommandError(
                    f"marker {i} missing 'mediapipe_xy' and no rig is loaded "
                    "to derive it from"
                )
            idx = MEDIAPIPE_FACEMESH_INDEX_BY_MARKER[name]
            if idx >= raw_face.shape[0]:
                raise OpenReposeCommandError(
                    f"marker {name!r} maps to FaceMesh index {idx} which is "
                    f"out of range (face_mesh has {raw_face.shape[0]} points)"
                )
            mp_xy = (float(raw_face[idx, 0]), float(raw_face[idx, 1]))
        else:
            if not (isinstance(mp_xy_raw, list) and len(mp_xy_raw) == 2):
                raise OpenReposeCommandError(
                    f"marker {i} 'mediapipe_xy' must be [x, y] when supplied"
                )
            mp_xy = (float(mp_xy_raw[0]), float(mp_xy_raw[1]))
        parsed.append(
            Marker(
                name=name,
                operator_xy=(float(op_xy[0]), float(op_xy[1])),
                mediapipe_xy=mp_xy,
            )
        )

    cal_p = calibration_path(d.outputs_root, avatar_slug)
    existing = load_calibration(cal_p)

    if merge and existing is not None:
        merged_by_name: dict[str, Marker] = {m.name: m for m in existing.markers}
        for m in parsed:
            merged_by_name[m.name] = m
        merged = tuple(merged_by_name.values())
        new_cal = Calibration(
            avatar_slug=existing.avatar_slug or avatar_slug,
            image_path=existing.image_path or (d.state.portrait or ""),
            image_size=existing.image_size,
            mediapipe_version=existing.mediapipe_version,
            markers=merged,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
    else:
        portrait = d.state.portrait or ""
        image_size: tuple[int, int] = (0, 0)
        if rig is not None:
            image_size = rig.portrait_size
        elif existing is not None:
            image_size = existing.image_size
        new_cal = Calibration(
            avatar_slug=avatar_slug,
            image_path=portrait,
            image_size=image_size,
            mediapipe_version=_mediapipe_version_string(),
            markers=tuple(parsed),
            created_at=existing.created_at if existing is not None else "",
            updated_at="",
        )

    save_calibration(new_cal, cal_p)

    if rig is not None:
        d._rig = rig.with_calibration(new_cal)

    _refresh_calibration_state(
        d.state,
        active_avatar=avatar_slug,
        calibration=new_cal,
        loaded_from=str(cal_p),
    )
    d.state.write()
    d.log.ok(
        "calibration.set",
        avatar=avatar_slug,
        marker_count=new_cal.marker_count,
        completeness=new_cal.completeness,
        merge=merge,
    )
    return {
        "avatar_slug": avatar_slug,
        "marker_count": new_cal.marker_count,
        "completeness": new_cal.completeness,
        "missing_required": list(new_cal.missing_required),
        "loaded_from": str(cal_p),
    }


def _h_dump_calibration(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Return the active avatar's calibration JSON in the response payload."""
    avatar_slug = d.state.avatar_slug
    if not avatar_slug:
        raise OpenReposeCommandError(
            "dump_calibration requires an active avatar"
        )
    cal_p = calibration_path(d.outputs_root, avatar_slug)
    cal = load_calibration(cal_p)
    if cal is None:
        d.log.ok("calibration.dump", avatar=avatar_slug, present=False)
        return {
            "avatar_slug": avatar_slug,
            "present": False,
            "calibration": None,
        }
    d.state.mark_calibration_dump()
    d.state.write()
    d.log.ok(
        "calibration.dump",
        avatar=avatar_slug,
        present=True,
        marker_count=cal.marker_count,
    )
    return {
        "avatar_slug": avatar_slug,
        "present": True,
        "calibration": {
            "schema_version": 1,
            "avatar_slug": cal.avatar_slug,
            "image_path": cal.image_path,
            "image_size": list(cal.image_size),
            "mediapipe_version": cal.mediapipe_version,
            "completeness": cal.completeness,
            "markers": [
                {
                    "name": m.name,
                    "operator_xy": list(m.operator_xy),
                    "mediapipe_xy": list(m.mediapipe_xy),
                }
                for m in cal.markers
            ],
            "created_at": cal.created_at,
            "updated_at": cal.updated_at,
        },
        "loaded_from": str(cal_p),
    }


def _h_clear_calibration(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Delete the active avatar's calibration JSON, drop the cached field,
    re-fit the rig with no calibration."""
    avatar_slug = d.state.avatar_slug
    if not avatar_slug:
        raise OpenReposeCommandError(
            "clear_calibration requires an active avatar"
        )
    cal_p = calibration_path(d.outputs_root, avatar_slug)
    deleted = False
    if cal_p.exists():
        cal_p.unlink()
        deleted = True

    if d._rig is not None:
        d._rig = d._rig.with_calibration(None)

    _refresh_calibration_state(
        d.state,
        active_avatar=avatar_slug,
        calibration=None,
        loaded_from=None,
    )
    d.state.write()
    d.log.ok("calibration.clear", avatar=avatar_slug, deleted=deleted)
    return {"avatar_slug": avatar_slug, "deleted": deleted}


def _h_get_calibration_status(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Read-only status for the active calibration. Mirrors state.calibration."""
    return dict(d.state.calibration)


# --- settings handler --------------------------------------------------------


# --- body part visibility handlers ------------------------------------------


def _h_set_body_part_visibility(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Set one or more body-part group flags. Payload:
        {"face": bool, "body_torso": bool, "arms": bool, "legs": bool, "hands": bool}
    Any subset is accepted; unmentioned flags are kept. Unknown group names raise.
    """
    updates: dict[str, bool] = {}
    for k, v in cmd.items():
        if k in ("command",):
            continue
        if k not in BODY_GROUPS:
            raise OpenReposeCommandError(
                f"unknown body_part group {k!r}; allowed: {BODY_GROUPS}"
            )
        if not isinstance(v, bool):
            raise OpenReposeCommandError(
                f"body_part group {k!r} requires a boolean; got {type(v).__name__}"
            )
        updates[k] = v
    if not updates:
        raise OpenReposeCommandError(
            "set_body_part_visibility requires at least one group flag"
        )

    new_bpv = dict(d.state.body_part_visibility)
    new_bpv.update(updates)
    with d.state._lock:
        d.state.body_part_visibility = new_bpv
    d.state.write()
    d.log.ok(
        "body_part.set",
        **{k: bool(v) for k, v in updates.items()},
    )
    return {"body_part_visibility": dict(new_bpv), "updated": updates}


def _h_get_body_part_visibility(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Read-only state.body_part_visibility."""
    return {"body_part_visibility": dict(d.state.body_part_visibility)}


# --- per-marker visibility handlers (WP-I1-029) -----------------------------


def _copy_marker_visibility(mv: dict) -> dict:
    """Defensive copy: state holds the canonical dict; serializers/renderers
    get their own copy so accidental mutation does not leak across calls."""
    return {schema: dict(overrides) for schema, overrides in mv.items()}


def _h_set_marker_visibility(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Set per-marker visibility override. Two payload shapes:

        {"command": "set_marker_visibility", "schema": "body_18", "index": 4, "visible": false}
        {"command": "set_marker_visibility", "schema": "face_70", "indices": [12, 13, 14], "visible": false}

    Single `index` and bulk `indices` are mutually exclusive; one is required.
    Unknown schema, missing visible, or out-of-range index raises a structured
    error.
    """
    schema = cmd.get("schema")
    if schema not in MARKER_SCHEMAS:
        raise OpenReposeCommandError(
            f"set_marker_visibility 'schema' must be one of {MARKER_SCHEMAS}; got {schema!r}"
        )
    visible = cmd.get("visible")
    if not isinstance(visible, bool):
        raise OpenReposeCommandError(
            "set_marker_visibility requires 'visible' as a boolean"
        )
    single = cmd.get("index")
    bulk = cmd.get("indices")
    if (single is None) == (bulk is None):
        raise OpenReposeCommandError(
            "set_marker_visibility requires exactly one of 'index' or 'indices'"
        )
    if single is not None:
        indices = [int(single)]
    else:
        if not isinstance(bulk, list):
            raise OpenReposeCommandError("'indices' must be a list of ints")
        indices = [int(i) for i in bulk]

    # Validate range against the schema.
    from .openpose_schema import _SCHEMA_COUNT

    upper = _SCHEMA_COUNT[schema]
    for idx in indices:
        if not (0 <= idx < upper):
            raise OpenReposeCommandError(
                f"{schema} index {idx} out of range [0, {upper})"
            )

    new_mv = _copy_marker_visibility(d.state.marker_visibility)
    overrides = new_mv.setdefault(schema, {})
    for idx in indices:
        overrides[str(idx)] = bool(visible)
    with d.state._lock:
        d.state.marker_visibility = new_mv
    d.state.write()
    d.log.ok(
        "marker.set",
        schema=schema,
        count=len(indices),
        visible=bool(visible),
    )
    return {
        "marker_visibility": {
            k: dict(v) for k, v in new_mv.items()
        },
        "schema": schema,
        "updated_count": len(indices),
        "visible": bool(visible),
    }


def _h_get_marker_visibility(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Read-only state.marker_visibility."""
    return {
        "marker_visibility": _copy_marker_visibility(d.state.marker_visibility)
    }


def _h_reset_marker_visibility(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Clear all per-marker overrides; markers inherit body-part group flags."""
    with d.state._lock:
        d.state.marker_visibility = default_marker_visibility()
    d.state.write()
    d.log.ok("marker.reset")
    return {"marker_visibility": dict(d.state.marker_visibility)}


def _h_dump_settings(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    """Return the effective settings JSON (operator-chosen export folder +
    subdir templates), the resolved export folder, and whether the default
    fallback is in use."""
    if d.settings is None:
        return {
            "present": False,
            "settings": None,
            "resolved_export_folder": str(d.outputs_root),
            "default_used": True,
        }
    resolved, default_used = (
        d.settings.export_folder_resolved_with_fallback_flag()
    )
    return {
        "present": True,
        "settings": d.settings.to_dict(),
        "settings_path": str(d.settings.settings_path),
        "resolved_export_folder": str(resolved),
        "default_used": default_used,
    }


def _mediapipe_version_string() -> str:
    try:
        import mediapipe  # type: ignore[import-untyped]

        return str(getattr(mediapipe, "__version__", "unknown"))
    except Exception:
        return "unknown"


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
    "set_calibration_points": _h_set_calibration_points,
    "dump_calibration": _h_dump_calibration,
    "clear_calibration": _h_clear_calibration,
    "get_calibration_status": _h_get_calibration_status,
    "set_body_part_visibility": _h_set_body_part_visibility,
    "get_body_part_visibility": _h_get_body_part_visibility,
    "set_marker_visibility": _h_set_marker_visibility,
    "get_marker_visibility": _h_get_marker_visibility,
    "reset_marker_visibility": _h_reset_marker_visibility,
    "dump_settings": _h_dump_settings,
}
