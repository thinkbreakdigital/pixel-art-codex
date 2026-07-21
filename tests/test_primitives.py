"""Tests for clipped and deterministic pixel primitives."""

from PIL import Image

from pixel_art_pipeline.geometry import Point
from pixel_art_pipeline.primitives import (
    circle,
    filled_rectangle,
    horizontal_line,
    line,
    mirror,
    palette_replace,
    pixel_mask,
    translate,
)

INK = (10, 20, 30, 255)
CLEAR = (0, 0, 0, 0)


def test_horizontal_line_clips_to_canvas() -> None:
    image = Image.new("RGBA", (3, 2), CLEAR)
    horizontal_line(image, -4, 9, 1, INK)
    assert [image.getpixel((x, 1)) for x in range(3)] == [INK, INK, INK]


def test_integer_line_determinism() -> None:
    first = Image.new("RGBA", (8, 8), CLEAR)
    second = Image.new("RGBA", (8, 8), CLEAR)
    line(first, Point(-1, 0), Point(7, 6), INK)
    line(second, Point(-1, 0), Point(7, 6), INK)
    assert first.tobytes() == second.tobytes()


def test_circle_clips_without_error() -> None:
    image = Image.new("RGBA", (3, 3), CLEAR)
    circle(image, Point(0, 0), 3, INK)
    assert image.mode == "RGBA"


def test_rectangle_mask_transform_and_replacement() -> None:
    image = Image.new("RGBA", (4, 4), CLEAR)
    filled_rectangle(image, Point(0, 0), Point(1, 1), INK)
    pixel_mask(image, Point(2, 2), ((True, False), (False, True)), INK)
    replaced = palette_replace(image, {INK: (255, 0, 0, 255)})
    assert replaced.getpixel((0, 0)) == (255, 0, 0, 255)
    assert mirror(replaced, axis="vertical").getpixel((3, 0)) == (255, 0, 0, 255)
    assert translate(image, 1, 0).getpixel((1, 0)) == INK


def test_non_rectangular_mask_is_rejected() -> None:
    image = Image.new("RGBA", (2, 2), CLEAR)
    try:
        pixel_mask(image, Point(0, 0), ((True,), (True, False)), INK)
    except ValueError as error:
        assert "equal" in str(error)
    else:
        raise AssertionError("expected invalid mask to fail")
