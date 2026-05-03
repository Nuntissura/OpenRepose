# Requirements and target trees

Every project has its own requirements and its own target structure. EXP120 wants 1080×1440 + clothing-mediated reveal + top-heavy proportions and 6 sets × 20 cards × 8 promoted = 960 total. A different project has different rules. OpenRepose stores both as structured DB rows authored either through the GUI editor or from operator markdown via round-trip importer.

Contract is in `.gov/spec/openrepose_requirements_v0_1.md`. Adult Production Boundary applies (`.gov/doc/manual/adult-production-boundary.md`).

## Requirement anatomy

A requirement is a project-scoped rule (per `.gov/spec/openrepose_rules_v0_1.md`) with these fields:

```text
rule_id              project-scoped (e.g. EXP120-RES-001)
kind                 hard_output | body | pose | face | crop | quality | clothing_story | structural | custom
scope_type           project | task | batch | card
severity             auto-route | block | warn | info
short                one-line summary
machine_check_fn     SQL expression (NULL = operator-judged)
auto_route_to        subdirectory under intake/<task_id>/diagnostic/ (auto-route only)
accept_terms[]       structured accept list
reject_terms[]       structured reject list
manual_link          relative path + anchor
```

## Severity tiers

```text
auto-route  deterministic check failed; route to evidence; doesn't count
block       hard refusal; safety-critical (juvenile/coercive content)
warn        cite + allow; operator/LLM acknowledges
info        display only
```

EXP120 examples by tier:

```text
auto-route   EXP120-RES-001  width=1080 AND height=1440  -> diagnostic/intermediate_evidence/
block        EXP120-CLOTH-001  reveal must be clothing-mediated; full nude rejects
warn         EXP120-BODY-001   top-heavy fantasy proportions
info         REQ-001           inheritance: lower scope wins
```

## Inheritance {#inheritance}

Lower scope wins on conflict. The requirements editor visualizes the chain.

```text
project requirement: EXP120-CROP-001 severity=warn (full head; no joint crops)
   inherits to all tasks
      inherits to all batches
         card-scope override on SF-15: CROP-002 severity=warn (allow lower-leg crop when clean)
         => SF-15 evaluates against CROP-002, not the project default
```

Rule citation: `REQ-001`.

## The 8 canonical kinds

The requirements editor checklist nudges across these 8 kinds when a project is created or edited (rule `REQ-003`).

| Kind | Use when |
|------|----------|
| `hard_output` | Resolution / aspect ratio / file format / hash uniqueness — deterministic, machine-checkable. |
| `body` | Body type acceptance/reject lists — operator-judged or face-age-estimator-advised. |
| `pose` | Pose acceptance/reject lists. |
| `face` | Face/expression rules. |
| `crop` | Head/joint/foot/hand crop rules. |
| `quality` | AI artifact rejection. |
| `clothing_story` | Clothing-mediated reveal mechanism (lifted/pulled aside/opened/lowered/shifted/held away). |
| `structural` | Per-set per-card target counts; tree shape. |
| `custom` | Operator-defined; rule_id project-scoped. |

## Auto-route reversibility {#auto-route}

Auto-routed outputs land in `intake/<task_id>/diagnostic/intermediate_evidence/` and do not count toward target. They are reversible: if a metadata bug mis-detected resolution, the operator runs `intake_reroute output_id=<id> target_status=pending` and the output enters the queue. Rule citation: `REQ-002`.

## Target tree

Structured target with rolling counters. Group → cards → counters.

```text
library_target_groups
  project_id, group_slug, group_name, expected_card_count, target_per_card, ordering
library_target_cards
  group_id, card_slug, card_id, target_promoted, stability_target
```

EXP120 instantiation:

```text
6 groups × 20 cards × 8 promoted = 960 total
```

## EXP120 worked example {#exp120}

Operator-supplied markdown round-trips to structured rows. This is the canonical teaching artifact.

### Operator markdown (input)

```text
## Sets
| SF-01..SF-20 | 20 | Standing frontal pussy exposure |
| SR-01..SR-20 | 20 | Standing rear ass exposure |
| IF-01..IF-20 | 20 | Sitting frontal pussy exposure |
| IR-01..IR-20 | 20 | Sitting rear ass exposure |
| LF-01..LF-20 | 20 | Lying frontal pussy exposure |
| LR-01..LR-20 | 20 | Lying rear ass exposure |

Each card needs 8 accepted images. 120 poses × 8 = 960 accepted total.

## Hard Output Requirement
1080x1440, 3:4 portrait. Lower-res outputs are intermediate evidence; do not count.

## Clothing / Story Requirement
Full nude rejects. Reveal must come from clothing being: lifted, pulled aside, opened,
lowered, shifted, or held away from the body.

## Body Requirement
Slender shoulders, narrow torso, narrow hips, skinny long legs, delicate wrists/ankles,
narrow waist, oversized breasts, top-heavy fantasy proportions.
Reject: broad shoulders, wide hips, thick legs, stocky body, masculine frame, average breasts.

## Pose Requirement
Accept: soft shoulders, weight shift, turned hips, bent knee, leaning/seated interaction,
over-shoulder look, clothing-adjustment pose, supportive hand placement.
Reject: brute spread, stiff power stance, anatomy showcase, catalog nude, awkward forced
exposure, full-nude display.

## Face / Expression
Accept: gaze, wink, soft smile, playful, coy/inviting, over-shoulder tease.
Reject: blank, bored, dead-eyed, smudged, doll-like, generic AI.

## Crop Rules
Full head always visible. No head/wrist/ankle crops. No joint crops. No-foot-crop cards
must show full feet. Crop-allowed cards may crop lower legs only when composed cleanly.

## Quality Gate
Reject: soft/smudged face, soft-focus full image, bad eyes/mouth, bad hands/fingers,
bad feet/toes, broken joints, warped target anatomy, pasted/inpaint patch look,
fake UI/text/watermark/camera-studio artifact, incoherent clothing edge or skin/fabric boundary.
```

### Structured rows (output)

```yaml
project:
  slug: exposure-120
  name: "Exposure 120"
  status: active

target_tree:
  total_target_promoted: 960
  groups:
    - { slug: SF, name: "Standing frontal pussy exposure", expected_card_count: 20, target_per_card: 8 }
    - { slug: SR, name: "Standing rear ass exposure",      expected_card_count: 20, target_per_card: 8 }
    - { slug: IF, name: "Sitting frontal pussy exposure",  expected_card_count: 20, target_per_card: 8 }
    - { slug: IR, name: "Sitting rear ass exposure",       expected_card_count: 20, target_per_card: 8 }
    - { slug: LF, name: "Lying frontal pussy exposure",    expected_card_count: 20, target_per_card: 8 }
    - { slug: LR, name: "Lying rear ass exposure",         expected_card_count: 20, target_per_card: 8 }

requirements:
  - rule_id: EXP120-RES-001
    kind: hard_output
    severity: auto-route
    short: "1080x1440 exact"
    machine_check_fn: "(width = 1080 AND height = 1440)"
    auto_route_to: "intermediate_evidence"

  - rule_id: EXP120-RES-002
    kind: hard_output
    severity: auto-route
    short: "3:4 portrait aspect ratio"
    machine_check_fn: "(abs(width::float / height::float - 0.75) < 0.001)"
    auto_route_to: "intermediate_evidence"

  - rule_id: EXP120-CLOTH-001
    kind: clothing_story
    severity: block
    short: "Reveal must be clothing-mediated; full nude rejects."
    accept_terms: ["lifted","pulled_aside","opened","lowered","shifted","held_away"]

  - rule_id: EXP120-BODY-001
    kind: body
    severity: warn
    short: "Top-heavy fantasy proportions; slender frame."
    accept_terms: ["slender_shoulders","narrow_torso","narrow_hips","skinny_legs","delicate_wrists_ankles","narrow_waist","oversized_breasts"]
    reject_terms: ["broad_shoulders","wide_hips","thick_legs","stocky_body","masculine_frame","average_breasts","small_breasts"]

  - rule_id: EXP120-POSE-001
    kind: pose
    severity: warn
    short: "Natural feminine inviting; reject brute spread / catalog nude."
    accept_terms: ["soft_shoulders","weight_shift","turned_hips","bent_knee","leaning_seated","over_shoulder","clothing_adjustment","supportive_hand"]
    reject_terms: ["brute_legspread","stiff_power_stance","anatomy_showcase","catalog_nude","awkward_forced_exposure","full_nude_display"]

  - rule_id: EXP120-FACE-001
    kind: face
    severity: warn
    short: "Expression reinforces exposure."
    accept_terms: ["gaze","wink","soft_smile","playful","coy_inviting","over_shoulder_tease"]
    reject_terms: ["blank","bored","dead_eyed","smudged","doll_like","generic_ai"]

  - rule_id: EXP120-CROP-001
    kind: crop
    severity: warn
    short: "Full head; no joint crops; foot rules per card."
    accept_terms: ["full_head_visible","lower_leg_crop_when_clean"]
    reject_terms: ["head_crop","hand_wrist_crop","foot_ankle_crop","joint_crop"]

  - rule_id: EXP120-QUAL-001
    kind: quality
    severity: warn
    short: "Standard AI artifact rejection."
    reject_terms: ["soft_smudged_face","soft_focus","bad_eyes_mouth","bad_hands","bad_feet","broken_joints","warped_target","pasted_inpaint","fake_ui_text_watermark","incoherent_clothing_edge"]
```

The round-trip importer parses this markdown into rows; the exporter renders rows back to markdown. Diff before save = trust.

## Where requirements surface {#completeness}

- **Project pane**: requirements checklist + target-tree progress (`SF: 24/160 promoted`, `SR: 8/160`, total `47/960`).
- **Triage view header**: current image's auto-route results + pending operator judgments per requirement, color-coded.
- **`state.library.requirements`**: active requirements list with rule_ids; LLM agents read this to see what governs the current action.
- **Errors**: every reject cites the requirement rule_id with manual link and fix.

The completeness checklist nudge (rule `REQ-003`) prompts: "have you set requirements for: hard_output? body? pose? face? crop? quality? clothing_story? structural?" — without forcing.

## Commands

```text
project_set_target_tree     project_id, groups[] -> creates/replaces target tree
project_add_requirement     project_id, rule_id, kind, severity, short, ... -> insert
project_set_requirement     scope_type, scope_id, rule_id, ... -> upsert; lower-scope override
project_dump_requirements   project_id [, scope filter] -> [requirements with inheritance chain]
project_render_markdown     project_id -> markdown projection
project_import_markdown     project_id, markdown_text -> parse + upsert; report diff before commit
```
