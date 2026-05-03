"""Library tab GUI (WP-I2-006).

Spec: `.gov/spec/openrepose_library_v0_1.md` Library Tab UI Requirements.
Operator-facing surface; LLM agents drive the same workflow via the
WP-I2-004 commands.
"""

from .pane import LibraryPane

__all__ = ["LibraryPane"]
