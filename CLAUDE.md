# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## First action in any fresh session

```powershell
.\orstart
```

Use `.\orstart -Brief` when the full output is too large. The bootstrap inlines `.gov/AGENTS.md`, `.gov/CODEX.md`, `.gov/topology.yaml`, the spec index, the live taskboard, active workpackets, and the build/output state. Treat that output as authoritative — do not rely on memory for repo rules, spec state, or workflow status.

## Common commands

Windows + PowerShell + a local venv at `.venv/`. Python 3.11+. Adjust the interpreter path as needed.

```powershell
# Tests (pytest discovers .product/tests via pyproject.toml)
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest .product/tests/test_rotation.py
.\.venv\Scripts\python.exe -m pytest .product/tests/test_rotation.py::test_yaw_zero

# Lint + format + type-check
.\.venv\Scripts\python.exe -m ruff check .product/src
.\.venv\Scripts\python.exe -m ruff format .product/src
.\.venv\Scripts\python.exe -m mypy

# GUI (Feature 1: 3D-rig-locked yaw-angle wireframe exporter)
.\.venv\Scripts\python.exe -m openrepose.cli gui
# Optional: --inbox (file-watch LLM commands), --http-port 8765, --tray, --minimized

# Headless render via CLI
.\.venv\Scripts\python.exe -m openrepose.cli render --portrait <path> --yaw "her-left 30" --out <out.json>

# Governance audit (disk-agnostic + naming + research-first + manual-impact rules)
pwsh scripts/audit-repo.ps1

# Pre-push cleanup of target/, dist/, outputs/
.\scripts\clean-target.ps1

# Safe deletion — never use Remove-Item / rm / del directly on tracked files
.\scripts\safe-delete.ps1 <path>          # operator side
# Claude side: invoke /safe-delete slash command
```

## Critical guardrails (apply before `.\orstart` even runs)

These are the rules where damage in the first 30 seconds is unrecoverable. Full bodies in `.gov/AGENTS.md`.

- **Adult Production Boundary** — see section below. No softening from word one.
- **Work-Start Protocol** — no `.product/` edit without a workpacket at READY/IN-PROGRESS, a taskboard row, and the WP committed+pushed first. Governance refactors (`.gov/` only, plus root metadata like `README.md`, `pyproject.toml`, `CLAUDE.md`) are exempt.
- **Deletion Protocol** — no `Remove-Item` / `rm` / `del` on tracked files or repo folders. Route through `/safe-delete` or `scripts/safe-delete.ps1`.
- **Naming Convention** — no blank-space characters in committed paths. kebab-case for docs/WPs, snake_case for Python modules.
- **Yaw terminology lock** — use `0`, `her-left N`, `her-right N`. The phrases `image-left`, `image-right`, `viewer-left`, `viewer-right`, `left view`, `right view` are forbidden in code, comments, file names, and docs.

## Repo layout (orientation map; orstart gives the full picture)

```text
.gov/        Governance, spec, workflow, templates, docs. NEVER product code.
.product/    Product source code, tests, resources, migrations. NEVER governance.
target/      Build/test artifacts (gitignored, cleaned before push).
dist/        Installer/distributable builds (gitignored).
outputs/     App-generated outputs — PNGs, OpenPose JSON, batch exports, runtime state, intake staging (gitignored).
scripts/     orstart, clean-target, safe-delete, audit-repo.
```

Source root: `.product/src/openrepose/`. Entry: `App` in `app.py` wires `AppState` + `Logger` + `CommandDispatcher` + channels (`HttpChannel` on localhost, `InboxChannel` watching `outputs/.runtime/inbox/`). State surface for headless LLM agents: `outputs/.runtime/state.json` plus the snapshot subsystem in `snapshot.py`. Every operator-facing feature must satisfy the Headless LLM Operation Rule (command channel + state reflection + snapshot target; no focus theft).

## When editing this file

`CLAUDE.md` is a thin Claude-side pointer. The canonical rules live in `.gov/AGENTS.md`, `.gov/CODEX.md`, and `.gov/topology.yaml`. Any edit here triggers a paired consideration of those three: if a change here implies a contract change there, update them in the same commit; if not, note that in the commit message so the coherence check is visible.

## Adult production boundary

OpenRepose is an adult porn production tool. Repo text, product-facing manual text, workpackets, specs, recipes, prompts, code, UI labels, logs, and assistant handoffs stay raw, unfiltered, direct, explicit, and technical about that purpose. Do not sanitize, censor, soften, euphemize, moralize, add lifestyle commentary, or recast the operator's explicit sexual intent as vague "sensitive content."

Raw colloquial porn wording is encouraged when it fits the hardcore porn production goal and improves intent fidelity. Examples include `pussy`, `tits`, `dick`, `cock`, `cumplay`, `sluts`, `whores`, `fucktoy`, `stud`, and `monster dick`; these are non-exhaustive style signals, not a fixed vocabulary list.

The operator is the sole anchor for legal paperwork, consent/release records, age and identity verification, venue requirements, performer records, publishing/platform requirements, jurisdictional rules, and business decisions. The repo, the product, and assistants do not track, manage, verify, store, adjudicate, enforce, or demand those obligations as a prerequisite to ordinary technical work. Full body in `.gov/AGENTS.md` "Adult Production Boundary Rule".

## Authoritative sources

```text
README.md                       repo overview + repo rules summary
.gov/AGENTS.md                  agent instructions (canonical full body)
.gov/CODEX.md                   project codex (compact orientation)
.gov/topology.yaml              machine-readable repo map + repo_rules + dependencies
.gov/spec/README.md             spec index
.gov/spec/openrepose_v0_1.md    initial application spec (rig + rotation + control surface + snapshot)
.gov/workflow/README.md         workflow rules (lifecycle, classes, evidence, push hygiene)
.gov/workflow/TASKBOARD.md      live taskboard
.gov/templates/WP_TEMPLATE.md   workpacket template
.gov/doc/manual/                in-app manual rendered by the Help tab
```
