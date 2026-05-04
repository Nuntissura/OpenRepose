# Feature 1 — Yaw wireframe exporter

The first feature OpenRepose ships. Spec: `.gov/spec/openrepose_v0_1.md` § "Feature 1".

## What gets exported

Per export angle:

- `<slug>_yaw_<bin>.json` — OpenPose-format keypoint JSON. Pretty-printed (`indent=2`).
- `<slug>_yaw_<bin>.png` — rendered wireframe at the same canvas dimensions.

Batch exports also write `manifest.json` listing all files + the angles + the run timestamp.

## Batch per-angle metadata

`export_batch` accepts optional `per_angle_metadata` for prompt seeds, sampler notes, workflow slugs, ControlNet strengths, or any other downstream dispatch data the operator/LLM wants to carry with the exported yaw set.

Accepted shapes:

```json
{
  "command": "export_batch",
  "angles": ["0", "her-left 15", "her-right 15"],
  "per_angle_metadata": [
    {"prompt_slug": "base", "seed": 1001},
    {"prompt_slug": "her-left-variant", "seed": 1002},
    {"prompt_slug": "her-right-variant", "seed": 1003}
  ]
}
```

```json
{
  "command": "export_batch",
  "per_angle_metadata": {
    "0": {"prompt_slug": "base"},
    "her-left 15": {"prompt_slug": "left-a"},
    "her-right 15": {"prompt_slug": "right-a"}
  }
}
```

The metadata is written only to `manifest.json`. It is not embedded in the OpenPose keypoint JSON files, so downstream DWPose/RenderPeopleKps compatibility stays clean. Unknown keys are preserved as data. A list length mismatch is rejected before files are written.

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

## Importing a portrait

Three operator-side paths land at the same `import_portrait` dispatcher command:

- **File → Open portrait...** (`Ctrl+O`) — file picker, opens at the last-used folder.
- **Drag-and-drop** (WP-I1-005) — drag a `.png` / `.jpg` / `.jpeg` from Explorer onto the main window or either viewport. Multi-file drop accepts the first image and logs `import.drop_multi_file` listing the rest; `.lnk` shell links and non-image files are rejected with `import.drop_rejected`. True multi-file workspace (tabs + per-file state) is WP-I1-036.
- **Headless** — LLM agent dispatches `{"command": "import_portrait", "path": "...", "avatar_slug": "..."}` over the HTTP or inbox channel.

The avatar slug used on import comes from the Options tab when set, otherwise it is sanitized from the filename stem.

## Clearing the workspace

WP-I1-016 added a **Clear workspace** action that drops the active document's rig, resets yaw to `0`, and clears the loaded portrait. Settings, log, body-part visibility, marker visibility, and calibration are NOT touched. The action is reachable from:

- **Toolbar** — the "Clear workspace" button immediately next to **Open**.
- **Edit → Clear workspace** menu entry.
- **Headless** — `{"command": "clear_workspace"}`. Returns `{cleared: true, portrait: null, avatar_slug: null, rig, yaw}`.

Distinct from `clear_outputs`, which only purges the in-memory exports/snapshots/errors arrays. Scope is the active document only — when WP-I1-036 multi-file lands, other tabs remain untouched.

## Operator settings persistence

Operator settings (export folder, subdir templates, library DB URL, operator slug, canvas border color, last-portrait folder, …) persist across launches at the OS-native config path: `%APPDATA%\openrepose\settings.json` on Windows, `~/.config/openrepose/settings.json` on Linux, `~/Library/Preferences/openrepose/settings.json` on macOS. Atomic writes, JSON-on-disk, schema-versioned with forward migration.

Headless surface (WP-I1-003 added `set_settings` + `clear_settings` alongside the existing `dump_settings`):

- `dump_settings` — return the effective settings JSON (with `library_db_url` redacted), the resolved export folder, and whether the default fallback is in use.
- `set_settings` — body `{"fields": {"export_folder": "...", "operator_slug": "..."}}`. Patches one or more fields; unknown fields are rejected and the on-disk file is left untouched.
- `clear_settings` — reset every operator-managed field back to its default and persist. `settings_path` and `schema_version` are preserved.

`library_db_url` is always returned redacted (`postgresql://user:***@host/db`) in command responses; the unredacted value lives in `settings.json` and is consumed internally by the dispatcher.


## Hand keypoints (WP-I1-018)

When visible hands are detected, OpenRepose emits OpenPose-compatible `hand_left_keypoints_2d` and `hand_right_keypoints_2d` arrays with 21 `(x, y, confidence)` triples per hand. Undetected hands stay zeroed so downstream OpenPose/DWPose renderers suppress them cleanly.

Runtime note: OpenRepose prefers MediaPipe Tasks `HandLandmarker` when `OPENREPOSE_HAND_LANDMARKER_TASK` points at a local `.task` model. If no Tasks model is configured, it falls back to the bundled legacy MediaPipe Hands path. `state.rig.hands_unavailable` tells an LLM agent whether the detector path was unavailable rather than merely finding no hands.
