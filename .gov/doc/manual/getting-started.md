# Getting started

## First launch

```powershell
.\.venv\Scripts\python.exe -m openrepose.cli gui
```

Optional flags:

- `--inbox` — also watch `outputs/.runtime/inbox/` for LLM commands.
- `--http-port 8765` — also expose the HTTP control surface on localhost.
- `--minimized` — start minimized.
- `--tray` — show a system-tray icon.

## Importing a portrait

1. **File → Open portrait...** (Ctrl+O), pick a PNG or JPG.
2. The avatar slug auto-derives from the filename, sanitized: `My Portrait, 2026-05-01.png` → `my-portrait-2026-05-01`.
3. The remembered last folder is reused on next launch.

The rig fits in ~1-3 seconds (MediaPipe FaceMesh + Pose). The 3D viewport (left) and OpenPose preview (right) populate.

## Exporting wireframes

- Ctrl+E — single export at the current yaw.
- Ctrl+Shift+E — 13-angle batch export.

Exports land in your configured **Export folder root** (Options tab → Browse...). Default: `~/Desktop/openrepose-output/`.

Each export writes BOTH a `.json` (OpenPose keypoints, pretty-printed) AND a `.png` (rendered wireframe).

## Where things are

- **Inspector** tab — read-only state.
- **Tools** tab — three sub-tabs:
  - Calibration — mark reference points for the active avatar (per-avatar TPS deformation).
  - Markers — uncheck individual OpenPose keypoints to suppress them.
  - Reframer — frame scale + offset + anchor controls.
- **Library** tab — PostgreSQL-backed search and detail view for OpenPose guides, generated images, prompts, workflow JSON, notes, and tags.
- **Triage** tab — read-only project/task/card progress view for intake queues, target counters, AMood batch state, and snapshot targets.
- **Options** tab — settings: export folder, Library DB URL/root/operator slug, body-part visibility, canvas border color.
- **Log** tab — live OpenRepose log.
- **Help** tab — this manual.
