"""Requirements editor + target tree subpackage (WP-I3-007).

Spec: `.gov/spec/openrepose_requirements_v0_1.md`. Composes with the schema
landed by WP-I3-003 (`library_target_groups`, `library_target_cards`,
`library_rules`, `library_target_card_counts` view).

Data-layer functions take a live `psycopg.Connection` so the dispatcher
controls transaction boundaries.
"""

from __future__ import annotations

from .errors import OpenReposeRequirementsError
from .markdown_io import (
    CanonicalMarkdownError,
    ParsedProject,
    ParsedRequirement,
    ParsedTargetGroup,
    parse_markdown,
    render_markdown,
)
from .rules import (
    LibraryRule,
    create_rule,
    delete_rule,
    dump_rules,
    get_rule_with_inheritance,
    update_rule,
)

__all__ = [
    "CanonicalMarkdownError",
    "LibraryRule",
    "OpenReposeRequirementsError",
    "ParsedProject",
    "ParsedRequirement",
    "ParsedTargetGroup",
    "create_rule",
    "delete_rule",
    "dump_rules",
    "get_rule_with_inheritance",
    "parse_markdown",
    "render_markdown",
    "update_rule",
]
