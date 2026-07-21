"""Tests for reusable animation-sequence helpers."""

import pytest
from PIL import Image

from pixel_art_pipeline.animation import (
    FrameSequence,
    directional_mirror,
    duplicate_frames,
    integer_interpolate,
    phase_progression,
    ping_pong_order,
    select_frame_range,
)


def _frames() -> tuple[Image.Image, Image.Image]:
    first = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    second = first.copy()
    first.putpixel((0, 0), (1, 2, 3, 255))
    second.putpixel((1, 0), (1, 2, 3, 255))
    return first, second


def test_sequence_timing_and_phases() -> None:
    sequence = FrameSequence.with_uniform_timing(_frames(), 50)
    assert sequence.loop_duration_ms == 100
    assert phase_progression(4) == (0.0, 0.25, 0.5, 0.75)


def test_integer_interpolation_and_ping_pong() -> None:
    assert integer_interpolate(0, 10, 1, 2) == 5
    assert integer_interpolate(10, 0, 1, 2) == 5
    assert ping_pong_order(4) == (0, 1, 2, 3, 2, 1)


def test_mirroring_duplication_and_selection_copy_frames() -> None:
    frames = _frames()
    mirrored = directional_mirror(frames, "left")
    assert mirrored[0].getpixel((1, 0)) == (1, 2, 3, 255)
    assert len(duplicate_frames(frames, 3)) == 6
    selected = select_frame_range(frames, 1, 1)
    assert len(selected) == 1 and selected[0] is not frames[1]


def test_invalid_animation_ranges_fail() -> None:
    with pytest.raises(ValueError):
        select_frame_range(_frames(), 1, 2)
