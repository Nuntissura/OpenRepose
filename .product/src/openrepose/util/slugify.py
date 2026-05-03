"""Avatar slug sanitization (WP-I1-030).

When the operator opens a portrait via File→Open without setting an
explicit avatar slug, the GUI falls back to the file's stem. Operator
filenames routinely contain spaces, commas, mixed case, and the resulting
folder names under `outputs/` were ugly. This helper normalizes those
strings to safe slugs (`a-z0-9-`).

Pure function. No side effects. Importable without Qt / mediapipe.
"""

from __future__ import annotations

import re
import unicodedata


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def sanitize_avatar_slug(text: str, fallback: str = "unknown") -> str:
    """Normalize an arbitrary string to a `[a-z0-9-]+` slug.

    Pipeline: NFKD normalize → ASCII strip → lowercase → replace runs of
    non-alphanumerics with `-` → trim leading/trailing `-`. Empty result
    falls back to `fallback`.

    Examples:
        "My Portrait, 2026-05-01.png" → "my-portrait-2026-05-01"
        "AERI Master.PNG"             → "aeri-master"
        "0-degree frontal view"       → "0-degree-frontal-view"
        ""                            → "unknown"
        "   ..."                      → "unknown"
        "Ärïá's Photo!"               → "aria-s-photo"

    Path-traversal-safe: `..` cannot appear in the result because `.` is
    in the non-alphanumeric class and gets replaced.
    """
    if not isinstance(text, str):
        return fallback
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", errors="ignore").decode("ascii")
    lowered = ascii_only.lower()
    slug = _SLUG_RE.sub("-", lowered).strip("-")
    return slug or fallback
