# Feature 2 — Per-avatar calibration overlay

The second feature. Spec: `.gov/spec/openrepose_v0_1.md` § "Feature 2".

## Why

MediaPipe FaceMesh fits a canonical face mesh trained on average human proportions. Stylized avatars (oversized eyes, narrow jaws, extra-wide thin mouths) get normalized toward average. Rotated wireframes inherit the bias and look "off".

Calibration corrects this with a thin-plate-spline (TPS) deformation field that maps detected MediaPipe positions to operator-marked positions.

## Marker vocabulary

Required (6): `eye_outer_left`, `eye_outer_right`, `mouth_corner_left`, `mouth_corner_right`, `jaw_corner_left`, `jaw_corner_right`.

Optional (4): `brow_outer_left`, `brow_outer_right`, `nose_tip`, `chin_bottom`.

Naming follows the her-anatomy convention: `_left` = the avatar's anatomical left.

## How to mark (Tools → Calibration)

1. **Pick a marker name** in the dropdown (default is `— pick one —`; nothing happens until you pick).
2. **Click on the portrait** at the actual feature location.
3. The system stores: `operator_xy` = your click; `mediapipe_xy` = where MediaPipe detected that feature (or your click if no detection).
4. Repeat for all 6 required markers (and any optional ones you want).

The TPS field is computed and applied to face + body landmark XY before rotation. Z values pass through unchanged.

## Overview mode

Pick **Overview (drag any marker)** in the dropdown. All your placed operator markers become draggable — left-click and drag to reposition. Right-click any operator marker to delete it (dispatches the `delete_markers` command).

## Always-on auto-detected dots

The dim dots labeled `eye_outer_left`, `mouth_corner_right`, etc. are MediaPipe's auto-detected positions, shown immediately on portrait load. Use these as a reference for where to place your operator marker.

## Zoom + pan

- **Mouse wheel** — zoom anchored under cursor.
- **Spacebar + left-click + drag** — pan (Photoshop convention).
- **Reset zoom** button — fit-to-view.

## "No detection" markers

Some markers may not have a MediaPipe detection (FaceMesh missed it). The Markers tab annotates these with `— no detection` in dim text. In Calibration tab, picking such a marker and clicking treats your click as both `operator_xy` and `mediapipe_xy` (operator-supplied detection).

## Persistence

Each avatar's calibration is stored as `outputs/<slug>/calibration.json`. Auto-loaded on next `import_portrait` for the same slug.

## LLM commands

- `set_calibration_points` — payload `{markers: [{name, operator_xy, mediapipe_xy?}, ...], merge: bool}`.
- `dump_calibration` — read the active avatar's full calibration JSON.
- `clear_calibration` — wipe.
- `delete_markers` — payload `{names: [str, ...]}`.
- `get_calibration_status` — read-only state mirror.

`calibration_overlay` snapshot target writes a PNG showing the operator markers + dim auto-detected dots.
