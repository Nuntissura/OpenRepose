"""Triage subpackage (WP-I3-008).

Read-only GUI tab that mirrors `state.library.intake`, `state.library.targets`,
and `state.library.amood`. Operator triage actions stay LLM-driven in v0.1
per spec. Three snapshot targets registered through `MainWindow._provide_widget`:
`intake_triage_view`, `task_summary_view`, `library_card_with_pose`.
"""

from __future__ import annotations

from .pane import (
    ActiveCardPane,
    ProjectSummaryPane,
    TaskSummaryPane,
    TriagePane,
)

__all__ = [
    "ActiveCardPane",
    "ProjectSummaryPane",
    "TaskSummaryPane",
    "TriagePane",
]
