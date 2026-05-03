"""OpenRepose Library data layer (Feature 3, WP-I2-003).

Spec: `.gov/spec/openrepose_library_v0_1.md` Database Schema + Tag System
+ Storage Layout. CRUD on `library_entries` and the M-to-N `entry_tags`
relation, the smart-tag extractor, and the filesystem layout under the
operator's library root.

LLM commands wrap these primitives in WP-I2-004; ComfyUI bridge in
WP-I2-005; Library tab GUI in WP-I2-006. Intake & triage subpackage
extension lands in WP-I3-004 (`library/intake/`).
"""

from .citations import (
    Rule,
    RuleNotInRegistryError,
    all_rule_ids,
    format_citation,
    get_rule,
)
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
from .prompts import PromptRevision, add_prompt, latest_prompt, list_prompts
from .search import SearchResult, search
from .smart_tags import AUTO_TAG_PREFIX, extract_smart_tags
from .storage import EntryFiles, ensure_entry_dir, relative_to_root, write_entry_files
from .tags import (
    LibraryTagError,
    add_tags,
    list_entry_tags,
    remove_tags,
    set_entry_tags,
)
from .text_records import TextRecord, add_text_record, list_text_records

__all__ = [
    "AUTO_TAG_PREFIX",
    "EntryFiles",
    "LibraryEntry",
    "LibraryEntryError",
    "LibraryEntryLockedError",
    "LibraryTagError",
    "PromptRevision",
    "Rule",
    "RuleNotInRegistryError",
    "SearchResult",
    "TextRecord",
    "add_prompt",
    "add_tags",
    "add_text_record",
    "all_rule_ids",
    "create_entry",
    "delete_entry",
    "ensure_entry_dir",
    "extract_smart_tags",
    "format_citation",
    "get_entry",
    "get_rule",
    "latest_prompt",
    "list_entries",
    "list_entry_tags",
    "list_prompts",
    "list_text_records",
    "relative_to_root",
    "remove_tags",
    "search",
    "set_entry_tags",
    "update_entry",
    "write_entry_files",
]
