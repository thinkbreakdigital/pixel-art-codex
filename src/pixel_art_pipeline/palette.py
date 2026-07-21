"""Strict JSON palette loading and image-palette validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PIL import Image

RGBA = tuple[int, int, int, int]
_RGBA_PATTERN = re.compile(r"^#[0-9A-Fa-f]{8}$")


class PaletteError(ValueError):
    """Raised when palette data is absent or malformed."""


def parse_rgba(value: object) -> RGBA:
    """Parse a strict ``#RRGGBBAA`` value into an RGBA tuple."""
    if not isinstance(value, str) or _RGBA_PATTERN.fullmatch(value) is None:
        raise PaletteError(f"expected #RRGGBBAA color, got {value!r}")
    channels = bytes.fromhex(value[1:])
    return channels[0], channels[1], channels[2], channels[3]


def rgba_to_hex(value: RGBA) -> str:
    """Format an RGBA tuple as canonical uppercase hexadecimal."""
    if len(value) != 4 or any(
        isinstance(channel, bool) or not isinstance(channel, int) or not 0 <= channel <= 255
        for channel in value
    ):
        raise PaletteError(f"invalid RGBA tuple: {value!r}")
    return "#" + "".join(f"{channel:02X}" for channel in value)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PaletteError(f"duplicate JSON name: {key!r}")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class Palette:
    """A named collection of declared RGBA colors."""

    entries: dict[str, RGBA]
    name: str = "unnamed"

    def __post_init__(self) -> None:
        if not self.entries:
            raise PaletteError("palette must contain at least one color")
        for entry_name, color in self.entries.items():
            if not isinstance(entry_name, str) or not entry_name.strip():
                raise PaletteError("palette entry names must be non-empty strings")
            rgba_to_hex(color)

    @property
    def colors(self) -> frozenset[RGBA]:
        """Return the unique set of declared colors."""
        return frozenset(self.entries.values())

    def __getitem__(self, name: str) -> RGBA:
        try:
            return self.entries[name]
        except KeyError as error:
            raise PaletteError(f"unknown palette entry: {name!r}") from error

    def to_json_values(self) -> dict[str, str]:
        """Return deterministic JSON-ready palette values."""
        return {name: rgba_to_hex(color) for name, color in sorted(self.entries.items())}

    @classmethod
    def from_data(cls, data: object) -> Palette:
        """Build a palette from a JSON-compatible object.

        ``colors`` can be either a name-to-color object or an array containing
        ``{"name": ..., "value": ...}`` records. The array form permits explicit
        duplicate-name detection before construction.
        """
        if not isinstance(data, dict):
            raise PaletteError("palette root must be a JSON object")
        name = data.get("name", "unnamed")
        if not isinstance(name, str) or not name.strip():
            raise PaletteError("palette name must be a non-empty string")
        colors = data.get("colors")
        entries: dict[str, RGBA] = {}
        if isinstance(colors, dict):
            for entry_name, value in colors.items():
                entries[entry_name] = parse_rgba(value)
        elif isinstance(colors, list):
            for index, record in enumerate(colors):
                if not isinstance(record, dict):
                    raise PaletteError(f"colors[{index}] must be an object")
                entry_name = record.get("name")
                if not isinstance(entry_name, str) or not entry_name.strip():
                    raise PaletteError(f"colors[{index}].name must be a non-empty string")
                if entry_name in entries:
                    raise PaletteError(f"duplicate palette name: {entry_name!r}")
                entries[entry_name] = parse_rgba(record.get("value"))
        else:
            raise PaletteError("palette 'colors' must be an object or array")
        return cls(entries=entries, name=name)

    @classmethod
    def load(cls, path: Path) -> Palette:
        """Load and validate a UTF-8 JSON palette from ``path``."""
        if not path.is_file():
            raise PaletteError(f"palette file does not exist: {path}")
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text, object_pairs_hook=_unique_object)
        except OSError as error:
            raise PaletteError(f"could not read palette {path}: {error}") from error
        except json.JSONDecodeError as error:
            raise PaletteError(f"invalid JSON in palette {path}: {error}") from error
        return cls.from_data(data)

    def undeclared_colors(self, image: Image.Image) -> frozenset[RGBA]:
        """Return all image colors not present in this palette."""
        if image.mode != "RGBA":
            raise PaletteError(f"image mode must be RGBA, got {image.mode}")
        used = {
            cast(RGBA, image.getpixel((x, y)))
            for y in range(image.height)
            for x in range(image.width)
        }
        return frozenset(used - self.colors)


def partial_alpha_colors(image: Image.Image) -> frozenset[RGBA]:
    """Return colors whose alpha channel is neither fully clear nor opaque."""
    if image.mode != "RGBA":
        raise PaletteError(f"image mode must be RGBA, got {image.mode}")
    pixels = (
        cast(RGBA, image.getpixel((x, y))) for y in range(image.height) for x in range(image.width)
    )
    return frozenset(pixel for pixel in pixels if pixel[3] not in (0, 255))
