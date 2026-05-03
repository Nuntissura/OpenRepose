# OpenRepose Spec Index

OpenRepose specs live here as versioned plain-Markdown files. Each spec describes one slice of the application contract. Workpackets cite the spec sections they implement. Spec changes must be paired with a workpacket of class `DOCUMENTATION` or higher.

## Active Specs

| Version | File | Scope | Status |
|---------|------|-------|--------|
| v0.1 | `openrepose_v0_1.md` | Initial application contract. First feature: 3D-rig yaw exporter (Feature 1). Calibration overlay (Feature 2). Yaw terminology, rig requirements, GUI requirements, export formats. | DRAFT |
| v0.1 | `openrepose_library_v0_1.md` | Feature 3: OpenPose Library + ComfyUI coupling + PostgreSQL. Authored by WP-I1-033. Locks DB schema, command surface, ComfyUI bridge contract, multi-operator concurrency model. Implementation lands in I2 iteration. | DRAFT |

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
