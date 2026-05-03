"""Top-level App: wires AppState + Logger + CommandDispatcher + channels.

Used by both the CLI `serve` subcommand and (future) the GUI.
"""

from __future__ import annotations

from pathlib import Path

from .channels.http import HttpChannel
from .channels.inbox import InboxChannel
from .commands import CommandDispatcher, CommandResult
from .db import LibraryPool, LibraryPoolError, Migrator
from .log import Logger
from .settings import Settings, load_or_default
from .state import AppState

# Default migrations directory: shipped under `.product/migrations/`
# alongside the source tree. Resolved from this file's location so the
# repo stays disk-agnostic. Override per-test via App(migrations_dir=...).
DEFAULT_MIGRATIONS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "migrations"
)


class App:
    """Wires the LLM control surface in a headless-friendly shape.

    Usage (programmatic):

        app = App()
        result = app.handle_command({"command": "import_portrait", "path": "...", "avatar_slug": "aeri"})

    Usage (long-running with channels):

        app = App()
        app.start_http(port=8765)
        app.start_inbox()
        try:
            ...wait for shutdown signal...
        finally:
            app.stop()
    """

    def __init__(
        self,
        *,
        outputs_root: Path | str = Path("outputs"),
        log_dir: Path | str = Path("target/logs"),
        state_path: Path | str | None = None,
        settings_path: Path | str | None = None,
        migrations_dir: Path | str | None = None,
        run_migrations: bool = True,
    ) -> None:
        self.outputs_root = Path(outputs_root)
        if state_path is None:
            state_path = self.outputs_root / ".runtime" / "state.json"
        self.state = AppState(state_path=Path(state_path))
        self.log = Logger(log_dir=log_dir)

        # Load operator settings from disk (or build defaults bound to the
        # given path). settings_path=None resolves to the cross-platform
        # AppConfigLocation default; tests pass an explicit tmp path.
        self.settings: Settings = load_or_default(settings_path)
        resolved_folder, default_used = (
            self.settings.export_folder_resolved_with_fallback_flag()
        )
        if default_used and self.settings.export_folder:
            self.log.warn(
                "settings.export_folder.fallback",
                reason="saved path does not exist",
                saved=self.settings.export_folder,
                fallback=str(resolved_folder),
            )
        self.state.set_settings_status(
            export_folder=str(resolved_folder),
            default_used=default_used,
            settings_path=str(self.settings.settings_path),
        )

        # Library subsystem (WP-I2-001). Lazy: empty library_db_url stays
        # disconnected and the rest of the app continues to work.
        self.migrations_dir = (
            Path(migrations_dir)
            if migrations_dir is not None
            else DEFAULT_MIGRATIONS_DIR
        )
        self.library_pool = LibraryPool(self.settings.library_db_url)
        if run_migrations:
            self._open_library_pool()
        else:
            self._refresh_library_state()

        self.dispatcher = CommandDispatcher(
            self.state,
            self.log,
            outputs_root=self.outputs_root,
            settings=self.settings,
        )
        # Library handlers (added in WP-I2-004) read this to issue queries.
        self.dispatcher.library_pool = self.library_pool

        self._http: HttpChannel | None = None
        self._inbox: InboxChannel | None = None
        self.state.write()  # always emit a fresh state.json at startup
        self.log.ok(
            "app.start",
            outputs_root=str(self.outputs_root),
            export_folder=str(resolved_folder),
            settings_default=default_used,
            library_connected=self.library_pool.is_connected,
        )

    # --- library lifecycle ----------------------------------------------

    def _open_library_pool(self) -> None:
        """Open the pool, run pending migrations, refresh state.library.

        Failures are degraded into `state.library.connected=false` + a
        WARN log so the rest of OpenRepose continues to function. The
        operator still gets `import_portrait` / `export_*` etc.; only
        Library commands are unavailable until the pool comes back.
        """
        if not self.settings.library_db_url:
            self.log.warn(
                "library.disabled",
                reason="settings.library_db_url is empty",
            )
            self._refresh_library_state(last_error="library_db_url is empty")
            return
        try:
            self.library_pool.open()
            with self.library_pool.connection() as conn:
                migrator = Migrator(conn, migrations_dir=self.migrations_dir)
                applied = migrator.apply_pending()
            if applied:
                self.log.ok(
                    "library.migrate",
                    applied=",".join(str(v) for v in applied),
                )
            self._refresh_library_state()
        except (LibraryPoolError, Exception) as e:  # noqa: BLE001
            self.log.warn(
                "library.open_failed",
                reason=str(e),
                db=self.settings.redacted_db_url(),
            )
            self._refresh_library_state(last_error=str(e))

    def _refresh_library_state(self, *, last_error: str | None = None) -> None:
        connected = self.library_pool.is_connected
        version = self.library_pool.schema_version() if connected else 0
        self.state.set_library_status(
            configured=self.library_pool.is_configured,
            connected=connected,
            db_url_redacted=self.settings.redacted_db_url(),
            schema_version=version,
            operator_slug=self.settings.effective_operator_slug(),
            library_root=str(self.settings.resolved_library_root()),
            last_error=last_error or self.library_pool.open_error,
        )

    def handle_command(self, command_dict: dict[str, object]) -> CommandResult:
        return self.dispatcher.dispatch(command_dict)

    def start_http(self, *, port: int = 8765) -> None:
        if self._http is not None:
            return
        self._http = HttpChannel(self.dispatcher, self.state, self.log, port=port)
        self._http.start()

    def start_inbox(
        self,
        *,
        inbox_dir: Path | str | None = None,
        processed_dir: Path | str | None = None,
        poll_interval_s: float = 0.5,
    ) -> None:
        if self._inbox is not None:
            return
        if inbox_dir is None:
            inbox_dir = self.outputs_root / ".runtime" / "inbox"
        if processed_dir is None:
            processed_dir = self.outputs_root / ".runtime" / "processed"
        self._inbox = InboxChannel(
            self.dispatcher,
            self.log,
            inbox_dir=inbox_dir,
            processed_dir=processed_dir,
            poll_interval_s=poll_interval_s,
        )
        self._inbox.start()

    def stop(self) -> None:
        if self._http is not None:
            self._http.stop()
            self._http = None
        if self._inbox is not None:
            self._inbox.stop()
            self._inbox = None
        try:
            self.library_pool.close()
        except Exception:  # noqa: BLE001
            self.log.warn("library.close_failed", reason="pool close raised")
        self.log.ok("app.stop")
