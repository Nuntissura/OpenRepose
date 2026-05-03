"""Library snapshot targets (WP-I2-007).

Two layers:
  * Pure renderer tests for `render_library_entry` /
    `render_library_search_results` — always run.
  * Dispatcher integration: the `snapshot` command produces non-empty
    PNGs for both targets, sourcing the entry / results from
    `state.library`. Skipped when no Postgres available, but the
    renderer tests give us coverage on every machine.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

from openrepose.render.draw_library import (
    ENTRY_PANEL_H,
    ENTRY_PANEL_W,
    GRID_COLS,
    GRID_ROWS,
    render_library_entry,
    render_library_search_results,
)
from openrepose.snapshot import VALID_TARGETS


# ---------------------------------------------------------------------------
# Pure renderers
# ---------------------------------------------------------------------------


def test_valid_targets_includes_library_targets():
    assert "library_entry" in VALID_TARGETS
    assert "library_search_results" in VALID_TARGETS


def test_render_library_entry_produces_placeholder_when_none(tmp_path: Path):
    img = render_library_entry(None, tmp_path)
    assert isinstance(img, np.ndarray)
    h, w = img.shape[:2]
    assert h > 0 and w > 0


def test_render_library_entry_with_real_files(tmp_path: Path):
    eid = "00000000-0000-0000-0000-000000000099"
    edir = tmp_path / eid
    edir.mkdir()
    fake = (np.random.rand(120, 160, 3) * 255).astype(np.uint8)
    cv2.imwrite(str(edir / "openpose.png"), fake)
    cv2.imwrite(str(edir / "generated.png"), fake)
    entry = {
        "title": "evidence",
        "avatar_slug": "aeri",
        "yaw_bin": "her-right-30",
        "openpose_png_path": f"{eid}/openpose.png",
        "generated_image_path": f"{eid}/generated.png",
    }
    img = render_library_entry(entry, tmp_path)
    h, w = img.shape[:2]
    # Composition is two ENTRY_PANEL_W panels side-by-side + 4px middle
    # divider + 32px header strip.
    assert w == ENTRY_PANEL_W * 2 + 4
    assert h == ENTRY_PANEL_H + 32


def test_render_library_entry_with_missing_files_does_not_crash(tmp_path: Path):
    entry = {
        "title": "missing",
        "avatar_slug": "aeri",
        "yaw_bin": "0",
        "openpose_png_path": "no-such-id/openpose.png",
        "generated_image_path": "no-such-id/generated.png",
    }
    img = render_library_entry(entry, tmp_path)
    assert img is not None and img.shape[0] > 0 and img.shape[1] > 0


def test_render_library_entry_with_locked_label(tmp_path: Path):
    entry = {
        "title": "held",
        "avatar_slug": "aeri",
        "yaw_bin": "0",
        "locked_by": "other-op",
        "openpose_png_path": None,
        "generated_image_path": None,
    }
    img = render_library_entry(entry, tmp_path)
    assert img.shape[0] > 0


def test_render_library_search_results_no_results(tmp_path: Path):
    img = render_library_search_results([], tmp_path)
    assert img is not None
    assert img.shape[0] > 0 and img.shape[1] > 0


def test_render_library_search_results_grid_dimensions(tmp_path: Path):
    results = [
        {
            "entry_id": f"id-{i}",
            "title": f"entry {i}",
            "openpose_png_path": None,
        }
        for i in range(GRID_ROWS * GRID_COLS)
    ]
    img = render_library_search_results(results, tmp_path)
    h, w = img.shape[:2]
    assert h > GRID_ROWS * 100  # rough lower bound; exact size internal
    assert w > GRID_COLS * 100


# ---------------------------------------------------------------------------
# Dispatcher round-trip (needs PG)
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

    snap_pg_proc = _factories.postgresql_proc(
        port=None,
        postgres_options="-c log_destination=stderr -c logging_collector=off",
    )
    snap_pg = _factories.postgresql("snap_pg_proc")
else:  # pragma: no cover
    @pytest.fixture
    def snap_pg():
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


@pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres",
)
def test_snapshot_command_produces_library_entry_png(snap_pg, tmp_path: Path):
    from openrepose.app import App
    from openrepose.settings import Settings

    settings = Settings(
        library_db_url=_to_dsn(snap_pg),
        library_root=str(tmp_path / "library"),
        operator_slug="snap-op",
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
        # Register an entry so we have something to snapshot.
        r = app.handle_command(
            {
                "command": "register_library_entry",
                "avatar_slug": "aeri",
                "title": "snap me",
            }
        )
        assert r.status == "ok"
        eid = r.payload["entry_id"]
        # Hydrate state.library.last_entry by calling get.
        g = app.handle_command(
            {"command": "get_library_entry", "entry_id": eid}
        )
        assert g.status == "ok"
        # library_entry snapshot target.
        s = app.handle_command(
            {"command": "snapshot", "target": "library_entry"}
        )
        assert s.status == "ok"
        png_path = Path(s.payload["out_path"])
        assert png_path.exists()
        img = cv2.imread(str(png_path))
        assert img is not None and img.shape[0] > 0
    finally:
        app.stop()


@pytest.mark.skipif(
    not (PG_AVAILABLE and HAS_PYTEST_POSTGRESQL),
    reason="no system Postgres",
)
def test_snapshot_command_produces_library_search_results_png(snap_pg, tmp_path: Path):
    from openrepose.app import App
    from openrepose.settings import Settings

    settings = Settings(
        library_db_url=_to_dsn(snap_pg),
        library_root=str(tmp_path / "library"),
        operator_slug="snap-op",
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
        for i in range(3):
            app.handle_command(
                {
                    "command": "register_library_entry",
                    "avatar_slug": "aeri",
                    "title": f"intimate scene {i}",
                }
            )
        # Run a search so state.library.last_search_results is populated.
        r = app.handle_command(
            {"command": "library_search", "query": "intimate"}
        )
        assert r.status == "ok"
        assert r.payload["count"] >= 1
        s = app.handle_command(
            {"command": "snapshot", "target": "library_search_results"}
        )
        assert s.status == "ok"
        png_path = Path(s.payload["out_path"])
        assert png_path.exists()
        img = cv2.imread(str(png_path))
        assert img is not None and img.shape[0] > 0
    finally:
        app.stop()
