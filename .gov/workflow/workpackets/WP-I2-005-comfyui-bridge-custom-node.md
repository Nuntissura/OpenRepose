# WP-I2-005 - ComfyUI Bridge Custom Node

## Header

- **Owner**: TBD
- **Date Opened**: 2026-05-03
- **Last Updated**: 2026-05-03
- **Status**: DRAFT
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

- [ ] Custom node loads in ComfyUI ≥ 0.3.65.
- [ ] POST payload matches spec schema.
- [ ] POST failure logs WARN; does not block image save.
- [ ] pytest payload + metadata extraction tests pass.
- [ ] Operator installs node + runs ComfyUI + image save triggers entry creation in OpenRepose.
- [ ] **Manual Impact**: Yes — add `feature-3-library-postgresql.md` ComfyUI Bridge subsection with operator install instructions (copy folder into ComfyUI's custom_nodes/), node-input fields explainer, troubleshooting.

## Headless LLM Operation Compliance

- [x] N/A — ComfyUI custom node, no GUI surface in OpenRepose itself.

## Change Ledger

- (filled at REVIEW)

## Evidence

- (filled at close)

## Progress Log

- 2026-05-03: WP drafted at DRAFT.
