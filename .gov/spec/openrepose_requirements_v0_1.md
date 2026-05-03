# OpenRepose Requirements & Targets Spec — v0.1

Version: v0.1 (DRAFT)
Authored by: WP-I3-001 (DOCUMENTATION)
Spec scope: typed scoped requirements registry, target tree (sets → cards → per-card targets), counters, satisfaction semantics, EXP120 worked example.

This spec composes with `openrepose_rules_v0_1.md` (requirements are a kind of project-scoped rule) and `openrepose_intake_v0_1.md` (counters derive from `library_outputs.status`). Adult Production Boundary applies (`.gov/topology.yaml` `repo_rules.adult_production_boundary`).

## Purpose

Different projects have different requirements. EXP120 demands 1080×1440 exact + clothing-mediated reveal + top-heavy proportions; another project might demand 16:9 cinematic + full-body framing + a different body type. Requirements must be:

1. **Typed** so the system can route, count, filter, and check uniformly.
2. **Scoped** to project / task / batch / card so a project-level rule inherits to all children unless overridden.
3. **Severity-tiered** so deterministic gates auto-route while qualitative rules warn or display only.
4. **Optionally machine-checkable** so deterministic rules (resolution) are evaluated automatically and qualitative rules (body type) wait for operator judgment.
5. **Round-trippable** between operator markdown and structured DB rows so authoring is easy and review is auditable.

Targets must be **structured** (a project may have 6 sets × 20 cards × 8 promoted = 960 total) so per-set, per-card, and per-project counters roll up correctly, and so an LLM agent can self-pace by reading `gap` and `forecast_ok`.

## Requirement Anatomy

A requirement is a project-scoped rule (per `openrepose_rules_v0_1.md`) with extra fields. Stored in `library_rules` (see rules spec) plus an extended view:

```text
rule_id              project-scoped (e.g. EXP120-RES-001)
kind                 enum: hard_output | body | pose | face | crop | quality | clothing_story | structural | custom
scope_type           project | task | batch | card
scope_id             FK to that level
severity             auto-route | block | warn | info
short                one-line summary
machine_check_fn     SQL expression or Python predicate (NULL = operator-judged)
auto_route_to        subdirectory name under intake/<task_id>/diagnostic/ (when severity=auto-route)
accept_terms[]       structured accept list (e.g. for body kind: ['slender_shoulders','narrow_torso',...])
reject_terms[]       structured reject list
manual_link          relative path + anchor
inherited_from       NULL when set at this scope; ancestor scope_id otherwise
created_at, last_validated_at
```

## Inheritance

Lower scope wins on conflict. Visualized in the requirements editor.

```text
project requirement: EXP120-CROP-001 severity=warn (full head visible, no joint crops)
    inherits to all tasks
    inherits to all batches
        card-scope override: SF-15 may have CROP-002 severity=warn (allow lower-leg crop when clean)
        => SF-15 evaluates against CROP-002, not the project default
```

Inheritance chain visible to operator and LLM: an LLM querying requirements for card SF-15 sees `[CROP-002 (card scope, overrides), CROP-001 (project scope, inherited but overridden)]` and can act knowing the override.

Rule citation: `REQ-001` (lower scope wins).

## Target Tree

A target is operator-declared expected output count. Counters are derived (single source of truth = `library_outputs.status`).

### Tables

```sql
CREATE TABLE library_target_groups (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id          uuid NOT NULL REFERENCES library_projects(id) ON DELETE CASCADE,
  group_slug          text NOT NULL,                          -- 'SF', 'SR', 'IF', 'IR', 'LF', 'LR' for EXP120
  group_name          text NOT NULL,                          -- 'Standing frontal pussy exposure'
  expected_card_count int  NOT NULL,                          -- 20 for EXP120
  target_per_card     int  NOT NULL,                          -- 8 for EXP120 (project-set; may differ from AMood stability)
  ordering            int  NOT NULL DEFAULT 0,
  UNIQUE (project_id, group_slug)
);

CREATE TABLE library_target_cards (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id            uuid NOT NULL REFERENCES library_target_groups(id) ON DELETE CASCADE,
  card_slug           text NOT NULL,                          -- 'SF-01' .. 'SF-20'
  card_id             uuid REFERENCES library_entries(id),    -- nullable; populated when card is created
  target_promoted     int  NOT NULL,                          -- inherited from group.target_per_card; per-card override allowed
  stability_target    int  NOT NULL DEFAULT 4,                -- AMood blueprint default
  UNIQUE (group_id, card_slug)
);
```

### Counters

Derived from `library_outputs.status`. Maintained as a PG view:

```sql
CREATE VIEW library_target_card_counts AS
SELECT
  tc.id                                                                        AS target_card_id,
  tc.card_id,
  tc.target_promoted,
  tc.stability_target,
  count(*) FILTER (WHERE o.status = 'pending')         AS pending_count,
  count(*) FILTER (WHERE o.status = 'triaging')        AS triaging_count,
  count(*) FILTER (WHERE o.status = 'soft_accepted')   AS soft_accepted_count,
  count(*) FILTER (WHERE o.status = 'promoted')        AS promoted_count,
  count(*) FILTER (WHERE o.status = 'rejected')        AS rejected_count,
  count(*) FILTER (WHERE o.status = 'diagnostic')      AS diagnostic_count,
  count(*) FILTER (WHERE o.status = 'abandoned')       AS abandoned_count
FROM library_target_cards tc
LEFT JOIN library_runs    r ON r.card_id = tc.card_id
LEFT JOIN library_outputs o ON o.run_id = r.id
GROUP BY tc.id, tc.card_id, tc.target_promoted, tc.stability_target;
```

Group-level and project-level counters are SUM aggregations over this view. Materialized variants may be added later if performance requires.

### Stable vs. Complete

```text
stable_card     promoted_count >= stability_target  (AMood blueprint rule, default 4)
complete_card   promoted_count >= target_promoted   (project rule; EXP120 sets 8)
```

Both flags exist on every card. Display both. Rule citation: `TARGET-003`.

## Counters and Satisfaction Semantics

Counters at every level use the same names. Aggregations roll up.

```text
gap            = max(0, target_promoted_count - promoted_count)
in_flight      = pending_count + triaging_count + soft_accepted_count
forecast_ok    = in_flight >= gap
count_satisfied = gap == 0
quota_satisfied = (per AMood accepted-set diversity audit: every axis realized_coverage >= 0.75)
fully_satisfied = count_satisfied AND quota_satisfied
```

Rule citations:

```text
TARGET-001  satisfaction = count + quota                              severity: warn
TARGET-002  forecast warning (in_flight < gap)                         severity: warn
TARGET-003  stability (AMood) vs completeness (project)               severity: info
```

### Forecast Warning

```text
forecast_ok = false  =>  surface in state.library.targets and triage view header.
                          Can mean: operator over-targeted, or LLM under-seeded, or excessive auto-route.
                          Action: operator may revise target down OR LLM seeds more cards OR investigate why intake is low.
```

This is the early-warning the operator currently lacks: today they only find out at the end of triage that the gap won't close.

## State Surface

Tree-shaped under `state.library.targets`:

```json
{
  "library": {
    "targets": {
      "project": {
        "slug": "exposure-120",
        "target_promoted": 960, "promoted": 47,
        "gap": 913, "in_flight": 87, "forecast_ok": false,
        "count_satisfied": false, "quota_satisfied": false, "fully_satisfied": false
      },
      "groups": [
        {"slug": "SF", "name": "Standing frontal pussy exposure",
         "target_promoted": 160, "promoted": 24, "gap": 136,
         "stable_cards": 1, "complete_cards": 0, "expected_cards": 20, "created_cards": 18},
        {"slug": "SR", "name": "Standing rear ass exposure",
         "target_promoted": 160, "promoted": 8, "gap": 152,
         "stable_cards": 0, "complete_cards": 0, "expected_cards": 20, "created_cards": 12}
      ],
      "active_task": {
        "task_id": "T-2026-05-03-01",
        "target_promoted": 80, "promoted": 12, "soft_accepted": 7,
        "pending": 41, "rejected": 880, "gap": 68,
        "in_flight": 48, "forecast_ok": false, "satisfied": false
      },
      "active_card": {
        "card_id": "<uuid>", "slug": "SF-15",
        "stability_target": 4, "target_promoted": 8,
        "promoted": 2, "stable": false, "complete": false
      }
    }
  }
}
```

LLMs read `targets.active_task.gap` to self-pace; loop until `gap == 0 || abandonment_triggered`.

## Requirement Kinds

Eight canonical kinds + `custom`:

```text
hard_output      file format / resolution / aspect ratio / size / hash uniqueness
body             body-type acceptance/reject lists; operator-judged or face-age-estimator-advised
pose             pose acceptance/reject lists; operator-judged
face             face/expression acceptance/reject lists
crop             head/joint/foot/hand crop rules
quality          AI artifact rejection list
clothing_story   clothing-mediated reveal mechanism (lifted/pulled aside/opened/lowered/shifted/held away)
structural       per-set per-card target counts; tree shape
custom           operator-defined; rule_id project-scoped
```

The requirements editor checklist (rule citation `REQ-003`) nudges across these 8 kinds when a project is created or edited.

## EXP120 Worked Example

Operator-supplied markdown round-trips to structured rows. This is the teaching artifact for `requirements-and-targets.md` manual topic.

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
Full head always visible. No head crop. No hand/wrist crop. No foot/ankle crop.
No-foot-crop cards must show full feet. Crop-allowed cards may crop lower legs only when
composed cleanly, never at joints.

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
    - { slug: SF, name: "Standing frontal pussy exposure", expected_card_count: 20, target_per_card: 8, ordering: 1 }
    - { slug: SR, name: "Standing rear ass exposure",      expected_card_count: 20, target_per_card: 8, ordering: 2 }
    - { slug: IF, name: "Sitting frontal pussy exposure",  expected_card_count: 20, target_per_card: 8, ordering: 3 }
    - { slug: IR, name: "Sitting rear ass exposure",       expected_card_count: 20, target_per_card: 8, ordering: 4 }
    - { slug: LF, name: "Lying frontal pussy exposure",    expected_card_count: 20, target_per_card: 8, ordering: 5 }
    - { slug: LR, name: "Lying rear ass exposure",         expected_card_count: 20, target_per_card: 8, ordering: 6 }

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

The round-trip importer/exporter (separate I3 IMPLEMENTATION WP) parses this markdown into rows and renders structured rows back to markdown. Diff before save = trust.

## Commands

```text
project_set_target_tree     project_id, groups[]                                  -> creates/replaces library_target_groups + library_target_cards
project_add_requirement     project_id, rule_id, kind, severity, short, ...        -> insert library_rules row at project scope
project_set_requirement     scope_type, scope_id, rule_id, ... (override fields)   -> upsert; lower-scope override
project_dump_requirements   project_id [, scope filter]                            -> [requirements with inheritance chain]
project_render_markdown     project_id                                             -> markdown projection of the structured rows
project_import_markdown     project_id, markdown_text                              -> parse + upsert; report diff before commit
target_recount              scope_id, scope_type                                   -> rebuild materialized counters from library_outputs
target_summary              scope_id (project|task|batch|card)                     -> {target_promoted, promoted, gap, in_flight, forecast_ok, count_satisfied, quota_satisfied, fully_satisfied}
```

All return responses with `adult_production_boundary` envelope.

## Out Of Scope For v0.1

- Rule-versioning per requirement (a project can change a requirement; the new version replaces; no per-version history beyond Git log of operator edits to markdown).
- ML-backed automatic evaluation of body/pose/face requirements (advisory hints only).
- Cross-project requirement reuse (copy a project's requirements when starting a new one — manual operator workflow only in v0.1).
- LLM-issued project-scope requirement authoring (operator-only in v0.1).
- Mid-flight retargeting that re-evaluates already-promoted outputs against new requirements (promoted stays promoted; new requirements apply only to subsequent outputs).

## Reality Boundary For v0.1

- **Real Seam**: 2 new tables (`library_target_groups`, `library_target_cards`); `library_rules` extended with `kind` + `auto_route_to` + `accept_terms[]` + `reject_terms[]`; `library_target_card_counts` view; 8 new commands; structured target tree with rolling counters; `state.library.targets` block; 8-kind taxonomy locked; auto-route severity behavior specified.
- **User-Visible Win**: an operator pastes EXP120 markdown into the requirements editor, gets back structured rules; LLM agent reads `state.library.targets` and self-paces a 960-image task to satisfaction; operator sees per-set, per-card, project-total progress at a glance; 60–80% of LLM outputs at wrong resolution auto-route before triage and never burn operator time.
- **Proof Target**: I3 IMPLEMENTATION WPs cite this spec by anchor; pytest covers target counter rollup correctness (per-card → per-group → per-project), markdown round-trip (operator markdown → DB rows → markdown matches), auto-route reversibility, inheritance resolution; integration test with EXP120 example provides at least 6 promoted outputs across ≥2 sets and shows correct counters.
- **Allowed Temporary Fallbacks**: markdown importer may parse a subset of kinds (hard_output, body, pose, face, crop, quality, clothing_story) in early I3 WPs; `structural` kind (target tree) authored via dedicated `project_set_target_tree` command. `custom` kind deferred to v0.2.
- **Promotion Guard**: do not declare requirements v0.1 stable until: (a) EXP120 markdown round-trips through importer + exporter without loss, (b) `target_summary` returns correct values for a synthetic 960-target project with mixed promoted/soft_accepted/pending/auto-routed outputs, (c) inheritance chain visible in the editor for a project + card-scope override case.
