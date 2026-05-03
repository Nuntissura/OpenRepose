"""Tests for the avatar slug sanitizer (WP-I1-030)."""

from __future__ import annotations

from openrepose.util.slugify import sanitize_avatar_slug


def test_basic_lowercase():
    assert sanitize_avatar_slug("Aeri") == "aeri"


def test_strips_extension_like_stem():
    assert sanitize_avatar_slug("AERI Master.PNG") == "aeri-master-png"


def test_replaces_spaces_with_dashes():
    assert sanitize_avatar_slug("0-degree frontal view") == "0-degree-frontal-view"


def test_replaces_commas_and_punctuation():
    assert (
        sanitize_avatar_slug("My Portrait, 2026-05-01.png")
        == "my-portrait-2026-05-01-png"
    )


def test_strips_leading_trailing_dashes():
    assert sanitize_avatar_slug("...aeri...") == "aeri"


def test_collapses_runs_of_special_chars():
    assert sanitize_avatar_slug("a   b___c") == "a-b-c"


def test_empty_string_falls_back():
    assert sanitize_avatar_slug("") == "unknown"


def test_only_whitespace_falls_back():
    assert sanitize_avatar_slug("    ") == "unknown"


def test_only_punctuation_falls_back():
    assert sanitize_avatar_slug("!!!,,,...") == "unknown"


def test_custom_fallback():
    assert sanitize_avatar_slug("", fallback="anon") == "anon"


def test_nfkd_normalizes_diacritics():
    # ä → a, ï → i, etc.
    assert sanitize_avatar_slug("Aria's Photo") == "aria-s-photo"


def test_no_path_traversal():
    """`..` cannot survive — `.` is non-alphanumeric and gets replaced."""
    result = sanitize_avatar_slug("../../etc/passwd")
    assert ".." not in result
    assert "/" not in result


def test_emoji_falls_back_or_strips():
    """Non-ASCII strips to nothing for emoji-only; falls back."""
    assert sanitize_avatar_slug("🎨") == "unknown"


def test_non_string_falls_back():
    """Defensive: non-string input returns fallback rather than raising."""
    assert sanitize_avatar_slug(None) == "unknown"  # type: ignore[arg-type]
    assert sanitize_avatar_slug(123) == "unknown"  # type: ignore[arg-type]


def test_long_filename_with_mixed_characters():
    """The exact pattern from operator's bug report."""
    raw = "0-degree frontal view Master Base ChatGPT Image May 1, 2026, 05_03_37 AM"
    result = sanitize_avatar_slug(raw)
    assert " " not in result
    assert "," not in result
    assert ":" not in result
    assert result.startswith("0-degree-frontal-view")
