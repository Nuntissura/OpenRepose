"""OpenRepose Bridge — ComfyUI custom node entry point (WP-I2-005).

Operator install: copy or symlink the entire `.product/comfyui-bridge/`
folder into ComfyUI's `custom_nodes/` directory under any name (commonly
`openrepose-bridge`). ComfyUI imports `__init__.py` on startup and reads
`NODE_CLASS_MAPPINGS` + `NODE_DISPLAY_NAME_MAPPINGS` to register the
node in the editor.

The node POSTs to OpenRepose's localhost HTTP control surface
(`/command` → `register_library_entry`) after each image save. Spec:
`.gov/spec/openrepose_library_v0_1.md` ComfyUI Bridge / Custom Node
Contract.

Stdlib-only on purpose: ComfyUI's bundled Python should not require
extra `pip install` to load this node.
"""

from __future__ import annotations

from .openrepose_bridge import OpenReposeBridge

NODE_CLASS_MAPPINGS = {
    "OpenReposeBridge": OpenReposeBridge,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OpenReposeBridge": "OpenRepose Bridge (Save + Register)",
}

# Optional namespace marker some ComfyUI managers display in the menu.
WEB_DIRECTORY = None

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "OpenReposeBridge",
]
