# Project instructions for coding agents

These instructions apply to the entire repository. Use them whenever creating or modifying pixel
sprites, tiles, props, effects, palettes, animations, generators, exports, or related documentation.

## Mission

Use this repository as a deterministic, code-first pixel-art studio. Create only the art or reusable
pipeline behavior the user requests. Build source frames with Python and Pillow, validate them,
export review formats, and use Pixelorama for optional manual inspection or editing.

Do not add generic demo art, placeholder images, or predefined example characters. Do not use image
generation services, AI image APIs, traced third-party art, or non-free tools.

## Read before changing anything

1. Read `README.md`, `docs/PIPELINE.md`, `docs/ART_SPEC.md`, and
   `docs/CREATING_ANIMATIONS.md`.
2. Inspect `assets/palettes/`, `assets/specifications/`, existing generator modules, and nearby tests.
3. Inspect the relevant APIs in `src/pixel_art_pipeline/`; reuse them instead of duplicating them.
4. Run `git status --short` and preserve unrelated work.
5. Run `make info` when the installed Python or Pixelorama state matters.

If a user provides visual references, treat them as authoritative for silhouette, proportions,
palette relationships, pose, facing direction, timing, and identifying details. Record any necessary
interpretation in the specification or generator docstring. Never silently substitute a different
reference, mix incompatible reference versions, or invent unseen details that materially change the
requested design.

## Reference-consistency contract

Choose one lowercase, filesystem-safe `asset_name` and use it consistently. For an asset named
`<asset_name>`, prefer these locations:

- Specification: `assets/specifications/<asset_name>.json`
- Generator: `src/pixel_art_pipeline/generators/<asset_name>.py`
- Generator tests: `tests/test_<asset_name>.py`
- Frames: `build/frames/<asset_name>_0000.png`, increasing contiguously
- Sheets/previews/metadata: the same `<asset_name>` prefix under their existing `build/` folders

Palette files may be shared, but their filename and named entries are canonical references. A
specification's `palette_path` must resolve relative to that specification. Do not copy colors into
generator constants when a named palette entry exists.

Before rendering, verify all of the following agree across the brief, reference material, palette,
specification, generator, tests, frames, sheets, and metadata:

- Asset identifier and filenames
- Canvas width and height
- Frame count and zero-based frame indexes
- Frame duration, loop behavior, and inclusive animation-tag ranges
- Anchor coordinates and facing/orientation conventions
- Layer names, visibility, and ordering
- Palette entry names and exact `#RRGGBBAA` values
- Output scale, transparent/opaque background policy, and sheet layout
- Random seed, when procedural variation exists

When any canonical value changes, update every dependent reference in the same task. Search the
repository for the old identifier/value before finishing. Never leave stale paths, filenames, tag
ranges, palette names, expected hashes, documentation, or Pixelorama instructions.

Do not rename, move, or delete existing asset files unless the user requests it. If a rename is
requested, treat it as an atomic migration: update the palette/spec/generator/tests/docs together,
validate the new paths, and confirm the old references are gone.

## Art rules

- Work exclusively in RGBA with integer coordinates.
- Alpha values must be 0 or 255. Never introduce partial alpha.
- Use only colors declared by the selected palette.
- Do not antialias, blur, rotate with interpolation, or use subpixel transforms.
- Scale only with `Image.Resampling.NEAREST` or existing nearest-neighbor helpers.
- Keep every frame in a sequence the same size and aligned to the same anchor.
- Clip drawing safely at canvas boundaries; do not rely on Pillow's implicit behavior.
- Use stable layer ordering. When equal orders are unavoidable, preserve insertion order deliberately.
- Use a local `random.Random(spec.random_seed)` for requested procedural variation. Never use global
  random state, current time, nondeterministic iteration, or machine-specific input.
- Keep intentional center movement explicit and covered by an asset-specific test.
- Do not hardcode a specific character, prop, or animation into the shared CLI.

## Creating an asset or animation

1. Translate the user brief and references into explicit constraints: size, palette, poses, frame
   count, timing, loop, anchor, layers, tags, scale, and background.
2. Add or reuse a palette in `assets/palettes/`. Use strict `#RRGGBBAA` values and meaningful stable
   names such as `outline`, `shadow`, and `highlight`, not positional names like `color1`.
3. Add `assets/specifications/<asset_name>.json`. Keep `palette_path` relative and validate it before
   writing generator logic:

   ```bash
   .venv/bin/python -m pixel_art_pipeline.cli validate-spec \
     --spec assets/specifications/<asset_name>.json
   ```

4. Add an asset-focused generator module. Expose a small typed public function that accepts a
   validated `SpriteSpecification` and `Palette` and returns RGBA frames. Use `RenderLayer`, existing
   primitives, animation helpers, and `save_frame_sequence` rather than reimplementing them.
5. Render only into `build/frames/`. Generated images and metadata are ignored working artifacts and
   must not be committed.
6. Validate the frames before export:

   ```bash
   .venv/bin/python -m pixel_art_pipeline.cli validate-assets \
     --spec assets/specifications/<asset_name>.json \
     --input-frames build/frames
   ```

7. Export review artifacts without overwriting unknown work:

   ```bash
   .venv/bin/python -m pixel_art_pipeline.cli export \
     --spec assets/specifications/<asset_name>.json \
     --input-frames build/frames \
     --output build
   ```

   Use `--overwrite` only after confirming that every existing target belongs to the same asset and
   render revision.

8. Validate again with `--output build` so matching sheets, metadata, hashes, and GIF timing are
   checked.
9. Render the same inputs twice when generator logic changes and compare frame SHA-256 hashes. Equal
   inputs must produce equal hashes.

Do not add a generator command that creates a bundled sample. Asset-specific entry points belong in
the generator module or a narrowly scoped script only when the user requests one.

## Animation guidance

- Define the timing model before drawing in-between frames.
- Use `phase_progression`, `integer_interpolate`, `ping_pong_order`, frame selection, duplication,
  and directional mirroring from `animation.py` where they fit.
- Keep animation-tag ranges inclusive, zero-based, non-overlapping unless overlap is intentional,
  and within `frame_count`.
- GIF timing is quantized to 10 ms; specification durations must be multiples of 10 ms.
- Mirrored directions must preserve the declared anchor convention. Test asymmetric reference
  details so left/right outputs do not accidentally change identity.
- A deliberate traveling animation may move its content bounds, but the intended displacement must
  be documented and tested instead of disabling validation broadly.

## Visual-reference checks

Automated validation cannot judge likeness or readability. When reference images are available,
compare each required view at native resolution and at the declared nearest-neighbor preview scale.
Check silhouette first, then proportions/anchor, major color regions, contrast, identifying details,
and frame-to-frame motion. Keep the reference set unchanged during a revision unless the user
replaces it.

Do not open a GUI during unattended automation. When the user requests manual inspection, open an
existing file with:

```bash
make open FILE=/absolute/path/to/asset.png
```

Pixelorama can open `.pxo`, PNG, GIF, APNG, and sprite-sheet images. It cannot create a `.pxo`
noninteractively, and PNG sequences require manual import/assembly. Do not invent Pixelorama flags;
use the verified syntax in `docs/PIPELINE.md`.

## Tests and completion

Asset tests must use in-memory images or pytest's `tmp_path`; they must not leave files in the
repository. At minimum, cover palette compliance, binary alpha, frame dimensions/count, anchor and
layer consistency, content bounds, deterministic bytes/hashes, tag/timing behavior, and reference-
specific invariants such as silhouette points or key color regions.

Run the narrowest relevant tests while iterating, then finish with:

```bash
make validate
make check
```

Before reporting completion:

- Confirm requested source palettes, specifications, generators, and tests are present.
- Confirm no generated PNG, GIF, APNG, `.pxo`, sheet, preview, or metadata file is staged.
- Search for stale references after any identifier, palette, dimension, timing, anchor, layer, or tag
  change.
- Report validation/check results honestly and call out visual judgments that still need human review.
- Do not commit, push, create releases, or publish generated assets unless the user explicitly asks.

