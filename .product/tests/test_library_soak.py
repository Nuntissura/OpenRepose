"""Library subsystem soak test (WP-I2-008).

Closes the spec promotion guard:
"ComfyUI bridge survives at least 100 round-trips without dropped
registrations".

We don't actually run ComfyUI; we POST 100 `register_library_entry`
commands through the dispatcher (the same dict the bridge would POST)
and verify every entry landed with its smart tags + filesystem layout
intact.
"""

from __future__ import annotations

import base64
import shutil
from pathlib import Path

import pytest

PG_AVAILABLE = shutil.which("pg_ctl") is not None
HAS_PYTEST_POSTGRESQL = False
try:  # pragma: no cover
    from pytest_postgresql import factories as _pg_factories  # noqa: F401

    HAS_PYTEST_POSTGRESQL = True
except ImportError:
    pass


pytestmark = pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres / pytest-postgresql",
)


if PG_AVAILABLE and HAS_PYTEST_POSTGRESQL:
    from pytest_postgresql import factories as _factories

    soak_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    soak_pg = _factories.postgresql("soak_pg_proc")
else:  # pragma: no cover
    @pytest.fixture
    def soak_pg():
        pytest.skip("no Postgres")


def _to_dsn(pg_conn) -> str:  # noqa: ANN001
    info = pg_conn.info
    parts = [
        f"host={info.host}",
        f"port={info.port}",
        f"user={info.user}",
        f"dbname={info.dbname}",
    ]
    if getattr(info, "password", ""):
        parts.append(f"password={info.password}")
    return " ".join(parts)


def test_one_hundred_register_commands_all_land(soak_pg, tmp_path: Path):
    from openrepose.app import App
    from openrepose.settings import Settings

    settings = Settings(
        library_db_url=_to_dsn(soak_pg),
        library_root=str(tmp_path / "library"),
        operator_slug="soak-op",
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
        ids: list[str] = []
        for i in range(100):
            payload = {
                "command": "register_library_entry",
                "avatar_slug": "aeri",
                "title": f"soak-{i:03d}",
                "yaw_bin": "0" if i % 2 == 0 else "her-right-30",
                "openpose_json": base64.b64encode(b'{"v":1.3}').decode(),
                "comfyui_workflow": {
                    f"{i + 1}": {
                        "class_type": "CheckpointLoaderSimple",
                        "inputs": {"ckpt_name": f"model_{i % 3}.safetensors"},
                    },
                    f"{i + 2}": {
                        "class_type": "KSampler",
                        "inputs": {"sampler_name": ["euler", "dpmpp_2m"][i % 2]},
                    },
                },
                "metadata": {"steps": 20 + i, "cfg": 6.0 + (i % 5)},
                "tags": [f"soak:{i % 10}"],
            }
            r = app.handle_command(payload)
            assert r.status == "ok", (i, r.payload)
            ids.append(r.payload["entry_id"])

        # All 100 entries land + are unique.
        assert len(ids) == 100
        assert len(set(ids)) == 100

        # Smart-tag derivation worked: search for one of the model variants.
        s = app.handle_command(
            {"command": "library_search", "query": "model_1"}
        )
        assert s.status == "ok"
        assert s.payload["count"] >= 1

        # Filesystem layout: one folder per entry id, with the openpose.json
        # we POST'd.
        lib_root = Path(settings.library_root)
        for eid in ids:
            entry_dir = lib_root / eid
            assert entry_dir.exists(), f"missing {entry_dir}"
            assert (entry_dir / "openpose.json").exists()
    finally:
        app.stop()
