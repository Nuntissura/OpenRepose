# OpenRepose Product

This directory holds the OpenRepose product source code, tests, and bundled resources. Governance, spec, and workflow live in `.gov/`.

## Layout

```text
.product/
  README.md                      this file
  src/                           source code
    openrepose/                  main Python package
      __init__.py
  tests/                         test suite
  resources/                     bundled resources (icons, default settings, sample portraits for tests)
```

## Build And Run

Build configuration lives at the repo root (`pyproject.toml`, `Cargo.toml`, etc.) so multiple toolchains can coexist. Build outputs go to `target/` (gitignored). Installer outputs go to `dist/` (gitignored). Generated application output goes to `outputs/` (gitignored).

For Python development:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
pytest .product/tests
```

The `pyproject.toml` lands in a future workpacket (class `INFRASTRUCTURE`).

## Coding Rules

- Use the locked yaw terminology (`0`, `her-left N`, `her-right N`). No `image-left` / `viewer-right` / `left view` anywhere in code, comments, file names, or UI strings.
- No code change without an active workpacket — see `.gov/workflow/README.md`.
- The core application path must run without depending on any specific LLM vendor. Provider-specific adapters live in clearly isolated subfolders.
- Visual outputs go to `outputs/`. Do not commit them.
