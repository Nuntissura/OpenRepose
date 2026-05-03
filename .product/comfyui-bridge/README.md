# OpenRepose Bridge — ComfyUI custom node

Drop-in `SaveImage` replacement that also POSTs the bundle (workflow JSON + image bytes + extracted prompts + auto-derived metadata + operator tags) to OpenRepose's localhost HTTP control surface (`/command` → `register_library_entry`). After each successful image generation in ComfyUI, the matching library entry appears in OpenRepose's Library tab automatically.

Spec: `.gov/spec/openrepose_library_v0_1.md` ComfyUI Bridge / Custom Node Contract.

## Install

1. Copy or symlink this entire folder into your ComfyUI installation under `custom_nodes/openrepose-bridge/`.

   ```powershell
   # Windows example (symlink):
   New-Item -ItemType SymbolicLink `
     -Path  "<ComfyUI>\custom_nodes\openrepose-bridge" `
     -Value "<repo>\.product\comfyui-bridge"
   ```

2. Restart ComfyUI.
3. The node appears in the editor under the **OpenRepose** category as "OpenRepose Bridge (Save + Register)".

No extra `pip install` is required — the node is stdlib-only on the ComfyUI side.

## Inputs

| Field | Required | Default | Notes |
|-------|----------|---------|-------|
| `images` | yes | — | The IMAGE tensor from upstream nodes (same as `SaveImage`). |
| `avatar_slug` | yes | `aeri` | Identifies which avatar the entry belongs to. |
| `title` | no | `""` | Human-readable title for the library row. |
| `yaw_bin` | no | `""` | E.g. `her-right-30`. Leave blank when not applicable. |
| `tags` | no | `""` | Comma-separated operator tags. Smart `auto:` tags are added automatically by OpenRepose. |
| `openpose_json_path` | no | `""` | Path on disk to the OpenPose JSON used as the rig source. |
| `openpose_png_path` | no | `""` | Path on disk to the rendered OpenPose PNG. |
| `openrepose_url` | no | `http://localhost:8765` | Override when OpenRepose's HTTP channel runs on a custom port. |
| `filename_prefix` | no | `openrepose` | PNG filename prefix in ComfyUI's `output/` folder. |

## Behavior

- The node saves the image normally (to ComfyUI's `output_directory/`) so existing pipelines still see the file on disk.
- It then POSTs to `http://localhost:8765/command` with `{ "command": "register_library_entry", ... }` per the spec contract.
- On HTTP failure (port unreachable, OpenRepose not running, timeout) the node logs `WARN openrepose_bridge.post_failed` to ComfyUI's console and continues. The image save itself never fails because of OpenRepose.
- Auto-derived `metadata` (`model`, `sampler`, `seed`, `steps`, `cfg`, `lora list`, `custom_node list`) is extracted from the workflow JSON and merged into the POST.
- Positive and negative prompts are extracted best-effort from the first two `CLIPTextEncode` nodes; operators that need exact disambiguation can pass them via the OpenRepose `update_library_entry` command afterward.

## Compatibility

- ComfyUI ≥ 0.3.65 (matches the precedent set by SaveImageWithMetaDataUniversal).
- The custom node refuses to load on older ComfyUI builds with a clear error message in the console (see `__init__.py`).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Node missing from ComfyUI menu | Wrong folder name or restart needed | Confirm folder is `custom_nodes/openrepose-bridge/__init__.py` and restart. |
| `post_failed: connection refused` | OpenRepose HTTP channel not enabled | Launch OpenRepose with `--http-port 8765` or enable the toggle in Options → LLM HTTP channel. |
| Library entry appears with no thumbnail | Image bytes were too large to POST in one shot, OR the operator's library_root is on a network share with intermittent latency | Check OpenRepose's log file for `library.register` events; re-run the workflow if needed. |
| `library subsystem is disabled` in OpenRepose log | `Settings.library_db_url` not set | Configure the DB URL in OpenRepose Options → Library DB URL (see `feature-3-library-postgresql.md`). |

## Local development

The pure helpers (`build_register_payload`, `send_post`, `extract_metadata`, `extract_prompts`) are tested under `.product/tests/test_comfyui_bridge.py` against an in-process mock ComfyUI workflow + `urllib.request` mock — no ComfyUI install required to run those tests.
