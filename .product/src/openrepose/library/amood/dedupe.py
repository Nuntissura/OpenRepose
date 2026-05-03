"""Anti-repetition service (WP-I3-006).

Spec: `.gov/spec/openrepose_amood_v0_1.md` "Anti-Repetition Service".

Wraps the `library.dedupe_check` SQL function from migration 003. The
function splits both signatures on '|', counts shared axes (8 by AMood
blueprint), restricts to status IN ('soft_accepted','promoted'), and
returns rows with overlap_count >= threshold.

Dedupe signature canonical shape (8 axes):

    <explicit_family>|<pose_family>|<orientation>|<wardrobe_state>|
    <support_object>|<setting_family>|<camera_family>|<palette_family>

Empty axis values ('') do not count as overlap (so a card with only
explicit_family set never collides with another card that has only
explicit_family set unless the explicit_family value matches).

Citation: AMOOD-001 (severity: warn). Threshold default = 6;
project-overridable via `library_batches.dedupe_threshold` (range 4..8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    import psycopg


DEDUPE_AXIS_COUNT = 8
DEFAULT_DEDUPE_THRESHOLD = 6


class DedupeInputError(ValueError):
    """Raised when a dedupe input is malformed."""


@dataclass(frozen=True)
class DedupeCandidate:
    candidate_id: UUID
    candidate_slug: str
    overlap_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": str(self.candidate_id),
            "candidate_slug": self.candidate_slug,
            "overlap_count": self.overlap_count,
        }


@dataclass(frozen=True)
class DedupeMatch:
    """Result of `check_card_pre_insert`. Empty `candidates` means no
    overlap at or above the threshold; the card is safe to insert."""
    threshold: int
    candidates: tuple[DedupeCandidate, ...]

    @property
    def has_overlap(self) -> bool:
        return len(self.candidates) > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "candidates": [c.to_dict() for c in self.candidates],
            "has_overlap": self.has_overlap,
        }


def compose_signature(
    *,
    explicit_family: str = "",
    pose_family: str = "",
    orientation: str = "",
    wardrobe_state: str = "",
    support_object: str = "",
    setting_family: str = "",
    camera_family: str = "",
    palette_family: str = "",
) -> str:
    """Build the canonical 8-axis dedupe signature.

    Empty axes serialize as '' between the pipes; the SQL function treats
    those as non-matching (a row with all axes blank cannot collide).

    Pipe characters in axis values are forbidden because they would
    collide with the delimiter; we replace them with `/` and document
    the substitution in code comments rather than rejecting outright,
    so an LLM agent never gets a hard failure on pipe-containing free
    text (which is rare but real, e.g. "robe-open|chest-out").
    """
    axes = (
        explicit_family,
        pose_family,
        orientation,
        wardrobe_state,
        support_object,
        setting_family,
        camera_family,
        palette_family,
    )
    return "|".join(_safe_axis(a) for a in axes)


def _safe_axis(value: str | None) -> str:
    if value is None:
        return ""
    # Pipe collides with the delimiter; substitute with '/' to preserve
    # round-trip without raising on operator free text.
    return value.replace("|", "/")


def check_card_pre_insert(
    conn: psycopg.Connection[object],
    *,
    project_id: UUID | str,
    dedupe_signature: str,
    threshold: int = DEFAULT_DEDUPE_THRESHOLD,
) -> DedupeMatch:
    """Call `library.dedupe_check` for a candidate signature.

    `library_create_card` calls this before INSERT so the AMOOD-001
    warning is surfaced with the matching card_id + overlap_count
    BEFORE the new dedupe_signature is committed (cause-and-effect
    visibility for the LLM caller).
    """
    if dedupe_signature is None or dedupe_signature == "":
        raise DedupeInputError("dedupe_signature must be non-empty")
    if dedupe_signature.count("|") != DEDUPE_AXIS_COUNT - 1:
        raise DedupeInputError(
            f"dedupe_signature must have exactly {DEDUPE_AXIS_COUNT} pipe-delimited axes; "
            f"got {dedupe_signature.count('|') + 1}"
        )
    if not 1 <= int(threshold) <= DEDUPE_AXIS_COUNT:
        raise DedupeInputError(
            f"threshold must be 1..{DEDUPE_AXIS_COUNT}; got {threshold}"
        )

    with conn.cursor() as cur:
        cur.execute(
            "SELECT candidate_id, candidate_slug, overlap_count "
            "FROM library.dedupe_check(%s, %s, %s) "
            "ORDER BY overlap_count DESC, candidate_id ASC",
            (str(project_id), dedupe_signature, int(threshold)),
        )
        rows = cur.fetchall()

    candidates = tuple(
        DedupeCandidate(
            candidate_id=row[0],
            candidate_slug=row[1] or "",
            overlap_count=int(row[2]),
        )
        for row in rows
    )
    return DedupeMatch(threshold=int(threshold), candidates=candidates)
