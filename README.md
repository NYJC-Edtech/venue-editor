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
draw/add/remove venues, drag labels, metre readout, undo/redo, export SVG /
export JSON / import JSON, localStorage autosave, **Reset** restores the converted
data.

A live **scale bar** (bottom-right) picks a round distance (10 m, 20 m, 50 m …) that
stays readable at the current zoom, and wheel-zooming briefly shows the **print
ratio** (e.g. `1 : 740` — approximate, assumes a 96 dpi screen at 100 % browser
zoom).

## Parametric shapes (Inkscape-free venue editing)

Rooms may carry a `shape` record — stored in metadata.json alongside the generated
`outline`, so every existing consumer keeps working:

- **Rectangle** `{kind:"rect", c, w, h, rot}` — centre, width, height, rotation in
  degrees. On the map it gets corner nodes, side nodes and a green rotation node
  (Shift-drag = 15° steps). The nodes rotate **with** the shape; dragging a side or
  corner resizes along the rotated axes with the opposite edge/c corner anchored.
- **Circle / donut** `{kind:"ring", c, rOut, rIn, a0, a1}` — centre, outer & inner
  radius, arc start/end angles (degrees; 360 sweep = full). rIn 0 + full sweep is a
  circle; partial sweep gives pie / annulus-sector shapes; holes render via two
  subpaths.

Draw with **+ Rect** (R) or **+ Circle** (C) — creation is interrupt-free: no dialog,
the room appears immediately as "Room" (polygons likewise) and the Selection panel's
name field is focused for an immediate rename; categorise via the Type dropdown only
if you want the colour coding. Every node is labelled on-canvas (outer / inner /
start / end / rotate) and shape-coded: corners are squares, side nodes dots, the
inner-radius node a hollow ring, arc ends orange diamonds. The `outline` polygon and
`area_m2` are regenerated from the parameters on every edit (analytic area, no
shoelace approximation). Existing Inkscape-drawn polygon rooms can be migrated from
the properties panel: **→ Rect** fits the minimum-area rectangle (rotation detected),
**→ Circle** fits centre + mean radius. Parametric rooms show no vertex editing —
that's deliberate ("no full path editing").

Exported SVGs carry `data-shape='…'` on each parametric room for round-tripping.

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
