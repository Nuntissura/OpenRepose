# OpenRepose Rule Registry Spec — v0.1

Version: v0.1 (DRAFT)
Authored by: WP-I3-001 (DOCUMENTATION)
Spec scope: stable rule_ids, severity tiers, error-citation contract, global-vs-project-scoped registry split, audit coverage, initial registry seeded with the 6 existing repo rules + AMood + intake + targets families.

This spec is the source of truth for *how* OpenRepose teaches itself to operators and LLMs. Adult Production Boundary applies (`.gov/topology.yaml` `repo_rules.adult_production_boundary`).

## Purpose

OpenRepose has many rules: the 6 existing repo rules (work-start protocol, pre-work commit, naming convention, disk-agnostic, research-first, deletion protocol), the new Adult Production Boundary first rule (operator-authored under WP-I3-002), AMood blueprint rules (anti-repetition threshold, abandonment criteria, fast-triage fail-fast), intake rules (two-stage acceptance, default-staging bridge), requirement rules (project-scoped like `EXP120-RES-001`).

Without a registry, these rules drift across `AGENTS.md` prose, `topology.yaml` YAML, error messages, GUI tooltips, and the manual. Each surface eventually says something slightly different. The registry collapses them to one source of truth: a rule has a stable ID, a severity, a short, a manual link, and (optionally) a machine-checkable expression. Everywhere else cites by ID.

The registry is what makes the system self-teaching for cold-start LLMs and operators (per the design conversation that produced WP-I3-001).

## Rule Anatomy

```text
rule_id           stable ID. Format: <FAMILY>-<NNN>
                  Examples: RUL-001 (existing repo rule), AMOOD-001, INTAKE-001, TARGET-001, EXP120-RES-001
                  Family prefix indicates origin scope:
                    RUL-     : repo-wide governance (the 6 existing rules + the new boundary rule)
                    AMOOD-   : AMood blueprint operationalization
                    INTAKE-  : intake & triage
                    TARGET-  : target tracking + satisfaction
                    REQ-     : requirements registry
                    SAFE-    : safety-critical rules (juvenile/coercive content blocks)
                    <PROJECT-SLUG>- : project-scoped rules (e.g. EXP120-RES-001)

name              short noun phrase ("two-stage acceptance", "anti-repetition threshold")
short             one-line plain-language summary; what shows in error messages and tooltips
severity          one of: auto-route | block | warn | info  (see Severity Tiers)
manual_link       relative path + anchor: ".gov/doc/manual/<topic>.md#<anchor>"
machine_check_fn  optional. SQL expression or Python predicate name. NULL when rule is judgment-based.
auto_route_to     optional. Subdirectory under intake/<task_id>/diagnostic/ when severity=auto-route.
accept_terms      optional text[]. For requirement-style rules with structured term lists.
reject_terms      optional text[].
scope_type        one of: global | project | task | batch | card
scope_id          NULL for global; matching FK value otherwise.
inherited_from    NULL when set at this scope; scope_id of the ancestor that defined it otherwise.
created_at, last_validated_at  freshness audit timestamps.
```

Global rules live in `.gov/topology.yaml` under `rules:` (versioned config). Project-scoped rules live in DB at project scope (operator content, project lifetime, archived when project closes). Same registry shape on both sides; commands and GUI read either transparently.

## Severity Tiers

Four tiers. Distinct semantics so each rule has unambiguous behavior.

| Severity | Meaning | Behavior on rule fire |
|----------|---------|------------------------|
| `auto-route` | Deterministic machine check failed. Output is not blocked, not warned about — it is routed to a non-counting evidence bucket. | File/output moved to `intake/<task_id>/diagnostic/<auto_route_to>/`; status set to `diagnostic`; does not count toward target counters; reversible. |
| `block` | Hard refusal. Action does not proceed. Used for safety-critical and architectural-integrity rules. | Command rejected with citation. State unchanged. Operator override may exist for non-safety blocks (e.g. dedupe override with reason); never for safety blocks. |
| `warn` | Citation logged; action proceeds; operator/LLM acknowledges via the citation. | Log line emitted with rule_id; continues. |
| `info` | Display-only. No gate, no warning. Documentation-grade. | State surface includes the rule when relevant; no log noise. |

Examples by tier:

```text
auto-route:  EXP120-RES-001 (1080x1440 exact)               -> route to diagnostic/intermediate_evidence/
block:       INTAKE-001 (two-stage acceptance LLM/operator) -> command refused with manual link
block:       SAFE-001 (juvenile/coercive content)           -> DB CHECK constraint refuses promotion; no override
warn:        AMOOD-001 (anti-repetition >= 6 axis overlap)  -> log + state warning; LLM/operator may override with reason
info:        INTAKE-004 (library_search excludes pending)   -> display-only documentation of search behavior
```

The `auto-route` tier exists because the design conversation determined that "wrong resolution" is not really blocked, not really warned, and not really info — it has its own routing-not-blocking semantic. Conflating it with any other tier loses operator clarity on whether they need to act.

## Global vs Project-Scoped Rules

```text
Global rules:
  storage:    .gov/topology.yaml under rules:
  lifetime:   versioned config; persists across all projects
  examples:   the 6 existing repo rules + Adult Production Boundary first rule + AMOOD-* + INTAKE-* + TARGET-* + SAFE-*
  authoring:  governance refactor (Workflow Version 1.1; DOCUMENTATION-class WP if substantive)

Project-scoped rules:
  storage:    library_rules table in PG (added in I3 implementation iteration)
  lifetime:   project-scope; archived alongside the project on close
  examples:   EXP120-RES-001 (1080x1440), EXP120-CLOTH-001 (clothing-mediated reveal), EXP120-BODY-001 (top-heavy proportions), ...
  authoring:  operator via requirements editor GUI or command surface; round-trips with operator markdown
```

Both registries share the same shape. Commands and GUI see one logical registry. The separation is a bootstrap concern (registry must exist before DB is up; project rules need DB) and an authoring concern (governance vs. operator content).

```sql
CREATE TABLE library_rules (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id         text NOT NULL,                         -- 'EXP120-RES-001'
  scope_type      text NOT NULL CHECK (scope_type IN ('project','task','batch','card')),
  scope_id        uuid NOT NULL,
  name            text NOT NULL,
  short           text NOT NULL,
  severity        text NOT NULL CHECK (severity IN ('auto-route','block','warn','info')),
  manual_link     text,
  machine_check_fn text,
  auto_route_to   text,
  accept_terms    text[],
  reject_terms    text[],
  kind            text,                                  -- per requirements spec: 'hard_output' | 'body' | 'pose' | ...
  inherited_from  uuid REFERENCES library_rules(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  last_validated_at timestamptz,
  UNIQUE (rule_id, scope_type, scope_id)
);
```

## Error Citation Contract

Every dispatcher rejection follows one shape:

```text
ERR cmd=<command>: <action_result> by <rule_id> (<rule_name>): <short>.
See manual: <manual_link>.
Fix: <suggested_command_or_action>.
```

Examples:

```text
ERR cmd=intake_finalize: blocked by INTAKE-001 (two-stage acceptance):
LLM may soft_accept; only operator may finalize.
See manual: intake-and-triage#two-stage-acceptance.
Fix: emit intake_soft_accept; operator runs intake_finalize.
```

```text
ERR cmd=library_create_card: warned by AMOOD-001 (anti-repetition threshold):
new card overlaps 7 dedupe axes with accepted card AMB-0042 (threshold=6).
See manual: amood-workflow#anti-repetition.
Fix: change at least 2 dedupe axes (pose_family, support_object, ...) before retry, or supply dedupe_override_reason.
```

```text
ERR cmd=intake_soft_accept: blocked by SAFE-001 (juvenile-coded content):
adult_gate_score < 5; promotion forbidden at DB level.
See manual: intake-and-triage#safety-boundary.
Fix: reject this output; do not retry. Document the trigger in card abandonment_reason.
```

```text
WARN cmd=library_create_card: routed by EXP120-RES-001 (1080x1440 exact):
output 1024x1536 routed to diagnostic/intermediate_evidence/.
See manual: requirements-and-targets#exp120.
Fix: operator may re-route via intake_reroute if the resolution detection was wrong.
```

The error-citation shape is uniform across every command. LLMs learn the pattern from one error and apply it everywhere.

## State Surface

`state.library.guidance.active_rules` is a list of rule_ids relevant to the current state (≤ 20 entries). Each entry is just an ID string; the full rule body is fetched on demand from the registry.

```json
{
  "library": {
    "guidance": {
      "active_rules": ["INTAKE-001", "INTAKE-002", "AMOOD-001", "EXP120-RES-001", "RUL-001"],
      "manual_index": ".gov/doc/manual/index.md",
      "topic_pointers": {
        "rules": ".gov/doc/manual/rules-and-guidance.md",
        "intake": ".gov/doc/manual/intake-and-triage.md",
        "amood":  ".gov/doc/manual/amood-workflow.md"
      },
      "recent_operator_corrections": []
    }
  }
}
```

The full registry is reachable via the `dump_rules` command:

```text
dump_rules         (optional family filter, optional severity filter)
                   -> [{rule_id, name, severity, short, manual_link, scope_type, ...}, ...]
```

## Audit Coverage

The existing audit script `scripts/audit-repo.ps1` (WP-I1-025) is extended in I3 to verify registry coverage. Audit checks:

```text
1. every rule_id in topology.yaml rules: has a matching manual anchor (manual_link resolves)
2. every dispatcher command has a help string
3. every error string in product code that matches the citation shape cites a real rule_id
4. every CHECK constraint that triggers a rejection in the DB schema cites a rule_id in its error name
5. project-scoped rules in library_rules have last_validated_at set within 30 days (warn only; not block)
6. duplicated rule_ids across global and project registries are flagged (warn only)
```

The audit extension lands in a separate INFRASTRUCTURE WP in I3.

## Initial Registry

The 6 existing repo rules are promoted into the registry as `RUL-001..006` so existing rules carry the same citation format as new ones.

```yaml
rules:
  RUL-000:
    name: "Adult Production Boundary"
    severity: block
    manual: adult-production-boundary
    short: "Repo + product + LLM assistants do not censor adult production language and do not enforce legal/consent paperwork."
    note: "Authored by WP-I3-002. Already in topology.yaml repo_rules.adult_production_boundary; promoted into registry shape."
  RUL-001:
    name: "Work-Start Protocol"
    severity: block
    manual: workflow#work-start-protocol
    short: "No .product/ edit without a WP at READY/IN-PROGRESS + taskboard row + kickoff push first."
  RUL-002:
    name: "Pre-Work Commit Rule"
    severity: block
    manual: workflow#pre-work-commit-rule
    short: "Commit + push WP file + taskboard row before opening any .product/ file in the editor."
  RUL-003:
    name: "Naming Convention"
    severity: block
    manual: governance#naming-convention
    short: "No blank-space characters in any committed file or folder path. kebab-case for docs/WPs, snake_case for Python."
  RUL-004:
    name: "Disk-Agnostic"
    severity: block
    manual: governance#disk-agnostic
    short: "No hardcoded absolute paths in any committed file."
  RUL-005:
    name: "Research-First"
    severity: warn
    manual: workflow#research-first
    short: "Research current sources before implementing non-trivial features; record findings in WP Research Notes."
  RUL-006:
    name: "Deletion Protocol"
    severity: block
    manual: governance#deletion-protocol
    short: "All deletions through /safe-delete or scripts/safe-delete.ps1; never manual rm/Remove-Item on tracked files."

  AMOOD-001:
    name: "anti-repetition threshold"
    severity: warn
    manual: amood-workflow#anti-repetition
    short: ">= 6 axis overlap with accepted card requires revision; project-overridable."
  AMOOD-002:
    name: "abandonment trigger"
    severity: warn
    manual: amood-workflow#abandonment-criteria
    short: "12 seeds with trigger_clarity < 4, or 8 seeds with repeated structural failure => card-level abandon."
  AMOOD-003:
    name: "fast-triage fail-fast"
    severity: warn
    manual: amood-workflow#fast-triage
    short: "Any of 4 fast-triage fields below bar => reject before full rubric runs."
  AMOOD-004:
    name: "AMood safety boundary"
    severity: block
    manual: amood-workflow#safety-boundary
    short: "Juvenile/coercive/hidden-camera output => card-level abandon, not just seed-level. DB CHECK enforced."

  INTAKE-001:
    name: "two-stage acceptance"
    severity: block
    manual: intake-and-triage#two-stage-acceptance
    short: "LLM may soft_accept; only operator may finalize."
  INTAKE-002:
    name: "default intake target"
    severity: block
    manual: intake-and-triage#default-intake
    short: "ComfyUI bridge writes to intake unless operator token allows direct library."
  INTAKE-003:
    name: "per-task isolation"
    severity: info
    manual: intake-and-triage#per-task-isolation
    short: "Wholesale reject = directory delete + DB row delete in one transaction."
  INTAKE-004:
    name: "library_search excludes pending"
    severity: info
    manual: intake-and-triage#library-search
    short: "library_search filters status='pending' by default; explicit include_pending=true to see."

  TARGET-001:
    name: "satisfaction = count + quota"
    severity: warn
    manual: targets-and-progress#fully-satisfied
    short: "task is fully_satisfied only when count_satisfied AND quota_satisfied (AMood diversity audit >= 0.75)."
  TARGET-002:
    name: "forecast warning"
    severity: warn
    manual: targets-and-progress#forecast
    short: "in_flight < gap => forecast_ok=false; cannot close target from current intake."
  TARGET-003:
    name: "stability vs completeness"
    severity: info
    manual: targets-and-progress#stable-vs-complete
    short: "card is 'stable' when promoted >= stability_target (AMood, default 4); 'complete' when promoted >= target_promoted (project, e.g. EXP120 sets 8)."

  REQ-001:
    name: "inheritance: lower scope wins"
    severity: info
    manual: requirements-and-targets#inheritance
    short: "On conflict, card-scope rule overrides batch-scope; batch overrides task; task overrides project."
  REQ-002:
    name: "auto-route reversibility"
    severity: info
    manual: requirements-and-targets#auto-route
    short: "Operator may re-route from diagnostic/intermediate_evidence/ back to pending if metadata mis-detected."
  REQ-003:
    name: "kind taxonomy completeness nudge"
    severity: warn
    manual: requirements-and-targets#completeness
    short: "Project requirements editor checklist nudges across the 8 canonical kinds."

  SAFE-001:
    name: "juvenile-coded content boundary"
    severity: block
    manual: amood-workflow#safety-boundary
    short: "Juvenile-coded outputs cannot be promoted; DB CHECK constraint enforced."
  SAFE-002:
    name: "coercion-coded content boundary"
    severity: block
    manual: amood-workflow#safety-boundary
    short: "Coercion-coded outputs cannot be promoted; DB CHECK constraint enforced."
  SAFE-003:
    name: "hidden-camera content boundary"
    severity: block
    manual: amood-workflow#safety-boundary
    short: "Hidden-camera-coded outputs cannot be promoted; DB CHECK constraint enforced."
```

This initial registry seeds `topology.yaml` `rules:` block. I3 INFRASTRUCTURE WP populates it; subsequent WPs add entries as new rules emerge.

## Out Of Scope For v0.1

- Rule-versioning. v0.1 rules are immutable in shape; new versions get new IDs (e.g. `AMOOD-001-v2`).
- Cross-rule dependencies (rule A applies only when rule B passes). Rules are flat in v0.1.
- LLM-issued rule authoring. Only operators may add project-scoped rules in v0.1.
- Severity escalation (warn → block on N occurrences). Not in v0.1.
- Mechanical extraction of rules from product code error strings (only the audit checks the inverse direction — that strings cite real IDs).

## Reality Boundary For v0.1

- **Real Seam**: registry shape locked across global YAML + project DB; 4-tier severity defined; error-citation contract specified; initial registry of 25 rule_ids seeded; DB schema for `library_rules` defined; `dump_rules` command added; `state.library.guidance.active_rules` block specified.
- **User-Visible Win**: any error message points to a manual topic with a fix command; any cold-start LLM reads `state.library.guidance.active_rules` + `dump_rules` and learns what governs the current action.
- **Proof Target**: I3 IMPLEMENTATION WPs cite rules by ID in error strings; pytest covers `dump_rules` filter behavior; audit script extension verifies every rule_id resolves to a manual anchor.
- **Allowed Temporary Fallbacks**: AMood and INTAKE rule_ids may exist in the spec before manual topics fully cover their anchors; the audit's `manual_link resolves` check is `warn` until WP-I3-001's manual topics land in the same WP.
- **Promotion Guard**: do not declare registry v0.1 stable until: (a) all 25 initial rule_ids resolve to a manual anchor, (b) audit script extension passes on the live tree, (c) at least 5 dispatcher errors in production code have been migrated to the citation shape and verified.
