# OpenRepose Bridge — ComfyUI custom node

Drop-in `SaveImage` replacement that POSTs each generated image to OpenRepose's localhost HTTP control surface. After each successful image generation in ComfyUI, the matching row appears in OpenRepose automatically — by default in the **intake queue** (per WP-I3-005), or directly into the main library when the operator is doing ad-hoc non-batch work.

Specs:
- `.gov/spec/openrepose_intake_v0_1.md` Default-Staging ComfyUI Bridge (the WP-I3-005 path)
- `.gov/spec/openrepose_library_v0_1.md` ComfyUI Bridge / Custom Node Contract (the legacy direct-library path)

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

- The node always saves the image to ComfyUI's `output_directory/` first (existing pipelines still see the file on disk; image save never fails because of OpenRepose).
- The bridge then chooses one of four branches based on **environment variables** (WP-I3-005):

| `OPENREPOSE_TASK_ID` | `OPENREPOSE_OPERATOR_TOKEN` | `OPENREPOSE_LEGACY_DIRECT_WRITE` | Branch | What happens |
|----------------------|-----------------------------|----------------------------------|--------|--------------|
| set                  | (any)                       | (any)                            | **intake** (default for batch runs) | bridge POSTs `intake_begin_run` once, then `intake_register_output` per image; rows land at `status='pending'` for triage |
| (unset)              | set                         | (any)                            | **legacy** | bridge POSTs `register_library_entry` with `operator_token` on the payload |
| (unset)              | (unset)                     | `=1`                             | **legacy_fallback** (FALLBACK v0.1, transitional) | legacy path even without a token — removed in the next bridge WP |
| (unset)              | (unset)                     | (unset)                          | **refused** | bridge logs `INTAKE-002` to stderr; no POST; image still on disk |

Set the env vars in the same shell you launch ComfyUI from. Operator setup steps are documented in `.gov/doc/manual/intake-and-triage.md#default-intake`.

The bridge emits a one-line summary on stderr at every save (`openrepose-bridge: path=intake images=4 url=...`) so operators can confirm the active branch from the ComfyUI console.

### Intake-path additional bindings

The intake path needs a card to attach the run to. Bind via one of:

- `OPENREPOSE_CARD_ID=<uuid>` — exact UUID (preferred, no ambiguity).
- `OPENREPOSE_CARD_SLUG=<slug>` — resolves under the active task's batch via `library_entries.title`.

Without either, the intake-path POST is skipped and the image still saves to disk (a hint is logged).

### Other notes

- On HTTP failure (port unreachable, OpenRepose not running, timeout) the node logs `WARN openrepose_bridge.*.post_failed` to ComfyUI's console and continues.
- Auto-derived `metadata` (`model`, `sampler`, `seed`, `steps`, `cfg`, `lora list`, `custom_node list`) is extracted from the workflow JSON and merged into both legacy and intake payloads.
- Positive and negative prompts are extracted best-effort from the first two `CLIPTextEncode` nodes; the legacy path stores them with the entry. The intake path defers prompt-association to the eventual `intake_finalize` step (after triage).

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
| Bridge logs `path=refused` and `INTAKE-002` | Neither `OPENREPOSE_TASK_ID` nor `OPENREPOSE_OPERATOR_TOKEN` is set | Set `OPENREPOSE_TASK_ID` for batch work, OR `OPENREPOSE_OPERATOR_TOKEN` for ad-hoc direct-library work, in the shell that launches ComfyUI. |
| Bridge logs `intake path needs OPENREPOSE_CARD_ID or OPENREPOSE_CARD_SLUG` | The intake branch is selected but no card binding | Set `OPENREPOSE_CARD_ID` or `OPENREPOSE_CARD_SLUG` to the card the run should attach to. |

## Local development

The pure helpers (`build_register_payload`, `send_post`, `extract_metadata`, `extract_prompts`) are tested under `.product/tests/test_comfyui_bridge.py` against an in-process mock ComfyUI workflow + `urllib.request` mock — no ComfyUI install required to run those tests.
