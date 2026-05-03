"""Help tab: in-app manual browser (WP-I1-035).

Reads Markdown topic files from `.gov/doc/manual/` (resolved relative to the
repo root via `__file__` walking) and renders them via QTextBrowser. Left
pane shows the file index; right pane shows the selected topic.

Operator-facing only. No LLM commands. No focus-stealing API calls.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


def _find_manual_root() -> Path | None:
    """Walk up from this file's location to find `.gov/doc/manual/`.

    Returns the resolved manual root or None if not found (e.g., running
    from a packaged installer without source). Caller falls back to a
    placeholder message in that case.
    """
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / ".gov" / "doc" / "manual"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


class HelpPane(QWidget):
    """Manual browser: list of topics on the left, rendered Markdown on the right."""

    INDEX_DEFAULT = "index.md"

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._manual_root = _find_manual_root()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        self._topic_list = QListWidget()
        self._topic_list.itemClicked.connect(self._on_topic_clicked)
        splitter.addWidget(self._topic_list)

        self._viewer = QTextBrowser()
        self._viewer.setOpenExternalLinks(False)
        # WP-I1-035 fix: handle internal Markdown links ourselves so clicking
        # `[Getting started](getting-started.md)` inside index.md actually
        # switches to that topic instead of doing nothing.
        self._viewer.setOpenLinks(False)
        self._viewer.anchorClicked.connect(self._on_anchor_clicked)
        self._viewer.setStyleSheet(
            "QTextBrowser { padding: 12px; font-family: Segoe UI, sans-serif; }"
        )
        splitter.addWidget(self._viewer)
        splitter.setSizes([180, 500])

        self._populate_topic_list()
        self._load_default_topic()

    def _populate_topic_list(self) -> None:
        self._topic_list.clear()
        if self._manual_root is None:
            item = QListWidgetItem("(manual not found in this build)")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._topic_list.addItem(item)
            return
        # Always lead with index.md if present, then alphabetical others.
        files = sorted(self._manual_root.glob("*.md"))
        index_first = sorted(files, key=lambda p: (p.name != self.INDEX_DEFAULT, p.name))
        for p in index_first:
            item = QListWidgetItem(p.stem.replace("-", " "))
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            self._topic_list.addItem(item)

    def _load_default_topic(self) -> None:
        if self._manual_root is None:
            self._viewer.setMarkdown(
                "# Manual not bundled\n\n"
                "OpenRepose's manual lives in `.gov/doc/manual/` in the source "
                "tree. This installation appears to be a packaged build without "
                "the source files. Refer to the GitHub repo for full docs."
            )
            return
        index_path = self._manual_root / self.INDEX_DEFAULT
        if index_path.exists():
            self._load_topic(index_path)
        elif self._topic_list.count() > 0:
            first = self._topic_list.item(0)
            self._load_topic(Path(first.data(Qt.ItemDataRole.UserRole)))

    def _on_topic_clicked(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        self._load_topic(Path(path_str))

    def _load_topic(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            self._viewer.setMarkdown(f"# Cannot load topic\n\n`{path}`: {e}")
            return
        self._viewer.setMarkdown(text)
        # Sync the topic-list selection with the loaded topic so the left
        # column highlights what's on the right.
        for i in range(self._topic_list.count()):
            item = self._topic_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == str(path):
                self._topic_list.blockSignals(True)
                self._topic_list.setCurrentRow(i)
                self._topic_list.blockSignals(False)
                break

    def _on_anchor_clicked(self, url) -> None:  # noqa: ANN001
        """WP-I1-035 fix: a click on a Markdown link inside the rendered
        topic loads the linked file when it's a relative .md path under
        the manual root. External / non-md links are ignored (no shell
        out — the manual is intentionally a closed reference)."""
        if self._manual_root is None:
            return
        href = url.toString()
        if not href or "://" in href:
            # External link; ignore (no operator-confusing shell-out).
            return
        # Strip any leading "./" and treat as relative to the manual root.
        if href.startswith("./"):
            href = href[2:]
        if not href.endswith(".md"):
            return
        target = (self._manual_root / href).resolve()
        try:
            target.relative_to(self._manual_root.resolve())
        except ValueError:
            # Path traversal attempt (`../../etc/passwd.md`); refuse.
            return
        if not target.exists():
            return
        self._load_topic(target)
