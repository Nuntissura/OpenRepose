# OpenRepose Governance

This directory holds governance, documentation, spec, workflow, and templates for OpenRepose. Product source code lives in `.product/`. This split is enforced by directory naming and reinforced by the `orstart` startup banner.

## Layout

```text
.gov/
  README.md                      this file
  AGENTS.md                      governing instructions for fresh assistants and automation
  CODEX.md                       compact project codex (purpose, authority map, common task flow)
  topology.yaml                  machine-readable map of project paths, terminology, and dependencies
  spec/                          versioned spec sections in plain Markdown
    README.md                    spec index
    openrepose_v0_1.md           initial application spec
  workflow/                      workpackets and taskboard
    README.md                    workflow rules
    TASKBOARD.md                 live workpacket taskboard
    workpackets/                 active workpacket files (DRAFT, READY, IN-PROGRESS, BLOCKED, REVIEW)
    archive/                     completed (DONE) and cancelled workpacket files
  templates/                     templates used across the project
    WP_TEMPLATE.md               workpacket template
  doc/                           supporting documentation, research notes, design memos
```

## Governance Rules Quick Reference

- Read `AGENTS.md` and `CODEX.md` before any edit.
- All material work flows through workpackets per `workflow/README.md`.
- Yaw terminology is locked: use `0`, `her-left N`, `her-right N`. Forbidden phrases listed in `AGENTS.md`.
- Reality Boundary, Fallback Register, and Change Ledger in workpackets remain truthful.
- Spec changes require a paired DOCUMENTATION-class or higher workpacket.
