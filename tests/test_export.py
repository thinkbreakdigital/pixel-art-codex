"""Tests for deterministic export calculations and metadata."""

from pathlib import Path

import pytest
from PIL import Image

from pixel_art_pipeline.animation import FrameSequence
from pixel_art_pipeline.export import (
    build_metadata,
    build_sprite_sheet,
    save_nearest_preview,
    save_sprite_sheet,
    sha256_path,
    sprite_sheet_rectangles,
)
from pixel_art_pipeline.geometry import Bounds
from pixel_art_pipeline.palette import Palette
from pixel_art_pipeline.renderer import save_frame_sequence


def _frames() -> tuple[Image.Image, ...]:
    first = Image.new("RGBA", (2, 3), (0, 0, 0, 0))
    second = first.copy()
    first.putpixel((0, 0), (1, 2, 3, 255))
    second.putpixel((1, 2), (1, 2, 3, 255))
    return first, second


def test_sprite_sheet_rectangle_calculation() -> None:
    assert sprite_sheet_rectangles((2, 3), 2, layout="horizontal") == (
        Bounds(0, 0, 1, 2),
        Bounds(2, 0, 3, 2),
    )
    assert sprite_sheet_rectangles((2, 3), 2, layout="vertical")[1] == Bounds(0, 3, 1, 5)


def test_sprite_sheet_layer_placement() -> None:
    result = build_sprite_sheet(_frames(), layout="grid", columns=1)
    assert result.image.size == (2, 6)
    assert result.image.getpixel((1, 5)) == (1, 2, 3, 255)


def test_metadata_generation_and_sha256(tmp_path: Path) -> None:
    frames = _frames()
    frame_paths = save_frame_sequence(frames, tmp_path / "frames", asset_name="unit")
    sequence = FrameSequence.with_uniform_timing(frames, 80)
    palette = Palette({"clear": (0, 0, 0, 0), "ink": (1, 2, 3, 255)})
    rectangles = sprite_sheet_rectangles((2, 3), 2, layout="horizontal")
    metadata = build_metadata(sequence, frame_paths, palette=palette, sheet_rectangles=rectangles)
    assert metadata["frame_count"] == 2
    assert metadata["loop_duration_ms"] == 160
    assert metadata["frame_sha256"][0] == sha256_path(frame_paths[0])
    assert metadata["content_bounds"][1]["right"] == 1


def test_export_path_overwrite_and_nearest_scaling(tmp_path: Path) -> None:
    result = build_sprite_sheet(_frames())
    sheet_path = tmp_path / "sheet.png"
    save_sprite_sheet(result, sheet_path)
    with pytest.raises(FileExistsError):
        save_sprite_sheet(result, sheet_path)
    preview = tmp_path / "preview.png"
    save_nearest_preview(result.image, preview, scale=3)
    with Image.open(preview) as image:
        assert image.size == (12, 9)
