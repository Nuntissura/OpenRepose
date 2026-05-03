"""Canonical markdown render + parse for projects + target tree + requirements.

Spec: `.gov/spec/openrepose_requirements_v0_1.md` § "EXP120 Worked Example".

The spec's worked example shows two markdown forms:

1. *Operator natural-prose form* (input only): freeform sections like
   "## Hard Output Requirement" with prose descriptions.
2. *Canonical structured form* (round-trippable): explicit `### <rule_id>`
   blocks with `key: value` lines.

This module implements the **canonical form** only. Round-trip is strict:
`render(parse(md)) == md` and `parse(render(rows)) == rows` modulo a
trailing newline. Operator natural-prose import is deferred to v0.2 per
the WP-I3-007 Fallback Register.

Hand-rolled (no PyYAML dep). The canonical form is tightly controlled, so
a line-based state-machine parser is sufficient and avoids dragging in a
YAML library. See WP-I3-007 Decisions Log for the dep-cost reasoning.

Canonical form:

```
# Project: <slug>

- name: <name>
- status: <status>

## Sets

| slug | name | expected_card_count | target_per_card | ordering |
|------|------|---------------------|-----------------|----------|
| SF | Standing frontal pussy exposure | 20 | 8 | 1 |
| SR | Standing rear ass exposure | 20 | 8 | 2 |

## Requirements

### <RULE-ID-001>

- kind: <kind>
- severity: <severity>
- short: <short>
- machine_check_fn: <fn>           (optional)
- auto_route_to: <route>           (optional)
- accept_terms: <a, b, c>          (optional)
- reject_terms: <a, b, c>          (optional)

### <RULE-ID-002>
...
```

Render is deterministic: groups sorted by `(ordering, slug)`, requirements
sorted by `rule_id`. Optional fields are rendered only when present;
empty/NULL values are omitted (so empty-array vs NULL is collapsed in v0.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

_VALID_PROJECT_STATUSES = ("active", "paused", "closed")
_VALID_KINDS = (
    "hard_output", "body", "pose", "face", "crop", "quality",
    "clothing_story", "structural", "custom",
)
_VALID_SEVERITIES = ("auto-route", "block", "warn", "info")
# Per Fallback Register: 'custom' kind defers to v0.2.
_V01_PARSEABLE_KINDS = tuple(k for k in _VALID_KINDS if k != "custom")


@dataclass
class ParsedTargetGroup:
    slug: str
    name: str
    expected_card_count: int
    target_per_card: int
    ordering: int


@dataclass
class ParsedRequirement:
    rule_id: str
    kind: str
    severity: str
    short: str
    machine_check_fn: str | None = None
    auto_route_to: str | None = None
    accept_terms: list[str] | None = None
    reject_terms: list[str] | None = None


@dataclass
class ParsedProject:
    slug: str
    name: str
    status: str
    groups: list[ParsedTargetGroup] = field(default_factory=list)
    requirements: list[ParsedRequirement] = field(default_factory=list)


class CanonicalMarkdownError(ValueError):
    """Raised when canonical markdown does not match the strict shape."""


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render_markdown(project: ParsedProject) -> str:
    """Render a `ParsedProject` to canonical markdown.

    Output ends in exactly one trailing newline. Round-trip is byte-stable:
    `render(parse(render(p))) == render(p)`.
    """
    if project.status not in _VALID_PROJECT_STATUSES:
        raise CanonicalMarkdownError(
            f"project.status must be one of {_VALID_PROJECT_STATUSES}; got {project.status!r}"
        )

    lines: list[str] = []
    lines.append(f"# Project: {project.slug}")
    lines.append("")
    lines.append(f"- name: {project.name}")
    lines.append(f"- status: {project.status}")
    lines.append("")
    lines.append("## Sets")
    lines.append("")
    lines.append("| slug | name | expected_card_count | target_per_card | ordering |")
    lines.append("|------|------|---------------------|-----------------|----------|")
    for g in sorted(project.groups, key=lambda g: (g.ordering, g.slug)):
        lines.append(
            f"| {g.slug} | {g.name} | {g.expected_card_count} | {g.target_per_card} | {g.ordering} |"
        )
    lines.append("")
    lines.append("## Requirements")
    for r in sorted(project.requirements, key=lambda r: r.rule_id):
        if r.kind not in _VALID_KINDS:
            raise CanonicalMarkdownError(
                f"requirement {r.rule_id}: kind must be one of {_VALID_KINDS}; got {r.kind!r}"
            )
        if r.severity not in _VALID_SEVERITIES:
            raise CanonicalMarkdownError(
                f"requirement {r.rule_id}: severity must be one of {_VALID_SEVERITIES}; got {r.severity!r}"
            )
        lines.append("")
        lines.append(f"### {r.rule_id}")
        lines.append("")
        lines.append(f"- kind: {r.kind}")
        lines.append(f"- severity: {r.severity}")
        lines.append(f"- short: {r.short}")
        if r.machine_check_fn is not None:
            lines.append(f"- machine_check_fn: {r.machine_check_fn}")
        if r.auto_route_to is not None:
            lines.append(f"- auto_route_to: {r.auto_route_to}")
        if r.accept_terms:
            lines.append(f"- accept_terms: {', '.join(r.accept_terms)}")
        if r.reject_terms:
            lines.append(f"- reject_terms: {', '.join(r.reject_terms)}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def parse_markdown(markdown_text: str) -> ParsedProject:
    """Parse canonical markdown into a `ParsedProject`.

    Strict line-based state machine. Raises `CanonicalMarkdownError` on
    any deviation from the canonical shape with a line-number diagnostic.
    """
    if not markdown_text.endswith("\n"):
        markdown_text = markdown_text + "\n"
    lines = markdown_text.split("\n")
    # Trailing element of split is empty when text ends with newline; drop it.
    if lines and lines[-1] == "":
        lines.pop()

    idx = 0
    n = len(lines)

    def err(line_no: int, msg: str) -> CanonicalMarkdownError:
        return CanonicalMarkdownError(f"line {line_no}: {msg}")

    # --- Project header ---
    if idx >= n or not lines[idx].startswith("# Project: "):
        raise err(idx + 1, "expected '# Project: <slug>' as first line")
    slug = lines[idx][len("# Project: "):].strip()
    if not slug:
        raise err(idx + 1, "project slug is empty")
    idx += 1

    if idx >= n or lines[idx] != "":
        raise err(idx + 1, "expected blank line after project header")
    idx += 1

    project_kv: dict[str, str] = {}
    while idx < n and lines[idx].startswith("- "):
        key, value = _parse_kv(lines[idx], idx + 1)
        project_kv[key] = value
        idx += 1

    if "name" not in project_kv:
        raise err(idx + 1, "project block missing 'name'")
    if "status" not in project_kv:
        raise err(idx + 1, "project block missing 'status'")
    if project_kv["status"] not in _VALID_PROJECT_STATUSES:
        raise err(idx + 1, f"project status must be one of {_VALID_PROJECT_STATUSES}")

    project = ParsedProject(
        slug=slug,
        name=project_kv["name"],
        status=project_kv["status"],
    )

    if idx >= n or lines[idx] != "":
        raise err(idx + 1, "expected blank line before '## Sets'")
    idx += 1

    # --- Sets section ---
    if idx >= n or lines[idx] != "## Sets":
        raise err(idx + 1, "expected '## Sets' heading")
    idx += 1

    if idx >= n or lines[idx] != "":
        raise err(idx + 1, "expected blank line after '## Sets'")
    idx += 1

    expected_table_header = "| slug | name | expected_card_count | target_per_card | ordering |"
    if idx >= n or lines[idx] != expected_table_header:
        raise err(idx + 1, f"expected table header '{expected_table_header}'")
    idx += 1

    expected_separator = "|------|------|---------------------|-----------------|----------|"
    if idx >= n or lines[idx] != expected_separator:
        raise err(idx + 1, "expected table separator row")
    idx += 1

    while idx < n and lines[idx].startswith("|"):
        cells = _parse_table_row(lines[idx], idx + 1, expected_columns=5)
        try:
            group = ParsedTargetGroup(
                slug=cells[0],
                name=cells[1],
                expected_card_count=int(cells[2]),
                target_per_card=int(cells[3]),
                ordering=int(cells[4]),
            )
        except ValueError as e:
            raise err(idx + 1, f"target-group row malformed: {e}") from e
        if group.expected_card_count <= 0:
            raise err(idx + 1, "expected_card_count must be > 0")
        if group.target_per_card <= 0:
            raise err(idx + 1, "target_per_card must be > 0")
        project.groups.append(group)
        idx += 1

    if idx >= n or lines[idx] != "":
        raise err(idx + 1, "expected blank line before '## Requirements'")
    idx += 1

    # --- Requirements section ---
    if idx >= n or lines[idx] != "## Requirements":
        raise err(idx + 1, "expected '## Requirements' heading")
    idx += 1

    while idx < n:
        # Each requirement: leading blank line, then '### <rule_id>', blank, then key:value lines.
        if lines[idx] != "":
            raise err(idx + 1, "expected blank line before next '### <rule_id>'")
        idx += 1
        if idx >= n:
            break
        if not lines[idx].startswith("### "):
            raise err(idx + 1, "expected '### <rule_id>' heading")
        rule_id = lines[idx][len("### "):].strip()
        if not rule_id:
            raise err(idx + 1, "rule_id is empty")
        idx += 1

        if idx >= n or lines[idx] != "":
            raise err(idx + 1, "expected blank line after '### <rule_id>'")
        idx += 1

        req_kv: dict[str, str] = {}
        while idx < n and lines[idx].startswith("- "):
            key, value = _parse_kv(lines[idx], idx + 1)
            req_kv[key] = value
            idx += 1

        for required in ("kind", "severity", "short"):
            if required not in req_kv:
                raise err(idx, f"requirement {rule_id}: missing '{required}'")
        kind = req_kv["kind"]
        if kind == "custom":
            raise err(idx, f"requirement {rule_id}: kind='custom' is deferred to v0.2 per WP-I3-007 Fallback Register")
        if kind not in _V01_PARSEABLE_KINDS:
            raise err(idx, f"requirement {rule_id}: kind must be one of {_V01_PARSEABLE_KINDS}")
        if req_kv["severity"] not in _VALID_SEVERITIES:
            raise err(idx, f"requirement {rule_id}: severity must be one of {_VALID_SEVERITIES}")

        req = ParsedRequirement(
            rule_id=rule_id,
            kind=kind,
            severity=req_kv["severity"],
            short=req_kv["short"],
            machine_check_fn=req_kv.get("machine_check_fn"),
            auto_route_to=req_kv.get("auto_route_to"),
            accept_terms=_parse_terms(req_kv.get("accept_terms")),
            reject_terms=_parse_terms(req_kv.get("reject_terms")),
        )
        project.requirements.append(req)

    return project


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _parse_kv(line: str, line_no: int) -> tuple[str, str]:
    """Parse `- key: value` from a kv-list line."""
    body = line[2:]  # drop '- '
    if ":" not in body:
        raise CanonicalMarkdownError(f"line {line_no}: kv-list line missing ': '")
    key, _, value = body.partition(":")
    return key.strip(), value.strip()


def _parse_table_row(line: str, line_no: int, *, expected_columns: int) -> list[str]:
    """Parse a markdown table data row into trimmed cells."""
    if not line.endswith("|"):
        raise CanonicalMarkdownError(f"line {line_no}: table row must end with '|'")
    inner = line[1:-1]  # drop the leading and trailing pipes
    cells = [c.strip() for c in inner.split("|")]
    if len(cells) != expected_columns:
        raise CanonicalMarkdownError(
            f"line {line_no}: expected {expected_columns} cells; got {len(cells)}"
        )
    return cells


def _parse_terms(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p]
    return parts or None


# ---------------------------------------------------------------------------
# Convenience: convert ParsedProject to/from dicts (for command JSON I/O)
# ---------------------------------------------------------------------------


def project_to_dict(p: ParsedProject) -> dict[str, Any]:
    return {
        "slug": p.slug,
        "name": p.name,
        "status": p.status,
        "groups": [
            {
                "slug": g.slug,
                "name": g.name,
                "expected_card_count": g.expected_card_count,
                "target_per_card": g.target_per_card,
                "ordering": g.ordering,
            }
            for g in sorted(p.groups, key=lambda g: (g.ordering, g.slug))
        ],
        "requirements": [
            {
                "rule_id": r.rule_id,
                "kind": r.kind,
                "severity": r.severity,
                "short": r.short,
                "machine_check_fn": r.machine_check_fn,
                "auto_route_to": r.auto_route_to,
                "accept_terms": list(r.accept_terms) if r.accept_terms else None,
                "reject_terms": list(r.reject_terms) if r.reject_terms else None,
            }
            for r in sorted(p.requirements, key=lambda r: r.rule_id)
        ],
    }
