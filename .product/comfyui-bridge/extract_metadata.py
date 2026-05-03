"""Pure-Python helpers for pulling production metadata + prompts out of a
ComfyUI workflow JSON document.

Used inside the OpenRepose Bridge custom node to build the POST body the
spec calls for. Stdlib-only — must not import anything from the rest of
OpenRepose so this file can ship verbatim under ComfyUI's
`custom_nodes/` tree.
"""

from __future__ import annotations

from typing import Any, Iterable


def iter_workflow_nodes(workflow: object) -> Iterable[dict[str, Any]]:
    """Yield each node dict from a ComfyUI workflow JSON document.

    Recognises the API format (dict keyed by node id, each value
    `{class_type, inputs}`) and the editor format (`{"nodes": [...]}`)."""
    if not isinstance(workflow, dict):
        return
    api_format = workflow and all(
        isinstance(v, dict) and "class_type" in v for v in workflow.values()
    )
    if api_format:
        for node in workflow.values():
            if isinstance(node, dict):
                yield node
        return
    nodes = workflow.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict):
                yield node


def _node_class(node: dict[str, Any]) -> str:
    cls = node.get("class_type") or node.get("type")
    return str(cls) if cls else ""


def _node_inputs(node: dict[str, Any]) -> dict[str, Any]:
    inputs = node.get("inputs")
    return inputs if isinstance(inputs, dict) else {}


def extract_metadata(workflow: dict[str, Any] | None) -> dict[str, Any]:
    """Build the OpenRepose `metadata` dict per the spec POST schema:

        {model, sampler, seed, steps, cfg, lora: [...], custom_node: [...]}

    Missing values are simply omitted (callers merge with operator-supplied
    metadata before POSTing). Lora list and custom_node list are
    deduplicated and sorted for stability."""
    out: dict[str, Any] = {}
    loras: set[str] = set()
    classes: set[str] = set()

    for node in iter_workflow_nodes(workflow):
        cls = _node_class(node)
        if cls:
            classes.add(cls)
        inputs = _node_inputs(node)

        if cls.startswith("CheckpointLoader") and "ckpt_name" in inputs:
            out.setdefault("model", str(inputs["ckpt_name"]))
        if cls.startswith("KSampler"):
            for src, dst in (
                ("sampler_name", "sampler"),
                ("scheduler", "scheduler"),
                ("seed", "seed"),
                ("steps", "steps"),
                ("cfg", "cfg"),
            ):
                if src in inputs and dst not in out:
                    out[dst] = inputs[src]
        if cls.startswith("LoraLoader") and "lora_name" in inputs:
            loras.add(str(inputs["lora_name"]))

    if loras:
        out["lora"] = sorted(loras)
    if classes:
        out["custom_node"] = sorted(classes)
    return out


def extract_prompts(workflow: dict[str, Any] | None) -> dict[str, str]:
    """Best-effort positive + negative prompt extraction from
    `CLIPTextEncode` nodes. Many workflows tag the negative encode with
    a `negative_prompt` title or chain it through the negative input on
    `KSampler`; without that signal we cannot disambiguate, so we pick
    the **first** CLIPTextEncode as positive and **second** as negative.

    Operator can override by passing `positive` / `negative` directly to
    `register_library_entry`."""
    encodes: list[str] = []
    for node in iter_workflow_nodes(workflow):
        if not _node_class(node).startswith("CLIPTextEncode"):
            continue
        text = ""
        inputs = _node_inputs(node)
        if "text" in inputs and isinstance(inputs["text"], str):
            text = inputs["text"]
        else:
            widgets = node.get("widgets_values")
            if isinstance(widgets, list) and widgets and isinstance(widgets[0], str):
                text = widgets[0]
        encodes.append(text)
        if len(encodes) == 2:
            break
    return {
        "positive": encodes[0] if encodes else "",
        "negative": encodes[1] if len(encodes) > 1 else "",
    }
