"""Per-avatar calibration overlay.

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 2: Per-Avatar
Calibration Overlay". Operator-marked reference points correct MediaPipe
FaceMesh's bias toward average human proportions on stylized avatars. A
thin-plate-spline (TPS) deformation field maps detected landmark
positions to operator-marked positions. The field is applied to landmark
XY coordinates only; z passes through. Four implicit corner clamps
suppress overshoot in unmarked regions.

Persistence: outputs/<avatar-slug>/calibration.json (gitignored).
"""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.interpolate import RBFInterpolator

CALIBRATION_SCHEMA_VERSION = 1

REQUIRED_MARKERS: tuple[str, ...] = (
    "eye_outer_left",
    "eye_outer_right",
    "mouth_corner_left",
    "mouth_corner_right",
    "jaw_corner_left",
    "jaw_corner_right",
)

OPTIONAL_MARKERS: tuple[str, ...] = (
    "brow_outer_left",
    "brow_outer_right",
    "nose_tip",
    "chin_bottom",
)

ALL_MARKER_NAMES: frozenset[str] = frozenset(REQUIRED_MARKERS + OPTIONAL_MARKERS)


class OpenReposeCalibrationError(ValueError):
    """Raised on invalid marker name, malformed JSON, or bad shape input."""


@dataclass(frozen=True)
class Marker:
    """One operator-marked reference point + the MediaPipe-detected
    position for the same anatomical feature."""

    name: str
    operator_xy: tuple[float, float]
    mediapipe_xy: tuple[float, float]


@dataclass(frozen=True)
class Calibration:
    """A complete (or partial) per-avatar calibration record.

    Persisted as `outputs/<avatar-slug>/calibration.json` per spec.
    """

    avatar_slug: str
    image_path: str
    image_size: tuple[int, int]
    mediapipe_version: str
    markers: tuple[Marker, ...]
    created_at: str
    updated_at: str

    @property
    def completeness(self) -> str:
        """`complete` when all 6 required markers present; `partial` when
        some required missing but at least one marker exists; `none` when
        the marker tuple is empty."""
        if not self.markers:
            return "none"
        marker_names = {m.name for m in self.markers}
        if marker_names >= set(REQUIRED_MARKERS):
            return "complete"
        return "partial"

    @property
    def missing_required(self) -> tuple[str, ...]:
        marker_names = {m.name for m in self.markers}
        return tuple(n for n in REQUIRED_MARKERS if n not in marker_names)

    @property
    def marker_count(self) -> int:
        return len(self.markers)


@dataclass(frozen=True)
class DeformationField:
    """A cached TPS field. Use `apply` to transform an (N, 2) array of
    pixel-space XY coordinates."""

    interpolator: Any  # scipy.interpolate.RBFInterpolator
    image_size: tuple[int, int]

    def apply(self, points_xy: np.ndarray) -> np.ndarray:
        if points_xy.ndim != 2 or points_xy.shape[1] != 2:
            raise OpenReposeCalibrationError(
                f"apply expects shape (N, 2); got {points_xy.shape}"
            )
        return np.asarray(self.interpolator(points_xy), dtype=np.float32)


def calibration_path(outputs_root: Path | str, avatar_slug: str) -> Path:
    """Conventional location: `outputs/<avatar-slug>/calibration.json`."""
    return Path(outputs_root) / avatar_slug / "calibration.json"


def load(path: Path | str) -> Calibration | None:
    """Load a calibration JSON. Returns None when the file does not exist.

    Raises OpenReposeCalibrationError on malformed JSON, wrong schema
    version, unknown marker name, or malformed marker entries.
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise OpenReposeCalibrationError(
            f"calibration JSON unparseable at {p}: {e}"
        ) from e

    if not isinstance(data, dict):
        raise OpenReposeCalibrationError(
            f"calibration JSON must be an object at {p}"
        )

    schema_version = data.get("schema_version")
    if schema_version != CALIBRATION_SCHEMA_VERSION:
        raise OpenReposeCalibrationError(
            f"unsupported schema_version {schema_version!r}; expected "
            f"{CALIBRATION_SCHEMA_VERSION}"
        )

    raw_markers = data.get("markers", [])
    if not isinstance(raw_markers, list):
        raise OpenReposeCalibrationError("markers must be a list")
    markers: list[Marker] = []
    for i, raw in enumerate(raw_markers):
        if not isinstance(raw, dict):
            raise OpenReposeCalibrationError(f"marker {i} must be an object")
        name = raw.get("name")
        op_xy = raw.get("operator_xy")
        mp_xy = raw.get("mediapipe_xy")
        if name not in ALL_MARKER_NAMES:
            raise OpenReposeCalibrationError(
                f"marker {i} has unknown name {name!r}; allowed: "
                f"{sorted(ALL_MARKER_NAMES)}"
            )
        if not (isinstance(op_xy, list) and len(op_xy) == 2):
            raise OpenReposeCalibrationError(
                f"marker {i} operator_xy must be [x, y]"
            )
        if not (isinstance(mp_xy, list) and len(mp_xy) == 2):
            raise OpenReposeCalibrationError(
                f"marker {i} mediapipe_xy must be [x, y]"
            )
        markers.append(
            Marker(
                name=name,
                operator_xy=(float(op_xy[0]), float(op_xy[1])),
                mediapipe_xy=(float(mp_xy[0]), float(mp_xy[1])),
            )
        )

    image_size_raw = data.get("image_size", [0, 0])
    if not (isinstance(image_size_raw, list) and len(image_size_raw) == 2):
        raise OpenReposeCalibrationError(
            "image_size must be [width, height]"
        )

    return Calibration(
        avatar_slug=str(data.get("avatar_slug", "")),
        image_path=str(data.get("image_path", "")),
        image_size=(int(image_size_raw[0]), int(image_size_raw[1])),
        mediapipe_version=str(data.get("mediapipe_version", "")),
        markers=tuple(markers),
        created_at=str(data.get("created_at", "")),
        updated_at=str(data.get("updated_at", "")),
    )


def save(calibration: Calibration, path: Path | str) -> None:
    """Atomic write to `path`. Bumps `updated_at` to now (UTC, ISO8601 ms)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    now = _now_iso()
    payload: dict[str, Any] = {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "avatar_slug": calibration.avatar_slug,
        "image_path": calibration.image_path,
        "image_size": list(calibration.image_size),
        "mediapipe_version": calibration.mediapipe_version,
        "completeness": calibration.completeness,
        "markers": [
            {
                "name": m.name,
                "operator_xy": list(m.operator_xy),
                "mediapipe_xy": list(m.mediapipe_xy),
            }
            for m in calibration.markers
        ],
        "created_at": calibration.created_at or now,
        "updated_at": now,
    }
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def compute_field(
    calibration: Calibration,
    image_size: tuple[int, int] | None = None,
) -> DeformationField | None:
    """Build the TPS deformation field for `calibration`.

    Source points are MediaPipe-detected positions; destination points are
    operator-marked positions. Four implicit corner clamps (image corners
    fixed in both source and destination) suppress overshoot in unmarked
    regions. Returns None when no markers exist (identity field implicit).

    `image_size` overrides `calibration.image_size` when supplied (useful
    when the calibration was authored against a master at a different
    resolution than the current rig fit).
    """
    if not calibration.markers:
        return None

    size = image_size or calibration.image_size
    if size[0] <= 0 or size[1] <= 0:
        raise OpenReposeCalibrationError(
            f"image_size must be positive; got {size}"
        )

    src = np.array(
        [m.mediapipe_xy for m in calibration.markers], dtype=np.float64
    )
    dst = np.array(
        [m.operator_xy for m in calibration.markers], dtype=np.float64
    )

    w, h = size
    corners = np.array(
        [
            [0.0, 0.0],
            [float(w), 0.0],
            [0.0, float(h)],
            [float(w), float(h)],
        ],
        dtype=np.float64,
    )
    src = np.vstack([src, corners])
    dst = np.vstack([dst, corners])

    interp = RBFInterpolator(src, dst, kernel="thin_plate_spline")
    return DeformationField(interpolator=interp, image_size=(int(w), int(h)))


def apply_deformation(
    field_: DeformationField | None,
    points_xy: np.ndarray,
) -> np.ndarray:
    """Apply `field_` to `points_xy`. Identity when `field_` is None."""
    if field_ is None:
        return points_xy
    return field_.apply(points_xy)


def _now_iso() -> str:
    """ISO-8601 UTC timestamp with millisecond precision (matches state.py)."""
    now = datetime.datetime.now(tz=datetime.UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
