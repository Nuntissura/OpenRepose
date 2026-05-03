"""Tests that export commands honor the operator-configured folder.

Spec: WP-I1-027 — `_h_export_single` / `_h_export_batch` use
`app.settings.resolved_export_folder() / <subdir-template>` when no
`out_dir` is supplied; explicit `out_dir` still wins.
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
    )


def _import_aeri(app: App, aeri_master: Path) -> None:
    r = app.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    assert r.status == "ok", r.payload


def test_export_single_uses_settings_export_folder(
    app: App, aeri_master: Path, tmp_path: Path
):
    """When export_folder is set in settings, single export lands under it."""
    target_root = tmp_path / "operator-exports"
    target_root.mkdir()
    app.settings.update(export_folder=str(target_root))
    _import_aeri(app, aeri_master)

    r = app.handle_command({"command": "export_single"})
    assert r.status == "ok", r.payload
    out_path = Path(r.payload["files"][0])
    # Falls under operator's chosen root.
    assert target_root in out_path.parents
    assert "aeri" in str(out_path)


def test_export_batch_uses_settings_export_folder(
    app: App, aeri_master: Path, tmp_path: Path
):
    target_root = tmp_path / "operator-exports"
    target_root.mkdir()
    app.settings.update(export_folder=str(target_root))
    _import_aeri(app, aeri_master)

    r = app.handle_command({"command": "export_batch"})
    assert r.status == "ok", r.payload
    files = [Path(f) for f in r.payload["files"]]
    for f in files:
        assert target_root in f.parents


def test_explicit_out_dir_overrides_settings(
    app: App, aeri_master: Path, tmp_path: Path
):
    """A command with `out_dir` still wins over settings.export_folder
    (regression for the existing API)."""
    target_root = tmp_path / "operator-exports"
    target_root.mkdir()
    app.settings.update(export_folder=str(target_root))
    _import_aeri(app, aeri_master)

    explicit = tmp_path / "explicit-out"
    r = app.handle_command(
        {"command": "export_single", "out_dir": str(explicit)}
    )
    assert r.status == "ok", r.payload
    out_path = Path(r.payload["files"][0])
    assert explicit in out_path.parents
    # Should NOT have landed under settings.export_folder.
    assert target_root not in out_path.parents


def test_export_falls_back_to_default_when_settings_path_missing(
    app: App, aeri_master: Path, tmp_path: Path
):
    """settings.export_folder pointing at a non-existent path → resolution
    falls back to ~/Desktop/openrepose-output/ (or ~/openrepose-output/ if
    Desktop missing). We don't actually want to write under the operator's
    real Desktop in a test, so we verify by checking the resolved path
    metadata via dump_settings."""
    app.settings.update(export_folder=str(tmp_path / "definitely-not-here"))
    r = app.handle_command({"command": "dump_settings"})
    assert r.status == "ok"
    assert r.payload["default_used"] is True
    # Resolved path is NOT the operator's missing path.
    assert "definitely-not-here" not in r.payload["resolved_export_folder"]


def test_dump_settings_returns_effective_state(app: App, tmp_path: Path):
    target_root = tmp_path / "exports"
    target_root.mkdir()
    app.settings.update(
        export_folder=str(target_root),
        single_export_subdir_template="{avatar}/single",
    )
    r = app.handle_command({"command": "dump_settings"})
    assert r.status == "ok"
    assert r.payload["present"] is True
    assert r.payload["default_used"] is False
    assert r.payload["resolved_export_folder"] == str(target_root)
    assert r.payload["settings"]["export_folder"] == str(target_root)
    assert (
        r.payload["settings"]["single_export_subdir_template"]
        == "{avatar}/single"
    )


def test_dump_settings_redacts_library_db_password(app: App, tmp_path: Path):
    """WP-I2-002: dump_settings is exposed to LLM agents; the
    library_db_url password component must be masked so callers cannot
    exfiltrate it."""
    app.settings.update(library_db_url="postgresql://op:secret@localhost:5432/db")
    r = app.handle_command({"command": "dump_settings"})
    assert r.status == "ok"
    assert r.payload["settings"]["library_db_url"] == (
        "postgresql://op:***@localhost:5432/db"
    )


def test_dump_settings_includes_library_resolved_fields(
    app: App, tmp_path: Path
):
    """WP-I2-002: dump_settings exposes resolved_library_root and
    effective_operator_slug so an LLM agent can introspect the library
    configuration without reading the disk file."""
    target_root = tmp_path / "exports"
    target_root.mkdir()
    app.settings.update(
        export_folder=str(target_root),
        library_root="",  # explicitly blank → derived from export folder
        operator_slug="ilja",
    )
    r = app.handle_command({"command": "dump_settings"})
    assert r.status == "ok"
    assert r.payload["resolved_library_root"] == str(target_root / "library")
    assert r.payload["effective_operator_slug"] == "ilja"


def test_dump_settings_omits_redaction_when_url_unset(app: App):
    """An empty library_db_url stays empty (not the literal '***')."""
    r = app.handle_command({"command": "dump_settings"})
    assert r.status == "ok"
    assert r.payload["settings"]["library_db_url"] == ""


def test_state_json_has_settings_block(app: App, tmp_path: Path):
    target_root = tmp_path / "exports"
    target_root.mkdir()
    app.settings.update(export_folder=str(target_root))
    # Manually refresh state.settings (the GUI does this in
    # _on_settings_changed; here we mirror it for the test).
    resolved, default_used = (
        app.settings.export_folder_resolved_with_fallback_flag()
    )
    app.state.set_settings_status(
        export_folder=str(resolved),
        default_used=default_used,
        settings_path=str(app.settings.settings_path),
    )
    app.state.write()
    state = json.loads(app.state.state_path.read_text(encoding="utf-8"))
    assert "settings" in state
    assert state["settings"]["export_folder"] == str(target_root)
    assert state["settings"]["default_used"] is False
    assert state["settings"]["settings_path"].endswith("settings.json")


def test_settings_persistence_survives_app_restart(
    aeri_master: Path, tmp_path: Path
):
    """Write settings via App #1; instantiate App #2 with the same
    settings_path; export uses the saved folder."""
    settings_p = tmp_path / "settings.json"
    target = tmp_path / "persistent-exports"
    target.mkdir()

    app1 = App(
        outputs_root=tmp_path / "outputs1",
        log_dir=tmp_path / "logs1",
        state_path=tmp_path / "state1.json",
        settings_path=settings_p,
    )
    app1.settings.update(export_folder=str(target))
    app1.stop()

    app2 = App(
        outputs_root=tmp_path / "outputs2",
        log_dir=tmp_path / "logs2",
        state_path=tmp_path / "state2.json",
        settings_path=settings_p,
    )
    assert app2.settings.export_folder == str(target)

    app2.handle_command(
        {
            "command": "import_portrait",
            "path": str(aeri_master),
            "avatar_slug": "aeri",
        }
    )
    r = app2.handle_command({"command": "export_single"})
    out_path = Path(r.payload["files"][0])
    assert target in out_path.parents
    app2.stop()
