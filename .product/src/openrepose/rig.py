"""3D rig fit from a frontal portrait.

Builds a locked rig from MediaPipe FaceMesh (478-point 3D face mesh with
iris pupils) and MediaPipe Pose (33-point 3D body landmarks). The rig is
treated as a single rigid 3D object after construction; rotation produces
a new RotatedRig without mutating the original.

Coordinate convention (right-handed):
    +x = positive screen-x axis (right edge of frame)
    +y = positive screen-y axis (bottom of frame)
    +z = into screen (away from camera)
    -z = toward camera

Both FaceMesh and Pose return z values where smaller means closer to camera,
which matches our convention with no sign flip: mp_z * W gives a world z
where the nose tip (closest to camera) lands at the most-negative z.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .openpose_schema import (
    BODY_NOSE,
    map_face_mesh_to_openpose,
    map_pose_to_body18,
)


class OpenReposeRigFitError(RuntimeError):
    """Raised when rig fit fails (no face / no body / unreadable input)."""


@dataclass(frozen=True)
class FitMetrics:
    """Telemetry from one rig fit. Recorded in state.json and rig dumps."""

    portrait_path: str
    portrait_width: int
    portrait_height: int
    face_landmark_count: int
    body_landmark_count: int
    fit_duration_ms: int
    body_partial: bool
    body_partial_missing: tuple[str, ...]


@dataclass(frozen=True)
class Rig:
    """Locked 3D rig from a frontal portrait.

    Attributes:
        portrait_size: (width, height) of the source portrait in pixels.
        face_mesh: (478, 3) array. MediaPipe FaceMesh world coordinates
            (x in pixels, y in pixels, z in width-scaled units).
        body_kps: (33, 3) array of MediaPipe Pose world coordinates.
        body_conf: (33,) array of per-keypoint visibilities in [0, 1].
        head_anchor: (3,) world coordinate of the rotation pivot. Computed
            as the synthesized neck (mean of shoulders) when shoulders are
            present, else falls back to the nose.
        fit_metrics: telemetry recorded at fit time.
    """

    portrait_size: tuple[int, int]
    face_mesh: np.ndarray
    body_kps: np.ndarray
    body_conf: np.ndarray
    head_anchor: np.ndarray
    fit_metrics: FitMetrics

    @classmethod
    def from_portrait(cls, portrait_path: str | Path) -> "Rig":
        """Fit a Rig to the portrait at `portrait_path`."""
        path = Path(portrait_path)
        if not path.exists():
            raise OpenReposeRigFitError(f"portrait not found: {path}")

        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise OpenReposeRigFitError(f"cv2 could not read portrait: {path}")

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]

        t_start = time.perf_counter()
        face_mesh, body_kps, body_conf, partial, missing = _run_mediapipe(rgb)
        t_ms = int((time.perf_counter() - t_start) * 1000)

        if face_mesh.shape[0] == 0:
            raise OpenReposeRigFitError(
                f"MediaPipe FaceMesh detected no face on {path}"
            )

        # Head anchor / rotation pivot: synthesized neck (mean of MediaPipe
        # Pose anatomical-left shoulder index 11 and anatomical-right
        # shoulder index 12) when both are detected. Otherwise fall back to
        # the MediaPipe Pose nose (index 0), or finally the face-mesh nose
        # tip (FaceMesh index 4). The pivot must sit on the body's vertical
        # axis so the unified yaw rotates head and body together about a
        # single line.
        MP_POSE_LEFT_SHOULDER = 11
        MP_POSE_RIGHT_SHOULDER = 12
        MP_POSE_NOSE = 0
        if (
            body_conf[MP_POSE_LEFT_SHOULDER] > 0.3
            and body_conf[MP_POSE_RIGHT_SHOULDER] > 0.3
        ):
            head_anchor = 0.5 * (
                body_kps[MP_POSE_LEFT_SHOULDER] + body_kps[MP_POSE_RIGHT_SHOULDER]
            )
        elif body_conf[MP_POSE_NOSE] > 0.3:
            head_anchor = body_kps[MP_POSE_NOSE].copy()
        else:
            head_anchor = (
                face_mesh[4].copy() if face_mesh.shape[0] > 4 else np.zeros(3)
            )

        return cls(
            portrait_size=(w, h),
            face_mesh=face_mesh,
            body_kps=body_kps,
            body_conf=body_conf,
            head_anchor=head_anchor,
            fit_metrics=FitMetrics(
                portrait_path=str(path),
                portrait_width=w,
                portrait_height=h,
                face_landmark_count=int(face_mesh.shape[0]),
                body_landmark_count=int((body_conf > 0.0).sum()),
                fit_duration_ms=t_ms,
                body_partial=partial,
                body_partial_missing=tuple(missing),
            ),
        )

    def openpose_face_70(self) -> np.ndarray:
        """Return the 70-point OpenPose face landmark subset of `face_mesh`."""
        return map_face_mesh_to_openpose(self.face_mesh)

    def openpose_body_18(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (body_18 xyz, body_18 confidences) mapped from MediaPipe Pose."""
        return map_pose_to_body18(self.body_kps, self.body_conf)


# --- internal MediaPipe runners ---------------------------------------------


def _run_mediapipe(rgb_image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool, list[str]]:
    """Run FaceMesh + Pose. Returns (face_mesh, body_kps, body_conf, partial, missing).

    face_mesh shape: (478, 3) or (0, 3) on failure.
    body_kps shape:  (33, 3).
    body_conf shape: (33,).
    partial: True if some pose keypoints have visibility 0 (typical on bust portraits).
    missing: human-readable names of missing keypoint groups.
    """
    import mediapipe as mp  # type: ignore[import-untyped]

    h, w = rgb_image.shape[:2]

    # FaceMesh — refine_landmarks=True gives 478 points (468 mesh + 10 iris).
    face_mesh = np.zeros((0, 3), dtype=np.float32)
    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.4,
    ) as fm:
        result = fm.process(rgb_image)
        if result.multi_face_landmarks:
            lms = result.multi_face_landmarks[0].landmark
            face_mesh = np.array(
                [[lm.x * w, lm.y * h, lm.z * w] for lm in lms],
                dtype=np.float32,
            )

    # Pose — static_image_mode for single frame, model_complexity=2 (heavy).
    body_kps = np.zeros((33, 3), dtype=np.float32)
    body_conf = np.zeros((33,), dtype=np.float32)
    with mp.solutions.pose.Pose(
        static_image_mode=True,
        model_complexity=2,
        enable_segmentation=False,
        min_detection_confidence=0.4,
    ) as ps:
        result = ps.process(rgb_image)
        if result.pose_landmarks:
            for i, lm in enumerate(result.pose_landmarks.landmark):
                body_kps[i] = (lm.x * w, lm.y * h, lm.z * w)
                body_conf[i] = float(lm.visibility)

    # Calibrate Pose z into FaceMesh z scale.
    #
    # MediaPipe FaceMesh and Pose return z values in different internal
    # scales: FaceMesh z is head-relative (small magnitude, ~-0.1..+0.1
    # normalized -> ~-100..+100 px after *W), Pose z is body/image-
    # relative (magnitude ~10x larger). They cannot be mixed in a single
    # rigid 3D rotation as-is. We bring Pose z into FaceMesh's frame using
    # the nose as a common landmark: FaceMesh idx 4 (nose tip) and Pose
    # idx 0 (nose) describe the same physical point. Their z ratio gives
    # a per-portrait scale factor we apply to every Pose z.
    if face_mesh.shape[0] > 4 and body_conf[0] > 0.3:
        fm_nose_z = float(face_mesh[4, 2])
        pose_nose_z = float(body_kps[0, 2])
        if abs(pose_nose_z) > 1e-6:
            z_scale = fm_nose_z / pose_nose_z
            body_kps[:, 2] *= z_scale

    # Check which OpenPose body slots are missing.
    from .openpose_schema import MP_POSE_TO_BODY18

    name_by_op = {
        2: "right_shoulder",
        3: "right_elbow",
        4: "right_wrist",
        5: "left_shoulder",
        6: "left_elbow",
        7: "left_wrist",
        8: "right_hip",
        11: "left_hip",
    }
    missing: list[str] = []
    for op_idx, mp_idx in enumerate(MP_POSE_TO_BODY18):
        if mp_idx < 0:
            continue
        if op_idx in name_by_op and body_conf[mp_idx] < 0.3:
            missing.append(name_by_op[op_idx])

    partial = len(missing) > 0
    return face_mesh, body_kps, body_conf, partial, missing
