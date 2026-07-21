"""Validation of specifications, frames, sheets, metadata, and GIF previews."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from PIL import Image

from pixel_art_pipeline.export import sha256_path, sprite_sheet_rectangles
from pixel_art_pipeline.geometry import Bounds, Point
from pixel_art_pipeline.palette import Palette, partial_alpha_colors, rgba_to_hex
from pixel_art_pipeline.renderer import SpriteSpecification, content_bounds

Severity = Literal["info", "warning", "error"]
_FRAME_PATTERN = re.compile(r"^(?P<prefix>.+)_(?P<index>\d{4,})\.png$")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One structured validation finding."""

    severity: Severity
    code: str
    message: str


@dataclass(slots=True)
class ValidationReport:
    """Accumulated structured findings from one validation run."""

    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, severity: Severity, code: str, message: str) -> None:
        """Append a validation finding."""
        self.issues.append(ValidationIssue(severity, code, message))

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        """Return error-level findings."""
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def ok(self) -> bool:
        """Return whether the report contains no errors."""
        return not self.errors

    def extend(self, other: ValidationReport) -> None:
        """Append all findings from another report."""
        self.issues.extend(other.issues)


def validate_frame_filenames(paths: Sequence[Path]) -> ValidationReport:
    """Validate a contiguous, consistently prefixed, zero-padded frame sequence."""
    report = ValidationReport()
    if not paths:
        report.add("info", "no-frames", "no frame filenames to validate")
        return report
    matches = [_FRAME_PATTERN.fullmatch(path.name) for path in paths]
    if any(match is None for match in matches):
        report.add("error", "frame-name", "frame names must end in _0000.png style indexes")
        return report
    valid_matches = [match for match in matches if match is not None]
    prefixes = {match.group("prefix") for match in valid_matches}
    widths = {len(match.group("index")) for match in valid_matches}
    indexes = [int(match.group("index")) for match in valid_matches]
    if len(prefixes) != 1 or len(widths) != 1:
        report.add("error", "frame-name-consistency", "frame prefixes/padding are inconsistent")
    if indexes != list(range(len(indexes))):
        report.add("error", "frame-contiguous", "frame indexes must be contiguous from zero")
    return report


def validate_frames(
    frames: Sequence[Image.Image],
    *,
    expected_size: tuple[int, int] | None = None,
    expected_count: int | None = None,
    palette: Palette | None = None,
    anchors: Sequence[Point] | None = None,
    center_tolerance: int = 1,
) -> ValidationReport:
    """Validate frame mode, dimensions, colors, alpha, anchors, and center movement."""
    report = ValidationReport()
    if expected_count is not None and len(frames) != expected_count:
        report.add("error", "frame-count", f"expected {expected_count} frames, found {len(frames)}")
    if not frames:
        report.add("info", "no-frames", "no frames to validate")
        return report
    baseline_size = expected_size or frames[0].size
    bounds_values: list[Bounds | None] = []
    for index, frame in enumerate(frames):
        if frame.mode != "RGBA":
            report.add("error", "frame-mode", f"frame {index} mode is {frame.mode}, expected RGBA")
            continue
        if frame.size != baseline_size:
            report.add(
                "error",
                "frame-dimensions",
                f"frame {index} size is {frame.size}, expected {baseline_size}",
            )
        partial = partial_alpha_colors(frame)
        if partial:
            values = ", ".join(sorted(rgba_to_hex(color) for color in partial))
            report.add("error", "partial-alpha", f"frame {index} uses partial alpha: {values}")
        if palette is not None:
            undeclared = palette.undeclared_colors(frame)
            if undeclared:
                values = ", ".join(sorted(rgba_to_hex(color) for color in undeclared))
                report.add(
                    "error", "palette-compliance", f"frame {index} uses undeclared colors: {values}"
                )
        bounds_values.append(content_bounds(frame))
    if anchors is not None:
        if len(anchors) != len(frames):
            report.add("error", "anchor-count", "one anchor is required for each frame")
        elif len(set(anchors)) != 1:
            report.add("error", "anchor-consistency", "anchors differ between frames")
        for anchor in anchors:
            if not 0 <= anchor.x < baseline_size[0] or not 0 <= anchor.y < baseline_size[1]:
                report.add("error", "anchor-bounds", f"anchor is outside canvas: {anchor}")
    centers = [bounds.center for bounds in bounds_values if bounds is not None]
    if centers:
        first = centers[0]
        tolerance = max(0, center_tolerance)
        if any(
            abs(center.x - first.x) > tolerance or abs(center.y - first.y) > tolerance
            for center in centers[1:]
        ):
            report.add(
                "error",
                "sprite-center-movement",
                f"content center moved by more than {tolerance} pixel(s)",
            )
    return report


def validate_sprite_sheet(
    sheet: Image.Image,
    *,
    frame_size: tuple[int, int],
    rectangles: Sequence[Bounds],
) -> ValidationReport:
    """Validate sprite-sheet mode, dimensions, and non-overlapping frame rectangles."""
    report = ValidationReport()
    if sheet.mode != "RGBA":
        report.add("error", "sheet-mode", f"sprite sheet mode is {sheet.mode}, expected RGBA")
    if not rectangles:
        report.add("error", "sheet-rectangles", "sprite sheet has no frame rectangles")
        return report
    expected_width = max(bounds.right for bounds in rectangles) + 1
    expected_height = max(bounds.bottom for bounds in rectangles) + 1
    if sheet.size != (expected_width, expected_height):
        report.add(
            "error",
            "sheet-dimensions",
            f"sprite sheet size is {sheet.size}, expected {(expected_width, expected_height)}",
        )
    occupied: set[tuple[int, int]] = set()
    for index, bounds in enumerate(rectangles):
        if (bounds.width, bounds.height) != frame_size:
            report.add("error", "sheet-rectangle-size", f"rectangle {index} has wrong dimensions")
        cells = {
            (x, y)
            for y in range(bounds.top, bounds.bottom + 1)
            for x in range(bounds.left, bounds.right + 1)
        }
        if occupied.intersection(cells):
            report.add("error", "sheet-rectangle-overlap", f"rectangle {index} overlaps")
        occupied.update(cells)
    return report


def validate_metadata(
    metadata: dict[str, Any], frame_paths: Sequence[Path], specification: SpriteSpecification
) -> ValidationReport:
    """Validate metadata fields against the specification and frame files."""
    report = ValidationReport()
    expected: dict[str, Any] = {
        "frame_width": specification.width,
        "frame_height": specification.height,
        "frame_count": specification.frame_count,
        "loop": specification.loop,
        "loop_duration_ms": specification.frame_count * specification.frame_duration_ms,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            report.add("error", "metadata-consistency", f"metadata {key!r} does not match")
    filenames = metadata.get("frame_filenames")
    if filenames != [path.name for path in frame_paths]:
        report.add("error", "metadata-filenames", "metadata frame filenames do not match")
    hashes = metadata.get("frame_sha256")
    if hashes != [sha256_path(path) for path in frame_paths]:
        report.add("error", "deterministic-hashes", "metadata frame SHA-256 hashes do not match")
    return report


def validate_gif(path: Path, *, expected_count: int, expected_duration_ms: int) -> ValidationReport:
    """Validate animated GIF frame count and per-frame timing."""
    report = ValidationReport()
    if not path.is_file():
        report.add("error", "gif-missing", f"GIF does not exist: {path}")
        return report
    durations: list[int] = []
    try:
        with Image.open(path) as image:
            count = getattr(image, "n_frames", 1)
            for index in range(count):
                image.seek(index)
                durations.append(int(image.info.get("duration", 0)))
    except (OSError, ValueError) as error:
        report.add("error", "gif-read", f"could not read GIF: {error}")
        return report
    if len(durations) != expected_count:
        report.add("error", "gif-frame-count", f"GIF contains {len(durations)} frames")
    if any(duration != expected_duration_ms for duration in durations):
        report.add("error", "gif-timing", f"GIF durations are {durations}")
    return report


def load_frame_files(paths: Sequence[Path]) -> tuple[Image.Image, ...]:
    """Load frame files for validation while retaining original modes."""
    frames: list[Image.Image] = []
    for path in paths:
        try:
            with Image.open(path) as image:
                image.load()
                frames.append(image.copy())
        except (OSError, ValueError) as error:
            raise ValueError(f"could not read frame {path}: {error}") from error
    return tuple(frames)


def validate_asset_directory(
    directory: Path,
    *,
    specification: SpriteSpecification | None = None,
    palette: Palette | None = None,
    strict: bool = False,
) -> ValidationReport:
    """Validate user-generated PNG frames, succeeding when empty unless strict."""
    report = ValidationReport()
    if not directory.exists():
        message = f"no assets to validate; directory does not exist: {directory}"
        report.add("error" if strict else "info", "no-assets", message)
        return report
    if not directory.is_dir():
        report.add("error", "asset-path", f"asset path is not a directory: {directory}")
        return report
    paths = tuple(sorted(directory.glob("*.png")))
    if not paths:
        report.add(
            "error" if strict else "info",
            "no-assets",
            f"no assets to validate in {directory}",
        )
        return report
    report.extend(validate_frame_filenames(paths))
    try:
        frames = load_frame_files(paths)
    except ValueError as error:
        report.add("error", "frame-read", str(error))
        return report
    expected_size = None
    expected_count = None
    anchors = None
    if specification is not None:
        expected_size = (specification.width, specification.height)
        expected_count = specification.frame_count
        anchors = tuple(specification.anchor for _ in frames)
    report.extend(
        validate_frames(
            frames,
            expected_size=expected_size,
            expected_count=expected_count,
            palette=palette,
            anchors=anchors,
        )
    )
    return report


def validate_export_artifacts(
    output_directory: Path,
    frame_paths: Sequence[Path],
    specification: SpriteSpecification,
) -> ValidationReport:
    """Validate matching sheets, metadata, and GIF when those exports exist."""
    report = ValidationReport()
    name = specification.asset_name
    metadata_path = output_directory / "metadata" / f"{name}.json"
    if metadata_path.is_file():
        try:
            metadata = load_metadata(metadata_path)
        except ValueError as error:
            report.add("error", "metadata-read", str(error))
        else:
            report.extend(validate_metadata(metadata, frame_paths, specification))

    horizontal_path = output_directory / "sheets" / f"{name}_horizontal.png"
    if horizontal_path.is_file():
        try:
            with Image.open(horizontal_path) as opened:
                opened.load()
                sheet = opened.copy()
        except (OSError, ValueError) as error:
            report.add("error", "sheet-read", f"could not read sprite sheet: {error}")
        else:
            rectangles = sprite_sheet_rectangles(
                (specification.width, specification.height),
                specification.frame_count,
                layout="horizontal",
            )
            report.extend(
                validate_sprite_sheet(
                    sheet,
                    frame_size=(specification.width, specification.height),
                    rectangles=rectangles,
                )
            )

    gif_path = output_directory / "previews" / f"{name}.gif"
    if gif_path.is_file():
        report.extend(
            validate_gif(
                gif_path,
                expected_count=specification.frame_count,
                expected_duration_ms=specification.frame_duration_ms,
            )
        )
    return report


def load_metadata(path: Path) -> dict[str, Any]:
    """Load an export metadata JSON object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not load metadata {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("metadata root must be an object")
    return data
