"""Yaw terminology lock + bin parser tests."""

from __future__ import annotations

import pytest

from openrepose.yaw_bin import (
    OpenReposeForbiddenTerminologyError,
    OpenReposeYawBinError,
    YawBin,
    direction_arrow,
    parse_bin,
    signed_deg_to_bin,
    standard_13_angle_bins,
)


def test_standard_13_bins_count_and_labels() -> None:
    bins = standard_13_angle_bins()
    assert len(bins) == 13
    assert bins[0] == "0"
    assert "her-left 15" in bins
    assert "her-right 90" in bins
    assert all(b.startswith(("0", "her-left ", "her-right ")) for b in bins)


def test_parse_frontal() -> None:
    b = parse_bin("0")
    assert b == YawBin(label="0", magnitude_deg=0, side="front", signed_deg=0.0)


def test_parse_her_left() -> None:
    b = parse_bin("her-left 30")
    assert b.signed_deg == 30.0
    assert b.side == "her-left"
    assert b.label == "her-left 30"


def test_parse_her_right_signed_negative() -> None:
    b = parse_bin("her-right 90")
    assert b.signed_deg == -90.0
    assert b.side == "her-right"


def test_parse_180_rear() -> None:
    b = parse_bin("180")
    assert b.side == "rear"
    assert b.signed_deg == 180.0


@pytest.mark.parametrize(
    "phrase",
    [
        "image-left 30",
        "image-right 30",
        "viewer-left 45",
        "viewer-right 60",
        "left view 15",
        "right view 75",
        "IMAGE-RIGHT 30",  # case-insensitive
    ],
)
def test_forbidden_phrases_raise(phrase: str) -> None:
    with pytest.raises(OpenReposeForbiddenTerminologyError):
        parse_bin(phrase)


@pytest.mark.parametrize(
    "junk",
    [
        "her-left",  # missing magnitude
        "her-left -5",  # negative magnitude
        "her-left 200",  # > 180
        "her-up 30",  # unknown side
        "0.5",  # not a recognized form
        "",
    ],
)
def test_invalid_bins_raise(junk: str) -> None:
    with pytest.raises(OpenReposeYawBinError):
        parse_bin(junk)


def test_signed_deg_round_trip_standard_bins() -> None:
    for label in standard_13_angle_bins():
        bin_obj = parse_bin(label)
        round_tripped = signed_deg_to_bin(bin_obj.signed_deg)
        assert round_tripped.label == bin_obj.label


def test_direction_arrow_her_left() -> None:
    assert direction_arrow(parse_bin("her-left 30")) == "->"


def test_direction_arrow_her_right() -> None:
    assert direction_arrow(parse_bin("her-right 30")) == "<-"


def test_direction_arrow_frontal_empty() -> None:
    assert direction_arrow(parse_bin("0")) == ""
