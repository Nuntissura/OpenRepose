"""Smart-tag extraction from ComfyUI workflow JSON + run metadata.

Spec: `.gov/spec/openrepose_library_v0_1.md` Tag System ("Smart tags —
derived tags computed by the dispatcher from metadata; auto-applied on
register_library_entry; prefix with `auto:` so the operator can
distinguish from manual tags").

Extractors are best-effort: a non-standard workflow shape returns the
tags it can compute and silently skips the rest. Callers may attach an
``auto:smart-tag-extraction-failed:1`` marker (separately) when the
extractor returned zero tags from a workflow that clearly has nodes.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

AUTO_TAG_PREFIX = "auto:"


_SAFE_VALUE_RE = re.compile(r"[^A-Za-z0-9._:+/-]")


def _slugify_value(value: object) -> str:
    """Normalize a smart-tag value into a stable identifier.

    Tags are compared by exact text in the DB, so we lowercase and strip
    inner whitespace + non-token characters. Empty result returns ``""``.
    """
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    text = text.replace(" ", "-")
    text = _SAFE_VALUE_RE.sub("-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def _add_tag(out: list[str], seen: set[str], namespace: str, value: object) -> None:
    slug = _slugify_value(value)
    if not slug:
        return
    tag = f"{AUTO_TAG_PREFIX}{namespace}:{slug}"
    if tag in seen:
        return
    seen.add(tag)
    out.append(tag)


def _iter_workflow_nodes(workflow: object) -> Iterable[dict[str, Any]]:
    """Yield each node dict from a ComfyUI workflow JSON document.

    ComfyUI ships two common shapes:
      1. API-format dict keyed by node id, each value `{class_type, inputs}`.
      2. Editor-format dict with `nodes: [{type, widgets_values}, ...]`.
    Recognize both. Anything unrecognized yields nothing.
    """
    if not isinstance(workflow, dict):
        return
    # API format: every value is a dict with `class_type`.
    api_format = (
        workflow
        and all(
            isinstance(v, dict) and "class_type" in v
            for v in workflow.values()
        )
    )
    if api_format:
        for node in workflow.values():
            if isinstance(node, dict):
                yield node
        return
    # Editor format: nodes list with a `type` discriminator.
    nodes = workflow.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict):
                yield node


def _node_class(node: dict[str, Any]) -> str:
    """Return the node's class identifier, supporting both API and editor formats."""
    cls = node.get("class_type") or node.get("type")
    return str(cls) if cls else ""


def _node_inputs(node: dict[str, Any]) -> dict[str, Any]:
    """Best-effort inputs dict. API format uses `inputs`; editor format
    bundles values into `widgets_values` (a list ordered by widget)."""
    inputs = node.get("inputs")
    if isinstance(inputs, dict):
        return inputs
    return {}


def extract_smart_tags(
    metadata: dict[str, Any] | None,
    workflow: dict[str, Any] | None,
) -> list[str]:
    """Return the auto-derived tag list for one library entry.

    Extracted families (each prefixed `auto:`):
      * model:<checkpoint-name>     (CheckpointLoaderSimple `ckpt_name`)
      * sampler:<sampler-name>      (KSampler `sampler_name`)
      * scheduler:<scheduler-name>  (KSampler `scheduler`)
      * lora:<lora-name>            (each LoraLoader `lora_name`)
      * custom_node:<class_type>    (each unique node class_type)
      * cfg:<float>                 (metadata.cfg if present)
      * steps:<int>                 (metadata.steps if present)
      * seed:<int>                  (metadata.seed if present)

    Output order is stable: model → sampler/scheduler → lora* (sorted) →
    custom_node* (sorted) → cfg/steps/seed. Duplicates removed.
    """
    out: list[str] = []
    seen: set[str] = set()
    metadata = metadata or {}
    workflow = workflow or {}

    # Walk the workflow nodes to pull model/sampler/lora/class_type tags.
    loras: list[str] = []
    classes: set[str] = set()
    model_tag_added = False
    sampler_tag_added = False

    for node in _iter_workflow_nodes(workflow):
        cls = _node_class(node)
        if cls:
            classes.add(cls)
        inputs = _node_inputs(node)

        if cls.startswith("CheckpointLoader") and "ckpt_name" in inputs and not model_tag_added:
            _add_tag(out, seen, "model", inputs["ckpt_name"])
            model_tag_added = True
        if cls.startswith("KSampler") and not sampler_tag_added:
            if "sampler_name" in inputs:
                _add_tag(out, seen, "sampler", inputs["sampler_name"])
                sampler_tag_added = True
            if "scheduler" in inputs:
                _add_tag(out, seen, "scheduler", inputs["scheduler"])
        if cls.startswith("LoraLoader") and "lora_name" in inputs:
            slug = _slugify_value(inputs["lora_name"])
            if slug:
                loras.append(slug)

    for lora in sorted(set(loras)):
        _add_tag(out, seen, "lora", lora)
    for cls in sorted(classes):
        _add_tag(out, seen, "custom_node", cls)

    # metadata-supplied numerics override workflow nodes when present.
    if "model" in metadata and not model_tag_added:
        _add_tag(out, seen, "model", metadata["model"])
    if "sampler" in metadata and not sampler_tag_added:
        _add_tag(out, seen, "sampler", metadata["sampler"])
    if "lora" in metadata:
        items = metadata["lora"]
        if isinstance(items, (list, tuple)):
            for lora in items:
                _add_tag(out, seen, "lora", lora)
        else:
            _add_tag(out, seen, "lora", items)

    for key in ("cfg", "steps", "seed"):
        if key in metadata and metadata[key] not in (None, ""):
            _add_tag(out, seen, key, metadata[key])

    return out
