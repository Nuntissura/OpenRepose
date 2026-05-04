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
import uuid
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
)
from .calibration import (
    load as load_calibration,
)
from .calibration import (
    save as save_calibration,
)
from .library import (
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
    set_entry_tags,
    update_entry,
    write_entry_files,
)
from .library import (
    search as library_search_fn,
)
from .library.amood import (
    AcceptedSetAuditError,
    AmoodBatchError,
    AmoodCardError,
    AmoodTsvError,
    AmoodVariantError,
    accepted_set_audit,
    check_compatibility,
    create_variants,
    export_tsv,
    get_batch,
    import_tsv,
    init_batch_package,
)
from .library.amood import (
    create_card as amood_create_card,
)
from .library.requirements import (
    CanonicalMarkdownError,
    OpenReposeRequirementsError,
    create_rule,
    dump_rules,
    get_rule_with_inheritance,
    parse_markdown,
    render_markdown,
    update_rule,
)
from .library.requirements.markdown_io import (
    ParsedProject,
    ParsedRequirement,
    ParsedTargetGroup,
    project_to_dict as parsed_project_to_dict,
)
from .library.targets import (
    card_summary as target_card_summary,
    group_summary as target_group_summary,
    list_groups as target_list_groups,
    project_summary as target_project_summary,
    set_target_tree as target_set_tree,
    state_targets_block,
    target_recount as target_recount_fn,
)
from .library.intake import (
    BULK_BATCH_MAX_DEFAULT,
    IntakeOutputError,
    LibraryRunError,
    begin_run,
    bulk_promote_task,
    create_project,
    create_task,
    finalize_output,
    get_output,
    get_task,
    list_outputs,
    list_projects,
    list_tasks,
    process_pending_file_ops,
    recover_audit,
    recover_retry,
    register_output,
    register_outputs_bulk,
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


class OpenReposeAmoodError(OpenReposeLibraryError):
    """Raised by AMood command handlers (WP-I3-006). Carries `rule_id`
    and a pre-formatted `citation` for the canonical error shape from
    openrepose_rules_v0_1.md."""

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




@dataclass
class FileSlot:
    """One open portrait in the multi-file workspace (WP-I1-037)."""

    file_id: str
    path: str
    avatar_slug: str | None
    rig: Rig
    yaw: dict[str, Any]
    rig_state: dict[str, Any]
    calibration: dict[str, Any]
    body_part_visibility: dict[str, bool]
    marker_visibility: dict[str, dict[str, bool]]
    detected_markers: dict[str, dict[str, bool]]
    frame: dict[str, Any]
    opened_at: str

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
        settings: Settings | None = None,
    ) -> None:
        self.state = state
        self.log = log
        self.outputs_root = Path(outputs_root)
        self.settings = settings  # operator-configured paths; None = legacy default
        self._lock = threading.Lock()
        self._rig: Rig | None = None
        self._files: dict[str, FileSlot] = {}
        self._file_order: list[str] = []
        self._active_file_id: str | None = None
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
                requested_file_id = command_dict.get("file_id")
                if (
                    isinstance(requested_file_id, str)
                    and requested_file_id
                    and cmd not in _FILE_MANAGEMENT_COMMANDS
                ):
                    _activate_file(self, requested_file_id)
                payload = handler(self, command_dict)
                _capture_active_slot(self)
                _sync_state_files(self)
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
            AmoodBatchError,
            AmoodCardError,
            AmoodVariantError,
            AmoodTsvError,
            AcceptedSetAuditError,
            CanonicalMarkdownError,
            OpenReposeRequirementsError,
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



_FILE_MANAGEMENT_COMMANDS = {"open_file", "close_file", "set_active_file", "list_files"}
_PER_ANGLE_METADATA_MAX_BYTES = 1_000_000
_KNOWN_PER_ANGLE_METADATA_KEYS = {
    "prompt_slug",
    "seed",
    "controlnet_strength",
    "sampler",
    "scheduler",
    "workflow_slug",
    "workflow",
    "notes",
}


def _new_file_id() -> str:
    return uuid.uuid4().hex


def _rig_state_from_rig(rig: Rig, *, status: str = "ok") -> dict[str, Any]:
    import numpy as np
    face_70 = rig.openpose_face_70()
    body_18, _conf_18 = rig.openpose_body_18()
    return {
        "status": status,
        "fit_at": _now_iso() if status == "ok" else None,
        "fit_duration_ms": int(rig.fit_metrics.fit_duration_ms),
        "face_landmark_count": int(rig.fit_metrics.face_landmark_count),
        "body_landmark_count": int(rig.fit_metrics.body_landmark_count),
        "face_visible_in_openpose": int(np.count_nonzero(np.any(face_70[:, :2] != 0, axis=1))),
        "body_visible_in_openpose": int(np.count_nonzero(np.any(body_18[:, :2] != 0, axis=1))),
        "hand_left_detected": bool(rig.fit_metrics.hand_left_detected),
        "hand_right_detected": bool(rig.fit_metrics.hand_right_detected),
        "hand_landmark_count": int(rig.fit_metrics.hand_landmark_count),
        "hands_unavailable": bool(rig.fit_metrics.hands_unavailable),
    }


def _set_state_rig_from_rig(d: CommandDispatcher, rig: Rig) -> None:
    rs = _rig_state_from_rig(rig)
    d.state.set_rig(
        status="ok",
        fit_duration_ms=rs["fit_duration_ms"],
        face_landmark_count=rs["face_landmark_count"],
        body_landmark_count=rs["body_landmark_count"],
        face_visible_in_openpose=rs["face_visible_in_openpose"],
        body_visible_in_openpose=rs["body_visible_in_openpose"],
        hand_left_detected=rs["hand_left_detected"],
        hand_right_detected=rs["hand_right_detected"],
        hand_landmark_count=rs["hand_landmark_count"],
        hands_unavailable=rs["hands_unavailable"],
    )


def _slot_summary(d: CommandDispatcher, slot: FileSlot) -> dict[str, Any]:
    return {
        "file_id": slot.file_id,
        "path": slot.path,
        "avatar_slug": slot.avatar_slug,
        "active": slot.file_id == d._active_file_id,
        "yaw": dict(slot.yaw),
        "rig": dict(slot.rig_state),
        "frame": dict(slot.frame),
        "body_part_visibility": dict(slot.body_part_visibility),
    }


def _sync_state_files(d: CommandDispatcher) -> None:
    d.state.set_files_state(
        files=[_slot_summary(d, d._files[fid]) for fid in d._file_order if fid in d._files],
        active_file_id=d._active_file_id,
    )


def _capture_active_slot(d: CommandDispatcher) -> None:
    fid = d._active_file_id
    if not fid or fid not in d._files or d._rig is None:
        _sync_state_files(d)
        return
    slot = d._files[fid]
    slot.rig = d._rig
    slot.yaw = dict(d.state.yaw)
    slot.rig_state = dict(d.state.rig)
    slot.calibration = dict(d.state.calibration)
    slot.body_part_visibility = dict(d.state.body_part_visibility)
    slot.marker_visibility = _copy_marker_visibility(d.state.marker_visibility)
    slot.detected_markers = {k: dict(v) for k, v in d.state.detected_markers.items()}
    slot.frame = dict(d.state.frame)
    _sync_state_files(d)


def _clear_active_state(d: CommandDispatcher) -> None:
    d._rig = None
    d._active_file_id = None
    d.state.set_portrait(None)
    d.state.set_rig(status="none")
    d.state.set_yaw(value_deg=0.0, bin_label="0")
    with d.state._lock:
        d.state.calibration = {
            "active_avatar": None,
            "completeness": "none",
            "marker_count": 0,
            "missing_required": [],
            "field_cached": False,
            "loaded_from": None,
            "last_dump_at": d.state.calibration.get("last_dump_at"),
        }
        d.state.marker_visibility = default_marker_visibility()
        d.state.detected_markers = {"body_18": {}, "face_70": {}}
        d.state.frame = default_frame()


def _apply_slot_to_state(d: CommandDispatcher, slot: FileSlot) -> None:
    d._active_file_id = slot.file_id
    d._rig = slot.rig
    d.state.set_portrait(slot.path, avatar_slug=slot.avatar_slug)
    with d.state._lock:
        d.state.rig = dict(slot.rig_state)
        d.state.yaw = dict(slot.yaw)
        d.state.calibration = dict(slot.calibration)
        d.state.body_part_visibility = dict(slot.body_part_visibility)
        d.state.marker_visibility = _copy_marker_visibility(slot.marker_visibility)
        d.state.detected_markers = {k: dict(v) for k, v in slot.detected_markers.items()}
        d.state.frame = dict(slot.frame)
    _sync_state_files(d)


def _activate_file(d: CommandDispatcher, file_id: str) -> FileSlot:
    slot = d._files.get(file_id)
    if slot is None:
        raise OpenReposeCommandError(f"unknown file_id: {file_id}")
    _capture_active_slot(d)
    _apply_slot_to_state(d, slot)
    return slot


def _close_file_id(d: CommandDispatcher, file_id: str) -> dict[str, Any]:
    if file_id not in d._files:
        raise OpenReposeCommandError(f"unknown file_id: {file_id}")
    was_active = file_id == d._active_file_id
    del d._files[file_id]
    d._file_order = [fid for fid in d._file_order if fid != file_id]
    if was_active:
        if d._file_order:
            _apply_slot_to_state(d, d._files[d._file_order[-1]])
        else:
            _clear_active_state(d)
    _sync_state_files(d)
    return {"closed_file_id": file_id, "active_file_id": d._active_file_id, "files": list(d.state.files)}


def _normalise_per_angle_metadata(
    raw: Any,
    *,
    angles: list[str],
    log: Logger,
) -> dict[str, dict[str, Any]]:
    """Validate and normalize export_batch per-angle metadata.

    Accepted inputs:
      - None -> {}
      - list aligned with canonical angle labels; entries are dict or None.
      - dict keyed by canonical/parseable yaw bin; values are dict or None.

    The output is always a yaw-bin keyed dict so downstream scripts can look
    up metadata without relying on list order.
    """
    if raw is None:
        return {}
    angle_set = set(angles)
    unknown_keys: set[str] = set()

    def _validate_item(angle: str, item: Any) -> dict[str, Any] | None:
        if item is None:
            return None
        if not isinstance(item, dict):
            raise OpenReposeCommandError(
                f"per_angle_metadata for {angle!r} must be an object or null"
            )
        for key in item:
            if not isinstance(key, str) or not key:
                raise OpenReposeCommandError(
                    f"per_angle_metadata for {angle!r} has a non-string or empty key"
                )
        encoded = json.dumps(item, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > _PER_ANGLE_METADATA_MAX_BYTES:
            raise OpenReposeCommandError(
                f"per_angle_metadata for {angle!r} exceeds {_PER_ANGLE_METADATA_MAX_BYTES} bytes"
            )
        unknown_keys.update(set(item) - _KNOWN_PER_ANGLE_METADATA_KEYS)
        return dict(item)

    normalised: dict[str, dict[str, Any]] = {}
    if isinstance(raw, list):
        if len(raw) != len(angles):
            raise OpenReposeCommandError(
                "per_angle_metadata list length must match angles length"
            )
        for angle, item in zip(angles, raw, strict=True):
            meta = _validate_item(angle, item)
            if meta is not None:
                normalised[angle] = meta
    elif isinstance(raw, dict):
        for key, item in raw.items():
            if not isinstance(key, str) or not key:
                raise OpenReposeCommandError(
                    "per_angle_metadata object keys must be non-empty yaw bin strings"
                )
            canonical = parse_bin(key).label
            if canonical not in angle_set:
                raise OpenReposeCommandError(
                    f"per_angle_metadata key {key!r} is not present in angles"
                )
            meta = _validate_item(canonical, item)
            if meta is not None:
                normalised[canonical] = meta
    else:
        raise OpenReposeCommandError(
            "per_angle_metadata must be a list aligned with angles or an object keyed by yaw bin"
        )

    encoded_all = json.dumps(normalised, ensure_ascii=False)
    if len(encoded_all.encode("utf-8")) > _PER_ANGLE_METADATA_MAX_BYTES:
        raise OpenReposeCommandError(
            f"per_angle_metadata exceeds {_PER_ANGLE_METADATA_MAX_BYTES} bytes"
        )
    if unknown_keys:
        log.warn(
            "export.batch_metadata",
            "unknown per-angle metadata keys preserved",
            keys=",".join(sorted(unknown_keys)),
        )
    return normalised


def _open_file_impl(d: CommandDispatcher, path: str, avatar_slug: str | None, file_id: str | None = None) -> dict[str, Any]:
    if avatar_slug is not None and (not isinstance(avatar_slug, str) or not avatar_slug):
        raise OpenReposeCommandError("avatar_slug must be a non-empty string")
    p = Path(path)
    fid = file_id or _new_file_id()
    if fid in d._files:
        raise OpenReposeCommandError(f"file_id already open: {fid}")
    if avatar_slug:
        effective_slug = avatar_slug
    else:
        from .util.slugify import sanitize_avatar_slug
        effective_slug = sanitize_avatar_slug(p.stem)

    previous_active = d._active_file_id
    d.state.set_portrait(str(p), avatar_slug=effective_slug)
    d.state.set_yaw(value_deg=0.0, bin_label="0")
    d.state.set_rig(status="fitting")
    d.state.write()
    d.log.ok("rig.fitting", portrait=str(p), avatar_slug=effective_slug or "")

    cal = None
    cal_loaded_from: str | None = None
    if effective_slug:
        cal_p = calibration_path(d.outputs_root, effective_slug)
        cal = load_calibration(cal_p)
        if cal is not None:
            cal_loaded_from = str(cal_p)

    try:
        rig = Rig.from_portrait(p, calibration=cal)
    except Exception:
        if previous_active and previous_active in d._files:
            _apply_slot_to_state(d, d._files[previous_active])
        elif d._file_order:
            _apply_slot_to_state(d, d._files[d._file_order[-1]])
        else:
            _clear_active_state(d)
            _sync_state_files(d)
        d.state.write()
        raise
    d._rig = rig
    d._active_file_id = fid
    _refresh_calibration_state(d.state, active_avatar=effective_slug, calibration=cal, loaded_from=cal_loaded_from)
    auto_uncheck, detected = _compute_marker_detection(rig)
    new_mv = default_marker_visibility()
    for schema, defaults in auto_uncheck.items():
        existing = new_mv.setdefault(schema, {})
        for idx_key, visible in defaults.items():
            existing.setdefault(idx_key, visible)
    with d.state._lock:
        d.state.marker_visibility = new_mv
        d.state.detected_markers = detected
        d.state.frame = default_frame()
    _set_state_rig_from_rig(d, rig)

    slot = FileSlot(
        file_id=fid,
        path=str(p),
        avatar_slug=effective_slug,
        rig=rig,
        yaw=dict(d.state.yaw),
        rig_state=dict(d.state.rig),
        calibration=dict(d.state.calibration),
        body_part_visibility=dict(d.state.body_part_visibility),
        marker_visibility=_copy_marker_visibility(d.state.marker_visibility),
        detected_markers={k: dict(v) for k, v in d.state.detected_markers.items()},
        frame=dict(d.state.frame),
        opened_at=_now_iso(),
    )
    d._files[fid] = slot
    d._file_order.append(fid)
    _sync_state_files(d)
    d.state.write()
    d.log.ok(
        "rig.fit",
        portrait=str(p),
        face=rig.fit_metrics.face_landmark_count,
        body=rig.fit_metrics.body_landmark_count,
        hands=rig.fit_metrics.hand_landmark_count,
        t_ms=rig.fit_metrics.fit_duration_ms,
        body_partial=rig.fit_metrics.body_partial,
    )
    return {
        "file_id": fid,
        "portrait": str(p),
        "avatar_slug": effective_slug,
        "fit_duration_ms": rig.fit_metrics.fit_duration_ms,
        "face_landmark_count": rig.fit_metrics.face_landmark_count,
        "body_landmark_count": rig.fit_metrics.body_landmark_count,
        "hand_landmark_count": rig.fit_metrics.hand_landmark_count,
        "hand_left_detected": rig.fit_metrics.hand_left_detected,
        "hand_right_detected": rig.fit_metrics.hand_right_detected,
        "hands_unavailable": rig.fit_metrics.hands_unavailable,
        "body_partial": rig.fit_metrics.body_partial,
        "body_partial_missing": list(rig.fit_metrics.body_partial_missing),
    }


def _h_open_file(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    path = cmd.get("path")
    if not isinstance(path, str) or not path:
        raise OpenReposeCommandError("open_file requires 'path'")
    file_id = cmd.get("file_id")
    if file_id is not None and (not isinstance(file_id, str) or not file_id):
        raise OpenReposeCommandError("file_id must be a non-empty string when supplied")
    return _open_file_impl(d, path, cmd.get("avatar_slug"), file_id=file_id)


def _h_close_file(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    file_id = cmd.get("file_id") or d._active_file_id
    if not isinstance(file_id, str) or not file_id:
        raise OpenReposeCommandError("close_file requires 'file_id' or an active file")
    result = _close_file_id(d, file_id)
    d.log.ok("workspace.file_close", file_id=file_id, active=d._active_file_id or "")
    return result


def _h_set_active_file(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    file_id = cmd.get("file_id")
    if not isinstance(file_id, str) or not file_id:
        raise OpenReposeCommandError("set_active_file requires 'file_id'")
    slot = _activate_file(d, file_id)
    d.state.write()
    d.log.ok("workspace.file_active", file_id=file_id)
    return {"active_file_id": file_id, "file": _slot_summary(d, slot)}


def _h_list_files(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    _sync_state_files(d)
    return {"active_file_id": d._active_file_id, "files": list(d.state.files)}

# --- handlers (registered in _HANDLERS at module bottom) --------------------


def _h_import_portrait(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    payload = _h_open_file(d, cmd)
    payload["alias"] = "import_portrait"
    return payload


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
    bin_objs = [parse_bin(label) for label in angles]
    angles = [bin_obj.label for bin_obj in bin_objs]
    if len(set(angles)) != len(angles):
        raise OpenReposeCommandError("angles must not contain duplicate yaw bins")
    per_angle_metadata = _normalise_per_angle_metadata(
        cmd.get("per_angle_metadata"),
        angles=angles,
        log=d.log,
    )

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
    for bin_obj in bin_objs:
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
    manifest = {
        "avatar_slug": avatar_slug,
        "portrait": d.state.portrait,
        "angles": angles,
        "files": written,
        "per_angle_metadata": per_angle_metadata,
        "per_angle_metadata_count": len(per_angle_metadata),
        "completed_at": _now_iso(),
    }
    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    written.append(str(manifest_path))

    d.state.add_export(
        type_="batch",
        out_dir=str(out_dir),
        files=written,
        metadata={
            "manifest": str(manifest_path),
            "per_angle_metadata": per_angle_metadata,
            "per_angle_metadata_count": len(per_angle_metadata),
        },
    )
    d.state.write()
    d.log.ok(
        "export.batch",
        avatar_slug=avatar_slug,
        angles=len(angles),
        out_dir=str(out_dir),
    )
    return {
        "out_dir": str(out_dir),
        "files": written,
        "angles": angles,
        "per_angle_metadata": per_angle_metadata,
        "per_angle_metadata_count": len(per_angle_metadata),
    }


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


def _h_clear_workspace(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Close the active file slot and return to empty state when last file closes."""
    file_id = cmd.get("file_id") or d._active_file_id
    if isinstance(file_id, str) and file_id in d._files:
        result = _close_file_id(d, file_id)
        d.log.ok("workspace.clear", file_id=file_id)
        return {"cleared": True, **result}

    _clear_active_state(d)
    _sync_state_files(d)
    d.log.ok("workspace.clear")
    return {
        "cleared": True,
        "portrait": None,
        "avatar_slug": None,
        "rig": dict(d.state.rig),
        "yaw": dict(d.state.yaw),
        "files": list(d.state.files),
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
        if k in ("command", "file_id"):
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


_SETTINGS_VALID_FIELDS = (
    "export_folder",
    "single_export_subdir_template",
    "batch_export_subdir_template",
    "last_portrait_dir",
    "canvas_border_color",
    "library_db_url",
    "library_root",
    "operator_slug",
)


def _settings_dump_payload(d: CommandDispatcher) -> dict[str, Any]:
    """Shared payload shape used by dump_settings / set_settings /
    clear_settings. Always redacts `library_db_url`."""
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


def _refresh_settings_state(d: CommandDispatcher) -> tuple[str, bool]:
    resolved, default_used = (
        d.settings.export_folder_resolved_with_fallback_flag()
    )
    d.state.set_settings_status(
        export_folder=str(resolved),
        default_used=default_used,
        settings_path=str(d.settings.settings_path),
    )
    return str(resolved), default_used


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
    return _settings_dump_payload(d)


def _h_set_settings(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    """Patch operator settings. Body: `fields` = dict of one or more
    settings field names mapped to new values. Unknown fields raise
    OpenReposeSettingsError; the existing on-disk file is untouched.

    Returns the same shape as `dump_settings` (with `library_db_url`
    redacted) so the caller sees the resulting state. Note: changing
    `library_db_url` does not reopen the live pool; the new URL takes
    effect on next App launch."""
    if d.settings is None:
        raise OpenReposeCommandError(
            "set_settings unavailable: dispatcher has no Settings instance"
        )
    fields = cmd.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise OpenReposeCommandError(
            "set_settings requires non-empty 'fields' (dict of "
            f"{{name: value}}); valid names: {sorted(_SETTINGS_VALID_FIELDS)}"
        )
    d.settings.update(**fields)
    resolved, default_used = _refresh_settings_state(d)
    d.log.ok(
        "settings.update",
        fields=",".join(sorted(fields.keys())),
        export_folder=resolved,
        default_used=default_used,
    )
    payload = _settings_dump_payload(d)
    payload["updated_fields"] = sorted(fields.keys())
    return payload


def _h_clear_settings(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    """Reset every operator-managed settings field to its default and
    persist. Preserves `settings_path` and `schema_version`. Mutates the
    live `Settings` instance in place so any references held elsewhere
    (e.g. App.settings) see the new defaults immediately."""
    if d.settings is None:
        raise OpenReposeCommandError(
            "clear_settings unavailable: dispatcher has no Settings instance"
        )
    defaults = Settings(settings_path=d.settings.settings_path)
    d.settings.update(
        **{name: getattr(defaults, name) for name in _SETTINGS_VALID_FIELDS}
    )
    resolved, default_used = _refresh_settings_state(d)
    d.log.ok(
        "settings.clear",
        path=str(d.settings.settings_path),
        export_folder=resolved,
        default_used=default_used,
    )
    payload = _settings_dump_payload(d)
    payload["cleared"] = True
    return payload


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


def _ensure_pool(d: CommandDispatcher):
    pool = getattr(d, "library_pool", None)
    if pool is None or not getattr(pool, "is_open", False):
        raise OpenReposeLibraryError(
            "library subsystem is disabled (no library_db_url configured "
            "or DB unreachable)"
        )
    return pool


def _operator_slug(d: CommandDispatcher) -> str | None:
    if d.settings is None:
        return None
    slug = d.settings.effective_operator_slug()
    return slug or None


def _library_root(d: CommandDispatcher) -> Path:
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
            if prompts_payload and isinstance(prompts_payload, dict):
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Return current schema_version + an inventory hash an operator /
    LLM agent can compare against the migration files in source control
    to confirm no drift."""
    pool = _ensure_pool(d)
    with pool.connection() as conn, conn.cursor() as cur:
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


def _intake_outputs_root(d: CommandDispatcher) -> Path:
    """Outputs root for intake filesystem operations. Same as the
    dispatcher's `outputs_root` (where `outputs/.runtime/`, `outputs/intake/`,
    `outputs/library/` all live)."""
    return Path(d.outputs_root)


def _require_operator_token(
    d: CommandDispatcher, cmd: dict[str, Any], command: str
) -> None:
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
    d: CommandDispatcher, task_uuid: str | None = None
) -> None:
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


def _h_project_create(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
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


def _h_project_list(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    status = cmd.get("status")
    with pool.connection() as conn:
        projects = list_projects(conn, status=status)
    return {"projects": [p.to_dict() for p in projects], "count": len(projects)}


def _h_task_create(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
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


def _h_task_list(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    project_id = cmd.get("project_id")
    status = cmd.get("status")
    with pool.connection() as conn:
        tasks = list_tasks(conn, project_id=project_id, status=status)
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}


def _h_task_summary(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    task_id = cmd.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise OpenReposeCommandError("task_summary requires 'task_id'")
    with pool.connection() as conn:
        summary = task_summary(conn, task_id=task_id)
    _refresh_intake_state(d, task_id)
    return {"summary": summary}


def _h_task_inspect(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
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
    d: CommandDispatcher, cmd: dict[str, Any]
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


def _h_intake_list(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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
    d: CommandDispatcher, cmd: dict[str, Any]
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


# ---------------------------------------------------------------------------
# I4 hardening commands (WP-I4-001)
# Spec: .gov/spec/openrepose_intake_v0_1.md
#       "I4 Scale + DB Hardening Extension"
# ---------------------------------------------------------------------------


def _h_intake_register_outputs_bulk(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Bulk counterpart to intake_register_output. One transaction per
    request. Idempotent on retry via the partial UNIQUE index on
    (task_id, agent_id, idempotency_key).

    Required payload:
      task_id, run_id, agent_id, outputs[]
    Optional payload:
      source_model, bulk_batch_max
    Each output dict requires: file_path, content_hash, width, height.
    Each output dict accepts: idempotency_key, producer_run_id, metadata.
    """
    pool = _ensure_pool(d)
    task_id = cmd.get("task_id")
    run_id = cmd.get("run_id")
    agent_id = cmd.get("agent_id")
    source_model = cmd.get("source_model")
    outputs = cmd.get("outputs")
    bulk_batch_max = int(cmd.get("bulk_batch_max", BULK_BATCH_MAX_DEFAULT))

    if not isinstance(task_id, str) or not task_id:
        raise OpenReposeCommandError(
            "intake_register_outputs_bulk requires 'task_id'"
        )
    if not isinstance(run_id, str) or not run_id:
        raise OpenReposeCommandError(
            "intake_register_outputs_bulk requires 'run_id'"
        )
    if not isinstance(agent_id, str) or not agent_id:
        raise OpenReposeCommandError(
            "intake_register_outputs_bulk requires 'agent_id'"
        )
    if not isinstance(outputs, list):
        raise OpenReposeCommandError(
            "intake_register_outputs_bulk requires 'outputs' (list)"
        )

    with pool.connection() as conn:
        task = get_task(conn, task_id=task_id)
        if task is None:
            raise OpenReposeCommandError(f"task {task_id} not found")
        if task.status in ("rejected_wholesale", "aborted"):
            raise OpenReposeCommandError(
                f"task {task_id} is terminal (status={task.status}); "
                f"cannot register"
            )

        result = register_outputs_bulk(
            conn,
            task_id=task_id,
            run_id=run_id,
            project_id=str(task.project_id),
            agent_id=agent_id,
            source_model=source_model,
            outputs=outputs,
            bulk_batch_max=bulk_batch_max,
            outputs_root=_intake_outputs_root(d),
        )
    _refresh_intake_state(d, task_id)
    return result.to_dict()


def _h_intake_recover_audit(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Read-only recovery audit. Optionally scoped to a single task.

    Optional payload:
      task_id           filter to a single task's outputs / file-ops
      check_disk        when True, additionally check on-disk presence
                        for non-terminal rows; defaults False because
                        large libraries make this expensive
    """
    pool = _ensure_pool(d)
    task_id = cmd.get("task_id")
    check_disk = bool(cmd.get("check_disk", False))
    outputs_root = _intake_outputs_root(d) if check_disk else None
    with pool.connection() as conn:
        audit = recover_audit(
            conn, task_id=task_id, outputs_root=outputs_root,
        )
    return audit.to_dict()


def _h_intake_recover_retry(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Retry one library_file_ops row exactly once.

    Required payload:
      file_op_id
    """
    pool = _ensure_pool(d)
    file_op_id = cmd.get("file_op_id")
    if not isinstance(file_op_id, str) or not file_op_id:
        raise OpenReposeCommandError("intake_recover_retry requires 'file_op_id'")
    actor = _operator_slug(d) or "system"
    with pool.connection() as conn:
        result = recover_retry(
            conn,
            file_op_id=file_op_id,
            outputs_root=_intake_outputs_root(d),
            actor=actor,
        )
    return result


def _h_intake_process_file_ops(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    """Drain pending library_file_ops rows. Operator/test driven.

    The bulk + auto-route paths enqueue file-op rows but do not
    execute them inline (so the bulk transaction stays bounded). This
    command runs one drain pass.

    Optional payload:
      limit             max rows to claim (default 20)
      claimed_by        worker slug for the claim (default operator slug)
    """
    pool = _ensure_pool(d)
    limit = int(cmd.get("limit", 20))
    claimed_by = cmd.get("claimed_by") or _operator_slug(d) or "dispatcher"
    with pool.connection() as conn:
        counters = process_pending_file_ops(
            conn,
            outputs_root=_intake_outputs_root(d),
            claimed_by=claimed_by,
            limit=limit,
        )
    return counters


# ---------------------------------------------------------------------------
# AMood commands (WP-I3-006)
# Spec: .gov/spec/openrepose_amood_v0_1.md "Command Surface (AMood-specific)"
# ---------------------------------------------------------------------------


def _h_init_batch_package(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    project_slug = cmd.get("project_slug")
    batch_slug = cmd.get("batch_slug")
    task_id = cmd.get("task_id")
    tier = cmd.get("tier", "production")
    primary_explicit_family = cmd.get("primary_explicit_family")
    dedupe_threshold = cmd.get("dedupe_threshold", 6)

    if not isinstance(project_slug, str) or not project_slug:
        raise OpenReposeCommandError("init_batch_package requires 'project_slug'")
    if not isinstance(batch_slug, str) or not batch_slug:
        raise OpenReposeCommandError("init_batch_package requires 'batch_slug'")
    if not isinstance(task_id, str) or not task_id:
        raise OpenReposeCommandError("init_batch_package requires 'task_id'")

    library_root = _library_root(d)
    with pool.connection() as conn:
        result = init_batch_package(
            conn,
            project_slug=project_slug,
            batch_slug=batch_slug,
            task_id=task_id,
            library_root=library_root,
            tier=tier,
            primary_explicit_family=primary_explicit_family,
            dedupe_threshold=int(dedupe_threshold),
        )

    batch = result["batch"]
    d.state.set_active_amood_batch(
        batch_id=batch["id"],
        batch_slug=batch["slug"],
        tier=batch["tier"],
        primary_explicit_family=batch["primary_explicit_family"],
    )
    d.state.set_guidance(
        current_focus=f"AMood batch {batch['slug']} initialized",
        next_valid_actions=[
            "library_create_card",
            "library_create_variants",
            "compatibility_check",
            "amood_export_tsv",
        ],
        active_rules=["AMOOD-001", "AMOOD-003", "AMOOD-004"],
    )
    return result


def _h_library_create_card(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    batch_id = cmd.get("batch_id")
    avatar_slug = cmd.get("avatar_slug")
    slug = cmd.get("slug")
    if not isinstance(batch_id, str) or not batch_id:
        raise OpenReposeCommandError("library_create_card requires 'batch_id'")
    if not isinstance(avatar_slug, str) or not avatar_slug:
        raise OpenReposeCommandError("library_create_card requires 'avatar_slug'")
    if not isinstance(slug, str) or not slug:
        raise OpenReposeCommandError("library_create_card requires 'slug'")

    extra_metadata = cmd.get("extra_metadata") or {}
    if not isinstance(extra_metadata, dict):
        raise OpenReposeCommandError("'extra_metadata' must be an object")

    with pool.connection() as conn:
        # Look up batch for dedupe_threshold default.
        batch = get_batch(conn, batch_id=batch_id)
        threshold = (
            cmd.get("dedupe_threshold")
            if cmd.get("dedupe_threshold") is not None
            else (batch.dedupe_threshold if batch else 6)
        )
        result = amood_create_card(
            conn,
            batch_id=batch_id,
            avatar_slug=avatar_slug,
            slug=slug,
            sexual_trigger=cmd.get("sexual_trigger"),
            kink_cue=cmd.get("kink_cue"),
            porn_archetype=cmd.get("porn_archetype"),
            fantasy_mode=cmd.get("fantasy_mode"),
            explicit_family=cmd.get("explicit_family"),
            exposure_detail=cmd.get("exposure_detail"),
            archetype_signal=cmd.get("archetype_signal"),
            scene_engine=cmd.get("scene_engine"),
            shot_purpose=cmd.get("shot_purpose"),
            pose_family=cmd.get("pose_family"),
            orientation=cmd.get("orientation"),
            wardrobe_state=cmd.get("wardrobe_state"),
            held_object=cmd.get("held_object"),
            support_object=cmd.get("support_object"),
            setting_family=cmd.get("setting_family"),
            lighting_family=cmd.get("lighting_family"),
            camera_family=cmd.get("camera_family"),
            gaze=cmd.get("gaze"),
            mouth_tongue=cmd.get("mouth_tongue"),
            palette_family=cmd.get("palette_family"),
            accent_color=cmd.get("accent_color"),
            dedupe_signature=cmd.get("dedupe_signature"),
            compatibility_signature=cmd.get("compatibility_signature"),
            dedupe_threshold=int(threshold),
            operator_slug=_operator_slug(d),
            extra_metadata=extra_metadata,
        )

    payload = result.to_dict()

    # Surface AMOOD-001 warning when dedupe overlap was found.
    if result.dedupe_match.has_overlap:
        top = result.dedupe_match.candidates[0]
        d.state.record_amood_dedupe_warning(
            card_id=str(result.card_id),
            overlap_count=top.overlap_count,
            matched_card_slug=top.candidate_slug,
        )
        citation = format_citation(
            command="library_create_card",
            rule_id="AMOOD-001",
            action_result="warned",
            fix_action=(
                f"revise card before promoting; overlaps {top.overlap_count}/8 "
                f"with {top.candidate_slug!r}; raise dedupe_threshold for the batch "
                "if intentional"
            ),
        )
        payload["amood_001_citation"] = citation
    return payload


def _h_library_create_variants(
    d: CommandDispatcher, cmd: dict[str, Any]
) -> dict[str, Any]:
    pool = _ensure_pool(d)
    parent_card_id = cmd.get("parent_card_id")
    variants = cmd.get("variants")
    if not isinstance(parent_card_id, str) or not parent_card_id:
        raise OpenReposeCommandError("library_create_variants requires 'parent_card_id'")
    if not isinstance(variants, list) or not variants:
        raise OpenReposeCommandError("library_create_variants requires non-empty 'variants' list")
    with pool.connection() as conn:
        children = create_variants(
            conn,
            parent_card_id=parent_card_id,
            variants=[str(v) for v in variants],
            operator_slug=_operator_slug(d),
        )
    return {"children": children, "count": len(children)}


def _h_compatibility_check(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    # No DB read required for the truth-table check; v0.1 takes axes
    # directly from the payload. (A future revision can resolve them
    # from card_id when the operator passes one instead of an axis set.)
    result = check_compatibility(
        sexual_trigger=cmd.get("sexual_trigger") or "",
        explicit_family=cmd.get("explicit_family") or "",
        pose_family=cmd.get("pose_family") or "",
        orientation=cmd.get("orientation") or "",
        camera_family=cmd.get("camera_family") or "",
        wardrobe_state=cmd.get("wardrobe_state") or "",
        support_object=cmd.get("support_object") or "",
        palette_family=cmd.get("palette_family") or "",
        lighting_family=cmd.get("lighting_family") or "",
        fantasy_mode=cmd.get("fantasy_mode") or "",
        primary_rejection_reason=cmd.get("primary_rejection_reason"),
    )
    payload = result.to_dict()
    if not result.pass_ok and result.hard_rejects:
        # Cite the first hard reject's rule_id (block-severity ones first).
        first = result.hard_rejects[0]
        rule_id = first.get("rule_id", "AMOOD-004")
        citation = format_citation(
            command="compatibility_check",
            rule_id=rule_id,
            action_result="blocked",
            fix_action=f"resolve hard_reject category {first.get('category')!r}: {first.get('detail', '')}",
        )
        payload["primary_citation"] = citation
    return payload


def _h_accepted_set_audit(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    batch_id = cmd.get("batch_id")
    if not isinstance(batch_id, str) or not batch_id:
        raise OpenReposeCommandError("accepted_set_audit requires 'batch_id'")
    with pool.connection() as conn:
        result = accepted_set_audit(conn, batch_id=batch_id)
    payload = result.to_dict()
    # Reflect last-audit summary on state.library.amood.
    summary = {
        "batch_id": payload["batch_id"],
        "axes_priority": [a for a in payload["axes"] if a["priority_flag"] == "priority"],
        "axes_watch":    [a for a in payload["axes"] if a["priority_flag"] == "watch"],
    }
    d.state.refresh_amood_card_counts(last_audit=summary)
    return payload


def _h_amood_export_tsv(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    schema = cmd.get("schema")
    batch_id = cmd.get("batch_id")
    project_id = cmd.get("project_id")
    if not isinstance(schema, str) or not schema:
        raise OpenReposeCommandError("amood_export_tsv requires 'schema'")
    with pool.connection() as conn:
        tsv_text = export_tsv(
            conn,
            schema=schema,
            batch_id=batch_id,
            project_id=project_id,
        )
    return {"schema": schema, "tsv_text": tsv_text, "byte_length": len(tsv_text)}


def _h_amood_import_tsv(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    pool = _ensure_pool(d)
    schema = cmd.get("schema")
    tsv_text = cmd.get("tsv_text")
    batch_id = cmd.get("batch_id")
    if not isinstance(schema, str) or not schema:
        raise OpenReposeCommandError("amood_import_tsv requires 'schema'")
    if not isinstance(tsv_text, str):
        raise OpenReposeCommandError("amood_import_tsv requires 'tsv_text'")
    with pool.connection() as conn:
        result = import_tsv(
            conn,
            schema=schema,
            tsv_text=tsv_text,
            batch_id=batch_id,
        )
    return {"schema": schema, **result}


# ===========================================================================
# WP-I3-007 — requirements editor + target tree commands
# Spec: .gov/spec/openrepose_requirements_v0_1.md
# ===========================================================================


def _resolve_project_id(d: CommandDispatcher, cmd: dict[str, Any]) -> tuple[str, str | None]:
    """Resolve project_id from command (accepting either id or slug). Returns
    (project_id, project_slug). Raises OpenReposeRequirementsError if neither
    resolves. project_slug may be None when only id was supplied."""
    pid = cmd.get("project_id")
    slug = cmd.get("project_slug")
    if not pid and not slug:
        raise OpenReposeRequirementsError(
            "command requires 'project_id' or 'project_slug'",
            rule_id="REQ-001",
        )
    pool = _ensure_pool(d)
    with pool.connection() as conn, conn.cursor() as cur:
        if pid:
            cur.execute("SELECT id, slug FROM library_projects WHERE id = %s", (pid,))
        else:
            cur.execute("SELECT id, slug FROM library_projects WHERE slug = %s", (slug,))
        row = cur.fetchone()
    if row is None:
        raise OpenReposeRequirementsError(
            f"project not found ({'id='+pid if pid else 'slug='+slug})",
            rule_id="REQ-001",
        )
    return str(row[0]), row[1]


def _refresh_targets_state(d: CommandDispatcher, project_id: str, project_slug: str | None) -> None:
    pool = _ensure_pool(d)
    with pool.connection() as conn:
        block = state_targets_block(conn, project_id=project_id, project_slug=project_slug)
    d.state.set_targets_state(
        project=block["project"],
        groups=block["groups"],
        active_task=block.get("active_task"),
        active_card=block.get("active_card"),
    )


def _h_project_set_target_tree(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    project_id, project_slug = _resolve_project_id(d, cmd)
    groups = cmd.get("groups")
    if not isinstance(groups, list):
        raise OpenReposeRequirementsError(
            "'groups' must be a list (may be empty)",
            rule_id="REQ-001",
        )
    pool = _ensure_pool(d)
    with pool.connection() as conn:
        result = target_set_tree(conn, project_id=project_id, groups=groups)
    _refresh_targets_state(d, project_id, project_slug)
    return {
        "project_id": project_id,
        "groups_created": len(result["groups"]),
        "cards_created": len(result["cards"]),
        "groups": result["groups"],
    }


def _h_project_add_requirement(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    project_id, _ = _resolve_project_id(d, cmd)
    rule_id = cmd.get("rule_id")
    name = cmd.get("name")
    short = cmd.get("short")
    severity = cmd.get("severity")
    kind = cmd.get("kind")
    if not isinstance(rule_id, str) or not rule_id:
        raise OpenReposeRequirementsError("project_add_requirement requires 'rule_id'", rule_id="REQ-001")
    if not isinstance(name, str) or not name:
        raise OpenReposeRequirementsError("project_add_requirement requires 'name'", rule_id="REQ-001")
    if not isinstance(short, str) or not short:
        raise OpenReposeRequirementsError("project_add_requirement requires 'short'", rule_id="REQ-001")
    if not isinstance(severity, str):
        raise OpenReposeRequirementsError("project_add_requirement requires 'severity'", rule_id="REQ-001")
    pool = _ensure_pool(d)
    with pool.connection() as conn:
        rule = create_rule(
            conn,
            rule_id=rule_id,
            scope_type=cmd.get("scope_type", "project"),
            scope_id=cmd.get("scope_id", project_id),
            name=name,
            short=short,
            severity=severity,
            kind=kind,
            manual_link=cmd.get("manual_link"),
            machine_check_fn=cmd.get("machine_check_fn"),
            auto_route_to=cmd.get("auto_route_to"),
            accept_terms=cmd.get("accept_terms"),
            reject_terms=cmd.get("reject_terms"),
        )
    return {"rule": rule.to_dict()}


def _h_project_set_requirement(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    """Upsert a rule. If a row with the given (rule_id, scope_type, scope_id)
    exists, update its mutable fields; otherwise create. Lower-scope override
    semantics per REQ-001 are realized at read time via
    `get_rule_with_inheritance`; this command only writes.
    """
    rule_id = cmd.get("rule_id")
    scope_type = cmd.get("scope_type")
    scope_id = cmd.get("scope_id")
    if not isinstance(rule_id, str) or not rule_id:
        raise OpenReposeRequirementsError("project_set_requirement requires 'rule_id'", rule_id="REQ-001")
    if not isinstance(scope_type, str):
        raise OpenReposeRequirementsError("project_set_requirement requires 'scope_type'", rule_id="REQ-001")
    if not scope_id:
        raise OpenReposeRequirementsError("project_set_requirement requires 'scope_id'", rule_id="REQ-001")
    pool = _ensure_pool(d)
    with pool.connection() as conn:
        existing = dump_rules(conn, scope_type=scope_type, scope_id=scope_id, rule_id=rule_id)
        if existing:
            rule = update_rule(
                conn,
                rule_uuid=existing[0].id,
                name=cmd.get("name"),
                short=cmd.get("short"),
                severity=cmd.get("severity"),
                kind=cmd.get("kind"),
                manual_link=cmd.get("manual_link"),
                machine_check_fn=cmd.get("machine_check_fn"),
                auto_route_to=cmd.get("auto_route_to"),
                accept_terms=cmd.get("accept_terms"),
                reject_terms=cmd.get("reject_terms"),
            )
            return {"rule": rule.to_dict(), "created": False}
        rule = create_rule(
            conn,
            rule_id=rule_id,
            scope_type=scope_type,
            scope_id=scope_id,
            name=cmd.get("name") or rule_id,
            short=cmd.get("short") or "",
            severity=cmd.get("severity") or "info",
            kind=cmd.get("kind"),
            manual_link=cmd.get("manual_link"),
            machine_check_fn=cmd.get("machine_check_fn"),
            auto_route_to=cmd.get("auto_route_to"),
            accept_terms=cmd.get("accept_terms"),
            reject_terms=cmd.get("reject_terms"),
        )
        return {"rule": rule.to_dict(), "created": True}


def _h_project_dump_requirements(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    project_id, _ = _resolve_project_id(d, cmd)
    scope_type = cmd.get("scope_type")
    scope_id = cmd.get("scope_id")
    rule_id = cmd.get("rule_id")
    pool = _ensure_pool(d)
    with pool.connection() as conn:
        if scope_type and scope_id and rule_id:
            rules = get_rule_with_inheritance(
                conn,
                rule_id=rule_id,
                scope_type=scope_type,
                scope_id=scope_id,
                project_id=project_id,
            )
        else:
            rules = dump_rules(conn, scope_type=scope_type, scope_id=scope_id, rule_id=rule_id)
    return {
        "project_id": project_id,
        "count": len(rules),
        "rules": [r.to_dict() for r in rules],
    }


def _h_project_render_markdown(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    project_id, project_slug = _resolve_project_id(d, cmd)
    pool = _ensure_pool(d)
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT slug, name, status FROM library_projects WHERE id = %s",
            (project_id,),
        )
        prow = cur.fetchone()
        if prow is None:
            raise OpenReposeRequirementsError(
                f"project {project_id} not found", rule_id="REQ-001"
            )
        slug, name, status = prow

        groups = target_list_groups(conn, project_id=project_id)
        rules = dump_rules(conn, scope_type="project", scope_id=project_id)

    project = ParsedProject(slug=slug, name=name, status=status)
    project.groups = [
        ParsedTargetGroup(
            slug=g.group_slug,
            name=g.group_name,
            expected_card_count=g.expected_card_count,
            target_per_card=g.target_per_card,
            ordering=g.ordering,
        )
        for g in groups
    ]
    project.requirements = [
        ParsedRequirement(
            rule_id=r.rule_id,
            kind=r.kind or "custom",
            severity=r.severity,
            short=r.short,
            machine_check_fn=r.machine_check_fn,
            auto_route_to=r.auto_route_to,
            accept_terms=r.accept_terms,
            reject_terms=r.reject_terms,
        )
        for r in rules
        if r.kind != "custom"  # v0.1: 'custom' kind not round-trippable
    ]
    md = render_markdown(project)
    return {
        "project_id": project_id,
        "markdown": md,
        "byte_count": len(md.encode("utf-8")),
        "structured": parsed_project_to_dict(project),
    }


def _h_project_import_markdown(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    project_id, project_slug = _resolve_project_id(d, cmd)
    md = cmd.get("markdown_text") or cmd.get("markdown")
    if not isinstance(md, str) or not md:
        raise OpenReposeRequirementsError(
            "project_import_markdown requires 'markdown_text'",
            rule_id="REQ-001",
        )
    try:
        parsed = parse_markdown(md)
    except CanonicalMarkdownError as e:
        raise OpenReposeRequirementsError(
            f"markdown parse failed: {e}",
            rule_id="REQ-001",
        ) from e

    pool = _ensure_pool(d)
    with pool.connection() as conn:
        # Markdown is operator-authoritative for project metadata: update
        # name + status from the parsed header so a subsequent
        # project_render_markdown round-trips byte-stable. Slug stays
        # immutable (it's the lookup key).
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE library_projects SET name = %s, status = %s WHERE id = %s",
                (parsed.name, parsed.status, project_id),
            )
        # Replace target tree.
        target_set_tree(
            conn,
            project_id=project_id,
            groups=[
                {
                    "slug": g.slug,
                    "name": g.name,
                    "expected_card_count": g.expected_card_count,
                    "target_per_card": g.target_per_card,
                    "ordering": g.ordering,
                }
                for g in parsed.groups
            ],
        )
        # Replace project-scope rules: drop existing project-scope rules,
        # insert from markdown. Higher-scope (task/batch/card) rules survive.
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM library_rules WHERE scope_type = 'project' AND scope_id = %s",
                (project_id,),
            )
        for r in parsed.requirements:
            create_rule(
                conn,
                rule_id=r.rule_id,
                scope_type="project",
                scope_id=project_id,
                name=r.rule_id,
                short=r.short,
                severity=r.severity,
                kind=r.kind,
                machine_check_fn=r.machine_check_fn,
                auto_route_to=r.auto_route_to,
                accept_terms=r.accept_terms,
                reject_terms=r.reject_terms,
            )
        conn.commit()

    _refresh_targets_state(d, project_id, project_slug)
    return {
        "project_id": project_id,
        "groups_imported": len(parsed.groups),
        "requirements_imported": len(parsed.requirements),
    }


def _h_target_summary(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    scope_type = cmd.get("scope_type", "project")
    scope_id = cmd.get("scope_id")
    if scope_type == "project" and scope_id is None:
        # Convenience: accept project_slug or project_id at the top level too.
        scope_id, _ = _resolve_project_id(d, cmd)
    if scope_id is None:
        raise OpenReposeRequirementsError(
            "target_summary requires 'scope_id'", rule_id="REQ-001"
        )
    pool = _ensure_pool(d)
    with pool.connection() as conn:
        if scope_type == "project":
            summary = target_project_summary(conn, project_id=scope_id)
        elif scope_type == "group":
            summary = target_group_summary(conn, group_id=scope_id)
        elif scope_type == "card":
            summary = target_card_summary(conn, target_card_id=scope_id)
        else:
            raise OpenReposeRequirementsError(
                f"target_summary scope_type must be project|group|card; got {scope_type!r}",
                rule_id="REQ-001",
            )
    return {"summary": summary.to_dict()}


def _h_target_recount(d: CommandDispatcher, cmd: dict[str, Any]) -> dict[str, Any]:
    scope_type = cmd.get("scope_type", "project")
    scope_id = cmd.get("scope_id")
    if scope_type == "project" and scope_id is None:
        scope_id, _ = _resolve_project_id(d, cmd)
    if scope_id is None:
        raise OpenReposeRequirementsError("target_recount requires 'scope_id'", rule_id="REQ-001")
    pool = _ensure_pool(d)
    with pool.connection() as conn:
        summary = target_recount_fn(conn, scope_type=scope_type, scope_id=scope_id)
    return {"summary": summary.to_dict()}


_HANDLERS = {
    "import_portrait": _h_import_portrait,
    "open_file": _h_open_file,
    "close_file": _h_close_file,
    "set_active_file": _h_set_active_file,
    "list_files": _h_list_files,
    "set_yaw": _h_set_yaw,
    "set_yaw_bin": _h_set_yaw_bin,
    "export_single": _h_export_single,
    "export_batch": _h_export_batch,
    "snapshot": _h_snapshot,
    "dump_rig": _h_dump_rig,
    "dump_state": _h_dump_state,
    "clear_outputs": _h_clear_outputs,
    "clear_workspace": _h_clear_workspace,
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
    "set_settings": _h_set_settings,
    "clear_settings": _h_clear_settings,
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
    # I4 hardening commands (WP-I4-001).
    "intake_register_outputs_bulk": _h_intake_register_outputs_bulk,
    "intake_recover_audit":         _h_intake_recover_audit,
    "intake_recover_retry":         _h_intake_recover_retry,
    "intake_process_file_ops":      _h_intake_process_file_ops,
    # AMood commands (WP-I3-006).
    "init_batch_package":     _h_init_batch_package,
    "library_create_card":    _h_library_create_card,
    "library_create_variants": _h_library_create_variants,
    "compatibility_check":    _h_compatibility_check,
    "accepted_set_audit":     _h_accepted_set_audit,
    "amood_export_tsv":       _h_amood_export_tsv,
    "amood_import_tsv":       _h_amood_import_tsv,
    # Requirements + target tree commands (WP-I3-007).
    "project_set_target_tree":   _h_project_set_target_tree,
    "project_add_requirement":   _h_project_add_requirement,
    "project_set_requirement":   _h_project_set_requirement,
    "project_dump_requirements": _h_project_dump_requirements,
    "project_render_markdown":   _h_project_render_markdown,
    "project_import_markdown":   _h_project_import_markdown,
    "target_summary":            _h_target_summary,
    "target_recount":            _h_target_recount,
}
