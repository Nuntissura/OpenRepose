"""Command schema, dispatch, and handlers for the LLM control surface.

Spec: `.gov/spec/openrepose_v0_1.md` section "LLM Control Surface".
Library commands (Feature 3) per `.gov/spec/openrepose_library_v0_1.md`.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import shutil
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
from .library import (
    AUTO_TAG_PREFIX,
    LibraryEntryError,
    LibraryEntryLockedError,
    LibraryTagError,
    add_prompt,
    add_tags,
    add_text_record,
    create_entry,
    delete_entry,
    extract_smart_tags,
    format_citation,
    get_entry,
    list_entry_tags,
    list_prompts,
    list_text_records,
    relative_to_root,
    search as library_search_fn,
    set_entry_tags,
    update_entry,
    write_entry_files,
)
from .library.intake import (
    IntakeOutputError,
    LibraryRunError,
    begin_run,
    bulk_promote_task,
    create_project,
    create_task,
    finalize_output,
    get_output,
    get_project,
    get_task,
    list_outputs,
    list_projects,
    list_tasks,
    register_output,
    reject_output,
    reroute_output,
    resolve_card_by_slug,
    soft_accept_output,
    task_summary,
    verify_operator_token,
    wholesale_reject_task,
)
from .log import Logger
from .openpose_schema import (
    ANCHOR_MODES,
    BODY_GROUPS,
    MARKER_SCHEMAS,
    default_frame,
    default_marker_visibility,
)
from .openpose_serialize import serialize_to_string
from .rig import OpenReposeRigFitError, Rig
from .rotation import rotate_yaw
from .settings import (
    OpenReposeSettingsError,
    Settings,
    render_subdir,
)
from .state import AppState, adult_production_boundary
from .yaw_bin import (
    OpenReposeForbiddenTerminologyError,
    OpenReposeYawBinError,
    parse_bin,
    standard_13_angle_bins,
)


class OpenReposeCommandError(ValueError):
    """Raised when a command is malformed or rejected."""


class OpenReposeLibraryError(RuntimeError):
    """Raised by library command handlers when the operation cannot
    complete (DB unreachable, payload invalid, lock contention, etc.).

    Distinct from `OpenReposeCommandError` so callers reading the
    structured error response can branch on `type` ("library_disabled"
    is reflected via the dispatcher's normal error envelope).
    """


class OpenReposeIntakeError(OpenReposeLibraryError):
    """Raised by intake command handlers (WP-I3-004). Carries `rule_id`
    and a pre-formatted `citation` so the dispatcher's error envelope
    surfaces the canonical citation shape from openrepose_rules_v0_1.md.
    """

    def __init__(self, message: str, *, rule_id: str | None = None, citation: str | None = None) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.citation = citation


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
            "adult_production_boundary": adult_production_boundary(),
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
        # Library subsystem pool. Wired by `App.__init__` after construction
        # (WP-I2-001). Library command handlers (added in WP-I2-004) read
        # `self.library_pool` to issue queries; until then it is None.
        self.library_pool: object | None = None

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
            OpenReposeLibraryError,
            LibraryEntryError,
            LibraryEntryLockedError,
            LibraryTagError,
            IntakeOutputError,
            LibraryRunError,
            FileNotFoundError,
            NotImplementedError,
        ) as e:
            self.state.add_error(level="ERR", op=f"cmd.{cmd}", reason=str(e))
            self.state.end_command(status="error")
            self.state.write()
            self.log.err(f"cmd.{cmd}", reason=str(e))
            payload: dict[str, Any] = {"reason": str(e), "type": type(e).__name__}
            # WP-I3-004: surface intake rule citations in the error envelope.
            rule_id = getattr(e, "rule_id", None)
            if rule_id:
                payload["rule_id"] = rule_id
            citation = getattr(e, "citation", None)
            if citation:
                payload["citation"] = citation
            return CommandResult(
                command=cmd,
                status="error",
                payload=payload,
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
    # WP-I1-029 fix: auto-uncheck undetected markers in the Markers tab
    # so the operator's checkbox state matches reality. Existing operator
    # overrides take priority — we only fill in entries that the operator
    # has not explicitly set. detected_markers is populated unconditionally
    # so the GUI can show "no detection" indicators next to undetected rows.
    auto_uncheck, detected = _compute_marker_detection(rig)
    new_mv = _copy_marker_visibility(d.state.marker_visibility)
    for schema, defaults in auto_uncheck.items():
        existing = new_mv.setdefault(schema, {})
        for idx_key, visible in defaults.items():
            existing.setdefault(idx_key, visible)
    with d.state._lock:
        d.state.marker_visibility = new_mv
        d.state.detected_markers = detected

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
    bpv = dict(d.state.body_part_visibility)
    mv = _copy_marker_visibility(d.state.marker_visibility)
    fr = dict(d.state.frame)
    border_color = (
        d.settings.canvas_border_color if d.settings is not None else None
    )
    # WP-I1-030: pretty-printed JSON (indent=2) so the operator can
    # eyeball-verify keypoint zeroing.
    payload = serialize_to_string(
        rotated,
        indent=2,
        body_part_visibility=bpv,
        marker_visibility=mv,
        frame=fr,
    )
    out_json.write_text(payload + "\n", encoding="utf-8")
    # WP-I1-030: PNG output alongside JSON via the existing render pipeline.
    from .render.draw_openpose import render_openpose_to_png
    out_png = out_json.with_suffix(".png")
    render_openpose_to_png(
        rotated,
        out_png,
        body_part_visibility=bpv,
        marker_visibility=mv,
        frame=fr,
        canvas_border_color=border_color,
    )

    d.state.add_export(
        type_="single",
        out_dir=str(out_dir),
        files=[str(out_json), str(out_png)],
    )
    d.state.write()
    d.log.ok(
        "export.single",
        avatar_slug=avatar_slug,
        bin=bin_obj.label,
        json=str(out_json),
        png=str(out_png),
    )
    return {
        "out_dir": str(out_dir),
        "files": [str(out_json), str(out_png)],
        "bin": bin_obj.label,
    }


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
    fr = dict(d.state.frame)
    border_color = (
        d.settings.canvas_border_color if d.settings is not None else None
    )
    from .render.draw_openpose import render_openpose_to_png
    for label in angles:
        bin_obj = parse_bin(label)  # validates each label
        safe_bin = bin_obj.label.replace(" ", "-")
        out_json = out_dir / f"{avatar_slug}_yaw_{safe_bin}.json"
        out_png = out_json.with_suffix(".png")
        rotated = rotate_yaw(d._rig, bin_obj)
        # WP-I1-030: pretty-printed JSON + PNG alongside.
        payload = serialize_to_string(
            rotated,
            indent=2,
            body_part_visibility=bpv,
            marker_visibility=mv,
            frame=fr,
        )
        out_json.write_text(payload + "\n", encoding="utf-8")
        render_openpose_to_png(
            rotated,
            out_png,
            body_part_visibility=bpv,
            marker_visibility=mv,
            frame=fr,
            canvas_border_color=border_color,
        )
        written.append(str(out_json))
        written.append(str(out_png))

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
    border_color = (
        d.settings.canvas_border_color if d.settings is not None else None
    )
    # Library snapshot targets pull from state.library populated by the
    # most recent get/search commands. Library root resolves from settings
    # when available, else falls back to <outputs_root>/library/.
    library_entry = d.state.library.get("last_entry") if target == "library_entry" else None
    library_search_results = (
        d.state.library.get("last_search_results")
        if target == "library_search_results"
        else None
    )
    library_root = (
        Path(d.settings.resolved_library_root())
        if d.settings is not None
        else d.outputs_root / "library"
    )

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
        frame=dict(d.state.frame),
        canvas_border_color=border_color,
        library_entry=library_entry,
        library_search_results=library_search_results,
        library_root=library_root,
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
    return {
        "out_path": str(out_path),
        "adult_production_boundary": adult_production_boundary(),
    }


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


def _h_delete_markers(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Remove operator markers by name from the active calibration.

    Payload: `{"names": ["eye_outer_left", ...]}`. Names not currently in
    the calibration are silently skipped (no-op for those). Unknown
    anatomical names raise a structured error. WP-I1-034.
    """
    avatar_slug = d.state.avatar_slug
    if not avatar_slug:
        raise OpenReposeCommandError(
            "delete_markers requires an active avatar"
        )
    raw_names = cmd.get("names")
    if not isinstance(raw_names, list) or not raw_names:
        raise OpenReposeCommandError(
            "delete_markers requires 'names' as a non-empty list of strings"
        )
    to_delete: set[str] = set()
    for n in raw_names:
        if not isinstance(n, str):
            raise OpenReposeCommandError(
                f"delete_markers names must be strings; got {type(n).__name__}"
            )
        if n not in ALL_MARKER_NAMES:
            raise OpenReposeCommandError(
                f"unknown marker name {n!r}; allowed: {sorted(ALL_MARKER_NAMES)}"
            )
        to_delete.add(n)

    cal_p = calibration_path(d.outputs_root, avatar_slug)
    existing = load_calibration(cal_p)
    if existing is None or not existing.markers:
        return {
            "avatar_slug": avatar_slug,
            "deleted_count": 0,
            "remaining": 0,
            "names": list(to_delete),
        }

    remaining = tuple(m for m in existing.markers if m.name not in to_delete)
    deleted = len(existing.markers) - len(remaining)
    if deleted == 0:
        return {
            "avatar_slug": avatar_slug,
            "deleted_count": 0,
            "remaining": len(remaining),
            "names": list(to_delete),
        }

    new_cal = Calibration(
        avatar_slug=existing.avatar_slug or avatar_slug,
        image_path=existing.image_path,
        image_size=existing.image_size,
        mediapipe_version=existing.mediapipe_version,
        markers=remaining,
        created_at=existing.created_at,
        updated_at="",
    )
    save_calibration(new_cal, cal_p)

    if d._rig is not None:
        d._rig = d._rig.with_calibration(new_cal)

    _refresh_calibration_state(
        d.state,
        active_avatar=avatar_slug,
        calibration=new_cal,
        loaded_from=str(cal_p),
    )
    d.state.write()
    d.log.ok(
        "calibration.delete_markers",
        avatar=avatar_slug,
        deleted=deleted,
        names=",".join(sorted(to_delete)),
    )
    return {
        "avatar_slug": avatar_slug,
        "deleted_count": deleted,
        "remaining": len(remaining),
        "names": list(to_delete),
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


def _compute_marker_detection(rig: Rig) -> tuple[dict, dict]:
    """Inspect the rig and decide which body_18 / face_70 markers MediaPipe
    actually detected. Returns (auto_uncheck, detected) where:

    - auto_uncheck: marker_visibility-shaped dict with explicit False for
      undetected indices (operator overrides take priority over these).
    - detected: full marker_detection map {schema: {idx: bool}} that the
      GUI Markers tab consumes to show "no detection" indicators.

    Body_18 detection: per-keypoint MediaPipe Pose visibility >= 0.3
    (matching the existing rig.py threshold). The synthesized neck
    (BODY_NECK = 1) is detected if both shoulders are detected.

    Face_70 detection: MediaPipe FaceMesh either returns all 478 points or
    none at all, so face_70 is all-detected when rig.face_mesh has rows
    and all-undetected otherwise.
    """
    from .openpose_schema import (
        BODY_L_SHOULDER,
        BODY_NECK,
        BODY_R_SHOULDER,
        MP_POSE_TO_BODY18,
        OPENPOSE_BODY_COUNT,
        OPENPOSE_FACE_COUNT,
    )

    auto_uncheck: dict[str, dict[str, bool]] = {"body_18": {}, "face_70": {}}
    detected: dict[str, dict[str, bool]] = {"body_18": {}, "face_70": {}}

    body_conf = rig.body_conf
    threshold = 0.3
    for op_idx in range(OPENPOSE_BODY_COUNT):
        if op_idx == BODY_NECK:
            l_mp = MP_POSE_TO_BODY18[BODY_L_SHOULDER]
            r_mp = MP_POSE_TO_BODY18[BODY_R_SHOULDER]
            ok = (
                0 <= l_mp < body_conf.shape[0]
                and 0 <= r_mp < body_conf.shape[0]
                and body_conf[l_mp] >= threshold
                and body_conf[r_mp] >= threshold
            )
        else:
            mp_idx = MP_POSE_TO_BODY18[op_idx]
            ok = (
                mp_idx >= 0
                and 0 <= mp_idx < body_conf.shape[0]
                and body_conf[mp_idx] >= threshold
            )
        detected["body_18"][str(op_idx)] = bool(ok)
        if not ok:
            auto_uncheck["body_18"][str(op_idx)] = False

    face_present = rig.face_mesh.shape[0] > 0
    for op_idx in range(OPENPOSE_FACE_COUNT):
        detected["face_70"][str(op_idx)] = bool(face_present)
        if not face_present:
            auto_uncheck["face_70"][str(op_idx)] = False

    return auto_uncheck, detected


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


# --- frame reframing handlers (WP-I1-023) -----------------------------------


def _h_set_frame_scale(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Set frame_scale (positive float)."""
    raw = cmd.get("scale")
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        raise OpenReposeCommandError("set_frame_scale requires numeric 'scale'")
    scale = float(raw)
    if scale <= 0.0:
        raise OpenReposeCommandError(
            f"frame scale must be > 0; got {scale}"
        )
    new_frame = dict(d.state.frame)
    new_frame["scale"] = scale
    with d.state._lock:
        d.state.frame = new_frame
    d.state.write()
    d.log.ok("frame.set_scale", scale=scale)
    return {"frame": dict(new_frame)}


def _h_set_frame_offset(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Set frame_offset (x, y as integers)."""
    x = cmd.get("x")
    y = cmd.get("y")
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        raise OpenReposeCommandError("set_frame_offset requires numeric 'x'")
    if not isinstance(y, (int, float)) or isinstance(y, bool):
        raise OpenReposeCommandError("set_frame_offset requires numeric 'y'")
    new_frame = dict(d.state.frame)
    new_frame["offset_x"] = int(x)
    new_frame["offset_y"] = int(y)
    with d.state._lock:
        d.state.frame = new_frame
    d.state.write()
    d.log.ok("frame.set_offset", x=int(x), y=int(y))
    return {"frame": dict(new_frame)}


def _h_set_frame_anchor(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Set frame anchor mode and (for custom) point.

    Payload: {"mode": "head_anchor"|"canvas_center"|"custom", "point": [x, y]?}.
    """
    mode = cmd.get("mode")
    if mode not in ANCHOR_MODES:
        raise OpenReposeCommandError(
            f"set_frame_anchor 'mode' must be one of {ANCHOR_MODES}; got {mode!r}"
        )
    point = cmd.get("point")
    if mode == "custom":
        if not (isinstance(point, list) and len(point) == 2):
            raise OpenReposeCommandError(
                "anchor mode 'custom' requires 'point' as [x, y]"
            )
        anchor_point = [float(point[0]), float(point[1])]
    else:
        anchor_point = None
    new_frame = dict(d.state.frame)
    new_frame["anchor_mode"] = mode
    new_frame["anchor_point"] = anchor_point
    with d.state._lock:
        d.state.frame = new_frame
    d.state.write()
    d.log.ok("frame.set_anchor", mode=mode, point=str(anchor_point))
    return {"frame": dict(new_frame)}


def _h_reset_frame(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Reset to default frame (scale=1, offset=(0,0), anchor=head_anchor)."""
    with d.state._lock:
        d.state.frame = default_frame()
    d.state.write()
    d.log.ok("frame.reset")
    return {"frame": dict(d.state.frame)}


def _h_get_frame(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    return {"frame": dict(d.state.frame)}


def _h_dump_settings(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    """Return the effective settings JSON (operator-chosen export folder +
    subdir templates + library config), the resolved export folder, and
    whether the default fallback is in use.

    `library_db_url` is redacted (`postgresql://user:***@host/db`) so an
    LLM agent reading the dump cannot exfiltrate the database password.
    The unredacted value stays on disk in `settings.json` and is used
    internally by the dispatcher only."""
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
    settings_dict = d.settings.to_dict()
    if settings_dict.get("library_db_url"):
        settings_dict["library_db_url"] = d.settings.redacted_db_url()
    return {
        "present": True,
        "settings": settings_dict,
        "settings_path": str(d.settings.settings_path),
        "resolved_export_folder": str(resolved),
        "resolved_library_root": str(d.settings.resolved_library_root()),
        "effective_operator_slug": d.settings.effective_operator_slug(),
        "default_used": default_used,
    }


def _mediapipe_version_string() -> str:
    try:
        import mediapipe  # type: ignore[import-untyped]

        return str(getattr(mediapipe, "__version__", "unknown"))
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Library command handlers (WP-I2-004; spec
# `.gov/spec/openrepose_library_v0_1.md` Command Surface).
#
# All 7 handlers share three preconditions enforced via _ensure_pool():
#   1. The library subsystem is enabled (settings.library_db_url set).
#   2. The pool is open and connected.
#   3. The dispatcher has a `library_pool` attached (set by App.__init__).
# A failure raises `OpenReposeLibraryError` which the dispatcher returns
# as `{status: "error", payload: {reason, type}}`.
# ---------------------------------------------------------------------------


def _ensure_pool(d: "CommandDispatcher"):  # noqa: ANN001
    pool = getattr(d, "library_pool", None)
    if pool is None or not getattr(pool, "is_open", False):
        raise OpenReposeLibraryError(
            "library subsystem is disabled (no library_db_url configured "
            "or DB unreachable)"
        )
    return pool


def _operator_slug(d: "CommandDispatcher") -> str | None:  # noqa: ANN001
    if d.settings is None:
        return None
    slug = d.settings.effective_operator_slug()
    return slug or None


def _library_root(d: "CommandDispatcher") -> Path:  # noqa: ANN001
    """Resolved library root for filesystem writes; falls back to
    `<outputs_root>/library/` when no settings are present (covers
    headless tests that build a dispatcher directly)."""
    if d.settings is not None:
        return Path(d.settings.resolved_library_root())
    return d.outputs_root / "library"


def _decode_payload(
    paths_or_b64: dict[str, Any], path_key: str, b64_key: str
) -> bytes | None:
    """Read either an existing file path or base64-encoded bytes.

    Returns None when neither key is present. Raises
    `OpenReposeLibraryError` on malformed b64 / unreadable path."""
    path_value = paths_or_b64.get(path_key)
    b64_value = paths_or_b64.get(b64_key)
    if path_value:
        try:
            return Path(path_value).read_bytes()
        except OSError as e:
            raise OpenReposeLibraryError(
                f"cannot read {path_key}={path_value!r}: {e}"
            ) from e
    if b64_value:
        if not isinstance(b64_value, str):
            raise OpenReposeLibraryError(f"{b64_key} must be a base64 string")
        try:
            return base64.b64decode(b64_value, validate=True)
        except (ValueError, TypeError) as e:
            raise OpenReposeLibraryError(
                f"{b64_key} is not valid base64: {e}"
            ) from e
    return None


def _h_register_library_entry(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    """Insert a new library entry. Either supply pre-existing paths
    (`portrait_path`, `openpose_json_path`, …) OR base64-encoded bytes
    (`portrait`, `openpose_json`, …); paths win when both are supplied.

    Auto-applies smart tags from `metadata` + `comfyui_workflow`. Per
    spec: returns `{entry_id, created_at}`."""
    pool = _ensure_pool(d)
    avatar_slug = cmd.get("avatar_slug")
    if not isinstance(avatar_slug, str) or not avatar_slug:
        raise OpenReposeCommandError(
            "register_library_entry requires non-empty 'avatar_slug'"
        )

    title = cmd.get("title", "") or ""
    yaw_bin = cmd.get("yaw_bin")
    metadata = cmd.get("metadata") or {}
    workflow = cmd.get("comfyui_workflow")
    operator_tags = list(cmd.get("tags") or [])
    prompts_payload = cmd.get("prompts") or None
    story_beats_payload = cmd.get("story_beats") or None
    notes_payload = cmd.get("notes") or None
    completeness = cmd.get("completeness")
    op = _operator_slug(d)

    portrait_b = _decode_payload(cmd, "portrait_path", "portrait")
    openpose_json_b = _decode_payload(cmd, "openpose_json_path", "openpose_json")
    openpose_png_b = _decode_payload(cmd, "openpose_png_path", "openpose_png")
    generated_b = _decode_payload(cmd, "generated_image_path", "generated_image")

    library_root = _library_root(d)

    with pool.connection() as conn:
        try:
            entry = create_entry(
                conn,
                avatar_slug=avatar_slug,
                title=title,
                yaw_bin=yaw_bin,
                metadata=metadata,
                comfyui_workflow=workflow,
                completeness=completeness,
                created_by=op,
            )

            # Filesystem layout — write whatever payloads the caller gave us.
            files = write_entry_files(
                library_root,
                entry.id,
                portrait_bytes=portrait_b,
                openpose_json_bytes=openpose_json_b,
                openpose_png_bytes=openpose_png_b,
                generated_image_bytes=generated_b,
                workflow=workflow,
                metadata=metadata,
            )

            # Patch the relative paths back onto the row so future SELECTs
            # carry them. Only the ones we wrote.
            patch: dict[str, Any] = {}
            if files.portrait_path is not None:
                patch["portrait_path"] = relative_to_root(files.portrait_path, library_root)
            if files.openpose_json_path is not None:
                patch["openpose_json_path"] = relative_to_root(files.openpose_json_path, library_root)
            if files.openpose_png_path is not None:
                patch["openpose_png_path"] = relative_to_root(files.openpose_png_path, library_root)
            if files.generated_image_path is not None:
                patch["generated_image_path"] = relative_to_root(files.generated_image_path, library_root)
            if patch:
                entry = update_entry(conn, entry.id, operator_slug=op, **patch)

            # Operator + smart tags.
            if operator_tags:
                add_tags(conn, entry.id, operator_tags)
            smart = extract_smart_tags(metadata, workflow)
            if smart:
                add_tags(conn, entry.id, smart, is_auto=True)

            # Optional sub-records.
            if prompts_payload:
                if isinstance(prompts_payload, dict):
                    add_prompt(
                        conn,
                        entry.id,
                        positive=prompts_payload.get("positive", "") or "",
                        negative=prompts_payload.get("negative", "") or "",
                        created_by=op,
                    )
            if story_beats_payload:
                items = (
                    story_beats_payload
                    if isinstance(story_beats_payload, list)
                    else [story_beats_payload]
                )
                for body in items:
                    if isinstance(body, str) and body.strip():
                        add_text_record(
                            conn, "story_beats", entry.id, body=body, created_by=op
                        )
            if notes_payload:
                items = (
                    notes_payload
                    if isinstance(notes_payload, list)
                    else [notes_payload]
                )
                for body in items:
                    if isinstance(body, str) and body.strip():
                        add_text_record(
                            conn, "notes", entry.id, body=body, created_by=op
                        )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    d.state.mark_library_register()
    d.state.write()
    d.log.ok(
        "library.register",
        entry_id=str(entry.id),
        avatar=avatar_slug,
        smart_tag_count=len(smart),
    )
    return {
        "entry_id": str(entry.id),
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "smart_tags": smart,
    }


def _h_update_library_entry(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    """Patch a library entry. Lock contention surfaces as a structured
    error including `retry_after` so the LLM agent can back off."""
    pool = _ensure_pool(d)
    entry_id = cmd.get("entry_id")
    if not isinstance(entry_id, str) or not entry_id:
        raise OpenReposeCommandError("update_library_entry requires 'entry_id'")
    patch_keys = {
        "avatar_slug",
        "title",
        "yaw_bin",
        "portrait_path",
        "openpose_json_path",
        "openpose_png_path",
        "generated_image_path",
        "comfyui_workflow",
        "metadata",
        "completeness",
    }
    patch = {k: v for k, v in cmd.items() if k in patch_keys}
    if not patch:
        raise OpenReposeCommandError(
            "update_library_entry needs at least one editable field"
        )
    op = _operator_slug(d)
    try:
        with pool.connection() as conn:
            try:
                entry = update_entry(conn, entry_id, operator_slug=op, **patch)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    except LibraryEntryLockedError as e:
        d.state.add_library_lock(entry_id, e.locked_by)
        d.state.write()
        # Re-raise a richer error for the dispatcher envelope.
        raise OpenReposeLibraryError(
            f"library entry {entry_id} locked by {e.locked_by or 'another operator'}; "
            f"retry_after=5"
        ) from e
    d.log.ok("library.update", entry_id=entry_id, fields=",".join(sorted(patch)))
    return entry.to_dict()


def _h_delete_library_entry(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    """Delete an entry + its `outputs/library/<entry-uuid>/` folder.
    Cascades to entry_tags / prompts / story_beats / notes via FKs."""
    pool = _ensure_pool(d)
    entry_id = cmd.get("entry_id")
    if not isinstance(entry_id, str) or not entry_id:
        raise OpenReposeCommandError("delete_library_entry requires 'entry_id'")
    library_root = _library_root(d)
    try:
        with pool.connection() as conn:
            try:
                deleted = delete_entry(conn, entry_id)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    except LibraryEntryLockedError as e:
        d.state.add_library_lock(entry_id, e.locked_by)
        d.state.write()
        raise OpenReposeLibraryError(
            f"library entry {entry_id} locked by {e.locked_by or 'another operator'}; "
            f"retry_after=5"
        ) from e
    if deleted:
        # Remove the on-disk folder. Best-effort: missing is fine.
        entry_dir = Path(library_root) / entry_id
        if entry_dir.exists():
            shutil.rmtree(entry_dir, ignore_errors=True)
    d.log.ok("library.delete", entry_id=entry_id, deleted=str(deleted).lower())
    return {"entry_id": entry_id, "deleted": bool(deleted)}


def _h_library_search(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    pool = _ensure_pool(d)
    query = cmd.get("query")
    if not isinstance(query, str) or not query.strip():
        raise OpenReposeCommandError("library_search requires non-empty 'query'")
    raw_limit = cmd.get("limit", 50)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as e:
        raise OpenReposeCommandError(f"limit must be int; got {raw_limit!r}") from e
    with pool.connection() as conn:
        results = library_search_fn(conn, query, limit=limit)
    result_dicts = [r.to_dict() for r in results]
    payload = {
        "query": query,
        "count": len(results),
        "results": result_dicts,
    }
    d.state.mark_library_search(
        query=query,
        count=len(results),
        results=result_dicts[:24],  # only keep what the snapshot grid shows
    )
    d.state.write()
    d.log.ok("library.search", query=query, count=len(results))
    return payload


def _h_get_library_entry(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    pool = _ensure_pool(d)
    entry_id = cmd.get("entry_id")
    if not isinstance(entry_id, str) or not entry_id:
        raise OpenReposeCommandError("get_library_entry requires 'entry_id'")
    include = set(cmd.get("include") or ["prompts", "story_beats", "notes", "tags"])
    with pool.connection() as conn:
        entry = get_entry(conn, entry_id)
        if entry is None:
            raise OpenReposeLibraryError(f"library entry {entry_id} not found")
        payload = entry.to_dict()
        if "tags" in include:
            payload["tags"] = list_entry_tags(conn, entry_id)
        if "prompts" in include:
            payload["prompts"] = [p.to_dict() for p in list_prompts(conn, entry_id)]
        if "story_beats" in include:
            payload["story_beats"] = [
                r.to_dict() for r in list_text_records(conn, "story_beats", entry_id)
            ]
        if "notes" in include:
            payload["notes"] = [
                r.to_dict() for r in list_text_records(conn, "notes", entry_id)
            ]
        if "workflow" not in include:
            payload.pop("comfyui_workflow", None)
        if "metadata" not in include:
            payload.pop("metadata", None)
    # Record so the `library_entry` snapshot target has an entry to render.
    d.state.mark_library_entry_view(payload)
    d.state.write()
    d.log.ok("library.get", entry_id=entry_id)
    return payload


def _h_set_library_tags(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    pool = _ensure_pool(d)
    entry_id = cmd.get("entry_id")
    if not isinstance(entry_id, str) or not entry_id:
        raise OpenReposeCommandError("set_library_tags requires 'entry_id'")
    tags = cmd.get("tags")
    if not isinstance(tags, list):
        raise OpenReposeCommandError("set_library_tags 'tags' must be a list")
    replace = bool(cmd.get("replace", False))
    with pool.connection() as conn:
        try:
            attached = set_entry_tags(conn, entry_id, tags, replace=replace)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    d.log.ok(
        "library.set_tags",
        entry_id=entry_id,
        replace=str(replace).lower(),
        count=len(attached),
    )
    return {"entry_id": entry_id, "tags": attached}


def _h_dump_library_schema(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    """Return current schema_version + an inventory hash an operator /
    LLM agent can compare against the migration files in source control
    to confirm no drift."""
    pool = _ensure_pool(d)
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_version"
            )
            row = cur.fetchone()
            version = int(row[0]) if row else 0
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "ORDER BY table_name"
            )
            tables = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT routine_name FROM information_schema.routines "
                "WHERE routine_schema = 'public' AND routine_type = 'FUNCTION' "
                "ORDER BY routine_name"
            )
            functions = [r[0] for r in cur.fetchall()]
    digest_input = json.dumps(
        {"version": version, "tables": tables, "functions": functions},
        sort_keys=True,
    )
    ddl_hash = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": version,
        "tables": tables,
        "functions": functions,
        "ddl_hash": ddl_hash,
    }


# ---------------------------------------------------------------------------
# Intake & triage commands (WP-I3-004)
# ---------------------------------------------------------------------------


def _intake_outputs_root(d: "CommandDispatcher") -> Path:  # noqa: ANN001
    """Outputs root for intake filesystem operations. Same as the
    dispatcher's `outputs_root` (where `outputs/.runtime/`, `outputs/intake/`,
    `outputs/library/` all live)."""
    return Path(d.outputs_root)


def _require_operator_token(
    d: "CommandDispatcher", cmd: dict[str, Any], command: str
) -> None:  # noqa: ANN001
    """Raise INTAKE-001 OpenReposeIntakeError if the payload does not
    carry a valid operator_token. The DB CHECK constraint is the kill
    switch; this gate is defense-in-depth + early citation."""
    if not verify_operator_token(cmd, d.settings):
        citation = format_citation(
            command=command,
            rule_id="INTAKE-001",
            action_result="blocked",
            fix_action="emit intake_soft_accept; operator runs the finalize/promote command from the GUI session",
        )
        raise OpenReposeIntakeError(citation, rule_id="INTAKE-001", citation=citation)


def _refresh_intake_state(
    d: "CommandDispatcher", task_uuid: str | None = None
) -> None:  # noqa: ANN001
    """Read task_summary for the active task (or clear) and write
    `state.library.intake` accordingly."""
    if not task_uuid:
        d.state.set_intake_state(active_task_id=None, active_task_slug=None)
        return
    pool = _ensure_pool(d)
    with pool.connection() as conn:
        summary = task_summary(conn, task_id=task_uuid)
    queue_depth = summary["pending_count"] + summary["triaging_count"]
    d.state.set_intake_state(
        active_task_id=summary["task_id"],
        active_task_slug=summary["task_slug"],
        received_count=summary["received_count"] or 0,
        pending_count=summary["pending_count"],
        triaging_count=summary["triaging_count"],
        soft_accepted_count=summary["soft_accepted_count"],
        promoted_count=summary["promoted_count"],
        rejected_count=summary["rejected_count"],
        diagnostic_count=summary["diagnostic_count"],
        abandoned_count=summary["abandoned_count"],
        queue_depth=queue_depth,
    )


def _h_project_create(d: "CommandDispatcher", cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    slug = cmd.get("slug")
    name = cmd.get("name")
    owner_slug = cmd.get("owner_slug") or _operator_slug(d) or ""
    if not isinstance(slug, str) or not slug:
        raise OpenReposeCommandError("project_create requires non-empty 'slug'")
    if not isinstance(name, str) or not name:
        raise OpenReposeCommandError("project_create requires non-empty 'name'")
    with pool.connection() as conn:
        project = create_project(conn, slug=slug, name=name, owner_slug=owner_slug)
    d.state.set_guidance(
        current_focus=f"project {project.slug} created",
        next_valid_actions=["task_create", "project_list", "project_set_target_tree"],
        active_rules=["INTAKE-001", "INTAKE-002"],
    )
    return {"project": project.to_dict()}


def _h_project_list(d: "CommandDispatcher", cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    status = cmd.get("status")
    with pool.connection() as conn:
        projects = list_projects(conn, status=status)
    return {"projects": [p.to_dict() for p in projects], "count": len(projects)}


def _h_task_create(d: "CommandDispatcher", cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    project_id = cmd.get("project_id")
    slug = cmd.get("slug")
    expected_count = cmd.get("expected_count")
    source = cmd.get("source")
    llm_model = cmd.get("llm_model")
    if not isinstance(project_id, str) or not project_id:
        raise OpenReposeCommandError("task_create requires 'project_id'")
    if not isinstance(slug, str) or not slug:
        raise OpenReposeCommandError("task_create requires non-empty 'slug'")
    with pool.connection() as conn:
        task = create_task(
            conn,
            project_id=project_id,
            slug=slug,
            expected_count=expected_count,
            source=source,
            llm_model=llm_model,
            outputs_root=_intake_outputs_root(d),
        )
    _refresh_intake_state(d, str(task.id))
    d.state.set_guidance(
        current_focus=f"task {task.slug} created (intake_dir={task.intake_dir})",
        next_valid_actions=["intake_register_output", "task_summary", "intake_list"],
        active_rules=["INTAKE-001", "INTAKE-002"],
    )
    return {"task": task.to_dict()}


def _h_task_list(d: "CommandDispatcher", cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    project_id = cmd.get("project_id")
    status = cmd.get("status")
    with pool.connection() as conn:
        tasks = list_tasks(conn, project_id=project_id, status=status)
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}


def _h_task_summary(d: "CommandDispatcher", cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    task_id = cmd.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise OpenReposeCommandError("task_summary requires 'task_id'")
    with pool.connection() as conn:
        summary = task_summary(conn, task_id=task_id)
    _refresh_intake_state(d, task_id)
    return {"summary": summary}


def _h_task_inspect(d: "CommandDispatcher", cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    task_id = cmd.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise OpenReposeCommandError("task_inspect requires 'task_id'")
    with pool.connection() as conn:
        task = get_task(conn, task_id=task_id)
        if task is None:
            raise OpenReposeCommandError(f"task {task_id} not found")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, slug, tier FROM library_batches WHERE task_id = %s",
                (task_id,),
            )
            batches = [
                {"id": str(r[0]), "slug": r[1], "tier": r[2]} for r in cur.fetchall()
            ]
            cur.execute(
                "SELECT COUNT(*) FROM library_runs WHERE task_id = %s", (task_id,)
            )
            run_count = int(cur.fetchone()[0])
    return {"task": task.to_dict(), "batches": batches, "run_count": run_count}


def _h_intake_register_output(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    """Register one library_outputs row.

    Two payload modes:
      (a) file already on disk: caller supplies `file_path` (relative
          under outputs_root) + `content_hash`.
      (b) inline image bytes: caller supplies `image_b64` + `filename`;
          the dispatcher writes the bytes into
          `outputs/intake/<task_intake_dir>/raw/<filename>`, computes
          sha256, and proceeds. Content-Hash from the caller is honored
          if supplied; otherwise computed from the bytes. This is the
          path the WP-I3-005 default-staging bridge uses.
    """
    pool = _ensure_pool(d)
    run_id = cmd.get("run_id")
    task_id = cmd.get("task_id")
    file_path = cmd.get("file_path")
    content_hash = cmd.get("content_hash")
    width = cmd.get("width")
    height = cmd.get("height")
    image_b64 = cmd.get("image_b64")
    filename = cmd.get("filename")

    if not isinstance(run_id, str) or not run_id:
        raise OpenReposeCommandError("intake_register_output requires 'run_id'")
    if not isinstance(task_id, str) or not task_id:
        raise OpenReposeCommandError("intake_register_output requires 'task_id'")
    if not isinstance(width, int) or not isinstance(height, int):
        raise OpenReposeCommandError("width and height must be integers")

    with pool.connection() as conn:
        task = get_task(conn, task_id=task_id)
        if task is None:
            raise OpenReposeCommandError(f"task {task_id} not found")
        if task.status in ("rejected_wholesale", "aborted"):
            raise OpenReposeCommandError(
                f"task {task_id} is terminal (status={task.status}); cannot register"
            )

        # Path (b): bridge ships bytes; we write to disk first.
        if image_b64 and not file_path:
            if not isinstance(filename, str) or not filename:
                raise OpenReposeCommandError(
                    "intake_register_output with 'image_b64' also requires 'filename'"
                )
            try:
                image_bytes = base64.b64decode(image_b64)
            except (ValueError, TypeError) as e:
                raise OpenReposeCommandError(
                    f"invalid base64 in 'image_b64': {e}"
                ) from e
            intake_root = Path(_intake_outputs_root(d)) / "intake" / task.intake_dir
            raw_dir = intake_root / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            # Sanitize filename: drop any path separators.
            safe_name = Path(filename).name
            target = raw_dir / safe_name
            target.write_bytes(image_bytes)
            file_path = str(
                Path("intake") / task.intake_dir.rstrip("/") / "raw" / safe_name
            ).replace("\\", "/")
            if not content_hash:
                content_hash = hashlib.sha256(image_bytes).hexdigest()

        if not isinstance(file_path, str) or not file_path:
            raise OpenReposeCommandError(
                "intake_register_output requires 'file_path' or 'image_b64'+'filename'"
            )
        if not isinstance(content_hash, str) or not content_hash:
            raise OpenReposeCommandError(
                "intake_register_output requires 'content_hash' (or 'image_b64' to compute it)"
            )
        output, auto = register_output(
            conn,
            run_id=run_id,
            task_id=task_id,
            project_id=str(task.project_id),
            file_path=file_path,
            content_hash=content_hash,
            width=int(width),
            height=int(height),
            outputs_root=_intake_outputs_root(d),
        )
    _refresh_intake_state(d, task_id)
    return {"output": output.to_dict(), "auto_route": auto.to_dict()}


def _h_intake_list(d: "CommandDispatcher", cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    task_id = cmd.get("task_id")
    status = cmd.get("status")
    limit = int(cmd.get("limit", 100))
    offset = int(cmd.get("offset", 0))
    with pool.connection() as conn:
        rows = list_outputs(
            conn, task_id=task_id, status=status, limit=limit, offset=offset
        )
    return {
        "outputs": [r.to_dict() for r in rows],
        "count": len(rows),
        "limit": limit,
        "offset": offset,
    }


def _h_intake_inspect(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    pool = _ensure_pool(d)
    output_id = cmd.get("output_id")
    if not isinstance(output_id, str) or not output_id:
        raise OpenReposeCommandError("intake_inspect requires 'output_id'")
    with pool.connection() as conn:
        output = get_output(conn, output_id=output_id)
        if output is None:
            raise OpenReposeCommandError(f"output {output_id} not found")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg.png_path, pg.json_path, pg.guide_type "
                "FROM library_runs r "
                "LEFT JOIN library_pose_guides pg ON pg.id = r.pose_guide_id "
                "WHERE r.id = %s",
                (str(output.run_id),),
            )
            pose_row = cur.fetchone()
            cur.execute(
                "SELECT rule_id, bucket, reason FROM library_diagnostics "
                "WHERE output_id = %s ORDER BY created_at ASC",
                (output_id,),
            )
            diagnostics = [
                {"rule_id": r[0], "bucket": r[1], "reason": r[2]}
                for r in cur.fetchall()
            ]
    pose_guide = None
    if pose_row and pose_row[0] is not None:
        pose_guide = {
            "png_path": pose_row[0],
            "json_path": pose_row[1],
            "guide_type": pose_row[2],
        }
    return {
        "output": output.to_dict(),
        "pose_guide": pose_guide,
        "diagnostics": diagnostics,
    }


def _h_intake_soft_accept(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    pool = _ensure_pool(d)
    output_id = cmd.get("output_id")
    notes = cmd.get("notes")
    if not isinstance(output_id, str) or not output_id:
        raise OpenReposeCommandError("intake_soft_accept requires 'output_id'")
    with pool.connection() as conn:
        output = soft_accept_output(conn, output_id=output_id, notes=notes)
    _refresh_intake_state(d, str(output.task_id))
    return {"output": output.to_dict()}


def _h_intake_reject(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    pool = _ensure_pool(d)
    output_id = cmd.get("output_id")
    primary_rejection_reason = cmd.get("primary_rejection_reason")
    notes = cmd.get("notes")
    if not isinstance(output_id, str) or not output_id:
        raise OpenReposeCommandError("intake_reject requires 'output_id'")
    if not isinstance(primary_rejection_reason, str) or not primary_rejection_reason:
        raise OpenReposeCommandError("intake_reject requires 'primary_rejection_reason'")
    with pool.connection() as conn:
        output = reject_output(
            conn,
            output_id=output_id,
            primary_rejection_reason=primary_rejection_reason,
            notes=notes,
            operator_slug=_operator_slug(d),
            outputs_root=_intake_outputs_root(d),
        )
    _refresh_intake_state(d, str(output.task_id))
    return {"output": output.to_dict()}


def _h_intake_finalize(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    _require_operator_token(d, cmd, "intake_finalize")
    pool = _ensure_pool(d)
    output_id = cmd.get("output_id")
    if not isinstance(output_id, str) or not output_id:
        raise OpenReposeCommandError("intake_finalize requires 'output_id'")
    op = _operator_slug(d) or ""
    if not op:
        raise OpenReposeCommandError(
            "intake_finalize requires an operator_slug in settings"
        )
    with pool.connection() as conn:
        output = finalize_output(conn, output_id=output_id, operator_slug=op)
    _refresh_intake_state(d, str(output.task_id))
    return {"output": output.to_dict()}


def _h_intake_reroute(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    pool = _ensure_pool(d)
    output_id = cmd.get("output_id")
    target_status = cmd.get("target_status")
    if not isinstance(output_id, str) or not output_id:
        raise OpenReposeCommandError("intake_reroute requires 'output_id'")
    if not isinstance(target_status, str) or not target_status:
        raise OpenReposeCommandError("intake_reroute requires 'target_status'")
    with pool.connection() as conn:
        output = reroute_output(conn, output_id=output_id, target_status=target_status)
    _refresh_intake_state(d, str(output.task_id))
    return {"output": output.to_dict()}


def _h_promote_to_library(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    _require_operator_token(d, cmd, "promote_to_library")
    pool = _ensure_pool(d)
    task_id = cmd.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise OpenReposeCommandError("promote_to_library requires 'task_id'")
    op = _operator_slug(d) or ""
    if not op:
        raise OpenReposeCommandError(
            "promote_to_library requires operator_slug in settings"
        )
    with pool.connection() as conn:
        promoted_ids = bulk_promote_task(conn, task_id=task_id, operator_slug=op)
    _refresh_intake_state(d, task_id)
    return {"promoted_ids": promoted_ids, "count": len(promoted_ids)}


def _h_intake_begin_run(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    """Create one library_runs row and return its run_id. The bridge calls
    this once per ComfyUI save before per-image intake_register_output
    calls (WP-I3-005)."""
    pool = _ensure_pool(d)
    task_id = cmd.get("task_id")
    card_id = cmd.get("card_id")
    card_slug = cmd.get("card_slug")
    if not isinstance(task_id, str) or not task_id:
        raise OpenReposeCommandError("intake_begin_run requires 'task_id'")
    if not card_id and not card_slug:
        raise OpenReposeCommandError(
            "intake_begin_run requires 'card_id' or 'card_slug'"
        )
    pose_guide_id = cmd.get("pose_guide_id")
    sampler = cmd.get("sampler")
    cfg = cmd.get("cfg")
    steps = cmd.get("steps")
    seed = cmd.get("seed")
    workflow_json = cmd.get("workflow_json")
    with pool.connection() as conn:
        if not card_id:
            resolved, match_count = resolve_card_by_slug(
                conn, task_id=task_id, card_slug=str(card_slug)
            )
            if resolved is None:
                raise OpenReposeCommandError(
                    f"intake_begin_run: card_slug {card_slug!r} did not "
                    f"resolve under task {task_id}"
                )
            if match_count > 1:
                d.log.warn(
                    "intake_begin_run.card_slug_ambiguous",
                    task_id=task_id,
                    card_slug=card_slug,
                    match_count=match_count,
                )
            card_id = str(resolved)
        run = begin_run(
            conn,
            card_id=card_id,
            task_id=task_id,
            pose_guide_id=pose_guide_id,
            sampler=sampler,
            cfg=cfg,
            steps=steps,
            seed=seed,
            workflow_json=workflow_json,
        )
    return {"run": run.to_dict()}


def _h_task_reject_wholesale(
    d: "CommandDispatcher", cmd: dict[str, Any]
) -> dict[str, Any]:
    _require_operator_token(d, cmd, "task_reject_wholesale")
    pool = _ensure_pool(d)
    task_id = cmd.get("task_id")
    reason = cmd.get("reason")
    if not isinstance(task_id, str) or not task_id:
        raise OpenReposeCommandError("task_reject_wholesale requires 'task_id'")
    if not isinstance(reason, str) or not reason:
        raise OpenReposeCommandError("task_reject_wholesale requires 'reason'")
    op = _operator_slug(d) or ""
    if not op:
        raise OpenReposeCommandError("task_reject_wholesale requires operator_slug")
    with pool.connection() as conn:
        result = wholesale_reject_task(
            conn,
            task_id=task_id,
            operator_slug=op,
            reason=reason,
            outputs_root=_intake_outputs_root(d),
        )
    _refresh_intake_state(d, task_id)
    return result


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
    "delete_markers": _h_delete_markers,
    "get_calibration_status": _h_get_calibration_status,
    "set_body_part_visibility": _h_set_body_part_visibility,
    "get_body_part_visibility": _h_get_body_part_visibility,
    "set_marker_visibility": _h_set_marker_visibility,
    "get_marker_visibility": _h_get_marker_visibility,
    "reset_marker_visibility": _h_reset_marker_visibility,
    "set_frame_scale": _h_set_frame_scale,
    "set_frame_offset": _h_set_frame_offset,
    "set_frame_anchor": _h_set_frame_anchor,
    "reset_frame": _h_reset_frame,
    "get_frame": _h_get_frame,
    "dump_settings": _h_dump_settings,
    # Library commands (WP-I2-004).
    "register_library_entry": _h_register_library_entry,
    "update_library_entry": _h_update_library_entry,
    "delete_library_entry": _h_delete_library_entry,
    "library_search": _h_library_search,
    "get_library_entry": _h_get_library_entry,
    "set_library_tags": _h_set_library_tags,
    "dump_library_schema": _h_dump_library_schema,
    # Intake & triage commands (WP-I3-004).
    "project_create": _h_project_create,
    "project_list": _h_project_list,
    "task_create": _h_task_create,
    "task_list": _h_task_list,
    "task_summary": _h_task_summary,
    "task_inspect": _h_task_inspect,
    "intake_register_output": _h_intake_register_output,
    "intake_list": _h_intake_list,
    "intake_inspect": _h_intake_inspect,
    "intake_soft_accept": _h_intake_soft_accept,
    "intake_reject": _h_intake_reject,
    "intake_finalize": _h_intake_finalize,
    "intake_reroute": _h_intake_reroute,
    "promote_to_library": _h_promote_to_library,
    "task_reject_wholesale": _h_task_reject_wholesale,
    "intake_begin_run": _h_intake_begin_run,
}
