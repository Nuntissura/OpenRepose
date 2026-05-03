"""Hand-rolled SQL migration runner for the OpenRepose Library backend.

Spec: `.gov/spec/openrepose_library_v0_1.md` Database Schema (`schema_version`
table read on startup; pending migrations applied automatically).

Migrations are plain `.sql` files under `.product/migrations/` named
`NNN_<slug>.sql` (NNN is a 3-digit zero-padded version). Discovery is by
filename pattern + numeric sort; the migrator records each applied
version into the `schema_version` table at end of the same transaction
that ran the file.

Concurrency: applying migrations holds a Postgres advisory lock keyed by
`LIBRARY_MIGRATION_LOCK_ID` (a stable 64-bit constant) so two OpenRepose
instances cannot race the same migration. Other instances that try to
apply concurrently block on the lock until the first finishes; if the
first fails, the lock is released and a second attempt proceeds.

This module avoids any Alembic / SQLAlchemy dependency on purpose: the
schema is small, hand-rolled SQL is auditable in plain text, and
operators can inspect / replay migrations with `psql` directly.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg

LOG = logging.getLogger(__name__)

# Stable advisory-lock identifier for OpenRepose Library migrations.
# Picked once and never changed. Any 64-bit signed int works; the hex
# tail `FEED053` is just a memorable handle when scanning pg_locks.
LIBRARY_MIGRATION_LOCK_ID = 0x0000_0000_0FEE_D053


_MIGRATION_NAME_RE = re.compile(r"^(\d{3,})_([a-z0-9_-]+)\.sql$", re.IGNORECASE)


class MigrationApplyError(RuntimeError):
    """Raised when a migration cannot be discovered, parsed, or applied."""


@dataclass(frozen=True)
class Migration:
    """A single discovered migration file.

    `version` is the integer parsed from the filename prefix (e.g. `1`
    for `001_library_initial.sql`). `path` is the absolute path to the
    file. `slug` is the human-readable suffix.
    """

    version: int
    slug: str
    path: Path

    def read_sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def discover_migrations(migrations_dir: Path | str) -> list[Migration]:
    """Return every `.sql` file under `migrations_dir` sorted by version.

    Files whose names do not match `NNN_<slug>.sql` are ignored (allows
    operators to drop README / scratch files alongside without breaking
    the runner). Duplicate version numbers raise.
    """
    base = Path(migrations_dir)
    if not base.exists():
        return []

    found: dict[int, Migration] = {}
    for entry in sorted(base.iterdir()):
        if not entry.is_file() or entry.suffix.lower() != ".sql":
            continue
        m = _MIGRATION_NAME_RE.match(entry.name)
        if not m:
            LOG.warning("migrator.skip_unmatched: file=%s", entry.name)
            continue
        version = int(m.group(1))
        slug = m.group(2)
        if version in found:
            raise MigrationApplyError(
                f"duplicate migration version {version}: "
                f"{found[version].path.name} vs {entry.name}"
            )
        found[version] = Migration(version=version, slug=slug, path=entry)

    return [found[v] for v in sorted(found.keys())]


class Migrator:
    """Apply pending migrations against a live psycopg 3 connection.

    Usage:

        with psycopg.connect(dsn) as conn:
            m = Migrator(conn, migrations_dir=Path(".product/migrations"))
            applied = m.apply_pending()  # -> list[int]

    Holds a session-level advisory lock during `apply_pending()` so two
    OpenRepose instances starting at the same time serialize. Idempotent:
    re-running on a current DB is a no-op.
    """

    def __init__(
        self,
        conn: "psycopg.Connection[object]",
        *,
        migrations_dir: Path | str,
        lock_id: int = LIBRARY_MIGRATION_LOCK_ID,
    ) -> None:
        self._conn = conn
        self._dir = Path(migrations_dir)
        self._lock_id = int(lock_id)

    # --- inspection ------------------------------------------------------

    def current_version(self) -> int:
        """Return MAX(version) from `schema_version`. Returns 0 when the
        table does not exist yet (fresh database) or has no rows."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('public.schema_version')"
            )
            row = cur.fetchone()
            if row is None or row[0] is None:
                return 0
            cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
            row = cur.fetchone()
            assert row is not None
            return int(row[0])

    def discover(self) -> list[Migration]:
        return discover_migrations(self._dir)

    def pending(self) -> list[Migration]:
        cur = self.current_version()
        return [m for m in self.discover() if m.version > cur]

    # --- mutation --------------------------------------------------------

    def apply_pending(self) -> list[int]:
        """Apply every migration with version > current. Returns the list
        of newly-applied versions. No-op when up-to-date."""
        applied: list[int] = []
        with self._lock():
            for migration in self.pending():
                self._apply_one(migration)
                applied.append(migration.version)
        return applied

    # --- internals -------------------------------------------------------

    def _lock(self) -> "_AdvisoryLockCM":
        return _AdvisoryLockCM(self._conn, self._lock_id)

    def _apply_one(self, migration: Migration) -> None:
        sql = migration.read_sql()
        LOG.info(
            "migrator.apply_begin: version=%s slug=%s path=%s",
            migration.version,
            migration.slug,
            migration.path,
        )
        # psycopg autocommit is False by default inside `with conn`, so
        # one transaction per migration is automatic; we explicitly
        # commit/rollback at the end so the advisory lock can release.
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_version (version) VALUES (%s) "
                    "ON CONFLICT (version) DO NOTHING",
                    (migration.version,),
                )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            LOG.exception(
                "migrator.apply_fail: version=%s slug=%s",
                migration.version,
                migration.slug,
            )
            raise
        LOG.info(
            "migrator.apply_ok: version=%s slug=%s",
            migration.version,
            migration.slug,
        )


class _AdvisoryLockCM:
    """Context manager: acquire a session-scoped advisory lock on enter,
    release on exit. Commits the lock acquisition so a future migration
    statement sees the lock outside an aborted transaction."""

    def __init__(self, conn: "psycopg.Connection[object]", lock_id: int) -> None:
        self._conn = conn
        self._lock_id = lock_id

    def __enter__(self) -> "_AdvisoryLockCM":
        with self._conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (self._lock_id,))
        self._conn.commit()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (self._lock_id,))
            self._conn.commit()
        except Exception:  # noqa: BLE001
            # Best-effort: if release fails (rare; connection died), the
            # session-scoped lock dies with the session.
            LOG.warning("migrator.advisory_unlock_failed", exc_info=True)
