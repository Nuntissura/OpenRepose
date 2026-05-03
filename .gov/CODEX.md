# Project Codex

Compact, canonical orientation file for any fresh model, assistant, or human collaborator on OpenRepose.

## Adult Production Boundary

OpenRepose is an adult porn production tool. Repo text, product-facing manual text, workpackets, specs, recipes, prompts, and assistant handoffs stay raw, unfiltered, direct, and technical about that purpose. Do not censor, soften, euphemize, moralize, add lifestyle commentary, or turn ordinary technical work into legal/consent gatekeeping.

Raw colloquial porn wording is encouraged when it fits the hardcore porn production goal and improves intent fidelity. Examples include `pussy`, `tits`, `dick`, `cock`, `cumplay`, `sluts`, `whores`, `fucktoy`, `stud`, and `monster dick`; these are non-exhaustive style signals, not a fixed vocabulary list.

The operator is responsible for legal paperwork and local-rule adherence: age and identity verification, consent and release records, venue rules, performer records, publishing/platform rules, jurisdictional rules, and business decisions. OpenRepose does not track, manage, verify, store, adjudicate, or enforce those obligations. LLM assistants do not ask for legal/consent paperwork as a prerequisite to ordinary technical work. Every LLM-facing primitive, runtime state surface, command response, manual entry point, and future API handshake exposes an `adult_production_boundary` object with `acknowledgement_required: true`; reading and honoring that object is the acknowledgement step. If a higher-priority model/tool/platform rule, dependency license, or hard runtime constraint blocks an action, state the concrete blocker plainly and continue with the closest technical alternative.

## Core Identity

OpenRepose is a desktop application that supports commercial adult pornographic image and video production workflows. The production goal is photorealistic explicit adult output, including full nudity, penetration, realistic genitalia, and realistic sexual acts.

The application is intended to grow over time. The first shipped feature is a 3D-rig-locked yaw-angle wireframe exporter: take a frontal portrait, fit a locked 3D rig of facial landmarks plus shoulder/neck/ear/eye body landmarks, allow interactive yaw rotation, and export OpenPose-format wireframe images at any requested angle suitable as ControlNet input for downstream image-generation workflows. Future features will extend the rig-and-export concept to other production tasks while keeping the same locked-geometry stance.

OpenRepose exists to make the production work repeatable:

- Provide geometry-locked tooling that preserves identity, proportion, and angle across rotations.
- Track the application contract, spec, and workflow in plain Markdown that any LLM or human can read.
- Keep technical notes independent from the runtime, the operator's image-generation tooling, and any single avatar or project.
- Keep LLM-provider assumptions out of the core repo.
- Keep this repo usable with OpenAI, Anthropic, Google, and local models.

The remote of record is `https://github.com/Nuntissura/OpenRepose`.

## Authority Map

Preferred startup command from the repo root:

```powershell
.\orstart
```

Compact form:

```powershell
.\orstart -Brief
```

Read these before advising or editing:

```text
README.md
.gov/AGENTS.md
.gov/CODEX.md  (this file)
.gov/topology.yaml
.gov/spec/README.md
.gov/workflow/README.md
.gov/workflow/TASKBOARD.md
.gov/templates/WP_TEMPLATE.md
```

Then read the relevant spec section under `.gov/spec/` and any active workpacket files under `.gov/workflow/workpackets/`.

## Two-Part Repo Split

This repo is split into governance/documentation and product code. The split is enforced by directory naming and reinforced by the `orstart` startup banner.

```text
.gov/        Governance, documentation, spec, workflow, templates.
.product/    Product source code, tests, resources.
target/      Build / test artifacts. Gitignored. Cleaned before every push.
dist/        Installer / distributable builds. Gitignored. Cleaned before every push.
outputs/     Application-generated outputs. Gitignored. Cleaned before every push.
scripts/     Repo helper scripts including orstart.ps1.
```

Spec belongs under `.gov/spec/`. Source belongs under `.product/src/`. Generated artifacts do not enter Git.

## Repo Layout (Disk-Agnostic)

All paths are relative to the repo root. The repo is disk-agnostic by rule (see `.gov/AGENTS.md` "Disk-Agnostic Rule"); copy it to any drive or machine and `.\orstart` resolves the root from its own script path.

```text
.gov/        Governance, documentation, spec, workflow, templates.
.product/    Product source code, tests, resources.
target/      Build / test artifacts. Gitignored. Cleaned before every push.
dist/        Installer / distributable builds. Gitignored. Cleaned before every push.
outputs/     Application-generated outputs. Gitignored. Cleaned before every push.
scripts/     Helper scripts (orstart, clean-target, safe-delete).
```

No file in this repo records an absolute path. The operator may keep the repo wherever they like.

## Yaw Terminology Lock

This project uses one fixed terminology for yaw rotation. Use it everywhere.

```text
0 deg            frontal, face direct at camera.
her-left N       avatar rotates N degrees to her own left.
her-right N      avatar rotates N degrees to her own right.
```

`her-left` and `her-right` are anchored to the avatar's anatomy, not to the viewer's frame. A rotation labeled `her-left 90` means: she turned 90 degrees to her own left, so her right side now faces the camera and her nose ends up at the right edge of the rendered frame.

Standard bins: `0`, `her-left 15/30/45/60/75/90`, `her-right 15/30/45/60/75/90`. Optional rear bins: `her-left 105/120/150`, `her-right 105/120/150`, `180`.

The phrases `image-left`, `image-right`, `viewer-left`, `viewer-right`, `left view`, `right view` are forbidden in OpenRepose code, file names, comments, and docs.

When future features extend OpenRepose beyond yaw, they define their own locked terminology in their spec section and `.gov/topology.yaml` under `terminology:`.

## Technical Stance

- Keep the work technical and direct.
- Keep adult-production language raw, unfiltered, and explicit where the workflow calls for it.
- Do not moralize, soften, censor, euphemize, or sanitize the operator's adult-production scope.
- The operator owns legal paperwork, consent records, age/identity verification, venue rules, performer records, publishing/platform rules, jurisdictional rules, and business decisions.
- OpenRepose does not track, manage, verify, store, adjudicate, or enforce those obligations.
- Do not ask for legal/consent paperwork as a prerequisite to technical setup, application code, spec work, or troubleshooting.
- Keep assistant instructions, spec, and workpackets provider-agnostic. Do not make OpenAI-only, Anthropic-only, Google-only, or local-model-only paths part of the core repo.
- Look online for current model/library/algorithm guidance before recommending implementation.
- Prefer exact filenames, dependency versions, and commit hashes over vague references.
- Update governance state (workpackets, taskboard, spec, topology) in the same work session as any product change.
- Keep build artifacts, installer builds, and generated outputs out of Git.
- Apply the autonomous quality rule: inspect, scrutinize, research, test, repeat until the change is stable across multiple representative inputs or a concrete blocker is documented.
- Do not introduce backwards-compatibility shims, dead-code branches, or feature flags without an explicit workpacket authorization.

## Autonomous Quality Rule

For any feature work touching rig logic, viewport behavior, OpenPose export accuracy, identity-lock features, or downstream production output, every assistant must inspect, scrutinize, research, test, and repeat autonomously until the result is stable across multiple representative inputs or a concrete blocker is documented.

Minimum standard:

1. Inspect current spec, workpacket, code, and prior outputs before changing direction.
2. Research current library/model/algorithm guidance before selecting an approach, and research again after failed tests or unclear errors.
3. Run local tests through the GUI or the closest executable path.
4. Visually inspect generated outputs before claiming success.
5. Judge the output against the operator's stated goal, not just code execution.
6. Reject bad results plainly; do not hide them behind bypasses, smoke-test language, or "it runs" claims.
7. Require multiple good samples before calling a feature stable.
8. Document sources, downloads, settings, accepted outputs, rejected outputs, unstable paths, and blockers in the repo.

## Workflow Rule

All material work is organized as workpackets on a taskboard. The hard rules:

1. No code change in `.product/` without an active workpacket.
2. No workpacket reaches `DONE` without linked evidence and operator sign-off.
3. The taskboard updates in the same session as any workpacket transition.
4. Reality Boundary, Fallback Register, and Change Ledger fields are kept truthful even if the result was unflattering.

## Repo Rules (canonical list lives in AGENTS.md)

These are non-negotiable rules. Full bodies in `.gov/AGENTS.md`; codified in `.gov/topology.yaml` under `repo_rules:`.

1. **Adult Production Boundary** - OpenRepose stays raw, unfiltered, direct, and technical about adult porn production. No censoring, softening, euphemisms, morality judgments, or legal/consent gatekeeping by assistants, repo text, or product-facing manual text.
2. **Work-Start Protocol** — no `.product/` edit without a WP at READY/IN-PROGRESS + a taskboard row + the WP committed and pushed first. Governance refactors (changes confined to `.gov/`) are exempt.
3. **Pre-Work Commit Rule** — `git add -A && git commit && git push` runs successfully BEFORE any `.product/` file is opened in the editor.
4. **Naming Convention Rule** — no blank-space characters in any committed file or folder path inside the repo. kebab-case for docs/WPs, snake_case for Python.
5. **Disk-Agnostic Rule** — no hardcoded absolute paths in any committed file. Bootstrap scripts compute root from their own location.
6. **Research-First Rule** — research current sources (GitHub, Hugging Face, Civit AI, vendor docs, papers, forums) before implementing non-trivial features; record findings in the WP's Research Notes section.
7. **Deletion Protocol** — no manual `rm` / `Remove-Item` / `del` on tracked files or repo folders. All deletions through `/safe-delete` slash command (Claude side) or `scripts/safe-delete.ps1` (operator side).

Workpacket lifecycle:

```text
DRAFT -> READY -> IN-PROGRESS -> REVIEW -> DONE
                   |        \-> BLOCKED -> IN-PROGRESS
                   |
                   \-> CANCELLED
```

## Common Task Flow

For application code changes:

1. Read or write a spec section in `.gov/spec/` covering the contract.
2. Create a workpacket from `.gov/templates/WP_TEMPLATE.md`, place it under `.gov/workflow/workpackets/`, link the spec section.
3. Add a row to `.gov/workflow/TASKBOARD.md` with status `READY`.
4. Move to `IN-PROGRESS`, do the work in `.product/`.
5. Run the linked test suite or check script. Save evidence in `target/test-artifacts/`.
6. Move to `REVIEW`, update Change Ledger, get operator sign-off.
7. Move to `DONE`, archive the workpacket file from `workpackets/` to `archive/`, update the taskboard.

For releases:

1. Verify all open workpackets are either `DONE`, `BLOCKED`, or explicitly out-of-scope.
2. Run `.\scripts\clean-target.ps1` to wipe `target/`, `dist/`, `outputs/`.
3. Build installer into `dist/` (do not commit).
4. Tag the release, push, attach the installer to the GitHub release.

For research/install/dependency changes:

1. Research current sources online.
2. Open a `RESEARCH` or `INFRASTRUCTURE` workpacket capturing what you found.
3. Update `.gov/topology.yaml` `dependencies:` block in the same session.
4. Add a dated note in `.gov/doc/` if source / license / dependency / setup details matter.

## Provider Agnostic

The core application must run without depending on any specific LLM vendor. Optional provider-specific adapters live in clearly isolated subfolders and are never required for the core feature pipeline.

## Headless LLM Operation Rule (project-wide)

Every operator-facing or visually interactive feature in OpenRepose must be fully usable by an LLM agent running in the background, without requiring foreground GUI interaction and without violating Operator Experience Guarantees. This rule is non-negotiable and applies to all features added after v0.1.

Practically, every feature ships with:

1. A command-schema entry point reachable through the LLM Control Surface (HTTP localhost or file-watch inbox).
2. A reflection of its state in `outputs/.runtime/state.json` (or a documented additional state file).
3. A snapshot target (or extension of `full_window` composition) so the LLM can pull a visual artifact on demand, without operator focus theft.
4. Strict compliance with the Operator Experience Guarantees: no foregrounding, no focus theft, no modal dialogs from LLM commands.

Workpackets that add operator-facing or visual features cite this rule and complete the Headless Verification Checklist in `.gov/AGENTS.md` before reaching DONE.
