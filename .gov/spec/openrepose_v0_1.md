# OpenRepose Spec v0.1

Status: DRAFT
Date: 2026-05-02
Workflow Version: 1.0

## Purpose

OpenRepose is a desktop application that supports commercial adult pornographic image and video production workflows. The first shipped feature is a 3D-rig-locked yaw-angle wireframe exporter. This spec defines that first feature's contract and the application-wide conventions (yaw terminology, repo split, output formats) that future features will inherit.

## Repo Layout

OpenRepose splits into two top-level directories:

```text
.gov/        governance — spec, topology, AGENTS.md, CODEX.md, workflow, templates,
             workpackets, taskboard. Authoritative. Read by humans and LLMs.
.product/    product code — src/openrepose/, tests/, fixtures, conftest.py.
             The thing that ships and runs.
```

Top-level helper files:

```text
README.md             project description with adult-production stance.
pyproject.toml        package + dependencies (mediapipe>=0.10.21,<0.10.30 until WP-I1-014).
orstart.cmd           bootstrap forwarder (Windows).
.gitignore            excludes target/, dist/, outputs/, .venv/, *.safetensors.
target/               build / test artifacts. Gitignored. Cleaned before push.
dist/                 installer build output. Gitignored.
outputs/              app runtime outputs (snapshots, exports, runtime state). Gitignored.
```

Why the split: governance and product evolve at different cadences and need different reviewers. `.gov/` is the contract; `.product/` is the implementation. An LLM agent reading just `.gov/` can plan work without scanning thousands of source lines; one reading just `.product/` can implement without negotiating governance.

## Application-Wide Conventions

### Yaw Terminology Lock

```text
0 deg            frontal, face direct at camera.
her-left N       avatar rotates N degrees about her vertical axis to her own left.
her-right N      avatar rotates N degrees about her vertical axis to her own right.
```

`her-left` and `her-right` are anchored to the avatar's anatomy, not the viewer's frame. A rotation labeled `her-left 90` means: she turned 90 degrees to her own left, so her right side now faces the camera and her nose ends up at the right edge of the rendered frame.

Standard bins: `0`, `her-left 15/30/45/60/75/90`, `her-right 15/30/45/60/75/90`.

Optional rear bins for full-body work: `her-left 105/120/150`, `her-right 105/120/150`, `180`.

The phrases `image-left`, `image-right`, `viewer-left`, `viewer-right`, `left view`, `right view` are forbidden anywhere in OpenRepose code, file names, comments, docs, or UI.

### Output Formats

OpenRepose writes to `outputs/` (gitignored). The default subfolder pattern:

```text
outputs/<avatar-slug>/<run-tag>/
  <avatar-slug>_yaw_0.png
  <avatar-slug>_yaw_0.json
  <avatar-slug>_yaw_her-left-15.png
  <avatar-slug>_yaw_her-left-15.json
  <avatar-slug>_yaw_her-right-15.png
  <avatar-slug>_yaw_her-right-15.json
  ...
  manifest.json
```

PNG specs: black background, OpenPose color spec, no annotations baked into the image. Resolution defaults to source image dimensions; configurable via export settings.

JSON specs: matches the schema produced by ComfyUI's DWPose node + `RenderPeopleKps` node — a top-level array containing one object with `people: [{pose_keypoints_2d, face_keypoints_2d, hand_left_keypoints_2d, hand_right_keypoints_2d}]`, plus `canvas_width`, `canvas_height` at the top level. Coordinates are flat `[x, y, confidence, ...]` triples. Hidden keypoints have all three values set to `0.0`.

`manifest.json` records: source portrait path, rig fit timestamp, app version, list of exported angles, settings used (focal length / projection mode / margin parameters), and any notes the GUI captured.

### Mechanical Log Format

Every log line OpenRepose emits, whether to stdout, the rolling file under `target/logs/openrepose-YYYYMMDD.log`, or the in-GUI log pane, follows one of these four exact shapes:

```text
[YYYY-MM-DDTHH:MM:SS.mmm] OK   <op>: <k=v> <k=v> ...
[YYYY-MM-DDTHH:MM:SS.mmm] WARN <op>: <reason>; <k=v> <k=v>
[YYYY-MM-DDTHH:MM:SS.mmm] ERR  <op>: <reason>; <k=v> <k=v>
[YYYY-MM-DDTHH:MM:SS.mmm] DBG  <op>: <k=v> <k=v>
```

`<op>` is dotted lower-snake-case: `rig.fit`, `rig.dump`, `viewport.update`, `viewport.snapshot`, `openpose.render`, `export.single`, `export.batch`, `format.check`, `cmd.received`, `cmd.completed`, `state.write`. No prose, no emoji, no punctuation other than what's shown above.

Key-value pairs use `key=value` with no spaces inside the value (quote with `"..."` if a value contains spaces). Examples:

```text
[2026-05-02T17:24:01.123] OK   rig.fit: portrait="aeri_master.png" face=478 body=33 t_ms=2287
[2026-05-02T17:24:05.044] OK   viewport.snapshot: target=3d_viewport out="outputs/.runtime/snapshots/20260502-172405-044_3d_viewport.png" t_ms=18
[2026-05-02T17:24:18.901] ERR  export.batch: reason="missing avatar slug"; angles_requested=13 angles_done=0
```

Logs go to stdout, to the rolling file, AND to the in-GUI log pane simultaneously. Same line, same format, three sinks. LLMs grep `ERR ` to find failures; humans skim the same file with the same eyes.

### LLM Control Surface

The application exposes a stable command schema usable by any LLM (OpenAI, Anthropic, Google, local, future) without provider-specific code in OpenRepose. Two channels are available; both can be enabled, disabled, or used together.

**State snapshot file** — always written, regardless of channel state.

```text
outputs/.runtime/state.json
```

Schema:

```json
{
  "version": "0.1",
  "started_at": "2026-05-02T17:00:00.000Z",
  "portrait": "absolute path or null",
  "avatar_slug": "string or null",
  "rig": {
    "status": "none|fitting|ok|error",
    "fit_at": "ISO timestamp or null",
    "fit_duration_ms": 0,
    "face_landmark_count": 0,
    "body_landmark_count": 0,
    "face_visible_in_openpose": 0,
    "body_visible_in_openpose": 0
  },
  "yaw": {
    "current_value_deg": 0.0,
    "current_bin": "0",
    "axis": "y"
  },
  "exports": [
    { "type": "single|batch", "out_dir": "string", "completed_at": "ISO", "files": ["string"] }
  ],
  "snapshots": [
    { "target": "string", "out_path": "string", "captured_at": "ISO" }
  ],
  "errors": [
    { "level": "ERR|WARN", "op": "string", "reason": "string", "at": "ISO" }
  ],
  "last_command": {
    "command": "string",
    "received_at": "ISO",
    "completed_at": "ISO or null",
    "status": "ok|error|in_progress"
  }
}
```

The state file is written atomically (temp file + rename) on every state change so a reader never sees a partial JSON document. Bounded retention: `exports`, `snapshots`, and `errors` arrays cap at 100 most-recent entries (FIFO).

**Channel A: HTTP localhost** — opt-in. Default off. When enabled by operator (Options tab or `--http-port N` flag), the app listens on `127.0.0.1:N` (default `N=8765`). One endpoint:

```text
POST /command   Content-Type: application/json   body: <command JSON>
GET  /state                                       returns state.json contents
GET  /log?lines=<N>                               returns last N log lines
```

Bound to `127.0.0.1` only. No CORS, no auth — single-user local tool. If the operator wants remote access they configure their own SSH tunnel.

**Channel B: File-watch inbox** — opt-in. Default off. When enabled by operator (Options tab or `--inbox` flag), the app watches `outputs/.runtime/inbox/` for new `*.json` files. Each file is one command. Processed in mtime order, one at a time, then deleted from the inbox and recorded in `outputs/.runtime/processed/<original-filename>.<status>.json` where `status` is `ok` or `err`. Result file contains the original command plus a `result` block.

**Command schema** — same shape on both channels:

```json
{
  "command": "import_portrait | set_yaw | set_yaw_bin | export_single | export_batch | snapshot | dump_rig | dump_state | clear_outputs",
  "request_id": "optional string for correlation"
}
```

Per-command arguments:

```json
{ "command": "import_portrait", "path": "absolute path to portrait", "avatar_slug": "string" }

{ "command": "set_yaw", "value_deg": -30.0 }

{ "command": "set_yaw_bin", "bin": "her-right 30" }

{ "command": "export_single", "out_dir": "optional, defaults to outputs/<avatar-slug>/" }

{ "command": "export_batch", "out_dir": "optional", "angles": ["optional list, defaults to 13-angle standard"] }

{ "command": "snapshot", "target": "3d_viewport|openpose_viewport|inspector_pane|log_pane|options_pane|status_bar|toolbar|full_window", "out_path": "optional, defaults to outputs/.runtime/snapshots/<auto>.png" }

{ "command": "dump_rig", "out_path": "optional, defaults to outputs/.runtime/rig_dump_<timestamp>.json" }

{ "command": "dump_state", "out_path": "optional, defaults to outputs/.runtime/state_dump_<timestamp>.json" }

{ "command": "clear_outputs", "scope": "snapshots|exports|all" }
```

All command results land in `state.json` under `last_command` and (where applicable) in the `exports` or `snapshots` arrays.

### Snapshot Subsystem

The snapshot subsystem renders any named module of the running application to a PNG file without requiring the application window to be foregrounded, focused, on-screen, or even visible. It exists for LLM visual inspection, not operator viewing.

**Snapshot targets:**

```text
3d_viewport         the rig viewport. Rendered via offscreen pyrender FBO; same scene data as the visible viewport, separate render call. Available regardless of window visibility.
openpose_viewport   the OpenPose preview. Rendered via PIL/cv2 from the current rotated rig keypoints, written directly to PNG. Independent of GUI state.
inspector_pane      the right-side inspector readouts. Rendered via QWidget.grab() — works whether the widget is on-screen or not.
log_pane            the log tab contents. Rendered via QWidget.grab() OR via direct text-to-image render of the current rolling log buffer.
options_pane        the options tab. Rendered via QWidget.grab().
status_bar          the bottom status bar. Rendered via QWidget.grab().
toolbar             the top toolbar with yaw slider. Rendered via QWidget.grab().
full_window         the entire main window composited. Built by grabbing each child pane and composing them in their layout positions; does NOT use desktop screen-grab APIs.
```

**Output convention:**

```text
outputs/.runtime/snapshots/<YYYYMMDD-HHMMSS-mmm>_<target>.png
outputs/.runtime/snapshots.jsonl        append-only manifest with one JSON object per line:
                                          { "captured_at": "ISO", "target": "...", "out_path": "...", "yaw_bin": "...", "rig_status": "..." }
```

**No-focus-hijack rules** (enforced in code, tested in the `snapshot` workpacket):

1. Snapshot handlers MUST NOT call `raise_()`, `activateWindow()`, `showNormal()` from minimized, or any window-manager API that affects window stack or focus.
2. Snapshot handlers MUST NOT post events that would cause the OS to bring the window to front.
3. Snapshot handlers MUST work when the window is minimized to taskbar or to system tray.
4. Snapshot handlers MUST work when another application is in the foreground; they do not touch foreground state.

**Render contracts:**

- `3d_viewport` snapshots use the offscreen pyrender FBO. The same rig + same yaw state that drives the visible viewport drives the offscreen render. Resolution is configurable per snapshot (defaults to the canvas dimensions in `state.json`).
- Qt-widget snapshots use `QWidget.grab()`. The widget's hierarchy must be realized at least once for `grab()` to render correctly; a one-time invisible render at app startup achieves this without showing the window. Implemented via `QWidget.show()` followed immediately by `QWidget.hide()` during init, before any LLM or operator interaction.
- `full_window` composition is the union of child pane snapshots placed at their layout coordinates with optional window-chrome included.

### Operator Experience Guarantees

OpenRepose is operator-respecting. The application MUST NOT, under any LLM-driven command path:

- Raise its own window to the foreground.
- Take keyboard focus from another application.
- Capture the mouse cursor.
- Modify the operator's window stack.
- Display modal dialogs in response to LLM commands. (Errors go to log + state.json + snapshots, never to a modal.)
- Play audio.
- Trigger OS-level notifications.

The application MAY:

- Update its own visible widgets when their underlying state changes (yaw slider value, log pane, viewports). The operator sees the update if they happen to be looking at the window; the window does not demand attention.
- Expose a system-tray icon (optional, operator opt-in). Tray icon's only operator-triggered action is "Show window" / "Hide window" / "Quit".
- Write to the rolling log file, the state file, and the snapshots/exports folders.
- Append-emit one log line per stdout per significant action.

The operator triggers foreground appearance through OS controls (clicking the taskbar icon, alt-tab, the tray menu). LLM commands do not.

## Feature 1: 3D-Rig Yaw Wireframe Exporter

### Purpose

Take a frontal portrait of a single subject. Fit a locked 3D rig of facial landmarks plus shoulder/neck/ear/eye body landmarks. Allow interactive yaw rotation of the rig in a GUI. Export OpenPose-format wireframe images at any rotation angle.

The rig locks face shape, eye size, mouth size, face oval scale, shoulder breadth, and the geometric relationships between these features. Rotation does not deform the rig; it rotates a fixed 3D object about its vertical axis and projects to 2D.

### Inputs

- A single frontal portrait of one subject.
  - Format: PNG or JPG.
  - The subject must be visible from at least the chest up. Eye-level camera. Both eyes and both shoulders visible (occlusion by hair is OK).
  - Frontal orientation: nose at or near the image horizontal center; face plane roughly perpendicular to the camera. Approximate is acceptable; the rig fitter will tolerate small deviations but reports them in the manifest.

### Rig Construction

OpenRepose builds a 3D rig from the input portrait using:

- **MediaPipe FaceMesh** (or compatible 3D face landmark model) — fits a canonical 3D face mesh of 478 landmarks to the portrait. This captures real per-landmark depth, eye outline, eye spacing, mouth outline, mouth width, nose, brows, jaw oval, and forehead. The result is a measured 3D model of the subject's face.
- **MediaPipe Pose** (or compatible 3D body landmark model) — fits 3D body landmarks for shoulders, neck, ears, eyes, hips. Provides real per-landmark depth so shoulders and torso retain front-to-back breadth at non-frontal yaw.
- **Anchor**: the face mesh is positioned in 3D space so that its neck-bottom matches the body skeleton's neck point.
- **Lock**: once fit, the rig is treated as a single rigid 3D object. No further deformation is allowed during rotation. The rig captures eye-to-mouth ratio, eye-to-shoulder ratio, face-to-shoulder ratio, and shoulder breadth as measured invariants.

### Rotation

- Rotation is rigid yaw about the rig's vertical (y) axis.
- The rotation axis passes through the rig's neck point (origin of the body skeleton).
- The application supports yaw values `[-180, +180]` in increments configurable via UI; standard bins are `0`, `her-left 15..90`, `her-right 15..90` plus optional rear bins.
- Pitch and roll are not supported in v0.1. Future spec versions may add them as separate locked axes.

### Projection

- Default projection is orthographic for the face/upper-body framing typical of portrait wireframes.
- A perspective projection mode is available via export settings; default focal-length parameter is set to a reasonable portrait value.
- Output canvas dimensions match the input portrait dimensions by default. Custom canvas dimensions are configurable via export settings.

### OpenPose Schema Mapping

OpenRepose maps from MediaPipe's 478 face landmarks to OpenPose's 70 face keypoints, and from MediaPipe Pose's 33 body landmarks to OpenPose's 18 body keypoints (`body_18` schema). The mapping is documented in the implementation; future spec versions may add `body_25` support.

Per-keypoint visibility (rendered vs. hidden in the output) is computed by surface-normal direction in the rotated rig: a landmark is visible if its outward normal has a forward (toward-camera) z component within a small margin. Hidden keypoints render with confidence `0.0` in the output JSON and are not drawn in the PNG.

### GUI Requirements

The desktop GUI is operator-facing only. LLM agents do not interact with the GUI directly; they use the LLM Control Surface (commands + state file + snapshots). The GUI and the LLM share the same underlying state model.

**Layout** — tool-style, dense, no AI-feel cardboard layouts:

- **Top menu bar**: File | Edit | View | Tools | Export | Help.
- **Toolbar row**: `[Open]` `[Reload]` ... yaw bin dropdown ... yaw slider ... `[Export single]` `[Export batch]` `[Stop]`.
- **Center, two-pane split**:
  - Left pane: 3D mesh viewport. Orbital inspection camera (mouse drag rotates the camera-of-inspection, read-only — does not change rig orientation). Face mesh rendered as a translucent surface plus body skeleton lines.
  - Right pane: OpenPose preview. Live render at the current yaw setting; matches the format OpenPoseXL2 was trained on (black background, OpenPose color spec).
- **Right dock — tabbed**:
  - `Inspector` tab (default): yaw bin, yaw value, axis, rig fit status, fit duration, face landmark count, body landmark count, canvas size, format-check status, plus action buttons `[Run format check]` `[Render single]` `[Compare to reference]` `[Snapshot viewport]` `[Dump rig]`.
  - `Options` tab: single export folder, batch export folder, avatar slug, run tag, default batch angle list, projection mode, focal length, output canvas, OpenPose schema (read-only display), LLM HTTP channel toggle + port, LLM file-watch inbox toggle, log level, clean outputs on close.
  - `Log` tab: read-only monospace text view of the rolling log file. Auto-scrolls. Filterable by level (`ERR`/`WARN`/`OK`/`DBG`).
  - `Help` tab: keyboard shortcuts, schema references, links to the spec.
- **Bottom status bar**: `status: ... | rig: locked|none|error | yaw: <bin> (<deg>) | last_export: <time> | errors: <n>`.

**Direction indicator**: a small arrow next to the yaw slider showing where the avatar's face ends up in the export. `→` for `her-left N` (her face goes to the right edge of the frame), `←` for `her-right N`. Reduces terminology confusion at a glance.

**Operator experience**:

- First launch: window appears normally so the operator can find it. After that, no code path under operator-driven OR LLM-driven commands calls `raise_()`, `activateWindow()`, `showNormal()`, or any focus-stealing API. Position is restored from the operator's last placement if WP-I1-003 settings persistence is in effect.
- Optional system-tray icon (operator opt-in). Tray menu: Show / Hide / Quit. No notifications, no toasts, no audio.
- Live updates: when the LLM control surface processes a command that changes state (rig fit, yaw, export), both viewports and the inspector readouts update silently. The operator sees the new state if they're looking; the window does not demand attention.
- Keyboard shortcuts on every action; visible in tooltips.
- Numerical readouts visible at all times in the status bar and inspector.

**What the GUI must NOT do**:

- No wizard flows or onboarding splashes.
- No Material Design cards, soft drop shadows, or excessive padding.
- No chatbot or "Ask AI" pane inside the app.
- No verbose marketing-style text. Tooltips, not paragraphs.
- No automatic foregrounding under any condition. See Operator Experience Guarantees.

### CLI Requirements

A CLI front-end provides headless equivalents of the GUI export buttons for batch automation. Minimum CLI surface:

```text
orstart                          # repo startup banner (already exists at repo root)
openrepose import <portrait>     # fit rig and save rig metadata to outputs/<slug>/rig.json
openrepose export --angle <bin>  # export single angle from saved rig
openrepose export --batch        # export the 13-angle default
openrepose export --angles <list># export a custom list of angles
```

CLI must work without launching the GUI (for headless servers / CI / scripted runs).

### Out Of Scope For v0.1

- Pitch and roll rotation (yaw only in v0.1).
- Hair, bangs, clothing, accessories, or background in the rig (the OpenPose wireframe does not constrain these; downstream LoRA / diffusion model handles them).
- Multi-subject portraits (single subject only).
- Profile or non-frontal input portraits (frontal only in v0.1).
- Animation / interpolation between angles.
- Direct ControlNet integration (export to disk; downstream tools load the files).
- Identity-preservation across hair/clothing changes (out of scope for v0.1; future feature).

### Performance Targets For v0.1

- Rig fit time on a portrait at 1024x1024: under 3 seconds on a CPU-only laptop.
- GUI yaw-slider responsiveness: live preview updates within 100 ms on a laptop GPU.
- 13-angle batch export: under 15 seconds total on a laptop GPU.

These are targets, not gates. v0.1 ships when the feature is functionally complete; performance tuning lives in a later spec version.

### Reality Boundary For v0.1

- **Real Seam**: rig construction from a real portrait, real 3D rotation, real OpenPose-format export. No photowarp. No flat-z body shortcuts.
- **User-Visible Win**: operator imports a frontal portrait of any subject, exports 13 OpenPose wireframes that preserve identity-relevant ratios across rotation, and feeds them into ControlNet workflows. Wireframes look like real DWPose detections of real photographs at the same angles.
- **Proof Target**: side-by-side comparison of OpenRepose's `her-left 90` wireframe export against a DWPose detection of an actual `her-left 90` photograph of the same subject. Eye position, ear position, shoulder breadth, jaw outline must agree within a documented tolerance.
- **Allowed Temporary Fallbacks**: synthetic body z values for hips/elbows/wrists if MediaPipe Pose fails on the input (with explicit label in the manifest).
- **Promotion Guard**: fallbacks must be removed before the spec is promoted from `DRAFT` to `STABLE`.

## Project-Wide Principle: Headless LLM Operation

Every operator-facing or visually interactive feature in OpenRepose must be fully usable by an LLM agent running in the background. This applies to every feature in this spec and every feature added in future spec versions.

Per-feature requirements:

1. The feature exposes a command-schema entry point reachable through the LLM Control Surface (HTTP localhost or file-watch inbox).
2. The feature reflects its state in `outputs/.runtime/state.json` (or a documented additional state file under `outputs/.runtime/`) so an LLM agent can read state without scraping the GUI.
3. The feature provides a snapshot target (or extends the `full_window` composition) so an LLM agent can pull a visual artifact on demand. Snapshot targets follow the no-focus-hijack rules in section "Snapshot Subsystem".
4. The feature honors every item in section "Operator Experience Guarantees".

Workpacket authors verify these requirements before opening any IMPLEMENTATION-class workpacket that adds an operator-facing or visual feature. The full checklist lives in `.gov/AGENTS.md` section "Headless Verification Checklist".

## Iteration Roadmap

The roadmap below points each spec area at the workpacket(s) that author or implement it. Live status of every WP lives in `.gov/workflow/TASKBOARD.md`. WP files live in `.gov/workflow/workpackets/` (active) and `.gov/workflow/archive/` (closed). Each future feature MUST satisfy the project-wide Headless LLM Operation principle.

### I0 — Initial Scaffold (this spec)

- **WP-I0-001 Rig and Rotation Core** (DONE) — `rig.py`, `rotation.py`, `openpose_serialize.py`, `yaw_bin.py`, `openpose_schema.py`.
- **WP-I0-002 LLM Control Surface** (DONE) — `state.py`, `commands.py`, `app.py`, `channels/http.py`, `channels/inbox.py`, `log.py`.
- **WP-I0-003 Snapshot Subsystem** (DONE) — `snapshot.py`, `render/draw_3d.py`, `render/draw_openpose.py`, `render/widget_grab.py`, `render/compose.py`.
- **WP-I0-004 Double Viewport GUI** (REVIEW) — `gui/main_window.py` and the entire `gui/` package; closes I0 on operator sign-off.

### I1 — Feature Expansion (drafted)

Feature WPs (operator-facing; Headless Compliance required):

- **WP-I1-001 Per-avatar calibration overlay** — operator marks reference points (eye outer corners, mouth corners, jaw corners, optional brow tips) on the master portrait; OpenRepose computes a 2D deformation field that maps FaceMesh-detected positions to operator-marked positions and applies it to every rotated wireframe. Mitigates the documented FaceMesh bias toward average human proportions seen in WP-I0-003. Commands: `set_calibration_points`, `dump_calibration`, `clear_calibration`. New snapshot target: `calibration_overlay`.
- **WP-I1-007 Pitch / roll rotation extension** — extends the rig to full pose: yaw + pitch + roll. Locked terminology mirrors the yaw lock (`chin-up N`, `chin-down N`, `lean-left N`, `lean-right N` per the predecessor DOCUMENTATION WP). Commands: `set_pitch`, `set_roll`, `set_pose`. State file extended with a pose block.
- **WP-I1-009 Identity-export profiles** — locked face/body identity exports for downstream face-swap and img2img conditioning. Command: `export_identity_profile`. New snapshot target: `identity_profile`.
- **WP-I1-010 Multi-angle automation** — extends `export_batch` with operator-defined prompt-seed lists. State file records the queue.
- **WP-I1-011 Multi-subject scenes** — rig schema lists subjects; commands gain `subject_index` where applicable. Likely promotes to I2.
- **WP-I1-015 Floating reference portrait window** — operator's continuous-context-during-work window: a small floating window pinned to the master portrait, persistent across yaw drags and exports. Position persisted via WP-I1-003.
- **WP-I1-016 Clear workspace command + button** — toolbar button + `clear_workspace` command that resets viewports, log filter, and inspector readouts to a known clean state.
- **WP-I1-017 Per-body-part visibility toggles** — operator toggles face / body / hands independently in both viewports and exports. Commands: `set_visibility`. State file records the mask.
- **WP-I1-018 Hand detection + OpenPose hand output** — adds 21-per-hand keypoints to the rig and the OpenPose JSON. Gates DWPose hand conditioning. Composes with WP-I1-014.
- **WP-I1-022 Read OpenPose JSON as alternate input** — non-portrait input path: load existing OpenPose JSON, rotate, export. Composes with WP-I1-023.
- **WP-I1-023 Frame reframing (robust rerender)** — pad / crop / scale the rendered frame by transforming keypoints and redrawing with constant line widths; not a naive image resize. Fixes portrait-bias and cropped-feet failures.

Polish WPs (no new commands required; Headless N/A or trivial):

- **WP-I1-002 Orbital camera in 3D viewport** — read-only camera-of-inspection orbit; rig is unchanged.
- **WP-I1-003 Settings persistence** — Options tab values + window geometry persist across launches. Prerequisite for WP-I1-015.
- **WP-I1-004 Extended keyboard shortcuts** — every action gets a shortcut; visible in tooltips.
- **WP-I1-005 Drag-and-drop portrait import** — drop a PNG/JPG on the window to trigger `import_portrait`.
- **WP-I1-006 GUI theme refinements** — dense tool-style tuning; no Material Design cards.
- **WP-I1-024 Synchronized viewport zoom** — wires WP-I1-023 frame state into the 3D viewport, OpenPose preview, and reference window so they zoom together. OpenPose preview always pads with black (DWPose / OpenPoseXL2 was trained on black-bg poses); reference window pads with operator-chosen color; 3D viewport pads with diagnostic gray.

Infrastructure WPs (no operator-facing surface; Headless N/A):

- **WP-I1-013 Installer build + release** — Windows installer; later iterations add macOS / Linux.
- **WP-I1-014 MediaPipe Tasks API migration** — switch `rig.py` from the deprecated `mp.solutions.*` namespace to `mp.tasks.vision.*`. Removes the `mediapipe<0.10.30` upper bound. Schedule before WP-I1-018.

Research WP:

- **WP-I1-008 Alternative landmark detector research** — investigate dlib 68-point + iris, MediaPipe Tasks, or other detectors for stylized faces. Output is a comparison report; implementation gated on findings.

### Deferred / Reserved

- **WP-I1-012 Garment locks** — DEFERRED. OpenPose has no garment channel; the locked-rig concept does not transfer cleanly. Re-scope candidate for I2: "garment polyline → secondary ControlNet input" if a multi-ControlNet workflow becomes a production path.
- **WP-I1-019 / 020 / 021 Joint-manipulation chain** — RESERVED, not drafted. Operator postponed to a later iteration.

### I2+ Themes (not yet drafted)

- Code signing for distributables.
- macOS / Linux installer builds.
- GitHub Actions CI for automated test + build.
- Per-feature-group calibration mixing (extension of WP-I1-001).
- Animated yaw-sweep video export.
- Read OpenPose PNG image (reverse-engineer keypoints from rendered colors). Pure RESEARCH first.
- Joint-manipulation chain (promotion of WP-I1-019 / 020 / 021).

Each becomes its own workpacket when authorized. The taskboard is the live truth; this section is the spec-side index.
