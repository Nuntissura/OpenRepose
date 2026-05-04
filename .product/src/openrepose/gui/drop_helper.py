"""Drag-and-drop validation for portrait import.

Multi-file workspace policy (WP-I1-037): accept every local PNG/JPG/JPEG in
the drop and open one file slot per accepted image. Rejected entries are
returned so callers can log a single WARN without silently swallowing them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_ACCEPTED_SUFFIXES = {".png", ".jpg", ".jpeg"}
_REJECTED_SUFFIXES = {".lnk"}


@dataclass(frozen=True)
class DropDecision:
    path: Path | None
    ignored: list[str]
    reason: str | None


@dataclass(frozen=True)
class MultiDropDecision:
    paths: list[Path]
    ignored: list[str]
    reason: str | None


def _local_paths_from_mime(mime_data) -> list[Path]:  # noqa: ANN001
    if not mime_data.hasUrls():
        return []
    return [Path(u.toLocalFile()) for u in mime_data.urls() if u.toLocalFile()]


def mime_has_acceptable_image(mime_data) -> bool:  # noqa: ANN001
    return any(_is_acceptable_image(p) for p in _local_paths_from_mime(mime_data))


def decide_drop(mime_data) -> DropDecision:  # noqa: ANN001
    multi = decide_multi_drop(mime_data)
    first = multi.paths[0] if multi.paths else None
    ignored = list(multi.ignored)
    if len(multi.paths) > 1:
        ignored.extend(p.name for p in multi.paths[1:])
    return DropDecision(path=first, ignored=ignored, reason=multi.reason)


def decide_multi_drop(mime_data) -> MultiDropDecision:  # noqa: ANN001
    paths = _local_paths_from_mime(mime_data)
    if not paths:
        return MultiDropDecision(paths=[], ignored=[], reason="drop carried no local file paths")
    accepted: list[Path] = []
    ignored: list[str] = []
    for p in paths:
        if _is_acceptable_image(p):
            accepted.append(p)
        else:
            ignored.append(p.name)
    if not accepted:
        return MultiDropDecision(
            paths=[],
            ignored=ignored,
            reason="no image file in drop (accepted: " + ", ".join(sorted(_ACCEPTED_SUFFIXES)) + ")",
        )
    return MultiDropDecision(paths=accepted, ignored=ignored, reason=None)


def _is_acceptable_image(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in _REJECTED_SUFFIXES:
        return False
    if suffix not in _ACCEPTED_SUFFIXES:
        return False
    if not path.exists():
        return False
    return True
