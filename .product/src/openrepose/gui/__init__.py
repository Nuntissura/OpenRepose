"""OpenRepose desktop GUI (PySide6).

Spec: `.gov/spec/openrepose_v0_1.md` section "Feature 1 / GUI Requirements"
plus the project-wide "Headless LLM Operation Rule" — the GUI is operator-
facing only; LLM agents never interact with widgets directly. Widget grabs
expose the visual state to LLM agents through the snapshot subsystem.
"""

from .main_window import MainWindow  # noqa: F401
