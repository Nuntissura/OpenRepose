"""Operator token gate for intake_finalize / promote_to_library /
task_reject_wholesale (WP-I3-004).

# FALLBACK v0.1: operator-token derivation is SHA-256(operator_slug +
# library_root). Replaced by session-scoped opaque token in a successor
# WP. The DB-level CHECK constraint (lib_outputs_intake_001_two_stage_
# acceptance) is the actual kill switch; this gate is defense-in-depth.

Spec: `.gov/spec/openrepose_intake_v0_1.md` "Two-Stage Acceptance".

Token is derived from settings the operator can configure but the LLM
control surface cannot read. Tokens are stable per install (good enough
for v0.1) but should not be logged — `Logger` redaction is the caller's
responsibility.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...settings import Settings


def expected_operator_token(settings: "Settings | None") -> str:
    """Compute the v0.1 operator token. Stable per install."""
    if settings is None:
        return ""
    op = (getattr(settings, "operator_slug", "") or "").strip()
    root = str(getattr(settings, "library_root", "") or "").strip()
    if not op or not root:
        return ""
    digest = hashlib.sha256(f"{op}|{root}".encode("utf-8")).hexdigest()
    return digest


def verify_operator_token(payload: dict[str, Any], settings: "Settings | None") -> bool:
    """True iff the payload carries a non-empty operator_token that
    matches the expected v0.1 derivation."""
    expected = expected_operator_token(settings)
    if not expected:
        return False
    supplied = payload.get("operator_token")
    if not isinstance(supplied, str) or not supplied:
        return False
    # Constant-time compare; tokens are SHA-256 hex (64 chars) so equality
    # via hmac.compare_digest is correct.
    import hmac

    return hmac.compare_digest(expected, supplied)
