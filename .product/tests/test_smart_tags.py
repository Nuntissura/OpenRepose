"""Smart-tag extraction (WP-I2-003). No DB required."""

from __future__ import annotations

from openrepose.library.smart_tags import (
    AUTO_TAG_PREFIX,
    _slugify_value,
    extract_smart_tags,
)


def test_slugify_lowercases_and_replaces_whitespace():
    assert _slugify_value("Flux Dev v2") == "flux-dev-v2"


def test_slugify_strips_unsafe_chars():
    # Forward slash, period, and colon stay; everything else collapses.
    assert _slugify_value("flux/dev:1.0") == "flux/dev:1.0"
    assert _slugify_value("foo!@#bar") == "foo-bar"


def test_slugify_returns_empty_for_blank():
    assert _slugify_value("") == ""
    assert _slugify_value("   ") == ""
    assert _slugify_value(None) == ""


def test_extract_returns_empty_for_empty_inputs():
    assert extract_smart_tags(None, None) == []
    assert extract_smart_tags({}, {}) == []


def test_extract_pulls_model_sampler_lora_from_api_workflow():
    workflow = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "fluxDev_v2.safetensors"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "seed": 12345,
            },
        },
        "3": {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "intimate-style-v3.safetensors"},
        },
        "4": {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "lighting-pack.safetensors"},
        },
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": "default.vae"}},
    }
    tags = extract_smart_tags({}, workflow)
    assert f"{AUTO_TAG_PREFIX}model:fluxdev_v2.safetensors" in tags
    assert f"{AUTO_TAG_PREFIX}sampler:dpmpp_2m" in tags
    assert f"{AUTO_TAG_PREFIX}scheduler:karras" in tags
    # Lora tags appear sorted, both present.
    assert f"{AUTO_TAG_PREFIX}lora:intimate-style-v3.safetensors" in tags
    assert f"{AUTO_TAG_PREFIX}lora:lighting-pack.safetensors" in tags
    # custom_node:VAELoader and other class types appear.
    assert f"{AUTO_TAG_PREFIX}custom_node:vaeloader" in tags


def test_extract_dedupes_duplicate_loras():
    workflow = {
        "a": {"class_type": "LoraLoader", "inputs": {"lora_name": "x.safetensors"}},
        "b": {"class_type": "LoraLoader", "inputs": {"lora_name": "x.safetensors"}},
    }
    tags = extract_smart_tags({}, workflow)
    lora_tags = [t for t in tags if t.startswith(f"{AUTO_TAG_PREFIX}lora:")]
    assert lora_tags == [f"{AUTO_TAG_PREFIX}lora:x.safetensors"]


def test_extract_uses_metadata_when_workflow_missing_fields():
    metadata = {
        "model": "sdxl_base.safetensors",
        "sampler": "euler",
        "lora": ["a.safetensors", "b.safetensors"],
        "cfg": 6.5,
        "steps": 28,
        "seed": 9001,
    }
    tags = extract_smart_tags(metadata, {})
    assert f"{AUTO_TAG_PREFIX}model:sdxl_base.safetensors" in tags
    assert f"{AUTO_TAG_PREFIX}sampler:euler" in tags
    assert f"{AUTO_TAG_PREFIX}lora:a.safetensors" in tags
    assert f"{AUTO_TAG_PREFIX}lora:b.safetensors" in tags
    assert f"{AUTO_TAG_PREFIX}cfg:6.5" in tags
    assert f"{AUTO_TAG_PREFIX}steps:28" in tags
    assert f"{AUTO_TAG_PREFIX}seed:9001" in tags


def test_workflow_model_overrides_metadata_model():
    """When both supply model, prefer the workflow node (more accurate)."""
    workflow = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "real_model.safetensors"},
        }
    }
    metadata = {"model": "wrong_model.safetensors"}
    tags = extract_smart_tags(metadata, workflow)
    model_tags = [t for t in tags if t.startswith(f"{AUTO_TAG_PREFIX}model:")]
    assert model_tags == [f"{AUTO_TAG_PREFIX}model:real_model.safetensors"]


def test_extract_handles_editor_format_with_type():
    """Editor format uses `nodes: [{type, ...}]` instead of API dict."""
    workflow = {
        "nodes": [
            {"type": "KSampler", "widgets_values": ["euler", "normal", 7.0]},
            {"type": "VAELoader"},
        ]
    }
    tags = extract_smart_tags({}, workflow)
    # We can't extract the sampler value (editor format buries it in
    # widgets_values, no name); but we DO record the node class.
    assert f"{AUTO_TAG_PREFIX}custom_node:ksampler" in tags
    assert f"{AUTO_TAG_PREFIX}custom_node:vaeloader" in tags


def test_metadata_zero_cfg_is_not_dropped():
    """`0` is a valid value; only `None`/empty get filtered."""
    tags = extract_smart_tags({"cfg": 0}, {})
    assert f"{AUTO_TAG_PREFIX}cfg:0" in tags
