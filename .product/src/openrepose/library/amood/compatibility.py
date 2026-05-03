"""AMood compatibility check (WP-I3-006).

Spec: `.gov/spec/openrepose_amood_v0_1.md` "compatibility_check".

Encodes the AMood blueprint compatibility truth table at
`.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md`. Returns
`pass:bool, hard_rejects:[reason,...], warnings:[reason,...]` for an
input set of card axes (or for a card_id resolved upstream).

Hard-reject categories from the blueprint:
- camera-cant-see-target
- wardrobe-covers-target
- prop-blocks-target
- fantasy-set-camera-mismatch
- pose-implausible
- palette-collapse
- juvenile/coercive/voyeur-violation
- multi-trigger-conflict

Safety-boundary checks cite SAFE-001 / SAFE-002 / SAFE-003 (block
severity; no override path). Other hard-rejects cite the broader
AMOOD-004 rule (warn severity) since they describe a moodboard-design
problem rather than a safety boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Camera families that physically cannot see a frontal/lower-body trigger.
_REAR_ONLY_CAMERAS = frozenset({"behind", "rear-three-quarter", "over-back"})

# Wardrobe states that cover the trigger without revealing it.
_FULLY_COVERING_WARDROBE = frozenset(
    {
        "fully clothed",
        "buttoned-up",
        "high-neck",
        "covered",
        "concealing",
    }
)

# Support objects that cannot physically be present given the camera/pose.
# v0.1 limits this to a small explicit set; expansion lands when
# operators surface specific failure modes.
_INCOMPATIBLE_PROP_FAMILIES: dict[tuple[str, str], str] = {
    ("counter edge", "behind"):
        "support_object 'counter edge' is not visible from a behind camera",
    ("bed edge", "behind"):
        "support_object 'bed edge' is forward-of-body; behind camera misses the seam",
}

# Fantasy-mode + camera-family combinations that produce a "can't read
# the fantasy" output. Curated subset for v0.1.
_FANTASY_CAMERA_MISMATCH: dict[tuple[str, str], str] = {
    ("editorial porn",         "raw-cam fixed"):
        "editorial porn fantasy needs a deliberate framing; raw-cam fixed-angle defeats it",
    ("staged voyeur",          "eye-level full-body"):
        "staged voyeur needs distance/angle; flat eye-level looks like a studio shot",
    ("raw-cam performance",    "editorial wide"):
        "raw-cam performance needs proximity; editorial wide defeats the live-cam intimacy",
}


# Palette/lighting collapses: same-family palette + same-family lighting
# yields a flat read for v0.1's small curated set.
_PALETTE_LIGHTING_COLLAPSE: frozenset[tuple[str, str]] = frozenset(
    {
        ("warm hotel amber",   "warm lamp"),
        ("flash-photo neutral", "flash on-camera"),
    }
)


# Safety-boundary primary rejection reasons -> rule_id mapping.
_SAFETY_RULE_BY_REASON: dict[str, str] = {
    "juvenile_coded":       "SAFE-001",
    "coercion_coded":       "SAFE-002",
    "hidden_camera_coded":  "SAFE-003",
}


class CompatibilityInputError(ValueError):
    """Raised when compatibility input is malformed."""


@dataclass
class CompatibilityCheckResult:
    """Pass + hard_rejects + warnings tuple per AMood compatibility table.

    `hard_rejects` includes a `rule_id` per item so the dispatcher can
    cite the canonical rule. `warnings` are advisory; the LLM caller can
    still proceed but the GUI surfaces them in the triage tab.
    """
    pass_ok: bool
    hard_rejects: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "pass": self.pass_ok,
            "hard_rejects": list(self.hard_rejects),
            "warnings": list(self.warnings),
        }


def check_compatibility(
    *,
    sexual_trigger: str = "",
    explicit_family: str = "",
    pose_family: str = "",
    orientation: str = "",
    camera_family: str = "",
    wardrobe_state: str = "",
    support_object: str = "",
    palette_family: str = "",
    lighting_family: str = "",
    fantasy_mode: str = "",
    primary_rejection_reason: str | None = None,
) -> CompatibilityCheckResult:
    """Run the AMood compatibility truth table on an input set.

    Returns `pass=False` if any hard_reject fires. `warnings` may also
    be populated when `pass=True`; warnings do not gate insertion.

    Inputs are free-text values matching the AMood blueprint axes; case
    is normalized to lowercase for matching against the v0.1 curated
    sets but the input strings are returned verbatim in error messages.
    """

    rejects: list[dict[str, str]] = []
    warns: list[dict[str, str]] = []

    cam_lc      = (camera_family or "").lower().strip()
    wardrobe_lc = (wardrobe_state or "").lower().strip()
    support_lc  = (support_object or "").lower().strip()
    fantasy_lc  = (fantasy_mode or "").lower().strip()
    palette_lc  = (palette_family or "").lower().strip()
    lighting_lc = (lighting_family or "").lower().strip()

    # ----- safety boundaries (block; no override path) -------------------
    if primary_rejection_reason in _SAFETY_RULE_BY_REASON:
        rule_id = _SAFETY_RULE_BY_REASON[primary_rejection_reason]
        rejects.append(
            {
                "category": "safety-boundary",
                "rule_id": rule_id,
                "detail": (
                    f"primary_rejection_reason={primary_rejection_reason!r} "
                    "is a hard safety block"
                ),
            }
        )

    # ----- camera-cant-see-target ---------------------------------------
    if explicit_family and cam_lc in _REAR_ONLY_CAMERAS and "rear" not in explicit_family.lower():
        rejects.append(
            {
                "category": "camera-cant-see-target",
                "rule_id": "AMOOD-004",
                "detail": (
                    f"camera_family {camera_family!r} cannot see a non-rear "
                    f"explicit_family {explicit_family!r}"
                ),
            }
        )

    # ----- wardrobe-covers-target ---------------------------------------
    if explicit_family and wardrobe_lc in _FULLY_COVERING_WARDROBE:
        rejects.append(
            {
                "category": "wardrobe-covers-target",
                "rule_id": "AMOOD-004",
                "detail": (
                    f"wardrobe_state {wardrobe_state!r} covers explicit_family "
                    f"{explicit_family!r}"
                ),
            }
        )

    # ----- prop-blocks-target -------------------------------------------
    prop_key = (support_lc, cam_lc)
    if prop_key in _INCOMPATIBLE_PROP_FAMILIES:
        rejects.append(
            {
                "category": "prop-blocks-target",
                "rule_id": "AMOOD-004",
                "detail": _INCOMPATIBLE_PROP_FAMILIES[prop_key],
            }
        )

    # ----- fantasy-set-camera-mismatch ----------------------------------
    fantasy_camera_key = (fantasy_lc, cam_lc)
    if fantasy_camera_key in _FANTASY_CAMERA_MISMATCH:
        rejects.append(
            {
                "category": "fantasy-set-camera-mismatch",
                "rule_id": "AMOOD-004",
                "detail": _FANTASY_CAMERA_MISMATCH[fantasy_camera_key],
            }
        )

    # ----- palette-collapse ---------------------------------------------
    if (palette_lc, lighting_lc) in _PALETTE_LIGHTING_COLLAPSE:
        warns.append(
            {
                "category": "palette-collapse",
                "rule_id": "AMOOD-004",
                "detail": (
                    f"palette_family {palette_family!r} + lighting_family "
                    f"{lighting_family!r} collapses tonal contrast"
                ),
            }
        )

    # ----- pose-implausible warning -------------------------------------
    # v0.1 only catches one specific implausible combo; expansion is
    # operator-driven as specific failures surface in production.
    pose_lc = (pose_family or "").lower().strip()
    orient_lc = (orientation or "").lower().strip()
    if pose_lc == "lying-on-back" and orient_lc == "rear":
        rejects.append(
            {
                "category": "pose-implausible",
                "rule_id": "AMOOD-004",
                "detail": "pose_family 'lying-on-back' is incompatible with orientation 'rear'",
            }
        )

    # ----- multi-trigger-conflict ---------------------------------------
    triggers = [
        s.strip()
        for s in (sexual_trigger or "").split(";")
        if s.strip()
    ]
    if len(triggers) > 1:
        warns.append(
            {
                "category": "multi-trigger-conflict",
                "rule_id": "AMOOD-004",
                "detail": (
                    f"sexual_trigger contains {len(triggers)} ;-separated triggers; "
                    "AMood guidance is one trigger per card"
                ),
            }
        )

    return CompatibilityCheckResult(
        pass_ok=not rejects,
        hard_rejects=rejects,
        warnings=warns,
    )
