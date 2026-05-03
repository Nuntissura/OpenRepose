"""Tests for openrepose.settings.

Spec: `.gov/spec/openrepose_v0_1.md` Feature 1 / Options tab + CLI export
folder. WP-I1-027. Extended for WP-I2-002 (schema_version 1 → 2: adds
library_db_url, library_root, operator_slug; v1 settings.json migrate
forward).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openrepose.settings import (
    DEFAULT_EXPORT_DIR_NAME,
    DEFAULT_LIBRARY_DIR_NAME,
    SETTINGS_SCHEMA_VERSION,
    OpenReposeSettingsError,
    Settings,
    default_export_folder,
    load,
    load_or_default,
    render_subdir,
    settings_path,
)
from openrepose.settings import _default_operator_slug, _redact_db_url


# --- defaults & path resolution ---------------------------------------------


def test_default_export_folder_uses_desktop_or_home():
    p = default_export_folder()
    assert p.name == DEFAULT_EXPORT_DIR_NAME
    assert p.parent in (Path.home() / "Desktop", Path.home())


def test_settings_path_resolves_under_app_config():
    p = settings_path()
    assert p.name == "settings.json"
    assert "openrepose" in p.parts


# --- round-trip --------------------------------------------------------------


def test_save_load_roundtrip(tmp_path: Path):
    s = Settings(
        export_folder=str(tmp_path / "exports"),
        single_export_subdir_template="{avatar}/single",
        batch_export_subdir_template="{avatar}/{run_tag}",
        last_portrait_dir=str(tmp_path / "portraits"),
        canvas_border_color="#ff8800",
        settings_path=tmp_path / "settings.json",
    )
    s.save()
    loaded = load(tmp_path / "settings.json")
    assert loaded is not None
    assert loaded.export_folder == str(tmp_path / "exports")
    assert loaded.single_export_subdir_template == "{avatar}/single"
    assert loaded.batch_export_subdir_template == "{avatar}/{run_tag}"
    assert loaded.last_portrait_dir == str(tmp_path / "portraits")
    assert loaded.canvas_border_color == "#ff8800"
    assert loaded.schema_version == SETTINGS_SCHEMA_VERSION


def test_settings_defaults_for_new_fields(tmp_path: Path):
    """A fresh Settings (no persisted file) defaults last_portrait_dir to ""
    and canvas_border_color to "#ffffff"."""
    s = load_or_default(tmp_path / "settings.json")
    assert s.last_portrait_dir == ""
    assert s.canvas_border_color == "#ffffff"


def test_update_persists_new_fields(tmp_path: Path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.save()
    s.update(
        last_portrait_dir=str(tmp_path / "portraits"),
        canvas_border_color="#00ff00",
    )
    reloaded = load(tmp_path / "settings.json")
    assert reloaded is not None
    assert reloaded.last_portrait_dir == str(tmp_path / "portraits")
    assert reloaded.canvas_border_color == "#00ff00"


def test_save_atomic_via_temp_then_rename(tmp_path: Path):
    s = Settings(
        export_folder=str(tmp_path / "x"),
        settings_path=tmp_path / "settings.json",
    )
    s.save()
    assert (tmp_path / "settings.json").exists()
    assert not (tmp_path / "settings.json.tmp").exists()


def test_save_writes_iso_timestamp(tmp_path: Path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.save()
    data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert data["updated_at"]
    assert data["schema_version"] == SETTINGS_SCHEMA_VERSION


def test_save_without_path_raises():
    s = Settings()  # settings_path empty
    with pytest.raises(OpenReposeSettingsError):
        s.save()


# --- load semantics ---------------------------------------------------------


def test_load_missing_file_returns_none(tmp_path: Path):
    assert load(tmp_path / "no-such.json") is None


def test_load_unparseable_raises(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(OpenReposeSettingsError):
        load(p)


def test_load_non_object_root_raises(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(OpenReposeSettingsError):
        load(p)


def test_load_future_schema_version_raises(tmp_path: Path):
    """A schema_version above the current is unsupported (future-app file
    being read by an older app version)."""
    p = tmp_path / "bad.json"
    p.write_text(
        json.dumps({"schema_version": 999, "export_folder": ""}),
        encoding="utf-8",
    )
    with pytest.raises(OpenReposeSettingsError):
        load(p)


def test_load_non_int_schema_version_raises(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text(
        json.dumps({"schema_version": "two", "export_folder": ""}),
        encoding="utf-8",
    )
    with pytest.raises(OpenReposeSettingsError):
        load(p)


def test_load_or_default_with_missing_file(tmp_path: Path):
    s = load_or_default(tmp_path / "settings.json")
    assert s.export_folder == ""
    assert s.single_export_subdir_template == "{avatar}"
    assert s.batch_export_subdir_template == "{avatar}/{run_tag}"
    assert s.settings_path == tmp_path / "settings.json"


def test_load_or_default_with_existing_file(tmp_path: Path):
    seed = Settings(
        export_folder=str(tmp_path / "exports"),
        settings_path=tmp_path / "settings.json",
    )
    seed.save()
    s = load_or_default(tmp_path / "settings.json")
    assert s.export_folder == str(tmp_path / "exports")


# --- resolution & fallback --------------------------------------------------


def test_resolved_export_folder_uses_saved_path_when_exists(tmp_path: Path):
    real = tmp_path / "exports"
    real.mkdir()
    s = Settings(export_folder=str(real))
    assert s.resolved_export_folder() == real


def test_resolved_export_folder_falls_back_when_missing(tmp_path: Path):
    s = Settings(export_folder=str(tmp_path / "no-such"))
    assert s.resolved_export_folder() == default_export_folder()


def test_resolved_export_folder_falls_back_when_empty():
    s = Settings(export_folder="")
    assert s.resolved_export_folder() == default_export_folder()


def test_resolved_with_flag_signals_default(tmp_path: Path):
    s = Settings(export_folder=str(tmp_path / "no-such"))
    path, default_used = s.export_folder_resolved_with_fallback_flag()
    assert default_used is True
    assert path == default_export_folder()


def test_resolved_with_flag_signals_real_path(tmp_path: Path):
    real = tmp_path / "exports"
    real.mkdir()
    s = Settings(export_folder=str(real))
    path, default_used = s.export_folder_resolved_with_fallback_flag()
    assert default_used is False
    assert path == real


# --- update -----------------------------------------------------------------


def test_update_persists(tmp_path: Path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.save()
    s.update(export_folder=str(tmp_path / "new-exports"))
    reloaded = load(tmp_path / "settings.json")
    assert reloaded is not None
    assert reloaded.export_folder == str(tmp_path / "new-exports")


def test_update_unknown_field_raises(tmp_path: Path):
    s = Settings(settings_path=tmp_path / "settings.json")
    with pytest.raises(OpenReposeSettingsError):
        s.update(bogus="x")


# --- subdir templates -------------------------------------------------------


def test_render_subdir_default_single():
    assert render_subdir("{avatar}", avatar="aeri") == "aeri"


def test_render_subdir_default_batch():
    assert (
        render_subdir(
            "{avatar}/{run_tag}", avatar="aeri", run_tag="20260503T120000Z"
        )
        == "aeri/20260503T120000Z"
    )


def test_render_subdir_unknown_placeholder_raises():
    with pytest.raises(OpenReposeSettingsError):
        render_subdir("{avatar}/{unknown}", avatar="aeri")


# --- WP-I2-002: schema_version 2 + library config ---------------------------


def test_schema_version_is_two():
    assert SETTINGS_SCHEMA_VERSION == 2


def test_default_library_fields_empty():
    s = Settings()
    assert s.library_db_url == ""
    assert s.library_root == ""
    assert s.operator_slug == ""


def test_to_dict_emits_library_fields(tmp_path: Path):
    s = Settings(
        library_db_url="postgresql://u:p@h/db",
        library_root=str(tmp_path / "lib"),
        operator_slug="ilja",
        settings_path=tmp_path / "settings.json",
    )
    d = s.to_dict()
    assert d["schema_version"] == 2
    assert d["library_db_url"] == "postgresql://u:p@h/db"
    assert d["library_root"] == str(tmp_path / "lib")
    assert d["operator_slug"] == "ilja"


def test_save_load_roundtrip_includes_library_fields(tmp_path: Path):
    s = Settings(
        export_folder=str(tmp_path / "exports"),
        library_db_url="postgresql://u:p@localhost:5432/openrepose",
        library_root=str(tmp_path / "lib"),
        operator_slug="ilja",
        settings_path=tmp_path / "settings.json",
    )
    s.save()
    loaded = load(tmp_path / "settings.json")
    assert loaded is not None
    assert loaded.schema_version == 2
    assert loaded.library_db_url == "postgresql://u:p@localhost:5432/openrepose"
    assert loaded.library_root == str(tmp_path / "lib")
    assert loaded.operator_slug == "ilja"


def test_update_persists_library_fields(tmp_path: Path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.save()
    s.update(
        library_db_url="postgresql://x:y@h/db",
        library_root=str(tmp_path / "lib2"),
        operator_slug="bob",
    )
    reloaded = load(tmp_path / "settings.json")
    assert reloaded is not None
    assert reloaded.library_db_url == "postgresql://x:y@h/db"
    assert reloaded.library_root == str(tmp_path / "lib2")
    assert reloaded.operator_slug == "bob"


def test_v1_settings_migrates_to_v2_in_place(tmp_path: Path):
    """A schema_version=1 settings.json must load cleanly (defaults
    patched in) and be re-saved at schema_version=2."""
    p = tmp_path / "settings.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "export_folder": str(tmp_path / "exports"),
                "single_export_subdir_template": "{avatar}",
                "batch_export_subdir_template": "{avatar}/{run_tag}",
                "last_portrait_dir": str(tmp_path / "portraits"),
                "canvas_border_color": "#abcdef",
            }
        ),
        encoding="utf-8",
    )

    loaded = load(p)
    assert loaded is not None
    # Existing v1 fields preserved.
    assert loaded.export_folder == str(tmp_path / "exports")
    assert loaded.last_portrait_dir == str(tmp_path / "portraits")
    assert loaded.canvas_border_color == "#abcdef"
    # New v2 fields default-patched.
    assert loaded.library_db_url == ""
    assert loaded.library_root == ""
    assert loaded.operator_slug == ""
    # Loaded record is at schema_version 2.
    assert loaded.schema_version == 2

    # File on disk is now schema_version 2 (re-emitted by load()).
    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert on_disk["schema_version"] == 2
    assert on_disk["library_db_url"] == ""
    assert on_disk["library_root"] == ""
    assert on_disk["operator_slug"] == ""


def test_v1_to_v2_migration_does_not_clobber_unrelated_fields(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "export_folder": "/some/path",
                "canvas_border_color": "#112233",
            }
        ),
        encoding="utf-8",
    )
    load(p)
    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert on_disk["export_folder"] == "/some/path"
    assert on_disk["canvas_border_color"] == "#112233"


def test_resolved_library_root_uses_explicit_when_set(tmp_path: Path):
    s = Settings(library_root=str(tmp_path / "explicit"))
    assert s.resolved_library_root() == tmp_path / "explicit"


def test_resolved_library_root_falls_back_to_export_subdir(tmp_path: Path):
    real_export = tmp_path / "exports"
    real_export.mkdir()
    s = Settings(export_folder=str(real_export))
    assert (
        s.resolved_library_root() == real_export / DEFAULT_LIBRARY_DIR_NAME
    )


def test_resolved_library_root_falls_back_to_default_export(tmp_path: Path):
    s = Settings()
    expected = default_export_folder() / DEFAULT_LIBRARY_DIR_NAME
    assert s.resolved_library_root() == expected


def test_effective_operator_slug_uses_explicit_when_set():
    s = Settings(operator_slug="custom")
    assert s.effective_operator_slug() == "custom"


def test_effective_operator_slug_falls_back_to_os_user():
    s = Settings()
    fallback = _default_operator_slug()
    # OS lookup may be empty in odd sandboxes; the slug must equal whatever
    # the helper returns (deterministic per machine).
    assert s.effective_operator_slug() == fallback


def test_redact_db_url_masks_password():
    redacted = _redact_db_url("postgresql://user:secret@localhost:5432/db")
    assert redacted == "postgresql://user:***@localhost:5432/db"


def test_redact_db_url_with_no_password_unchanged():
    assert _redact_db_url("postgresql://localhost/db") == "postgresql://localhost/db"


def test_redact_db_url_empty_input_returns_empty():
    assert _redact_db_url("") == ""


def test_redacted_db_url_method():
    s = Settings(library_db_url="postgresql://u:p@h:5432/db")
    assert s.redacted_db_url() == "postgresql://u:***@h:5432/db"


def test_redacted_db_url_when_unset():
    s = Settings()
    assert s.redacted_db_url() == ""


def test_update_unknown_library_field_raises(tmp_path: Path):
    s = Settings(settings_path=tmp_path / "settings.json")
    s.save()
    with pytest.raises(OpenReposeSettingsError):
        s.update(library_db_password="x")  # not a real field
