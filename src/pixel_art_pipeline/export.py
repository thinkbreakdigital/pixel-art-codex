"""Deterministic PNG, sprite-sheet, GIF, preview, and metadata exports."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image

from pixel_art_pipeline import __version__
from pixel_art_pipeline.animation import FrameSequence
from pixel_art_pipeline.geometry import Bounds, require_int
from pixel_art_pipeline.palette import Palette
from pixel_art_pipeline.renderer import content_bounds, save_frame_sequence

SheetLayout = Literal["horizontal", "vertical", "grid"]


class ExportError(RuntimeError):
    """Raised when requested output cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class SheetResult:
    """A sprite sheet and the corresponding frame rectangles."""

    image: Image.Image
    rectangles: tuple[Bounds, ...]


def sha256_path(path: Path) -> str:
    """Calculate the SHA-256 digest of a regular file."""
    if not path.is_file():
        raise ExportError(f"cannot hash missing file: {path}")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise ExportError(f"could not hash {path}: {error}") from error
    return digest.hexdigest()


def _validate_frames(frames: Sequence[Image.Image]) -> tuple[int, int]:
    if not frames:
        raise ExportError("at least one frame is required")
    width, height = frames[0].size
    if width <= 0 or height <= 0:
        raise ExportError("frame dimensions must be positive")
    for index, frame in enumerate(frames):
        if frame.mode != "RGBA":
            raise ExportError(f"frame {index} mode must be RGBA, got {frame.mode}")
        if frame.size != (width, height):
            raise ExportError(f"frame {index} dimensions are inconsistent")
    return width, height


def sprite_sheet_rectangles(
    frame_size: tuple[int, int],
    frame_count: int,
    *,
    layout: SheetLayout,
    columns: int | None = None,
) -> tuple[Bounds, ...]:
    """Calculate inclusive frame rectangles for a sheet layout."""
    width, height = frame_size
    require_int(width, "frame width")
    require_int(height, "frame height")
    count = require_int(frame_count, "frame_count")
    if width <= 0 or height <= 0 or count <= 0:
        raise ValueError("frame dimensions and count must be positive")
    if layout == "horizontal":
        column_count = count
    elif layout == "vertical":
        column_count = 1
    elif layout == "grid":
        if columns is None:
            raise ValueError("columns is required for a grid sheet")
        column_count = require_int(columns, "columns")
        if column_count <= 0:
            raise ValueError("columns must be positive")
    else:
        raise ValueError(f"unsupported sheet layout: {layout}")
    return tuple(
        Bounds(
            (index % column_count) * width,
            (index // column_count) * height,
            (index % column_count + 1) * width - 1,
            (index // column_count + 1) * height - 1,
        )
        for index in range(count)
    )


def build_sprite_sheet(
    frames: Sequence[Image.Image],
    *,
    layout: SheetLayout = "horizontal",
    columns: int | None = None,
) -> SheetResult:
    """Build an RGBA sprite sheet without resizing or filtering."""
    frame_size = _validate_frames(frames)
    rectangles = sprite_sheet_rectangles(frame_size, len(frames), layout=layout, columns=columns)
    sheet_width = max(rectangle.right for rectangle in rectangles) + 1
    sheet_height = max(rectangle.bottom for rectangle in rectangles) + 1
    sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
    for frame, rectangle in zip(frames, rectangles, strict=True):
        sheet.alpha_composite(frame, dest=(rectangle.left, rectangle.top))
    return SheetResult(sheet, rectangles)


def _prepare_target(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)


def save_sprite_sheet(result: SheetResult, path: Path, *, overwrite: bool = False) -> Path:
    """Save a sprite-sheet result as a deterministic PNG."""
    _prepare_target(path, overwrite)
    result.image.save(path, format="PNG", optimize=False, compress_level=9)
    return path


def save_gif_preview(sequence: FrameSequence, path: Path, *, overwrite: bool = False) -> Path:
    """Save an animated GIF preview with explicit per-frame timing."""
    _prepare_target(path, overwrite)
    if any(duration % 10 != 0 for duration in sequence.durations_ms):
        raise ExportError("GIF frame durations must be multiples of 10 milliseconds")
    first, *remaining = sequence.frames
    loop_options: dict[str, Any] = {"loop": 0} if sequence.loop else {}
    try:
        first.save(
            path,
            format="GIF",
            save_all=True,
            append_images=list(remaining),
            duration=list(sequence.durations_ms),
            disposal=2,
            optimize=False,
            **loop_options,
        )
    except OSError as error:
        raise ExportError(f"could not export GIF {path}: {error}") from error
    return path


def save_nearest_preview(
    image: Image.Image, path: Path, *, scale: int, overwrite: bool = False
) -> Path:
    """Save an enlarged PNG using nearest-neighbor resampling only."""
    if image.mode != "RGBA":
        raise ExportError("preview source must use RGBA mode")
    checked_scale = require_int(scale, "scale")
    if checked_scale <= 0:
        raise ValueError("scale must be positive")
    _prepare_target(path, overwrite)
    resized = image.resize(
        (image.width * checked_scale, image.height * checked_scale),
        resample=Image.Resampling.NEAREST,
    )
    resized.save(path, format="PNG", optimize=False, compress_level=9)
    return path


def build_contact_sheet(
    frames: Sequence[Image.Image], *, columns: int, padding: int = 1
) -> SheetResult:
    """Build a transparent contact sheet separated by integer padding."""
    width, height = _validate_frames(frames)
    column_count = require_int(columns, "columns")
    checked_padding = require_int(padding, "padding")
    if column_count <= 0 or checked_padding < 0:
        raise ValueError("columns must be positive and padding non-negative")
    row_count = (len(frames) + column_count - 1) // column_count
    sheet = Image.new(
        "RGBA",
        (
            column_count * width + (column_count - 1) * checked_padding,
            row_count * height + (row_count - 1) * checked_padding,
        ),
        (0, 0, 0, 0),
    )
    rectangles: list[Bounds] = []
    for index, frame in enumerate(frames):
        left = (index % column_count) * (width + checked_padding)
        top = (index // column_count) * (height + checked_padding)
        sheet.alpha_composite(frame, dest=(left, top))
        rectangles.append(Bounds(left, top, left + width - 1, top + height - 1))
    return SheetResult(sheet, tuple(rectangles))


def current_git_commit(repository: Path) -> str | None:
    """Return the current Git commit, or ``None`` outside a committed repository."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value or None


def build_metadata(
    sequence: FrameSequence,
    frame_paths: Sequence[Path],
    *,
    palette: Palette,
    sheet_rectangles: Sequence[Bounds] = (),
    repository: Path | None = None,
) -> dict[str, Any]:
    """Build deterministic export metadata, including file hashes and bounds."""
    width, height = _validate_frames(sequence.frames)
    if len(frame_paths) != len(sequence.frames):
        raise ExportError("frame path count must match frame count")
    bounds_values: list[dict[str, int] | None] = []
    for frame in sequence.frames:
        bounds = content_bounds(frame)
        bounds_values.append(
            None
            if bounds is None
            else {
                "left": bounds.left,
                "top": bounds.top,
                "right": bounds.right,
                "bottom": bounds.bottom,
            }
        )
    metadata: dict[str, Any] = {
        "generator_version": __version__,
        "frame_width": width,
        "frame_height": height,
        "frame_count": len(sequence.frames),
        "frame_durations_ms": list(sequence.durations_ms),
        "loop": sequence.loop,
        "loop_duration_ms": sequence.loop_duration_ms,
        "palette": palette.to_json_values(),
        "frame_filenames": [path.name for path in frame_paths],
        "frame_sha256": [sha256_path(path) for path in frame_paths],
        "content_bounds": bounds_values,
        "animation_tags": [
            {"name": tag.name, "start": tag.start, "end": tag.end} for tag in sequence.tags
        ],
        "sheet_frame_rectangles": [
            {
                "left": bounds.left,
                "top": bounds.top,
                "right": bounds.right,
                "bottom": bounds.bottom,
            }
            for bounds in sheet_rectangles
        ],
    }
    if repository is not None:
        metadata["git_commit"] = current_git_commit(repository)
    return metadata


def save_metadata(data: dict[str, Any], path: Path, *, overwrite: bool = False) -> Path:
    """Save metadata as sorted, indented UTF-8 JSON."""
    _prepare_target(path, overwrite)
    try:
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise ExportError(f"could not write metadata {path}: {error}") from error
    return path


def load_png_frames(directory: Path) -> tuple[Image.Image, ...]:
    """Load a lexically ordered PNG frame directory into independent RGBA images."""
    if not directory.is_dir():
        raise ExportError(f"input frame directory does not exist: {directory}")
    paths = tuple(sorted(directory.glob("*.png")))
    if not paths:
        raise ExportError(f"no PNG frames found in {directory}")
    frames: list[Image.Image] = []
    for path in paths:
        try:
            with Image.open(path) as opened:
                opened.load()
                frames.append(opened.copy())
        except (OSError, ValueError) as error:
            raise ExportError(f"could not load frame {path}: {error}") from error
    return tuple(frames)


def export_bundle(
    sequence: FrameSequence,
    output_directory: Path,
    *,
    asset_name: str,
    palette: Palette,
    preview_scale: int = 8,
    overwrite: bool = False,
    repository: Path | None = None,
) -> dict[str, Path]:
    """Export frames, three sheets, GIF/nearest previews, contact sheet, and metadata."""
    if output_directory.exists() and not output_directory.is_dir():
        raise ExportError(f"output path is not a directory: {output_directory}")
    padding = max(4, len(str(len(sequence.frames) - 1)))
    expected_paths = [
        *(
            output_directory / "frames" / f"{asset_name}_{index:0{padding}d}.png"
            for index in range(len(sequence.frames))
        ),
        output_directory / "sheets" / f"{asset_name}_horizontal.png",
        output_directory / "sheets" / f"{asset_name}_vertical.png",
        output_directory / "sheets" / f"{asset_name}_grid.png",
        output_directory / "previews" / f"{asset_name}.gif",
        output_directory / "previews" / f"{asset_name}_nearest.png",
        output_directory / "previews" / f"{asset_name}_contact.png",
        output_directory / "metadata" / f"{asset_name}.json",
    ]
    if not overwrite:
        conflict = next((path for path in expected_paths if path.exists()), None)
        if conflict is not None:
            raise FileExistsError(f"refusing partial export; output already exists: {conflict}")
    frame_paths = save_frame_sequence(
        sequence.frames,
        output_directory / "frames",
        asset_name=asset_name,
        overwrite=overwrite,
    )
    horizontal = build_sprite_sheet(sequence.frames, layout="horizontal")
    vertical = build_sprite_sheet(sequence.frames, layout="vertical")
    grid_columns = max(1, int(len(sequence.frames) ** 0.5))
    grid = build_sprite_sheet(sequence.frames, layout="grid", columns=grid_columns)
    contact = build_contact_sheet(sequence.frames, columns=grid_columns, padding=1)
    paths = {
        "horizontal_sheet": save_sprite_sheet(
            horizontal,
            output_directory / "sheets" / f"{asset_name}_horizontal.png",
            overwrite=overwrite,
        ),
        "vertical_sheet": save_sprite_sheet(
            vertical,
            output_directory / "sheets" / f"{asset_name}_vertical.png",
            overwrite=overwrite,
        ),
        "grid_sheet": save_sprite_sheet(
            grid, output_directory / "sheets" / f"{asset_name}_grid.png", overwrite=overwrite
        ),
        "gif_preview": save_gif_preview(
            sequence, output_directory / "previews" / f"{asset_name}.gif", overwrite=overwrite
        ),
        "nearest_preview": save_nearest_preview(
            horizontal.image,
            output_directory / "previews" / f"{asset_name}_nearest.png",
            scale=preview_scale,
            overwrite=overwrite,
        ),
        "contact_sheet": save_sprite_sheet(
            contact,
            output_directory / "previews" / f"{asset_name}_contact.png",
            overwrite=overwrite,
        ),
    }
    metadata = build_metadata(
        sequence,
        frame_paths,
        palette=palette,
        sheet_rectangles=horizontal.rectangles,
        repository=repository,
    )
    paths["metadata"] = save_metadata(
        metadata,
        output_directory / "metadata" / f"{asset_name}.json",
        overwrite=overwrite,
    )
    return paths
