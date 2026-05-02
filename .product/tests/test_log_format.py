"""Mechanical log format tests."""

from __future__ import annotations

import re

import pytest

from openrepose.log import LogLevel, format_line

LINE_RE = re.compile(
    r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\] (OK  |WARN|ERR |DBG ) [a-z][a-z0-9_.]*:.*$"
)


def test_ok_shape() -> None:
    line = format_line(LogLevel.OK, "rig.fit", face=478, body=33, t_ms=1234)
    assert LINE_RE.match(line), line
    assert "OK  " in line
    assert "rig.fit:" in line
    assert "face=478" in line
    assert "t_ms=1234" in line


def test_warn_shape_has_reason_semicolon() -> None:
    line = format_line(
        LogLevel.WARN,
        "rig.fit_body_partial",
        reason="missing right_elbow",
        missing="right_elbow",
    )
    assert "WARN" in line
    assert "; " in line
    assert "missing=right_elbow" in line


def test_err_shape() -> None:
    line = format_line(LogLevel.ERR, "rig.fit", reason="no face detected")
    assert "ERR " in line
    assert "rig.fit:" in line
    assert '"no face detected"' in line


def test_dbg_shape() -> None:
    line = format_line(LogLevel.DBG, "cmd.received", command="set_yaw_bin")
    assert "DBG " in line
    assert "cmd.received:" in line


def test_op_must_be_lowercase() -> None:
    with pytest.raises(ValueError):
        format_line(LogLevel.OK, "Rig.Fit")


def test_op_segments_must_be_alphanum_or_underscore() -> None:
    with pytest.raises(ValueError):
        format_line(LogLevel.OK, "rig.fit-thing")


def test_value_with_space_quoted() -> None:
    line = format_line(LogLevel.OK, "export.single", out="path with space")
    assert 'out="path with space"' in line


def test_bool_serialized_as_yes_no() -> None:
    line = format_line(LogLevel.OK, "rig.fit", body_partial=True)
    assert "body_partial=yes" in line


def test_reason_only_for_warn_or_err() -> None:
    with pytest.raises(ValueError):
        format_line(LogLevel.OK, "rig.fit", reason="bad")
    with pytest.raises(ValueError):
        format_line(LogLevel.DBG, "rig.fit", reason="bad")
