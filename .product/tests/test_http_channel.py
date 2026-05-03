"""HTTP localhost channel tests."""

from __future__ import annotations

import json
import socket
import time
import urllib.request
from pathlib import Path

import pytest

from openrepose.app import App


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def http_app(tmp_path: Path) -> App:
    export_root = tmp_path / "exports"
    export_root.mkdir()
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"schema_version": 2, "export_folder": str(export_root)}),
        encoding="utf-8",
    )
    app = App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=settings_path,
    )
    port = _free_port()
    app._test_port = port  # type: ignore[attr-defined]
    app.start_http(port=port)
    time.sleep(0.1)  # let server bind
    yield app
    app.stop()


def _post(app: App, body: dict) -> tuple[int, dict]:
    port = app._test_port  # type: ignore[attr-defined]
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/command",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get(app: App, path: str) -> tuple[int, str]:
    port = app._test_port  # type: ignore[attr-defined]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as r:
        return r.status, r.read().decode("utf-8")


def test_post_command_returns_200_for_unknown(http_app: App) -> None:
    code, payload = _post(http_app, {"command": "nonexistent"})
    assert code == 400
    assert payload["status"] == "error"
    assert payload["adult_production_boundary"]["acknowledgement_required"] is True


def test_post_set_yaw_bin(http_app: App) -> None:
    code, payload = _post(http_app, {"command": "set_yaw_bin", "bin": "her-left 30"})
    assert code == 200
    assert payload["status"] == "ok"
    assert payload["payload"]["bin"] == "her-left 30"


def test_get_state(http_app: App) -> None:
    code, body = _get(http_app, "/state")
    assert code == 200
    state = json.loads(body)
    assert state["version"] == "0.1"
    assert state["adult_production_boundary"]["acknowledgement_required"] is True


def test_get_log(http_app: App) -> None:
    _post(http_app, {"command": "set_yaw_bin", "bin": "her-left 30"})
    code, body = _get(http_app, "/log?lines=10")
    assert code == 200
    assert "yaw.set_bin" in body or "cmd.completed" in body


def test_invalid_json_rejected(http_app: App) -> None:
    port = http_app._test_port  # type: ignore[attr-defined]
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/command",
        data=b"this is not json",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            assert r.status == 400
    except urllib.error.HTTPError as e:
        assert e.code == 400
        payload = json.loads(e.read())
        assert payload["adult_production_boundary"]["acknowledgement_required"] is True


def test_post_full_pipeline(http_app: App, aeri_master: Path) -> None:
    code, payload = _post(
        http_app,
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"},
    )
    assert code == 200
    assert payload["status"] == "ok"

    code, payload = _post(http_app, {"command": "set_yaw_bin", "bin": "her-right 45"})
    assert code == 200

    code, payload = _post(http_app, {"command": "export_single"})
    assert code == 200
    files = payload["payload"]["files"]
    # WP-I1-030: export_single returns both .json and .png paths.
    assert len(files) == 2
    for f in files:
        assert Path(f).exists()
