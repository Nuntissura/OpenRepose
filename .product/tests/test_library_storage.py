"""Filesystem layout for library entries (WP-I2-003). No DB required."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from openrepose.library.storage import (
    GENERATED_NAME,
    METADATA_NAME,
    OPENPOSE_JSON_NAME,
    OPENPOSE_PNG_NAME,
    PORTRAIT_NAME,
    WORKFLOW_NAME,
    ensure_entry_dir,
    relative_to_root,
    write_entry_files,
)


def test_ensure_entry_dir_creates_uuid_subfolder(tmp_path: Path):
    eid = uuid4()
    p = ensure_entry_dir(tmp_path, eid)
    assert p == tmp_path / str(eid)
    assert p.is_dir()


def test_write_entry_files_writes_each_provided_payload(tmp_path: Path):
    eid = uuid4()
    files = write_entry_files(
        tmp_path,
        eid,
        portrait_bytes=b"PNGDATA1",
        openpose_json_bytes=b"{}",
        openpose_png_bytes=b"PNGDATA2",
        generated_image_bytes=b"PNGDATA3",
        workflow={"nodes": []},
        metadata={"sampler": "euler"},
    )
    edir = tmp_path / str(eid)
    assert files.entry_dir == edir
    assert (edir / PORTRAIT_NAME).read_bytes() == b"PNGDATA1"
    assert (edir / OPENPOSE_JSON_NAME).read_bytes() == b"{}"
    assert (edir / OPENPOSE_PNG_NAME).read_bytes() == b"PNGDATA2"
    assert (edir / GENERATED_NAME).read_bytes() == b"PNGDATA3"
    assert json.loads((edir / WORKFLOW_NAME).read_text()) == {"nodes": []}
    assert json.loads((edir / METADATA_NAME).read_text()) == {"sampler": "euler"}


def test_write_entry_files_omits_unspecified_payloads(tmp_path: Path):
    eid = uuid4()
    files = write_entry_files(tmp_path, eid, openpose_json_bytes=b"{}")
    written = files.written_paths()
    assert "openpose_json_path" in written
    # Other keys absent.
    for key in (
        "portrait_path",
        "openpose_png_path",
        "generated_image_path",
        "workflow_path",
        "metadata_path",
    ):
        assert key not in written
    # Filesystem only contains openpose.json.
    assert {p.name for p in (tmp_path / str(eid)).iterdir()} == {OPENPOSE_JSON_NAME}


def test_write_entry_files_atomic_via_tmp_then_rename(tmp_path: Path):
    """The .tmp file must not survive after the rename — proves we use
    atomic writes."""
    eid = uuid4()
    write_entry_files(tmp_path, eid, openpose_json_bytes=b"{}")
    tmps = list((tmp_path / str(eid)).glob("*.tmp"))
    assert tmps == []


def test_write_entry_files_overwrites_existing(tmp_path: Path):
    eid = uuid4()
    write_entry_files(tmp_path, eid, openpose_json_bytes=b"{ \"a\": 1 }")
    # Re-write with new content; must replace cleanly.
    write_entry_files(tmp_path, eid, openpose_json_bytes=b"{ \"a\": 2 }")
    txt = (tmp_path / str(eid) / OPENPOSE_JSON_NAME).read_text()
    assert txt == "{ \"a\": 2 }"


def test_relative_to_root_returns_posix(tmp_path: Path):
    eid = uuid4()
    files = write_entry_files(tmp_path, eid, openpose_json_bytes=b"{}")
    rel = relative_to_root(files.openpose_json_path, tmp_path)
    assert rel == f"{eid}/{OPENPOSE_JSON_NAME}"


def test_relative_to_root_falls_back_when_outside(tmp_path: Path):
    other = tmp_path / "elsewhere.json"
    other.write_bytes(b"{}")
    # When `path` isn't under `library_root`, return the original string
    # rather than crash.
    rel = relative_to_root(other, tmp_path / "library")
    assert rel == str(other)
