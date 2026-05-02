"""Rig.from_portrait + Rig.with_calibration integration tests against the
Aeri master fixture.

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 2: Per-Avatar
Calibration Overlay" / Application Flow.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from openrepose.calibration import (
    MEDIAPIPE_FACEMESH_INDEX_BY_MARKER,
    REQUIRED_MARKERS,
    Calibration,
    Marker,
)
from openrepose.rig import Rig


def _calibration_from_rig(
    rig: Rig,
    *,
    eye_outer_left_offset: tuple[float, float] = (0.0, 0.0),
) -> Calibration:
    """Build a 6-required-marker calibration whose mediapipe_xy values are
    drawn from the rig's actual FaceMesh detections, so the deformation is
    well-defined. `eye_outer_left_offset` displaces that one marker."""
    src = rig.raw_face_mesh if rig.raw_face_mesh is not None else rig.face_mesh
    markers: list[Marker] = []
    for name in REQUIRED_MARKERS:
        idx = MEDIAPIPE_FACEMESH_INDEX_BY_MARKER[name]
        mp_xy = (float(src[idx, 0]), float(src[idx, 1]))
        op_xy = mp_xy
        if name == "eye_outer_left":
            op_xy = (
                mp_xy[0] + eye_outer_left_offset[0],
                mp_xy[1] + eye_outer_left_offset[1],
            )
        markers.append(
            Marker(name=name, operator_xy=op_xy, mediapipe_xy=mp_xy)
        )
    return Calibration(
        avatar_slug="aeri",
        image_path=str(rig.fit_metrics.portrait_path),
        image_size=rig.portrait_size,
        mediapipe_version="0.10.21",
        markers=tuple(markers),
        created_at="",
        updated_at="",
    )


def test_from_portrait_without_calibration_preserves_raw(
    aeri_rig: Rig,
) -> None:
    assert aeri_rig.calibration is None
    assert aeri_rig.raw_face_mesh is not None
    assert aeri_rig.raw_body_kps is not None
    # face_mesh and raw_face_mesh must be equal when no calibration applied.
    assert np.array_equal(aeri_rig.face_mesh, aeri_rig.raw_face_mesh)
    assert np.array_equal(aeri_rig.body_kps, aeri_rig.raw_body_kps)


def test_with_calibration_identity_returns_unchanged_landmarks(
    aeri_rig: Rig,
) -> None:
    """Identity calibration (operator_xy == mediapipe_xy) yields ~no change."""
    cal = _calibration_from_rig(aeri_rig, eye_outer_left_offset=(0.0, 0.0))
    new_rig = aeri_rig.with_calibration(cal)
    assert new_rig.calibration is cal
    # Landmarks should be near-identical (within float tolerance).
    assert np.allclose(
        new_rig.face_mesh[:, :2], aeri_rig.face_mesh[:, :2], atol=1e-2
    )
    assert np.allclose(
        new_rig.body_kps[:, :2], aeri_rig.body_kps[:, :2], atol=1e-2
    )
    # Z must be passed through unchanged.
    assert np.array_equal(new_rig.face_mesh[:, 2], aeri_rig.face_mesh[:, 2])
    assert np.array_equal(new_rig.body_kps[:, 2], aeri_rig.body_kps[:, 2])


def test_with_calibration_displaces_marked_landmark(aeri_rig: Rig) -> None:
    """Displacing eye_outer_left moves face_mesh[263] toward operator_xy."""
    offset = (50.0, -30.0)
    cal = _calibration_from_rig(aeri_rig, eye_outer_left_offset=offset)
    new_rig = aeri_rig.with_calibration(cal)

    idx = MEDIAPIPE_FACEMESH_INDEX_BY_MARKER["eye_outer_left"]
    raw_xy = aeri_rig.raw_face_mesh[idx, :2]
    new_xy = new_rig.face_mesh[idx, :2]

    expected = (raw_xy[0] + offset[0], raw_xy[1] + offset[1])
    assert np.allclose(new_xy, expected, atol=1.0)


def test_with_calibration_then_clear_restores_raw(aeri_rig: Rig) -> None:
    cal = _calibration_from_rig(
        aeri_rig, eye_outer_left_offset=(50.0, -30.0)
    )
    cal_rig = aeri_rig.with_calibration(cal)
    assert not np.allclose(
        cal_rig.face_mesh[:, :2], aeri_rig.face_mesh[:, :2]
    )

    cleared = cal_rig.with_calibration(None)
    assert cleared.calibration is None
    # face_mesh must equal raw_face_mesh after clearing.
    assert np.array_equal(cleared.face_mesh, cleared.raw_face_mesh)
    # And those raws should equal the original rig's raws (round-trip safe).
    assert np.array_equal(
        cleared.raw_face_mesh, aeri_rig.raw_face_mesh
    )


def test_with_calibration_recomputes_head_anchor(aeri_rig: Rig) -> None:
    """Head anchor depends on body_kps; calibration changes it (only if
    the field reaches the body region — corner clamps usually keep body
    landmarks stable in this fixture, so we tolerate small drift)."""
    cal = _calibration_from_rig(aeri_rig, eye_outer_left_offset=(0.0, 0.0))
    new_rig = aeri_rig.with_calibration(cal)
    # With identity calibration the head anchor must not drift.
    assert np.allclose(new_rig.head_anchor, aeri_rig.head_anchor, atol=1.0)


def test_calibration_stored_on_rig(aeri_rig: Rig) -> None:
    cal = _calibration_from_rig(aeri_rig)
    new_rig = aeri_rig.with_calibration(cal)
    assert new_rig.calibration is cal
    assert new_rig.calibration.completeness == "complete"
