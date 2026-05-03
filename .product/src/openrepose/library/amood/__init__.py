"""AMood data-model surface (WP-I3-006).

Spec: `.gov/spec/openrepose_amood_v0_1.md`.

Operationalizes the AMood adult-moodboard blueprint at
`.gov/doc/references/ADULT_MOODBOARD_SYSTEM_2026-05-03.md`. The blueprint
is the structural source of truth (canonical, operator-authored,
provider/model-agnostic). This package exposes the OpenRepose-side data
model: per-batch DB rows, per-card AMood-extended rows, variant ladder,
compatibility check, accepted-set audit, anti-repetition service, TSV
round-trip.

Adult Production Boundary applies (per `.gov/AGENTS.md`): raw, direct,
technical. No softening of operator workflows.
"""

from __future__ import annotations

from .audit import (
    AcceptedSetAuditError,
    AcceptedSetAuditResult,
    AxisCoverage,
    accepted_set_audit,
    compute_realized_coverage,
)
from .batches import (
    AmoodBatchError,
    LibraryBatch,
    create_batch,
    get_batch,
    init_batch_package,
    list_batches,
)
from .cards import (
    AmoodCardError,
    AmoodCardResult,
    create_card,
)
from .compatibility import (
    CompatibilityCheckResult,
    CompatibilityInputError,
    check_compatibility,
)
from .dedupe import (
    DedupeCandidate,
    DedupeMatch,
    check_card_pre_insert,
    compose_signature,
)
from .tsv_io import (
    AMOOD_IMPORTABLE_SCHEMAS,
    AMOOD_TSV_SCHEMAS,
    AmoodTsvError,
    export_tsv,
    import_tsv,
)
from .tsv_views import AMOOD_VIEW_COLUMNS, view_for_schema
from .variants import (
    LIBRARY_VARIANT_LABELS,
    AmoodVariantError,
    create_variants,
)

__all__ = [
    "AMOOD_IMPORTABLE_SCHEMAS",
    "AMOOD_TSV_SCHEMAS",
    "AMOOD_VIEW_COLUMNS",
    "LIBRARY_VARIANT_LABELS",
    "AcceptedSetAuditError",
    "AcceptedSetAuditResult",
    "AmoodBatchError",
    "AmoodCardError",
    "AmoodCardResult",
    "AmoodTsvError",
    "AmoodVariantError",
    "AxisCoverage",
    "CompatibilityCheckResult",
    "CompatibilityInputError",
    "DedupeCandidate",
    "DedupeMatch",
    "LibraryBatch",
    "accepted_set_audit",
    "check_card_pre_insert",
    "check_compatibility",
    "compose_signature",
    "compute_realized_coverage",
    "create_batch",
    "create_card",
    "create_variants",
    "export_tsv",
    "get_batch",
    "import_tsv",
    "init_batch_package",
    "list_batches",
    "view_for_schema",
]
