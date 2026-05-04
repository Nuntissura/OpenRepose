"""Intake & triage subpackage (WP-I3-004).

Spec: `.gov/spec/openrepose_intake_v0_1.md`. Composes with the schema
landed by WP-I3-003 (`library_projects`, `library_tasks`, `library_outputs`,
`library_pose_guides`, `library_runs`, `library_batches`, `library_diagnostics`,
`library_rules`).

Data-layer functions take a live `psycopg.Connection` so the dispatcher
controls transaction boundaries.
"""

from .auto_route import AutoRouteResult, run_auto_route
from .bulk import (
    BULK_BATCH_MAX_DEFAULT,
    BulkIntakeError,
    BulkOutputResult,
    register_outputs_bulk,
)
from .runs import LibraryRun, LibraryRunError, begin_run, resolve_card_by_slug
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
from .storage import (
    INTAKE_006_STORAGE_STATES,
    STATUS_TO_STORAGE_STATE,
    RecoveryAudit,
    StorageError,
    claim_pending_file_ops,
    complete_file_op,
    diagnostic_dst_path,
    enqueue_file_op,
    execute_file_op,
    process_pending_file_ops,
    record_event,
    recover_audit,
    recover_retry,
    reject_dst_path,
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
    "BULK_BATCH_MAX_DEFAULT",
    "BulkIntakeError",
    "BulkOutputResult",
    "INTAKE_006_STORAGE_STATES",
    "IntakeOutput",
    "IntakeOutputError",
    "LibraryProject",
    "LibraryRun",
    "LibraryRunError",
    "LibraryTask",
    "RecoveryAudit",
    "STATUS_TO_STORAGE_STATE",
    "StorageError",
    "begin_run",
    "bulk_promote_task",
    "claim_pending_file_ops",
    "complete_file_op",
    "create_project",
    "create_task",
    "diagnostic_dst_path",
    "enqueue_file_op",
    "execute_file_op",
    "expected_operator_token",
    "finalize_output",
    "get_output",
    "get_project",
    "get_task",
    "list_outputs",
    "list_projects",
    "list_tasks",
    "process_pending_file_ops",
    "record_event",
    "recover_audit",
    "recover_retry",
    "register_output",
    "register_outputs_bulk",
    "reject_dst_path",
    "reject_output",
    "resolve_card_by_slug",
    "reroute_output",
    "run_auto_route",
    "soft_accept_output",
    "task_summary",
    "verify_operator_token",
    "wholesale_reject_task",
]
