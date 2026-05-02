"""Help tab: keyboard shortcuts, command schema reference, links to spec."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


HELP_TEXT = """OpenRepose v0.1 Quick Reference
================================

Yaw terminology (locked):
  0                  frontal
  her-left N         avatar rotates to her own left; her right side faces camera;
                     her nose ends up at the right edge of the frame
  her-right N        avatar rotates to her own right; her left side faces camera;
                     her nose ends up at the left edge of the frame
  Forbidden phrases: image-left, image-right, viewer-left, viewer-right,
                     left view, right view

Keyboard shortcuts (v0.1):
  Ctrl+O             Open portrait
  Ctrl+E             Export single
  Ctrl+Shift+E       Export 13-angle batch
  Ctrl+S             Save settings (snapshot of options to .runtime/state.json)
  Ctrl+Q             Quit (close to tray if tray enabled, else exit)
  Esc                Cancel current operation (where applicable)

LLM control surface:
  HTTP localhost:    POST http://127.0.0.1:8765/command (when --http-port set)
                     GET  http://127.0.0.1:8765/state
                     GET  http://127.0.0.1:8765/log?lines=200
  File-watch inbox:  drop *.json files in outputs/.runtime/inbox/ (when enabled)

Snapshot targets (LLM-only; never invoked by GUI clicks):
  3d_viewport, openpose_viewport, inspector_pane, log_pane, options_pane,
  status_bar, toolbar, full_window

Operator experience guarantees:
  - The app NEVER raises its own window, takes focus, captures keyboard,
    or pops modals from LLM commands.
  - Operator window stack is never modified.
  - All operator-facing changes (rig fit, yaw set, exports) update silently;
    you see them if you look. The window does not demand attention.

Spec and rules:
  .gov/spec/openrepose_v0_1.md      application contract
  .gov/AGENTS.md                    agent instructions, headless rule, checklist
  .gov/CODEX.md                     compact project codex
  .gov/topology.yaml                machine-readable topology
  .gov/workflow/README.md           workflow rules
"""


class HelpPane(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(HELP_TEXT)
        text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(text)
