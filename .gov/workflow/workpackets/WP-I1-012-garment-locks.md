# WP-I1-012 - Garment Locks

## Header

- **Owner**: TBD (operator)
- **Date Opened**: 2026-05-02
- **Status**: DEFERRED
- **Iteration**: I2+ (not part of I1)
- **Workflow Version**: 1.0
- **Packet Class**: IMPLEMENTATION
- **Effort Estimate**: M
- **Linked Spec**: future spec section "Garment locks".

## Intent

Extend the locked-rig concept to lock garment landmarks (necklines, straps, collars, hem lines) so they rotate with the body and survive ControlNet conditioning. Operator marks the garment outline once on the master portrait (similar UX to the calibration overlay); OpenRepose carries those landmarks through every yaw rotation and emits them as a sidecar file consumable by a *secondary* ControlNet (lineart / canny synthesized from the polyline).

## Status — DEFERRED 2026-05-02

OpenPoseXL2 / DWPose ControlNet have no garment-keypoint channel — they only consume body 18 + face 70 + hands 21 keypoints. Garment landmarks therefore cannot improve OpenPose-driven generation; they would only feed a separate ControlNet (lineart / canny) in a multi-ControlNet workflow.

Operator decision (2026-05-02): defer this WP. Useful only when a multi-ControlNet workflow is the active production path, not as part of OpenPose conditioning. Re-scope as "garment polyline -> secondary ControlNet input" if/when needed.

The original full WP body below is preserved as a record of the original idea. Do not promote to READY without re-scoping the spec section first.

## Linked Workpackets

- **Predecessor(s)**: WP-I0-001..004 (foundation); WP-I1-001 calibration overlay (shares the operator-marker UX).
- **Related**: WP-I1-009 identity-export profiles (garment lock should ride along with identity).

## Reality Boundary

- **Real Seam**: `garment.py` module persists garment landmark sets per avatar; `rotation.rotate_yaw` rotates them alongside face/body landmarks; `openpose_serialize` emits an additional `garment_keypoints_2d` block (out of OpenPose schema; documented as an OpenRepose extension) or a parallel `garment.json` next to the OpenPose JSON.
- **User-Visible Win**: operator marks "neckline points" and "strap points" on Aeri's master once. Subsequent batch exports include garment landmarks at every angle. Downstream workflow can use them to drive a secondary ControlNet (lineart or canny synthesized from the garment polyline).
- **Proof Target**: rotated 90deg garment landmarks visually match the actual neckline of a 90-degree photograph (operator-confirmed).

## In Scope

- Garment landmark schema (groups: neckline, strap-left, strap-right, hem, optional sleeves).
- New commands: `set_garment_points`, `dump_garment`, `clear_garment`.
- New snapshot target `garment` showing the marks overlaid on the master.
- Garment landmarks rotated with the rig in `rotate_yaw`.
- JSON output channel decision: extension to OpenPose JSON or sidecar file (decided in linked DOCUMENTATION WP).

## Out Of Scope

- Cloth simulation / soft-body deformation (rigid landmark transform only in v0.1).
- Fabric pattern / texture (landmarks only).

## Headless LLM Operation Compliance

- [ ] LLM agent triggers via 3 new commands.
- [ ] State reflected in `state.json` under `garment` block.
- [ ] LLM pulls visual via `snapshot {target: "garment"}`.
- [ ] No focus theft.
- [ ] Tests cover headless path.

## Definition Of Done

- [ ] Operator can mark garment landmarks via GUI tab and via headless commands.
- [ ] Landmarks rotate with the rig.
- [ ] Output channel populated; downstream sample workflow consumes it.

## Progress Log

- 2026-05-02: WP drafted, status DRAFT.
