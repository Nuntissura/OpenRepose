"""Pytest fixtures shared across the OpenRepose test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
AERI_MASTER = FIXTURES_DIR / "aeri_master.png"


@pytest.fixture(scope="session")
def aeri_master() -> Path:
    if not AERI_MASTER.exists():
        pytest.skip(f"missing fixture: {AERI_MASTER}")
    return AERI_MASTER


@pytest.fixture(scope="session")
def aeri_rig(aeri_master: Path):
    """A Rig fitted once per session against the master fixture."""
    from openrepose.rig import Rig

    return Rig.from_portrait(aeri_master)
