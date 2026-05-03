# OpenRepose AMood Integration Spec — v0.1

Version: v0.1 (DRAFT)
Authored by: WP-I3-001 (DOCUMENTATION)
Spec scope: how OpenRepose operationalizes the AMood adult-moodboard blueprint. The blueprint stays canonical for *structure*; this spec covers *operation*.

This spec is the OpenRepose-side contract. It defines DB shape, command surface, package layout, and integration points so I3 IMPLEMENTATION workpackets land against a stable contract.

## Purpose

The AMood blueprint at `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md` is the operator-authored, provider/model-agnostic structural source for adult-production batches: tier table, package layout, 8+ TSV schemas with additive-only rule, fast-triage 4-field + full-rubric 16-field scoring, accepted-set diversity audit, anti-repetition ledger, abandonment criteria.

OpenRepose operationalizes that blueprint by:

1. Storing AMood concepts (batch, card, run, output) in the PostgreSQL library so they are queryable, multi-operator safe, and survive folder churn.
2. Generating AMood TSV artifacts as views over the DB rather than maintaining duplicate stores.
3. Registering pose guides exported by the yaw exporter as first-class artifacts paired to cards.
4. Closing the ComfyUI generation loop into the library via the existing bridge custom node (extended in I3).
5. Surfacing every blueprint rule (anti-repetition threshold, abandonment trigger, fast-triage fail-fast) in OpenRepose's rule registry so cold-start LLMs and operators see citations instead of needing to re-read the 2070-line blueprint.

Adult Production Boundary applies (per `.gov/topology.yaml` `repo_rules.adult_production_boundary` and `.gov/AGENTS.md`): this spec uses raw production language; OpenRepose does not track legal/consent paperwork; the operator owns those obligations.

## Blueprint Provenance

```text
canonical structural source: .gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md
authored by:                 operator
modification policy:         OpenRepose specs do not modify the blueprint. Drift fixes go in this spec or new specs.
acknowledgement primitive:   every AMood-related command response embeds adult_production_boundary acknowledgement_required=true (per WP-I3-002 LLM stance acknowledgement primitives).
```

If a real production batch exposes a blueprint gap (a new diversity axis, a new rejection reason), the assistant amends the blueprint Changelog (operator-side decision) and this spec's column-additive-only rule absorbs the new field.

## Concept-to-Entity Mapping

| AMood concept | OpenRepose entity | Source of truth |
| --- | --- | --- |
| Batch package folder | `library_batches` row + `outputs/library/<project_slug>/<batch_slug>/` directory | DB row authoritative; folder is a projection (regenerable from DB on demand). |
| Moodboard card | `library_entries` row with card-schema fields (extended below) | DB row. |
| Story file | `library_entries.story_beats` text records (existing I2 surface) | DB. |
| Pose guide PNG + JSON | `library_pose_guides` row (NEW), FK from `library_runs.pose_guide_id` | DB. Files live under `outputs/library/<project_slug>/<batch_slug>/pose_guides/<guide_type>/`. |
| Generated image | `library_outputs` row (NEW per `openrepose_intake_v0_1.md`), FK to `library_runs` | DB. Files routed through intake first (see intake spec). |
| Quota plan TSV | View over `library_target_groups` + `library_target_cards` (per `openrepose_requirements_v0_1.md`) | DB. |
| Batch matrix TSV | View over `library_entries` filtered to one batch | DB. |
| Variant ladder TSV | View over `library_entries` parent/child (`parent_card_id`) | DB. |
| Anti-repetition ledger TSV | View over `library_entries.dedupe_signature` filtered to project | DB. |
| Prompt manifest TSV | View over `library_entries.prompts` joined to runs | DB. |
| Run manifest TSV | View over `library_runs` | DB. |
| Review manifest TSV | View over `library_outputs.review_*` fields joined to scorecards | DB. |
| Scorecard TSV | View over `library_scorecards` (NEW) | DB. |

TSV exports preserve AMood's locked column order (additive-only rule). New columns appended on the right; never reorder, rename, or delete existing columns. Header changes append a Changelog entry in the blueprint and add a column to this spec's view definitions.

## Card Schema Extension (on `library_entries`)

I2 shipped `library_entries` with prompts/story_beats/notes/tags/comfyui_workflows. I3 adds AMood card fields for direct queryability and dedupe.

```sql
ALTER TABLE library_entries
  ADD COLUMN sexual_trigger          text,
  ADD COLUMN kink_cue                text,
  ADD COLUMN porn_archetype          text,
  ADD COLUMN fantasy_mode            text,            -- 'archetype-heavy fantasy' | 'casual intimate' | 'staged voyeur' | 'raw-cam performance' | 'editorial porn' | NULL
  ADD COLUMN explicit_family         text,
  ADD COLUMN exposure_detail         text,
  ADD COLUMN archetype_signal        text,
  ADD COLUMN scene_engine            text,            -- 'performance' | 'private-room' | 'editorial-porn' | 'raw-cam' | 'environment-pressure'
  ADD COLUMN shot_purpose            text,
  ADD COLUMN dedupe_signature        text NOT NULL,   -- '<explicit_family>|<pose_family>|<orientation>|<wardrobe_state>|<support_object>|<setting_family>|<camera_family>|<palette_family>'
  ADD COLUMN compatibility_signature text NOT NULL,
  ADD COLUMN parent_card_id          uuid REFERENCES library_entries(id),  -- variant ladder
  ADD COLUMN variant_label           text,            -- 'baseline' | 'intimate' | 'explicit_plus' | 'editorial' | 'raw_cam' | 'story_plus' | NULL
  ADD COLUMN stability_target        int  NOT NULL DEFAULT 4,  -- AMood blueprint default; project may override on library_target_cards
  ADD COLUMN target_promoted         int,             -- nullable per-card target (project may set higher than stability)
  ADD COLUMN abandonment_reason      text,            -- 'trigger_fights_model' | 'pose_needs_guide' | 'wardrobe_incompatible' | 'identity_drift' | 'duplicate_scene' | 'safety_boundary' | NULL
  ADD COLUMN abandoned_after_seeds   int;
```

Indexes (added in the same migration as the columns):

```sql
CREATE INDEX idx_library_entries_dedupe_signature_trgm ON library_entries USING gin (dedupe_signature gin_trgm_ops);
CREATE INDEX idx_library_entries_explicit_family       ON library_entries (explicit_family);
CREATE INDEX idx_library_entries_fantasy_mode          ON library_entries (fantasy_mode);
CREATE INDEX idx_library_entries_porn_archetype        ON library_entries (porn_archetype);
CREATE INDEX idx_library_entries_parent_card_id        ON library_entries (parent_card_id) WHERE parent_card_id IS NOT NULL;
```

Field bodies (free text). Diversity axes (pose_family, orientation, wardrobe_state, held_object, support_object, setting_family, lighting_family, camera_family, gaze, mouth_tongue, palette_family, accent_color, texture_details, etc.) live as `tags` on the entry — re-using I2's `tags` + `entry_tags` + `pg_trgm` infrastructure. AMood's matrix axes are tag namespaces, not new columns. Tag namespace convention:

```text
amood:explicit_family:<value>
amood:pose_family:<value>
amood:orientation:<value>
amood:wardrobe_state:<value>
amood:held_object:<value>
amood:support_object:<value>
amood:setting_family:<value>
amood:lighting_family:<value>
amood:camera_family:<value>
amood:gaze:<value>
amood:mouth_tongue:<value>
amood:palette_family:<value>
amood:accent_color:<value>
```

## Anti-Repetition Service

Blueprint rule: "If a new row matches 6 or more dedupe fields with a recent accepted row, revise it before generation." Threshold (default 6) is configurable per batch on `library_batches.dedupe_threshold` (range 4–8).

```sql
CREATE OR REPLACE FUNCTION library.dedupe_check(
  p_project_id uuid,
  p_dedupe_signature text,
  p_threshold int DEFAULT 6
) RETURNS TABLE (
  candidate_id uuid,
  candidate_slug text,
  overlap_count int
) ...
-- splits both signatures on '|', counts shared axes, returns rows with overlap >= p_threshold,
-- restricted to library_entries.status IN ('soft_accepted','promoted') and same project.
```

Commands invoke `dedupe_check` before promoting a card from DRAFT to TRIAGE-eligible. A match returns the matching card_id + overlap count + manual-override flag (`library_entries.dedupe_override_reason`). LLM agents must not write `dedupe_override_reason` without operator-issued token (cited as `AMOOD-001`).

Rule citation:

```text
AMOOD-001  anti-repetition threshold (default >= 6 axis overlap with accepted card requires revision; project-overridable)  severity: warn
AMOOD-002  abandonment trigger met (12 seeds without trigger_clarity >= 4, or 8 seeds with repeated structural failure)     severity: warn
AMOOD-003  fast-triage fail-fast (any of 4 fields fails the bar => reject before full rubric runs)                          severity: warn
AMOOD-004  juvenile/coercive/hidden-camera content => card-level abandon, not just seed-level                               severity: block
```

## Acceptance & Scoring Storage

The fast-triage 4 fields and full-rubric 16 fields are stored on `library_scorecards` (NEW) — see `openrepose_intake_v0_1.md` for the full table definition. Promotion enforcement is a CHECK constraint at DB level:

```text
promotion_decision = 'promote' is REJECTED by trigger if any of:
  adult_gate_score < 5
  trigger_clarity_score < 4
  explicit_target_score < 4
  anatomy_score < 3
  artifact_score < 4
  arousal_score < 4
  beauty_score < 4
  primary_rejection_reason IN ('juvenile_coded', 'coercion_coded', 'hidden_camera_coded')
```

Triggering rule_ids: `AMOOD-003` (fast triage), `AMOOD-004` (safety boundary).

## Command Surface (AMood-specific)

These commands extend the I2 dispatcher. All return responses embed `adult_production_boundary` per WP-I3-002.

```text
init_batch_package
  input:  project_slug, batch_slug, tier ('quick'|'mini'|'production'), primary_explicit_family, dedupe_threshold (optional, default 6)
  output: batch_id, package_path, intake_dir
  effect: creates library_batches row + outputs/library/<project_slug>/<batch_slug>/{cards,moodboards,prompt_blocks,pose_guides,manifests,accepted,soft_accepted}/ folder layout + INDEX.md + README.md from blueprint templates.
  idempotent: re-running validates layout and reports diffs without overwriting.

library_create_card
  input:  batch_id, slug, sexual_trigger, kink_cue, porn_archetype, fantasy_mode, explicit_family, ...
  output: card_id, dedupe_signature, compatibility_signature
  effect: creates library_entries row with card-schema fields populated. Calls dedupe_check pre-insert; emits AMOOD-001 warning when threshold met.

library_create_variants
  input:  parent_card_id, variants (subset of 'baseline','intimate','explicit_plus','editorial','raw_cam','story_plus')
  output: child_card_ids[]
  effect: spawns child rows with parent_card_id FK + variant_label set; default change-rules per blueprint variant ladder.

compatibility_check
  input:  card_id (DRAFT) OR (sexual_trigger, pose_family, orientation, camera_family, wardrobe_state, support_object, palette_family)
  output: pass:bool, hard_rejects:[reason,...], warnings:[reason,...]
  effect: encodes AMood compatibility-check table. Hard rejects: camera-cant-see-target, wardrobe-covers-target, prop-blocks-target, fantasy-set-camera-mismatch, pose-implausible, palette-collapse, juvenile/coercive/voyeur-violation, multi-trigger-conflict.

accepted_set_audit
  input:  batch_id (or project_id for cross-batch)
  output: per-axis realized_coverage + priority_flag ('ok'|'watch'|'priority') per AMood thresholds (>= 0.75, 0.5–0.74, < 0.5)
  effect: writes audit rows to library_diversity_audits (NEW) keyed by (batch_id, axis); updates state.library.audit.

amood_export_tsv
  input:  batch_id, schema ('quota_plan'|'batch_matrix'|'variant_ladder'|'anti_repetition'|'prompt_manifest'|'run_manifest'|'review_manifest'|'scorecard'|'pose_control_guide'|'series_plan')
  output: tsv_text (full file, AMood-locked column order)
  effect: read-only view query rendered to TSV. New columns appended right of header per blueprint additive-only rule.

amood_import_tsv
  input:  batch_id, schema, tsv_text
  output: imported_count, conflict_count, errors[]
  effect: parses TSV in AMood-locked column order; upserts to underlying tables (matrix-row -> library_entries DRAFT; quota-plan -> library_target_groups). Operator-token-gated to prevent LLM-driven mass overwrite.
```

## Package Layout

Re-paths AMood's blueprint `references/prompts/<batch_slug>/` onto OpenRepose's `outputs/` policy.

```text
outputs/library/<project_slug>/<batch_slug>/
  INDEX.md                       generated from DB on init_batch_package; refreshable
  README.md                      generated from blueprint template
  stories/<card_id>_<slug>_story.md
  cards/<card_id>_<slug>.md      generated from library_entries on demand (read-only render)
  moodboards/<card_id>_<slug>_moodboard.md
  matrices/<batch_slug>_batch_matrix.tsv          generated view; do not edit by hand
  matrices/<batch_slug>_variant_ladder.tsv         generated view
  matrices/<batch_slug>_quota_plan.tsv             generated view
  ledgers/<batch_slug>_anti_repetition_ledger.tsv  generated view
  manifests/<batch_slug>_prompt_manifest.tsv       generated view
  manifests/<batch_slug>_run_manifest.tsv          generated view
  manifests/<batch_slug>_review_manifest.tsv       generated view
  manifests/<batch_slug>_scorecard.tsv             generated view
  prompt_blocks/<card_id>_<slug>_positive.txt
  prompt_blocks/<card_id>_<slug>_negative.txt
  pose_guides/openpose/{png,json,source,rejected}/
  pose_guides/dwpose/{png,json,source,rejected}/
  accepted/                       finalized outputs (operator stage-2)
  soft_accepted/                  LLM stage-1 acceptances awaiting operator finalize
```

`accepted/` and `soft_accepted/` are populated by intake promotion (see `openrepose_intake_v0_1.md`). All directories under `outputs/` remain gitignored; the DB is authoritative.

## State Surface

```json
{
  "library": {
    "amood": {
      "active_batch_id": "<uuid or null>",
      "active_batch_slug": "<slug>",
      "tier": "production",
      "primary_explicit_family": "vulva-pussy-exposure",
      "stable_cards": 3,
      "unstable_cards": 17,
      "abandoned_cards": 2,
      "dedupe_recent_warnings": [
        {"card_id": "<uuid>", "overlap_count": 7, "matched_card_slug": "hotel-robe-bed-edge"}
      ]
    }
  }
}
```

Detailed counters and target-tree state live in `state.library.targets` (per `openrepose_requirements_v0_1.md`). Triage state lives in `state.library.intake` (per `openrepose_intake_v0_1.md`).

## Snapshot Targets

Two new headless-compliant snapshot targets:

```text
amood_card_with_pose         renders a card detail view: card metadata + paired pose guide PNG + variant strip (if variants exist)
amood_batch_overview         renders a batch-level summary: target tree + accepted-set audit + abandoned cards + dedupe warnings
```

Both follow snapshot-subsystem rules (no `raise_()`, no focus theft, no foreground hijack).

## Out Of Scope For v0.1

- Probabilistic auto-prefilter (face-age estimator, hand-sanity classifier). Specified as advisory hints only in `openrepose_intake_v0_1.md`; ML-backed implementations are separate RESEARCH+IMPLEMENTATION WPs.
- Cross-project anti-repetition (only intra-project for v0.1).
- Embedding-based card similarity. Trigram on dedupe_signature is sufficient for v0.1.
- Series plan / video keyframe sequencing (mentioned in blueprint; deferred to a later spec).
- Real-time blueprint sync (operator manually amends blueprint when AMood evolves; this spec follows on its own cadence).
- Batch wholesale acceptance command. Per blueprint guidance, acceptance happens at card/variant level; bulk macros may be added later but never bypass the per-card stability rule.

## Reality Boundary For v0.1

- **Real Seam**: blueprint operationalized via DB-authoritative storage with 16 new card-schema columns on `library_entries`, a `library.dedupe_check` SQL function, 6 new commands (init_batch_package / library_create_card / library_create_variants / compatibility_check / accepted_set_audit / amood_export_tsv / amood_import_tsv), 4 AMood-prefixed rule_ids in the registry (AMOOD-001..004), and the blueprint reference tracked in Git.
- **User-Visible Win**: an LLM agent given EXP120-style operator targets reads `state.library.amood`, calls `init_batch_package` + `library_create_card` + `compatibility_check` + `accepted_set_audit`; an operator opens the Library tab AMood Batch sub-pane (added in I3 implementation) and sees per-batch state without reading the 2070-line blueprint.
- **Proof Target**: I3 IMPLEMENTATION WPs cite this spec section by anchor; new commands return responses with `adult_production_boundary` envelope; pytest covers AMOOD-003 fast-triage CHECK constraint and AMOOD-004 safety-boundary CHECK constraint at DB level; integration test exercises a 5-card mini-tier batch end-to-end.
- **Allowed Temporary Fallbacks**: TSV import (`amood_import_tsv`) may parse a subset of schemas in early I3 IMPLEMENTATION WPs; full schema coverage is the Promotion Guard for the importer WP.
- **Promotion Guard**: do not declare AMood integration v0.1 stable until: (a) operator runs one production-tier batch end-to-end through OpenRepose without external scratch files, (b) generated TSVs round-trip through `amood_export_tsv` + `amood_import_tsv` without loss, (c) accepted-set audit produces correct realized-coverage numbers cross-checked with operator's manual count.
