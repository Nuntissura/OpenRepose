"""Tests for openrepose.settings.

Spec: `.gov/spec/openrepose_v0_1.md` Feature 1 / Options tab + CLI export
folder. WP-I1-027.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openrepose.settings import (
    DEFAULT_EXPORT_DIR_NAME,
    SETTINGS_SCHEMA_VERSION,
    OpenReposeSettingsError,
    Settings,
    default_export_folder,
    load,
    load_or_default,
    render_subdir,
    settings_path,
)


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
        settings_path=tmp_path / "settings.json",
    )
    s.save()
    loaded = load(tmp_path / "settings.json")
    assert loaded is not None
    assert loaded.export_folder == str(tmp_path / "exports")
    assert loaded.single_export_subdir_template == "{avatar}/single"
    assert loaded.batch_export_subdir_template == "{avatar}/{run_tag}"
    assert loaded.schema_version == SETTINGS_SCHEMA_VERSION


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


def test_load_wrong_schema_version_raises(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text(
        json.dumps({"schema_version": 999, "export_folder": ""}),
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
