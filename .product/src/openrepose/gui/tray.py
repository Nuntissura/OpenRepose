"""System-tray icon (operator-opt-in). Tray menu only: Show / Hide / Quit.
No notifications, no toasts, no sound — operator experience guarantees."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayIcon(QObject):
    show_window_requested = Signal()
    hide_window_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(self)
        # Use a default icon (empty pixmap is fine; the tray icon is mostly
        # a context-menu host for v0.1).
        self._tray.setIcon(QIcon())
        self._tray.setToolTip("OpenRepose")

        menu = QMenu()
        act_show = QAction("Show window", menu)
        act_show.triggered.connect(self.show_window_requested.emit)
        menu.addAction(act_show)

        act_hide = QAction("Hide window", menu)
        act_hide.triggered.connect(self.hide_window_requested.emit)
        menu.addAction(act_hide)

        menu.addSeparator()

        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(act_quit)

        self._tray.setContextMenu(menu)

    def start(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show()

    def stop(self) -> None:
        self._tray.hide()
