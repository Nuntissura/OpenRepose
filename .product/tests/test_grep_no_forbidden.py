"""Grep test: no forbidden yaw phrase appears anywhere in the product source.

The yaw terminology lock bans `image-left`, `image-right`, `viewer-left`,
`viewer-right`, `left view`, and `right view` in OpenRepose code, file
names, comments, and docs. This test enforces the rule on .product/src/.
"""

from __future__ import annotations

from pathlib import Path

FORBIDDEN = (
    "image-left",
    "image-right",
    "viewer-left",
    "viewer-right",
    "left view",
    "right view",
)

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "openrepose"

# Files that DEFINE or ENFORCE the rule (and therefore must contain the
# phrases as data) are allowlisted from the grep.
ALLOWLISTED_FILES = {
    "yaw_bin.py",  # canonical definition + parser that rejects them
    "help_pane.py",  # operator-facing help text DOCUMENTS the rule
}


def test_no_forbidden_phrases_in_source() -> None:
    offenders: list[str] = []
    for path in SRC_DIR.rglob("*.py"):
        if path.name in ALLOWLISTED_FILES:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN:
            if phrase in text:
                offenders.append(f"{path.relative_to(SRC_DIR)}: {phrase!r}")
    assert not offenders, "forbidden yaw phrases found:\n" + "\n".join(offenders)
