"""Integer-only geometry helpers used by the rendering pipeline."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


def require_int(value: object, name: str) -> int:
    """Return an integer value or raise a descriptive error.

    Booleans are rejected even though Python models them as integers.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer, got {type(value).__name__}")
    return value


@dataclass(frozen=True, slots=True)
class Point:
    """An immutable integer coordinate."""

    x: int
    y: int

    def __post_init__(self) -> None:
        require_int(self.x, "x")
        require_int(self.y, "y")

    def translated(self, dx: int, dy: int) -> Point:
        """Return this point translated by an integer offset."""
        return Point(self.x + require_int(dx, "dx"), self.y + require_int(dy, "dy"))


@dataclass(frozen=True, slots=True)
class Bounds:
    """Inclusive integer bounds for non-empty pixel content."""

    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        for name, value in (
            ("left", self.left),
            ("top", self.top),
            ("right", self.right),
            ("bottom", self.bottom),
        ):
            require_int(value, name)
        if self.right < self.left or self.bottom < self.top:
            raise ValueError("bounds must be non-empty and ordered")

    @property
    def width(self) -> int:
        """Return the number of columns in the bounds."""
        return self.right - self.left + 1

    @property
    def height(self) -> int:
        """Return the number of rows in the bounds."""
        return self.bottom - self.top + 1

    @property
    def center(self) -> Point:
        """Return the integer midpoint, rounded toward the top-left."""
        return Point((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    def translated(self, dx: int, dy: int) -> Bounds:
        """Return translated bounds."""
        checked_dx = require_int(dx, "dx")
        checked_dy = require_int(dy, "dy")
        return Bounds(
            self.left + checked_dx,
            self.top + checked_dy,
            self.right + checked_dx,
            self.bottom + checked_dy,
        )

    def clipped(self, width: int, height: int) -> Bounds | None:
        """Clip bounds to a canvas, returning ``None`` when fully outside."""
        checked_width = require_int(width, "width")
        checked_height = require_int(height, "height")
        if checked_width <= 0 or checked_height <= 0:
            raise ValueError("canvas dimensions must be positive")
        left = max(0, self.left)
        top = max(0, self.top)
        right = min(checked_width - 1, self.right)
        bottom = min(checked_height - 1, self.bottom)
        if right < left or bottom < top:
            return None
        return Bounds(left, top, right, bottom)

    @classmethod
    def from_points(cls, points: Iterable[Point]) -> Bounds:
        """Construct the smallest bounds containing all supplied points."""
        collected = tuple(points)
        if not collected:
            raise ValueError("at least one point is required")
        return cls(
            min(point.x for point in collected),
            min(point.y for point in collected),
            max(point.x for point in collected),
            max(point.y for point in collected),
        )


def integer_line(start: Point, end: Point) -> tuple[Point, ...]:
    """Return deterministic Bresenham coordinates including both endpoints."""
    x0, y0 = start.x, start.y
    x1, y1 = end.x, end.y
    dx = abs(x1 - x0)
    step_x = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    step_y = 1 if y0 < y1 else -1
    error = dx + dy
    points: list[Point] = []
    while True:
        points.append(Point(x0, y0))
        if x0 == x1 and y0 == y1:
            return tuple(points)
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += step_x
        if doubled <= dx:
            error += dx
            y0 += step_y


def translate_points(points: Iterable[Point], dx: int, dy: int) -> tuple[Point, ...]:
    """Translate every point by the same integer offset."""
    return tuple(point.translated(dx, dy) for point in points)


def mirror_points(points: Iterable[Point], *, axis: str, coordinate: int) -> tuple[Point, ...]:
    """Mirror points across an integer horizontal or vertical axis."""
    checked_coordinate = require_int(coordinate, "coordinate")
    collected = tuple(points)
    if axis == "vertical":
        return tuple(Point(2 * checked_coordinate - point.x, point.y) for point in collected)
    if axis == "horizontal":
        return tuple(Point(point.x, 2 * checked_coordinate - point.y) for point in collected)
    raise ValueError("axis must be 'horizontal' or 'vertical'")
