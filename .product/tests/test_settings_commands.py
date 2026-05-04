"""Tests for the set_settings / clear_settings dispatcher commands
(WP-I1-003).

dump_settings already exists and is covered indirectly by other suites;
these tests target the two new write commands and the round-trip
behaviour through the App + Settings + state.json surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openrepose.app import App


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
        run_migrations=False,
    )


# --- set_settings ----------------------------------------------------------


def test_set_settings_patches_export_folder(app: App, tmp_path: Path):
    target = tmp_path / "operator-exports"
    target.mkdir()

    r = app.handle_command(
        {"command": "set_settings", "fields": {"export_folder": str(target)}}
    )

    assert r.status == "ok", r.payload
    assert r.payload["updated_fields"] == ["export_folder"]
    assert r.payload["settings"]["export_folder"] == str(target)
    # On-disk file reflects the change.
    on_disk = json.loads(Path(app.settings.settings_path).read_text(encoding="utf-8"))
    assert on_disk["export_folder"] == str(target)
    # state.json reflects the resolved folder + default_used flag.
    state_doc = json.loads(app.state.state_path.read_text(encoding="utf-8"))
    assert state_doc["settings"]["export_folder"] == str(target)
    assert state_doc["settings"]["default_used"] is False


def test_set_settings_patches_multiple_fields(app: App, tmp_path: Path):
    r = app.handle_command(
        {
            "command": "set_settings",
            "fields": {
                "single_export_subdir_template": "{avatar}/single",
                "batch_export_subdir_template": "{avatar}/batch/{run_tag}",
                "operator_slug": "ilja",
            },
        }
    )

    assert r.status == "ok", r.payload
    assert sorted(r.payload["updated_fields"]) == [
        "batch_export_subdir_template",
        "operator_slug",
        "single_export_subdir_template",
    ]
    assert app.settings.single_export_subdir_template == "{avatar}/single"
    assert app.settings.batch_export_subdir_template == "{avatar}/batch/{run_tag}"
    assert app.settings.operator_slug == "ilja"


def test_set_settings_redacts_library_db_url(app: App):
    r = app.handle_command(
        {
            "command": "set_settings",
            "fields": {
                "library_db_url": "postgresql://user:s3cret@localhost:5432/db",
            },
        }
    )

    assert r.status == "ok", r.payload
    # In the response payload the password is masked.
    assert r.payload["settings"]["library_db_url"] == (
        "postgresql://user:***@localhost:5432/db"
    )
    # On disk the unredacted value is preserved (App relies on it at startup).
    on_disk = json.loads(Path(app.settings.settings_path).read_text(encoding="utf-8"))
    assert on_disk["library_db_url"] == "postgresql://user:s3cret@localhost:5432/db"


def test_set_settings_unknown_field_rejected_and_disk_untouched(
    app: App, tmp_path: Path
):
    target = tmp_path / "operator-exports"
    target.mkdir()
    # Seed a known-good value so we can prove the rejection didn't clobber it.
    app.settings.update(export_folder=str(target))
    on_disk_before = Path(app.settings.settings_path).read_text(encoding="utf-8")

    r = app.handle_command(
        {
            "command": "set_settings",
            "fields": {"not_a_real_field": "x"},
        }
    )

    assert r.status == "error", r.payload
    assert r.payload["type"] == "OpenReposeSettingsError"
    on_disk_after = Path(app.settings.settings_path).read_text(encoding="utf-8")
    assert on_disk_before == on_disk_after


def test_set_settings_empty_fields_rejected(app: App):
    r = app.handle_command({"command": "set_settings", "fields": {}})
    assert r.status == "error", r.payload
    assert r.payload["type"] == "OpenReposeCommandError"


def test_set_settings_missing_fields_rejected(app: App):
    r = app.handle_command({"command": "set_settings"})
    assert r.status == "error", r.payload
    assert r.payload["type"] == "OpenReposeCommandError"


def test_set_settings_non_dict_fields_rejected(app: App):
    r = app.handle_command({"command": "set_settings", "fields": ["a", "b"]})
    assert r.status == "error", r.payload
    assert r.payload["type"] == "OpenReposeCommandError"


# --- clear_settings --------------------------------------------------------


def test_clear_settings_resets_to_defaults(app: App, tmp_path: Path):
    target = tmp_path / "operator-exports"
    target.mkdir()
    app.settings.update(
        export_folder=str(target),
        single_export_subdir_template="{avatar}/single-custom",
        batch_export_subdir_template="{avatar}/batch-custom/{run_tag}",
        operator_slug="ilja",
        library_db_url="postgresql://u:p@h/db",
        library_root=str(tmp_path / "lib"),
        canvas_border_color="#ff0000",
        last_portrait_dir=str(tmp_path / "portraits"),
    )

    r = app.handle_command({"command": "clear_settings"})

    assert r.status == "ok", r.payload
    assert r.payload["cleared"] is True
    # Live instance flipped back to defaults.
    assert app.settings.export_folder == ""
    assert app.settings.single_export_subdir_template == "{avatar}"
    assert app.settings.batch_export_subdir_template == "{avatar}/{run_tag}"
    assert app.settings.operator_slug == ""
    assert app.settings.library_db_url == ""
    assert app.settings.library_root == ""
    assert app.settings.canvas_border_color == "#ffffff"
    assert app.settings.last_portrait_dir == ""
    # On disk reflects the reset.
    on_disk = json.loads(Path(app.settings.settings_path).read_text(encoding="utf-8"))
    assert on_disk["export_folder"] == ""
    assert on_disk["library_db_url"] == ""
    assert on_disk["operator_slug"] == ""
    # schema_version preserved.
    assert on_disk["schema_version"] == 2


def test_clear_settings_then_dump_returns_defaults(app: App):
    app.settings.update(operator_slug="ilja", library_db_url="postgresql://u:p@h/db")
    app.handle_command({"command": "clear_settings"})

    r = app.handle_command({"command": "dump_settings"})
    assert r.status == "ok", r.payload
    assert r.payload["settings"]["operator_slug"] == ""
    assert r.payload["settings"]["library_db_url"] == ""


def test_clear_settings_survives_app_restart(app: App, tmp_path: Path):
    """Persistence proof: clear_settings, then construct a second App over
    the same on-disk paths and assert it sees the reset."""
    app.settings.update(
        operator_slug="ilja",
        library_db_url="postgresql://u:p@h/db",
        last_portrait_dir=str(tmp_path / "portraits"),
    )
    app.handle_command({"command": "clear_settings"})
    settings_path = Path(app.settings.settings_path)
    state_path = app.state.state_path
    outputs_root = app.outputs_root
    log_dir = Path(app.log.log_dir) if hasattr(app.log, "log_dir") else (tmp_path / "logs")

    app2 = App(
        outputs_root=outputs_root,
        log_dir=log_dir,
        state_path=state_path,
        settings_path=settings_path,
        run_migrations=False,
    )

    assert app2.settings.operator_slug == ""
    assert app2.settings.library_db_url == ""
    assert app2.settings.last_portrait_dir == ""


# --- adult_production_boundary surface -------------------------------------


def test_set_settings_response_carries_stance(app: App, tmp_path: Path):
    target = tmp_path / "exports"
    target.mkdir()
    r = app.handle_command(
        {"command": "set_settings", "fields": {"export_folder": str(target)}}
    )
    envelope = r.to_dict()
    assert envelope["adult_production_boundary"]["acknowledgement_required"] is True


def test_clear_settings_response_carries_stance(app: App):
    r = app.handle_command({"command": "clear_settings"})
    envelope = r.to_dict()
    assert envelope["adult_production_boundary"]["acknowledgement_required"] is True
