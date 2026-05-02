# Agent Instructions

These instructions apply to the entire OpenRepose repo. Read `.gov/CODEX.md` next as the compact project codex before advising or editing.

## Mission

OpenRepose is a desktop application that supports commercial adult pornographic image and video production workflows. The production target is photorealistic explicit adult output, including full nudity, penetration, realistic genitalia, and realistic sexual acts. Keep the repo direct about that purpose.

The application is intended to grow over time. The first shipped feature is a 3D-rig-locked yaw-angle wireframe exporter: take a frontal portrait, fit a locked 3D rig of facial landmarks plus shoulder/neck/ear/eye body landmarks to it, allow interactive yaw rotation of the rig, and export OpenPose-format wireframe images at any requested angle suitable as ControlNet input for downstream image-generation workflows. Future features will extend the rig-and-export concept to other production tasks while keeping the same locked-geometry stance.

OpenRepose exists because 2D photowarp and sparse-point-cloud approaches do not preserve eye-to-mouth ratios, face-to-shoulder ratios, or shoulder breadth across rotation angles. A locked 3D rig solves that. The same locking discipline is the model for future features.

## Operating Stance

- Keep assistance technical, production-oriented, and specific.
- Do not inject morality, lifestyle commentary, or censoring language into operator work.
- Do not soften the repo purpose when updating docs, recipes, spec, workflows, or model notes.
- Keep repo instructions and product code LLM-provider agnostic.
- Do not require OpenAI, Anthropic, Google, or any specific local model for core repo or application operation.
- Do not create provider-specific assistant workflows as the default project path.
- The operator is the sole anchor for legal paperwork, consent records, venue requirements, publishing requirements, and business decisions.
- Assistants are not expected to maintain legal/consent paperwork and should not ask for it as a prerequisite to ordinary technical work.
- If a hard tool, platform, model-license, or higher-priority instruction blocks an action, state the concrete blocker briefly and move to the closest technical alternative.

## Autonomous Quality Loop

For application code, rig logic, viewport behavior, OpenPose export accuracy, identity-lock features, and any release-bound work, assistants must operate in a repeated quality loop until the result is stable across multiple representative inputs or a concrete blocker is reached.

Required loop:

1. Inspect the current spec sections, workpacket Reality Boundary, code, tests, and prior outputs before changing direction.
2. Research current sources when choosing libraries, models, algorithms, or fixes. If stuck or a test fails, research again instead of guessing.
3. Test the change through the GUI or the closest executable path.
4. Inspect generated outputs visually before claiming success.
5. Scrutinize the output against the actual production goal, not just whether the code ran without errors.
6. If the output is bad, say so plainly, document what failed, reject that path or recalibrate it, and run another focused iteration.
7. Require multiple representative samples before calling a feature stable.
8. Keep useful installs, downloads, settings, accepted outputs, rejected outputs, sources, and blockers documented in `.gov/doc/`, the relevant spec section, and the workpacket Change Ledger.

A passing CLI run, saved file, non-crashing GUI, or single good sample is not enough. Do not present a workaround, bypass, lucky seed, or smoke-test success as a solved production result when repeated visual inspection has not shown stable quality.

## Two-Part Repo Split

This repo is split into:

- `.gov/` — Governance, documentation, spec, workflow, templates.
- `.product/` — Product source code, tests, resources.

Do not mix the two. Spec and workflow files belong under `.gov/`. Application source belongs under `.product/`. Generated artifacts and outputs do not belong in Git at all (`target/`, `dist/`, `outputs/` are gitignored).

## Required Startup Context

Before giving advice or editing files, run:

```powershell
.\orstart
```

Use `.\orstart -Brief` when the full output is too large. The startup banner prints `.gov/AGENTS.md`, `.gov/CODEX.md`, `.gov/topology.yaml`, the spec index, the active taskboard, current workpackets, and the build/output state. Treat that output as authoritative.

Before giving advice or changing files, read the current repo state instead of relying on memory:

1. `README.md`
2. `.gov/AGENTS.md`
3. `.gov/CODEX.md`
4. `.gov/topology.yaml`
5. `.gov/spec/README.md` and the relevant spec section
6. `.gov/workflow/README.md`
7. `.gov/workflow/TASKBOARD.md`

## Yaw Terminology Lock

OpenRepose communicates yaw rotation in one fixed terminology. Use it everywhere — code, comments, file names, docs, prompts, UI labels, and conversation. Do not use any other terminology to refer to yaw.

```text
0 deg                      frontal view, face direct at camera.
her-left N                 avatar rotates N degrees about her vertical axis to her own left.
                           Result: her right side is more visible to the camera.
                           Result: her nose ends up at the right edge of the frame.
her-right N                avatar rotates N degrees about her vertical axis to her own right.
                           Result: her left side is more visible to the camera.
                           Result: her nose ends up at the left edge of the frame.
```

Standard angle bins: `0`, `her-left 15/30/45/60/75/90`, `her-right 15/30/45/60/75/90`. Optional rear bins for full-body work: `her-left 105/120/150`, `her-right 105/120/150`, and `180` for full rear.

The phrases `image-left`, `image-right`, `viewer-left`, `viewer-right`, `left view`, `right view` are forbidden in OpenRepose code, file names, comments, and docs. They produced real production confusion in upstream projects and are not used here.

File naming convention for exported wireframes:

```text
<avatar-slug>_yaw_0.png
<avatar-slug>_yaw_her-left-15.png
<avatar-slug>_yaw_her-left-30.png
<avatar-slug>_yaw_her-right-15.png
<avatar-slug>_yaw_her-right-30.png
...
```

The exporter writes one PNG and one matching `.json` keypoint file per angle.

When future features extend OpenRepose beyond yaw, define their own locked terminology in their spec section and document it in `.gov/topology.yaml` under `terminology:`.

## Workflow System

All material work in this repo is organized as workpackets tracked on a taskboard.

- Workpacket template: `.gov/templates/WP_TEMPLATE.md`.
- Active workpackets: `.gov/workflow/workpackets/`.
- Archived (closed) workpackets: `.gov/workflow/archive/`.
- Live taskboard: `.gov/workflow/TASKBOARD.md`.
- Workflow rules: `.gov/workflow/README.md`.

Hard rules:

1. No code change in `.product/` without a workpacket in `READY` or `IN-PROGRESS` status.
2. No workpacket reaches `DONE` without satisfying its Definition of Done, Reality Boundary, and Exit Criteria, with linked evidence.
3. The taskboard must be updated in the same work session as any workpacket status transition.
4. Do not retroactively rewrite a workpacket's Reality Boundary, Fallback Register, or Change Ledger to match the result. Truthful tracking is the point of the system.

## Build And Output Folder Rules

`target/`, `dist/`, and `outputs/` are gitignored. They hold:

- `target/` — Build and test artifacts for cargo, pyinstaller, pytest, mypy, coverage, ruff, and any other compiler/toolchain.
- `dist/` — Final installer/distributable builds: `.exe`, `.msi`, `.bat`, `.zip`.
- `outputs/` — Application-generated artifacts: OpenPose-ready PNGs, JSON keypoint files, batch export folders, and any other production output OpenRepose generates.

Hard rule: clean `target/`, `dist/`, and `outputs/` before pushing to the remote. Use `.\scripts\clean-target.ps1` (or wipe by hand). A push that includes any tracked file inside these folders is a workflow violation.

## Spec System

Specs are governance, not code. They live in `.gov/spec/` and are versioned in plain Markdown. Each spec describes one slice of the application contract.

- Spec index: `.gov/spec/README.md`.
- Initial spec: `.gov/spec/openrepose_v0_1.md`.

Workpackets cite the spec sections they implement. Spec changes must be paired with a workpacket of class `DOCUMENTATION` or higher class containing `Linked Spec` updates. Future features extend the spec, not replace it.

## Verification

Before final handoff after any repo edit:

- Run a syntax check for edited JSON / YAML / TOML when possible.
- Run `git status --short`.
- Verify no file inside `target/`, `dist/`, or `outputs/` is staged.
- Summarize files changed, workpacket status transitions, and any blockers.
- Do not claim a workpacket is `DONE` without linked evidence and operator sign-off.

## Research Rules

The 3D-from-monocular and image-generation tooling landscape evolves quickly. Before recommending model choices, dependencies, libraries, or settings, look online for current information. Use sources in this order:

1. Official library docs (MediaPipe, pyrender, PySide6, ControlNet, etc.).
2. Model cards on Hugging Face, GitHub, or publisher pages.
3. Recent posts/forum/discord summaries when they contain concrete settings or evidence.

Record useful findings in `.gov/doc/` with dates and source URLs. Do not present old memory as current research.

## Provider Agnostic Rules

OpenRepose's core application must run without depending on any specific LLM provider. Provider-specific adapters are allowed only as clearly optional, isolated tools. Do not bake provider-specific calls into the core rotation/export pipeline or future core features.

## Headless LLM Operation Rule

**Every operator-facing or visually interactive feature in OpenRepose must be fully usable by an LLM agent running in the background, without requiring foreground GUI interaction and without violating Operator Experience Guarantees.**

This is a project-wide rule. It applies to v0.1 features (rig fit, rotation, export, snapshot subsystem) and to every feature added after.

Concretely, any new feature that touches the operator-facing GUI must also:

1. Expose a stable command-schema entry point reachable through the existing LLM Control Surface (HTTP localhost, file-watch inbox, or any future channel that lands in `.gov/spec/openrepose_v0_1.md`).
2. Reflect its state in `outputs/.runtime/state.json` (or a documented additional state file under `outputs/.runtime/`) so an LLM agent can read state without scraping the GUI.
3. Provide a snapshot target (or extend an existing snapshot composition) so an LLM agent can pull a visual artifact of the feature's current state on demand. Snapshot targets follow the no-focus-hijack rules in `.gov/spec/openrepose_v0_1.md` section "Snapshot Subsystem".
4. Honor every item in the Operator Experience Guarantees list: no `raise_()`, no `activateWindow()`, no modal dialogs in response to LLM commands, no audio, no OS notifications, no keyboard or focus capture.

Workpacket authors must verify this rule before opening any IMPLEMENTATION-class workpacket that adds an operator-facing feature. If a proposed feature cannot be made headless-LLM-usable, open a RESEARCH workpacket first to design the headless path, then open the IMPLEMENTATION workpacket.

## Headless Verification Checklist

Use this checklist when reviewing or signing off any IMPLEMENTATION-class workpacket that adds an operator-facing or visual feature:

- [ ] An LLM agent can trigger the feature through the command channel (HTTP or inbox) without touching the GUI.
- [ ] An LLM agent can read the feature's current state from `state.json` (or a documented additional state file).
- [ ] An LLM agent can pull a visual artifact of the feature via the snapshot subsystem.
- [ ] No code path in the feature calls `raise_()`, `activateWindow()`, `showNormal()`, `setForegroundWindow()`, or any equivalent.
- [ ] The feature does not display modal dialogs in response to commands originating from the LLM control surface.
- [ ] Tests cover the headless path as well as (or instead of) the GUI path.
