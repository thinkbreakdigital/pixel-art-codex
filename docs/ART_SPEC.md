# Art specification

1. Every coordinate, transform, dimension, radius, and anchor is an integer. Booleans are not
   accepted as integers. There is no subpixel placement or antialiasing.
2. Use RGBA canvases and only colors declared in the selected palette. Palette syntax is exactly
   `#RRGGBBAA`; transparency is explicit.
3. Alpha is binary: 0 or 255. Partial alpha is an error, including pixels introduced by an editor.
4. Fix canvas dimensions in the specification and keep them identical across every frame.
5. Anchors use top-left-origin `(x, y)` coordinates and must remain on-canvas and consistent across
   a sequence. Character/prop generators should align motion relative to the anchor.
6. Keep expected center motion within the validator tolerance. Intentional travel animations should
   configure or test their own movement policy rather than bypass validation silently.
7. Give every layer a unique semantic name and integer order. Stable insertion order breaks ties.
8. Enlarge only with nearest-neighbor resampling. Never resize a source frame during composition.
9. Store frame timing in milliseconds. GIF previews require multiples of 10 ms. Tags use inclusive,
   zero-based ranges and must remain inside `frame_count`.
10. Use lowercase safe asset identifiers. Frame files are `asset_name_0000.png`, contiguous from
    zero with at least four digits. Sheets and metadata retain the same asset-name prefix.
11. Keep generated files in `build/`; palettes/specifications belong in `assets/`. Do not commit
    exports unless a future repository policy explicitly changes this rule.

