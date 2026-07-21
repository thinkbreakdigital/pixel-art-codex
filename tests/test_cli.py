"""Tests for documented CLI exit behavior."""

from pathlib import Path

from pixel_art_pipeline.cli import main


def test_validate_empty_assets_exit_codes(tmp_path: Path) -> None:
    assert main(["validate-assets", "--input-frames", str(tmp_path)]) == 0
    assert main(["validate-assets", "--input-frames", str(tmp_path), "--strict"]) == 1


def test_invalid_spec_path_returns_input_error(tmp_path: Path) -> None:
    assert main(["validate-spec", "--spec", str(tmp_path / "missing.json")]) == 1


def test_export_missing_input_returns_clear_error(tmp_path: Path) -> None:
    assert (
        main(
            [
                "export",
                "--spec",
                str(tmp_path / "missing.json"),
                "--input-frames",
                str(tmp_path / "frames"),
            ]
        )
        == 2
    )
