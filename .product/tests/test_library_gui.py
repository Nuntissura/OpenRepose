"""Library tab GUI smoke tests (WP-I2-006).

pytest-qt + offscreen Qt platform. The pane wires every operator action
to a dispatcher command, so we substitute a tiny stand-in `App` that
records the command stream and returns canned payloads. End-to-end
against a real Postgres is covered by the dispatcher tests in
WP-I2-004.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from openrepose.commands import CommandResult
from openrepose.gui.library import LibraryPane
from openrepose.state import AppState


@dataclass
class _StubLog:
    def info(self, *a, **kw): pass
    def ok(self, *a, **kw): pass
    def warn(self, *a, **kw): pass
    def err(self, *a, **kw): pass
    def dbg(self, *a, **kw): pass


class _StubApp:
    """Records dispatched commands; replays canned responses keyed on
    command name. `state.library` mirrors the real shape so the pane's
    last-search lookup works."""

    def __init__(self, *, settings_dir: Path) -> None:
        self.calls: list[dict[str, Any]] = []
        self._responses: dict[str, list[dict[str, Any]]] = {}
        self.state = AppState(state_path=settings_dir / "state.json")
        self.log = _StubLog()
        self.settings = MagicMock()
        self.settings.effective_operator_slug.return_value = "test-op"
        self.settings.resolved_library_root.return_value = settings_dir / "library"

    def queue(self, command: str, payload: dict[str, Any], *, status: str = "ok") -> None:
        bucket = self._responses.setdefault(command, [])
        bucket.append({"status": status, "payload": payload})

    def handle_command(self, cmd: dict[str, Any]) -> CommandResult:
        self.calls.append(dict(cmd))
        name = cmd.get("command", "")
        bucket = self._responses.get(name) or []
        if bucket:
            entry = bucket.pop(0)
            return CommandResult(command=name, status=entry["status"], payload=entry["payload"])
        # Default empty ok payload so the pane doesn't crash.
        return CommandResult(command=name, status="ok", payload={})


@pytest.fixture
def stub_app(tmp_path: Path) -> _StubApp:
    return _StubApp(settings_dir=tmp_path)


def test_pane_constructs_and_starts_idle(qtbot, stub_app):
    pane = LibraryPane(stub_app)
    qtbot.addWidget(pane)
    assert pane._search_edit.placeholderText().startswith("Search:")
    assert pane._list.count() == 0
    assert pane._detail._title_label.text() == "(no entry selected)"


def test_search_dispatches_library_search_and_populates_list(qtbot, stub_app):
    stub_app.queue(
        "library_search",
        {
            "query": "intimate",
            "count": 2,
            "results": [
                {
                    "entry_id": "11111111-1111-1111-1111-111111111111",
                    "title": "scene one",
                    "avatar_slug": "aeri",
                    "yaw_bin": "her-right-30",
                    "rank": 0.9,
                    "top_tags": ["mood:intimate", "lighting:lowkey"],
                },
                {
                    "entry_id": "22222222-2222-2222-2222-222222222222",
                    "title": "scene two",
                    "avatar_slug": "aeri",
                    "yaw_bin": "0",
                    "rank": 0.6,
                    "top_tags": [],
                },
            ],
        },
    )
    pane = LibraryPane(stub_app)
    qtbot.addWidget(pane)
    pane._search_edit.setText("intimate")
    pane._on_search()

    assert any(c["command"] == "library_search" for c in stub_app.calls)
    assert pane._list.count() == 2
    assert "scene one" in pane._list.item(0).text()
    assert "Library: 2 results" in pane._status_label.text()


def test_empty_search_query_does_not_dispatch(qtbot, stub_app):
    pane = LibraryPane(stub_app)
    qtbot.addWidget(pane)
    pane._search_edit.setText("   ")
    pane._on_search()
    assert not any(c["command"] == "library_search" for c in stub_app.calls)
    assert "type a search query" in pane._status_label.text()


def test_select_entry_dispatches_get_and_populates_detail(qtbot, stub_app):
    stub_app.queue(
        "library_search",
        {
            "query": "x",
            "count": 1,
            "results": [
                {
                    "entry_id": "33333333-3333-3333-3333-333333333333",
                    "title": "the pick",
                    "avatar_slug": "aeri",
                    "yaw_bin": "0",
                    "rank": 0.8,
                    "top_tags": ["pose:0"],
                }
            ],
        },
    )
    stub_app.queue(
        "get_library_entry",
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "title": "the pick",
            "avatar_slug": "aeri",
            "yaw_bin": "0",
            "tags": ["pose:0", "auto:model:flux"],
            "prompts": [{"positive": "p", "negative": "n", "created_at": None, "created_by": None}],
            "story_beats": [],
            "notes": [],
            "comfyui_workflow": {"nodes": []},
            "metadata": {"sampler": "euler"},
            "openpose_png_path": None,
            "generated_image_path": None,
            "portrait_path": None,
            "locked_by": None,
        },
    )
    pane = LibraryPane(stub_app)
    qtbot.addWidget(pane)
    pane._search_edit.setText("x")
    pane._on_search()
    pane._list.setCurrentRow(0)  # triggers _on_select via signal

    cmds = [c["command"] for c in stub_app.calls]
    assert "get_library_entry" in cmds
    assert "the pick" in pane._detail._title_label.text()
    # Tags mirror onto the chips label.
    assert "pose:0" in pane._detail._tags_tab._chips.text()


def test_locked_entry_renders_grey_and_tooltip(qtbot, stub_app):
    stub_app.queue(
        "library_search",
        {
            "query": "x",
            "count": 1,
            "results": [
                {
                    "entry_id": "44444444-4444-4444-4444-444444444444",
                    "title": "held",
                    "avatar_slug": "aeri",
                    "yaw_bin": "0",
                    "rank": 0.5,
                    "top_tags": [],
                    "locked_by": "other-op",
                }
            ],
        },
    )
    pane = LibraryPane(stub_app)
    qtbot.addWidget(pane)
    pane._search_edit.setText("x")
    pane._on_search()
    item = pane._list.item(0)
    assert "Locked by other-op" in item.toolTip()


def test_tags_changed_dispatches_set_library_tags(qtbot, stub_app):
    pane = LibraryPane(stub_app)
    qtbot.addWidget(pane)
    pane._current_entry = {"id": "55555555-5555-5555-5555-555555555555"}
    stub_app.queue(
        "set_library_tags",
        {"entry_id": "55555555-5555-5555-5555-555555555555", "tags": ["a", "b"]},
    )
    pane._on_tags_changed(["a", "b"], False)
    last = stub_app.calls[-1]
    assert last["command"] == "set_library_tags"
    assert last["replace"] is False
    assert last["tags"] == ["a", "b"]


def test_delete_dispatches_delete_command(qtbot, stub_app):
    pane = LibraryPane(stub_app)
    qtbot.addWidget(pane)
    pane._current_entry = {"id": "66666666-6666-6666-6666-666666666666"}
    stub_app.queue("delete_library_entry", {"entry_id": "x", "deleted": True})
    pane._on_delete()
    assert any(c["command"] == "delete_library_entry" for c in stub_app.calls)


def test_main_window_registers_library_tab(qtbot, tmp_path: Path):
    """End-to-end: real App + real MainWindow has a Library tab. Verifies
    the wiring in `_build_central_widget`. No DB required: the pane works
    in the disabled-library state (pool unavailable returns errors but
    the tab still renders)."""
    from openrepose.app import App
    from openrepose.gui.main_window import MainWindow

    app = App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
    )
    try:
        win = MainWindow(app)
        qtbot.addWidget(win)
        tab_titles = [win._tabs.tabText(i) for i in range(win._tabs.count())]
        assert "Library" in tab_titles
        assert isinstance(win._library, LibraryPane)
    finally:
        app.stop()
