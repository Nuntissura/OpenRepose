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

import os
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from .openpose_schema import (
    BODY_NOSE,
    map_face_mesh_to_openpose,
    map_pose_to_body18,
)

if TYPE_CHECKING:
    from .calibration import Calibration


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
    hand_landmark_count: int = 0
    hand_left_detected: bool = False
    hand_right_detected: bool = False
    hands_unavailable: bool = False


@dataclass(frozen=True)
class Rig:
    """Locked 3D rig from a frontal portrait.

    Attributes:
        portrait_size: (width, height) of the source portrait in pixels.
        face_mesh: (478, 3) array. MediaPipe FaceMesh world coordinates
            (x in pixels, y in pixels, z in width-scaled units). Calibrated
            (via the per-avatar TPS field) when `calibration` is set,
            otherwise identical to `raw_face_mesh`.
        body_kps: (33, 3) array of MediaPipe Pose world coordinates. Same
            calibration semantics as `face_mesh`.
        body_conf: (33,) array of per-keypoint visibilities in [0, 1].
        head_anchor: (3,) world coordinate of the rotation pivot.
        fit_metrics: telemetry recorded at fit time.
        raw_face_mesh: pre-calibration FaceMesh coords (for re-applying a
            different calibration without re-running MediaPipe). When None,
            no calibration was ever applied and `face_mesh` is the raw
            detection.
        raw_body_kps: pre-calibration Pose coords (same semantics).
        calibration: the active per-avatar calibration record, or None.
    """

    portrait_size: tuple[int, int]
    face_mesh: np.ndarray
    body_kps: np.ndarray
    body_conf: np.ndarray
    head_anchor: np.ndarray
    fit_metrics: FitMetrics
    raw_face_mesh: np.ndarray | None = None
    raw_body_kps: np.ndarray | None = None
    calibration: "Calibration | None" = None
    hand_left_kps: np.ndarray = field(default_factory=lambda: np.zeros((21, 3), dtype=np.float32))
    hand_right_kps: np.ndarray = field(default_factory=lambda: np.zeros((21, 3), dtype=np.float32))
    hand_left_conf: np.ndarray = field(default_factory=lambda: np.zeros((21,), dtype=np.float32))
    hand_right_conf: np.ndarray = field(default_factory=lambda: np.zeros((21,), dtype=np.float32))
    raw_hand_left_kps: np.ndarray | None = None
    raw_hand_right_kps: np.ndarray | None = None

    @classmethod
    def from_portrait(
        cls,
        portrait_path: str | Path,
        *,
        calibration: "Calibration | None" = None,
    ) -> "Rig":
        """Fit a Rig to the portrait at `portrait_path`.

        When `calibration` is supplied, the TPS deformation field is computed
        from its markers (plus 4 implicit corner clamps) and applied to face
        and body landmark XY coordinates before head_anchor is computed.
        """
        path = Path(portrait_path)
        if not path.exists():
            raise OpenReposeRigFitError(f"portrait not found: {path}")

        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise OpenReposeRigFitError(f"cv2 could not read portrait: {path}")

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]

        t_start = time.perf_counter()
        (
            face_mesh,
            body_kps,
            body_conf,
            hand_left,
            hand_left_conf,
            hand_right,
            hand_right_conf,
            hands_unavailable,
            partial,
            missing,
        ) = _run_mediapipe(rgb)
        t_ms = int((time.perf_counter() - t_start) * 1000)

        if face_mesh.shape[0] == 0:
            raise OpenReposeRigFitError(
                f"MediaPipe FaceMesh detected no face on {path}"
            )

        raw_face_mesh = face_mesh.copy()
        raw_body_kps = body_kps.copy()
        raw_hand_left = hand_left.copy()
        raw_hand_right = hand_right.copy()

        # Apply per-avatar calibration to landmark XY before head_anchor so
        # the synthesized neck reflects the operator's marks. Z passes
        # through unchanged.
        if calibration is not None:
            from .calibration import compute_field

            cal_field = compute_field(calibration, image_size=(w, h))
            if cal_field is not None:
                face_mesh = face_mesh.copy()
                body_kps = body_kps.copy()
                hand_left = hand_left.copy()
                hand_right = hand_right.copy()
                face_mesh[:, :2] = cal_field.apply(
                    face_mesh[:, :2].astype(np.float64)
                )
                body_kps[:, :2] = cal_field.apply(
                    body_kps[:, :2].astype(np.float64)
                )
                if self.hand_left_conf.max(initial=0.0) > 0.0:
                    hand_left[:, :2] = cal_field.apply(
                        hand_left[:, :2].astype(np.float64)
                    )
                if self.hand_right_conf.max(initial=0.0) > 0.0:
                    hand_right[:, :2] = cal_field.apply(
                        hand_right[:, :2].astype(np.float64)
                    )
                if hand_left_conf.max(initial=0.0) > 0.0:
                    hand_left[:, :2] = cal_field.apply(
                        hand_left[:, :2].astype(np.float64)
                    )
                if hand_right_conf.max(initial=0.0) > 0.0:
                    hand_right[:, :2] = cal_field.apply(
                        hand_right[:, :2].astype(np.float64)
                    )

        head_anchor = _compute_head_anchor(face_mesh, body_kps, body_conf)

        hand_count = int((hand_left_conf > 0.0).sum() + (hand_right_conf > 0.0).sum())

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
                hand_landmark_count=hand_count,
                hand_left_detected=bool(hand_left_conf.max(initial=0.0) > 0.0),
                hand_right_detected=bool(hand_right_conf.max(initial=0.0) > 0.0),
                hands_unavailable=bool(hands_unavailable),
            ),
            raw_face_mesh=raw_face_mesh,
            raw_body_kps=raw_body_kps,
            calibration=calibration,
            hand_left_kps=hand_left,
            hand_right_kps=hand_right,
            hand_left_conf=hand_left_conf,
            hand_right_conf=hand_right_conf,
            raw_hand_left_kps=raw_hand_left,
            raw_hand_right_kps=raw_hand_right,
        )

    def with_calibration(self, new_calibration: "Calibration | None") -> "Rig":
        """Return a new Rig with `new_calibration` applied to the cached raw
        landmarks. Cheap: no MediaPipe re-run, just a TPS field rebuild and
        coordinate transform. Falls back to `face_mesh` / `body_kps` if no
        raw cache is present (Rigs constructed directly without going
        through `from_portrait`)."""
        from .calibration import compute_field

        raw_face = (
            self.raw_face_mesh
            if self.raw_face_mesh is not None
            else self.face_mesh
        )
        raw_body = (
            self.raw_body_kps
            if self.raw_body_kps is not None
            else self.body_kps
        )

        raw_hand_left = (
            self.raw_hand_left_kps
            if self.raw_hand_left_kps is not None
            else self.hand_left_kps
        )
        raw_hand_right = (
            self.raw_hand_right_kps
            if self.raw_hand_right_kps is not None
            else self.hand_right_kps
        )

        face_mesh = raw_face.copy()
        body_kps = raw_body.copy()
        hand_left = raw_hand_left.copy()
        hand_right = raw_hand_right.copy()

        if new_calibration is not None:
            cal_field = compute_field(
                new_calibration, image_size=self.portrait_size
            )
            if cal_field is not None:
                face_mesh[:, :2] = cal_field.apply(
                    face_mesh[:, :2].astype(np.float64)
                )
                body_kps[:, :2] = cal_field.apply(
                    body_kps[:, :2].astype(np.float64)
                )

        head_anchor = _compute_head_anchor(
            face_mesh, body_kps, self.body_conf
        )

        return replace(
            self,
            face_mesh=face_mesh,
            body_kps=body_kps,
            head_anchor=head_anchor,
            raw_face_mesh=raw_face,
            raw_body_kps=raw_body,
            calibration=new_calibration,
            hand_left_kps=hand_left,
            hand_right_kps=hand_right,
            raw_hand_left_kps=raw_hand_left,
            raw_hand_right_kps=raw_hand_right,
        )

    def openpose_face_70(self) -> np.ndarray:
        """Return the 70-point OpenPose face landmark subset of `face_mesh`."""
        return map_face_mesh_to_openpose(self.face_mesh)

    def openpose_body_18(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (body_18 xyz, body_18 confidences) mapped from MediaPipe Pose."""
        return map_pose_to_body18(self.body_kps, self.body_conf)

    def openpose_hands_21(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return left/right hand landmark arrays plus confidences."""
        return (
            self.hand_left_kps.copy(),
            self.hand_left_conf.copy(),
            self.hand_right_kps.copy(),
            self.hand_right_conf.copy(),
        )


# --- helpers ----------------------------------------------------------------


def _compute_head_anchor(
    face_mesh: np.ndarray,
    body_kps: np.ndarray,
    body_conf: np.ndarray,
) -> np.ndarray:
    """Synthesized neck (mean of shoulders) when both are detected; else
    fall back to MediaPipe Pose nose, then FaceMesh nose tip. The pivot
    must sit on the body's vertical axis so unified yaw rotates head and
    body together about a single line."""
    MP_POSE_LEFT_SHOULDER = 11
    MP_POSE_RIGHT_SHOULDER = 12
    MP_POSE_NOSE = 0
    if (
        body_conf[MP_POSE_LEFT_SHOULDER] > 0.3
        and body_conf[MP_POSE_RIGHT_SHOULDER] > 0.3
    ):
        return 0.5 * (
            body_kps[MP_POSE_LEFT_SHOULDER]
            + body_kps[MP_POSE_RIGHT_SHOULDER]
        )
    if body_conf[MP_POSE_NOSE] > 0.3:
        return body_kps[MP_POSE_NOSE].copy()
    return face_mesh[4].copy() if face_mesh.shape[0] > 4 else np.zeros(3)


# --- internal MediaPipe runners ---------------------------------------------


def _run_mediapipe(
    rgb_image: np.ndarray,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    bool,
    bool,
    list[str],
]:
    """Run FaceMesh + Pose + Hands. Returns landmark arrays, partial, missing.

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

    hand_left, hand_left_conf, hand_right, hand_right_conf, hands_unavailable = _run_hands(
        rgb_image, mp, body_kps, body_conf
    )

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
    return (
        face_mesh,
        body_kps,
        body_conf,
        hand_left,
        hand_left_conf,
        hand_right,
        hand_right_conf,
        hands_unavailable,
        partial,
        missing,
    )


def _run_hands(
    rgb_image: np.ndarray,
    mp: Any,
    body_kps: np.ndarray,
    body_conf: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool]:
    """Run hand detection.

    Prefer MediaPipe Tasks when OPENREPOSE_HAND_LANDMARKER_TASK points at a
    `.task` model file; fall back to legacy MediaPipe Hands so OpenRepose keeps
    working when no model asset is bundled.
    """
    h, w = rgb_image.shape[:2]
    left = np.zeros((21, 3), dtype=np.float32)
    right = np.zeros((21, 3), dtype=np.float32)
    left_conf = np.zeros((21,), dtype=np.float32)
    right_conf = np.zeros((21,), dtype=np.float32)

    task_model = os.environ.get("OPENREPOSE_HAND_LANDMARKER_TASK", "").strip()
    if task_model and Path(task_model).exists():
        try:
            from mediapipe.tasks import python as mp_python  # type: ignore[import-untyped]
            from mediapipe.tasks.python import vision  # type: ignore[import-untyped]

            options = vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=task_model),
                running_mode=vision.RunningMode.IMAGE,
                num_hands=2,
                min_hand_detection_confidence=0.4,
                min_hand_presence_confidence=0.4,
            )
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
            with vision.HandLandmarker.create_from_options(options) as landmarker:
                result = landmarker.detect(mp_image)
            for lms, handedness in zip(result.hand_landmarks, result.handedness):
                label, score = _handedness_label_score(handedness)
                pts = np.array([[lm.x * w, lm.y * h, lm.z * w] for lm in lms], dtype=np.float32)
                pts = _align_hand_z(label, pts, body_kps, body_conf)
                if label == "Left" and left_conf.max(initial=0.0) == 0.0:
                    left[:] = pts
                    left_conf[:] = float(score)
                elif label == "Right" and right_conf.max(initial=0.0) == 0.0:
                    right[:] = pts
                    right_conf[:] = float(score)
            return left, left_conf, right, right_conf, False
        except Exception:
            pass

    try:
        with mp.solutions.hands.Hands(
            static_image_mode=True,
            max_num_hands=2,
            model_complexity=1,
            min_detection_confidence=0.4,
        ) as hs:
            result = hs.process(rgb_image)
            if result.multi_hand_landmarks:
                handedness_list = result.multi_handedness or []
                for idx, hand_lms in enumerate(result.multi_hand_landmarks):
                    label, score = _handedness_label_score(
                        handedness_list[idx].classification if idx < len(handedness_list) else None
                    )
                    pts = np.array(
                        [[lm.x * w, lm.y * h, lm.z * w] for lm in hand_lms.landmark],
                        dtype=np.float32,
                    )
                    pts = _align_hand_z(label, pts, body_kps, body_conf)
                    if label == "Left" and left_conf.max(initial=0.0) == 0.0:
                        left[:] = pts
                        left_conf[:] = float(score)
                    elif label == "Right" and right_conf.max(initial=0.0) == 0.0:
                        right[:] = pts
                        right_conf[:] = float(score)
        return left, left_conf, right, right_conf, False
    except Exception:
        return left, left_conf, right, right_conf, True


def _handedness_label_score(raw: Any) -> tuple[str, float]:
    if raw is None:
        return "Right", 0.5
    try:
        item = raw[0]
    except Exception:
        item = raw
    label = (
        getattr(item, "category_name", None)
        or getattr(item, "label", None)
        or getattr(item, "display_name", None)
    )
    score = getattr(item, "score", None)
    label = "Left" if str(label).lower() == "left" else "Right"
    try:
        score_f = float(score)
    except Exception:
        score_f = 0.5
    return label, max(0.0, min(1.0, score_f))


def _align_hand_z(
    label: str,
    hand_kps: np.ndarray,
    body_kps: np.ndarray,
    body_conf: np.ndarray,
) -> np.ndarray:
    mp_wrist = 15 if label == "Left" else 16
    if 0 <= mp_wrist < body_conf.shape[0] and body_conf[mp_wrist] > 0.3:
        wrist_z = float(hand_kps[0, 2])
        hand_kps = hand_kps.copy()
        hand_kps[:, 2] = (hand_kps[:, 2] - wrist_z) + float(body_kps[mp_wrist, 2])
    return hand_kps
