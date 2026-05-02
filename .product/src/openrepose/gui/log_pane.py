"""Log pane: read-only monospace tail of the rolling log buffer.

Polls the Logger ring buffer at a fixed interval; never blocks the main
thread on file I/O."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..log import Logger, LogLevel


class LogPane(QWidget):
    POLL_MS = 500

    def __init__(self, logger: Logger) -> None:
        super().__init__()
        self._logger = logger
        self._level_filter: LogLevel | None = None
        self._last_seen_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("filter"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["ALL", "ERR", "WARN", "OK", "DBG"])
        self.filter_combo.setCurrentText("ALL")
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        bar.addWidget(self.filter_combo)
        bar.addStretch(1)
        self.btn_clear = QPushButton("Clear view")
        self.btn_clear.clicked.connect(self._clear_view)
        bar.addWidget(self.btn_clear)
        layout.addLayout(bar)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(5000)
        layout.addWidget(self.text, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _poll(self) -> None:
        lines = self._logger.tail(2000)
        if len(lines) == self._last_seen_count:
            return
        self._last_seen_count = len(lines)
        self.text.clear()
        for line in lines:
            if self._passes_filter(line):
                self.text.appendPlainText(line)

    def _passes_filter(self, line: str) -> bool:
        if self._level_filter is None:
            return True
        # Mechanical-format lines have the level token at fixed offset.
        # Quick contains check is enough for filtering display.
        return f"] {self._level_filter.value:<4s}" in line

    def _on_filter_changed(self, text: str) -> None:
        if text == "ALL":
            self._level_filter = None
        else:
            try:
                self._level_filter = LogLevel(text)
            except ValueError:
                self._level_filter = None
        self._last_seen_count = -1  # force redraw
        self._poll()

    def _clear_view(self) -> None:
        self.text.clear()
