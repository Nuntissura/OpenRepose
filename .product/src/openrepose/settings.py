"""Cross-launch operator settings (export folder, subdir templates).

Spec: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements (Options
tab) and Feature 1 / CLI Requirements (export honors operator-chosen
folder).

Settings are stored as plain JSON at `<AppConfigLocation>/openrepose/
settings.json` (resolved via Qt's `QStandardPaths` for cross-platform
correctness). Plain JSON over `QSettings` because the operator can
inspect, edit, and back up the file directly — matches the rest of the
repo (state.json, calibration.json are all plain JSON).
"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SETTINGS_SCHEMA_VERSION = 1
DEFAULT_EXPORT_DIR_NAME = "openrepose-output"


class OpenReposeSettingsError(ValueError):
    """Raised on malformed settings JSON or wrong schema version."""


@dataclass
class Settings:
    """In-memory settings record. Mutable by design — call `save()` to
    persist; `update()` mutates in place + persists in one shot."""

    schema_version: int = SETTINGS_SCHEMA_VERSION
    export_folder: str = ""
    single_export_subdir_template: str = "{avatar}"
    batch_export_subdir_template: str = "{avatar}/{run_tag}"
    settings_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "export_folder": str(self.export_folder),
            "single_export_subdir_template": str(self.single_export_subdir_template),
            "batch_export_subdir_template": str(self.batch_export_subdir_template),
            "updated_at": _now_iso(),
        }

    def resolved_export_folder(self) -> Path:
        """Return the operator's `export_folder` if set and existing,
        else fall back to the default. The fallback is computed lazily so
        that test environments without `~/Desktop/` still work."""
        if self.export_folder:
            p = Path(self.export_folder)
            if p.exists():
                return p
        return default_export_folder()

    def export_folder_resolved_with_fallback_flag(self) -> tuple[Path, bool]:
        """Return (path, default_used). `default_used=True` when the saved
        export_folder is empty or does not exist on disk."""
        if self.export_folder:
            p = Path(self.export_folder)
            if p.exists():
                return p, False
        return default_export_folder(), True

    def save(self) -> None:
        """Atomic write to `self.settings_path`."""
        if self.settings_path is None or not Path(self.settings_path).name:
            raise OpenReposeSettingsError(
                "settings_path is unset; refusing to save"
            )
        p = Path(self.settings_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp, p)

    def update(self, **kwargs: Any) -> None:
        """Patch fields in place + persist. Unknown keys raise."""
        valid = {
            "export_folder",
            "single_export_subdir_template",
            "batch_export_subdir_template",
        }
        for k, v in kwargs.items():
            if k not in valid:
                raise OpenReposeSettingsError(
                    f"unknown settings field {k!r}; valid: {sorted(valid)}"
                )
            setattr(self, k, v)
        if self.settings_path is not None and Path(self.settings_path).name:
            self.save()


def settings_path() -> Path:
    """Default cross-platform settings file location.

    Resolved via `QStandardPaths.writableLocation(AppConfigLocation)` —
    `%APPDATA%\\openrepose\\` on Windows, `~/.config/openrepose/` on Linux,
    `~/Library/Preferences/openrepose/` on macOS. The function imports
    PySide6 lazily so callers that only need the storage primitives (e.g.,
    headless tests) can pass an explicit path and avoid the Qt import.
    """
    from PySide6.QtCore import QStandardPaths

    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    if not base:
        # Defensive fallback when Qt cannot resolve the location (rare;
        # would require a broken Qt install). Use ~/.openrepose/.
        return Path.home() / ".openrepose" / "settings.json"
    return Path(base) / "openrepose" / "settings.json"


def default_export_folder() -> Path:
    """`~/Desktop/openrepose-output/` when Desktop exists; else
    `~/openrepose-output/`. Operator's request: discoverable location, not
    buried inside the repo."""
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        return desktop / DEFAULT_EXPORT_DIR_NAME
    return Path.home() / DEFAULT_EXPORT_DIR_NAME


def load(path: Path | str) -> Settings | None:
    """Load settings from JSON. Returns None if the file does not exist
    (caller should construct defaults). Raises on malformed JSON or wrong
    schema version."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise OpenReposeSettingsError(
            f"settings JSON unparseable at {p}: {e}"
        ) from e

    if not isinstance(data, dict):
        raise OpenReposeSettingsError(
            f"settings JSON must be an object at {p}"
        )

    schema_version = data.get("schema_version")
    if schema_version != SETTINGS_SCHEMA_VERSION:
        raise OpenReposeSettingsError(
            f"unsupported schema_version {schema_version!r}; expected "
            f"{SETTINGS_SCHEMA_VERSION}"
        )

    return Settings(
        schema_version=int(schema_version),
        export_folder=str(data.get("export_folder", "")),
        single_export_subdir_template=str(
            data.get("single_export_subdir_template", "{avatar}")
        ),
        batch_export_subdir_template=str(
            data.get("batch_export_subdir_template", "{avatar}/{run_tag}")
        ),
        settings_path=p,
    )


def load_or_default(path: Path | str | None = None) -> Settings:
    """Load settings, or return a fresh defaults Settings bound to `path`.

    `path=None` resolves to the cross-platform `settings_path()` default.
    """
    if path is None:
        path = settings_path()
    p = Path(path)
    loaded = load(p)
    if loaded is not None:
        return loaded
    return Settings(settings_path=p)


def render_subdir(
    template: str,
    *,
    avatar: str,
    run_tag: str = "",
) -> str:
    """Render a `{avatar}` / `{run_tag}` subdir template. Missing keys raise."""
    try:
        return template.format(avatar=avatar, run_tag=run_tag)
    except KeyError as e:
        raise OpenReposeSettingsError(
            f"unknown template placeholder {e!r}; allowed: {{avatar}}, {{run_tag}}"
        ) from e


def _now_iso() -> str:
    """ISO-8601 UTC timestamp with millisecond precision (matches state.py)."""
    now = datetime.datetime.now(tz=datetime.UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
