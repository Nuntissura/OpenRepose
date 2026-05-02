"""Tests for openrepose.calibration module.

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 2: Per-Avatar
Calibration Overlay".
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from openrepose.calibration import (
    ALL_MARKER_NAMES,
    CALIBRATION_SCHEMA_VERSION,
    OPTIONAL_MARKERS,
    REQUIRED_MARKERS,
    Calibration,
    Marker,
    OpenReposeCalibrationError,
    apply_deformation,
    calibration_path,
    compute_field,
    load,
    save,
)


def _identity_marker(name: str, x: float, y: float) -> Marker:
    return Marker(name=name, operator_xy=(x, y), mediapipe_xy=(x, y))


def _displaced_marker(
    name: str, mp_x: float, mp_y: float, op_x: float, op_y: float
) -> Marker:
    return Marker(
        name=name, operator_xy=(op_x, op_y), mediapipe_xy=(mp_x, mp_y)
    )


def _all_required_markers(spread: float = 50.0, base_x: float = 100.0,
                          base_y: float = 200.0) -> list[Marker]:
    """Six identity markers spread across a small region."""
    return [
        _identity_marker(n, base_x + i * spread, base_y + (i % 2) * spread)
        for i, n in enumerate(REQUIRED_MARKERS)
    ]


# --- vocabulary -------------------------------------------------------------


def test_required_markers_count_six():
    assert len(REQUIRED_MARKERS) == 6


def test_optional_markers_count_four():
    assert len(OPTIONAL_MARKERS) == 4


def test_marker_names_are_unique():
    assert len(ALL_MARKER_NAMES) == len(REQUIRED_MARKERS) + len(OPTIONAL_MARKERS)


def test_marker_names_use_her_anatomy_convention():
    # Forbidden phrases per yaw lock should not appear in marker names.
    forbidden = ("image-left", "image-right", "viewer-left", "viewer-right")
    for name in ALL_MARKER_NAMES:
        for bad in forbidden:
            assert bad not in name


# --- completeness -----------------------------------------------------------


def test_completeness_complete_when_all_required_present():
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=tuple(_all_required_markers()),
        created_at="",
        updated_at="",
    )
    assert cal.completeness == "complete"
    assert cal.missing_required == ()
    assert cal.marker_count == 6


def test_completeness_partial_when_some_required_missing():
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=(_identity_marker("eye_outer_left", 100, 200),),
        created_at="",
        updated_at="",
    )
    assert cal.completeness == "partial"
    assert "eye_outer_right" in cal.missing_required
    assert "mouth_corner_left" in cal.missing_required
    assert cal.marker_count == 1


def test_completeness_none_when_no_markers():
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=(),
        created_at="",
        updated_at="",
    )
    assert cal.completeness == "none"
    assert cal.missing_required == REQUIRED_MARKERS
    assert cal.marker_count == 0


def test_completeness_complete_with_optional_markers():
    markers = list(_all_required_markers())
    markers.append(_identity_marker("nose_tip", 300, 300))
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=tuple(markers),
        created_at="",
        updated_at="",
    )
    assert cal.completeness == "complete"
    assert cal.marker_count == 7


# --- round-trip -------------------------------------------------------------


def test_save_load_roundtrip(tmp_path: Path):
    cal = Calibration(
        avatar_slug="aeri",
        image_path="outputs/aeri/master.png",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=tuple(_all_required_markers()),
        created_at="",
        updated_at="",
    )
    p = tmp_path / "calibration.json"
    save(cal, p)
    loaded = load(p)
    assert loaded is not None
    assert loaded.avatar_slug == "aeri"
    assert loaded.image_size == (1024, 1024)
    assert len(loaded.markers) == 6
    assert {m.name for m in loaded.markers} == set(REQUIRED_MARKERS)


def test_save_writes_completeness_and_iso_timestamps(tmp_path: Path):
    cal = Calibration(
        avatar_slug="aeri",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=(_identity_marker("eye_outer_left", 100, 200),),
        created_at="",
        updated_at="",
    )
    p = tmp_path / "calibration.json"
    save(cal, p)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["schema_version"] == CALIBRATION_SCHEMA_VERSION
    assert data["completeness"] == "partial"
    assert data["created_at"]
    assert data["updated_at"]


def test_save_atomic_via_temp_then_rename(tmp_path: Path):
    """Save uses a .tmp + os.replace pattern; no .tmp file remains."""
    cal = Calibration(
        avatar_slug="aeri",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=tuple(_all_required_markers()),
        created_at="",
        updated_at="",
    )
    p = tmp_path / "calibration.json"
    save(cal, p)
    assert p.exists()
    assert not (tmp_path / "calibration.json.tmp").exists()


def test_load_missing_file_returns_none(tmp_path: Path):
    assert load(tmp_path / "no-such-file.json") is None


def test_load_unparseable_raises(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(OpenReposeCalibrationError):
        load(p)


def test_load_non_object_root_raises(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(OpenReposeCalibrationError):
        load(p)


def test_load_wrong_schema_version_raises(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text(
        json.dumps({"schema_version": 999, "markers": []}),
        encoding="utf-8",
    )
    with pytest.raises(OpenReposeCalibrationError):
        load(p)


def test_load_unknown_marker_name_raises(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": CALIBRATION_SCHEMA_VERSION,
                "markers": [
                    {
                        "name": "made_up_marker",
                        "operator_xy": [0, 0],
                        "mediapipe_xy": [0, 0],
                    }
                ],
                "image_size": [1024, 1024],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OpenReposeCalibrationError):
        load(p)


def test_load_missing_marker_xy_raises(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": CALIBRATION_SCHEMA_VERSION,
                "markers": [
                    {"name": "eye_outer_left", "operator_xy": [100, 200]}
                ],
                "image_size": [1024, 1024],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OpenReposeCalibrationError):
        load(p)


# --- conventional path ------------------------------------------------------


def test_calibration_path_format(tmp_path: Path):
    p = calibration_path(tmp_path, "aeri")
    assert p == tmp_path / "aeri" / "calibration.json"


# --- deformation field ------------------------------------------------------


def test_compute_field_with_no_markers_returns_none():
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=(),
        created_at="",
        updated_at="",
    )
    assert compute_field(cal) is None


def test_compute_field_rejects_zero_image_size():
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(0, 0),
        mediapipe_version="0.10.21",
        markers=tuple(_all_required_markers()),
        created_at="",
        updated_at="",
    )
    with pytest.raises(OpenReposeCalibrationError):
        compute_field(cal)


def test_identity_field_passes_points_through():
    """If every operator_xy == mediapipe_xy, the field is ~identity."""
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=tuple(_all_required_markers()),
        created_at="",
        updated_at="",
    )
    f = compute_field(cal)
    assert f is not None
    pts = np.array([[110.0, 200.0], [300.0, 400.0], [512.0, 512.0]])
    out = f.apply(pts)
    assert np.allclose(pts, out, atol=1e-2)


def test_field_pulls_marked_points_to_destinations():
    """A point exactly at a source location maps to the destination."""
    markers = list(_all_required_markers(spread=80.0))
    markers[0] = _displaced_marker(
        "eye_outer_left", 100.0, 200.0, 150.0, 220.0
    )
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=tuple(markers),
        created_at="",
        updated_at="",
    )
    f = compute_field(cal)
    assert f is not None
    out = f.apply(np.array([[100.0, 200.0]]))
    assert np.allclose(out[0], (150.0, 220.0), atol=1.0)


def test_field_keeps_far_corner_points_near_identity():
    """Corner clamps prevent runaway deformation in unmarked regions."""
    markers = list(_all_required_markers(spread=80.0))
    markers[0] = _displaced_marker(
        "eye_outer_left", 100.0, 200.0, 150.0, 220.0
    )
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=tuple(markers),
        created_at="",
        updated_at="",
    )
    f = compute_field(cal)
    assert f is not None
    corners = np.array(
        [[0.0, 0.0], [1024.0, 0.0], [0.0, 1024.0], [1024.0, 1024.0]]
    )
    out = f.apply(corners)
    assert np.allclose(out, corners, atol=1.0)


def test_apply_deformation_with_none_field_is_identity():
    pts = np.array([[100.0, 200.0], [300.0, 400.0]])
    out = apply_deformation(None, pts)
    assert out is pts


def test_field_apply_rejects_wrong_shape():
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=tuple(_all_required_markers()),
        created_at="",
        updated_at="",
    )
    f = compute_field(cal)
    assert f is not None
    with pytest.raises(OpenReposeCalibrationError):
        f.apply(np.array([1.0, 2.0]))  # 1D, not (N, 2)
    with pytest.raises(OpenReposeCalibrationError):
        f.apply(np.array([[1.0, 2.0, 3.0]]))  # (1, 3), not (N, 2)


def test_field_image_size_override():
    """When `image_size` is supplied, corner clamps use that size."""
    cal = Calibration(
        avatar_slug="test",
        image_path="x",
        image_size=(1024, 1024),
        mediapipe_version="0.10.21",
        markers=tuple(_all_required_markers()),
        created_at="",
        updated_at="",
    )
    f = compute_field(cal, image_size=(512, 512))
    assert f is not None
    assert f.image_size == (512, 512)
    # The (512, 512) corner should now be clamped, not the (1024, 1024).
    out = f.apply(np.array([[512.0, 512.0]]))
    assert np.allclose(out[0], (512.0, 512.0), atol=1.0)


# --- forbidden terminology --------------------------------------------------


def test_no_forbidden_yaw_phrases_in_module_source():
    """Per yaw lock, calibration.py must not contain forbidden phrases."""
    src = (
        Path(__file__).parent.parent
        / "src"
        / "openrepose"
        / "calibration.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "image-left",
        "image-right",
        "viewer-left",
        "viewer-right",
    ):
        assert forbidden not in src, (
            f"forbidden phrase {forbidden!r} found in calibration.py"
        )
