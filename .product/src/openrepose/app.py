"""Top-level App: wires AppState + Logger + CommandDispatcher + channels.

Used by both the CLI `serve` subcommand and (future) the GUI.
"""

from __future__ import annotations

from pathlib import Path

from .channels.http import HttpChannel
from .channels.inbox import InboxChannel
from .commands import CommandDispatcher, CommandResult
from .log import Logger
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
    ) -> None:
        self.outputs_root = Path(outputs_root)
        if state_path is None:
            state_path = self.outputs_root / ".runtime" / "state.json"
        self.state = AppState(state_path=Path(state_path))
        self.log = Logger(log_dir=log_dir)
        self.dispatcher = CommandDispatcher(
            self.state, self.log, outputs_root=self.outputs_root
        )
        self._http: HttpChannel | None = None
        self._inbox: InboxChannel | None = None
        self.state.write()  # always emit a fresh state.json at startup
        self.log.ok("app.start", outputs_root=str(self.outputs_root))

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
