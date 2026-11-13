# NYJC Floor Plans — Inkscape → Editor workflow

`nyjc-floor-plans.svg` (the Inkscape multi-page file: 5 pages, `lvl 1…5` background
layers, named venue shapes in the `locations` layer) is the **source of truth**.

## Rebuild after editing the SVG

```bash
python convert_inkscape.py          # regenerates metadata.json + editor.html
```

- Venue outlines are read from every labelled shape in the `locations` layer
  (rect/circle/ellipse/path/polygon; group transforms composed correctly, curves
  flattened). Page placement decides the floor.
- The background PNGs are extracted from the level layers and embedded in the editor.
- `metadata.json` gets one record per venue: outline in page units, area m², bbox
  width × depth in metres (minimum-area rectangle, so rotated rooms measure by their
  true sides), centroid, and a type inferred from the label (`TYPE_RULES` in the
  converter — edit there to re-classify).
- Add new venues in Inkscape: draw a shape, give it an `inkscape:label`, keep it in
  the `locations` layer, re-run the converter. Labels are the venue names.

## Scale

**1 SVG unit = 0.18522 m.** Derived chain: source drawings are **1:700** (title
blocks); the background PNGs are that A0 drawing at **200 dpi** (verified pixel-match
against the PDF, correlation 0.978) → 0.0889 m/px × 2.0835 px/unit. Cross-checks at
conversion time: tennis strip 553 u → 102.4 m, classroom 43×50 u → 8.0×9.3 m,
hall → 31.9×33.1 m. If you re-render or re-scale the backgrounds, pass `--dpi` (and
re-check the printed cross-checks).

## Editor

`editor.html` — single file, works offline from `file://`. Floating Google-Maps-style
storey selector on the right edge of the map (keys **1–5** also work), the faded
desaturated floor plan behind the venues (**plan** checkbox in the header hides it),
draw/add/remove venues, drag labels, vertex editing, metre readout (min-area rect, so
rotated rooms measure correctly), undo/redo, export SVG / export JSON / import JSON,
localStorage autosave, **Reset** restores the converted data.

A live **scale bar** (bottom-right) picks a round distance (10 m, 20 m, 50 m …) that
stays readable at the current zoom, and wheel-zooming briefly shows the **print
ratio** (e.g. `1 : 740` — approximate, assumes a 96 dpi screen at 100 % browser
zoom).

## Icons

Marker glyphs (restroom, staircase, elevator, entrance, exit) are **Google Material
Symbols** (the `wc`, `stairs`, `elevator`, `login`, `logout` solid variants), drawn as
white discs with kind-coloured glyphs. The icon paths are embedded inline, so the
editor still works fully offline. License: **Apache 2.0** — free for any use; the
license notice is embedded next to the `GLYPH` constant in `editor_template.html` and
in exported SVGs. (Alternatives checked: Mapbox **Maki**, BSD/CC0 — no notice needed;
Font Awesome Free, CC BY 4.0 — attribution required. Material Symbols matched the
Google Maps look best.)

Support files: `bg-lvl1..5.png` (extracted backgrounds), `editor_template.html`
(build input), `editor-preview-*.png` (placement previews).
