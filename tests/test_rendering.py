"""Tests for specification loading and ordered rendering."""

import json
from pathlib import Path

import pytest
from PIL import Image

from pixel_art_pipeline.geometry import Bounds, Point
from pixel_art_pipeline.primitives import filled_rectangle
from pixel_art_pipeline.renderer import (
    RenderLayer,
    SpecificationError,
    content_bounds,
    load_specification,
    render_frame,
    save_frame_sequence,
)


def _write_spec(tmp_path: Path, **overrides: object) -> Path:
    palette = tmp_path / "palette.json"
    palette.write_text('{"colors":{"clear":"#00000000","ink":"#000000FF"}}', encoding="utf-8")
    data: dict[str, object] = {
        "asset_name": "unit",
        "canvas": {"width": 4, "height": 4},
        "frame_count": 2,
        "frame_duration_ms": 100,
        "loop": True,
        "palette_path": "palette.json",
        "output_scale": 8,
        "background": "transparent",
        "anchor": {"x": 2, "y": 3},
        "layers": [{"name": "base", "order": 0}],
        "animation_tags": [{"name": "idle", "start": 0, "end": 1}],
        "random_seed": 7,
    }
    data.update(overrides)
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_specification_loading_and_validation(tmp_path: Path) -> None:
    specification = load_specification(_write_spec(tmp_path))
    assert specification.width == 4
    assert specification.anchor == Point(2, 3)
    assert specification.random_seed == 7


def test_invalid_specification_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SpecificationError, match="frame_count"):
        load_specification(_write_spec(tmp_path, frame_count=0))


def test_layer_ordering_and_content_bounds(tmp_path: Path) -> None:
    specification = load_specification(_write_spec(tmp_path))

    def red(image: Image.Image, frame_index: int) -> None:
        filled_rectangle(image, Point(1, 1), Point(2, 2), (255, 0, 0, 255))

    def blue(image: Image.Image, frame_index: int) -> None:
        image.putpixel((2, 2), (0, 0, 255, 255))

    frame = render_frame(
        specification,
        (RenderLayer("top", 2, blue), RenderLayer("bottom", 1, red)),
        0,
    )
    assert frame.getpixel((2, 2)) == (0, 0, 255, 255)
    assert content_bounds(frame) == Bounds(1, 1, 2, 2)


def test_save_frame_sequence_uses_padding_and_overwrite_control(tmp_path: Path) -> None:
    frames = (Image.new("RGBA", (2, 2)), Image.new("RGBA", (2, 2)))
    paths = save_frame_sequence(frames, tmp_path, asset_name="unit")
    assert [path.name for path in paths] == ["unit_0000.png", "unit_0001.png"]
    with pytest.raises(FileExistsError):
        save_frame_sequence(frames, tmp_path, asset_name="unit")
