"""Intake & triage subpackage (WP-I3-004).

Spec: `.gov/spec/openrepose_intake_v0_1.md`. Composes with the schema
landed by WP-I3-003 (`library_projects`, `library_tasks`, `library_outputs`,
`library_pose_guides`, `library_runs`, `library_batches`, `library_diagnostics`,
`library_rules`).

Data-layer functions take a live `psycopg.Connection` so the dispatcher
controls transaction boundaries.
"""

from .auto_route import AutoRouteResult, run_auto_route
from .outputs import (
    IntakeOutput,
    IntakeOutputError,
    bulk_promote_task,
    finalize_output,
    get_output,
    list_outputs,
    register_output,
    reject_output,
    reroute_output,
    soft_accept_output,
)
from .projects import (
    LibraryProject,
    create_project,
    get_project,
    list_projects,
)
from .tasks import (
    LibraryTask,
    create_task,
    get_task,
    list_tasks,
    task_summary,
    wholesale_reject_task,
)
from .tokens import expected_operator_token, verify_operator_token

__all__ = [
    "AutoRouteResult",
    "IntakeOutput",
    "IntakeOutputError",
    "LibraryProject",
    "LibraryTask",
    "bulk_promote_task",
    "create_project",
    "create_task",
    "expected_operator_token",
    "finalize_output",
    "get_output",
    "get_project",
    "get_task",
    "list_outputs",
    "list_projects",
    "list_tasks",
    "register_output",
    "reject_output",
    "reroute_output",
    "run_auto_route",
    "soft_accept_output",
    "task_summary",
    "verify_operator_token",
    "wholesale_reject_task",
]
