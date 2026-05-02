"""Tool-style dark theme for OpenRepose. Tight spacing, monospace logs, no
Material card shadows or wizard chrome."""

from __future__ import annotations

DARK_QSS = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Segoe UI", "Helvetica Neue", "Helvetica", "Arial", sans-serif;
    font-size: 11px;
}
QToolBar {
    background-color: #252526;
    border-bottom: 1px solid #333;
    spacing: 4px;
    padding: 3px;
}
QToolBar QToolButton, QToolBar QPushButton {
    background-color: #2d2d30;
    border: 1px solid #3f3f46;
    color: #d4d4d4;
    padding: 4px 10px;
    border-radius: 0;
}
QToolBar QToolButton:hover, QToolBar QPushButton:hover {
    background-color: #3e3e42;
}
QStatusBar {
    background-color: #007acc;
    color: white;
    font-family: "Consolas", "Menlo", "Courier New", monospace;
    font-size: 11px;
}
QTabWidget::pane {
    border: 1px solid #333;
    background-color: #252526;
    top: -1px;
}
QTabBar::tab {
    background-color: #2d2d30;
    color: #d4d4d4;
    padding: 6px 14px;
    border: 1px solid #333;
    border-bottom: none;
}
QTabBar::tab:selected {
    background-color: #1e1e1e;
    border-bottom: 1px solid #1e1e1e;
}
QTabBar::tab:hover {
    background-color: #3e3e42;
}
QPlainTextEdit, QTextEdit {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Consolas", "Menlo", "Courier New", monospace;
    font-size: 11px;
    border: 1px solid #333;
}
QLabel#inspector-key {
    color: #9cdcfe;
    font-family: "Consolas", "Menlo", "Courier New", monospace;
}
QLabel#inspector-value {
    color: #d4d4d4;
    font-family: "Consolas", "Menlo", "Courier New", monospace;
}
QSlider::groove:horizontal {
    border: 1px solid #3f3f46;
    height: 6px;
    background: #2d2d30;
}
QSlider::handle:horizontal {
    background: #007acc;
    border: 1px solid #007acc;
    width: 14px;
    margin: -5px 0;
}
QComboBox {
    background-color: #2d2d30;
    color: #d4d4d4;
    border: 1px solid #3f3f46;
    padding: 3px 6px;
}
QPushButton {
    background-color: #2d2d30;
    color: #d4d4d4;
    border: 1px solid #3f3f46;
    padding: 5px 12px;
}
QPushButton:hover {
    background-color: #3e3e42;
}
QPushButton:pressed {
    background-color: #007acc;
    color: white;
}
QPushButton:disabled {
    color: #6a6a6a;
}
QCheckBox, QRadioButton {
    color: #d4d4d4;
}
QLineEdit {
    background-color: #2d2d30;
    color: #d4d4d4;
    border: 1px solid #3f3f46;
    padding: 3px;
}
QMenuBar {
    background-color: #252526;
    color: #d4d4d4;
}
QMenuBar::item:selected {
    background-color: #007acc;
}
"""
