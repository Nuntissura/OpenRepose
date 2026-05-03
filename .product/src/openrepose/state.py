"""Atomic state file for OpenRepose.

Every command updates `outputs/.runtime/state.json` atomically (write to
temp + rename) so an LLM agent reading it never sees a partial JSON
document. Schema is the one in `.gov/spec/openrepose_v0_1.md` section
"LLM Control Surface".

Bounded retention: `exports`, `snapshots`, `errors` arrays cap at 100
most-recent entries (FIFO).
"""

from __future__ import annotations

import datetime
import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_STATE_FILE = Path("outputs/.runtime/state.json")
STATE_VERSION = "0.1"
RETENTION_LIMIT = 100


def _now() -> str:
    """ISO-8601 UTC timestamp with millisecond precision."""
    return datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{datetime.datetime.now(tz=datetime.UTC).microsecond // 1000:03d}Z"
    )


@dataclass
class AppState:
    """In-memory mirror of state.json. Mutate via the helper methods so
    retention bounds and atomic writes stay consistent."""

    state_path: Path = DEFAULT_STATE_FILE
    version: str = STATE_VERSION
    started_at: str = field(default_factory=_now)
    portrait: str | None = None
    avatar_slug: str | None = None
    rig: dict[str, Any] = field(
        default_factory=lambda: {
            "status": "none",
            "fit_at": None,
            "fit_duration_ms": 0,
            "face_landmark_count": 0,
            "body_landmark_count": 0,
            "face_visible_in_openpose": 0,
            "body_visible_in_openpose": 0,
        }
    )
    yaw: dict[str, Any] = field(
        default_factory=lambda: {
            "current_value_deg": 0.0,
            "current_bin": "0",
            "axis": "y",
        }
    )
    exports: list[dict[str, Any]] = field(default_factory=list)
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    last_command: dict[str, Any] = field(
        default_factory=lambda: {
            "command": None,
            "received_at": None,
            "completed_at": None,
            "status": None,
        }
    )
    calibration: dict[str, Any] = field(
        default_factory=lambda: {
            "active_avatar": None,
            "completeness": "none",
            "marker_count": 0,
            "missing_required": [],
            "field_cached": False,
            "loaded_from": None,
            "last_dump_at": None,
        }
    )
    settings: dict[str, Any] = field(
        default_factory=lambda: {
            "export_folder": None,
            "default_used": True,
            "settings_path": None,
        }
    )
    body_part_visibility: dict[str, bool] = field(
        default_factory=lambda: {
            "face": True,
            "body_torso": True,
            "arms": True,
            "legs": True,
            "hands": True,
        }
    )
    marker_visibility: dict[str, dict[str, bool]] = field(
        default_factory=lambda: {"body_18": {}, "face_70": {}}
    )
    detected_markers: dict[str, dict[str, bool]] = field(
        default_factory=lambda: {"body_18": {}, "face_70": {}}
    )
    frame: dict[str, Any] = field(
        default_factory=lambda: {
            "scale": 1.0,
            "offset_x": 0,
            "offset_y": 0,
            "anchor_mode": "head_anchor",
            "anchor_point": None,
        }
    )
    library: dict[str, Any] = field(
        default_factory=lambda: {
            "connected": False,
            "configured": False,
            "db_url_redacted": "",
            "schema_version": 0,
            "operator_slug": "",
            "library_root": "",
            "last_error": None,
            "last_search_query": None,
            "last_search_count": 0,
            "last_search_at": None,
            "last_register_at": None,
            "pending_writes": 0,
            "locked_entries": [],
        }
    )

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # --- mutation helpers ------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "started_at": self.started_at,
            "portrait": self.portrait,
            "avatar_slug": self.avatar_slug,
            "rig": dict(self.rig),
            "yaw": dict(self.yaw),
            "exports": list(self.exports),
            "snapshots": list(self.snapshots),
            "errors": list(self.errors),
            "last_command": dict(self.last_command),
            "calibration": dict(self.calibration),
            "settings": dict(self.settings),
            "body_part_visibility": dict(self.body_part_visibility),
            "marker_visibility": {
                k: dict(v) for k, v in self.marker_visibility.items()
            },
            "detected_markers": {
                k: dict(v) for k, v in self.detected_markers.items()
            },
            "frame": dict(self.frame),
            "library": dict(self.library),
        }

    def write(self) -> None:
        """Atomic write to `state_path`. Caller must hold no other lock on
        the file. Internally serializes `state_path.parent` write order via
        `self._lock`. Retries `os.replace` briefly on Windows where a
        concurrent reader can transiently block the rename."""
        import time

        with self._lock:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
            last_err: OSError | None = None
            for _ in range(50):
                try:
                    os.replace(tmp, self.state_path)
                    return
                except PermissionError as e:
                    last_err = e
                    time.sleep(0.005)
            # Best-effort: bubble the last error if we couldn't replace
            # within ~250ms. State writes are frequent so a swallow would
            # silently lose updates.
            if last_err is not None:
                raise last_err

    def set_portrait(self, path: str, avatar_slug: str | None = None) -> None:
        with self._lock:
            self.portrait = path
            if avatar_slug is not None:
                self.avatar_slug = avatar_slug

    def set_rig(
        self,
        status: str,
        *,
        fit_duration_ms: int = 0,
        face_landmark_count: int = 0,
        body_landmark_count: int = 0,
        face_visible_in_openpose: int = 0,
        body_visible_in_openpose: int = 0,
    ) -> None:
        with self._lock:
            self.rig = {
                "status": status,
                "fit_at": _now() if status == "ok" else None,
                "fit_duration_ms": int(fit_duration_ms),
                "face_landmark_count": int(face_landmark_count),
                "body_landmark_count": int(body_landmark_count),
                "face_visible_in_openpose": int(face_visible_in_openpose),
                "body_visible_in_openpose": int(body_visible_in_openpose),
            }

    def set_yaw(self, *, value_deg: float, bin_label: str) -> None:
        with self._lock:
            self.yaw = {
                "current_value_deg": float(value_deg),
                "current_bin": bin_label,
                "axis": "y",
            }

    def add_export(self, *, type_: str, out_dir: str, files: list[str]) -> None:
        with self._lock:
            self.exports.append(
                {
                    "type": type_,
                    "out_dir": out_dir,
                    "completed_at": _now(),
                    "files": list(files),
                }
            )
            self._cap_array("exports")

    def add_snapshot(self, *, target: str, out_path: str) -> None:
        with self._lock:
            self.snapshots.append(
                {
                    "target": target,
                    "out_path": out_path,
                    "captured_at": _now(),
                }
            )
            self._cap_array("snapshots")

    def add_error(self, *, level: str, op: str, reason: str) -> None:
        with self._lock:
            self.errors.append(
                {
                    "level": level,
                    "op": op,
                    "reason": reason,
                    "at": _now(),
                }
            )
            self._cap_array("errors")

    def set_calibration_status(
        self,
        *,
        active_avatar: str | None,
        completeness: str,
        marker_count: int,
        missing_required: tuple[str, ...] | list[str] = (),
        field_cached: bool = False,
        loaded_from: str | None = None,
    ) -> None:
        """Update the `calibration` block. Preserves `last_dump_at`."""
        with self._lock:
            self.calibration = {
                "active_avatar": active_avatar,
                "completeness": completeness,
                "marker_count": int(marker_count),
                "missing_required": list(missing_required),
                "field_cached": bool(field_cached),
                "loaded_from": loaded_from,
                "last_dump_at": self.calibration.get("last_dump_at"),
            }

    def mark_calibration_dump(self) -> None:
        with self._lock:
            self.calibration["last_dump_at"] = _now()

    def set_settings_status(
        self,
        *,
        export_folder: str | None,
        default_used: bool,
        settings_path: str | None,
    ) -> None:
        with self._lock:
            self.settings = {
                "export_folder": export_folder,
                "default_used": bool(default_used),
                "settings_path": settings_path,
            }

    def set_library_status(
        self,
        *,
        configured: bool,
        connected: bool,
        db_url_redacted: str,
        schema_version: int,
        operator_slug: str,
        library_root: str,
        last_error: str | None = None,
    ) -> None:
        """Update the `library` block's connection status (WP-I2-001).

        Activity fields (last_search_*, last_register_at, locked_entries)
        are mutated by the library command handlers (WP-I2-004)."""
        with self._lock:
            self.library = {
                **self.library,
                "configured": bool(configured),
                "connected": bool(connected),
                "db_url_redacted": str(db_url_redacted),
                "schema_version": int(schema_version),
                "operator_slug": str(operator_slug),
                "library_root": str(library_root),
                "last_error": last_error,
            }

    def mark_library_register(self) -> None:
        """Record the timestamp of the last `register_library_entry`."""
        with self._lock:
            self.library = {**self.library, "last_register_at": _now()}

    def mark_library_search(self, *, query: str, count: int) -> None:
        with self._lock:
            self.library = {
                **self.library,
                "last_search_query": query,
                "last_search_count": int(count),
                "last_search_at": _now(),
            }

    def add_library_lock(self, entry_id: str, locked_by: str | None) -> None:
        """Append an entry id to `locked_entries` (deduped). The dispatcher
        clears the list at the start of each command via
        `clear_library_locks`."""
        with self._lock:
            current = list(self.library.get("locked_entries") or [])
            tag = {"entry_id": str(entry_id), "locked_by": locked_by}
            if tag not in current:
                current.append(tag)
            self.library = {**self.library, "locked_entries": current}

    def clear_library_locks(self) -> None:
        with self._lock:
            self.library = {**self.library, "locked_entries": []}

    def begin_command(self, command: str) -> None:
        with self._lock:
            self.last_command = {
                "command": command,
                "received_at": _now(),
                "completed_at": None,
                "status": "in_progress",
            }

    def end_command(self, *, status: str) -> None:
        with self._lock:
            self.last_command["completed_at"] = _now()
            self.last_command["status"] = status

    # --- internals -------------------------------------------------------

    def _cap_array(self, name: str) -> None:
        arr = getattr(self, name)
        if len(arr) > RETENTION_LIMIT:
            del arr[: len(arr) - RETENTION_LIMIT]
