"""Tests for strict palette loading and compliance."""

from pathlib import Path

import pytest
from PIL import Image

from pixel_art_pipeline.palette import Palette, PaletteError, parse_rgba, partial_alpha_colors


def test_palette_parses_named_transparent_entry(tmp_path: Path) -> None:
    path = tmp_path / "palette.json"
    path.write_text(
        '{"name":"test","colors":{"clear":"#00000000","ink":"#112233FF"}}',
        encoding="utf-8",
    )
    palette = Palette.load(path)
    assert palette["clear"] == (0, 0, 0, 0)
    assert palette.to_json_values()["ink"] == "#112233FF"


@pytest.mark.parametrize("value", ["112233FF", "#123", "#GG2233FF", None])
def test_invalid_rgba_is_rejected(value: object) -> None:
    with pytest.raises(PaletteError):
        parse_rgba(value)


def test_duplicate_palette_names_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"colors":[{"name":"ink","value":"#000000FF"},{"name":"ink","value":"#FFFFFFFF"}]}',
        encoding="utf-8",
    )
    with pytest.raises(PaletteError, match="duplicate"):
        Palette.load(path)


def test_duplicate_json_object_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate-key.json"
    path.write_text('{"colors":{"ink":"#000000FF","ink":"#FFFFFFFF"}}', encoding="utf-8")
    with pytest.raises(PaletteError, match="duplicate"):
        Palette.load(path)


def test_palette_and_partial_alpha_validation() -> None:
    palette = Palette({"clear": (0, 0, 0, 0), "ink": (1, 2, 3, 255)})
    image = Image.new("RGBA", (2, 1), (1, 2, 3, 255))
    image.putpixel((1, 0), (9, 9, 9, 127))
    assert palette.undeclared_colors(image) == frozenset({(9, 9, 9, 127)})
    assert partial_alpha_colors(image) == frozenset({(9, 9, 9, 127)})
