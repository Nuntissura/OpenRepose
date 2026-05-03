# OpenRepose Spec Index

OpenRepose specs live here as versioned plain-Markdown files. Each spec describes one slice of the application contract. Workpackets cite the spec sections they implement. Spec changes must be paired with a workpacket of class `DOCUMENTATION` or higher.

## Active Specs

| Version | File | Scope | Status |
|---------|------|-------|--------|
| v0.1 | `openrepose_v0_1.md` | Initial application contract. First feature: 3D-rig yaw exporter (Feature 1). Calibration overlay (Feature 2). Yaw terminology, rig requirements, GUI requirements, export formats. | DRAFT |
| v0.1 | `openrepose_library_v0_1.md` | Feature 3: OpenPose Library + ComfyUI coupling + PostgreSQL. Authored by WP-I1-033. Locks DB schema, command surface, ComfyUI bridge contract, multi-operator concurrency model. Implementation lands in I2 iteration. | DRAFT |
| v0.1 | `openrepose_amood_v0_1.md` | I3 — AMood blueprint operationalization. Authored by WP-I3-001. Maps AMood concepts (batch/card/run/output) to OpenRepose DB; locks card-schema extension on `library_entries`, anti-repetition service, command surface (init_batch_package / library_create_card / library_create_variants / compatibility_check / accepted_set_audit / amood_export_tsv / amood_import_tsv), package layout under `outputs/library/<project>/<batch>/`. References operator-canonical blueprint at `.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md`. | LOCKED |
| v0.1 | `openrepose_intake_v0_1.md` | I3 — Intake & triage. Authored by WP-I3-001. Locks Project / Task / Batch / Card / Run / Output hierarchy with new `library_projects` + `library_tasks` + `library_outputs` + `library_pose_guides` tables; status enum across all levels; folder layout (`outputs/intake/`, `outputs/library/`); two-stage acceptance (LLM may soft_accept; operator-only finalize); default-staging ComfyUI bridge; 16 dispatcher commands; `state.library.intake` + `state.library.guidance` blocks; 3 new snapshot targets. | LOCKED |
| v0.1 | `openrepose_rules_v0_1.md` | I3 — Rule registry. Authored by WP-I3-001. Locks rule anatomy, four severity tiers (auto-route / block / warn / info), error citation contract, global-vs-project-scoped split, audit coverage requirements, initial registry of 25 rule_ids (RUL-000..006 promoting existing repo rules + Adult Production Boundary first rule, AMOOD-001..004, INTAKE-001..004, TARGET-001..003, REQ-001..003, SAFE-001..003). | LOCKED |
| v0.1 | `openrepose_requirements_v0_1.md` | I3 — Typed scoped requirements + target tree. Authored by WP-I3-001. Locks 8-kind taxonomy (hard_output / body / pose / face / crop / quality / clothing_story / structural / custom), inheritance, target tree (`library_target_groups` + `library_target_cards`), counters from `library_outputs.status`, satisfaction semantics (`fully_satisfied = count_satisfied AND quota_satisfied`), forecast warning, EXP120 worked example, markdown round-trip importer/exporter. | LOCKED |

## Spec Versioning

- `v0.1` is the initial draft.
- Major revisions bump the minor: `v0.2`, `v0.3`, etc.
- Major contract reshapes bump the major: `v1.0`, `v2.0`. A major bump requires an explicit workpacket and operator sign-off.
- Old spec files stay in this folder for historical reference. The latest live spec is the highest version in the `Active` table above.

## Spec Authoring Rules

- Write contract, not implementation. The spec says what; product code says how.
- Use the locked yaw terminology (`0`, `her-left N`, `her-right N`). Forbidden phrases listed in `.gov/AGENTS.md`.
- Be explicit about non-goals. A spec without an "Out Of Scope" section is incomplete.
- Reference dependencies by name and version (`mediapipe >= 0.10.21`, `pyrender >= 0.1.45`, etc.).
- Keep the spec readable by a fresh assistant or human collaborator who has just run `orstart`.

## Future Spec Files

As OpenRepose grows beyond yaw, additional spec files will land here for each major feature area. Naming convention:

```text
openrepose_<area>_v<X_Y>.md
```

Examples (not yet authored):

```text
openrepose_v0_1.md            # initial app contract; in this iteration
openrepose_yaw_v0_2.md        # later refinements to the yaw feature
openrepose_<future-area>_v0_1.md
```
