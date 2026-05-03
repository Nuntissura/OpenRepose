"""`OpenReposeBridge` ComfyUI node — saves the upstream image as a
standard PNG **and** POSTs the bundle (workflow JSON + image bytes +
metadata + prompts + operator tags) to OpenRepose's
`register_library_entry` HTTP endpoint.

Spec: `.gov/spec/openrepose_library_v0_1.md` ComfyUI Bridge / Custom
Node Contract.

Stdlib-only — must not import OpenRepose. `urllib.request` is used for
the POST so the node loads inside ComfyUI's bundled Python without
extra `pip install`.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from .extract_metadata import extract_metadata, extract_prompts

LOG = logging.getLogger(__name__)

DEFAULT_URL = "http://localhost:8765"
DEFAULT_TIMEOUT_S = 5.0


class OpenReposeBridge:
    """ComfyUI custom node that registers the just-saved image with the
    OpenRepose Library. Mirrors `SaveImage` semantics for the actual save
    so an operator can drop this node in place of the upstream save."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:  # noqa: N802 - ComfyUI convention
        return {
            "required": {
                "images": ("IMAGE",),
                "avatar_slug": ("STRING", {"default": "aeri"}),
            },
            "optional": {
                "title": ("STRING", {"default": ""}),
                "yaw_bin": ("STRING", {"default": ""}),
                "tags": ("STRING", {"default": ""}),  # comma-separated
                "openpose_json_path": ("STRING", {"default": ""}),
                "openpose_png_path": ("STRING", {"default": ""}),
                "openrepose_url": ("STRING", {"default": DEFAULT_URL}),
                "filename_prefix": ("STRING", {"default": "openrepose"}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    CATEGORY = "OpenRepose"
    FUNCTION = "save_and_register"

    def save_and_register(  # noqa: PLR0913 - ComfyUI signature
        self,
        images,
        avatar_slug: str,
        title: str = "",
        yaw_bin: str = "",
        tags: str = "",
        openpose_json_path: str = "",
        openpose_png_path: str = "",
        openrepose_url: str = DEFAULT_URL,
        filename_prefix: str = "openrepose",
        prompt: dict | None = None,
        extra_pnginfo: dict | None = None,
    ) -> dict:
        """Per-image save loop. Returns the standard ComfyUI dict so the
        editor can show the previews. Errors POSTing to OpenRepose are
        logged WARN; image saving still succeeds (spec rule)."""
        # `extra_pnginfo` carries the full workflow JSON under the
        # `workflow` key (ComfyUI convention; api format).
        workflow_json = (extra_pnginfo or {}).get("workflow") or prompt or {}

        saved_paths = self._save_images(
            images, filename_prefix=filename_prefix, prompt=prompt, extra_pnginfo=extra_pnginfo
        )

        url = openrepose_url.rstrip("/") + "/command"
        operator_tags = [t.strip() for t in (tags or "").split(",") if t.strip()]
        for image_path in saved_paths:
            try:
                payload = build_register_payload(
                    avatar_slug=avatar_slug,
                    title=title,
                    yaw_bin=yaw_bin,
                    tags=operator_tags,
                    image_path=image_path,
                    workflow=workflow_json,
                    openpose_json_path=openpose_json_path,
                    openpose_png_path=openpose_png_path,
                )
                send_post(url, payload)
            except Exception as e:  # noqa: BLE001 - non-blocking per spec
                LOG.warning(
                    "openrepose_bridge.post_failed: image=%s url=%s reason=%s",
                    image_path, url, e,
                )

        return {"ui": {"images": [{"filename": os.path.basename(p), "subfolder": "", "type": "output"} for p in saved_paths]}}

    # --- helpers ---------------------------------------------------------

    def _save_images(  # noqa: ANN001
        self,
        images,
        *,
        filename_prefix: str,
        prompt,
        extra_pnginfo,
    ) -> list[str]:
        """Save the upstream IMAGE tensor(s) to ComfyUI's `output_directory`
        as PNGs. Mirrors the behavior of the stock `SaveImage` node so a
        drop-in replacement works the same."""
        # Imports are deferred so this module loads in pytest without
        # ComfyUI present.
        try:
            import folder_paths  # type: ignore[import-untyped]
            import numpy as np  # type: ignore[import-untyped]
            from PIL import Image, PngImagePlugin  # type: ignore[import-untyped]
        except ImportError:  # pragma: no cover - executes only inside ComfyUI
            return []

        output_dir = folder_paths.get_output_directory()
        os.makedirs(output_dir, exist_ok=True)
        results: list[str] = []
        for i, image in enumerate(images):
            # ComfyUI IMAGE tensors are torch tensors HWC float in [0,1].
            arr = (255.0 * image.cpu().numpy()).clip(0, 255).astype(np.uint8)
            pil = Image.fromarray(arr)
            metadata = PngImagePlugin.PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for k, v in extra_pnginfo.items():
                    metadata.add_text(k, json.dumps(v))
            counter = i + 1
            filename = f"{filename_prefix}_{counter:05d}.png"
            full = os.path.join(output_dir, filename)
            pil.save(full, pnginfo=metadata, compress_level=4)
            results.append(full)
        return results


# ---------------------------------------------------------------------------
# Pure helpers (testable without ComfyUI)
# ---------------------------------------------------------------------------


def build_register_payload(
    *,
    avatar_slug: str,
    title: str,
    yaw_bin: str,
    tags: list[str],
    image_path: str,
    workflow: dict[str, Any] | None,
    openpose_json_path: str,
    openpose_png_path: str,
) -> dict[str, Any]:
    """Construct the dict the `register_library_entry` command expects.

    Spec: ComfyUI Bridge / Custom Node Contract — POST schema. Reads the
    saved image into a base64 string (stdlib only). When the operator
    supplied paths to existing OpenPose JSON / PNG files, those land as
    `*_path` keys (the dispatcher will read them itself); otherwise they
    are omitted."""
    metadata = extract_metadata(workflow)
    prompts = extract_prompts(workflow)

    payload: dict[str, Any] = {
        "command": "register_library_entry",
        "avatar_slug": avatar_slug or "",
        "title": title or "",
        "metadata": metadata,
        "prompts": prompts,
        "tags": list(tags or []),
    }
    if yaw_bin:
        payload["yaw_bin"] = yaw_bin
    if workflow is not None:
        payload["comfyui_workflow"] = workflow

    # Image payload: read bytes once, base64-encode (avoids file I/O on
    # the OpenRepose side).
    try:
        with open(image_path, "rb") as f:
            payload["generated_image"] = base64.b64encode(f.read()).decode("ascii")
    except OSError:
        # Best-effort: still POST so the rest of the entry registers.
        pass

    if openpose_json_path:
        payload["openpose_json_path"] = openpose_json_path
    if openpose_png_path:
        payload["openpose_png_path"] = openpose_png_path
    return payload


def send_post(url: str, payload: dict[str, Any], *, timeout: float = DEFAULT_TIMEOUT_S) -> dict[str, Any]:
    """Send `payload` as JSON to `url`. Returns the parsed response on
    success, raises on non-2xx status / network failure. Caller wraps in
    try/except; the bridge swallows failures per spec."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - localhost POST by design
        raw = resp.read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
