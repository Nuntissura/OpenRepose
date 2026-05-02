"""Rig fit tests against the Aeri master fixture."""

from __future__ import annotations

import numpy as np

from openrepose.openpose_schema import (
    MEDIAPIPE_FACEMESH_COUNT,
    MEDIAPIPE_POSE_COUNT,
)
from openrepose.rig import Rig


def test_rig_fits_aeri_master_face_478(aeri_rig: Rig) -> None:
    assert aeri_rig.face_mesh.shape == (MEDIAPIPE_FACEMESH_COUNT, 3)


def test_rig_body_kps_shape(aeri_rig: Rig) -> None:
    assert aeri_rig.body_kps.shape == (MEDIAPIPE_POSE_COUNT, 3)
    assert aeri_rig.body_conf.shape == (MEDIAPIPE_POSE_COUNT,)


def test_rig_head_anchor_within_image(aeri_rig: Rig) -> None:
    w, h = aeri_rig.portrait_size
    cx, cy, _cz = aeri_rig.head_anchor
    # The synthesized neck for a centered bust portrait should sit close to
    # the canvas horizontal midline.
    assert 0 < cx < w
    assert 0 < cy < h


def test_rig_face_z_in_facemesh_scale(aeri_rig: Rig) -> None:
    """FaceMesh z should be in head-relative pixel scale (~tens of px)."""
    z = aeri_rig.face_mesh[:, 2]
    assert -300 < float(z.min()) < 0  # forward-most landmark close to camera
    assert 0 < float(z.max()) < 300  # back-of-mesh landmark behind face plane


def test_rig_body_z_calibrated_into_facemesh_scale(aeri_rig: Rig) -> None:
    """After calibration the visible body z values should sit in the same
    rough scale as FaceMesh z (tens of pixels), not Pose's native ~thousands."""
    visible = aeri_rig.body_conf > 0.3
    if not visible.any():
        return
    z = aeri_rig.body_kps[visible, 2]
    assert float(np.abs(z).max()) < 500  # Pose native scale would be ~1000+


def test_rig_has_face_landmark_4_nose_tip(aeri_rig: Rig) -> None:
    nose = aeri_rig.face_mesh[4]
    w, h = aeri_rig.portrait_size
    # Nose tip near center of frame.
    assert w * 0.3 < float(nose[0]) < w * 0.7
    assert h * 0.2 < float(nose[1]) < h * 0.7


def test_rig_metrics_recorded(aeri_rig: Rig) -> None:
    m = aeri_rig.fit_metrics
    assert m.face_landmark_count == MEDIAPIPE_FACEMESH_COUNT
    assert m.fit_duration_ms > 0
    assert isinstance(m.body_partial, bool)
    assert isinstance(m.body_partial_missing, tuple)


def test_rig_openpose_face_70_shape(aeri_rig: Rig) -> None:
    face_70 = aeri_rig.openpose_face_70()
    assert face_70.shape == (70, 3)


def test_rig_openpose_body_18_shape(aeri_rig: Rig) -> None:
    body_18, conf_18 = aeri_rig.openpose_body_18()
    assert body_18.shape == (18, 3)
    assert conf_18.shape == (18,)
