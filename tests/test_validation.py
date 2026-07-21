"""Tests for asset and artifact validation."""

from pathlib import Path

from PIL import Image

from pixel_art_pipeline.animation import FrameSequence
from pixel_art_pipeline.export import build_sprite_sheet, save_gif_preview
from pixel_art_pipeline.geometry import Point
from pixel_art_pipeline.palette import Palette
from pixel_art_pipeline.renderer import SpriteSpecification
from pixel_art_pipeline.validation import (
    validate_asset_directory,
    validate_frame_filenames,
    validate_frames,
    validate_gif,
    validate_metadata,
    validate_sprite_sheet,
)


def test_empty_asset_directory_succeeds_unless_strict(tmp_path: Path) -> None:
    assert validate_asset_directory(tmp_path).ok
    assert not validate_asset_directory(tmp_path, strict=True).ok


def test_alpha_palette_and_anchor_validation() -> None:
    frame = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    frame.putpixel((0, 0), (9, 9, 9, 127))
    palette = Palette({"clear": (0, 0, 0, 0)})
    report = validate_frames((frame,), palette=palette, anchors=(Point(5, 5),))
    codes = {issue.code for issue in report.errors}
    assert {"partial-alpha", "palette-compliance", "anchor-bounds"} <= codes


def test_inconsistent_dimensions_and_center_movement() -> None:
    first = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    second = Image.new("RGBA", (5, 4), (0, 0, 0, 0))
    first.putpixel((0, 0), (1, 1, 1, 255))
    second.putpixel((4, 0), (1, 1, 1, 255))
    report = validate_frames((first, second), center_tolerance=1)
    codes = {issue.code for issue in report.errors}
    assert "frame-dimensions" in codes
    assert "sprite-center-movement" in codes


def test_contiguous_frame_names() -> None:
    report = validate_frame_filenames((Path("unit_0000.png"), Path("unit_0002.png")))
    assert not report.ok


def test_sheet_dimensions_and_rectangles() -> None:
    frames = (
        Image.new("RGBA", (2, 2), (1, 1, 1, 255)),
        Image.new("RGBA", (2, 2), (2, 2, 2, 255)),
    )
    result = build_sprite_sheet(frames)
    assert validate_sprite_sheet(result.image, frame_size=(2, 2), rectangles=result.rectangles).ok


def test_gif_frame_count_and_timing(tmp_path: Path) -> None:
    first = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
    second = Image.new("RGBA", (2, 2), (0, 0, 255, 255))
    path = save_gif_preview(
        FrameSequence.with_uniform_timing((first, second), 70), tmp_path / "a.gif"
    )
    assert validate_gif(path, expected_count=2, expected_duration_ms=70).ok


def test_metadata_hash_mismatch_is_detected(tmp_path: Path) -> None:
    frame_path = tmp_path / "unit_0000.png"
    Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(frame_path)
    specification = SpriteSpecification(
        asset_name="unit",
        width=2,
        height=2,
        frame_count=1,
        frame_duration_ms=100,
        loop=True,
        palette_path=tmp_path / "palette.json",
        output_scale=1,
        background="transparent",
        anchor=Point(0, 0),
        layers=(),
        animation_tags=(),
    )
    metadata = {
        "frame_width": 2,
        "frame_height": 2,
        "frame_count": 1,
        "loop": True,
        "loop_duration_ms": 100,
        "frame_filenames": [frame_path.name],
        "frame_sha256": ["0" * 64],
    }
    report = validate_metadata(metadata, (frame_path,), specification)
    assert "deterministic-hashes" in {issue.code for issue in report.errors}
