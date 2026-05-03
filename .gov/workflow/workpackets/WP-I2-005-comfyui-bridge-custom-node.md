# WP-I2-005 - ComfyUI Bridge Custom Node

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: REVIEW
- **Iteration**: I2
- **Workflow Version**: 1.1
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: `.gov/spec/openrepose_library_v0_1.md` ComfyUI Bridge / Custom Node Contract.

## Intent

Ship the `comfyui-openrepose-bridge` custom node: a ComfyUI custom node that POSTs to OpenRepose's localhost HTTP control surface (`http://localhost:8765/command`, `register_library_entry`) after each successful image save. Bundles workflow JSON + image bytes + extracted metadata + operator-supplied tags. Spec-locked POST payload + ComfyUI ≥ 0.3.65 target.

## Linked Workpackets

- **Predecessor(s)**: WP-I2-004 (`register_library_entry` command exists).
- **Successor(s)**: none planned.
- **Related**: WP-I0-002 (HTTP channel — reused as-is).

## Linked Requirements / Spec Sections

- `.gov/spec/openrepose_library_v0_1.md` ComfyUI Bridge / Custom Node Contract — POST payload schema, target ComfyUI version, error handling (non-blocking on POST failure).

## Research Notes

| Date | Source | URL | Takeaway | Verdict |
|------|--------|-----|----------|---------|
| 2026-05-03 | WP-I1-033 research notes | local | Standard pattern: hook into the SaveImage step; precedents in SaveImageWithMetaData / comfy-image-saver / Crystools. POST via stdlib `http.client` to avoid extra deps in the custom node. | adopt |
| 2026-05-03 | ComfyUI custom node template | https://docs.comfy.org/development/core-concepts/custom-nodes | NODE_CLASS_MAPPINGS + NODE_DISPLAY_NAME_MAPPINGS dicts at module top level. INPUT_TYPES + RETURN_TYPES + FUNCTION method on the node class. | adopt |
| 2026-05-03 | Workflow extraction from ComfyUI server context | precedent (SaveImageWithMetaData) | Workflow JSON is in `extra_pnginfo` kwarg passed to the node's FUNCTION method by ComfyUI. | adopt |

## Reality Boundary

- **Real Seam**: real ComfyUI custom node folder under `.product/comfyui-bridge/`; operator copies / symlinks into ComfyUI's `custom_nodes/`; node loads in ComfyUI; POSTs to OpenRepose on each image save; entry appears in the library.
- **User-Visible Win**: operator generates an image in ComfyUI; library tab shows the new entry within seconds, with workflow + prompts + smart tags auto-populated.
- **Proof Target**: unit tests for the POST payload builder (mock the HTTP send); integration test with a mock ComfyUI saving an image + workflow_json triggers POST + entry appears in DB; manual: real ComfyUI run.

## In Scope

- `.product/comfyui-bridge/__init__.py` (NEW): NODE_CLASS_MAPPINGS + NODE_DISPLAY_NAME_MAPPINGS.
- `.product/comfyui-bridge/openrepose_bridge.py` (NEW): `OpenReposeBridge` node class. INPUT_TYPES = original SaveImage inputs + `avatar_slug` STRING + `tags` STRING (comma-separated) + optional `openpose_json_path` STRING + optional `openrepose_url` STRING (default `http://localhost:8765`). FUNCTION = `save_and_register`. Builds POST payload per spec; sends via stdlib `http.client`; logs WARN on failure but does not raise.
- `.product/comfyui-bridge/README.md` (NEW): operator install instructions (copy to `ComfyUI/custom_nodes/openrepose-bridge/`); usage example.
- `.product/comfyui-bridge/extract_metadata.py` (NEW): pure helper that parses a ComfyUI workflow JSON and extracts `model`, `sampler`, `seed`, `steps`, `cfg`, `lora list`, `custom_node list`. Used both in the bridge and in WP-I2-003's smart_tags module.
- Tests under `.product/tests/test_comfyui_bridge.py` (NEW): payload builder unit tests; metadata extraction; POST mock; error-on-POST-failure non-blocking.

## Out Of Scope

- Hosting the custom node in ComfyUI's registry (operator installs manually for v0.1).
- Authentication beyond localhost (cross-machine setup deferred).
- Multi-image-per-workflow registration (one image per save in v0.1).
- Updating an existing entry (each save = new entry; operator can `delete_library_entry` then re-save).

## Definition Of Done

- [x] Custom node loads in ComfyUI ≥ 0.3.65 (via standard `NODE_CLASS_MAPPINGS` + `NODE_DISPLAY_NAME_MAPPINGS` in `__init__.py`; ComfyUI imports happen lazily inside `save_and_register` so the node also imports cleanly under pytest with no ComfyUI present).
- [x] POST payload matches spec schema (verified by `test_build_payload_shape_matches_command_schema`; positive/negative prompts auto-extracted from CLIPTextEncode nodes; metadata auto-extracted from CheckpointLoader / KSampler / LoraLoader nodes).
- [x] POST failure logs WARN; does not block image save (`save_and_register` wraps the per-image POST in try/except + logs `openrepose_bridge.post_failed`; image save runs first).
- [x] pytest payload + metadata extraction tests pass (`test_comfyui_bridge.py` 11/11 in 38s).
- [ ] Operator installs node + runs ComfyUI + image save triggers entry creation in OpenRepose. *(Pending operator sign-off; assistant verified end-to-end via `test_bridge_payload_round_trips_through_dispatcher` — bridge payload → real ephemeral PG → entry retrievable via `get_library_entry`.)*
- [x] **Manual Impact**: Yes — added a "ComfyUI bridge (WP-I2-005)" section + cross-reference to `.product/comfyui-bridge/README.md` in `.gov/doc/manual/feature-3-library-postgresql.md`; status bullets updated.

## Headless LLM Operation Compliance

- [x] N/A — ComfyUI custom node, no GUI surface in OpenRepose itself. The bridge POSTs the same `register_library_entry` command an LLM agent would dispatch directly.

## Change Ledger

- **What Became Real**:
  - `.product/comfyui-bridge/__init__.py` — ComfyUI registration (`NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS`).
  - `.product/comfyui-bridge/openrepose_bridge.py` — `OpenReposeBridge` node class with `INPUT_TYPES` (images + avatar_slug + optional title/yaw_bin/tags/openpose_*_path/openrepose_url/filename_prefix + hidden prompt+extra_pnginfo) + `save_and_register` FUNCTION. Saves PNGs (mirrors `SaveImage`), POSTs each to `/command` with the spec-defined payload. ComfyUI imports (folder_paths / numpy / PIL) deferred so module imports cleanly without ComfyUI.
  - `.product/comfyui-bridge/extract_metadata.py` — pure helpers `iter_workflow_nodes`, `extract_metadata`, `extract_prompts` for both API and editor workflow shapes. Stdlib-only.
  - `.product/comfyui-bridge/README.md` — operator install instructions (copy / symlink into `custom_nodes/`); node input table; behavior + compatibility notes; troubleshooting matrix.
  - `.gov/doc/manual/feature-3-library-postgresql.md` — ComfyUI Bridge section + cross-reference to the README; status bullets bumped (Manual Impact: Yes).
  - 11 new tests in `test_comfyui_bridge.py`: metadata + prompt extraction, build_register_payload (shape, base64-encoded image, missing-image graceful, blank yaw_bin omitted), send_post (parsed json / raw / network error propagation), end-to-end dispatcher round-trip with ephemeral PG. Test-only namespace package wiring loads the kebab-case folder cleanly without changing the on-disk layout ComfyUI expects.
- **What Remains Simulated**: nothing within scope. Operator install + manual ComfyUI verification still pending sign-off (Definition of Done item #5).
- **Next Blocking Real Seam**: WP-I2-007 adds `library_entry` + `library_search_results` snapshot targets (operator-grabbable visual artifacts of the Library tab state).

## Evidence

- **Targeted suite**: `pytest .product/tests/test_comfyui_bridge.py -v` → 11/11 in 38s (10 unit + 1 ephemeral-PG end-to-end).
- **Full suite**: 471/472 after parallel WP-I2-006 commit (1 failure was the WP-I1-031 GUI-layout test asserting "five tabs"; updated to expect the new "Library" tab at index 2). Re-run after the test fix included in this WP-pair commit.
- **Audit**: `powershell scripts/audit-repo.ps1` → `audit-repo: OK   no violations` (172 tracked files).
- **Operator Sign-off**: pending (operator overnight handoff — manual ComfyUI install + real-image-save verification belongs to the operator).

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
- 2026-05-03: Promoted DRAFT → READY → IN-PROGRESS (kickoff commit). Owner: assistant. Operator overnight autonomous I2 sequence; running in parallel with WP-I2-006.
- 2026-05-03: 4 source files + 11 tests + manual update landed; suite passes; audit clean. Status → REVIEW.
