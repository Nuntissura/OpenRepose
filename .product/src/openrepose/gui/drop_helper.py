"""Drag-and-drop validation for portrait import (WP-I1-005).

Operator drags a PNG/JPG file from Explorer into the OpenRepose window;
this module validates the MIME data and extracts the first acceptable
image path. Used by `MainWindow`, `Viewport3D`, and `ViewportOpenPose`
so the validation lives in one place.

Multi-file drop policy (frozen at WP-I1-005 kickoff): accept the first
image, log WARN listing the ignored entries; do NOT silently iterate.
True multi-file workspace support is WP-I1-036 territory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_ACCEPTED_SUFFIXES = {".png", ".jpg", ".jpeg"}
_REJECTED_SUFFIXES = {".lnk"}  # Windows shell links can resolve to images;
# we never resolve them in case the resolution surprises the operator.


@dataclass(frozen=True)
class DropDecision:
    """Outcome of inspecting a drop's mime data.

    `path` is the first acceptable image path (None if none qualified).
    `ignored` lists every other entry the drop carried (used for the
    multi-file WARN line). `reason` is a one-line rejection reason when
    `path is None` (e.g. "no image file in drop").
    """

    path: Path | None
    ignored: list[str]
    reason: str | None


def _local_paths_from_mime(mime_data) -> list[Path]:  # noqa: ANN001
    if not mime_data.hasUrls():
        return []
    return [Path(u.toLocalFile()) for u in mime_data.urls() if u.toLocalFile()]


def mime_has_acceptable_image(mime_data) -> bool:  # noqa: ANN001
    """Cheap pre-check for `dragEnterEvent` — returns True if any url in
    the drop ends with an accepted image suffix and is not a rejected
    suffix (e.g. .lnk)."""
    paths = _local_paths_from_mime(mime_data)
    return any(_is_acceptable_image(p) for p in paths)


def decide_drop(mime_data) -> DropDecision:  # noqa: ANN001
    """Inspect a drop's mime data and return the first acceptable image
    + the names that were ignored. Caller logs WARN when `ignored` is
    non-empty."""
    paths = _local_paths_from_mime(mime_data)
    if not paths:
        return DropDecision(path=None, ignored=[], reason="drop carried no local file paths")
    first: Path | None = None
    ignored: list[str] = []
    for p in paths:
        if first is None and _is_acceptable_image(p):
            first = p
            continue
        ignored.append(p.name)
    if first is None:
        return DropDecision(
            path=None,
            ignored=ignored,
            reason=(
                "no image file in drop (accepted: "
                + ", ".join(sorted(_ACCEPTED_SUFFIXES))
                + ")"
            ),
        )
    return DropDecision(path=first, ignored=ignored, reason=None)


def _is_acceptable_image(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in _REJECTED_SUFFIXES:
        return False
    if suffix not in _ACCEPTED_SUFFIXES:
        return False
    if not path.exists():
        return False
    return True
