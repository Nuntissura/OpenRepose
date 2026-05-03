"""CRUD on `library_tasks` + intake_dir filesystem layout (WP-I3-004).

Spec: `.gov/spec/openrepose_intake_v0_1.md` "Hierarchy / library_tasks"
                                            + "Folder Layout".

Task creation also creates the `outputs/intake/<YYYYMMDD>-<task_slug>/`
directory tree (`raw/`, `diagnostic/`, `contact_sheets/`, `rejected/`).
Wholesale-reject deletes the directory via `scripts/safe-delete.ps1`
(operator helper) — never via direct `Remove-Item` (RUL-006).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    import psycopg


_INTAKE_SUBDIRS = ("raw", "diagnostic", "contact_sheets", "rejected")
_VALID_TASK_STATUSES = (
    "pending", "triaging", "complete", "rejected_wholesale", "aborted",
)


class LibraryTaskError(ValueError):
    """Raised when task input is malformed or a row is missing."""


@dataclass
class LibraryTask:
    id: UUID
    project_id: UUID
    slug: str
    source: str | None
    llm_model: str | None
    expected_count: int | None
    received_count: int
    status: str
    intake_dir: str
    summary_json: dict[str, Any] | None
    created_at: datetime | None
    finalized_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "slug": self.slug,
            "source": self.source,
            "llm_model": self.llm_model,
            "expected_count": self.expected_count,
            "received_count": self.received_count,
            "status": self.status,
            "intake_dir": self.intake_dir,
            "summary_json": self.summary_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "finalized_at": self.finalized_at.isoformat() if self.finalized_at else None,
        }


def create_task(
    conn: "psycopg.Connection[object]",
    *,
    project_id: UUID | str,
    slug: str,
    expected_count: int | None = None,
    source: str | None = None,
    llm_model: str | None = None,
    outputs_root: Path | None = None,
) -> LibraryTask:
    """Insert a library_tasks row + create the intake directory tree.

    `intake_dir` is recorded as a relative path under `outputs/intake/`
    (stable identifier; the absolute path is `<outputs_root>/intake/<dir>`).
    """
    if not slug:
        raise LibraryTaskError("slug is required")
    if expected_count is not None and expected_count < 0:
        raise LibraryTaskError("expected_count must be >= 0")
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    rel_dir = f"{today}-{slug}/"
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO library_tasks "
            "(project_id, slug, expected_count, source, llm_model, intake_dir) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "RETURNING id, project_id, slug, source, llm_model, expected_count, "
            "          received_count, status, intake_dir, summary_json, "
            "          created_at, finalized_at",
            (str(project_id), slug, expected_count, source, llm_model, rel_dir),
        )
        row = cur.fetchone()
    conn.commit()
    task = _row_to_task(row)
    if outputs_root is not None:
        _ensure_intake_dir_tree(outputs_root, rel_dir)
    return task


def _ensure_intake_dir_tree(outputs_root: Path, rel_dir: str) -> None:
    base = Path(outputs_root) / "intake" / rel_dir
    base.mkdir(parents=True, exist_ok=True)
    for sub in _INTAKE_SUBDIRS:
        (base / sub).mkdir(exist_ok=True)


def get_task(
    conn: "psycopg.Connection[object]",
    *,
    task_id: UUID | str,
) -> LibraryTask | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, project_id, slug, source, llm_model, expected_count, "
            "       received_count, status, intake_dir, summary_json, "
            "       created_at, finalized_at "
            "FROM library_tasks WHERE id = %s",
            (str(task_id),),
        )
        row = cur.fetchone()
    return _row_to_task(row) if row else None


def list_tasks(
    conn: "psycopg.Connection[object]",
    *,
    project_id: UUID | str | None = None,
    status: str | None = None,
) -> list[LibraryTask]:
    where_parts: list[str] = []
    args: list[Any] = []
    if project_id is not None:
        where_parts.append("project_id = %s")
        args.append(str(project_id))
    if status is not None:
        if status not in _VALID_TASK_STATUSES:
            raise LibraryTaskError(
                f"status filter must be one of {_VALID_TASK_STATUSES}"
            )
        where_parts.append("status = %s")
        args.append(status)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, project_id, slug, source, llm_model, expected_count, "
            "       received_count, status, intake_dir, summary_json, "
            "       created_at, finalized_at "
            f"FROM library_tasks {where} ORDER BY created_at DESC",
            tuple(args),
        )
        rows = cur.fetchall()
    return [_row_to_task(r) for r in rows]


def task_summary(
    conn: "psycopg.Connection[object]",
    *,
    task_id: UUID | str,
) -> dict[str, Any]:
    """Return per-status counters for a task + warnings the operator
    can act on at pre-flight.

    Counters come from `library_outputs.status` directly (cheaper than
    the per-target-card view when all we need is task-level totals)."""
    task = get_task(conn, task_id=task_id)
    if task is None:
        raise LibraryTaskError(f"task {task_id} not found")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, COUNT(*) FROM library_outputs "
            "WHERE task_id = %s GROUP BY status",
            (str(task_id),),
        )
        counts = {row[0]: int(row[1]) for row in cur.fetchall()}
        cur.execute(
            "SELECT COUNT(*) FROM library_runs r "
            "WHERE r.task_id = %s AND r.pose_guide_id IS NULL",
            (str(task_id),),
        )
        missing_pose_guides = int(cur.fetchone()[0])
    return {
        "task_id": str(task.id),
        "task_slug": task.slug,
        "expected_count": task.expected_count,
        "received_count": task.received_count,
        "pending_count": counts.get("pending", 0),
        "triaging_count": counts.get("triaging", 0),
        "soft_accepted_count": counts.get("soft_accepted", 0),
        "promoted_count": counts.get("promoted", 0),
        "rejected_count": counts.get("rejected", 0),
        "diagnostic_count": counts.get("diagnostic", 0),
        "abandoned_count": counts.get("abandoned", 0),
        "missing_pose_guides": missing_pose_guides,
        "status": task.status,
    }


def wholesale_reject_task(
    conn: "psycopg.Connection[object]",
    *,
    task_id: UUID | str,
    operator_slug: str,
    reason: str,
    outputs_root: Path | None = None,
) -> dict[str, Any]:
    """Transition every non-terminal output for the task to status
    'rejected' in one transaction; mark the task itself as
    'rejected_wholesale'; delete the intake directory.

    Per RUL-006, directory deletion uses `shutil.rmtree` only when the
    target resolves under `outputs_root/intake/` — never on absolute
    paths supplied by the caller. The repo's `scripts/safe-delete.ps1`
    is the operator-facing equivalent; this Python path mirrors its
    guards.
    """
    task = get_task(conn, task_id=task_id)
    if task is None:
        raise LibraryTaskError(f"task {task_id} not found")
    if task.status in ("rejected_wholesale", "aborted"):
        raise LibraryTaskError(
            f"task {task_id} already terminal: status={task.status}"
        )

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE library_outputs SET status = 'rejected', "
            "       rejected_at = NOW(), "
            "       primary_rejection_reason = %s, "
            "       finalized_by = %s "
            "WHERE task_id = %s "
            "  AND status NOT IN ('rejected', 'promoted') "
            "RETURNING id",
            (f"wholesale: {reason}", operator_slug, str(task_id)),
        )
        affected = [str(row[0]) for row in cur.fetchall()]
        cur.execute(
            "UPDATE library_tasks "
            "SET status = 'rejected_wholesale', finalized_at = NOW() "
            "WHERE id = %s",
            (str(task_id),),
        )
    conn.commit()

    deleted_dir = _safe_remove_intake_dir(
        outputs_root, task.intake_dir
    ) if outputs_root is not None else None
    return {
        "task_id": str(task.id),
        "transitioned_count": len(affected),
        "transitioned_output_ids": affected,
        "deleted_intake_dir": deleted_dir,
        "status": "rejected_wholesale",
    }


def _safe_remove_intake_dir(outputs_root: Path, intake_dir: str) -> str | None:
    """Remove a per-task intake directory. Mirrors `scripts/safe-delete.ps1`
    guards: target must resolve inside `<outputs_root>/intake/`, must not
    contain `..`, and must not be the intake root itself.
    """
    if not intake_dir or ".." in intake_dir.split("/") or ".." in intake_dir.split("\\"):
        raise LibraryTaskError(f"unsafe intake_dir: {intake_dir!r}")
    intake_root = (Path(outputs_root) / "intake").resolve()
    target = (intake_root / intake_dir).resolve()
    if target == intake_root:
        raise LibraryTaskError("refused to delete intake root")
    try:
        target.relative_to(intake_root)
    except ValueError as e:
        raise LibraryTaskError(
            f"intake_dir resolves outside intake root: {target}"
        ) from e
    if not target.exists():
        return None
    shutil.rmtree(target)
    return str(Path("intake") / intake_dir).replace("\\", "/")


def _row_to_task(row: Any) -> LibraryTask:
    return LibraryTask(
        id=row[0],
        project_id=row[1],
        slug=row[2],
        source=row[3],
        llm_model=row[4],
        expected_count=row[5],
        received_count=int(row[6]),
        status=row[7],
        intake_dir=row[8],
        summary_json=row[9],
        created_at=row[10],
        finalized_at=row[11],
    )
