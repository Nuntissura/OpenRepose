"""Citation-carrying error class for requirements + target-tree commands.

Mirrors `OpenReposeIntakeError` (WP-I3-004) and `OpenReposeAmoodError`
(WP-I3-006) so dispatcher error envelopes surface the canonical citation
shape from `.gov/spec/openrepose_rules_v0_1.md` § "Error Citation Contract".

Listed in the dispatcher's typed-catch block in `commands.py` so the error
envelope picks up `rule_id` + `citation`.
"""

from __future__ import annotations


class OpenReposeRequirementsError(RuntimeError):
    """Raised by requirements / target-tree command handlers (WP-I3-007).

    Carries `rule_id` (a registry-resolvable ID — global from
    `library/citations.py` or project-scoped from `library_rules`) and a
    pre-formatted `citation` string the dispatcher can surface verbatim.
    """

    def __init__(
        self,
        message: str,
        *,
        rule_id: str | None = None,
        citation: str | None = None,
    ) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.citation = citation
