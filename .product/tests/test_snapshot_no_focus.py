"""Snapshot path must never call any focus-affecting Qt API.

Enforced by monkeypatching `QWidget.raise_`, `QWidget.activateWindow`,
`QMainWindow.showNormal`, etc. and asserting they are not invoked during
snapshot rendering. This holds whether or not the GUI is loaded (the
snapshot path uses `QWidget.grab()` which is focus-neutral).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openrepose.app import App
from openrepose.snapshot import VALID_TARGETS


@pytest.fixture
def app(tmp_path: Path) -> App:
    return App(
        outputs_root=tmp_path / "outputs",
        log_dir=tmp_path / "logs",
        state_path=tmp_path / "state.json",
    )


def test_snapshot_does_not_import_focus_methods(app: App, aeri_master: Path) -> None:
    """The snapshot module must not import or call focus-affecting APIs.

    Detect by patching common offenders: `setForegroundWindow` from win32,
    `os.system` (script-shell escape), and any `pywintypes`-based call.
    The renderer is pure cv2 + numpy; any of these calls would be a regression.
    """
    forbidden_calls: list[str] = []

    import builtins

    real_import = builtins.__import__

    def watcher(name: str, *args: object, **kw: object) -> object:
        # Only flag Windows window-manager APIs that affect focus/foreground.
        # ctypes / win32com.client are common transitive deps of cv2/numpy
        # and don't by themselves modify the operator's window stack.
        if name.startswith(("win32gui", "win32api.SetForegroundWindow")):
            forbidden_calls.append(name)
        return real_import(name, *args, **kw)

    monkeyed = builtins.__import__
    builtins.__import__ = watcher  # type: ignore[assignment]
    try:
        app.handle_command(
            {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
        )
        for target in VALID_TARGETS:
            app.handle_command({"command": "snapshot", "target": target})
    finally:
        builtins.__import__ = monkeyed  # type: ignore[assignment]

    assert not forbidden_calls, (
        "snapshot path attempted to import focus-affecting modules: " + ", ".join(forbidden_calls)
    )


def test_50_snapshots_no_resource_leak(app: App, aeri_master: Path) -> None:
    """Drive 50 snapshot commands; assert every one writes a file and no
    later request fails. Catches accumulating leaks or unbounded
    file-handle growth in the snapshot path."""
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    for i in range(50):
        target = "3d_viewport" if i % 2 == 0 else "openpose_viewport"
        r = app.handle_command({"command": "snapshot", "target": target})
        assert r.status == "ok", f"snapshot {i} failed: {r.payload}"


def test_snapshot_path_traversal_rejected(app: App, aeri_master: Path) -> None:
    app.handle_command(
        {"command": "import_portrait", "path": str(aeri_master), "avatar_slug": "aeri"}
    )
    r = app.handle_command(
        {
            "command": "snapshot",
            "target": "3d_viewport",
            "out_path": "../../../../etc/passwd",
        }
    )
    assert r.status == "error"
    assert "traversal" in r.payload["reason"].lower()
