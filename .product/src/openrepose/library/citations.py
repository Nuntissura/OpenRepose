"""Rule citation registry + uniform error citation formatter.

Spec: `.gov/spec/openrepose_rules_v0_1.md` "Error Citation Contract".

The registry below mirrors `.gov/topology.yaml rule_registry.rules`. Both
copies are kept in sync by the WP-I3-009 audit-script extension; if you
change one, change the other.

Citation shape (uniform across every command):

    ERR cmd=<command>: <action_result> by <rule_id> (<rule_name>): <short>.
    See manual: <manual_link>.
    Fix: <suggested_command_or_action>.
"""

from __future__ import annotations

from dataclasses import dataclass


class RuleNotInRegistryError(KeyError):
    """Raised when code tries to cite a rule_id that is not in the registry.

    Surfaces as a developer-facing failure during testing — the citation
    layer must never emit an error message for a non-existent rule_id.
    """


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    severity: str  # 'auto-route' | 'block' | 'warn' | 'info'
    short: str
    manual: str

    def manual_link(self) -> str:
        return f".gov/doc/manual/{self.manual}.md" if "#" not in self.manual else f".gov/doc/manual/{self.manual}"


# Mirror of topology.yaml `rule_registry.rules`. Order matches the YAML
# block for review-time diffability.
_REGISTRY: dict[str, Rule] = {
    # Repo-wide governance rules
    "RUL-000": Rule("RUL-000", "Adult Production Boundary", "block",
                   "Repo + product + LLM assistants do not censor adult production language and do not enforce legal/consent paperwork.",
                   "adult-production-boundary"),
    "RUL-001": Rule("RUL-001", "Work-Start Protocol", "block",
                   "No .product/ edit without WP at READY/IN-PROGRESS + taskboard row + kickoff push first.",
                   "../workflow/README.md#hard-rules"),
    "RUL-002": Rule("RUL-002", "Pre-Work Commit Rule", "block",
                   "Commit + push WP file + taskboard row before opening any .product/ file.",
                   "../workflow/README.md#hard-rules"),
    "RUL-003": Rule("RUL-003", "Naming Convention", "block",
                   "No blank-space chars in any committed file/folder path. kebab-case for docs/WPs, snake_case for Python.",
                   "../AGENTS.md#naming-convention-rule"),
    "RUL-004": Rule("RUL-004", "Disk-Agnostic", "block",
                   "No hardcoded absolute paths in any committed file.",
                   "../AGENTS.md#disk-agnostic-rule"),
    "RUL-005": Rule("RUL-005", "Research-First", "warn",
                   "Research current sources before non-trivial features; record findings in WP Research Notes.",
                   "../AGENTS.md#research-first-rule"),
    "RUL-006": Rule("RUL-006", "Deletion Protocol", "block",
                   "All deletions through /safe-delete or scripts/safe-delete.ps1.",
                   "../AGENTS.md#deletion-protocol"),
    "RUL-007": Rule("RUL-007", "Manual Impact Rule", "block",
                   "Every IMPLEMENTATION-class WP at Workflow Version 1.1+ has a 'Manual Impact:' line in DoD.",
                   "../AGENTS.md#manual-impact-rule"),
    # AMood
    "AMOOD-001": Rule("AMOOD-001", "anti-repetition threshold", "warn",
                     ">= 6 axis overlap with accepted card requires revision; project-overridable.",
                     "amood-workflow.md#anti-repetition"),
    "AMOOD-002": Rule("AMOOD-002", "abandonment trigger", "warn",
                     "12 seeds with trigger_clarity < 4, or 8 seeds with repeated structural failure => card-level abandon.",
                     "amood-workflow.md#abandonment-criteria"),
    "AMOOD-003": Rule("AMOOD-003", "fast-triage fail-fast", "warn",
                     "Any of 4 fast-triage fields below bar => reject before full rubric runs.",
                     "amood-workflow.md#fast-triage"),
    "AMOOD-004": Rule("AMOOD-004", "AMood safety boundary", "block",
                     "Juvenile/coercive/hidden-camera output => card-level abandon. DB CHECK enforced.",
                     "amood-workflow.md#safety-boundary"),
    # Intake & triage
    "INTAKE-001": Rule("INTAKE-001", "two-stage acceptance", "block",
                      "LLM may soft_accept; only operator may finalize.",
                      "intake-and-triage.md#two-stage-acceptance"),
    "INTAKE-002": Rule("INTAKE-002", "default intake target", "block",
                      "ComfyUI bridge writes to intake unless operator token allows direct library.",
                      "intake-and-triage.md#default-intake"),
    "INTAKE-003": Rule("INTAKE-003", "per-task isolation", "info",
                      "Wholesale reject = directory delete + DB row delete in one transaction.",
                      "intake-and-triage.md#per-task-isolation"),
    "INTAKE-004": Rule("INTAKE-004", "library_search excludes pending", "info",
                      "library_search filters status='pending' by default; explicit include_pending=true to see.",
                      "intake-and-triage.md#library-search"),
    # Targets
    "TARGET-001": Rule("TARGET-001", "satisfaction = count + quota", "warn",
                      "task is fully_satisfied only when count_satisfied AND quota_satisfied (AMood diversity audit >= 0.75).",
                      "targets-and-progress.md#fully-satisfied"),
    "TARGET-002": Rule("TARGET-002", "forecast warning", "warn",
                      "in_flight < gap => forecast_ok=false; cannot close target from current intake.",
                      "targets-and-progress.md#forecast"),
    "TARGET-003": Rule("TARGET-003", "stability vs completeness", "info",
                      "card 'stable' when promoted >= stability_target (AMood, default 4); 'complete' when promoted >= target_promoted (project).",
                      "targets-and-progress.md#stable-vs-complete"),
    # Requirements
    "REQ-001": Rule("REQ-001", "inheritance: lower scope wins", "info",
                   "On conflict, card-scope rule overrides batch; batch overrides task; task overrides project.",
                   "requirements-and-targets.md#inheritance"),
    "REQ-002": Rule("REQ-002", "auto-route reversibility", "info",
                   "Operator may re-route from diagnostic/intermediate_evidence/ back to pending if metadata mis-detected.",
                   "requirements-and-targets.md#auto-route"),
    "REQ-003": Rule("REQ-003", "kind taxonomy completeness nudge", "warn",
                   "Project requirements editor checklist nudges across the 8 canonical kinds.",
                   "requirements-and-targets.md#completeness"),
    # Safety boundaries
    "SAFE-001": Rule("SAFE-001", "juvenile-coded content boundary", "block",
                    "Juvenile-coded outputs cannot be promoted; DB CHECK constraint enforced.",
                    "amood-workflow.md#safety-boundary"),
    "SAFE-002": Rule("SAFE-002", "coercion-coded content boundary", "block",
                    "Coercion-coded outputs cannot be promoted; DB CHECK constraint enforced.",
                    "amood-workflow.md#safety-boundary"),
    "SAFE-003": Rule("SAFE-003", "hidden-camera content boundary", "block",
                    "Hidden-camera-coded outputs cannot be promoted; DB CHECK constraint enforced.",
                    "amood-workflow.md#safety-boundary"),
}


def get_rule(rule_id: str) -> Rule:
    try:
        return _REGISTRY[rule_id]
    except KeyError as e:
        raise RuleNotInRegistryError(
            f"rule_id {rule_id!r} not in registry; check topology.yaml rule_registry.rules"
        ) from e


def all_rule_ids() -> list[str]:
    return list(_REGISTRY.keys())


def format_citation(
    *,
    command: str,
    rule_id: str,
    action_result: str,
    fix_action: str,
) -> str:
    """Format an error message in the canonical citation shape.

    `action_result` is the verb phrase ("blocked", "warned", "routed").
    `fix_action` is the operator/LLM remediation hint.
    """
    rule = get_rule(rule_id)
    return (
        f"ERR cmd={command}: {action_result} by {rule_id} ({rule.name}): {rule.short}\n"
        f"See manual: {rule.manual}.\n"
        f"Fix: {fix_action}."
    )
