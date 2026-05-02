"""Mechanical log format for OpenRepose.

Spec: `.gov/spec/openrepose_v0_1.md` section "Mechanical Log Format".

Every log line takes one of four exact shapes:

    [YYYY-MM-DDTHH:MM:SS.mmm] OK   <op>: <k=v> <k=v> ...
    [YYYY-MM-DDTHH:MM:SS.mmm] WARN <op>: <reason>; <k=v>
    [YYYY-MM-DDTHH:MM:SS.mmm] ERR  <op>: <reason>; <k=v>
    [YYYY-MM-DDTHH:MM:SS.mmm] DBG  <op>: <k=v>

`<op>` is dotted lower-snake-case (rig.fit, viewport.snapshot, etc.). Emitted
to stdout, to a rolling per-day file under `target/logs/`, and to an
in-memory ring buffer the GUI reads later.
"""

from __future__ import annotations

import collections
import datetime
import sys
import threading
from enum import Enum
from pathlib import Path

DEFAULT_LOG_DIR = Path("target/logs")
LOG_FILE_PATTERN = "openrepose-{date}.log"
RING_BUFFER_SIZE = 2000


class LogLevel(str, Enum):
    OK = "OK"
    WARN = "WARN"
    ERR = "ERR"
    DBG = "DBG"


class Logger:
    """Thread-safe mechanical-format logger.

    Sinks:
        - stdout (text)
        - rolling file `target/logs/openrepose-YYYYMMDD.log` (text)
        - in-memory ring buffer (read by GUI / state dump)
    """

    def __init__(
        self,
        log_dir: Path | str = DEFAULT_LOG_DIR,
        ring_size: int = RING_BUFFER_SIZE,
        *,
        write_stdout: bool = True,
        write_file: bool = True,
    ) -> None:
        self.log_dir = Path(log_dir)
        if write_file:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        self._ring: collections.deque[str] = collections.deque(maxlen=ring_size)
        self._lock = threading.Lock()
        self._write_stdout = write_stdout
        self._write_file = write_file
        self._level_filter: LogLevel | None = None

    def set_level_filter(self, level: LogLevel | None) -> None:
        """Restrict which levels are emitted to stdout. The ring buffer and
        file always see everything, regardless of filter."""
        self._level_filter = level

    def emit(
        self,
        level: LogLevel,
        op: str,
        *,
        reason: str | None = None,
        **fields: object,
    ) -> str:
        line = format_line(level, op, reason=reason, **fields)
        with self._lock:
            self._ring.append(line)
            if self._write_file:
                self._append_to_file(line)
            if self._write_stdout and self._stdout_passes(level):
                print(line, file=sys.stdout, flush=True)
        return line

    def ok(self, op: str, **fields: object) -> str:
        return self.emit(LogLevel.OK, op, **fields)

    def warn(self, op: str, reason: str, **fields: object) -> str:
        return self.emit(LogLevel.WARN, op, reason=reason, **fields)

    def err(self, op: str, reason: str, **fields: object) -> str:
        return self.emit(LogLevel.ERR, op, reason=reason, **fields)

    def dbg(self, op: str, **fields: object) -> str:
        return self.emit(LogLevel.DBG, op, **fields)

    def tail(self, n: int = 200) -> list[str]:
        with self._lock:
            data = list(self._ring)
        return data[-n:]

    def _stdout_passes(self, level: LogLevel) -> bool:
        if self._level_filter is None:
            return True
        order = (LogLevel.DBG, LogLevel.OK, LogLevel.WARN, LogLevel.ERR)
        return order.index(level) >= order.index(self._level_filter)

    def _append_to_file(self, line: str) -> None:
        date = datetime.datetime.now(tz=datetime.UTC).strftime("%Y%m%d")
        target = self.log_dir / LOG_FILE_PATTERN.format(date=date)
        with target.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")


def format_line(
    level: LogLevel,
    op: str,
    *,
    reason: str | None = None,
    **fields: object,
) -> str:
    """Format a single mechanical log line. Pure function, exposed for tests."""
    if not isinstance(level, LogLevel):
        raise TypeError(f"level must be LogLevel; got {type(level).__name__}")
    _validate_op(op)

    ts = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{datetime.datetime.now(tz=datetime.UTC).microsecond // 1000:03d}"
    )
    level_padded = f"{level.value:<4s}"
    head = f"[{ts}] {level_padded} {op}:"

    body_parts: list[str] = []
    if reason is not None:
        if level not in (LogLevel.WARN, LogLevel.ERR):
            raise ValueError(
                f"reason= only valid for WARN/ERR levels; got {level.value}"
            )
        body_parts.append(_quote_value(reason))
    body_parts.extend(_format_fields(fields))

    if reason is not None and fields:
        # WARN/ERR shape uses semicolon between reason and key-value tail.
        return f"{head} {body_parts[0]}; " + " ".join(body_parts[1:])
    if not body_parts:
        return head
    return f"{head} " + " ".join(body_parts)


def _format_fields(fields: dict[str, object]) -> list[str]:
    out: list[str] = []
    for k, v in fields.items():
        if not k:
            raise ValueError("log field key cannot be empty")
        if not k.replace("_", "").isalnum():
            raise ValueError(f"log field key must be alphanumeric/underscore: {k!r}")
        out.append(f"{k}={_format_value(v)}")
    return out


def _format_value(v: object) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return _quote_value(v)
    return _quote_value(str(v))


def _quote_value(s: str) -> str:
    if " " in s or s == "" or '"' in s:
        return '"' + s.replace('"', '\\"') + '"'
    return s


def _validate_op(op: str) -> None:
    if not op:
        raise ValueError("op cannot be empty")
    if op != op.lower():
        raise ValueError(f"op must be lowercase: {op!r}")
    for part in op.split("."):
        if not part:
            raise ValueError(f"op has empty segment: {op!r}")
        if not part.replace("_", "").isalnum():
            raise ValueError(f"op segment must be alphanumeric/underscore: {part!r}")
