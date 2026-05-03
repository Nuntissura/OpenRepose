# OpenRepose Manual — v0.1

The in-app reference for OpenRepose. Open this from the **Help** tab. OpenRepose is an adult porn production tool; the manual stays raw, unfiltered, direct, and technical.

## Topics

- [Adult production boundary](adult-production-boundary.md) - no censoring, no softening, no morality judgments, and no legal/consent gatekeeping by the repo, product, or LLM assistants.

- [Getting started](getting-started.md) — first launch, importing a portrait, exporting wireframes.
- [Feature 1: Yaw exporter](feature-1-yaw-exporter.md) — what gets exported, the OpenPose schema, file naming.
- [Feature 2: Calibration overlay](feature-2-calibration-overlay.md) — marking reference points so MediaPipe's average-face fit doesn't dominate stylized avatars.
- [Feature 3: Library + ComfyUI coupling](feature-3-library-postgresql.md) — PostgreSQL-backed library, ComfyUI bridge, multi-operator concurrency.
- [AMood prompting in the Library](amood-workflow.md) - attach project, task, workflow, prompt requirements, OpenPose guides, generated images, and review decisions to Library entries.
- [Keyboard shortcuts](keyboard-shortcuts.md) — Ctrl+O, Ctrl+E, Ctrl+Shift+E, etc.

## Operator stance

OpenRepose's operator stance starts with [Adult production boundary](adult-production-boundary.md). The repo-level rule is also in `.gov/AGENTS.md`, `.gov/CODEX.md`, and `.gov/topology.yaml`. Spec is in `.gov/spec/`.

## Yaw terminology lock

`0` (frontal), `her-left N`, `her-right N`. `N` is degrees. Anchored to the avatar's anatomy, not the camera frame.

Forbidden phrases everywhere: `image-left`, `image-right`, `viewer-left`, `viewer-right`, `left view`, `right view`. The grep test enforces this.
