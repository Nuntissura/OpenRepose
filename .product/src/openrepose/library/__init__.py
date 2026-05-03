"""OpenRepose Library data layer (Feature 3, WP-I2-003).

Spec: `.gov/spec/openrepose_library_v0_1.md` Database Schema + Tag System
+ Storage Layout. CRUD on `library_entries` and the M-to-N `entry_tags`
relation, the smart-tag extractor, and the filesystem layout under the
operator's library root.

LLM commands wrap these primitives in WP-I2-004; ComfyUI bridge in
WP-I2-005; Library tab GUI in WP-I2-006.
"""

from .entries import (
    LibraryEntry,
    LibraryEntryError,
    LibraryEntryLockedError,
    create_entry,
    delete_entry,
    get_entry,
    list_entries,
    update_entry,
)
from .smart_tags import AUTO_TAG_PREFIX, extract_smart_tags
from .storage import EntryFiles, ensure_entry_dir, write_entry_files
from .tags import (
    LibraryTagError,
    add_tags,
    list_entry_tags,
    remove_tags,
    set_entry_tags,
)

__all__ = [
    "AUTO_TAG_PREFIX",
    "EntryFiles",
    "LibraryEntry",
    "LibraryEntryError",
    "LibraryEntryLockedError",
    "LibraryTagError",
    "add_tags",
    "create_entry",
    "delete_entry",
    "ensure_entry_dir",
    "extract_smart_tags",
    "get_entry",
    "list_entries",
    "list_entry_tags",
    "remove_tags",
    "set_entry_tags",
    "update_entry",
    "write_entry_files",
]
