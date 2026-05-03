"""File-watch inbox channel tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openrepose.app import App


@pytest.fixture
def inbox_app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
    )


def test_inbox_processes_command_file(inbox_app: App) -> None:
    # Drop a command file directly; use process_once for deterministic test.
    inbox_dir = inbox_app.outputs_root / ".runtime" / "inbox"
    processed_dir = inbox_app.outputs_root / ".runtime" / "processed"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    (inbox_dir / "cmd1.json").write_text(
        json.dumps({"command": "set_yaw_bin", "bin": "her-left 30"}),
        encoding="utf-8",
    )

    from openrepose.channels.inbox import InboxChannel

    channel = InboxChannel(
        inbox_app.dispatcher,
        inbox_app.log,
        inbox_dir=inbox_dir,
        processed_dir=processed_dir,
    )
    n = channel.process_once()
    assert n == 1

    # Original file gone, processed file present.
    assert not (inbox_dir / "cmd1.json").exists()
    matches = list(processed_dir.glob("cmd1.*.json"))
    assert len(matches) == 1
    wrapper = json.loads(matches[0].read_text(encoding="utf-8"))
    assert wrapper["result"]["status"] == "ok"
    assert wrapper["result"]["adult_production_boundary"]["acknowledgement_required"] is True
    assert wrapper["result"]["payload"]["bin"] == "her-left 30"


def test_inbox_processes_in_mtime_order(inbox_app: App, tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    processed_dir = tmp_path / "processed"
    inbox_dir.mkdir()
    processed_dir.mkdir()
    # Create three files with explicit mtime ordering.
    import os

    paths = []
    for i, label in enumerate(["her-left 15", "her-left 30", "her-left 45"]):
        p = inbox_dir / f"c{i}.json"
        p.write_text(json.dumps({"command": "set_yaw_bin", "bin": label}), encoding="utf-8")
        os.utime(p, (1_000_000 + i, 1_000_000 + i))
        paths.append(p)

    from openrepose.channels.inbox import InboxChannel

    channel = InboxChannel(
        inbox_app.dispatcher,
        inbox_app.log,
        inbox_dir=inbox_dir,
        processed_dir=processed_dir,
    )
    channel.process_once()
    # After processing, state.yaw should reflect the LAST file processed.
    assert inbox_app.state.yaw["current_bin"] == "her-left 45"


def test_inbox_malformed_json_moved_to_err(inbox_app: App, tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    processed_dir = tmp_path / "processed"
    inbox_dir.mkdir()
    processed_dir.mkdir()
    (inbox_dir / "junk.json").write_text("this is not json", encoding="utf-8")

    from openrepose.channels.inbox import InboxChannel

    channel = InboxChannel(
        inbox_app.dispatcher,
        inbox_app.log,
        inbox_dir=inbox_dir,
        processed_dir=processed_dir,
    )
    channel.process_once()

    err_files = list(processed_dir.glob("junk.err.json"))
    assert len(err_files) == 1
    wrapper = json.loads(err_files[0].read_text(encoding="utf-8"))
    assert wrapper["result"]["status"] == "error"
    assert wrapper["result"]["adult_production_boundary"]["acknowledgement_required"] is True
    assert "JSONDecodeError" in wrapper["result"]["reason"] or "json" in wrapper["result"]["reason"].lower()
