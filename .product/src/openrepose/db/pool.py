"""Library connection pool wrapper.

Spec: `.gov/spec/openrepose_library_v0_1.md` Multi-Operator Concurrency
("Connection pooling — psycopg_pool.ConnectionPool sync at min_size=4,
max_size=10 per OpenRepose instance").

`LibraryPool` wraps `psycopg_pool.ConnectionPool` so the rest of the app
can ask `is_connected`, `schema_version`, etc., without poking at psycopg
internals. The pool opens lazily on first `connection()` call so an empty
`library_db_url` does not crash startup.

Lifecycle:

    pool = LibraryPool(dsn)
    pool.open()                # blocks until min_size connections ready
    with pool.connection() as conn:   # checked out, returned on exit
        ...
    pool.close()
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    import psycopg
    from psycopg_pool import ConnectionPool

LOG = logging.getLogger(__name__)

DEFAULT_MIN_SIZE = 4
DEFAULT_MAX_SIZE = 10


class LibraryPoolError(RuntimeError):
    """Raised when the pool cannot open or a health-check fails."""


class LibraryPool:
    """Thin wrapper around `psycopg_pool.ConnectionPool`.

    `dsn` is the operator's `Settings.library_db_url`. Empty / unset DSN
    is allowed: the pool stays in `is_connected=False` and every helper
    raises `LibraryPoolError` on use. Callers test `is_open` /
    `is_connected` first.

    The wrapper exists so the dispatcher can degrade gracefully when the
    operator hasn't set a DB up yet (Library commands fail with a
    structured error; the rest of OpenRepose works).
    """

    def __init__(
        self,
        dsn: str | None,
        *,
        min_size: int = DEFAULT_MIN_SIZE,
        max_size: int = DEFAULT_MAX_SIZE,
        open_timeout: float | None = None,
    ) -> None:
        self._dsn = (dsn or "").strip()
        self._min_size = int(min_size)
        self._max_size = int(max_size)
        self._open_timeout = open_timeout
        self._pool: "ConnectionPool[psycopg.Connection[Any]] | None" = None
        self._open_error: str | None = None

    # --- introspection ---------------------------------------------------

    @property
    def dsn(self) -> str:
        return self._dsn

    @property
    def is_configured(self) -> bool:
        """True when a DSN was supplied (open may still fail)."""
        return bool(self._dsn)

    @property
    def is_open(self) -> bool:
        return self._pool is not None

    @property
    def open_error(self) -> str | None:
        return self._open_error

    @property
    def is_connected(self) -> bool:
        """True when the pool is open AND a SELECT 1 round-trip succeeds.

        Callers use this for `state.library.connected`. Cheap; psycopg
        pools health-check connections at checkout time, so this only
        adds one round-trip on demand.
        """
        if self._pool is None:
            return False
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return True
        except Exception as e:  # noqa: BLE001
            LOG.warning("library_pool.health_check_failed: %s", e)
            return False

    def schema_version(self) -> int:
        """Return MAX(version) from `schema_version` (0 if absent)."""
        if self._pool is None:
            return 0
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.schema_version')")
                    row = cur.fetchone()
                    if row is None or row[0] is None:
                        return 0
                    cur.execute(
                        "SELECT COALESCE(MAX(version), 0) FROM schema_version"
                    )
                    row = cur.fetchone()
                    return int(row[0]) if row else 0
        except Exception as e:  # noqa: BLE001
            LOG.warning("library_pool.schema_version_failed: %s", e)
            return 0

    # --- lifecycle -------------------------------------------------------

    def open(self) -> None:
        """Open the underlying `ConnectionPool`. No-op when DSN unset.

        Raises `LibraryPoolError` if open fails for an operator-actionable
        reason (bad DSN, server unreachable). The caller catches and
        records `state.library.connected=false`."""
        if not self._dsn:
            return
        if self._pool is not None:
            return

        # Lazy psycopg_pool import so the rest of the app boots even when
        # the optional library subsystem deps are missing.
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as e:
            self._open_error = (
                "psycopg_pool not installed; install OpenRepose with the "
                "library extras (pip install -e .)"
            )
            raise LibraryPoolError(self._open_error) from e

        try:
            kwargs: dict[str, Any] = {
                "min_size": self._min_size,
                "max_size": self._max_size,
                "open": True,
            }
            if self._open_timeout is not None:
                # `psycopg_pool.ConnectionPool.open(timeout)` waits for at
                # least `min_size` connections; the constructor accepts
                # the same as `open=True, timeout=...` is not a kwarg, so
                # open lazily then call `wait()` with a short deadline.
                kwargs["open"] = False
            self._pool = ConnectionPool(self._dsn, **kwargs)
            if self._open_timeout is not None:
                self._pool.open(wait=True, timeout=float(self._open_timeout))
        except Exception as e:
            self._open_error = str(e)
            if self._pool is not None:
                try:
                    self._pool.close()
                except Exception:  # noqa: BLE001
                    pass
            self._pool = None
            raise LibraryPoolError(
                f"cannot open library pool against {_redact(self._dsn)}: {e}"
            ) from e

        # `open=True` on construction triggers the initial connect; we
        # do an explicit health check here so callers know on return
        # whether the pool is actually usable. If the health check fails
        # we tear the partially-opened pool down so a future retry starts
        # clean.
        if not self.is_connected:
            self._open_error = "health-check failed after open"
            try:
                self._pool.close()
            except Exception:  # noqa: BLE001
                LOG.warning("library_pool.close_after_open_failed")
            self._pool = None
            raise LibraryPoolError(self._open_error)

    @contextmanager
    def connection(self) -> "Iterator[psycopg.Connection[Any]]":
        """Check out a connection from the pool. Auto-returns on exit."""
        if self._pool is None:
            raise LibraryPoolError("library pool is not open")
        with self._pool.connection() as conn:
            yield conn

    def close(self) -> None:
        if self._pool is None:
            return
        try:
            self._pool.close()
        finally:
            self._pool = None


def _redact(dsn: str) -> str:
    """Mirror `Settings.redacted_db_url` here so log lines from this
    module don't pull settings as a dep cycle."""
    sep = "://"
    idx = dsn.find(sep)
    if idx < 0:
        return dsn
    head = dsn[: idx + len(sep)]
    rest = dsn[idx + len(sep):]
    at = rest.rfind("@")
    if at < 0:
        return dsn
    creds = rest[:at]
    tail = rest[at:]
    colon = creds.find(":")
    if colon < 0:
        return dsn
    return f"{head}{creds[:colon]}:***{tail}"
