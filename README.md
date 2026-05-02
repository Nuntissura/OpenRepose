# OpenRepose

A lightweight desktop application that supports commercial adult pornographic image and video production workflows. The first shipped feature is a 3D-rig-locked yaw-angle wireframe exporter that converts a frontal portrait into OpenPose-format wireframe images at any rotation, suitable as ControlNet input for downstream image-generation workflows. The application is designed to grow into other production tasks (additional rig manipulations, identity-locked exports, batch automation) over time.

The production target is photorealistic explicit adult output, including full nudity, penetration, realistic genitalia, and realistic sexual acts. The repo is direct about that purpose and does not soften it in docs, recipes, or governance text.

The remote of record is `https://github.com/Nuntissura/OpenRepose`.

## Two-Part Repo Split

This repo is split into governance/documentation and product code. The split is enforced by directory naming and reinforced by the `orstart` startup banner so a fresh assistant or human collaborator always knows which side of the line they are on.

```text
.gov/        Governance, documentation, spec, workflow, templates.
.product/    Product source code, tests, resources.
```

Supporting infrastructure folders live alongside the split:

```text
target/      Build and test artifacts for cargo, pyinstaller, pytest, and other compilers/toolchains. Gitignored. Cleaned before every push.
dist/        Final installer/distributable builds (.exe, .msi, .bat, .zip). Gitignored.
outputs/     Application-generated outputs (OpenPose-ready images, JSON keypoints, batch exports). Gitignored.
scripts/     Repo helper scripts including the `orstart` startup script.
```

## Goals

- Provide repeatable, geometry-locked tooling for adult production workflows that need consistent identity, proportion, and angle control.
- First feature: 3D-rig-driven yaw-angle wireframe exporter. Future features: additional rig manipulations, identity exports, automation utilities — all in service of the production stance.
- Stay LLM provider agnostic in the core application: OpenAI, Anthropic, Google, local models, or any other assistant can read and update the same repo conventions and governance.
- Keep generated images, model weights, and other large local files out of Git.

## Operating Stance

- Keep the work technical, production-oriented, and specific.
- Do not inject morality, lifestyle commentary, or censoring language into operator work.
- Do not soften the repo purpose when updating docs, recipes, spec, or governance.
- The operator is the sole anchor for legal paperwork, consent records, venue rules, publishing rules, and business decisions.
- Assistants are not expected to maintain legal/consent paperwork and should not ask for it as a prerequisite to ordinary technical work.
- If a hard tool, model-license, or higher-priority instruction blocks an action, state the concrete blocker briefly and move to the closest technical alternative.

## Startup Command

From the repo root, run:

```powershell
.\orstart
```

This prints repo rules, the active codex, agent instructions, machine-readable topology, the workflow taskboard, current spec status, and the build/output state. Every fresh assistant or human collaborator should run this before changing any file.

Use `.\orstart -Brief` for a shorter boot context when the full output is too large.

## First-Time Local Setup

```powershell
git init
git remote add origin https://github.com/Nuntissura/OpenRepose.git
git add .
git commit -m "Initial scaffold"
git push -u origin main
```

Before any push, run `.\scripts\clean-target.ps1` to wipe `target/`, `dist/`, and `outputs/` (or verify they are empty / gitignored). Build artifacts and generated outputs do not enter Git.

## Project Notes

- Agent instructions: `.gov/AGENTS.md`
- Project codex: `.gov/CODEX.md`
- Machine-readable topology: `.gov/topology.yaml`
- Spec index: `.gov/spec/README.md`
- Workflow rules: `.gov/workflow/README.md`
- Active taskboard: `.gov/workflow/TASKBOARD.md`
- Workpacket template: `.gov/templates/WP_TEMPLATE.md`
