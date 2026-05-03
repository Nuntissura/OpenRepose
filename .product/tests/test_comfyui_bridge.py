"""Tests for the ComfyUI bridge custom node (WP-I2-005).

Pure-helper tests run anywhere. The end-to-end path (workflow JSON →
build_register_payload → POST → register_library_entry handler →
library entry appears) is covered too: it uses a real ephemeral PG
through `App.handle_command` (no actual HTTP socket — we call the
dispatcher directly with the same payload the bridge would POST)."""

from __future__ import annotations

import base64
import json
import shutil
import sys
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

# The bridge folder lives under `.product/comfyui-bridge/` (a kebab-case
# path that is not importable as a normal Python package). Build a
# synthetic package `_orbridge_test` rooted at that folder so the
# `from .extract_metadata import ...` relative import inside
# openrepose_bridge.py resolves cleanly. The synthetic package mirrors
# what ComfyUI does at runtime when it loads the folder under whatever
# name the operator chose.
import importlib.util
import types

_BRIDGE_DIR = Path(__file__).resolve().parent.parent / "comfyui-bridge"


def _load_bridge_package():
    pkg_name = "_orbridge_test"
    if pkg_name in sys.modules:
        return sys.modules[pkg_name]
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [str(_BRIDGE_DIR)]  # makes relative imports work
    sys.modules[pkg_name] = pkg
    return pkg


def _import_bridge_module(name: str):
    _load_bridge_package()
    full = f"_orbridge_test.{name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(
        full,
        _BRIDGE_DIR / f"{name}.py",
        submodule_search_locations=[str(_BRIDGE_DIR)],
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


extract_metadata_mod = _import_bridge_module("extract_metadata")
bridge_mod = _import_bridge_module("openrepose_bridge")
extract_metadata = extract_metadata_mod.extract_metadata
extract_prompts = extract_metadata_mod.extract_prompts
build_register_payload = bridge_mod.build_register_payload
send_post = bridge_mod.send_post


# ---------------------------------------------------------------------------
# extract_metadata
# ---------------------------------------------------------------------------


def test_extract_metadata_pulls_model_sampler_lora():
    workflow = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "fluxDev_v2.safetensors"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "seed": 12345,
                "steps": 28,
                "cfg": 6.5,
            },
        },
        "3": {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "intimate.safetensors"},
        },
    }
    md = extract_metadata(workflow)
    assert md["model"] == "fluxDev_v2.safetensors"
    assert md["sampler"] == "dpmpp_2m"
    assert md["scheduler"] == "karras"
    assert md["seed"] == 12345
    assert md["steps"] == 28
    assert md["cfg"] == 6.5
    assert md["lora"] == ["intimate.safetensors"]
    assert "CheckpointLoaderSimple" in md["custom_node"]
    assert "KSampler" in md["custom_node"]
    assert "LoraLoader" in md["custom_node"]


def test_extract_metadata_handles_empty():
    assert extract_metadata({}) == {}
    assert extract_metadata(None) == {}


def test_extract_prompts_picks_first_two_clip_text_encodes():
    workflow = {
        "10": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a tasteful portrait"},
        },
        "11": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "blurry, low quality"},
        },
        "12": {"class_type": "VAEDecode", "inputs": {}},
    }
    prompts = extract_prompts(workflow)
    assert prompts["positive"] == "a tasteful portrait"
    assert prompts["negative"] == "blurry, low quality"


def test_extract_prompts_handles_missing():
    assert extract_prompts({}) == {"positive": "", "negative": ""}
    assert extract_prompts(None) == {"positive": "", "negative": ""}


# ---------------------------------------------------------------------------
# build_register_payload
# ---------------------------------------------------------------------------


def test_build_payload_shape_matches_command_schema(tmp_path: Path):
    img = tmp_path / "out.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n_real_png_bytes_")
    workflow = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "model.safetensors"},
        },
        "10": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "studio shot"},
        },
        "11": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "blurry"},
        },
    }
    payload = build_register_payload(
        avatar_slug="aeri",
        title="run-007",
        yaw_bin="her-right-30",
        tags=["mood:intimate", "lighting:lowkey"],
        image_path=str(img),
        workflow=workflow,
        openpose_json_path="poses/aeri_yaw_her-right-30.json",
        openpose_png_path="",
    )
    assert payload["command"] == "register_library_entry"
    assert payload["avatar_slug"] == "aeri"
    assert payload["title"] == "run-007"
    assert payload["yaw_bin"] == "her-right-30"
    assert payload["tags"] == ["mood:intimate", "lighting:lowkey"]
    assert payload["metadata"]["model"] == "model.safetensors"
    assert payload["prompts"]["positive"] == "studio shot"
    assert payload["prompts"]["negative"] == "blurry"
    # Image must be base64-encoded.
    decoded = base64.b64decode(payload["generated_image"])
    assert decoded.startswith(b"\x89PNG")
    # When supplied, openpose paths land verbatim; when blank they are
    # omitted (no empty-string keys).
    assert payload["openpose_json_path"] == "poses/aeri_yaw_her-right-30.json"
    assert "openpose_png_path" not in payload
    # Workflow stored verbatim.
    assert payload["comfyui_workflow"] == workflow


def test_build_payload_omits_image_on_unreadable_path():
    payload = build_register_payload(
        avatar_slug="aeri",
        title="",
        yaw_bin="",
        tags=[],
        image_path="C:/no/such/file/at/all.png",
        workflow={},
        openpose_json_path="",
        openpose_png_path="",
    )
    assert "generated_image" not in payload  # missing image is non-blocking


def test_build_payload_omits_yaw_bin_when_blank(tmp_path: Path):
    img = tmp_path / "x.png"
    img.write_bytes(b"PNGDATA")
    payload = build_register_payload(
        avatar_slug="aeri",
        title="",
        yaw_bin="",
        tags=[],
        image_path=str(img),
        workflow={},
        openpose_json_path="",
        openpose_png_path="",
    )
    assert "yaw_bin" not in payload


# ---------------------------------------------------------------------------
# send_post — patches urlopen
# ---------------------------------------------------------------------------


def test_send_post_returns_parsed_json():
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b'{"status":"ok","payload":{"entry_id":"abc"}}'

    with patch.object(bridge_mod.urllib.request, "urlopen", return_value=_Resp()):
        out = send_post("http://localhost:8765/command", {"command": "ping"})
    assert out["status"] == "ok"


def test_send_post_returns_raw_when_response_not_json():
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b"hello"

    with patch.object(bridge_mod.urllib.request, "urlopen", return_value=_Resp()):
        out = send_post("http://localhost:8765/command", {"command": "ping"})
    assert out == {"raw": "hello"}


def test_send_post_propagates_network_error():
    err = urllib.error.URLError("connection refused")
    with patch.object(bridge_mod.urllib.request, "urlopen", side_effect=err):
        with pytest.raises(urllib.error.URLError):
            send_post("http://localhost:8765/command", {"command": "ping"})


# ---------------------------------------------------------------------------
# End-to-end against ephemeral PG (skipped when no Postgres)
# ---------------------------------------------------------------------------

PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass

if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    bridge_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    bridge_pg = _factories.postgresql("bridge_pg_proc")
else:  # pragma: no cover
    @pytest.fixture
    def bridge_pg():
        pytest.skip("no Postgres")


@pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres / pytest-postgresql",
)
def test_bridge_payload_round_trips_through_dispatcher(bridge_pg, tmp_path: Path):
    """Build the exact dict the bridge would POST and feed it to
    `App.handle_command`. Verifies the contract holds end-to-end without
    actually opening a network socket."""
    from openrepose.app import App
    from openrepose.settings import Settings

    info = bridge_pg.info
    dsn = (
        f"host={info.host} port={info.port} user={info.user} "
        f"dbname={info.dbname}"
    )
    if getattr(info, "password", ""):
        dsn += f" password={info.password}"

    settings = Settings(
        library_db_url=dsn,
        library_root=str(tmp_path / "library"),
        operator_slug="bridge-test",
        settings_path=tmp_path / "settings.json",
    )
    settings.save()
    app = App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
        settings_path=tmp_path / "settings.json",
    )
    try:
        img = tmp_path / "out.png"
        img.write_bytes(b"\x89PNGfake")
        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "2": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "euler", "seed": 1},
            },
            "10": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "positive prompt"},
            },
        }
        payload = build_register_payload(
            avatar_slug="aeri",
            title="from-bridge",
            yaw_bin="0",
            tags=["bridge:test"],
            image_path=str(img),
            workflow=workflow,
            openpose_json_path="",
            openpose_png_path="",
        )
        r = app.handle_command(payload)
        assert r.status == "ok", r.payload
        eid = r.payload["entry_id"]
        # smart_tags echo back so the bridge can log them.
        assert "auto:model:model.safetensors" in r.payload["smart_tags"]
        assert "auto:sampler:euler" in r.payload["smart_tags"]

        # Fetch it back to confirm the title + tags + workflow stuck.
        g = app.handle_command(
            {"command": "get_library_entry", "entry_id": eid, "include": ["tags", "workflow", "prompts"]}
        )
        assert g.status == "ok"
        assert g.payload["title"] == "from-bridge"
        assert "bridge:test" in g.payload["tags"]
        assert g.payload["comfyui_workflow"] == workflow
        assert g.payload["prompts"][0]["positive"] == "positive prompt"
    finally:
        app.stop()
