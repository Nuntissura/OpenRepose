"""File-watch inbox channel for LLM commands.

Polling-based watcher (no `watchdog` dependency). Watches
`outputs/.runtime/inbox/` for new `*.json` files. Each file is one command.
Processed in mtime order, one at a time. Result file lands in
`outputs/.runtime/processed/<original-stem>.<status>.json` with the
original command plus a `result` block.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..commands import CommandDispatcher
    from ..log import Logger


class InboxChannel:
    """Polling-based file-watch command channel.

    Polls the inbox directory at `poll_interval_s` seconds. New `*.json`
    files are processed in ascending-mtime order. Each file is moved to
    the processed directory after handling.
    """

    def __init__(
        self,
        dispatcher: "CommandDispatcher",
        logger: "Logger",
        *,
        inbox_dir: Path | str = Path("outputs/.runtime/inbox"),
        processed_dir: Path | str = Path("outputs/.runtime/processed"),
        poll_interval_s: float = 0.5,
    ) -> None:
        self.dispatcher = dispatcher
        self.logger = logger
        self.inbox_dir = Path(inbox_dir)
        self.processed_dir = Path(processed_dir)
        self.poll_interval_s = poll_interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("InboxChannel already started")
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="openrepose-inbox",
            daemon=True,
        )
        self._thread.start()
        self.logger.ok(
            "inbox.start",
            inbox=str(self.inbox_dir),
            processed=str(self.processed_dir),
        )

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=5)
        self._thread = None
        self.logger.ok("inbox.stop")

    def process_once(self) -> int:
        """Process all currently-pending files. Returns count processed.
        Useful for tests."""
        files = self._pending_files()
        for f in files:
            self._handle_file(f)
        return len(files)

    # --- internals -------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                files = self._pending_files()
                for f in files:
                    if self._stop.is_set():
                        break
                    self._handle_file(f)
            except Exception as e:  # noqa: BLE001
                self.logger.err("inbox.loop_error", reason=str(e))
            self._stop.wait(self.poll_interval_s)

    def _pending_files(self) -> list[Path]:
        try:
            entries = [p for p in self.inbox_dir.iterdir() if p.is_file() and p.suffix == ".json"]
        except FileNotFoundError:
            return []
        entries.sort(key=lambda p: p.stat().st_mtime)
        return entries

    def _handle_file(self, src: Path) -> None:
        try:
            text = src.read_text(encoding="utf-8")
            command = json.loads(text)
        except json.JSONDecodeError as e:
            reason = f"invalid json in {src.name}: {e}"
            self.logger.err("inbox.bad_json", reason=reason)
            self._move_processed(
                src,
                {"command": None, "result": {"status": "error", "reason": reason}},
                status="err",
            )
            return
        except OSError as e:
            self.logger.err("inbox.read_error", reason=str(e), file=str(src))
            return

        self.logger.dbg("inbox.recv", file=src.name)
        result = self.dispatcher.dispatch(command)
        self._move_processed(
            src,
            {"command": command, "result": result.to_dict()},
            status="ok" if result.status == "ok" else "err",
        )

    def _move_processed(
        self,
        src: Path,
        wrapper: dict[str, object],
        *,
        status: str,
    ) -> None:
        try:
            self.processed_dir.mkdir(parents=True, exist_ok=True)
            out = self.processed_dir / f"{src.stem}.{status}.json"
            out.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")
            src.unlink()
        except OSError as e:
            self.logger.err("inbox.move_error", reason=str(e), file=str(src))
