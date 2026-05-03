"""Pytest fixtures shared across the OpenRepose test suite."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Force Qt to use the offscreen platform plugin during pytest so GUI tests
# do not flash real top-level windows on the operator's desktop. Must be
# set BEFORE any PySide6 import. Override with `QT_QPA_PLATFORM=windows`
# (or your platform default) if you want to see widgets pop up while
# debugging a GUI test interactively.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


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
