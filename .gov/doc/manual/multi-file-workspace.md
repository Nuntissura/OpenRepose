# Multi-File Workspace

Cross-cutting capability that lets one OpenRepose hold several portraits open at once, each with its own rig + per-file state. Spec: `.gov/spec/openrepose_v0_1.md` § "Multi-File Workspace". Authored by WP-I1-036; implementation lands in WP-I1-037+.

## What you get

- Open more than one portrait. Each opens in its own tab in the file area on the left side of the window.
- Switching tabs flips the right-dock readouts (Inspector, Tools, Options) and the toolbar's yaw / export buttons to that file's state. No re-import; no MediaPipe re-fit on switch.
- Per-file state: yaw bin, calibration markers, frame scale/offset/anchor, body-part visibility, marker visibility, detected markers — all isolated per tab.
- Drag-and-drop a portrait onto the file area or any open tab's viewport: opens a new tab.
- Close a tab via its `X` button. Close is non-destructive — only the in-memory file slot is dropped; the source PNG/JPG on disk is untouched.
- Multi-file drop: drop N images, get N tabs.

## What stays global

- Operator settings (export folder, library DB URL, operator slug, canvas border color, …).
- Library connection + search results.
- Log file.
- Exports / snapshots / errors arrays in `state.json`.
- Adult production boundary stance object.

## Empty state

When zero files are open, the file area shows a centered "Drop a portrait here · or use File → Open portrait... (Ctrl+O)" placeholder with a dashed border. Drop or use File→Open to populate.

## Tab interactions

- **Close** — `X` on the tab. Dispatches `close_file {file_id}`. No confirmation; close is operator-explicit.
- **Reorder** — drag the tab within the bar. Order is operator preference only — no semantic meaning.
- **Switch active** — click the tab. Dispatches `set_active_file {file_id}`. Right-dock + toolbar refresh.
- **Locked tab** — when the file's `avatar_slug` matches a library entry currently locked by another operator, the tab title shows a `🔒` prefix and write commands return an error. Read commands (`dump_rig`, `get_*`, `snapshot`) still work.

## Headless command surface

Four new commands manage the file list:

| Command | Body | Returns |
|---------|------|---------|
| `open_file` | `{path, avatar_slug?}` | `{file_id, active_file_id, files_count}` |
| `close_file` | `{file_id}` (or `"active"`) | `{closed_file_id, active_file_id, files_count}` |
| `set_active_file` | `{file_id}` | `{active_file_id}` |
| `list_files` | `{}` | `{files: [{file_id, portrait, avatar_slug, rig.status}, …], active_file_id}` |

`import_portrait` stays as a v0.1-compatible alias for `open_file`. Existing per-file commands (`set_yaw`, `set_yaw_bin`, `export_single`, `export_batch`, `set_calibration_points`, `set_frame_*`, `set_body_part_visibility`, `set_marker_visibility`, …) gain an optional `file_id` parameter. When omitted, they target the active file — preserving v0.1 LLM-agent behavior.

The following commands stay global (no `file_id`): `snapshot` (defaults to active file's widgets; optional `file_id` for cross-file inspection without switching tabs), `dump_state`, `dump_settings` / `set_settings` / `clear_settings`, `clear_outputs`, all library / intake / AMood / requirements commands.

## state.json layout (v2)

`state.json` schema bumps from `0.1` to `2.0` to reflect the multi-file structure:

- New top-level `active_file_id` — UUID of the active file (or null).
- New top-level `files` array — full per-file state for every open file.
- Top-level `portrait`, `rig`, `yaw`, `calibration`, `frame`, `body_part_visibility`, `marker_visibility`, `detected_markers` become a **mirror** of the active file's per-file state for backward compatibility with v0.1 LLM agents.
- `settings`, `library`, `exports`, `snapshots`, `errors`, `last_command`, `adult_production_boundary` stay global.

The mirror is read-only as far as LLM agents are concerned — mutations target either an explicit `file_id` or the active file via the relevant command.

## Persistence

Workspace persistence is operator-controlled:

- `Settings.persist_workspace` (default `true`) — on shutdown, OpenRepose writes the open file paths + slugs (NOT the per-file state) to `<AppConfigLocation>/openrepose/workspace.json`. On next launch, files re-import in order.
- Per-file state (rig, calibration, frame, visibility) is recomputed from the portrait + the per-avatar `<slug>/calibration.json` on each launch. This keeps `workspace.json` small and avoids drift between sessions.
- Lazy-fit allowance: implementation MAY defer the MediaPipe fit until the first switch-to-tab. While pending, the tab title shows "(loading…)" and `rig.status` is `"pending"`.
- Missing source path at restore time: tab opens with `rig.status = "missing"` and a placeholder. Operator can close it or re-import.

## Snapshot subsystem behavior

Existing snapshot targets (`3d_viewport`, `openpose_viewport`, `inspector_pane`, `log_pane`, `options_pane`, `status_bar`, `toolbar`, `full_window`, `calibration_overlay`) all gain an optional `file_id` parameter. When omitted, they snapshot the active file's widgets. When supplied, the snapshot subsystem renders the requested file's state to an offscreen buffer — the GUI does NOT switch tabs and the operator's view does NOT change. This preserves the no-focus-theft contract.

`full_window` always composes the active file's viewports + the right dock + status bar + toolbar. There is no v0.1 `all_files_grid` composition.

## Out of scope (v0.1 multi-file)

- Tab tear-off / multi-window mode.
- Multi-monitor support.
- Drag-and-drop reordering of tabs across multiple rows.
- Per-file undo/redo.
- Auto-save / unsaved-changes confirmation on close.
- Cross-process multi-operator presence (one operator per OpenRepose process; library locks are the only cross-process surface).

## Compatibility

v0.1 LLM agents that read `state.portrait`, `state.calibration`, `state.frame` directly continue to work — the top-level mirror reflects the active file. v0.1 commands without `file_id` continue to operate on the active file. The v0.1 single-file workflow is the multi-file workflow with `len(files) == 1`.
