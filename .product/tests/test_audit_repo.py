"""Tests for scripts/audit-repo.ps1.

Each test stages a temporary copy of the repo, optionally injects a violation,
runs the script, and asserts the exit code and reported violation lines.

The current tree must be clean for these tests to pass (the "clean" test
relies on it). If the audit reports violations on the unmodified tree, fix
them — the test is the canary.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "audit-repo.ps1"


def _have_pwsh() -> bool:
    return shutil.which("pwsh") is not None or shutil.which("powershell") is not None


pytestmark = pytest.mark.skipif(
    not _have_pwsh(), reason="pwsh / powershell not available on this runner"
)


def _run_audit(repo: Path) -> subprocess.CompletedProcess[str]:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    assert pwsh is not None
    script = repo / "scripts" / "audit-repo.ps1"
    return subprocess.run(
        [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def _stage_repo(tmp_path: Path) -> Path:
    """Copy the repo (sans target/ dist/ outputs/ .venv/ .git/) to tmp_path/repo and `git init` it."""
    dst = tmp_path / "repo"
    excludes = {"target", "dist", "outputs", ".venv", ".git", "__pycache__"}

    def _ignore(_dir: str, names: Iterable[str]) -> set[str]:
        return {n for n in names if n in excludes}

    shutil.copytree(REPO_ROOT, dst, ignore=_ignore)

    # Fresh git init so `git ls-files` works in the copy.
    subprocess.run(["git", "init", "-q"], cwd=str(dst), check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(dst), check=True)
    subprocess.run(
        ["git", "-c", "user.email=a@b", "-c", "user.name=test", "commit", "-q", "-m", "stage"],
        cwd=str(dst),
        check=True,
    )
    return dst


def _commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(
        ["git", "-c", "user.email=a@b", "-c", "user.name=test", "commit", "-q", "-m", message],
        cwd=str(repo),
        check=True,
    )


def test_clean_tree_exits_zero(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    result = _run_audit(repo)
    assert result.returncode == 0, (
        f"audit failed on clean tree:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "no violations" in result.stdout


def test_hardcoded_path_detected(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    bad = repo / ".gov" / "doc-injected.md"
    bad.write_text(
        "Reference path for testing: D:\\Projects\\Something\\file.txt\n",
        encoding="utf-8",
    )
    _commit(repo, "inject hardcoded path")

    result = _run_audit(repo)
    assert result.returncode == 1
    assert "[hardcoded-path]" in result.stdout
    assert "doc-injected.md" in result.stdout


def test_doc_folder_is_allowlisted(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    doc_dir = repo / ".gov" / "doc"
    doc_dir.mkdir(exist_ok=True)
    (doc_dir / "operator-supplied-paths.md").write_text(
        "Operator's machine path: D:\\Projects\\Whatever\\\n",
        encoding="utf-8",
    )
    _commit(repo, "doc folder example")

    result = _run_audit(repo)
    assert result.returncode == 0, (
        f"doc folder allowlist not honored:\n{result.stdout}\n{result.stderr}"
    )


def test_blank_space_path_detected(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    bad = repo / ".gov" / "bad name.md"
    bad.write_text("oops\n", encoding="utf-8")
    _commit(repo, "inject blank-space filename")

    result = _run_audit(repo)
    assert result.returncode == 1
    assert "[blank-space-path]" in result.stdout
    assert "bad name.md" in result.stdout


def test_wp_missing_research_notes_detected(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    wp_dir = repo / ".gov" / "workflow" / "workpackets"
    wp_dir.mkdir(parents=True, exist_ok=True)
    (wp_dir / "WP-I9-099-test-impl.md").write_text(
        """# WP-I9-099 - Test

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I9
- **Workflow Version**: `1.1`
- **Packet Class**: `IMPLEMENTATION`
- **Effort Estimate**: S

## Intent

Test WP without Research Notes.
""",
        encoding="utf-8",
    )
    _commit(repo, "inject WP without research notes")

    result = _run_audit(repo)
    assert result.returncode == 1
    assert "[wp-research-notes]" in result.stdout
    assert "WP-I9-099-test-impl.md" in result.stdout


def test_wp_with_research_notes_passes(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    wp_dir = repo / ".gov" / "workflow" / "workpackets"
    # WP-I1-035: must also include Manual Impact line for IMPLEMENTATION v1.1+.
    (wp_dir / "WP-I9-100-test-impl-ok.md").write_text(
        """# WP-I9-100 - Test OK

## Header

- **Owner**: assistant
- **Date Opened**: 2026-05-02
- **Status**: DRAFT
- **Iteration**: I9
- **Workflow Version**: `1.1`
- **Packet Class**: `IMPLEMENTATION`
- **Effort Estimate**: S

## Research Notes

Checked existing approaches; none ship.

## Intent

Has Research Notes.

## Definition Of Done

- [ ] Manual Impact: No — internal refactor with no operator-facing change.
""",
        encoding="utf-8",
    )
    _commit(repo, "WP with research notes")

    result = _run_audit(repo)
    assert result.returncode == 0, (
        f"WP with Research Notes flagged:\n{result.stdout}\n{result.stderr}"
    )


def test_wp_at_workflow_version_1_0_grandfathered(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    wp_dir = repo / ".gov" / "workflow" / "workpackets"
    (wp_dir / "WP-I9-101-legacy.md").write_text(
        """# WP-I9-101 - Legacy

## Header

- **Owner**: assistant
- **Workflow Version**: `1.0`
- **Packet Class**: `IMPLEMENTATION`

## Intent

Pre-1.1 WP without Research Notes — grandfathered.
""",
        encoding="utf-8",
    )
    _commit(repo, "legacy WP")

    result = _run_audit(repo)
    assert result.returncode == 0, (
        f"1.0 WP should be grandfathered:\n{result.stdout}\n{result.stderr}"
    )


def test_documentation_class_not_required_to_have_research_notes(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    wp_dir = repo / ".gov" / "workflow" / "workpackets"
    (wp_dir / "WP-I9-102-doc.md").write_text(
        """# WP-I9-102 - Doc

## Header

- **Workflow Version**: `1.1`
- **Packet Class**: `DOCUMENTATION`

## Intent

Documentation WPs are not subject to Research Notes rule.
""",
        encoding="utf-8",
    )
    _commit(repo, "doc class WP")

    result = _run_audit(repo)
    assert result.returncode == 0, (
        f"DOCUMENTATION WP flagged:\n{result.stdout}\n{result.stderr}"
    )


def test_wp_missing_manual_impact_detected(tmp_path: Path) -> None:
    """WP-I1-035: active IMPLEMENTATION at v1.1+ without Manual Impact fails."""
    repo = _stage_repo(tmp_path)
    wp_dir = repo / ".gov" / "workflow" / "workpackets"
    (wp_dir / "WP-I9-200-no-manual-impact.md").write_text(
        """# WP-I9-200 - Test

## Header

- **Workflow Version**: `1.1`
- **Packet Class**: `IMPLEMENTATION`

## Research Notes

Has notes.

## Intent

Missing Manual Impact line.
""",
        encoding="utf-8",
    )
    _commit(repo, "inject WP without manual impact")

    result = _run_audit(repo)
    assert result.returncode == 1
    assert "[wp-manual-impact]" in result.stdout
    assert "WP-I9-200-no-manual-impact.md" in result.stdout


def test_wp_with_manual_impact_passes(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    wp_dir = repo / ".gov" / "workflow" / "workpackets"
    (wp_dir / "WP-I9-201-with-manual-impact.md").write_text(
        """# WP-I9-201 - OK

## Header

- **Workflow Version**: `1.1`
- **Packet Class**: `IMPLEMENTATION`

## Research Notes

Has notes.

## Intent

Has Manual Impact: Yes — extends getting-started.md with new flow.
""",
        encoding="utf-8",
    )
    _commit(repo, "WP with manual impact")

    result = _run_audit(repo)
    assert result.returncode == 0, (
        f"WP with Manual Impact flagged:\n{result.stdout}"
    )


def test_wp_manual_impact_n_a_bug_fix_form_passes(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    wp_dir = repo / ".gov" / "workflow" / "workpackets"
    (wp_dir / "WP-I9-202-bug-fix.md").write_text(
        """# WP-I9-202 - Bug fix

## Header

- **Workflow Version**: `1.1`
- **Packet Class**: `IMPLEMENTATION`

## Research Notes

Reproduced the bug; fix is local.

## Definition Of Done

- [ ] **Manual Impact**: N/A (bug fix) — fixes off-by-one in serializer.
""",
        encoding="utf-8",
    )
    _commit(repo, "bug-fix WP with N/A form")

    result = _run_audit(repo)
    assert result.returncode == 0, result.stdout


def test_archived_wp_not_required_to_have_manual_impact(tmp_path: Path) -> None:
    """Archived WPs are grandfathered (rule introduced mid-iteration via WP-I1-035)."""
    repo = _stage_repo(tmp_path)
    archive_dir = repo / ".gov" / "workflow" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "WP-I9-203-archived.md").write_text(
        """# WP-I9-203 - Archived

## Header

- **Workflow Version**: `1.1`
- **Packet Class**: `IMPLEMENTATION`

## Research Notes

Has notes.
""",
        encoding="utf-8",
    )
    _commit(repo, "archived WP without manual impact")

    result = _run_audit(repo)
    assert result.returncode == 0, (
        f"archived WP should be grandfathered for manual-impact rule:\n{result.stdout}"
    )


def test_documentation_class_not_required_to_have_manual_impact(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    wp_dir = repo / ".gov" / "workflow" / "workpackets"
    (wp_dir / "WP-I9-204-doc.md").write_text(
        """# WP-I9-204 - Doc

## Header

- **Workflow Version**: `1.1`
- **Packet Class**: `DOCUMENTATION`

## Intent

DOCUMENTATION class is exempt from manual-impact too.
""",
        encoding="utf-8",
    )
    _commit(repo, "doc class WP")

    result = _run_audit(repo)
    assert result.returncode == 0, result.stdout


def test_multiple_violations_all_reported(tmp_path: Path) -> None:
    repo = _stage_repo(tmp_path)
    (repo / ".gov" / "v1.md").write_text("path: D:\\Projects\\X\n", encoding="utf-8")
    (repo / ".gov" / "v2 with space.md").write_text("oops\n", encoding="utf-8")
    _commit(repo, "two violations")

    result = _run_audit(repo)
    assert result.returncode == 1
    assert "[hardcoded-path]" in result.stdout
    assert "[blank-space-path]" in result.stdout
    assert "v1.md" in result.stdout
    assert "v2 with space.md" in result.stdout
