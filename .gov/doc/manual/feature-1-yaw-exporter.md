# Feature 1 — Yaw wireframe exporter

The first feature OpenRepose ships. Spec: `.gov/spec/openrepose_v0_1.md` § "Feature 1".

## What gets exported

Per export angle:

- `<slug>_yaw_<bin>.json` — OpenPose-format keypoint JSON. Pretty-printed (`indent=2`).
- `<slug>_yaw_<bin>.png` — rendered wireframe at the same canvas dimensions.

Batch exports also write `manifest.json` listing all files + the angles + the run timestamp.

## OpenPose schema

- `body_18` — 18 body keypoints (OpenPose / DWPose convention).
- `face_70` — 70 face keypoints (dlib-style ordering + 2 pupils).
- `hand_left_keypoints_2d` / `hand_right_keypoints_2d` — null/zeros in v0.1 (gated on WP-I1-018).

Schema mapping is documented in `.product/src/openrepose/openpose_schema.py`.

## Yaw bins

Standard 13: `0`, `her-left 15/30/45/60/75/90`, `her-right 15/30/45/60/75/90`. Optional rear bins: `her-left 105/120/150`, `her-right 105/120/150`, `180`.

File names sanitize spaces to dashes: `aeri_yaw_her-right-30.png`.

## Visibility

- Body-part toggles (Options tab → Body part visibility) suppress entire groups: `face` / `body_torso` / `arms` / `legs` / `hands`.
- Per-marker toggles (Tools → Markers) suppress individual keypoints. Per-marker overrides body-part group flags.
- Suppressed keypoints emit `[0.0, 0.0, 0.0]` in the JSON and are skipped in the rendered preview.

## Frame reframing

Tools → Reframer:

- **Scale** — `(kp - anchor) * scale + anchor + offset`. Line widths and dot sizes are canvas-pixel constants and stay invariant under any scale.
- **Offset** — pixel translation.
- **Anchor** — `head_anchor` (synthesized neck) or `canvas_center`.

A **canvas border** outline (default white, color in Options) shows where the canvas edges are when `frame_scale < 1.0` shrinks the figure away from them.
