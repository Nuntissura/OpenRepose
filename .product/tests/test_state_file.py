"""AppState atomic-write and retention tests."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from openrepose.state import RETENTION_LIMIT, AppState


def test_state_default_shape(tmp_path: Path) -> None:
    s = AppState(state_path=tmp_path / "state.json")
    s.write()
    obj = json.loads(s.state_path.read_text(encoding="utf-8"))
    assert obj["version"] == "0.1"
    stance = obj["adult_production_boundary"]
    assert stance["acknowledgement_required"] is True
    assert "adult porn production tool" in stance["stance"]
    assert stance["not_a_compliance_record"] is True
    assert stance["not_command_blocking"] is True
    assert "started_at" in obj
    assert obj["rig"]["status"] == "none"
    assert obj["yaw"]["axis"] == "y"
    assert obj["exports"] == []
    assert obj["snapshots"] == []
    assert obj["errors"] == []


def test_state_write_atomic_no_partial(tmp_path: Path) -> None:
    """Hammer write() in one thread; read in another. Reader never sees malformed JSON."""
    s = AppState(state_path=tmp_path / "state.json")
    s.write()
    stop = threading.Event()
    errors: list[str] = []

    def writer() -> None:
        for i in range(100):
            s.add_export(type_="single", out_dir=f"dir{i}", files=[f"f{i}.json"])
            s.write()
            if stop.is_set():
                return

    def reader() -> None:
        while not stop.is_set():
            try:
                json.loads(s.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:  # pragma: no cover
                errors.append(str(e))

    w = threading.Thread(target=writer)
    r = threading.Thread(target=reader)
    r.start()
    w.start()
    w.join(timeout=10)
    stop.set()
    r.join(timeout=2)
    assert not errors, errors


def test_state_export_retention_capped(tmp_path: Path) -> None:
    s = AppState(state_path=tmp_path / "state.json")
    for i in range(RETENTION_LIMIT + 50):
        s.add_export(type_="single", out_dir=f"d{i}", files=[f"f{i}.json"])
    assert len(s.exports) == RETENTION_LIMIT


def test_state_snapshot_retention_capped(tmp_path: Path) -> None:
    s = AppState(state_path=tmp_path / "state.json")
    for i in range(RETENTION_LIMIT + 50):
        s.add_snapshot(target=f"t{i}", out_path=f"o{i}.png")
    assert len(s.snapshots) == RETENTION_LIMIT


def test_state_errors_retention_capped(tmp_path: Path) -> None:
    s = AppState(state_path=tmp_path / "state.json")
    for i in range(RETENTION_LIMIT + 50):
        s.add_error(level="ERR", op="rig.fit", reason=f"r{i}")
    assert len(s.errors) == RETENTION_LIMIT


def test_state_command_lifecycle(tmp_path: Path) -> None:
    s = AppState(state_path=tmp_path / "state.json")
    s.begin_command("import_portrait")
    assert s.last_command["status"] == "in_progress"
    assert s.last_command["received_at"] is not None
    assert s.last_command["completed_at"] is None
    s.end_command(status="ok")
    assert s.last_command["status"] == "ok"
    assert s.last_command["completed_at"] is not None
