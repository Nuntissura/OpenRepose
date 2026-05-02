"""HTTP localhost channel for LLM commands.

Stdlib `http.server` only — no Flask/FastAPI dependency. Bound to
`127.0.0.1` exclusively so the surface is single-user local.

Endpoints (spec: `.gov/spec/openrepose_v0_1.md` section "LLM Control Surface"):

    POST /command   Content-Type: application/json   body: <command JSON>
    GET  /state                                       returns state.json
    GET  /log?lines=<N>                               returns last N log lines
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..commands import CommandDispatcher
    from ..log import Logger
    from ..state import AppState


def make_request_handler(
    dispatcher: "CommandDispatcher",
    state: "AppState",
    logger: "Logger",
) -> type[BaseHTTPRequestHandler]:
    """Build a BaseHTTPRequestHandler subclass closed over our app objects."""

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            # Suppress default stderr access log; we have our own logger.
            return

        def _check_localhost(self) -> bool:
            client_ip = self.client_address[0]
            if client_ip not in ("127.0.0.1", "::1"):
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"status": "error", "reason": "non-localhost"}).encode()
                )
                logger.warn(
                    "http.reject_non_localhost",
                    reason="connection not from 127.0.0.1",
                    client=client_ip,
                )
                return False
            return True

        def do_POST(self) -> None:
            if not self._check_localhost():
                return
            if self.path != "/command":
                self.send_error(404, "unknown POST endpoint")
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except json.JSONDecodeError as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"status": "error", "reason": f"invalid JSON: {e}"}).encode()
                )
                logger.err("http.bad_json", reason=str(e))
                return

            result = dispatcher.dispatch(body)
            payload = json.dumps(result.to_dict()).encode("utf-8")
            self.send_response(200 if result.status == "ok" else 400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if not self._check_localhost():
                return
            if self.path == "/state":
                payload = json.dumps(state.to_dict()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path.startswith("/log"):
                # Parse ?lines=N; default 200.
                n = 200
                if "?" in self.path:
                    qs = self.path.split("?", 1)[1]
                    for kv in qs.split("&"):
                        if kv.startswith("lines="):
                            try:
                                n = max(1, min(10000, int(kv[len("lines=") :])))
                            except ValueError:
                                pass
                lines = logger.tail(n)
                body = "\n".join(lines).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404, "unknown GET endpoint")

    return _Handler


class HttpChannel:
    """Lifecycle wrapper for the localhost HTTP server. Runs in a daemon thread."""

    def __init__(
        self,
        dispatcher: "CommandDispatcher",
        state: "AppState",
        logger: "Logger",
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        if host not in ("127.0.0.1", "::1"):
            raise ValueError(f"HttpChannel host must be localhost; got {host!r}")
        self.host = host
        self.port = port
        self.dispatcher = dispatcher
        self.state = state
        self.logger = logger
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("HttpChannel already started")
        handler = make_request_handler(self.dispatcher, self.state, self.logger)
        self._server = HTTPServer((self.host, self.port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"openrepose-http-{self.port}",
            daemon=True,
        )
        self._thread.start()
        self.logger.ok("http.start", host=self.host, port=self.port)

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None
        self.logger.ok("http.stop", host=self.host, port=self.port)
