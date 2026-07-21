# Pipeline

## Inputs

Palette JSON uses strict `#RRGGBBAA` values. The `colors` field may be an object or an array of
`{"name": ..., "value": ...}` records. Duplicate names, malformed values, empty palettes, and
undeclared output pixels fail validation. Fully transparent colors are supported; alpha must be
either 0 or 255 in generated art.

A specification is a JSON object with this shape (field names are illustrative, not sample art):

```json
{
  "asset_name": "asset_identifier",
  "canvas": {"width": 32, "height": 32},
  "frame_count": 4,
  "frame_duration_ms": 100,
  "loop": true,
  "palette_path": "../palettes/palette.json",
  "output_scale": 8,
  "background": "transparent",
  "anchor": {"x": 16, "y": 31},
  "layers": [{"name": "base", "order": 0, "visible": true}],
  "animation_tags": [{"name": "default", "start": 0, "end": 3}],
  "random_seed": 0
}
```

Paths resolve relative to the specification. Dimensions/counts/scales are positive integers, the
anchor is on-canvas, layer names are unique, tag ranges are valid, and GIF-compatible duration is a
multiple of 10 ms. Validate before rendering with `validate-spec`.

## Rendering and animation

Generator modules create RGBA canvases with `create_canvas`, define ordered `RenderLayer`
callbacks, and call `render_frame`. Primitives accept integer coordinates, clip at the canvas, and
never resize or antialias. `content_bounds` tracks inclusive nontransparent bounds.

`animation.py` supplies uniform/per-frame timing, normalized phase progression, integer
interpolation, ping-pong indexes, directional mirroring, frame duplication, and inclusive range
selection. If procedural variation is needed, create a local `random.Random(spec.random_seed)`;
never depend on global random state, wall-clock time, locale, or unordered iteration.

## Export and validation

The exporter writes zero-padded PNG frames, horizontal/vertical/grid sheets, an animated GIF,
nearest-neighbor enlarged preview, contact sheet, and sorted JSON metadata. Metadata records frame
size/count/timing, loop duration, palette, filenames, sheet rectangles, content bounds, SHA-256
hashes, generator version, tags, and the Git commit when available. All output paths are preflighted
before an overwrite-protected bundle starts.

Validation covers RGBA mode, dimensions/count, palette and binary alpha, consistent anchors,
unexpected center movement, contiguous filenames, sheet size/rectangles, metadata/file hashes, and
GIF count/timing. Matching optional artifacts are checked when a specification and export root are
provided. An empty asset directory reports `no-assets` and succeeds; `--strict` makes it fail.

Recommended Codex workflow:

1. Add a palette and specification, then run `make validate`.
2. Add a focused generator module using existing components.
3. Render user-requested frames into `build/frames`.
4. Run the CLI `export`, then `validate-assets` with its spec.
5. Run `make check` and compare metadata hashes between repeated clean renders.
6. Open the desired output in Pixelorama for visual inspection.

To preserve determinism, pin dependencies, use integer arithmetic, stable ordering, fixed seeds,
explicit PNG settings, nearest-neighbor scaling, and compare SHA-256 values after repeated renders.

## Pixelorama integration (verified for v1.1.10)

The official release contains Godot 4.6.2. Engine options come before `--`; Pixelorama options and
files come after it. The installed program reported the following application CLI capabilities:

```bash
.tools/pixelorama/pixelorama --headless --quit -- --pixelorama-version
.tools/pixelorama/pixelorama --headless --quit -- PROJECT.pxo --framecount
.tools/pixelorama/pixelorama --headless --quit -- PROJECT.pxo --export --output OUTPUT.png
.tools/pixelorama/pixelorama --headless --quit -- PROJECT.pxo --spritesheet --output SHEET.png
```

Other verified Pixelorama options are `--size`, `--scale`, `--frames`, `--direction`, `--json`,
`--split-layers`, and `--sheet_layers_as_separate_files`. The wrapper does not hide or invent flags.

Relevant open formats include `.pxo`, PNG (including animated PNG detection), GIF, and common raster
images; the application also contains importers for OpenRaster, Aseprite, Krita, Piskel, and
Photoshop projects. Relevant export formats are PNG, WebP, JPEG, EXR, GIF, and APNG; MP4, AVI, OGV,
MKV, and WebM are offered when FFmpeg support is available. Sprite-sheet raster exports support
PNG, WebP, JPEG, and EXR.

There is no verified CLI save/create-`.pxo` command. Headless export is designed for an existing
project, particularly one saved with blended images when third-party/CLI export needs them. Passing
individual PNGs opens them, but no CLI option groups a PNG sequence into one animation; use the GUI
import flow. A sprite-sheet PNG opens, and slicing it into frames is a manual import operation.

