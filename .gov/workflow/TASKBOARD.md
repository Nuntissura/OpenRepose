# OpenRepose Taskboard

Last Updated: 2026-05-03 (fast-track batch in progress: WP-I1-027/017/029/023 sequential)

Live status of all OpenRepose workpackets. Update in the same session as any workpacket transition. Rules in `.gov/workflow/README.md`. Template at `.gov/templates/WP_TEMPLATE.md`.

## Summary

- WPs in flight (READY + IN-PROGRESS): 0
- WPs pending review (REVIEW): 0
- WPs blocked (BLOCKED): 0
- WPs draft (DRAFT, eligible to promote): 22 (19 original + WP-I1-027/028/029 follow-ups drafted 2026-05-03)
- WPs deferred (DEFERRED): 1 (WP-I1-012 garment locks)
- WPs done (I0): 4 (WP-I0-001/002/003/004) — I0 CLOSED 2026-05-02
- WPs done (I1): 3 (WP-I1-025, WP-I1-026, WP-I1-001)
- WPs reserved-not-drafted: 3 (WP-I1-019/020/021 joint-manipulation chain — operator deferred to later)
- Iterations open: I1 (in progress)

## Active

Workpackets currently progressing toward DONE.

| WP-ID | Title | Owner | Status | Class | Effort | Updated |
|-------|-------|-------|--------|-------|--------|---------|
| WP-I1-027 | Export Folder Picker And Persistence | assistant | READY | IMPLEMENTATION | M | 2026-05-03 |

## Pending Review

Implementation claims to be done; awaiting operator verification.

| WP-ID | Title | Owner | Class | Updated | Verify |
|-------|-------|-------|-------|---------|--------|

_(none)_

## Blocked

Cannot proceed until the named blocker resolves.

| WP-ID | Title | Owner | Blocked By | Reason | Updated |
|-------|-------|-------|------------|--------|---------|

_(none)_

## Draft (Will Promote To Ready When Predecessors Close)

Drafted now so dependencies, scope, and contracts are settled. Status moves to READY when the named predecessor reaches DONE.

I0 closed 2026-05-02. The I0-blocking constraint on every I1 WP below is satisfied; individual WPs may now be promoted from DRAFT → READY in priority order. WPs that list a separate predecessor (e.g., `WP-I0-004` alone, `WP-I1-001 + DOCUMENTATION WP`, etc.) still need that named predecessor satisfied before promotion. Headless LLM Operation Compliance is mandatory for every IMPLEMENTATION-class WP touching operator-facing or visual features (see `.gov/AGENTS.md`).

| WP-ID | Title | Class | Effort | Priority | Headless | Predecessor |
|-------|-------|-------|--------|----------|----------|-------------|
| WP-I1-001 | Per-avatar calibration overlay | IMPLEMENTATION | L | High (fixes WP-I0-003 diagnostic) | yes | I0 (DONE) + WP-I1-026 (DONE) — PROMOTED to READY |
| WP-I1-002 | Orbital camera in 3D viewport | IMPLEMENTATION | S | Polish | n/a | WP-I0-004 |
| WP-I1-003 | Settings persistence | IMPLEMENTATION | S | Polish | yes | WP-I0-004 |
| WP-I1-004 | Extended keyboard shortcuts | IMPLEMENTATION | XS | Polish | n/a | WP-I0-004 |
| WP-I1-005 | Drag-and-drop portrait import | IMPLEMENTATION | XS | Polish | n/a | WP-I0-004 |
| WP-I1-006 | GUI theme refinements | IMPLEMENTATION | S | Polish | n/a | WP-I0-004 |
| WP-I1-007 | Pitch / roll rotation extension | IMPLEMENTATION | M | Feature expansion | yes | I0 + DOCUMENTATION WP |
| WP-I1-008 | Alternative landmark detector research | RESEARCH | M | Investigation | n/a | I0 |
| WP-I1-009 | Identity-export profiles | IMPLEMENTATION | M | Feature expansion | yes | I0; ideally WP-I1-001 |
| WP-I1-010 | Multi-angle automation | IMPLEMENTATION | M | Feature expansion | yes | I0 |
| WP-I1-011 | Multi-subject scenes | IMPLEMENTATION | L | Feature expansion (likely I2) | yes | I0; ideally WP-I1-007 |
| WP-I1-012 | Garment locks | IMPLEMENTATION | M | DEFERRED (OpenPose has no garment channel) | n/a | n/a |
| WP-I1-013 | Installer build + release | INFRASTRUCTURE | M | Distribution | n/a | I0; ideally WP-I1-003 |
| WP-I1-014 | MediaPipe Tasks API migration | INFRASTRUCTURE | M | Future-proofing | n/a | I0 |
| WP-I1-015 | Floating reference portrait window | IMPLEMENTATION | S | Polish | yes | WP-I0-004; WP-I1-003 |
| WP-I1-016 | Clear workspace command + button | IMPLEMENTATION | XS | Polish | yes | WP-I0-004 |
| WP-I1-017 | Per-body-part visibility toggles | IMPLEMENTATION | S | Feature expansion | yes | WP-I0-004 |
| WP-I1-018 | Hand detection + OpenPose hand output | IMPLEMENTATION | M | Feature expansion (gates DWPose hand conditioning) | yes | I0; relates to WP-I1-014 |
| WP-I1-022 | Read OpenPose JSON as alternate input | IMPLEMENTATION | M | Workflow expansion | yes | I0; composes with WP-I1-023 |
| WP-I1-023 | Frame reframing (robust rerender) | IMPLEMENTATION | M | High (fixes portrait-bias / cropped-feet) | yes | I0; composes with WP-I1-022 |
| WP-I1-024 | Synchronized viewport zoom | IMPLEMENTATION | S | Polish | n/a (GUI sync only; headless covered by WP-I1-023) | WP-I0-004; WP-I1-015; WP-I1-023 |
| WP-I1-027 | Export folder picker + persistence | IMPLEMENTATION | M | High (current bug: pasted paths silently ignored) | yes (dump_settings) | I0 (DONE) |
| WP-I1-028 | Calibration zoom + frontal mesh inspector | IMPLEMENTATION | M | High (WP-I1-001 UX polish — operator confused jaw markers without it) | n/a (operator-side polish) | WP-I1-001 (DONE) |
| WP-I1-029 | Per-marker visibility toggles | IMPLEMENTATION | M | Mid (companion to WP-I1-017 group-level toggles; per-marker overrides) | yes | I0 (DONE); composes with WP-I1-017 |

## Recently Done

Last 10 workpackets to reach DONE. Files moved from `workpackets/` to `archive/`.

| WP-ID | Title | Owner | Class | Closed |
|-------|-------|-------|-------|--------|
| WP-I0-001 | Rig And Rotation Core | assistant | IMPLEMENTATION | 2026-05-02 |
| WP-I0-002 | LLM Control Surface | assistant | IMPLEMENTATION | 2026-05-02 |
| WP-I0-003 | Snapshot Subsystem | assistant | IMPLEMENTATION | 2026-05-02 |
| WP-I0-004 | Double Viewport GUI | assistant | IMPLEMENTATION | 2026-05-02 |
| WP-I1-025 | Quarterly Governance Audit | assistant | INFRASTRUCTURE | 2026-05-02 |
| WP-I1-026 | Feature 2 Calibration Overlay Spec | assistant | DOCUMENTATION | 2026-05-02 |
| WP-I1-001 | Per-Avatar Calibration Overlay | assistant | IMPLEMENTATION | 2026-05-03 |

## Cancelled

Workpackets that will not be done. Reason recorded in the workpacket file (which still moves to `archive/`).

| WP-ID | Title | Owner | Class | Reason | Cancelled |
|-------|-------|-------|-------|--------|-----------|

_(none)_

## Iteration Notes

### I0 — Initial Scaffold (CLOSED 2026-05-02)

- Repo created 2026-05-02.
- Governance, product split, target/dist/outputs folders, orstart command, codex, agents, topology, workflow framework, and improved WP template all scaffolded.
- Spec v0.1 drafted with: yaw terminology lock, output formats, mechanical log format, LLM control surface, snapshot subsystem, operator experience guarantees, Feature 1 (3D-rig yaw exporter) GUI + CLI requirements.
- Four workpackets shipped: WP-I0-001 (rig+rotation core), WP-I0-002 (LLM control surface), WP-I0-003 (snapshot subsystem), WP-I0-004 (double viewport GUI). All four DONE on 2026-05-02.
- I0 close criterion met: operator can launch the GUI, import a frontal portrait, watch both viewports update through 13 yaw angles, export a 13-angle batch; a separate LLM agent drives the same workflow through the inbox channel without operator focus theft. 111/111 tests green at close.

### I1 — In Progress

- WP-I1-025 (Quarterly Governance Audit) shipped DONE on 2026-05-02 ahead of the rest of I1 because the audit script is infrastructure scaffolding for the workflow rules introduced this iteration.
- Workflow Version bumped to 1.1: new IMPLEMENTATION/RESEARCH WPs created from the template must carry a `## Research Notes` section. Existing 1.0 WPs grandfathered.
- WP-I1-026 (Feature 2 Calibration Overlay Spec, DOCUMENTATION) shipped DONE 2026-05-02 — locks the deformation algorithm (TPS via scipy), marker schema, calibration JSON schema, command surface, state-file shape, and snapshot target for WP-I1-001 to implement against.
- WP-I1-001 (Per-Avatar Calibration Overlay, IMPLEMENTATION, L) shipped DONE 2026-05-03. 178/178 tests passing; junit XML at `target/test-artifacts/WP-I1-001/`. GUI verification surfaced two Calibration-tab usability gaps (no zoom; no frontal mesh sanity preview) — operator approved sign-off on the basis that the spec contract + headless surface + tests are met; deferred items recorded in WP-I1-001 Fallback Register and queued as WP-I1-028.
- 2026-05-03: three follow-up WPs drafted at status DRAFT: **WP-I1-027 Export folder picker + persistence** (highest priority — fixes the bug where the OptionsPane `settings_changed` signal is unwired so pasted paths silently ignored); **WP-I1-028 Calibration zoom + frontal mesh inspector** (UX polish for WP-I1-001 — surfaced during sign-off when operator confused jaw markers without an independent mesh reference); **WP-I1-029 Per-marker visibility toggles** (sibling of WP-I1-017's per-body-part — per-marker overrides, both layers compose with documented precedence).
- 22 I1 WPs at DRAFT awaiting promotion.

## Iteration Pipeline

I1 has 20 drafted workpackets, 1 deferred (WP-I1-012 garment locks), 3 reserved-not-drafted (WP-I1-019/020/021 joint manipulation — operator postponed). Once I0 closes, the operator promotes individual WPs from DRAFT → READY in priority order.

Recommended sequencing once I0 closes:

1. **WP-I1-001 calibration overlay** — directly fixes the WP-I0-003 wireframe-fidelity gap. High priority.
2. **WP-I1-016 clear workspace + WP-I1-017 per-body-part visibility** — small daily-UX wins; unblock common operator complaints.
3. **WP-I1-022 read OpenPose JSON input** — unlocks workflows that don't start from a portrait.
4. **WP-I1-023 frame reframing** — robust rerender approach; fixes portrait-bias / cropped-feet. High priority.
5. **WP-I1-003 settings persistence** — needed before WP-I1-015 reference window can persist its position.
6. **WP-I1-015 floating reference portrait window + WP-I1-024 synchronized viewport zoom** in parallel — operator's continuous-context-during-work feature.
7. **WP-I1-014 MediaPipe Tasks API migration** before any new feature WP that adds MediaPipe usage. Schedule before WP-I1-018.
8. **WP-I1-018 hand detection + OpenPose hand output** — enables DWPose hand conditioning.
9. **WP-I1-002 orbital camera, WP-I1-004 keyboard shortcuts, WP-I1-005 drag-and-drop, WP-I1-006 theme refinements** — polish, can run anytime in parallel.
10. **WP-I1-007 pitch/roll rotation** before **WP-I1-009 identity profiles** and **WP-I1-011 multi-subject scenes**.
11. **WP-I1-008 alternative landmark detector research** can run anytime; pure RESEARCH.
12. **WP-I1-010 multi-angle automation** — straightforward extension of `export_batch`.
13. **WP-I1-013 installer build + release** — when v0.1 feature set is stable.

Future iteration themes not yet drafted as workpackets:

- I2: WP-I1-019/020/021 joint manipulation chain (RESEARCH then IMPLEMENTATION). Deferred per operator.
- I2: code signing for distributables.
- I2: macOS / Linux builds.
- I2: GitHub Actions CI for automated test + build.
- I2: per-feature-group calibration mixing (extension of WP-I1-001).
- I2: animated yaw-sweep video export.
- I2: read OpenPose PNG image (reverse-engineer keypoints from rendered colors). Pure RESEARCH first.
- I2: re-scope WP-I1-012 garment locks as "garment polyline -> secondary ControlNet input" if multi-ControlNet workflow becomes a production path.

Each becomes its own workpacket when authorized.
