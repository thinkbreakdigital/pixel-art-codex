# Creating animations

## 1. Define inputs

Add a strict RGBA palette JSON below `assets/palettes/`, then a specification below
`assets/specifications/`. Point `palette_path` to the palette relative to the specification. Run:

```bash
.venv/bin/python -m pixel_art_pipeline.cli validate-spec --spec assets/specifications/ASSET.json
```

## 2. Add a generator module

Create a focused module in your own application package (or beneath `src/pixel_art_pipeline/` only
when it is broadly reusable). Load the specification/palette; define `RenderLayer` callbacks using
functions from `primitives.py`; render exactly `frame_count` frames; and create a `FrameSequence`.
Do not add a predefined-art command to the shared CLI.

Use local seeded randomness only when the specification provides `random_seed`. Make phase and
motion values with animation helpers and integer interpolation. Keep every frame RGBA and identical
in size. Test layer order, bounds, anchors, colors, and repeated-render byte equality.

## 3. Export user-generated frames

If a generator writes its zero-padded frames to `build/frames`, export all supported artifacts with:

```bash
.venv/bin/python -m pixel_art_pipeline.cli export \
  --spec assets/specifications/ASSET.json \
  --input-frames build/frames \
  --output build
```

Use `--overwrite` only when replacing a known prior export. The command produces previews/sheets and
metadata from existing frames; it never generates predefined artwork.

## 4. Validate and inspect

```bash
.venv/bin/python -m pixel_art_pipeline.cli validate-assets \
  --spec assets/specifications/ASSET.json \
  --input-frames build/frames \
  --output build
make check
./scripts/open_in_pixelorama.sh build/sheets/ASSET_horizontal.png
```

For a PNG sequence, import/assemble frames manually in Pixelorama. Save a `.pxo` from the GUI if a
native editable project is required. Pixelorama can headlessly export an existing `.pxo`, but it
cannot create one through a verified CLI flag.

## 5. Add tests

Use Pillow images in memory and pytest's `tmp_path`. Cover invalid inputs as well as the successful
path: fixed hashes/bytes, clipping, palette and alpha compliance, frame alignment, content bounds,
sheet rectangles, metadata, and timing. Never write test outputs into `build/`, and assert that
overwrite protection behaves as intended.

