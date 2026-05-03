"""Library tab — search bar, entry list, side-by-side detail view, and
six sub-tabs (Tags / Prompts / Story / Notes / Workflow / Metadata).

Spec: `.gov/spec/openrepose_library_v0_1.md` Library Tab UI Requirements.

The pane reads / writes through the dispatcher: every operator action
maps to one of the WP-I2-004 commands so an LLM agent and the operator
share the same code path. No `raise_/activateWindow/showNormal` from any
GUI callback (Headless Verification Checklist).

Entries are loaded by `library_search`. An empty search bar shows the
"type a query" placeholder; pressing Enter (or Refresh) issues the
search. Selecting an entry calls `get_library_entry` with all
sub-records included; the detail view renders + the sub-tab editors
populate. Lock indicator: entries whose `locked_by` field is set + does
not equal the operator's slug appear greyed with a "[locked by X]"
suffix.

Image previews are loaded from disk via `library_root` + the relative
paths the dispatcher returns. When a file is missing, the preview shows
a labeled placeholder.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ...app import App

PLACEHOLDER_PIXMAP_BG = "#1f2933"


class LibraryPane(QWidget):
    """Top-level Library tab. Hosted by `MainWindow` alongside Inspector
    / Tools / Options / Log / Help."""

    def __init__(self, app: "App") -> None:
        super().__init__()
        self._app = app
        self._current_entry: dict[str, Any] | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        # --- toolbar row ---
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(
            "Search: title fuzzy match (try 'inimate'); tags; prompts FTS"
        )
        self._search_edit.returnPressed.connect(self._on_search)
        bar.addWidget(self._search_edit, 1)
        self._btn_search = QPushButton("Search")
        self._btn_search.clicked.connect(self._on_search)
        bar.addWidget(self._btn_search)
        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.clicked.connect(self._on_refresh)
        bar.addWidget(self._btn_refresh)
        self._btn_import = QPushButton("Import OpenPose...")
        self._btn_import.clicked.connect(self._on_import)
        bar.addWidget(self._btn_import)
        outer.addLayout(bar)

        # --- splitter: list (1/3) + detail (2/3) ---
        split = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(split, 1)

        self._list = QListWidget()
        self._list.itemSelectionChanged.connect(self._on_select)
        split.addWidget(self._list)

        self._detail = LibraryEntryDetail()
        self._detail.tags_changed.connect(self._on_tags_changed)
        self._detail.prompt_added.connect(self._on_prompt_added)
        self._detail.delete_clicked.connect(self._on_delete)
        split.addWidget(self._detail)
        split.setSizes([320, 640])

        # --- status row ---
        status = QHBoxLayout()
        self._status_label = QLabel("Library: idle")
        self._status_label.setStyleSheet("color: #889; font-style: italic;")
        status.addWidget(self._status_label)
        status.addStretch(1)
        outer.addLayout(status)

    # --- dispatcher helpers ----------------------------------------------

    def _dispatch(self, command: str, **kw: Any) -> dict[str, Any]:
        """Issue a command through the existing dispatcher. Returns the
        payload on success, an empty dict on error (status reflected in
        the status label so the operator can see what happened)."""
        result = self._app.handle_command({"command": command, **kw})
        if result.status != "ok":
            self._status_label.setText(
                f"Library error: {result.payload.get('reason', 'unknown')}"
            )
            return {}
        self._status_label.setText(f"Library: {command} ok")
        return result.payload

    # --- callbacks --------------------------------------------------------

    def _on_search(self) -> None:
        query = self._search_edit.text().strip()
        if not query:
            self._status_label.setText("Library: type a search query")
            return
        payload = self._dispatch("library_search", query=query, limit=50)
        if not payload:
            return
        self._populate_list(payload.get("results") or [])

    def _on_refresh(self) -> None:
        # Re-run the last search if any.
        last = self._app.state.library.get("last_search_query")
        if last:
            self._search_edit.setText(last)
            self._on_search()
        else:
            self._status_label.setText("Library: nothing to refresh — type a query first")

    def _on_import(self) -> None:
        """Operator-triggered: pick an OpenPose JSON path; create a new
        entry referencing it. The actual register happens through the
        dispatcher so the LLM-side path is identical."""
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Select OpenPose JSON to import",
            "",
            "OpenPose JSON (*.json);;All files (*.*)",
        )
        if not chosen:
            return
        slug = (
            self._app.settings.effective_operator_slug()
            if self._app.settings is not None
            else "default"
        )
        payload = self._dispatch(
            "register_library_entry",
            avatar_slug=slug,
            title=Path(chosen).stem,
            openpose_json_path=chosen,
        )
        if payload:
            self._on_refresh()

    def _on_select(self) -> None:
        items = self._list.selectedItems()
        if not items:
            self._detail.clear()
            self._current_entry = None
            return
        entry_id = items[0].data(Qt.ItemDataRole.UserRole)
        payload = self._dispatch(
            "get_library_entry",
            entry_id=entry_id,
            include=["tags", "prompts", "story_beats", "notes", "workflow", "metadata"],
        )
        if not payload:
            return
        self._current_entry = payload
        library_root = (
            Path(self._app.settings.resolved_library_root())
            if self._app.settings is not None
            else Path("outputs/library")
        )
        self._detail.populate(payload, library_root=library_root)

    def _on_tags_changed(self, tags: list[str], replace: bool) -> None:
        if self._current_entry is None:
            return
        payload = self._dispatch(
            "set_library_tags",
            entry_id=self._current_entry["id"],
            tags=tags,
            replace=replace,
        )
        if payload:
            self._detail.set_tags(payload.get("tags") or [])

    def _on_prompt_added(self, positive: str, negative: str) -> None:
        if self._current_entry is None:
            return
        # Prompts are immutable revisions on the spec — `update_library_entry`
        # does not edit them; the spec ships per-entry prompt history. We
        # round-trip via register_library_entry would create a new entry,
        # so use the dispatcher's get/update path with a metadata-only
        # patch + add a prompt sub-record by re-fetching after dispatching
        # a `register` style call. For v0.1 we surface this as "edit
        # prompts via API" and just refetch.
        # TODO(WP-I2-004 follow-up): a dedicated `add_prompt_revision`
        # command would be cleaner; for now operators add through the
        # ComfyUI bridge / register_library_entry flow.
        self._status_label.setText(
            "Library: prompt-add coming in a follow-up WP; use ComfyUI bridge for now"
        )

    def _on_delete(self) -> None:
        if self._current_entry is None:
            return
        eid = self._current_entry["id"]
        payload = self._dispatch("delete_library_entry", entry_id=eid)
        if payload.get("deleted"):
            self._current_entry = None
            self._detail.clear()
            self._on_refresh()

    # --- list rendering ---------------------------------------------------

    def _populate_list(self, results: list[dict[str, Any]]) -> None:
        self._list.clear()
        op_slug = (
            self._app.settings.effective_operator_slug()
            if self._app.settings is not None
            else ""
        )
        for r in results:
            title = r.get("title") or "(untitled)"
            avatar = r.get("avatar_slug") or "—"
            yaw = r.get("yaw_bin") or "—"
            tags = r.get("top_tags") or []
            label = f"{title}  [{avatar} · {yaw}]"
            if tags:
                label += "  " + " ".join(f"·{t}" for t in tags[:3])
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, r.get("entry_id"))
            self._list.addItem(item)

        # Lock indicator pass — colors entries whose detail says they're
        # held by another operator. Cheap: only fetched when shown.
        for r in results:
            locked_by = r.get("locked_by")
            if locked_by and locked_by != op_slug:
                idx = results.index(r)
                self._list.item(idx).setForeground(Qt.GlobalColor.darkGray)
                self._list.item(idx).setToolTip(f"Locked by {locked_by}")

        self._status_label.setText(
            f"Library: {len(results)} result{'s' if len(results) != 1 else ''}"
        )

    # --- snapshot helpers (used by WP-I2-007) ----------------------------

    def detail_widget(self) -> "LibraryEntryDetail":
        return self._detail


# ---------------------------------------------------------------------------
# Detail pane (right side)
# ---------------------------------------------------------------------------


class LibraryEntryDetail(QWidget):
    """Right-pane detail: side-by-side OpenPose preview + reference image
    over a 6-tab editor (Tags / Prompts / Story / Notes / Workflow /
    Metadata)."""

    tags_changed = Signal(list, bool)  # (tags, replace)
    prompt_added = Signal(str, str)  # (positive, negative)
    delete_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        # Header strip with title + delete button.
        head = QHBoxLayout()
        self._title_label = QLabel("(no entry selected)")
        f = QFont()
        f.setBold(True)
        self._title_label.setFont(f)
        head.addWidget(self._title_label, 1)
        self._btn_delete = QPushButton("Delete")
        self._btn_delete.clicked.connect(self.delete_clicked.emit)
        head.addWidget(self._btn_delete)
        outer.addLayout(head)

        # Side-by-side previews (OpenPose + reference / generated).
        preview_row = QHBoxLayout()
        self._openpose_preview = ImagePreview("openpose.png")
        self._image_preview = ImagePreview("generated.png / portrait.png")
        preview_row.addWidget(self._openpose_preview)
        preview_row.addWidget(self._image_preview)
        outer.addLayout(preview_row, 2)

        # Sub-tabs.
        self._tabs = QTabWidget()
        self._tags_tab = TagsTab()
        self._tags_tab.tags_committed.connect(self.tags_changed.emit)
        self._prompts_tab = PromptsTab()
        self._prompts_tab.add_clicked.connect(self.prompt_added.emit)
        self._story_tab = TextListTab(label="Story beat (one per box, newest first)")
        self._notes_tab = TextListTab(label="Operator notes (one per box, newest first)")
        self._workflow_tab = JsonViewerTab()
        self._metadata_tab = JsonViewerTab()
        self._tabs.addTab(self._tags_tab, "Tags")
        self._tabs.addTab(self._prompts_tab, "Prompts")
        self._tabs.addTab(self._story_tab, "Story")
        self._tabs.addTab(self._notes_tab, "Notes")
        self._tabs.addTab(self._workflow_tab, "Workflow")
        self._tabs.addTab(self._metadata_tab, "Metadata")
        outer.addWidget(self._tabs, 3)

        self.clear()

    # --- public ----------------------------------------------------------

    def clear(self) -> None:
        self._title_label.setText("(no entry selected)")
        self._openpose_preview.show_placeholder()
        self._image_preview.show_placeholder()
        self._tags_tab.set_tags([])
        self._prompts_tab.show_revisions([])
        self._story_tab.show_records([])
        self._notes_tab.show_records([])
        self._workflow_tab.show_obj({})
        self._metadata_tab.show_obj({})
        self._btn_delete.setEnabled(False)

    def populate(self, entry: dict[str, Any], *, library_root: Path) -> None:
        title = entry.get("title") or "(untitled)"
        avatar = entry.get("avatar_slug") or "—"
        yaw = entry.get("yaw_bin") or "—"
        locked = entry.get("locked_by")
        suffix = f"  [locked by {locked}]" if locked else ""
        self._title_label.setText(f"{title}  ·  {avatar}  ·  {yaw}{suffix}")
        self._btn_delete.setEnabled(True)

        # Image previews.
        self._openpose_preview.show_path(_resolve(entry.get("openpose_png_path"), library_root))
        # Prefer generated_image; fall back to portrait.
        ref = entry.get("generated_image_path") or entry.get("portrait_path")
        self._image_preview.show_path(_resolve(ref, library_root))

        self._tags_tab.set_tags(entry.get("tags") or [])
        self._prompts_tab.show_revisions(entry.get("prompts") or [])
        self._story_tab.show_records(entry.get("story_beats") or [])
        self._notes_tab.show_records(entry.get("notes") or [])
        self._workflow_tab.show_obj(entry.get("comfyui_workflow") or {})
        self._metadata_tab.show_obj(entry.get("metadata") or {})

    def set_tags(self, tags: list[str]) -> None:
        self._tags_tab.set_tags(tags)


# ---------------------------------------------------------------------------
# Sub-widgets
# ---------------------------------------------------------------------------


class ImagePreview(QWidget):
    def __init__(self, label: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._cap = QLabel(label)
        self._cap.setStyleSheet("color: #889; font-size: 11px;")
        self._cap.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._cap)
        self._img = QLabel()
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setMinimumSize(180, 180)
        self._img.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._img.setStyleSheet(
            f"background: {PLACEHOLDER_PIXMAP_BG}; border: 1px solid #333;"
        )
        layout.addWidget(self._img, 1)
        self.show_placeholder()

    def show_placeholder(self) -> None:
        self._img.setText("(no image)")
        self._img.setPixmap(QPixmap())

    def show_path(self, path: Path | None) -> None:
        if path is None or not path.exists():
            self.show_placeholder()
            return
        pix = QPixmap(str(path))
        if pix.isNull():
            self._img.setText(f"(failed to read {path.name})")
            return
        self._img.setText("")
        scaled = pix.scaled(
            self._img.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._img.setPixmap(scaled)


class TagsTab(QWidget):
    """Tag editor. Operator types comma-separated tags; "Add" appends,
    "Replace" overwrites (preserves auto: tags via spec-default behavior
    in the dispatcher)."""

    tags_committed = Signal(list, bool)  # (tags, replace)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._chips = QLabel("(no tags)")
        self._chips.setWordWrap(True)
        self._chips.setStyleSheet("color: #cde;")
        layout.addWidget(self._chips)
        self._edit = QLineEdit()
        self._edit.setPlaceholderText(
            "comma-separated tags (e.g. mood:intimate, lighting:lowkey)"
        )
        layout.addWidget(self._edit)
        row = QHBoxLayout()
        self._btn_add = QPushButton("Add")
        self._btn_add.clicked.connect(lambda: self._commit(replace=False))
        self._btn_replace = QPushButton("Replace (keeps auto:)")
        self._btn_replace.clicked.connect(lambda: self._commit(replace=True))
        row.addWidget(self._btn_add)
        row.addWidget(self._btn_replace)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)

    def set_tags(self, tags: list[str]) -> None:
        if not tags:
            self._chips.setText("(no tags)")
        else:
            self._chips.setText(" · ".join(tags))

    def _commit(self, *, replace: bool) -> None:
        text = self._edit.text().strip()
        if not text:
            return
        tags = [t.strip() for t in text.split(",") if t.strip()]
        self.tags_committed.emit(tags, replace)
        self._edit.clear()


class PromptsTab(QWidget):
    add_clicked = Signal(str, str)  # (positive, negative)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(QLabel("Positive prompt"))
        self._pos = QPlainTextEdit()
        self._pos.setMaximumBlockCount(0)
        layout.addWidget(self._pos, 1)
        layout.addWidget(QLabel("Negative prompt"))
        self._neg = QPlainTextEdit()
        layout.addWidget(self._neg, 1)
        row = QHBoxLayout()
        self._btn_add = QPushButton("Add revision (via dispatcher)")
        self._btn_add.clicked.connect(
            lambda: self.add_clicked.emit(self._pos.toPlainText(), self._neg.toPlainText())
        )
        row.addWidget(self._btn_add)
        row.addStretch(1)
        layout.addLayout(row)

    def show_revisions(self, revisions: list[dict[str, Any]]) -> None:
        if not revisions:
            self._pos.setPlainText("")
            self._neg.setPlainText("")
            return
        latest = revisions[0]
        self._pos.setPlainText(latest.get("positive") or "")
        self._neg.setPlainText(latest.get("negative") or "")


class TextListTab(QWidget):
    def __init__(self, *, label: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._label = QLabel(label)
        self._label.setStyleSheet("color: #889;")
        layout.addWidget(self._label)
        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        layout.addWidget(self._view, 1)

    def show_records(self, records: list[dict[str, Any]]) -> None:
        if not records:
            self._view.setPlainText("(no records yet — register via the bridge or dispatcher)")
            return
        chunks = []
        for r in records:
            ts = r.get("created_at") or "?"
            who = r.get("created_by") or "?"
            chunks.append(f"[{ts}] {who}\n{r.get('body', '')}\n")
        self._view.setPlainText("\n---\n\n".join(chunks))


class JsonViewerTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._view.setFont(font)
        layout.addWidget(self._view, 1)

    def show_obj(self, obj: Any) -> None:
        self._view.setPlainText(json.dumps(obj or {}, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _resolve(rel_or_abs: str | None, library_root: Path) -> Path | None:
    """Return an absolute path for an entry's stored relative path. None
    when the input is empty / unset."""
    if not rel_or_abs:
        return None
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p
    return library_root / p
