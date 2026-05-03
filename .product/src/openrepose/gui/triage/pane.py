"""Triage tab — read-only view of intake + targets + amood state.

Spec: `.gov/spec/openrepose_intake_v0_1.md` § "State Surface" +
      `.gov/spec/openrepose_requirements_v0_1.md` § "State Surface" +
      `.gov/spec/openrepose_amood_v0_1.md` § "State Surface".

Three sub-panes the snapshot subsystem can grab independently:

  * ProjectSummaryPane      project-level target_promoted / promoted / gap
                            / forecast_ok / count_satisfied + per-group
                            stable_cards / complete_cards counts
  * TaskSummaryPane         active task counters from state.library.intake
                            and state.library.targets.active_task; this
                            is the snapshot target ``task_summary_view``
  * ActiveCardPane          active card slug / promoted / stable / complete
                            + dedupe warnings tail from state.library.amood;
                            this is the snapshot target ``library_card_with_pose``

Headless rule: never calls ``raise_``, ``activateWindow``, ``showNormal``,
``setForegroundWindow``. No QMessageBox imports — operator-side dialogs
land in a future GUI polish WP after WP-I3-010.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...state import AppState

_VALUE_OBJECT = "triage-value"
_KEY_OBJECT = "triage-key"


def _value_label(initial: str = "-") -> QLabel:
    label = QLabel(initial)
    label.setObjectName(_VALUE_OBJECT)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _key_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(_KEY_OBJECT)
    return label


def _heading(text: str) -> QLabel:
    h = QLabel(text)
    h.setObjectName("triage-heading")
    h.setStyleSheet("font-weight: 600; padding: 6px 0 2px 0;")
    return h


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


# ---------------------------------------------------------------------------
# Sub-panes
# ---------------------------------------------------------------------------


class ProjectSummaryPane(QWidget):
    """Project-level target tree summary + per-group rows."""

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        outer.addWidget(_heading("Project"))
        form = QFormLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(2)
        self._fields: dict[str, QLabel] = {}
        for key in (
            "slug", "target_promoted", "promoted", "gap",
            "in_flight", "forecast_ok", "count_satisfied", "fully_satisfied",
        ):
            v = _value_label()
            form.addRow(_key_label(key), v)
            self._fields[key] = v
        outer.addLayout(form)

        outer.addWidget(_heading("Groups"))
        self._groups_list = QListWidget()
        self._groups_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        outer.addWidget(self._groups_list, 1)

    def update_state(self, targets: dict[str, Any] | None) -> None:
        targets = targets or {}
        project = targets.get("project") or {}
        if not project:
            self._fields["slug"].setText("(no active project)")
            for k in (
                "target_promoted", "promoted", "gap", "in_flight",
                "forecast_ok", "count_satisfied", "fully_satisfied",
            ):
                self._fields[k].setText("-")
            self._groups_list.clear()
            self._groups_list.addItem("(no project — author one with project_create)")
            return

        self._fields["slug"].setText(str(project.get("slug") or "-"))
        self._fields["target_promoted"].setText(str(project.get("target_promoted", 0)))
        self._fields["promoted"].setText(str(project.get("promoted", 0)))
        self._fields["gap"].setText(str(project.get("gap", 0)))
        self._fields["in_flight"].setText(str(project.get("in_flight", 0)))
        self._fields["forecast_ok"].setText(str(project.get("forecast_ok", False)))
        self._fields["count_satisfied"].setText(str(project.get("count_satisfied", False)))
        self._fields["fully_satisfied"].setText(str(project.get("fully_satisfied", False)))

        self._groups_list.clear()
        groups = targets.get("groups") or []
        if not groups:
            self._groups_list.addItem("(no target tree — run project_set_target_tree)")
            return
        for g in groups:
            slug = g.get("slug") or "?"
            name = g.get("name") or ""
            promoted = g.get("promoted", 0)
            target = g.get("target_promoted", 0)
            gap = g.get("gap", 0)
            stable = g.get("stable_cards", 0)
            complete = g.get("complete_cards", 0)
            created = g.get("created_cards", 0)
            expected = g.get("expected_cards", 0)
            line = (
                f"{slug:<5} {promoted:>4}/{target:<4}  gap={gap:<4}  "
                f"stable={stable:<3}  complete={complete:<3}  "
                f"cards={created}/{expected}   {name}"
            )
            self._groups_list.addItem(QListWidgetItem(line))


class TaskSummaryPane(QWidget):
    """Active task counters + intake queue head.

    Snapshot target name: ``task_summary_view``.
    """

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        outer.addWidget(_heading("Active task"))
        form = QFormLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(2)
        self._fields: dict[str, QLabel] = {}
        for key in (
            "task_slug", "task_id", "received", "pending", "triaging",
            "soft_accepted", "promoted", "rejected", "diagnostic",
            "abandoned", "queue_depth",
        ):
            v = _value_label()
            form.addRow(_key_label(key), v)
            self._fields[key] = v
        outer.addLayout(form)

        outer.addWidget(_hline())
        outer.addWidget(_heading("Forecast"))
        self._forecast_label = _value_label("(no active task)")
        self._forecast_label.setWordWrap(True)
        outer.addWidget(self._forecast_label)

        outer.addStretch(1)

    def update_state(
        self,
        intake: dict[str, Any] | None,
        targets: dict[str, Any] | None,
    ) -> None:
        intake = intake or {}
        targets = targets or {}
        active_task = targets.get("active_task") or {}

        slug = intake.get("active_task_slug") or "(no active task)"
        task_id = intake.get("active_task_id") or "-"
        self._fields["task_slug"].setText(str(slug))
        self._fields["task_id"].setText(str(task_id))
        for src_key, dst_key in (
            ("received_count", "received"),
            ("pending_count", "pending"),
            ("triaging_count", "triaging"),
            ("soft_accepted_count", "soft_accepted"),
            ("promoted_count", "promoted"),
            ("rejected_count", "rejected"),
            ("diagnostic_count", "diagnostic"),
            ("abandoned_count", "abandoned"),
            ("queue_depth", "queue_depth"),
        ):
            self._fields[dst_key].setText(str(intake.get(src_key, 0)))

        if not active_task:
            self._forecast_label.setText("(no active task — task_summary returns empty)")
            return
        gap = active_task.get("gap", 0)
        in_flight = active_task.get("in_flight", 0)
        forecast_ok = active_task.get("forecast_ok", False)
        satisfied = active_task.get("satisfied", False)
        line = (
            f"gap={gap}  in_flight={in_flight}  "
            f"forecast_ok={forecast_ok}  satisfied={satisfied}"
        )
        self._forecast_label.setText(line)


class ActiveCardPane(QWidget):
    """Active card slug + promoted/stable/complete flags + dedupe-warning tail.

    Snapshot target name: ``library_card_with_pose``. The pose preview itself
    is rendered by `render/draw_triage.render_library_card_with_pose` for the
    headless path; the widget-grab path captures this widget directly.
    """

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        outer.addWidget(_heading("Active card"))
        form = QFormLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(2)
        self._fields: dict[str, QLabel] = {}
        for key in (
            "card_slug", "card_id", "target_promoted",
            "stability_target", "promoted", "stable", "complete",
        ):
            v = _value_label()
            form.addRow(_key_label(key), v)
            self._fields[key] = v
        outer.addLayout(form)

        outer.addWidget(_hline())
        outer.addWidget(_heading("AMood batch"))
        self._batch_label = _value_label("(no active batch)")
        self._batch_label.setWordWrap(True)
        outer.addWidget(self._batch_label)

        outer.addWidget(_heading("Dedupe warnings (last 5)"))
        self._dedupe_list = QListWidget()
        self._dedupe_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._dedupe_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        outer.addWidget(self._dedupe_list, 1)

    def update_state(
        self,
        targets: dict[str, Any] | None,
        amood: dict[str, Any] | None,
    ) -> None:
        targets = targets or {}
        amood = amood or {}
        card = targets.get("active_card") or {}

        if not card:
            self._fields["card_slug"].setText("(no active card)")
            for k in (
                "card_id", "target_promoted", "stability_target",
                "promoted", "stable", "complete",
            ):
                self._fields[k].setText("-")
        else:
            self._fields["card_slug"].setText(str(card.get("slug") or "-"))
            self._fields["card_id"].setText(str(card.get("card_id") or "-"))
            self._fields["target_promoted"].setText(str(card.get("target_promoted", 0)))
            self._fields["stability_target"].setText(str(card.get("stability_target", 0)))
            self._fields["promoted"].setText(str(card.get("promoted", 0)))
            self._fields["stable"].setText(str(card.get("stable", False)))
            self._fields["complete"].setText(str(card.get("complete", False)))

        if not amood or not amood.get("active_batch_id"):
            self._batch_label.setText("(no active batch)")
        else:
            slug = amood.get("active_batch_slug") or "-"
            tier = amood.get("tier") or "-"
            family = amood.get("primary_explicit_family") or "-"
            stable = amood.get("stable_cards", 0)
            unstable = amood.get("unstable_cards", 0)
            abandoned = amood.get("abandoned_cards", 0)
            self._batch_label.setText(
                f"{slug} ({tier}, {family})  "
                f"stable={stable}  unstable={unstable}  abandoned={abandoned}"
            )

        self._dedupe_list.clear()
        warnings = (amood.get("dedupe_recent_warnings") or [])[-5:]
        if not warnings:
            self._dedupe_list.addItem("(no recent dedupe warnings)")
        else:
            for w in warnings:
                line = (
                    f"{w.get('at', '')}  "
                    f"card={w.get('card_id', '')[:8]}  "
                    f"overlap={w.get('overlap_count', 0)}  "
                    f"matched={w.get('matched_card_slug', '')}"
                )
                self._dedupe_list.addItem(line)


# ---------------------------------------------------------------------------
# Top-level tab
# ---------------------------------------------------------------------------


class TriagePane(QWidget):
    """Top-level Triage tab. Polled by `MainWindow._on_state_poll`.

    Layout: horizontal splitter. Left = ProjectSummaryPane. Right = vertical
    splitter with TaskSummaryPane (top) + ActiveCardPane (bottom).
    """

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self._state = state

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._project_pane = ProjectSummaryPane()
        self._task_pane = TaskSummaryPane()
        self._card_pane = ActiveCardPane()

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.addWidget(self._task_pane)
        right_split.addWidget(self._card_pane)
        right_split.setSizes([260, 260])

        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.addWidget(self._project_pane)
        main_split.addWidget(right_split)
        main_split.setSizes([320, 360])

        outer.addWidget(main_split)
        self.refresh()

    # --- accessors for the snapshot widget provider ---------------------

    @property
    def task_summary_pane(self) -> TaskSummaryPane:
        return self._task_pane

    @property
    def active_card_pane(self) -> ActiveCardPane:
        return self._card_pane

    # --- state -> widget sync -------------------------------------------

    def refresh(self) -> None:
        library = dict(self._state.library)
        intake = library.get("intake")
        targets = library.get("targets")
        amood = library.get("amood")
        self._project_pane.update_state(targets)
        self._task_pane.update_state(intake, targets)
        self._card_pane.update_state(targets, amood)
