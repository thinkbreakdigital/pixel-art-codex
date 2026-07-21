# pixel-art-codex

A deterministic, code-first Python foundation for pixel-art sprites and animations. It provides
integer geometry, strict palettes and JSON specifications, reusable drawing primitives, layered
rendering, animation helpers, exports, validation, and a verified portable Pixelorama install.
No character generator or example artwork is included.

Coding agents should read [`AGENTS.md`](AGENTS.md) before creating or changing sprites, palettes,
animations, generators, or asset references.

## Install

Requirements are Linux, Python 3.12 or newer, Git, `curl`, `tar`, `sha256sum`, and `make`.

```bash
cd ~/Documents/ThinkbreakDev/pixel-art-codex
make install
make check
```

`make install` creates `.venv`, installs the fully resolved versions in `requirements.lock`, resolves the latest
stable release from the official Pixelorama GitHub API, selects the current CPU architecture,
checks GitHub's published SHA-256 digest, rejects unsafe archive members, and installs the portable
application below `.tools/pixelorama/`. On Debian-family systems without `python3-venv`, the build
script creates a standard `--without-pip` venv and bootstraps pip from a PyPI wheel only after
checking the hash from PyPI metadata.

## Commands

```bash
make install                          # provision Python and Pixelorama
make validate                         # validate specs/assets; empty assets are valid
make test                             # run pytest
make check                            # Ruff, formatting, mypy, pytest, shell syntax
make info                             # show versions and resolved paths
make open FILE=/absolute/asset.png    # launch Pixelorama with an existing asset
make clean                            # remove generated outputs and caches only
```

The Python CLI can also be used directly:

```bash
.venv/bin/python -m pixel_art_pipeline.cli validate-spec --spec assets/specifications/name.json
.venv/bin/python -m pixel_art_pipeline.cli validate-assets --spec assets/specifications/name.json
.venv/bin/python -m pixel_art_pipeline.cli export --spec SPEC.json --input-frames FRAMES --output build
.venv/bin/python -m pixel_art_pipeline.cli clean
.venv/bin/python -m pixel_art_pipeline.cli info
```

Export refuses to overwrite by default; add `--overwrite` intentionally. `--preview-scale`,
`--palette`, `--strict`, `--output`, and global `--verbose` are available where applicable.

## Layout and extension points

- `assets/palettes/` and `assets/specifications/`: user-authored JSON inputs.
- `src/pixel_art_pipeline/`: geometry, palette, primitives, renderer, animation, export, validation,
  and CLI modules.
- `build/`: ignored generated frames, previews, sheets, metadata, and Pixelorama working files.
- `.tools/pixelorama/`: ignored portable installation; the wrapper discovers the binary regardless
  of the release archive's enclosing directory.
- `tests/`: in-memory and temporary-directory tests; no test images remain in the repository.
- `docs/`: pipeline, art rules, and generator workflow.
- `AGENTS.md`: repository-specific operating and reference-consistency rules for coding agents.

Future generators should be separate modules that accept a validated `SpriteSpecification` and
`Palette`, return RGBA Pillow frames, and contain no hard-coded example command in the main CLI.
Use `RenderLayer` callbacks and the existing primitives, then construct `FrameSequence`, call the
export API, and add asset-specific tests that write only to pytest's `tmp_path`.

## Pixelorama workflow and limitations

Open a `.pxo`, PNG, GIF, APNG, or PNG sprite sheet with:

```bash
./scripts/open_in_pixelorama.sh /absolute/path/to/asset.png
```

Pixelorama 1.1.10 accepts file arguments after Godot's `--` separator. Its verified CLI can export
an existing `.pxo` headlessly, but it has no option that creates/saves a `.pxo` noninteractively.
PNG sequences need manual import/assembly in the GUI; a sprite sheet opens as an image and can be
sliced with Pixelorama's import UI. See [docs/PIPELINE.md](docs/PIPELINE.md) for exact verified CLI
syntax and format details. Video exports depend on an available FFmpeg installation.

Generated formats have inherent limits: GIF timing is quantized to 10 ms, so specifications reject
other durations; GIF is a preview format with indexed color. The Python pipeline intentionally does
not generate `.pxo`, because Pixelorama does not publish a stable noninteractive creation command.
