"""Tests for integer geometry."""

import pytest

from pixel_art_pipeline.geometry import Bounds, Point, integer_line, mirror_points


def test_point_requires_integers() -> None:
    with pytest.raises(TypeError, match="integer"):
        Point(1.5, 2)  # type: ignore[arg-type]


def test_bounds_dimensions_and_clipping() -> None:
    bounds = Bounds(-1, 1, 4, 7)
    assert bounds.width == 6
    assert bounds.height == 7
    assert bounds.clipped(4, 4) == Bounds(0, 1, 3, 3)


def test_integer_line_is_inclusive_and_deterministic() -> None:
    expected = (Point(0, 0), Point(1, 1), Point(2, 1), Point(3, 2))
    assert integer_line(Point(0, 0), Point(3, 2)) == expected
    assert integer_line(Point(0, 0), Point(3, 2)) == expected


def test_mirror_points_uses_integer_axis() -> None:
    assert mirror_points((Point(1, 2), Point(3, 4)), axis="vertical", coordinate=2) == (
        Point(3, 2),
        Point(1, 4),
    )
