"""WP-I3-007 — canonical markdown round-trip.

The EXP120 worked example is the acceptance gate: render(parse(md)) must
be byte-equal to the input modulo trailing newline. Spec contract in
`.gov/spec/openrepose_requirements_v0_1.md` § "EXP120 Worked Example";
implementation in `.product/src/openrepose/library/requirements/markdown_io.py`.
"""

from __future__ import annotations

import pytest

from openrepose.library.requirements.markdown_io import (
    CanonicalMarkdownError,
    ParsedProject,
    ParsedRequirement,
    ParsedTargetGroup,
    parse_markdown,
    project_to_dict,
    render_markdown,
)


EXP120_CANONICAL_MARKDOWN = """\
# Project: exposure-120

- name: Exposure 120
- status: active

## Sets

| slug | name | expected_card_count | target_per_card | ordering |
|------|------|---------------------|-----------------|----------|
| SF | Standing frontal pussy exposure | 20 | 8 | 1 |
| SR | Standing rear ass exposure | 20 | 8 | 2 |
| IF | Sitting frontal pussy exposure | 20 | 8 | 3 |
| IR | Sitting rear ass exposure | 20 | 8 | 4 |
| LF | Lying frontal pussy exposure | 20 | 8 | 5 |
| LR | Lying rear ass exposure | 20 | 8 | 6 |

## Requirements

### EXP120-BODY-001

- kind: body
- severity: warn
- short: Top-heavy fantasy proportions; slender frame.
- accept_terms: slender_shoulders, narrow_torso, narrow_hips, skinny_legs, delicate_wrists_ankles, narrow_waist, oversized_breasts
- reject_terms: broad_shoulders, wide_hips, thick_legs, stocky_body, masculine_frame, average_breasts, small_breasts

### EXP120-CLOTH-001

- kind: clothing_story
- severity: block
- short: Reveal must be clothing-mediated; full nude rejects.
- accept_terms: lifted, pulled_aside, opened, lowered, shifted, held_away

### EXP120-CROP-001

- kind: crop
- severity: warn
- short: Full head; no joint crops; foot rules per card.
- accept_terms: full_head_visible, lower_leg_crop_when_clean
- reject_terms: head_crop, hand_wrist_crop, foot_ankle_crop, joint_crop

### EXP120-FACE-001

- kind: face
- severity: warn
- short: Expression reinforces exposure.
- accept_terms: gaze, wink, soft_smile, playful, coy_inviting, over_shoulder_tease
- reject_terms: blank, bored, dead_eyed, smudged, doll_like, generic_ai

### EXP120-POSE-001

- kind: pose
- severity: warn
- short: Natural feminine inviting; reject brute spread / catalog nude.
- accept_terms: soft_shoulders, weight_shift, turned_hips, bent_knee, leaning_seated, over_shoulder, clothing_adjustment, supportive_hand
- reject_terms: brute_legspread, stiff_power_stance, anatomy_showcase, catalog_nude, awkward_forced_exposure, full_nude_display

### EXP120-QUAL-001

- kind: quality
- severity: warn
- short: Standard AI artifact rejection.
- reject_terms: soft_smudged_face, soft_focus, bad_eyes_mouth, bad_hands, bad_feet, broken_joints, warped_target, pasted_inpaint, fake_ui_text_watermark, incoherent_clothing_edge

### EXP120-RES-001

- kind: hard_output
- severity: auto-route
- short: 1080x1440 exact
- machine_check_fn: (width = 1080 AND height = 1440)
- auto_route_to: intermediate_evidence

### EXP120-RES-002

- kind: hard_output
- severity: auto-route
- short: 3:4 portrait aspect ratio
- machine_check_fn: (abs(width::float / height::float - 0.75) < 0.001)
- auto_route_to: intermediate_evidence
"""


def test_exp120_canonical_round_trip_byte_stable() -> None:
    """Acceptance gate per WP-I3-007 handoff: render(parse(md)) == md."""
    parsed = parse_markdown(EXP120_CANONICAL_MARKDOWN)
    rendered = render_markdown(parsed)
    assert rendered == EXP120_CANONICAL_MARKDOWN, (
        "Canonical render did not byte-equal input.\n"
        f"--- input ---\n{EXP120_CANONICAL_MARKDOWN}\n"
        f"--- rendered ---\n{rendered}"
    )


def test_exp120_double_round_trip_stable() -> None:
    """Second round trip equals first: render(parse(render(parse(md)))) == render(parse(md))."""
    once = render_markdown(parse_markdown(EXP120_CANONICAL_MARKDOWN))
    twice = render_markdown(parse_markdown(once))
    assert once == twice


def test_exp120_parsed_structure() -> None:
    """The parser extracts the right number of groups + requirements."""
    parsed = parse_markdown(EXP120_CANONICAL_MARKDOWN)
    assert parsed.slug == "exposure-120"
    assert parsed.name == "Exposure 120"
    assert parsed.status == "active"
    assert len(parsed.groups) == 6
    assert {g.slug for g in parsed.groups} == {"SF", "SR", "IF", "IR", "LF", "LR"}
    assert all(g.expected_card_count == 20 and g.target_per_card == 8 for g in parsed.groups)
    assert len(parsed.requirements) == 8
    assert {r.rule_id for r in parsed.requirements} == {
        "EXP120-BODY-001", "EXP120-CLOTH-001", "EXP120-CROP-001", "EXP120-FACE-001",
        "EXP120-POSE-001", "EXP120-QUAL-001", "EXP120-RES-001", "EXP120-RES-002",
    }


def test_render_orders_groups_by_ordering_then_slug() -> None:
    """Groups must render in (ordering ASC, slug ASC) order regardless of input order."""
    project = ParsedProject(slug="p", name="P", status="active")
    project.groups = [
        ParsedTargetGroup(slug="B", name="b", expected_card_count=1, target_per_card=1, ordering=2),
        ParsedTargetGroup(slug="A", name="a", expected_card_count=1, target_per_card=1, ordering=1),
        ParsedTargetGroup(slug="C", name="c", expected_card_count=1, target_per_card=1, ordering=1),
    ]
    rendered = render_markdown(project)
    a_idx = rendered.index("| A ")
    c_idx = rendered.index("| C ")
    b_idx = rendered.index("| B ")
    assert a_idx < c_idx < b_idx


def test_render_orders_requirements_by_rule_id() -> None:
    """Requirements render in rule_id ASC order regardless of input order."""
    project = ParsedProject(slug="p", name="P", status="active")
    project.requirements = [
        ParsedRequirement(rule_id="X-002", kind="body", severity="warn", short="b"),
        ParsedRequirement(rule_id="X-001", kind="body", severity="warn", short="a"),
    ]
    rendered = render_markdown(project)
    a_idx = rendered.index("X-001")
    b_idx = rendered.index("X-002")
    assert a_idx < b_idx


def test_parse_rejects_missing_project_header() -> None:
    bad = "## Sets\n\n| slug |\n|------|\n"
    with pytest.raises(CanonicalMarkdownError, match="expected '# Project: <slug>'"):
        parse_markdown(bad)


def test_parse_rejects_missing_required_kv() -> None:
    bad = """\
# Project: x

- name: X

## Sets

| slug | name | expected_card_count | target_per_card | ordering |
|------|------|---------------------|-----------------|----------|

## Requirements
"""
    with pytest.raises(CanonicalMarkdownError, match="missing 'status'"):
        parse_markdown(bad)


def test_parse_rejects_invalid_severity() -> None:
    bad = """\
# Project: x

- name: X
- status: active

## Sets

| slug | name | expected_card_count | target_per_card | ordering |
|------|------|---------------------|-----------------|----------|

## Requirements

### X-001

- kind: body
- severity: maybe
- short: bad
"""
    with pytest.raises(CanonicalMarkdownError, match="severity must be"):
        parse_markdown(bad)


def test_parse_rejects_custom_kind_v01() -> None:
    """v0.1 does not parse 'custom' kind from markdown (WP-I3-007 fallback)."""
    bad = """\
# Project: x

- name: X
- status: active

## Sets

| slug | name | expected_card_count | target_per_card | ordering |
|------|------|---------------------|-----------------|----------|

## Requirements

### X-001

- kind: custom
- severity: warn
- short: bad
"""
    with pytest.raises(CanonicalMarkdownError, match="custom.*v0.2"):
        parse_markdown(bad)


def test_parse_rejects_zero_expected_card_count() -> None:
    bad = """\
# Project: x

- name: X
- status: active

## Sets

| slug | name | expected_card_count | target_per_card | ordering |
|------|------|---------------------|-----------------|----------|
| A | a | 0 | 1 | 1 |

## Requirements
"""
    with pytest.raises(CanonicalMarkdownError, match="expected_card_count must be > 0"):
        parse_markdown(bad)


def test_empty_project_renders_minimal_skeleton() -> None:
    """Empty project: header + empty Sets table + empty Requirements section."""
    project = ParsedProject(slug="empty", name="Empty", status="active")
    rendered = render_markdown(project)
    expected = """\
# Project: empty

- name: Empty
- status: active

## Sets

| slug | name | expected_card_count | target_per_card | ordering |
|------|------|---------------------|-----------------|----------|

## Requirements
"""
    assert rendered == expected
    # Round-trips.
    assert render_markdown(parse_markdown(rendered)) == rendered


def test_project_to_dict_preserves_order() -> None:
    parsed = parse_markdown(EXP120_CANONICAL_MARKDOWN)
    d = project_to_dict(parsed)
    group_slugs = [g["slug"] for g in d["groups"]]
    assert group_slugs == ["SF", "SR", "IF", "IR", "LF", "LR"]
    rule_ids = [r["rule_id"] for r in d["requirements"]]
    assert rule_ids == sorted(rule_ids)
