"""Filesystem layout for OpenRepose library entries.

Spec: `.gov/spec/openrepose_library_v0_1.md` Storage Layout.

Layout under `Settings.library_root` (defaults to `<export_folder>/library/`):

    outputs/library/<entry-uuid>/
      portrait.png        (operator's source / reference image)
      openpose.json       (the OpenPose-format JSON)
      openpose.png        (the rendered wireframe)
      generated.png       (downstream image from ComfyUI)
      workflow.json       (a copy of the ComfyUI workflow JSON)
      metadata.json       (mirror of the DB metadata column)

Per the spec, the database stores filesystem paths (relative to the
library root for portability). This module is the only writer/reader of
the per-entry directory layout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

# Canonical filenames inside `<entry-uuid>/`. Pinned so future code can
# discover what's there without an index file.
PORTRAIT_NAME = "portrait.png"
OPENPOSE_JSON_NAME = "openpose.json"
OPENPOSE_PNG_NAME = "openpose.png"
GENERATED_NAME = "generated.png"
WORKFLOW_NAME = "workflow.json"
METADATA_NAME = "metadata.json"


@dataclass(frozen=True)
class EntryFiles:
    """Resolved filesystem paths produced by `write_entry_files`.

    Each field is None when the corresponding payload was not supplied;
    callers store these as `library_entries.<column>_path` (relative form
    via `relative_to(library_root)` is the spec-prescribed shape).
    """

    entry_dir: Path
    portrait_path: Path | None = None
    openpose_json_path: Path | None = None
    openpose_png_path: Path | None = None
    generated_image_path: Path | None = None
    workflow_path: Path | None = None
    metadata_path: Path | None = None

    def written_paths(self) -> dict[str, Path]:
        """Return only the populated paths as a dict (helps tests / log lines)."""
        keys = (
            "portrait_path",
            "openpose_json_path",
            "openpose_png_path",
            "generated_image_path",
            "workflow_path",
            "metadata_path",
        )
        return {k: getattr(self, k) for k in keys if getattr(self, k) is not None}


def ensure_entry_dir(library_root: Path | str, entry_id: UUID | str) -> Path:
    """Compute and create the per-entry directory; return its absolute path."""
    root = Path(library_root)
    entry_dir = root / str(entry_id)
    entry_dir.mkdir(parents=True, exist_ok=True)
    return entry_dir


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_entry_files(
    library_root: Path | str,
    entry_id: UUID | str,
    *,
    portrait_bytes: bytes | None = None,
    openpose_json_bytes: bytes | None = None,
    openpose_png_bytes: bytes | None = None,
    generated_image_bytes: bytes | None = None,
    workflow: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> EntryFiles:
    """Write any provided payloads into the per-entry directory.

    Each parameter is optional. The function never deletes files; an
    update that supplies a smaller subset overwrites only what was given.
    Bytes are written atomically (write to .tmp, rename). Returns the
    paths of files that ended up on disk after this call (existing files
    that were not part of the payload are NOT included)."""
    entry_dir = ensure_entry_dir(library_root, entry_id)

    portrait = openpose_json = openpose_png = generated = workflow_p = metadata_p = None

    if portrait_bytes is not None:
        portrait = entry_dir / PORTRAIT_NAME
        _atomic_write_bytes(portrait, portrait_bytes)
    if openpose_json_bytes is not None:
        openpose_json = entry_dir / OPENPOSE_JSON_NAME
        _atomic_write_bytes(openpose_json, openpose_json_bytes)
    if openpose_png_bytes is not None:
        openpose_png = entry_dir / OPENPOSE_PNG_NAME
        _atomic_write_bytes(openpose_png, openpose_png_bytes)
    if generated_image_bytes is not None:
        generated = entry_dir / GENERATED_NAME
        _atomic_write_bytes(generated, generated_image_bytes)
    if workflow is not None:
        workflow_p = entry_dir / WORKFLOW_NAME
        _atomic_write_text(workflow_p, json.dumps(workflow, indent=2, sort_keys=True))
    if metadata is not None:
        metadata_p = entry_dir / METADATA_NAME
        _atomic_write_text(metadata_p, json.dumps(metadata, indent=2, sort_keys=True))

    return EntryFiles(
        entry_dir=entry_dir,
        portrait_path=portrait,
        openpose_json_path=openpose_json,
        openpose_png_path=openpose_png,
        generated_image_path=generated,
        workflow_path=workflow_p,
        metadata_path=metadata_p,
    )


def relative_to_root(path: Path, library_root: Path | str) -> str:
    """Return `path` expressed relative to the library root, with forward
    slashes for portability across platforms (the DB stores these as
    plain TEXT)."""
    root = Path(library_root)
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return str(path)
    return rel.as_posix()
