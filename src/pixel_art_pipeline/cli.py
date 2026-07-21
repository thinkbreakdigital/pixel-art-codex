"""Command-line interface for validation, export, cleanup, and environment info."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from pixel_art_pipeline.animation import FrameSequence
from pixel_art_pipeline.export import ExportError, export_bundle, load_png_frames
from pixel_art_pipeline.palette import Palette, PaletteError
from pixel_art_pipeline.renderer import (
    SpecificationError,
    SpriteSpecification,
    load_specification,
)
from pixel_art_pipeline.validation import (
    ValidationReport,
    validate_asset_directory,
    validate_export_artifacts,
    validate_frames,
)

LOGGER = logging.getLogger("pixel_art_pipeline")


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _path(value: str) -> Path:
    path = Path(value).expanduser()
    if "\0" in value:
        raise argparse.ArgumentTypeError("paths must not contain null bytes")
    return path.resolve()


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s level=%(levelname)s event=%(message)s",
    )


def _print_report(report: ValidationReport) -> None:
    for issue in report.issues:
        print(f"{issue.severity.upper()} [{issue.code}] {issue.message}")


def _load_optional_context(
    specification_path: Path | None, palette_path: Path | None
) -> tuple[SpriteSpecification | None, Palette | None]:
    specification = (
        load_specification(specification_path) if specification_path is not None else None
    )
    resolved_palette = palette_path
    if resolved_palette is None and specification is not None:
        resolved_palette = specification.palette_path
    palette = Palette.load(resolved_palette) if resolved_palette is not None else None
    return specification, palette


def command_validate_spec(args: argparse.Namespace) -> int:
    """Validate one specification or every JSON specification in the repository."""
    repository = _repository_root()
    paths = (
        [args.spec]
        if args.spec is not None
        else sorted((repository / "assets" / "specifications").glob("*.json"))
    )
    if not paths:
        print("INFO [no-specifications] no specifications to validate")
        return 0
    failed = False
    for path in paths:
        try:
            specification = load_specification(path)
        except (SpecificationError, PaletteError) as error:
            failed = True
            print(f"ERROR [invalid-specification] {path}: {error}")
        else:
            print(
                f"INFO [valid-specification] {path}: "
                f"{specification.frame_count} frame(s), "
                f"{specification.width}x{specification.height}"
            )
    return 1 if failed else 0


def command_validate_assets(args: argparse.Namespace) -> int:
    """Validate a user-generated frame directory."""
    specification, palette = _load_optional_context(args.spec, args.palette)
    report = validate_asset_directory(
        args.input_frames,
        specification=specification,
        palette=palette,
        strict=args.strict,
    )
    frame_paths = tuple(sorted(args.input_frames.glob("*.png")))
    if specification is not None and frame_paths:
        report.extend(validate_export_artifacts(args.output, frame_paths, specification))
    _print_report(report)
    return 0 if report.ok else 1


def command_export(args: argparse.Namespace) -> int:
    """Export user-provided frames according to a validated specification."""
    specification = load_specification(args.spec)
    palette = Palette.load(args.palette or specification.palette_path)
    frames = load_png_frames(args.input_frames)
    preflight = validate_frames(
        frames,
        expected_size=(specification.width, specification.height),
        expected_count=specification.frame_count,
        palette=palette,
        anchors=tuple(specification.anchor for _ in frames),
    )
    if not preflight.ok:
        _print_report(preflight)
        return 1
    sequence = FrameSequence.with_uniform_timing(
        frames,
        specification.frame_duration_ms,
        loop=specification.loop,
        tags=specification.animation_tags,
    )
    outputs = export_bundle(
        sequence,
        args.output,
        asset_name=specification.asset_name,
        palette=palette,
        preview_scale=args.preview_scale,
        overwrite=args.overwrite,
        repository=_repository_root(),
    )
    for output_type, path in sorted(outputs.items()):
        LOGGER.info("exported type=%s path=%s", output_type, path)
    return 0


def clean_generated(repository: Path) -> None:
    """Remove generated outputs and caches while preserving tools and sentinels."""
    build_directory = repository / "build"
    for output_name in ("frames", "previews", "sheets", "metadata", "pixelorama"):
        output_directory = build_directory / output_name
        if not output_directory.is_dir():
            continue
        for child in output_directory.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    for cache_name in (".pytest_cache", ".mypy_cache", ".ruff_cache"):
        cache_path = repository / cache_name
        if cache_path.is_dir():
            shutil.rmtree(cache_path)
    for cache_path in repository.rglob("__pycache__"):
        if ".venv" not in cache_path.parts and cache_path.is_dir():
            shutil.rmtree(cache_path)


def command_clean(args: argparse.Namespace) -> int:
    """Clean generated repository outputs."""
    clean_generated(_repository_root())
    LOGGER.info("cleaned repository=%s", _repository_root())
    return 0


def _pixelorama_wrapper(repository: Path) -> Path | None:
    candidate = repository / ".tools" / "pixelorama" / "pixelorama"
    return candidate if candidate.is_file() and candidate.stat().st_mode & 0o111 else None


def command_info(args: argparse.Namespace) -> int:
    """Report versions, paths, and available commands."""
    repository = _repository_root()
    wrapper = _pixelorama_wrapper(repository)
    version_file = repository / ".tools" / "pixelorama" / "VERSION"
    pixelorama_version = (
        version_file.read_text(encoding="utf-8").strip()
        if version_file.is_file()
        else "not installed"
    )
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Pixelorama version: {pixelorama_version}")
    print(f"Repository path: {repository}")
    print(f"Virtual environment: {Path(sys.prefix).resolve()}")
    print(f"Pixelorama executable: {wrapper or 'not installed'}")
    print("CLI commands: validate-spec, validate-assets, export, clean, info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the complete CLI parser."""
    parser = argparse.ArgumentParser(
        prog="pixel-art",
        description="Deterministic pixel-art validation and export pipeline",
    )
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_spec = subparsers.add_parser("validate-spec", help="validate JSON specifications")
    validate_spec.add_argument("--spec", type=_path, help="specification JSON path")
    validate_spec.set_defaults(handler=command_validate_spec)

    validate_assets = subparsers.add_parser("validate-assets", help="validate generated frames")
    validate_assets.add_argument(
        "--input-frames",
        type=_path,
        default=_repository_root() / "build" / "frames",
        help="frame directory (default: build/frames)",
    )
    validate_assets.add_argument("--spec", type=_path, help="specification JSON path")
    validate_assets.add_argument("--palette", type=_path, help="palette JSON override")
    validate_assets.add_argument(
        "--output",
        type=_path,
        default=_repository_root() / "build",
        help="export root containing optional sheets, previews, and metadata",
    )
    validate_assets.add_argument("--strict", action="store_true", help="fail when no assets exist")
    validate_assets.set_defaults(handler=command_validate_assets)

    export_parser = subparsers.add_parser("export", help="export existing user-generated frames")
    export_parser.add_argument("--spec", type=_path, required=True, help="specification JSON path")
    export_parser.add_argument(
        "--input-frames", type=_path, required=True, help="input PNG frame directory"
    )
    export_parser.add_argument(
        "--output",
        type=_path,
        default=_repository_root() / "build",
        help="output root (default: build)",
    )
    export_parser.add_argument("--palette", type=_path, help="palette JSON override")
    export_parser.add_argument("--preview-scale", type=int, default=8)
    export_parser.add_argument("--overwrite", action="store_true")
    export_parser.set_defaults(handler=command_export)

    clean_parser = subparsers.add_parser("clean", help="remove generated outputs and caches")
    clean_parser.set_defaults(handler=command_clean)

    info_parser = subparsers.add_parser("info", help="report environment and tool paths")
    info_parser.set_defaults(handler=command_info)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a documented process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    try:
        return int(args.handler(args))
    except (SpecificationError, PaletteError, ExportError, ValueError, OSError) as error:
        LOGGER.error("failed command=%s error=%s", args.command, error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
