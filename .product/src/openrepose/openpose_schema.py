"""Index maps from MediaPipe to OpenPose schemas.

OpenPose body_18 schema (the schema OpenPoseXL2 ControlNet was trained on):

    0: nose, 1: neck (synthesized as shoulder midpoint),
    2: right_shoulder (anatomical), 3: right_elbow, 4: right_wrist,
    5: left_shoulder (anatomical), 6: left_elbow, 7: left_wrist,
    8: right_hip, 9: right_knee, 10: right_ankle,
    11: left_hip, 12: left_knee, 13: left_ankle,
    14: right_eye, 15: left_eye, 16: right_ear, 17: left_ear

OpenPose 70-point face schema (dlib-style ordering):

    0-16: jaw outline (17 pts), traversed from the anatomical-right corner
          (which projects to the -x edge of a frontal photograph) across the
          chin to the anatomical-left corner (+x edge of a frontal photograph)
    17-21: right eyebrow (anatomical right, 5 pts)
    22-26: left eyebrow (anatomical left, 5 pts)
    27-30: nose bridge (4 pts)
    31-35: nose bottom (5 pts)
    36-41: right eye (anatomical right, 6 pts)
    42-47: left eye (anatomical left, 6 pts)
    48-59: outer mouth (12 pts)
    60-67: inner mouth (8 pts)
    68: right pupil (anatomical right)
    69: left pupil (anatomical left)

MediaPipe Pose 33-keypoint schema and MediaPipe FaceMesh 478-vertex mesh
indices are documented at https://developers.google.com/mediapipe.

MediaPipe uses subject-anatomical left/right (left_shoulder = anatomical
left), matching OpenPose body_18's convention. No mirror-flip required.
"""

from __future__ import annotations

# MediaPipe Pose 33 -> OpenPose body_18.
#
# Index of this list = OpenPose body_18 index. Value = MediaPipe Pose 33 index.
# A value of -1 means "synthesize" (handled in code).
#
# Synthesized: neck (1) = mean of MP left_shoulder (11) and right_shoulder (12).
MP_POSE_TO_BODY18: tuple[int, ...] = (
    0,    # 0  nose                <- MP 0  nose
    -1,   # 1  neck                <- synthesized (mean of MP 11, 12)
    12,   # 2  right_shoulder      <- MP 12 right_shoulder
    14,   # 3  right_elbow         <- MP 14 right_elbow
    16,   # 4  right_wrist         <- MP 16 right_wrist
    11,   # 5  left_shoulder       <- MP 11 left_shoulder
    13,   # 6  left_elbow          <- MP 13 left_elbow
    15,   # 7  left_wrist          <- MP 15 left_wrist
    24,   # 8  right_hip           <- MP 24 right_hip
    26,   # 9  right_knee          <- MP 26 right_knee
    28,   # 10 right_ankle         <- MP 28 right_ankle
    23,   # 11 left_hip            <- MP 23 left_hip
    25,   # 12 left_knee           <- MP 25 left_knee
    27,   # 13 left_ankle          <- MP 27 left_ankle
    5,    # 14 right_eye           <- MP 5  right_eye (center)
    2,    # 15 left_eye            <- MP 2  left_eye (center)
    8,    # 16 right_ear           <- MP 8  right_ear
    7,    # 17 left_ear            <- MP 7  left_ear
)

# OpenPose body_18 index aliases (for code clarity).
BODY_NOSE = 0
BODY_NECK = 1
BODY_R_SHOULDER = 2
BODY_R_ELBOW = 3
BODY_R_WRIST = 4
BODY_L_SHOULDER = 5
BODY_L_ELBOW = 6
BODY_L_WRIST = 7
BODY_R_HIP = 8
BODY_R_KNEE = 9
BODY_R_ANKLE = 10
BODY_L_HIP = 11
BODY_L_KNEE = 12
BODY_L_ANKLE = 13
BODY_R_EYE = 14
BODY_L_EYE = 15
BODY_R_EAR = 16
BODY_L_EAR = 17

# MediaPipe FaceMesh 478 -> OpenPose 70-point face.
#
# Index of this list = OpenPose 70 index. Value = MediaPipe FaceMesh 478 index.
#
# Source: well-known mapping used in several open-source MediaPipe-to-dlib
# converters. The OpenPose 70 ordering matches dlib's 68 + 2 pupils.
MP_FACEMESH_TO_OPENPOSE_70: tuple[int, ...] = (
    # Jaw outline 0-16 (17 pts), -x edge of frontal frame across chin to +x edge
    234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152,
    377, 400, 378, 379, 365, 397,
    # Right eyebrow 17-21 (anatomical right, 5 pts)
    70, 63, 105, 66, 107,
    # Left eyebrow 22-26 (anatomical left, 5 pts)
    336, 296, 334, 293, 300,
    # Nose bridge 27-30 (4 pts, top to tip)
    168, 6, 195, 4,
    # Nose bottom 31-35 (5 pts, anat-right nostril to anat-left nostril)
    98, 97, 2, 326, 327,
    # Right eye 36-41 (anatomical right, 6 pts)
    33, 160, 158, 133, 153, 144,
    # Left eye 42-47 (anatomical left, 6 pts)
    362, 385, 387, 263, 373, 380,
    # Outer mouth 48-59 (12 pts)
    61, 39, 37, 0, 267, 269, 291, 405, 314, 17, 84, 181,
    # Inner mouth 60-67 (8 pts)
    78, 81, 13, 311, 308, 402, 14, 178,
    # Pupils 68-69 (refined-landmarks output of FaceMesh)
    468, 473,
)

OPENPOSE_FACE_COUNT = 70
OPENPOSE_BODY_COUNT = 18
OPENPOSE_HAND_COUNT = 21
MEDIAPIPE_FACEMESH_COUNT = 478
MEDIAPIPE_POSE_COUNT = 33

assert len(MP_FACEMESH_TO_OPENPOSE_70) == OPENPOSE_FACE_COUNT, "face map length mismatch"
assert len(MP_POSE_TO_BODY18) == OPENPOSE_BODY_COUNT, "body map length mismatch"

# OpenPose / MediaPipe hand topology: wrist + 4 joints per finger.
OPENPOSE_HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
)


# --- per-body-part visibility (WP-I1-017) -----------------------------------

# Coarse-grained visibility groups operator can toggle on/off. The `face`
# group covers BOTH the face landmarks present in body_18 AND the entire
# face_70 array. The `hands` group is reserved for WP-I1-018 hand detection;
# in v0.1 it has no body_18 indices to suppress (hand_*_keypoints_2d in the
# OpenPose JSON are already null/zeros). Naming follows the spec.
BODY_GROUPS: tuple[str, ...] = (
    "face",
    "body_torso",
    "arms",
    "legs",
    "hands",
)

BODY_18_INDICES_BY_GROUP: dict[str, tuple[int, ...]] = {
    "face": (BODY_NOSE, BODY_R_EYE, BODY_L_EYE, BODY_R_EAR, BODY_L_EAR),
    "body_torso": (
        BODY_NECK,
        BODY_R_SHOULDER,
        BODY_L_SHOULDER,
        BODY_R_HIP,
        BODY_L_HIP,
    ),
    "arms": (BODY_R_ELBOW, BODY_R_WRIST, BODY_L_ELBOW, BODY_L_WRIST),
    "legs": (BODY_R_KNEE, BODY_R_ANKLE, BODY_L_KNEE, BODY_L_ANKLE),
    "hands": (),
}


def default_body_part_visibility() -> dict[str, bool]:
    """All groups visible. The default state.json `body_part_visibility` block."""
    return {g: True for g in BODY_GROUPS}


def apply_body_part_visibility(
    body18_visible,  # numpy bool / float array of shape (18,)
    face70_visible,  # numpy bool array of shape (70,)
    mask: dict[str, bool] | None,
):
    """Apply group flags to (body18_visible, face70_visible).

    Returns new arrays with suppressed groups zeroed; original arrays
    unchanged. If `mask` is None or all-true, returns the inputs as-is.
    Unknown group names raise ValueError so callers can surface a
    structured error.
    """
    if mask is None:
        return body18_visible, face70_visible
    # Validate keys first so an early-return on "all true" still rejects
    # bogus group names.
    for group in mask:
        if group not in BODY_GROUPS:
            raise ValueError(
                f"unknown body_part group: {group!r}; allowed: {BODY_GROUPS}"
            )
    if all(mask.get(g, True) for g in BODY_GROUPS):
        return body18_visible, face70_visible
    import numpy as np

    body18 = np.asarray(body18_visible).copy()
    face70 = np.asarray(face70_visible).copy()
    for group, visible in mask.items():
        if visible:
            continue
        if group == "face":
            face70[:] = False if face70.dtype == bool else 0
            for idx in BODY_18_INDICES_BY_GROUP["face"]:
                body18[idx] = False if body18.dtype == bool else 0
        else:
            for idx in BODY_18_INDICES_BY_GROUP[group]:
                body18[idx] = False if body18.dtype == bool else 0
    return body18, face70


# --- per-marker visibility (WP-I1-029) --------------------------------------

MARKER_SCHEMAS: tuple[str, ...] = ("body_18", "face_70")
_SCHEMA_COUNT: dict[str, int] = {
    "body_18": OPENPOSE_BODY_COUNT,
    "face_70": OPENPOSE_FACE_COUNT,
}


def default_marker_visibility() -> dict[str, dict[str, bool]]:
    """Empty per-schema override dicts. Empty = no individual overrides;
    every marker inherits its body-part group's visibility."""
    return {schema: {} for schema in MARKER_SCHEMAS}


def apply_marker_visibility(
    body18_visible,
    face70_visible,
    marker_visibility: dict | None,
):
    """Apply per-marker overrides on top of group flags.

    `marker_visibility` shape: `{"body_18": {<int_index>: bool, ...},
    "face_70": {<int_index>: bool, ...}}`. Indices may be int or stringified
    int (JSON-friendly). Per-marker entries are the authoritative override:
    an explicit True keeps the marker visible even if its group is off; an
    explicit False suppresses it even if its group is on.

    Unknown schema name raises ValueError. Out-of-range index raises
    IndexError. Empty / missing dicts are no-ops.
    """
    if marker_visibility is None:
        return body18_visible, face70_visible
    for schema in marker_visibility:
        if schema not in MARKER_SCHEMAS:
            raise ValueError(
                f"unknown marker schema {schema!r}; allowed: {MARKER_SCHEMAS}"
            )
    body_overrides = marker_visibility.get("body_18", {}) or {}
    face_overrides = marker_visibility.get("face_70", {}) or {}
    if not body_overrides and not face_overrides:
        return body18_visible, face70_visible

    import numpy as np

    body18 = np.asarray(body18_visible).copy()
    face70 = np.asarray(face70_visible).copy()

    for raw_idx, visible in body_overrides.items():
        idx = int(raw_idx)
        if not (0 <= idx < _SCHEMA_COUNT["body_18"]):
            raise IndexError(
                f"body_18 index {idx} out of range [0, {_SCHEMA_COUNT['body_18']})"
            )
        if body18.dtype == bool:
            body18[idx] = bool(visible)
        else:
            body18[idx] = 1.0 if visible else 0.0

    for raw_idx, visible in face_overrides.items():
        idx = int(raw_idx)
        if not (0 <= idx < _SCHEMA_COUNT["face_70"]):
            raise IndexError(
                f"face_70 index {idx} out of range [0, {_SCHEMA_COUNT['face_70']})"
            )
        if face70.dtype == bool:
            face70[idx] = bool(visible)
        else:
            face70[idx] = 1.0 if visible else 0.0

    return body18, face70


# --- frame reframing (WP-I1-023) --------------------------------------------

ANCHOR_MODES: tuple[str, ...] = ("head_anchor", "canvas_center", "custom")


def default_frame() -> dict:
    """Identity frame: no scale change, no offset, head_anchor mode."""
    return {
        "scale": 1.0,
        "offset_x": 0,
        "offset_y": 0,
        "anchor_mode": "head_anchor",
        "anchor_point": None,
    }


def resolve_frame_anchor(
    mode: str,
    point,
    head_anchor_xy,
    canvas_size: tuple[int, int],
):
    """Resolve a frame anchor to a 2D pixel coord."""
    import numpy as np

    if mode == "head_anchor":
        if head_anchor_xy is None:
            # Fallback: canvas center.
            return np.array(
                [canvas_size[0] / 2.0, canvas_size[1] / 2.0],
                dtype=np.float64,
            )
        return np.asarray(head_anchor_xy, dtype=np.float64)
    if mode == "canvas_center":
        return np.array(
            [canvas_size[0] / 2.0, canvas_size[1] / 2.0],
            dtype=np.float64,
        )
    if mode == "custom":
        if point is None:
            raise ValueError(
                "anchor_mode 'custom' requires anchor_point as [x, y]"
            )
        return np.asarray(point, dtype=np.float64)
    raise ValueError(
        f"unknown anchor_mode {mode!r}; allowed: {ANCHOR_MODES}"
    )


def apply_frame_to_keypoints(
    kp_xy,
    frame: dict | None,
    head_anchor_xy,
    canvas_size: tuple[int, int],
):
    """Apply `(kp - anchor) * scale + anchor + offset` to an (N, 2) array.

    `frame` is the state.frame dict. If None or identity, returns the input
    array unchanged. Out-of-canvas keypoints are emitted unchanged (the
    renderer + serializer apply their own clip semantics).
    """
    if frame is None:
        return kp_xy
    scale = float(frame.get("scale", 1.0))
    offset = (
        float(frame.get("offset_x", 0)),
        float(frame.get("offset_y", 0)),
    )
    if scale == 1.0 and offset == (0.0, 0.0):
        return kp_xy

    import numpy as np

    anchor = resolve_frame_anchor(
        frame.get("anchor_mode", "head_anchor"),
        frame.get("anchor_point"),
        head_anchor_xy,
        canvas_size,
    )
    arr = np.asarray(kp_xy, dtype=np.float64)
    return (arr - anchor) * scale + anchor + np.array(offset, dtype=np.float64)


def map_face_mesh_to_openpose(mp_mesh_xyz):
    """Take a (478, 3) MediaPipe FaceMesh array and return (70, 3) in OpenPose order.

    Pupil indices 468 and 473 only exist when refined_landmarks=True (which
    OpenRepose enables). If the input array has fewer than 478 points, pupil
    rows in the output are zero (with confidence handled separately by caller).
    """
    import numpy as np

    arr = np.asarray(mp_mesh_xyz)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(
            f"mp_mesh_xyz must have shape (N, 3); got {arr.shape}"
        )
    out = np.zeros((OPENPOSE_FACE_COUNT, 3), dtype=arr.dtype)
    n_in = arr.shape[0]
    for op_idx, mp_idx in enumerate(MP_FACEMESH_TO_OPENPOSE_70):
        if 0 <= mp_idx < n_in:
            out[op_idx] = arr[mp_idx]
    return out


def map_pose_to_body18(mp_pose_xyz, mp_pose_visibility=None):
    """Take a (33, 3) MediaPipe Pose array and return (18, 3) in OpenPose body_18 order.

    Synthesizes the neck (idx 1) as the midpoint of left_shoulder and right_shoulder.
    Returns also a (18,) confidence array. Confidence is taken from
    mp_pose_visibility when provided; the synthesized neck takes the min of the
    two shoulder confidences.
    """
    import numpy as np

    arr = np.asarray(mp_pose_xyz)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(
            f"mp_pose_xyz must have shape (N, 3); got {arr.shape}"
        )
    if mp_pose_visibility is None:
        vis = np.ones((arr.shape[0],), dtype=arr.dtype)
    else:
        vis = np.asarray(mp_pose_visibility, dtype=arr.dtype)

    out = np.zeros((OPENPOSE_BODY_COUNT, 3), dtype=arr.dtype)
    out_conf = np.zeros((OPENPOSE_BODY_COUNT,), dtype=arr.dtype)

    n_in = arr.shape[0]
    for op_idx, mp_idx in enumerate(MP_POSE_TO_BODY18):
        if mp_idx == -1:
            continue
        if 0 <= mp_idx < n_in:
            out[op_idx] = arr[mp_idx]
            out_conf[op_idx] = vis[mp_idx]

    # Synthesize neck (op_idx 1) as mean of shoulders if both present.
    l_sh_mp = MP_POSE_TO_BODY18[BODY_L_SHOULDER]
    r_sh_mp = MP_POSE_TO_BODY18[BODY_R_SHOULDER]
    if 0 <= l_sh_mp < n_in and 0 <= r_sh_mp < n_in:
        out[BODY_NECK] = 0.5 * (arr[l_sh_mp] + arr[r_sh_mp])
        out_conf[BODY_NECK] = min(float(vis[l_sh_mp]), float(vis[r_sh_mp]))

    return out, out_conf
