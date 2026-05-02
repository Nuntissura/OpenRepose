"""Yaw terminology lock and bin parsing for OpenRepose.

The application uses one fixed terminology for yaw rotation:

    "0"            frontal, face direct at camera.
    "her-left N"   avatar rotates N degrees about her vertical axis to her own left.
                   Result: her right side is more visible to the camera.
                   Result: her nose ends up at the right edge of the frame.
    "her-right N"  avatar rotates N degrees about her vertical axis to her own right.
                   Result: her left side is more visible to the camera.
                   Result: her nose ends up at the left edge of the frame.

Forbidden phrases (raise OpenReposeForbiddenTerminologyError on parse):
"image-left", "image-right", "viewer-left", "viewer-right", "left view",
"right view".

Internal degree convention used by the rotation math: positive degrees =
her-left N (nose moves to image-right). Negative degrees = her-right N.
"""

from __future__ import annotations

from dataclasses import dataclass

# Standard front+side bins in degrees (operator-visible labels paired with
# internal signed angles).
STANDARD_FRONT_BINS_DEG = (0,)
STANDARD_HER_LEFT_BINS_DEG = (15, 30, 45, 60, 75, 90)
STANDARD_HER_RIGHT_BINS_DEG = (15, 30, 45, 60, 75, 90)

# Optional rear/body bins (not used in v0.1 default batch but parsable).
OPTIONAL_HER_LEFT_REAR_DEG = (105, 120, 150)
OPTIONAL_HER_RIGHT_REAR_DEG = (105, 120, 150)
OPTIONAL_FULL_REAR_DEG = (180,)

FORBIDDEN_PHRASES = (
    "image-left",
    "image-right",
    "viewer-left",
    "viewer-right",
    "left view",
    "right view",
)


class OpenReposeForbiddenTerminologyError(ValueError):
    """Raised when a forbidden yaw phrase appears in input."""


class OpenReposeYawBinError(ValueError):
    """Raised when a yaw bin string cannot be parsed."""


@dataclass(frozen=True)
class YawBin:
    """Parsed yaw bin.

    Attributes:
        label: canonical bin string ("0", "her-left 30", "her-right 90", ...).
        magnitude_deg: non-negative magnitude of the rotation in degrees.
        side: one of "front" (magnitude == 0), "her-left", "her-right",
            or "rear" (the special 180 bin).
        signed_deg: internal signed angle for rotation math. her-left -> +N,
            her-right -> -N, 0 -> 0, 180 -> 180.
    """

    label: str
    magnitude_deg: int
    side: str
    signed_deg: float

    def __post_init__(self) -> None:
        if self.magnitude_deg < 0:
            raise OpenReposeYawBinError(
                f"YawBin magnitude must be non-negative; got {self.magnitude_deg}"
            )
        if self.side not in ("front", "her-left", "her-right", "rear"):
            raise OpenReposeYawBinError(f"YawBin side invalid: {self.side!r}")


def standard_13_angle_bins() -> list[str]:
    """Return the labels of the 13 standard angle bins used by export_batch."""
    bins = ["0"]
    for n in STANDARD_HER_LEFT_BINS_DEG:
        bins.append(f"her-left {n}")
    for n in STANDARD_HER_RIGHT_BINS_DEG:
        bins.append(f"her-right {n}")
    return bins


def check_forbidden(text: str) -> None:
    """Raise if `text` contains any forbidden yaw phrase. Case-insensitive."""
    lowered = text.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            raise OpenReposeForbiddenTerminologyError(
                f"forbidden yaw phrase {phrase!r} in input; use 0 / her-left N / her-right N"
            )


def parse_bin(label: str) -> YawBin:
    """Parse a yaw bin label into a YawBin.

    Accepts:
        "0"
        "her-left N"   for N in 1..180 (typically the standard or optional bins)
        "her-right N"
        "180"          full rear

    Raises:
        OpenReposeForbiddenTerminologyError if input contains a banned phrase.
        OpenReposeYawBinError if input cannot be parsed.
    """
    if not isinstance(label, str):
        raise OpenReposeYawBinError(f"yaw bin must be str; got {type(label).__name__}")

    check_forbidden(label)

    s = label.strip().lower()
    if s == "0":
        return YawBin(label="0", magnitude_deg=0, side="front", signed_deg=0.0)
    if s == "180":
        return YawBin(label="180", magnitude_deg=180, side="rear", signed_deg=180.0)

    # her-left N / her-right N
    for prefix, side, sign in (("her-left ", "her-left", +1), ("her-right ", "her-right", -1)):
        if s.startswith(prefix):
            n_part = s[len(prefix):].strip()
            if not n_part.isdigit():
                raise OpenReposeYawBinError(
                    f"yaw bin {label!r} has non-integer magnitude {n_part!r}"
                )
            n = int(n_part)
            if n <= 0:
                raise OpenReposeYawBinError(
                    f"yaw bin {label!r} magnitude must be > 0 for {side}"
                )
            if n > 180:
                raise OpenReposeYawBinError(
                    f"yaw bin {label!r} magnitude must be <= 180; got {n}"
                )
            canonical = f"{side} {n}"
            return YawBin(
                label=canonical,
                magnitude_deg=n,
                side=side,
                signed_deg=float(sign * n),
            )

    raise OpenReposeYawBinError(
        f"yaw bin {label!r} not recognized; expected '0', 'her-left N', 'her-right N', or '180'"
    )


def signed_deg_to_bin(signed_deg: float) -> YawBin:
    """Inverse of `parse_bin`: take a signed degree and return the canonical YawBin.

    Snaps to the standard bin when the value is within 0.05 degrees; otherwise
    returns a free-form YawBin with the closest int magnitude and the appropriate
    side label. Useful for the GUI slider readouts.
    """
    if signed_deg == 0.0:
        return YawBin(label="0", magnitude_deg=0, side="front", signed_deg=0.0)
    if abs(signed_deg - 180.0) < 1e-6 or abs(signed_deg + 180.0) < 1e-6:
        return YawBin(label="180", magnitude_deg=180, side="rear", signed_deg=180.0)

    side = "her-left" if signed_deg > 0 else "her-right"
    n = int(round(abs(signed_deg)))
    if n <= 0:
        return YawBin(label="0", magnitude_deg=0, side="front", signed_deg=0.0)
    if n > 180:
        raise OpenReposeYawBinError(
            f"signed_deg {signed_deg} out of range; expected magnitude <= 180"
        )
    canonical = f"{side} {n}"
    sign = +1 if side == "her-left" else -1
    return YawBin(
        label=canonical,
        magnitude_deg=n,
        side=side,
        signed_deg=float(sign * n),
    )


def direction_arrow(bin_or_signed_deg: YawBin | float) -> str:
    """Return the operator-friendly arrow showing where her face goes in the export.

    her-left N -> face goes to the right edge of the frame -> "->".
    her-right N -> face goes to the left edge of the frame -> "<-".
    0 / 180 -> "" (no horizontal direction).

    Used in the GUI direction indicator next to the yaw slider.
    """
    if isinstance(bin_or_signed_deg, YawBin):
        signed = bin_or_signed_deg.signed_deg
    else:
        signed = float(bin_or_signed_deg)
    if signed > 0:
        return "->"
    if signed < 0:
        return "<-"
    return ""
