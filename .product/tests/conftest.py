"""Pytest fixtures shared across the OpenRepose test suite."""

from __future__ import annotations

import os
import shutil
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

# WP-I2-001: known Postgres install candidates on Windows. The library
# tests skip when none are reachable (CI without Postgres, etc.).
_PG_CANDIDATE_DIRS = (
    Path("C:/Program Files/PostgreSQL/16/bin"),
    Path("C:/Program Files/PostgreSQL/15/bin"),
    Path("C:/Program Files/PostgreSQL/14/bin"),
)


def _ensure_pg_on_path() -> str | None:
    """Return the discovered `pg_ctl` directory, also prepending it to
    `PATH` for child processes (pytest-postgresql + psycopg). None when
    no install is detected."""
    if shutil.which("pg_ctl"):
        return None  # already on PATH
    for candidate in _PG_CANDIDATE_DIRS:
        if (candidate / "pg_ctl.exe").exists() or (candidate / "pg_ctl").exists():
            os.environ["PATH"] = (
                str(candidate) + os.pathsep + os.environ.get("PATH", "")
            )
            return str(candidate)
    return None


_ensure_pg_on_path()


def _patch_pytest_postgresql_for_windows() -> None:
    """pytest-postgresql 8 hardcodes single-quoted server option values
    in `PostgreSQLExecutor.BASE_PROC_START_COMMAND`
    (e.g. `log_destination='stderr'`). On POSIX the surrounding shell
    strips the quotes; on Windows the quotes land inside Postgres'
    parameter parser and cause `FATAL: invalid value for parameter`.

    Patch the template once at import time to use unquoted values. Only
    applied when pytest-postgresql is importable; safe no-op otherwise.
    """
    if os.name != "nt":
        return
    try:
        from pytest_postgresql.executor import PostgreSQLExecutor
    except ImportError:
        return
    template = (
        '{executable} start -D "{datadir}" '
        "-o \"-F -p {port} -c log_destination=stderr "
        "-c logging_collector=off "
        '-c unix_socket_directories=\\"{unixsocketdir}\\" {postgres_options}" '
        '-l "{logfile}" {startparams}'
    )
    PostgreSQLExecutor.BASE_PROC_START_COMMAND = template


_patch_pytest_postgresql_for_windows()


def _patch_mirakuru_for_windows() -> None:
    """mirakuru's `SimpleExecutor.stop` / `.kill` call `os.killpg`, which
    does not exist on Windows. Replace with `Popen.terminate` / `.kill`
    so pytest-postgresql teardown does not crash. No-op on POSIX."""
    if os.name != "nt":
        return
    try:
        from mirakuru import base as _mb
    except ImportError:
        return

    def _win_stop(self, stop_signal=None, expected_returncode=None):  # noqa: ANN001
        if self.process is None:
            return self
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
        except Exception:  # noqa: BLE001
            try:
                self.process.kill()
                self.process.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass
        self._clear_process()
        return self

    def _win_kill(self, wait=True, sig=None):  # noqa: ANN001
        if self.process is None:
            return self
        try:
            self.process.kill()
            if wait:
                self.process.wait(timeout=5)
        except Exception:  # noqa: BLE001
            pass
        self._clear_process()
        return self

    _mb.SimpleExecutor.stop = _win_stop  # type: ignore[assignment]
    _mb.SimpleExecutor.kill = _win_kill  # type: ignore[assignment]


_patch_mirakuru_for_windows()


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
