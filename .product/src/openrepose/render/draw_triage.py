"""Render Triage snapshot targets to OpenCV BGR images (headless path).

Spec: `.gov/spec/openrepose_intake_v0_1.md` § "State Surface" +
      `.gov/spec/openrepose_requirements_v0_1.md` § "State Surface".

Three outputs:

  * `render_intake_triage_view(state_library)` — combined project + task
    + card text panel; the headless equivalent of the GUI tab grab.
  * `render_task_summary_view(state_targets, state_intake)` — task-scope
    counters as a labeled text block.
  * `render_library_card_with_pose(card, pose_path, library_root)` —
    side-by-side card preview (pose-guide PNG left, label strip right).

Pure OpenCV / numpy — no Qt imports — so the snapshot subsystem stays
runnable headlessly. Mirrors the visual conventions of
`render/draw_library.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .draw_library import (
    PLACEHOLDER_BG,
    PLACEHOLDER_FG,
    _label_strip,
    _placeholder,
    _read_or_placeholder,
    _resolve,
)


_TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
_TEXT_SCALE = 0.5
_TEXT_THICK = 1
_LINE_HEIGHT = 22
_PANEL_W = 560
_PANEL_H = 540
_HEADER_H = 32


def _draw_lines(canvas: np.ndarray, lines: list[str], *, x: int = 16, y0: int = 28) -> None:
    y = y0
    for line in lines:
        cv2.putText(
            canvas, line, (x, y), _TEXT_FONT, _TEXT_SCALE, PLACEHOLDER_FG,
            _TEXT_THICK, cv2.LINE_AA,
        )
        y += _LINE_HEIGHT


def render_task_summary_view(
    state_targets: dict[str, Any] | None,
    state_intake: dict[str, Any] | None,
) -> np.ndarray:
    """Render the active-task counters as a labeled text panel.

    `state_targets` is `state.library.targets`; `state_intake` is
    `state.library.intake`. Either may be None / empty — the panel renders
    "(no active task)" rather than failing.
    """
    intake = state_intake or {}
    targets = state_targets or {}
    active_task = targets.get("active_task") or {}

    canvas = np.full((_PANEL_H, _PANEL_W, 3), PLACEHOLDER_BG, dtype=np.uint8)
    title = (
        "task_summary_view"
        if intake.get("active_task_slug") is None
        else f"task_summary_view  ·  {intake['active_task_slug']}"
    )
    canvas[:_HEADER_H, :, :] = (24, 28, 34)
    cv2.putText(
        canvas, title, (12, _HEADER_H - 10),
        _TEXT_FONT, 0.55, PLACEHOLDER_FG, 1, cv2.LINE_AA,
    )

    lines: list[str] = []
    if not intake.get("active_task_slug"):
        lines.append("(no active task)")
        lines.append("")
        lines.append("LLM agents may run task_create to start one.")
    else:
        lines.append(f"task_id          {intake.get('active_task_id', '-')}")
        lines.append(f"received         {intake.get('received_count', 0)}")
        lines.append(f"pending          {intake.get('pending_count', 0)}")
        lines.append(f"triaging         {intake.get('triaging_count', 0)}")
        lines.append(f"soft_accepted    {intake.get('soft_accepted_count', 0)}")
        lines.append(f"promoted         {intake.get('promoted_count', 0)}")
        lines.append(f"rejected         {intake.get('rejected_count', 0)}")
        lines.append(f"diagnostic       {intake.get('diagnostic_count', 0)}")
        lines.append(f"abandoned        {intake.get('abandoned_count', 0)}")
        lines.append(f"queue_depth      {intake.get('queue_depth', 0)}")
        lines.append("")
        if active_task:
            lines.append(
                f"gap={active_task.get('gap', 0)}  "
                f"in_flight={active_task.get('in_flight', 0)}  "
                f"forecast_ok={active_task.get('forecast_ok', False)}  "
                f"satisfied={active_task.get('satisfied', False)}"
            )
        else:
            lines.append("(no target_tree active_task block)")

    _draw_lines(canvas, lines, y0=_HEADER_H + 28)
    return canvas


def render_intake_triage_view(state_library: dict[str, Any] | None) -> np.ndarray:
    """Render the full triage view (project + task + card) as a combined panel.

    `state_library` is `AppState.library`. Empty / missing keys render
    "(no …)" labels.
    """
    library = state_library or {}
    intake = library.get("intake") or {}
    targets = library.get("targets") or {}
    amood = library.get("amood") or {}
    project = targets.get("project") or {}
    active_card = targets.get("active_card") or {}

    canvas = np.full((_PANEL_H, _PANEL_W * 2 + 4, 3), PLACEHOLDER_BG, dtype=np.uint8)
    canvas[:_HEADER_H, :, :] = (24, 28, 34)
    cv2.putText(
        canvas, "intake_triage_view", (12, _HEADER_H - 10),
        _TEXT_FONT, 0.55, PLACEHOLDER_FG, 1, cv2.LINE_AA,
    )

    # Left half: project + groups.
    left_lines: list[str] = []
    if not project:
        left_lines.append("(no active project)")
    else:
        left_lines.append(f"project          {project.get('slug', '-')}")
        left_lines.append(f"target_promoted  {project.get('target_promoted', 0)}")
        left_lines.append(f"promoted         {project.get('promoted', 0)}")
        left_lines.append(f"gap              {project.get('gap', 0)}")
        left_lines.append(f"in_flight        {project.get('in_flight', 0)}")
        left_lines.append(f"forecast_ok      {project.get('forecast_ok', False)}")
        left_lines.append(f"count_satisfied  {project.get('count_satisfied', False)}")
        left_lines.append(f"fully_satisfied  {project.get('fully_satisfied', False)}")
        left_lines.append("")
        left_lines.append("Groups:")
        for g in (targets.get("groups") or [])[:8]:
            left_lines.append(
                f"  {g.get('slug', '?'):<5} "
                f"{g.get('promoted', 0):>3}/{g.get('target_promoted', 0):<3}  "
                f"gap={g.get('gap', 0):<3}  "
                f"stable={g.get('stable_cards', 0):<2}  "
                f"complete={g.get('complete_cards', 0):<2}"
            )
    _draw_lines(canvas[:, :_PANEL_W, :], left_lines, y0=_HEADER_H + 28)

    # Right half: task + card + amood.
    right_lines: list[str] = []
    if intake.get("active_task_slug"):
        right_lines.append(f"task            {intake['active_task_slug']}")
        right_lines.append(f"pending         {intake.get('pending_count', 0)}")
        right_lines.append(f"soft_accepted   {intake.get('soft_accepted_count', 0)}")
        right_lines.append(f"promoted        {intake.get('promoted_count', 0)}")
        right_lines.append(f"rejected        {intake.get('rejected_count', 0)}")
        right_lines.append(f"queue_depth     {intake.get('queue_depth', 0)}")
        right_lines.append("")
    else:
        right_lines.append("(no active task)")
        right_lines.append("")

    if active_card:
        right_lines.append(f"card            {active_card.get('slug', '-')}")
        right_lines.append(f"target_promoted {active_card.get('target_promoted', 0)}")
        right_lines.append(f"promoted        {active_card.get('promoted', 0)}")
        right_lines.append(f"stable          {active_card.get('stable', False)}")
        right_lines.append(f"complete        {active_card.get('complete', False)}")
        right_lines.append("")
    else:
        right_lines.append("(no active card)")
        right_lines.append("")

    if amood and amood.get("active_batch_slug"):
        right_lines.append(f"amood batch     {amood['active_batch_slug']}")
        right_lines.append(f"  tier          {amood.get('tier', '-')}")
        right_lines.append(f"  stable_cards  {amood.get('stable_cards', 0)}")
        right_lines.append(f"  unstable      {amood.get('unstable_cards', 0)}")
    else:
        right_lines.append("(no AMood batch active)")

    _draw_lines(canvas[:, _PANEL_W + 4 :, :], right_lines, y0=_HEADER_H + 28)
    return canvas


def render_library_card_with_pose(
    card: dict[str, Any] | None,
    pose_path: str | Path | None,
    library_root: Path | str,
) -> np.ndarray:
    """Side-by-side card label panel + pose-guide PNG preview.

    `card` is the dict from state.library.targets.active_card or a
    library_entries row; `pose_path` is the resolved PNG path (absolute
    or relative to library_root).
    """
    if card is None:
        return _placeholder(
            _PANEL_W * 2 + 4, _PANEL_H + _HEADER_H,
            "library_card_with_pose: no card selected",
        )

    label_lines: list[str] = []
    label_lines.append(f"card_slug        {card.get('slug') or card.get('card_slug') or '-'}")
    label_lines.append(f"card_id          {card.get('card_id') or card.get('id') or '-'}")
    label_lines.append(f"target_promoted  {card.get('target_promoted', 0)}")
    label_lines.append(f"stability_target {card.get('stability_target', 0)}")
    label_lines.append(f"promoted         {card.get('promoted', 0)}")
    label_lines.append(f"stable           {card.get('stable', False)}")
    label_lines.append(f"complete         {card.get('complete', False)}")

    label_panel = np.full((_PANEL_H, _PANEL_W, 3), PLACEHOLDER_BG, dtype=np.uint8)
    _draw_lines(label_panel, label_lines, y0=28)

    pose_resolved = _resolve(str(pose_path) if pose_path else None, library_root)
    pose_panel = _read_or_placeholder(
        pose_resolved, width=_PANEL_W, height=_PANEL_H,
        label="pose_guide.png",
    )

    middle = np.full((_PANEL_H, 4, 3), PLACEHOLDER_BG, dtype=np.uint8)
    body = np.hstack([pose_panel, middle, label_panel])
    header = _label_strip(
        _PANEL_W * 2 + 4, _HEADER_H,
        f"library_card_with_pose · {card.get('slug') or card.get('card_slug') or '-'}",
    )
    return np.vstack([header, body])
