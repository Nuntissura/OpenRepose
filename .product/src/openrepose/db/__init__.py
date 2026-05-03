"""OpenRepose database layer (Library subsystem, Feature 3).

Spec: `.gov/spec/openrepose_library_v0_1.md` Database Schema + Storage
Layout. Backed by PostgreSQL >= 16; psycopg 3 + psycopg_pool.
"""

from .migrator import (
    LIBRARY_MIGRATION_LOCK_ID,
    Migration,
    MigrationApplyError,
    Migrator,
    discover_migrations,
)
from .pool import LibraryPool, LibraryPoolError

__all__ = [
    "LIBRARY_MIGRATION_LOCK_ID",
    "LibraryPool",
    "LibraryPoolError",
    "Migration",
    "MigrationApplyError",
    "Migrator",
    "discover_migrations",
]
