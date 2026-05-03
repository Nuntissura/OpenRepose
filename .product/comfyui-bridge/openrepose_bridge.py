"""`OpenReposeBridge` ComfyUI node — saves the upstream image as a
standard PNG **and** POSTs the bundle to OpenRepose.

WP-I2-005 shipped this with one path: POST `register_library_entry`
to write directly into the main library.

WP-I3-005 makes intake the default destination. At node-call time the
bridge inspects the environment:

  OPENREPOSE_TASK_ID set            -> intake path (default for batch runs):
                                        POST `intake_begin_run` once,
                                        then POST `intake_register_output`
                                        per image. Outputs land in
                                        `outputs/intake/<task_dir>/raw/`
                                        at status='pending' for triage.
  OPENREPOSE_OPERATOR_TOKEN set     -> legacy direct-library path:
                                        POST `register_library_entry`
                                        with `operator_token` field. Use
                                        case: operator running ComfyUI
                                        for ad-hoc non-batch work.
  OPENREPOSE_LEGACY_DIRECT_WRITE=1  -> FALLBACK v0.1: legacy path even
                                        without a token. Removed in the
                                        next bridge WP after operator
                                        transition.
  none of the above                 -> refused: bridge logs INTAKE-002
                                        and skips the POST. Image is
                                        still saved to ComfyUI's output
                                        directory (per spec rule that
                                        image-save never fails).

Spec: `.gov/spec/openrepose_intake_v0_1.md` Default-Staging ComfyUI
Bridge; `.gov/spec/openrepose_library_v0_1.md` ComfyUI Bridge / Custom
Node Contract (the legacy-path contract this WP composes with).

Stdlib-only — must not import OpenRepose. `urllib.request` is used for
the POST so the node loads inside ComfyUI's bundled Python without
extra `pip install`.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from .extract_metadata import extract_metadata, extract_prompts

LOG = logging.getLogger(__name__)

DEFAULT_URL = "http://localhost:8765"
DEFAULT_TIMEOUT_S = 5.0

# ---------------------------------------------------------------------------
# Environment-var contract (WP-I3-005)
# ---------------------------------------------------------------------------

ENV_TASK_ID = "OPENREPOSE_TASK_ID"
ENV_CARD_ID = "OPENREPOSE_CARD_ID"
ENV_CARD_SLUG = "OPENREPOSE_CARD_SLUG"
ENV_OPERATOR_TOKEN = "OPENREPOSE_OPERATOR_TOKEN"
ENV_LEGACY_FLAG = "OPENREPOSE_LEGACY_DIRECT_WRITE"

PATH_INTAKE = "intake"
PATH_LEGACY = "legacy"
PATH_LEGACY_FLAG = "legacy_fallback"
PATH_REFUSED = "refused"

INTAKE_002_CITATION = (
    "ERR cmd=register_library_entry: blocked by INTAKE-002 (default intake target):\n"
    "ComfyUI bridge writes to intake unless operator token allows direct library.\n"
    "See manual: intake-and-triage#default-intake.\n"
    "Fix: set OPENREPOSE_TASK_ID environment variable for the active task, or supply\n"
    "OPENREPOSE_OPERATOR_TOKEN to consciously bypass intake for ad-hoc work."
)


def _stripped_env(name: str) -> str:
    """Treat empty / whitespace-only env values as unset."""
    return (os.environ.get(name) or "").strip()


def select_path() -> str:
    """Decide which dispatch branch to take based on the current env.

    Returns one of `PATH_INTAKE`, `PATH_LEGACY`, `PATH_LEGACY_FLAG`,
    `PATH_REFUSED`. Pure helper for testability.
    """
    if _stripped_env(ENV_TASK_ID):
        return PATH_INTAKE
    if _stripped_env(ENV_OPERATOR_TOKEN):
        return PATH_LEGACY
    if _stripped_env(ENV_LEGACY_FLAG) == "1":
        return PATH_LEGACY_FLAG
    return PATH_REFUSED


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
                # WP-I3-005: optional sampler params surfaced for intake_begin_run
                "sampler": ("STRING", {"default": ""}),
                "cfg": ("FLOAT", {"default": 0.0}),
                "steps": ("INT", {"default": 0}),
                "seed": ("INT", {"default": 0}),
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
        sampler: str = "",
        cfg: float = 0.0,
        steps: int = 0,
        seed: int = 0,
        prompt: dict | None = None,
        extra_pnginfo: dict | None = None,
    ) -> dict:
        """Per-image save loop. Branches on env vars per WP-I3-005."""
        workflow_json = (extra_pnginfo or {}).get("workflow") or prompt or {}

        saved_paths = self._save_images(
            images, filename_prefix=filename_prefix, prompt=prompt, extra_pnginfo=extra_pnginfo
        )

        url_base = openrepose_url.rstrip("/") + "/command"
        operator_tags = [t.strip() for t in (tags or "").split(",") if t.strip()]
        path = select_path()
        # One-line summary for the ComfyUI console so operators can see
        # which branch fired without reading the full bridge log.
        print(
            f"openrepose-bridge: path={path} images={len(saved_paths)} url={url_base}",
            file=sys.stderr,
        )

        if path == PATH_REFUSED:
            print(INTAKE_002_CITATION, file=sys.stderr)
            LOG.warning("openrepose_bridge.refused: rule_id=INTAKE-002 image_count=%d", len(saved_paths))
            return _ui_dict(saved_paths)

        if path == PATH_INTAKE:
            self._dispatch_intake_path(url_base, saved_paths, workflow_json,
                                       sampler=sampler, cfg=cfg, steps=steps, seed=seed)
        else:
            # Legacy paths (operator-token explicit OR fallback flag).
            operator_token = _stripped_env(ENV_OPERATOR_TOKEN) or None
            self._dispatch_legacy_path(
                url_base, saved_paths,
                avatar_slug=avatar_slug, title=title, yaw_bin=yaw_bin,
                operator_tags=operator_tags, workflow_json=workflow_json,
                openpose_json_path=openpose_json_path,
                openpose_png_path=openpose_png_path,
                operator_token=operator_token,
            )

        return _ui_dict(saved_paths)

    # --- intake path -----------------------------------------------------

    def _dispatch_intake_path(
        self,
        url: str,
        saved_paths: list[str],
        workflow_json: dict[str, Any] | None,
        *,
        sampler: str,
        cfg: float,
        steps: int,
        seed: int,
    ) -> None:
        if not saved_paths:
            return
        task_id = _stripped_env(ENV_TASK_ID)
        card_id = _stripped_env(ENV_CARD_ID) or None
        card_slug = _stripped_env(ENV_CARD_SLUG) or None
        if not card_id and not card_slug:
            # Bridge cannot create a run without a card binding. Log
            # and skip — image still on disk.
            print(
                "openrepose-bridge: intake path needs OPENREPOSE_CARD_ID or "
                "OPENREPOSE_CARD_SLUG to begin a run; skipping POST.",
                file=sys.stderr,
            )
            return
        begin_payload = build_intake_begin_run_payload(
            task_id=task_id,
            card_id=card_id,
            card_slug=card_slug,
            sampler=sampler or None,
            cfg=cfg if cfg else None,
            steps=steps if steps else None,
            seed=seed if seed else None,
            workflow_json=workflow_json,
        )
        try:
            response = send_post(url, begin_payload)
        except (urllib.error.URLError, OSError) as e:
            LOG.warning("openrepose_bridge.intake_begin_run.post_failed: reason=%s", e)
            return
        run_payload = (response or {}).get("payload", {}) if isinstance(response, dict) else {}
        run_info = run_payload.get("run") if isinstance(run_payload, dict) else None
        run_id = run_info.get("id") if isinstance(run_info, dict) else None
        if not run_id:
            LOG.warning("openrepose_bridge.intake_begin_run.no_run_id: response=%s", response)
            return

        for image_path in saved_paths:
            try:
                content_hash, width, height, image_b64 = compute_image_metadata(image_path)
                payload = build_intake_register_output_payload(
                    task_id=task_id,
                    run_id=run_id,
                    filename=os.path.basename(image_path),
                    image_b64=image_b64,
                    width=width,
                    height=height,
                    content_hash=content_hash,
                )
                send_post(url, payload)
            except Exception as e:  # noqa: BLE001 - best-effort per spec
                LOG.warning(
                    "openrepose_bridge.intake_register.post_failed: image=%s reason=%s",
                    image_path, e,
                )

    # --- legacy path -----------------------------------------------------

    def _dispatch_legacy_path(
        self,
        url: str,
        saved_paths: list[str],
        *,
        avatar_slug: str,
        title: str,
        yaw_bin: str,
        operator_tags: list[str],
        workflow_json: dict[str, Any] | None,
        openpose_json_path: str,
        openpose_png_path: str,
        operator_token: str | None,
    ) -> None:
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
                    operator_token=operator_token,
                )
                send_post(url, payload)
            except Exception as e:  # noqa: BLE001 - best-effort per spec
                LOG.warning(
                    "openrepose_bridge.legacy_register.post_failed: image=%s reason=%s",
                    image_path, e,
                )

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
        as PNGs. Mirrors the behavior of the stock `SaveImage` node."""
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
    operator_token: str | None = None,
) -> dict[str, Any]:
    """Construct the dict the legacy `register_library_entry` command
    expects. Optional `operator_token` forwarded for the WP-I3-005
    legacy-path branch (operator consciously bypassing intake)."""
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
    if operator_token:
        payload["operator_token"] = operator_token

    try:
        with open(image_path, "rb") as f:
            payload["generated_image"] = base64.b64encode(f.read()).decode("ascii")
    except OSError:
        pass

    if openpose_json_path:
        payload["openpose_json_path"] = openpose_json_path
    if openpose_png_path:
        payload["openpose_png_path"] = openpose_png_path
    return payload


def build_intake_begin_run_payload(
    *,
    task_id: str,
    card_id: str | None,
    card_slug: str | None,
    sampler: str | None,
    cfg: float | None,
    steps: int | None,
    seed: int | None,
    workflow_json: dict[str, Any] | None,
) -> dict[str, Any]:
    """Construct the dict the `intake_begin_run` command expects."""
    payload: dict[str, Any] = {
        "command": "intake_begin_run",
        "task_id": task_id,
    }
    if card_id:
        payload["card_id"] = card_id
    elif card_slug:
        payload["card_slug"] = card_slug
    if sampler:
        payload["sampler"] = sampler
    if cfg is not None:
        payload["cfg"] = float(cfg)
    if steps is not None:
        payload["steps"] = int(steps)
    if seed is not None:
        payload["seed"] = int(seed)
    if workflow_json is not None:
        payload["workflow_json"] = workflow_json
    return payload


def build_intake_register_output_payload(
    *,
    task_id: str,
    run_id: str,
    filename: str,
    image_b64: str,
    width: int,
    height: int,
    content_hash: str,
) -> dict[str, Any]:
    """Construct the dict the `intake_register_output` command expects
    when the bridge ships image bytes (the dispatcher writes them to the
    intake_dir on the OpenRepose side)."""
    return {
        "command": "intake_register_output",
        "task_id": task_id,
        "run_id": run_id,
        "filename": filename,
        "image_b64": image_b64,
        "width": int(width),
        "height": int(height),
        "content_hash": content_hash,
    }


def compute_image_metadata(image_path: str) -> tuple[str, int, int, str]:
    """Return (sha256_hex, width, height, base64_bytes) for `image_path`.
    Reads the file once. PIL is the local PNG decoder; if PIL is not
    available (rare outside ComfyUI), width/height fall back to 0/0 and
    auto-route effectively no-ops on dimension predicates."""
    with open(image_path, "rb") as f:
        raw = f.read()
    sha = hashlib.sha256(raw).hexdigest()
    b64 = base64.b64encode(raw).decode("ascii")
    width = 0
    height = 0
    try:
        from PIL import Image  # type: ignore[import-untyped]

        with Image.open(io.BytesIO(raw)) as im:
            width, height = im.size
    except (ImportError, Exception):  # noqa: BLE001
        pass
    return sha, int(width), int(height), b64


def send_post(url: str, payload: dict[str, Any], *, timeout: float = DEFAULT_TIMEOUT_S) -> dict[str, Any]:
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


def _ui_dict(saved_paths: list[str]) -> dict[str, Any]:
    return {
        "ui": {
            "images": [
                {"filename": os.path.basename(p), "subfolder": "", "type": "output"}
                for p in saved_paths
            ]
        }
    }
