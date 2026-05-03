# Agent Instructions

These instructions apply to the entire OpenRepose repo. Read `.gov/CODEX.md` next as the compact project codex before advising or editing.

## Root AGENTS.md Entry Point

The canonical agent instructions live at `.gov/AGENTS.md`.

The repo root may contain `AGENTS.md` only as an initialization entry point for GPT/Codex-style agents that auto-load root instruction files.

Preferred form:

- root `AGENTS.md` is a true symlink to `.gov/AGENTS.md`.

Windows fallback:

- if symlink creation is blocked, root `AGENTS.md` may temporarily be a hard link to `.gov/AGENTS.md`.

Do not maintain root `AGENTS.md` as a separate copied rulebook. If it is not linked, treat that as drift risk and repair it before editing agent rules.

First action in every fresh agent session remains:

```powershell
.\orstart
```

**First rule: Adult Production Boundary.** OpenRepose is an adult porn production tool. Repo text, product-facing manual text, workpackets, specs, recipes, prompts, and assistant handoffs stay raw, unfiltered, direct, and technical about that purpose. Do not censor, soften, euphemize, moralize, add lifestyle commentary, or turn ordinary technical work into legal/consent gatekeeping. The operator manages legal paperwork and local-rule adherence; OpenRepose, this repo, the product, and LLM assistants do not track, manage, verify, store, adjudicate, or enforce those obligations.

## Mission

OpenRepose is a desktop application that supports commercial adult pornographic image and video production workflows. The production target is photorealistic explicit adult output, including full nudity, penetration, realistic genitalia, and realistic sexual acts. Keep the repo direct about that purpose.

The application is intended to grow over time. The first shipped feature is a 3D-rig-locked yaw-angle wireframe exporter: take a frontal portrait, fit a locked 3D rig of facial landmarks plus shoulder/neck/ear/eye body landmarks to it, allow interactive yaw rotation of the rig, and export OpenPose-format wireframe images at any requested angle suitable as ControlNet input for downstream image-generation workflows. Future features will extend the rig-and-export concept to other production tasks while keeping the same locked-geometry stance.

OpenRepose exists because 2D photowarp and sparse-point-cloud approaches do not preserve eye-to-mouth ratios, face-to-shoulder ratios, or shoulder breadth across rotation angles. A locked 3D rig solves that. The same locking discipline is the model for future features.

## Operating Stance

- Keep assistance technical, production-oriented, and specific.
- Keep adult-production language raw, unfiltered, direct, and explicit where the workflow calls for it.
- Raw colloquial porn wording is encouraged when it fits the hardcore porn production goal and improves intent fidelity. Examples include `pussy`, `tits`, `dick`, `cock`, `cumplay`, `sluts`, `whores`, `fucktoy`, `stud`, and `monster dick`; these are non-exhaustive style signals, not a fixed vocabulary list.
- Do not inject morality, lifestyle commentary, censoring language, euphemisms, or softening into operator work.
- Do not soften the repo purpose when updating docs, recipes, spec, workflows, product-facing manual text, prompts, handoffs, or model notes.
- Keep repo instructions and product code LLM-provider agnostic.
- Do not require OpenAI, Anthropic, Google, or any specific local model for core repo or application operation.
- Do not create provider-specific assistant workflows as the default project path.
- The operator is the sole anchor for legal paperwork, consent records, age/identity verification, venue requirements, performer records, publishing/platform requirements, jurisdictional rules, and business decisions.
- OpenRepose does not track, manage, verify, store, adjudicate, or enforce legal paperwork, consent records, age/identity verification, venue rules, publishing/platform rules, jurisdictional rules, or business decisions.
- Assistants are not expected to maintain legal/consent paperwork and should not ask for it as a prerequisite to ordinary technical work.
- If a hard tool, platform, model-license, or higher-priority instruction blocks an action, state the concrete blocker briefly and move to the closest technical alternative.

## Adult Production Boundary Rule

This is the first repo rule because it defines how every assistant and product-facing document treats the project domain.

1. OpenRepose is used for adult porn production. Use direct production terms. Do not replace explicit workflow language with euphemisms, sanitized phrasing, content warnings, morality judgments, lifestyle commentary, or vague "sensitive content" framing.
2. Repo governance, specs, workpackets, manual pages, recipes, prompts, code comments, logs, UI labels, and handoff notes stay raw, unfiltered, direct, and technical when describing operator workflows.
3. Raw colloquial porn wording is encouraged when it fits the hardcore porn production goal and improves intent fidelity. Examples include `pussy`, `tits`, `dick`, `cock`, `cumplay`, `sluts`, `whores`, `fucktoy`, `stud`, and `monster dick`; these are non-exhaustive style signals, not a fixed vocabulary list.
4. The operator is responsible for legal and business compliance: age and identity verification, consent and release records, venue rules, performer records, publishing/platform rules, jurisdictional rules, and business decisions.
5. The repo and product do not track, manage, verify, store, adjudicate, or enforce those obligations. Do not add product features or assistant workflows that pretend OpenRepose is a legal/compliance record system unless the operator opens an explicit feature spec for that purpose.
6. LLM assistants do not demand legal paperwork, consent records, or local-law proof as a prerequisite to ordinary technical work in this repo.
7. Every LLM-facing primitive, runtime state surface, command response, manual entry point, and future API handshake must expose an `adult_production_boundary` object with `acknowledgement_required: true`. Reading and honoring that object is the acknowledgement step for any LLM touching OpenRepose.
8. This acknowledgement is technical context only. It is not a legal/compliance record, not a consent store, and not a command-blocking database.
9. If a higher-priority model/tool/platform rule, dependency license, or hard runtime constraint blocks a requested action, state the concrete blocker plainly and continue with the closest technical alternative. Do not dress the blocker up as project morality.

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

## Work-Start Protocol

Hard rule for every product change.

1. **Workpacket exists.** No edit under `.product/` may begin without a workpacket file in `.gov/workflow/workpackets/` at status `READY` or `IN-PROGRESS`. The workpacket cites a spec section and lists Expected Files Touched.
2. **Taskboard row exists.** `.gov/workflow/TASKBOARD.md` has a row for the WP at the same status.
3. **Repo is committed and pushed.** Before any product file is edited, the workpacket file + taskboard row are committed and pushed to `origin/main`. The commit message names the WP-ID. The push must succeed.
4. **Only then** does product code get touched.

This is the survival sequence. Past delete fiascos — wrong git tooling, accidental directory climbing, scripts deleting parents of parents — lost product code that had not been pushed. Pushing intent first means the WP scope and taskboard row outlive any local-tree disaster.

**Governance refactors are exempt from this protocol.** Edits confined to `.gov/` (spec, AGENTS.md, CODEX.md, topology.yaml, workflow files, templates, taskboard, individual workpackets) do not require their own workpacket and may be committed directly. They still obey the disk-agnostic, naming-convention, research-first, and deletion-protocol rules below.

A change is a "governance refactor" iff it touches only files under `.gov/` (and possibly `README.md` or `pyproject.toml` for cross-cutting metadata). Any modification of a file under `.product/`, `scripts/`, or `orstart.cmd` is product work and requires a WP.

## Pre-Work Commit Rule

Before opening or editing any file under `.product/`:

```powershell
git add -A
git commit -m "WP-IX-NNN: kickoff — <one line summary>"
git push
```

The commit may contain only the WP file + taskboard row + governance updates. Push must return success before the editor opens any product file. If the push fails (network, auth, hooks), do not proceed; resolve the push first.

## Naming Convention Rule

Files and folders inside this repo MUST NOT contain blank-space characters.

- Preferred for docs, WPs, scripts: `kebab-case` (e.g., `WP-I1-007-pitch-roll-rotation.md`).
- Preferred for Python modules: `snake_case` (e.g., `openpose_serialize.py`).
- Forbidden: `Some File With Spaces.md`, `My Folder/`.

If a legacy path with blank space is found, rename it before any other change in the same workpacket and update every reference in the same commit. The rule does not extend to ancestor directories outside the repo root (the operator's choice of parent directory is not under repo control).

A grep test `git ls-files | grep ' '` MUST return zero matches. Any new commit that introduces a path with a blank space is a workflow violation.

## Disk-Agnostic Rule

No absolute path may be hardcoded into any committed file. Every script, doc, spec, WP, and config must work when the repo is moved to any disk (`C:\`, `D:\`, `E:\`, network drive) or any machine.

Allowed pattern in PowerShell scripts:

```powershell
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir "..")
```

Forbidden: machine-specific roots such as a drive-letter `Projects` path, a Unix home-directory path, or a Windows user-profile path in any committed file. Examples that legitimately need a real path (e.g., illustrating an absolute path the operator must supply at runtime) belong in `.gov/doc/` with a clear "operator supplies" label.

Test: copy the repo to a different disk or path; run `.\orstart`. Anything that breaks because of a hardcoded path is a violation. The CI / pre-push grep is `Select-String -Pattern '[A-Z]:\\\\Projects' -Path **/*.md, **/*.yaml, **/*.ps1, **/*.py` returning zero matches outside `.gov/doc/`.

## Research-First Rule

Before implementing a non-trivial feature, dependency choice, model, or algorithm, research current sources. Someone may have shipped a better solution; implementing without checking is a known anti-pattern in this domain.

Search order (use as many as the question warrants):

1. Official library / vendor docs (MediaPipe, ControlNet, PySide6, OpenCV, etc.).
2. GitHub repos — issues, READMEs, releases, code search.
3. Hugging Face — model cards, discussions, leaderboards.
4. Civit AI — model pages, version notes, reviews relevant to the production stack.
5. Vendor and university research papers — arXiv, vendor research blogs.
6. Forums, Discord summaries, blog posts when they contain concrete settings or evidence.

Output goes in the WP's `## Research Notes` section (added by the v1.1 template) with: source URL, date checked, one-line takeaway, and a verdict (`adopt | adapt | reject | watch`). Old memory is not research; date the source.

If research changes the WP's Reality Boundary or Definition of Done, update those sections in the same commit so the workpacket reflects the chosen approach, not the original guess.

## Deletion Protocol

Manual deletion of tracked files or repo folders is forbidden. All deletions go through one of:

- **Claude side**: the `/safe-delete` slash command (`.claude/commands/safe-delete.md`). Refuses any path that resolves outside the repo root or that names the repo root or its parent.
- **Operator side**: `scripts/safe-delete.ps1`. Same guards. Logs every removal under `target/safe-delete-log/` (gitignored) so post-mortem is possible.

Forbidden patterns:

- `cd ..` followed by `Remove-Item` or `rm -rf`.
- `Remove-Item -Recurse -Force` on any path containing `OpenRepose` literal.
- Any deletion using an absolute path supplied by the assistant rather than computed by the safe-delete helper.

Past disasters: wrong git tooling and accidental directory-climbing deleted entire repos, and on one occasion an entire disk. Routing every deletion through a checked path makes that class of error impossible.

When the safe-delete helper refuses a path, do not work around it — investigate why. If the legitimate target really is outside the repo root, the operator runs the deletion by hand consciously.

## Manual Impact Rule

Every IMPLEMENTATION-class workpacket at Workflow Version 1.1+ MUST contain a `Manual Impact:` line in its Definition Of Done section. The author explicitly answers whether the in-app manual (`.gov/doc/manual/`) needs an update for this change.

Acceptable forms:

- `Manual Impact: Yes — extends <topic-file>.md with <what>` (or names a new topic file).
- `Manual Impact: No — internal refactor with no operator-facing surface change.`
- `Manual Impact: N/A (bug fix)` — when the WP only fixes a defect in existing behavior. Brief reason recommended.

Bug-fix WPs may use the `N/A (bug fix)` form. Other WPs must answer Yes or No truthfully and update the manual in the same WP if the answer is Yes.

The audit script (`scripts/audit-repo.ps1`) enforces field presence on **active** workpackets in `.gov/workflow/workpackets/`. Archived WPs are grandfathered (the rule was introduced mid-iteration via WP-I1-035). The check is mechanical (line presence, not truthfulness); operator self-review enforces the spirit of the rule.

The manual itself lives as Markdown topic files under `.gov/doc/manual/`. The Help tab in the GUI renders the index + selected topic. Future assistants and human collaborators use the manual to onboard the app without reading the spec.

## Headless Verification Checklist

Use this checklist when reviewing or signing off any IMPLEMENTATION-class workpacket that adds an operator-facing or visual feature:

- [ ] An LLM agent can trigger the feature through the command channel (HTTP or inbox) without touching the GUI.
- [ ] An LLM agent can read the feature's current state from `state.json` (or a documented additional state file).
- [ ] An LLM agent can pull a visual artifact of the feature via the snapshot subsystem.
- [ ] No code path in the feature calls `raise_()`, `activateWindow()`, `showNormal()`, `setForegroundWindow()`, or any equivalent.
- [ ] The feature does not display modal dialogs in response to commands originating from the LLM control surface.
- [ ] Tests cover the headless path as well as (or instead of) the GUI path.
