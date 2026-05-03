# OpenRepose Manual — v0.1

The in-app reference for OpenRepose. Open this from the **Help** tab.

## Topics

- [Getting started](getting-started.md) — first launch, importing a portrait, exporting wireframes.
- [Feature 1: Yaw exporter](feature-1-yaw-exporter.md) — what gets exported, the OpenPose schema, file naming.
- [Feature 2: Calibration overlay](feature-2-calibration-overlay.md) — marking reference points so MediaPipe's average-face fit doesn't dominate stylized avatars.
- [Feature 3: Library + ComfyUI coupling](feature-3-library-postgresql.md) — PostgreSQL-backed library, ComfyUI bridge, multi-operator concurrency.
- [Keyboard shortcuts](keyboard-shortcuts.md) — Ctrl+O, Ctrl+E, Ctrl+Shift+E, etc.

## Operator stance

OpenRepose's operator stance is in `.gov/AGENTS.md` and `.gov/CODEX.md`. Spec is in `.gov/spec/`.

## Yaw terminology lock

`0` (frontal), `her-left N`, `her-right N`. `N` is degrees. Anchored to the avatar's anatomy, not the camera frame.

Forbidden phrases everywhere: `image-left`, `image-right`, `viewer-left`, `viewer-right`, `left view`, `right view`. The grep test enforces this.
