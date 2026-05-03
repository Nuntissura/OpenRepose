"""Triage pane state-poll + widget-construction tests (WP-I3-008).

Runs against the offscreen Qt platform (configured in conftest.py) so
no real widget surfaces are created on the operator desktop.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from openrepose.gui.triage import (  # noqa: E402
    ActiveCardPane,
    ProjectSummaryPane,
    TaskSummaryPane,
    TriagePane,
)
from openrepose.state import AppState  # noqa: E402


@pytest.fixture
def state(tmp_path) -> AppState:
    return AppState(state_path=tmp_path / "state.json")


@pytest.fixture(autouse=True)
def qapp():
    """Ensure a single QApplication exists for the test session."""
    from PySide6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


def test_triage_pane_constructs_against_empty_state(state: AppState) -> None:
    pane = TriagePane(state)
    assert pane.task_summary_pane is not None
    assert pane.active_card_pane is not None


def test_project_summary_pane_empty_renders_no_active(state: AppState) -> None:
    pane = ProjectSummaryPane()
    pane.update_state(None)
    # The slug field should show the no-active label.
    label = pane.findChildren(type(pane.findChild(type, "")))  # noqa: E501
    # Easier: read the layout via the public attribute.
    assert pane._fields["slug"].text() == "(no active project)"


def test_task_summary_pane_reflects_intake_counts(state: AppState) -> None:
    pane = TaskSummaryPane()
    intake = {
        "active_task_id": "abc",
        "active_task_slug": "T-EXP120-001",
        "received_count": 50,
        "pending_count": 12,
        "soft_accepted_count": 3,
        "promoted_count": 4,
        "rejected_count": 30,
        "diagnostic_count": 1,
        "queue_depth": 12,
    }
    pane.update_state(intake, None)
    assert pane._fields["task_slug"].text() == "T-EXP120-001"
    assert pane._fields["pending"].text() == "12"
    assert pane._fields["promoted"].text() == "4"
    assert pane._fields["queue_depth"].text() == "12"


def test_active_card_pane_reflects_targets_and_amood() -> None:
    pane = ActiveCardPane()
    targets = {
        "active_card": {
            "card_id": "c-1", "slug": "SF-15", "target_promoted": 8,
            "stability_target": 4, "promoted": 5, "stable": True, "complete": False,
        }
    }
    amood = {
        "active_batch_id": "b-1",
        "active_batch_slug": "exp120-batch-01",
        "tier": "production",
        "primary_explicit_family": "exposure",
        "stable_cards": 3,
        "unstable_cards": 1,
        "abandoned_cards": 0,
        "dedupe_recent_warnings": [
            {"card_id": "abcd1234", "overlap_count": 7,
             "matched_card_slug": "SF-12", "at": "2026-05-04T10:00:00Z"},
        ],
    }
    pane.update_state(targets, amood)
    assert pane._fields["card_slug"].text() == "SF-15"
    assert pane._fields["promoted"].text() == "5"
    assert pane._fields["stable"].text() == "True"


def test_triage_refresh_picks_up_state_changes(state: AppState) -> None:
    """End-to-end: mutate AppState.library, call refresh, verify display."""
    pane = TriagePane(state)
    # Start: no project, no task.
    assert pane.task_summary_pane._fields["task_slug"].text() == "(no active task)"

    state.set_intake_state(
        active_task_id="t-1",
        active_task_slug="T-INTAKE-A",
        pending_count=7,
        promoted_count=2,
        queue_depth=7,
    )
    state.set_targets_state(
        project={
            "id": "p-1", "slug": "exposure-120",
            "target_promoted": 960, "promoted": 12, "gap": 948,
            "in_flight": 7, "forecast_ok": False,
            "count_satisfied": False, "quota_satisfied": False, "fully_satisfied": False,
        },
        groups=[],
        active_task=None,
        active_card={
            "slug": "SF-01", "card_id": "c-1",
            "target_promoted": 8, "stability_target": 4,
            "promoted": 0, "stable": False, "complete": False,
        },
    )
    pane.refresh()

    # Updated values should now appear.
    assert pane.task_summary_pane._fields["task_slug"].text() == "T-INTAKE-A"
    assert pane.task_summary_pane._fields["pending"].text() == "7"
    assert pane.active_card_pane._fields["card_slug"].text() == "SF-01"
