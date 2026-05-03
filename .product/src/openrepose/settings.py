"""Cross-launch operator settings (export folder, subdir templates,
library config).

Spec: `.gov/spec/openrepose_v0_1.md` Feature 1 / GUI Requirements (Options
tab) and Feature 1 / CLI Requirements (export honors operator-chosen
folder). v2 fields land per `.gov/spec/openrepose_library_v0_1.md`
Storage Layout (`library_db_url`, `library_root`, `operator_slug`).

Settings are stored as plain JSON at `<AppConfigLocation>/openrepose/
settings.json` (resolved via Qt's `QStandardPaths` for cross-platform
correctness). Plain JSON over `QSettings` because the operator can
inspect, edit, and back up the file directly — matches the rest of the
repo (state.json, calibration.json are all plain JSON).

Schema migration policy: `load()` accepts schema_version <
`SETTINGS_SCHEMA_VERSION` and patches in defaults for new fields, then
re-saves the file at the current schema_version. Schema_version >
`SETTINGS_SCHEMA_VERSION` raises (a future version of the app
downgrading is not supported).
"""

from __future__ import annotations

import datetime
import getpass
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SETTINGS_SCHEMA_VERSION = 2
DEFAULT_EXPORT_DIR_NAME = "openrepose-output"
DEFAULT_LIBRARY_DIR_NAME = "library"


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
    last_portrait_dir: str = ""
    canvas_border_color: str = "#ffffff"
    library_db_url: str = ""
    library_root: str = ""
    operator_slug: str = ""
    settings_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "export_folder": str(self.export_folder),
            "single_export_subdir_template": str(self.single_export_subdir_template),
            "batch_export_subdir_template": str(self.batch_export_subdir_template),
            "last_portrait_dir": str(self.last_portrait_dir),
            "canvas_border_color": str(self.canvas_border_color),
            "library_db_url": str(self.library_db_url),
            "library_root": str(self.library_root),
            "operator_slug": str(self.operator_slug),
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
            "last_portrait_dir",
            "canvas_border_color",
            "library_db_url",
            "library_root",
            "operator_slug",
        }
        for k, v in kwargs.items():
            if k not in valid:
                raise OpenReposeSettingsError(
                    f"unknown settings field {k!r}; valid: {sorted(valid)}"
                )
            setattr(self, k, v)
        if self.settings_path is not None and Path(self.settings_path).name:
            self.save()

    def resolved_library_root(self) -> Path:
        """Return the operator's `library_root` if set, else
        `<resolved_export_folder>/library/`. Does not mkdir; the library
        machinery is responsible for creating the directory when the DB
        connection actually succeeds."""
        if self.library_root:
            return Path(self.library_root)
        return self.resolved_export_folder() / DEFAULT_LIBRARY_DIR_NAME

    def effective_operator_slug(self) -> str:
        """Return the operator slug, falling back to the OS username when
        unset. Used for `library_entries.created_by` / `locked_by` and the
        state.json `library.operator_slug` reflection."""
        if self.operator_slug:
            return self.operator_slug
        return _default_operator_slug()

    def redacted_db_url(self) -> str:
        """Return `library_db_url` with the password component masked.

        Example: `postgresql://user:secret@host:5432/db` →
        `postgresql://user:***@host:5432/db`. Empty input returns empty."""
        if not self.library_db_url:
            return ""
        return _redact_db_url(self.library_db_url)


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
    (caller should construct defaults). Raises on malformed JSON or
    schema_version > current. Older schema_versions are migrated forward
    in place: defaults are patched in for new fields and the file is
    re-saved at the current `SETTINGS_SCHEMA_VERSION`."""
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
    if not isinstance(schema_version, int):
        raise OpenReposeSettingsError(
            f"schema_version must be an int; got {schema_version!r} at {p}"
        )
    if schema_version > SETTINGS_SCHEMA_VERSION:
        raise OpenReposeSettingsError(
            f"unsupported schema_version {schema_version!r}; this app "
            f"version supports up to {SETTINGS_SCHEMA_VERSION}"
        )

    needs_migration = schema_version < SETTINGS_SCHEMA_VERSION

    settings = Settings(
        schema_version=SETTINGS_SCHEMA_VERSION,
        export_folder=str(data.get("export_folder", "")),
        single_export_subdir_template=str(
            data.get("single_export_subdir_template", "{avatar}")
        ),
        batch_export_subdir_template=str(
            data.get("batch_export_subdir_template", "{avatar}/{run_tag}")
        ),
        last_portrait_dir=str(data.get("last_portrait_dir", "")),
        canvas_border_color=str(data.get("canvas_border_color", "#ffffff")),
        library_db_url=str(data.get("library_db_url", "")),
        library_root=str(data.get("library_root", "")),
        operator_slug=str(data.get("operator_slug", "")),
        settings_path=p,
    )

    if needs_migration:
        # Re-emit at the current schema_version with defaults patched in.
        # Atomic via Settings.save (temp file + os.replace).
        settings.save()

    return settings


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


def _default_operator_slug() -> str:
    """OS username, lowercased, with whitespace stripped. Empty if the
    underlying lookup fails (rare; sandboxed environments)."""
    try:
        name = getpass.getuser()
    except Exception:
        return ""
    return name.strip().lower()


def _redact_db_url(url: str) -> str:
    """Mask the password in a `scheme://user:password@host[:port]/db` URL.

    Returns the input unchanged when no password component is present.
    Pure-string parsing (no urllib import) so the function stays cheap and
    handles odd vendor URL shapes consistently with `psycopg`'s parser
    behavior (it treats everything between `:` and `@` as the password).
    """
    scheme_sep = "://"
    idx = url.find(scheme_sep)
    if idx < 0:
        return url
    head = url[: idx + len(scheme_sep)]
    rest = url[idx + len(scheme_sep) :]
    at = rest.rfind("@")
    if at < 0:
        return url
    creds = rest[:at]
    tail = rest[at:]
    colon = creds.find(":")
    if colon < 0:
        return url
    user = creds[:colon]
    return f"{head}{user}:***{tail}"
