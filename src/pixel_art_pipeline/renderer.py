"""Specification loading and ordered, integer-coordinate frame rendering."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from pixel_art_pipeline.geometry import Bounds, Point, require_int
from pixel_art_pipeline.palette import RGBA, Palette, PaletteError, rgba_to_hex


class SpecificationError(ValueError):
    """Raised when a sprite or animation specification is invalid."""


@dataclass(frozen=True, slots=True)
class AnimationTag:
    """A named inclusive frame range."""

    name: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise SpecificationError("animation tag name must not be empty")
        require_int(self.start, "tag start")
        require_int(self.end, "tag end")
        if self.start < 0 or self.end < self.start:
            raise SpecificationError(f"invalid animation tag range: {self.start}..{self.end}")


@dataclass(frozen=True, slots=True)
class LayerDefinition:
    """Declarative layer ordering and default visibility."""

    name: str
    order: int
    visible: bool = True


@dataclass(frozen=True, slots=True)
class SpriteSpecification:
    """Validated settings shared by render, export, and validation stages."""

    asset_name: str
    width: int
    height: int
    frame_count: int
    frame_duration_ms: int
    loop: bool
    palette_path: Path
    output_scale: int
    background: str
    anchor: Point
    layers: tuple[LayerDefinition, ...]
    animation_tags: tuple[AnimationTag, ...]
    random_seed: int | None = None

    def __post_init__(self) -> None:
        if not self.asset_name.strip():
            raise SpecificationError("asset_name must be a non-empty string")
        if any(character in self.asset_name for character in ("/", "\\", "\0")):
            raise SpecificationError("asset_name must not contain path separators")
        for name, value in (
            ("width", self.width),
            ("height", self.height),
            ("frame_count", self.frame_count),
            ("frame_duration_ms", self.frame_duration_ms),
            ("output_scale", self.output_scale),
        ):
            require_int(value, name)
            if value <= 0:
                raise SpecificationError(f"{name} must be positive")
        if not isinstance(self.loop, bool):
            raise SpecificationError("loop must be a boolean")
        if self.background not in {"transparent", "opaque"}:
            raise SpecificationError("background must be 'transparent' or 'opaque'")
        if self.frame_duration_ms % 10 != 0:
            raise SpecificationError("frame_duration_ms must be a multiple of 10 for GIF timing")
        if not (0 <= self.anchor.x < self.width and 0 <= self.anchor.y < self.height):
            raise SpecificationError("anchor must be inside the canvas")
        if self.random_seed is not None:
            require_int(self.random_seed, "random_seed")
        names = [layer.name for layer in self.layers]
        if any(not name.strip() for name in names) or len(names) != len(set(names)):
            raise SpecificationError("layer names must be non-empty and unique")
        for tag in self.animation_tags:
            if tag.end >= self.frame_count:
                raise SpecificationError(f"animation tag {tag.name!r} ends beyond frame_count")


RenderCallback = Callable[[Image.Image, int], None]


@dataclass(frozen=True, slots=True)
class RenderLayer:
    """A named callback rendered at an integer offset and explicit order."""

    name: str
    order: int
    render: RenderCallback
    offset: Point = field(default_factory=lambda: Point(0, 0))
    visible: bool = True


def _expect_mapping(data: object, field: str) -> Mapping[str, Any]:
    if not isinstance(data, dict):
        raise SpecificationError(f"{field} must be a JSON object")
    return data


def _expect_int(data: Mapping[str, Any], field: str, default: int | None = None) -> int:
    value = data.get(field, default)
    try:
        return require_int(value, field)
    except TypeError as error:
        raise SpecificationError(str(error)) from error


def specification_from_data(data: object, *, base_directory: Path) -> SpriteSpecification:
    """Validate a JSON-compatible sprite specification object."""
    root = _expect_mapping(data, "specification")
    canvas_value = root.get("canvas", {})
    canvas = _expect_mapping(canvas_value, "canvas")
    width = _expect_int(canvas, "width", root.get("canvas_width", root.get("width")))
    height = _expect_int(canvas, "height", root.get("canvas_height", root.get("height")))

    asset_name = root.get("asset_name")
    if not isinstance(asset_name, str):
        raise SpecificationError("asset_name must be a string")
    palette_value = root.get("palette_path")
    if not isinstance(palette_value, str) or not palette_value.strip():
        raise SpecificationError("palette_path must be a non-empty string")
    palette_path = (base_directory / palette_value).resolve()
    if not palette_path.is_file():
        raise SpecificationError(f"palette file does not exist: {palette_path}")
    try:
        Palette.load(palette_path)
    except PaletteError as error:
        raise SpecificationError(f"invalid palette: {error}") from error

    anchor_value = _expect_mapping(root.get("anchor", {}), "anchor")
    anchor = Point(_expect_int(anchor_value, "x", 0), _expect_int(anchor_value, "y", 0))

    layers_value = root.get("layers", [])
    if not isinstance(layers_value, list):
        raise SpecificationError("layers must be an array")
    layers: list[LayerDefinition] = []
    for index, item in enumerate(layers_value):
        record = _expect_mapping(item, f"layers[{index}]")
        name = record.get("name")
        visible = record.get("visible", True)
        if not isinstance(name, str) or not isinstance(visible, bool):
            raise SpecificationError(f"layers[{index}] has invalid name or visibility")
        layers.append(LayerDefinition(name, _expect_int(record, "order", index), visible))

    tags_value = root.get("animation_tags", [])
    if not isinstance(tags_value, list):
        raise SpecificationError("animation_tags must be an array")
    tags: list[AnimationTag] = []
    for index, item in enumerate(tags_value):
        record = _expect_mapping(item, f"animation_tags[{index}]")
        name = record.get("name")
        if not isinstance(name, str):
            raise SpecificationError(f"animation_tags[{index}].name must be a string")
        tags.append(AnimationTag(name, _expect_int(record, "start"), _expect_int(record, "end")))

    loop = root.get("loop", True)
    background = root.get("background", "transparent")
    seed = root.get("random_seed")
    if not isinstance(loop, bool) or not isinstance(background, str):
        raise SpecificationError("loop must be boolean and background must be a string")
    if seed is not None:
        try:
            seed = require_int(seed, "random_seed")
        except TypeError as error:
            raise SpecificationError(str(error)) from error
    return SpriteSpecification(
        asset_name=asset_name,
        width=width,
        height=height,
        frame_count=_expect_int(root, "frame_count"),
        frame_duration_ms=_expect_int(root, "frame_duration_ms"),
        loop=loop,
        palette_path=palette_path,
        output_scale=_expect_int(root, "output_scale", 1),
        background=background,
        anchor=anchor,
        layers=tuple(layers),
        animation_tags=tuple(tags),
        random_seed=seed,
    )


def load_specification(path: Path) -> SpriteSpecification:
    """Read and validate a sprite specification from JSON."""
    if not path.is_file():
        raise SpecificationError(f"specification file does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SpecificationError(f"could not read specification {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SpecificationError(f"invalid JSON in specification {path}: {error}") from error
    return specification_from_data(data, base_directory=path.parent)


def create_canvas(width: int, height: int, background: RGBA = (0, 0, 0, 0)) -> Image.Image:
    """Create a positive-sized RGBA canvas without antialiasing."""
    checked_width = require_int(width, "width")
    checked_height = require_int(height, "height")
    if checked_width <= 0 or checked_height <= 0:
        raise ValueError("canvas dimensions must be positive")
    rgba_to_hex(background)
    return Image.new("RGBA", (checked_width, checked_height), background)


def render_frame(
    specification: SpriteSpecification,
    layers: Sequence[RenderLayer],
    frame_index: int,
    *,
    background: RGBA | None = None,
) -> Image.Image:
    """Render one frame by compositing visible layers in stable order."""
    checked_index = require_int(frame_index, "frame_index")
    if not 0 <= checked_index < specification.frame_count:
        raise ValueError(f"frame_index must be in 0..{specification.frame_count - 1}")
    if background is None:
        if specification.background == "opaque":
            raise ValueError("opaque specifications require an explicit background color")
        background = (0, 0, 0, 0)
    canvas = create_canvas(specification.width, specification.height, background)
    for layer in sorted(enumerate(layers), key=lambda item: (item[1].order, item[0])):
        render_layer = layer[1]
        if not render_layer.visible:
            continue
        layer_canvas = create_canvas(specification.width, specification.height)
        render_layer.render(layer_canvas, checked_index)
        canvas.alpha_composite(
            layer_canvas,
            dest=(render_layer.offset.x, render_layer.offset.y),
        )
    return canvas


def content_bounds(image: Image.Image) -> Bounds | None:
    """Return inclusive bounds of nontransparent pixels, or ``None``."""
    if image.mode != "RGBA":
        raise ValueError(f"image mode must be RGBA, got {image.mode}")
    box = image.getchannel("A").getbbox()
    if box is None:
        return None
    left, top, right_exclusive, bottom_exclusive = box
    return Bounds(left, top, right_exclusive - 1, bottom_exclusive - 1)


def save_frame_sequence(
    frames: Sequence[Image.Image],
    output_directory: Path,
    *,
    asset_name: str,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    """Save a zero-padded PNG sequence and return its paths."""
    if not frames:
        raise ValueError("at least one frame is required")
    if not asset_name or any(character in asset_name for character in "/\\\0"):
        raise ValueError("asset_name must be a safe non-empty filename component")
    output_directory.mkdir(parents=True, exist_ok=True)
    padding = max(4, len(str(len(frames) - 1)))
    paths = tuple(
        output_directory / f"{asset_name}_{index:0{padding}d}.png" for index in range(len(frames))
    )
    conflicts = [path for path in paths if path.exists()]
    if conflicts and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing frame: {conflicts[0]}")
    expected_size = frames[0].size
    for index, (frame, path) in enumerate(zip(frames, paths, strict=True)):
        if frame.mode != "RGBA" or frame.size != expected_size:
            raise ValueError(f"frame {index} has inconsistent mode or dimensions")
        frame.save(path, format="PNG", optimize=False, compress_level=9)
    return paths
