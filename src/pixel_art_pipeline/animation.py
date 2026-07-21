"""Reusable deterministic animation-sequence utilities."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image

from pixel_art_pipeline.geometry import require_int
from pixel_art_pipeline.primitives import mirror
from pixel_art_pipeline.renderer import AnimationTag


@dataclass(frozen=True, slots=True)
class FrameSequence:
    """An immutable collection of equally sized RGBA animation frames."""

    frames: tuple[Image.Image, ...]
    durations_ms: tuple[int, ...]
    loop: bool = True
    tags: tuple[AnimationTag, ...] = ()

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("frame sequence must not be empty")
        if len(self.frames) != len(self.durations_ms):
            raise ValueError("one duration is required for every frame")
        size = self.frames[0].size
        for index, (frame, duration) in enumerate(zip(self.frames, self.durations_ms, strict=True)):
            if frame.mode != "RGBA" or frame.size != size:
                raise ValueError(f"frame {index} has inconsistent mode or dimensions")
            require_int(duration, f"durations_ms[{index}]")
            if duration <= 0:
                raise ValueError("frame durations must be positive")
        if not isinstance(self.loop, bool):
            raise TypeError("loop must be a boolean")

    @classmethod
    def with_uniform_timing(
        cls,
        frames: Sequence[Image.Image],
        duration_ms: int,
        *,
        loop: bool = True,
        tags: Sequence[AnimationTag] = (),
    ) -> FrameSequence:
        """Construct a sequence using one duration for every frame."""
        checked_duration = require_int(duration_ms, "duration_ms")
        return cls(
            tuple(frame.copy() for frame in frames),
            tuple(checked_duration for _ in frames),
            loop,
            tuple(tags),
        )

    @property
    def loop_duration_ms(self) -> int:
        """Return total duration of one traversal."""
        return sum(self.durations_ms)


def phase_progression(frame_count: int, *, include_endpoint: bool = False) -> tuple[float, ...]:
    """Return stable normalized phases for an integer frame count."""
    count = require_int(frame_count, "frame_count")
    if count <= 0:
        raise ValueError("frame_count must be positive")
    if count == 1:
        return (0.0,)
    divisor = count - 1 if include_endpoint else count
    return tuple(index / divisor for index in range(count))


def integer_interpolate(start: int, end: int, numerator: int, denominator: int) -> int:
    """Interpolate using integer arithmetic with half-away-from-zero rounding."""
    start_value = require_int(start, "start")
    end_value = require_int(end, "end")
    step = require_int(numerator, "numerator")
    total = require_int(denominator, "denominator")
    if total <= 0 or not 0 <= step <= total:
        raise ValueError("require denominator > 0 and 0 <= numerator <= denominator")
    scaled = (end_value - start_value) * step
    adjustment = total // 2 if scaled >= 0 else -(total // 2)
    return start_value + int((scaled + adjustment) / total)


def ping_pong_order(frame_count: int, *, duplicate_endpoints: bool = False) -> tuple[int, ...]:
    """Return forward/backward indexes for a ping-pong animation."""
    count = require_int(frame_count, "frame_count")
    if count <= 0:
        raise ValueError("frame_count must be positive")
    if count == 1:
        return (0,)
    reverse_start = count - 1 if duplicate_endpoints else count - 2
    reverse_end = -1 if duplicate_endpoints else 0
    return (*range(count), *range(reverse_start, reverse_end, -1))


def directional_mirror(frames: Sequence[Image.Image], direction: str) -> tuple[Image.Image, ...]:
    """Mirror frames for ``left``/``up`` or copy them for ``right``/``down``."""
    if direction in {"right", "down"}:
        return tuple(frame.copy() for frame in frames)
    if direction == "left":
        return tuple(mirror(frame, axis="vertical") for frame in frames)
    if direction == "up":
        return tuple(mirror(frame, axis="horizontal") for frame in frames)
    raise ValueError("direction must be left, right, up, or down")


def duplicate_frames(frames: Sequence[Image.Image], copies: int) -> tuple[Image.Image, ...]:
    """Return each input frame repeated ``copies`` times as independent images."""
    checked_copies = require_int(copies, "copies")
    if checked_copies <= 0:
        raise ValueError("copies must be positive")
    return tuple(frame.copy() for frame in frames for _ in range(checked_copies))


def select_frame_range(
    frames: Sequence[Image.Image], start: int, end: int
) -> tuple[Image.Image, ...]:
    """Copy an inclusive, validated frame range."""
    start_index = require_int(start, "start")
    end_index = require_int(end, "end")
    if start_index < 0 or end_index < start_index or end_index >= len(frames):
        raise ValueError("invalid inclusive frame range")
    return tuple(frame.copy() for frame in frames[start_index : end_index + 1])
