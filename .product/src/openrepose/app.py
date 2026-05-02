"""Top-level App: wires AppState + Logger + CommandDispatcher + channels.

Used by both the CLI `serve` subcommand and (future) the GUI.
"""

from __future__ import annotations

from pathlib import Path

from .channels.http import HttpChannel
from .channels.inbox import InboxChannel
from .commands import CommandDispatcher, CommandResult
from .log import Logger
from .settings import Settings, load_or_default
from .state import AppState


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

        self.dispatcher = CommandDispatcher(
            self.state,
            self.log,
            outputs_root=self.outputs_root,
            settings=self.settings,
        )
        self._http: HttpChannel | None = None
        self._inbox: InboxChannel | None = None
        self.state.write()  # always emit a fresh state.json at startup
        self.log.ok(
            "app.start",
            outputs_root=str(self.outputs_root),
            export_folder=str(resolved_folder),
            settings_default=default_used,
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
        self.log.ok("app.stop")
