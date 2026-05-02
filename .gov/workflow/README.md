# OpenRepose Workflow Rules

All material work in OpenRepose is organized as workpackets tracked on a taskboard. This file defines the rules. The template lives at `.gov/templates/WP_TEMPLATE.md`. The live taskboard lives at `.gov/workflow/TASKBOARD.md`.

## Why Workpackets

Workpackets give every change a contract before it happens, evidence after it happens, and a truthful record of what was real vs. simulated. They prevent the failure mode where a change ships, looks fine, and then nobody can reconstruct what was actually verified.

## Hard Rules

1. **No code change in `.product/` without an active workpacket.** A workpacket exists in `.gov/workflow/workpackets/` and has status `READY` or `IN-PROGRESS` on the taskboard.
2. **No workpacket reaches `DONE` without satisfying its Definition of Done, Reality Boundary, and Exit Criteria.** Every Exit Criterion has linked evidence.
3. **Taskboard updates in the same session as any status transition.** A workpacket transitioning to `IN-PROGRESS` or `DONE` without a matching taskboard row update is a workflow violation.
4. **Reality Boundary, Fallback Register, and Change Ledger remain truthful.** Do not retroactively rewrite them to match the result. Truthful tracking is the point of the system.
5. **Spec changes require a paired DOCUMENTATION-class or higher-class workpacket.** A spec edit without a workpacket is a workflow violation.

## Workpacket Lifecycle

```text
DRAFT      Workpacket file exists but is being written; not approved to start.
READY      Approved to start; on the taskboard. Implementation can begin.
IN-PROGRESS Active work. Edits to .product/ allowed.
BLOCKED    Cannot proceed. Reason and unblocker named in workpacket.
REVIEW     Implementation done. Operator reviewing evidence.
DONE       Operator-approved. Workpacket file moved from workpackets/ to archive/.
CANCELLED  Will not be done. Reason recorded.
```

Allowed transitions:

```text
DRAFT       -> READY       (after spec/contract is approved)
READY       -> IN-PROGRESS (work starts)
IN-PROGRESS -> BLOCKED     (dependency hit)
BLOCKED     -> IN-PROGRESS (unblocker resolved)
IN-PROGRESS -> REVIEW      (work claimed done, awaiting verification)
REVIEW      -> IN-PROGRESS (review found issues)
REVIEW      -> DONE        (operator sign-off)
any state   -> CANCELLED   (with reason)
```

## Numbering And Naming

Workpacket IDs use the format:

```text
WP-<ITERATION>-<NNN>
```

Iteration is `I0`, `I1`, etc. Number is zero-padded three-digit, monotonic within the iteration.

File naming inside `.gov/workflow/workpackets/`:

```text
WP-I0-001-<short-slug>.md
```

Once `DONE`, the file moves to `.gov/workflow/archive/` keeping its filename.

## Packet Classes

Pick the most specific class:

```text
RESEARCH        Investigate options, read sources, produce a written recommendation. No product code change.
SCAFFOLD        Create folder structure, empty modules, build config. Compiles but does no real work.
IMPLEMENTATION  Real product code change. Most common class.
VERIFICATION    Add tests, checks, evidence collection. May or may not change product code.
DOCUMENTATION   Spec, README, codex, terminology, governance text changes only.
INFRASTRUCTURE  Build/CI/dev-environment changes (pyproject.toml, Cargo.toml, GitHub Actions, etc.).
```

The required sections of a workpacket vary by class. The template marks per-class optional sections. Smaller classes (RESEARCH, DOCUMENTATION, SCAFFOLD) need fewer sections; IMPLEMENTATION and VERIFICATION need the full set.

## Effort Estimates

Use t-shirt sizes:

```text
XS    < 1 hour
S     1-3 hours
M     3-8 hours (one focused day)
L     1-3 focused days
XL    > 3 focused days (consider splitting)
```

If a workpacket would be `XL`, consider splitting into smaller workpackets with explicit predecessor/successor links.

## Linked Workpackets

Workpackets explicitly track their relationships:

```text
Predecessor   This workpacket cannot start until predecessor is DONE.
Successor     A future workpacket that depends on this one.
Blocks        Other workpackets that cannot start until this is DONE (inverse of Predecessor for them).
Blocked-By    Other workpackets currently blocking this one.
Related       Useful context but no strict dependency.
```

## Reality Boundary

Every workpacket has a Reality Boundary section that captures, before the work starts:

- **Real Seam**: which part of reality this workpacket actually changes.
- **User-Visible Win**: what the operator will see different after this workpacket.
- **Proof Target**: which command output, file, or artifact proves the change is real.
- **Allowed Temporary Fallbacks**: stubs, mocks, or sample data acceptable during this workpacket.
- **Promotion Guard**: explicit condition under which fallbacks must be removed.

Reality Boundary is sacred. Do not rewrite it after the fact. If the boundary turns out to be wrong, open a follow-up workpacket and document the correction in the original's Change Ledger.

## Definition Of Done

The Definition of Done is a concrete checkbox list specific to this workpacket. It is checked off, not narrated. Examples of good Definition of Done items:

- [ ] `.product/src/openrepose/rig.py` compiles and `from openrepose.rig import Rig` works.
- [ ] `pytest .product/tests/test_rig.py` returns zero failures.
- [ ] `.\orstart -Brief` includes the new spec section in its output.
- [ ] `.gov/spec/openrepose_v0_1.md` references the new YawConvention enum.

Bad Definition of Done items (avoid these):

- [ ] "Code is good." (not testable)
- [ ] "Documentation updated." (which doc, what change?)
- [ ] "Works as expected." (no proof target)

## Evidence

Every `DONE` workpacket has linked evidence. Acceptable evidence:

- Command output (stdout/stderr saved to file under `target/test-artifacts/<wp-id>/`).
- Screenshots saved under `target/screenshots/<wp-id>/`.
- Test suite results (pytest junit XML, coverage report).
- Build artifact paths under `target/` or `dist/`.
- Operator sign-off message in the workpacket's Evidence section.

## Push Hygiene

Before any push to `origin`:

```powershell
.\scripts\clean-target.ps1
git status --short
```

`target/`, `dist/`, and `outputs/` must contain no tracked files. The `.gitignore` enforces this for new files; the cleanup script removes existing build artifacts. A push that includes any file inside these folders is a workflow violation.

## Taskboard

The live taskboard at `.gov/workflow/TASKBOARD.md` shows:

- Active workpackets (`READY`, `IN-PROGRESS`, `BLOCKED`).
- Pending review (`REVIEW`).
- Recently done (last 10 closed).
- Aggregate counts per state.

The taskboard is a Markdown table, hand-edited. If the taskboard scale grows beyond what is practical to maintain by hand, propose a generator script in a workpacket of class `INFRASTRUCTURE`.

## Templates

```text
.gov/templates/WP_TEMPLATE.md         Workpacket template (improved over StratAtlas v4.0).
```

Future templates (test suite, spec extraction, check script) can be added under `.gov/templates/` as the workflow needs them. Add them via a `DOCUMENTATION`-class workpacket so the rule is documented before the template is used.

## Workflow Version

The current workflow framework version is `1.0`. Workpackets pin the version in their header to allow future framework upgrades without breaking historical workpackets.
