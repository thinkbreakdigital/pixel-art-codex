"""Clipped, deterministic pixel primitives with no antialiasing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from PIL import Image, ImageDraw

from pixel_art_pipeline.geometry import Point, integer_line, require_int
from pixel_art_pipeline.palette import RGBA, rgba_to_hex


def _validate_image(image: Image.Image) -> None:
    if image.mode != "RGBA":
        raise ValueError(f"image mode must be RGBA, got {image.mode}")


def _validate_color(color: RGBA) -> None:
    rgba_to_hex(color)


def pixel(image: Image.Image, point: Point, color: RGBA) -> None:
    """Draw one pixel, safely ignoring coordinates outside the canvas."""
    _validate_image(image)
    _validate_color(color)
    if 0 <= point.x < image.width and 0 <= point.y < image.height:
        image.putpixel((point.x, point.y), color)


def horizontal_line(image: Image.Image, x0: int, x1: int, y: int, color: RGBA) -> None:
    """Draw a clipped horizontal line including both endpoints."""
    checked_x0 = require_int(x0, "x0")
    checked_x1 = require_int(x1, "x1")
    checked_y = require_int(y, "y")
    if checked_x1 < checked_x0:
        raise ValueError("x1 must be greater than or equal to x0")
    for x in range(checked_x0, checked_x1 + 1):
        pixel(image, Point(x, checked_y), color)


def vertical_line(image: Image.Image, x: int, y0: int, y1: int, color: RGBA) -> None:
    """Draw a clipped vertical line including both endpoints."""
    checked_x = require_int(x, "x")
    checked_y0 = require_int(y0, "y0")
    checked_y1 = require_int(y1, "y1")
    if checked_y1 < checked_y0:
        raise ValueError("y1 must be greater than or equal to y0")
    for y in range(checked_y0, checked_y1 + 1):
        pixel(image, Point(checked_x, y), color)


def line(image: Image.Image, start: Point, end: Point, color: RGBA) -> None:
    """Draw a clipped Bresenham integer line."""
    for point_value in integer_line(start, end):
        pixel(image, point_value, color)


def rectangle_outline(
    image: Image.Image, top_left: Point, bottom_right: Point, color: RGBA
) -> None:
    """Draw an axis-aligned, one-pixel rectangle outline."""
    if bottom_right.x < top_left.x or bottom_right.y < top_left.y:
        raise ValueError("bottom_right must not precede top_left")
    horizontal_line(image, top_left.x, bottom_right.x, top_left.y, color)
    horizontal_line(image, top_left.x, bottom_right.x, bottom_right.y, color)
    vertical_line(image, top_left.x, top_left.y, bottom_right.y, color)
    vertical_line(image, bottom_right.x, top_left.y, bottom_right.y, color)


def filled_rectangle(image: Image.Image, top_left: Point, bottom_right: Point, color: RGBA) -> None:
    """Draw a clipped filled rectangle."""
    if bottom_right.x < top_left.x or bottom_right.y < top_left.y:
        raise ValueError("bottom_right must not precede top_left")
    for y in range(top_left.y, bottom_right.y + 1):
        horizontal_line(image, top_left.x, bottom_right.x, y, color)


def circle(image: Image.Image, center: Point, radius: int, color: RGBA) -> None:
    """Draw a one-pixel midpoint circle approximation."""
    checked_radius = require_int(radius, "radius")
    if checked_radius < 0:
        raise ValueError("radius must be non-negative")
    x = checked_radius
    y = 0
    decision = 1 - checked_radius
    while x >= y:
        offsets = (
            (x, y),
            (y, x),
            (-y, x),
            (-x, y),
            (-x, -y),
            (-y, -x),
            (y, -x),
            (x, -y),
        )
        for dx, dy in offsets:
            pixel(image, center.translated(dx, dy), color)
        y += 1
        if decision <= 0:
            decision += 2 * y + 1
        else:
            x -= 1
            decision += 2 * (y - x) + 1


def ellipse(image: Image.Image, center: Point, radius_x: int, radius_y: int, color: RGBA) -> None:
    """Draw a deterministic integer ellipse approximation."""
    rx = require_int(radius_x, "radius_x")
    ry = require_int(radius_y, "radius_y")
    if rx < 0 or ry < 0:
        raise ValueError("ellipse radii must be non-negative")
    if rx == 0:
        vertical_line(image, center.x, center.y - ry, center.y + ry, color)
        return
    if ry == 0:
        horizontal_line(image, center.x - rx, center.x + rx, center.y, color)
        return
    # Pick the boundary pixel with the smallest implicit-equation error per column/row.
    for dx in range(-rx, rx + 1):
        candidates = range(0, ry + 1)
        dy = min(
            candidates,
            key=lambda value: abs(dx * dx * ry * ry + value * value * rx * rx - rx * rx * ry * ry),
        )
        pixel(image, center.translated(dx, dy), color)
        pixel(image, center.translated(dx, -dy), color)
    for dy in range(-ry, ry + 1):
        candidates_x = range(0, rx + 1)
        dx = min(
            candidates_x,
            key=lambda value: abs(value * value * ry * ry + dy * dy * rx * rx - rx * rx * ry * ry),
        )
        pixel(image, center.translated(dx, dy), color)
        pixel(image, center.translated(-dx, dy), color)


def polygon(image: Image.Image, points: Sequence[Point], color: RGBA, *, fill: bool = True) -> None:
    """Draw a clipped integer polygon, filled by default."""
    _validate_image(image)
    _validate_color(color)
    if len(points) < 3:
        raise ValueError("polygon requires at least three points")
    coordinates = [(point.x, point.y) for point in points]
    drawing = ImageDraw.Draw(image)
    if fill:
        drawing.polygon(coordinates, fill=color)
    else:
        drawing.line([*coordinates, coordinates[0]], fill=color, width=1)


def pixel_mask(
    image: Image.Image,
    origin: Point,
    mask: Sequence[Sequence[bool]],
    color: RGBA,
) -> None:
    """Draw truthy cells from a rectangular boolean pixel mask."""
    if not mask:
        raise ValueError("pixel mask must contain at least one row")
    width = len(mask[0])
    if width == 0 or any(len(row) != width for row in mask):
        raise ValueError("pixel mask rows must be non-empty and equal in length")
    for y, row in enumerate(mask):
        for x, enabled in enumerate(row):
            if not isinstance(enabled, bool):
                raise TypeError("pixel mask values must be booleans")
            if enabled:
                pixel(image, origin.translated(x, y), color)


def mirror(image: Image.Image, *, axis: str) -> Image.Image:
    """Return a lossless horizontal or vertical mirror of an RGBA image."""
    _validate_image(image)
    if axis == "vertical":
        return image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if axis == "horizontal":
        return image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    raise ValueError("axis must be 'horizontal' or 'vertical'")


def translate(image: Image.Image, dx: int, dy: int) -> Image.Image:
    """Translate an image on an equally sized transparent canvas."""
    _validate_image(image)
    offset = (require_int(dx, "dx"), require_int(dy, "dy"))
    translated = Image.new("RGBA", image.size, (0, 0, 0, 0))
    translated.alpha_composite(image, dest=offset)
    return translated


def palette_replace(image: Image.Image, replacements: Mapping[RGBA, RGBA]) -> Image.Image:
    """Return a copy with exact declared color replacements."""
    _validate_image(image)
    for source, target in replacements.items():
        _validate_color(source)
        _validate_color(target)
    result = image.copy()
    for y in range(image.height):
        for x in range(image.width):
            value = cast(RGBA, image.getpixel((x, y)))
            result.putpixel((x, y), replacements.get(value, value))
    return result
