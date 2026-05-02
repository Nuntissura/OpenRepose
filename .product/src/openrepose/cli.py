"""OpenRepose CLI.

Headless entry point for the rig + rotation + serialize pipeline.

Subcommands (v0.1):

    openrepose render
        Fit a rig to a portrait, rotate to the requested yaw bin, and
        serialize to OpenPose-format JSON.

Future subcommands ship in WP-I0-002 (`serve`) and WP-I0-004 (`gui`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .openpose_serialize import serialize_to_string
from .rig import OpenReposeRigFitError, Rig
from .rotation import rotate_yaw
from .yaw_bin import (
    OpenReposeForbiddenTerminologyError,
    OpenReposeYawBinError,
    parse_bin,
    standard_13_angle_bins,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openrepose",
        description="OpenRepose CLI - rig + rotation + OpenPose export",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- render ---
    p_render = sub.add_parser(
        "render",
        help="fit rig to a portrait, rotate to a yaw bin, write OpenPose JSON",
    )
    p_render.add_argument(
        "--portrait", required=True, type=Path, help="path to a frontal portrait"
    )
    p_render.add_argument(
        "--yaw",
        required=True,
        help="yaw bin: '0', 'her-left N', 'her-right N', or '180'",
    )
    p_render.add_argument(
        "--out",
        required=True,
        type=Path,
        help="output JSON path (parent dir created if missing)",
    )
    p_render.add_argument(
        "--canvas-width",
        type=int,
        default=None,
        help="output canvas width (default: portrait width)",
    )
    p_render.add_argument(
        "--canvas-height",
        type=int,
        default=None,
        help="output canvas height (default: portrait height)",
    )
    p_render.add_argument(
        "--indent",
        type=int,
        default=None,
        help="JSON indent (default: compact one-line)",
    )

    # --- list-bins ---
    sub.add_parser(
        "list-bins",
        help="print the 13 standard yaw bins (one per line)",
    )

    # --- gui ---
    p_gui = sub.add_parser(
        "gui",
        help="launch the operator-facing PySide6 GUI (also accepts --http-port / --inbox)",
    )
    p_gui.add_argument(
        "--http-port",
        type=int,
        default=None,
        help="enable HTTP localhost channel on this port",
    )
    p_gui.add_argument(
        "--inbox",
        action="store_true",
        help="enable file-watch inbox channel",
    )
    p_gui.add_argument(
        "--outputs-root",
        type=Path,
        default=Path("outputs"),
        help="application outputs root (default: outputs/)",
    )
    p_gui.add_argument(
        "--minimized",
        action="store_true",
        help="start minimized (operator can show via taskbar / tray)",
    )
    p_gui.add_argument(
        "--tray",
        action="store_true",
        help="show a system-tray icon (Show/Hide/Quit menu)",
    )

    # --- serve ---
    p_serve = sub.add_parser(
        "serve",
        help="run the LLM control surface (HTTP localhost and/or file-watch inbox)",
    )
    p_serve.add_argument(
        "--http-port",
        type=int,
        default=None,
        help="enable HTTP localhost channel on this port (default: disabled)",
    )
    p_serve.add_argument(
        "--inbox",
        action="store_true",
        help="enable file-watch inbox channel at outputs/.runtime/inbox/",
    )
    p_serve.add_argument(
        "--outputs-root",
        type=Path,
        default=Path("outputs"),
        help="application outputs root (default: outputs/)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "render":
        return _cmd_render(args)
    if args.cmd == "list-bins":
        for b in standard_13_angle_bins():
            print(b)
        return 0
    if args.cmd == "serve":
        return _cmd_serve(args)
    if args.cmd == "gui":
        return _cmd_gui(args)

    parser.error(f"unknown subcommand {args.cmd!r}")
    return 2


def _cmd_gui(args: argparse.Namespace) -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from .app import App
    from .gui.main_window import MainWindow

    qt_app = QApplication.instance() or QApplication([])
    qt_app.setQuitOnLastWindowClosed(True)

    app = App(outputs_root=args.outputs_root)
    if args.http_port is not None:
        app.start_http(port=args.http_port)
    if args.inbox:
        app.start_inbox()

    window = MainWindow(app)
    window.resize(1280, 800)

    if args.minimized:
        window.showMinimized()
    else:
        window.show()

    if args.tray:
        from .gui.tray import TrayIcon

        tray = TrayIcon(window)
        tray.show_window_requested.connect(window.show)
        tray.hide_window_requested.connect(window.hide)
        tray.quit_requested.connect(qt_app.quit)
        tray.start()

    print("OK   gui.ready: " + (
        f"http_port={args.http_port if args.http_port else 'none'} "
        f"inbox={'yes' if args.inbox else 'no'} tray={'yes' if args.tray else 'no'}"
    ))
    code = qt_app.exec()
    app.stop()
    return code


def _cmd_render(args: argparse.Namespace) -> int:
    try:
        yaw = parse_bin(args.yaw)
    except OpenReposeForbiddenTerminologyError as e:
        print(f"ERR  yaw_bin.forbidden: {e}", file=sys.stderr)
        return 3
    except OpenReposeYawBinError as e:
        print(f"ERR  yaw_bin.parse: {e}", file=sys.stderr)
        return 3

    try:
        rig = Rig.from_portrait(args.portrait)
    except OpenReposeRigFitError as e:
        print(f"ERR  rig.fit: {e}", file=sys.stderr)
        return 4

    rotated = rotate_yaw(rig, yaw)
    payload = serialize_to_string(
        rotated,
        canvas_width=args.canvas_width,
        canvas_height=args.canvas_height,
        indent=args.indent,
    )

    out_path: Path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")

    metrics = rig.fit_metrics
    print(
        f"OK   rig.fit: portrait={metrics.portrait_path!r} face={metrics.face_landmark_count} "
        f"body={metrics.body_landmark_count} t_ms={metrics.fit_duration_ms} "
        f"body_partial={'yes' if metrics.body_partial else 'no'}"
    )
    if metrics.body_partial:
        print(
            f"WARN rig.fit_body_partial: missing={','.join(metrics.body_partial_missing)}; "
            f"fallback=zero_confidence"
        )
    print(
        f"OK   render.write: yaw={yaw.label!r} signed_deg={yaw.signed_deg} out={str(out_path)!r}"
    )
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import signal
    import time

    from .app import App

    app = App(outputs_root=args.outputs_root)
    if args.http_port is not None:
        app.start_http(port=args.http_port)
    if args.inbox:
        app.start_inbox()
    if args.http_port is None and not args.inbox:
        print(
            "ERR  serve.no_channel: reason=\"both --http-port and --inbox disabled; nothing to serve\"",
            file=sys.stderr,
        )
        app.stop()
        return 5

    stop = False

    def _on_signal(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    try:
        signal.signal(signal.SIGINT, _on_signal)
    except (AttributeError, ValueError):
        pass
    try:
        signal.signal(signal.SIGTERM, _on_signal)
    except (AttributeError, ValueError):
        pass

    print("OK   serve.ready: http_port=" + (str(args.http_port) if args.http_port else "none") + " inbox=" + ("yes" if args.inbox else "no"))
    try:
        while not stop:
            time.sleep(0.2)
    finally:
        app.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
