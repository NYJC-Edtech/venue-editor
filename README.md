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
add features (staircase / room / marker, each with its own tool panel), metre
readout, undo/redo, export SVG / export JSON / import JSON, localStorage
autosave, **Reset** restores the converted data.

**Moving things is select-then-drag**: the first click on a room, marker or stair
run only selects it (accent-blue outline); only an **already-selected** shape
responds to a drag, so an accidental press-and-slide on an unselected shape never
shifts anything. Clicking empty space deselects (and pans); Esc deselects too.
**Undo/redo keep the selection**: the selected shape stays selected after a
history restore — re-found by id (rooms, stair runs) or content (markers), so it
even survives index shifts — and is deselected only when that undo/redo removed
it. **Space** is a second hotkey for the Select tool.

**Snap to vertex / edge**: while dragging a vertex or parametric handle (rect corner,
ring centre / inner / outer radius, arc start / end, polygon vertex, stair-run
node), the point snaps to the nearest other vertex on the floor — or, when no
vertex is in range, onto the nearest **edge** (projected onto the segment) —
within a configurable threshold — ⚙ **Settings** in the header has the on/off
checkbox and a threshold slider (screen pixels, persisted in localStorage); hold
**Alt** while dragging to bypass. A green ring marks the snapped target. A snapped
rect corner re-derives the rectangle from its fixed opposite corner, and ring
radii / arc angles follow the snapped handle. The dragged shape's own incident
edges are excluded from edge snapping, so nothing snaps to itself. The centre
handle wins press overlaps with the radius handles on small rings (it is drawn
last).

**Moving whole shapes snaps too**: dragging a room or stair run snaps its
vertices to nearby vertices / edge projections, and its edges align collinear
onto nearby parallel edges — the adjustment is perpendicular only, so shapes
with touching edges keep sliding against each other, and equal-sized rooms land
exactly adjacent (corner snaps onto corner). Snapping targets are **same-level
shapes only** — rooms and stair runs stored on the current floor; the ref-aligned
mirrors of other levels' shapes stay visible and editable but are never snap
targets (no cross-level snapping). Alignment candidates require the
edges to overlap along their direction, and already-touching alignments never
block vertex snaps.

A live **scale bar** (bottom-right) picks a round distance (10 m, 20 m, 50 m …) that
stays readable at the current zoom, and wheel-zooming briefly shows the **print
ratio** (e.g. `1 : 740` — approximate, assumes a 96 dpi screen at 100 % browser
zoom). Panning is pixel-matched 1:1: the drag is computed from raw screen-pixel
deltas and coalesced to animation frames — the SVG transform is never re-sampled
mid-drag (a stale CTM made the old pan oscillate) and nothing rebuilds per event.
The viewport is also aspect-locked (`view.w/clientWidth == view.h/clientHeight`
enforced on every fit and resize), so the SVG never letterboxes: units-per-screen-
px is exactly `view.w/clientWidth`, which pan, scale bar, marker and label sizing
all rely on. Pan and zoom are **clamped to the content**: after any pan or wheel
move the view still overlaps the floor's content by ≥ 20 % of the smaller side per
axis, and zoom is bounded to 1/100 – 10× of the content's largest dimension — a
stray scroll can never lose the plan, and panning back toward it always works. **← ↑ → ↓** nudge the selection by 1 unit (≈ 18.5 cm);
**Alt+arrow** = fine (0.05 u), **Shift+arrow** = coarse (10 u); a burst of nudges is
one undo step.

**Categories follow the venue enumeration** (`nyxchange-timetable-v2/fixtures/
venues.csv` → `venue_category`): AC / Non-AC Classrooms, Computer Rooms, Science
Labs, Phy Labs, Large Capacity Venues, Meeting Rooms, Special Rooms, Recording
Pods, Sports Facilities — plus plan-anatomy types (corridor, void, store …).
The Type dropdown offers only those two groups; the superseded legacy slugs
(classroom, lab, hall, music, wc …) are **not offered** — the load/import repair
pass remaps them to their canonical categories automatically and the status bar
reports the count. Entrance / exit rooms are likewise not offered (the marker
system represents those). The converter's `TYPE_RULES` emit the same canonical
vocabulary, and exported SVGs tint rooms with the same category colours as the
editor. The legend is drawn in screen-constant sizes — it does **not** change
when you zoom — with small non-overlapping marker icons, and it always paints
**above** every shape (with `pointer-events: none`, so it never blocks clicks).

**Switching storeys keeps the global zoom**: the viewport size and the position
relative to the floor's background origin survive level changes (keys 1–5 or the
floating selector) — and the **selection survives too** when the selected shape
exists on the new floor: multi-level rooms and stair runs re-select as their
mirror (the readout names the home storey), while markers deselect (they belong
to one floor). Parametric handles show rotation-aware cursors (corners/sides
pick the nearest of the 8 resize cursors based on the shape's rotation; radius and
arc nodes grab). **Ctrl+D** or the **Duplicate** button clones the selected room,
marker or stair run with a fresh id, offset by 8 units.

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

Draw with the **+ Room** panel — **Rect** (R) or **Circle / Donut** (C); creation is interrupt-free: no dialog,
the room appears immediately as "Room" (polygons likewise) and the Selection panel's
name field is focused for an immediate rename; categorise via the Type dropdown only
if you want the colour coding. Every node is labelled on-canvas (outer / inner /
start / end / rotate) and shape-coded: corners are squares, side nodes dots, the
inner-radius node a hollow ring, arc ends orange diamonds. The `outline` polygon and
`area_m2` are regenerated from the parameters on every edit (analytic area, no
shoelace approximation).

Conversion is **one-way into polygons**: rect and circle/donut rooms get a
**→ Polygon** button that bakes the shape into a plain outline (arcs at 240
segments; a full donut keeps its hole as a wound outer + inner-arc outline) and
removes the parametric handles — polygons have no way back. On load, a repair pass
also converts existing **rectangular polygons** into parametric Rects
(minimum-area rectangle fit; a polygon whose OBB area matches its own area within
1% is a rectangle) — the status bar reports the count and it runs once.

Exported SVGs carry `data-shape='…'` on each parametric room for round-tripping.

## Multi-level rooms

The Selection panel's **Height** dropdown (`room.height`, options 1 / 2 / 3,
default 1) says how many levels a room spans **vertically**, the room being
drawn once on its bottom storey. A room with height ≥ 2 renders ref-aligned
copies on the levels above — the same mirror machinery as stair runs: the
copies are editable views of the home room (selecting one selects it "on its
home storey", and dragging, resizing, node edits, delete and duplicate apply to
the one shared room). Native rooms of a floor take precedence over mirrors;
labels, legend categories, and derived restroom icons appear on every spanned
level; exports carry `data-height` on the home room and
`data-mirrored-from="storey N"` on each copy. A span reaching past the top
storey renders only the levels that exist (the readout notes the truncation).

This replaces the lt4-lower / lt4-upper hack: draw the lecture theatre once on
its lower storey, set Height to 2, and delete the duplicate room from the upper
storey. `convert_inkscape.py` preserves `height` (and `shape`, while the SVG
outline is unchanged) per room id across rebuilds.

## Multi-select & groups

**Shift+click** builds a multi-selection: holding Shift and clicking a shape adds
it, clicking a selected shape removes it again. Selected shapes **move together**
— by dragging any already-selected member or with **← ↑ → ↓** (same 1 / fine /
coarse steps) — but a loose multi-selection has **no resize**; vertex and
parametric handles belong to single selections only. Ctrl+D duplicates the whole
selection (fresh ids, offset copies), Del deletes it with one confirm, and
undo/redo keep every selected shape re-found (by id, or by content for markers).
Multi-selections are per-storey: switching floors clears them.

**Ctrl+G** (or the header **Group** button) groups the selection; **Ctrl+Shift+G**
(or **Ungroup**) dissolves it. Only **one level** of grouping exists, with
PowerPoint-style semantics: grouping a selection that already contains a group
**adds the loose shapes to that group** (several selected groups merge into one),
and a shape can belong to at most one group. Clicking any member selects the
**whole group**; clicking a member **while the group is selected** sub-selects
that member for individual editing (double-click works too).

A lone selected group renders a dashed bounding box with 8 handles and **resizes
as one** — along the group's OWN axes: when the member rooms share one rotation
(a uniform classroom row), the group keeps that `rot` (set automatically at
creation, or via the panel's **Rot** field), the bounding box and its handles
draw **rotated** with it, and dragging a handle scales every member's geometry
AND position along those axes about the fixed anchor corner/edge — rect rooms
scale w/h, circles and donuts stay circles (radii scale by the geometric mean of
the axis factors), polygon vertices, stair runs (access points stay on the run)
and markers all follow, and entrances are re-projected onto their venue edge.
Mixed-rotation groups keep an axis-aligned box until you align them. Group moves
snap like single moves: the union of the moved geometry snaps to same-level
vertices and edges, excluding every moved shape. Groups are fully usable through
a height-mirror: clicking the mirror upstairs selects the group (the readout
names the home storey) and drags/resizes apply to the shared home geometry.

**Sub-selection**: clicking a member while its group is selected drills into that
member — it becomes an ordinary single selection (handles, vertex editing,
Name/Type/Height panel, everything), while a press-*drag* on a member of the
selected group still moves the whole group. Click another member to jump back to
the group; Esc or empty-click clears.

**Direct text entry** (Selection panel): a selected rect room (or a sub-selected
group member) shows **Size** (length × width in metres, 2 d.p.) and **Rot**
(degrees, 1 d.p.) fields — type a value and press Enter. Rects set
`shape.w/h/rot` about their centre; polygons scale along their minimum-area OBB
axes and rotate about their area centroid (rings keep their radius/arc handles).
The selected **group** shows **Box** (length × width in metres — scales every
member and its position about the box centre) and **Rot** (align rotation —
sets every room in the group to the same angle; the bounding box follows; newly
added members are aligned to the group rotation automatically). All entries are
one undo step.

Groups live in metadata.json as a per-storey list
`storeys[f].groups = [{id, members:[{kind:"room"|"stair"|"marker", id}], rot?}]` —
members reference shapes **by id**, which is why markers now get stable ids
(`s{f}-mNN`, assigned silently by the repair pass and at placement). Deleting a
shape prunes it from its group (empty groups disappear), duplicating a group
clones it with a fresh group id (keeping `rot`), and exports carry `data-group`
on every member room, staircase and marker (plus `data-group-rot` when aligned;
markers also export their `id`). The converter preserves `groups` across rebuilds
like `ref` and `staircases`; members whose shapes a rebuild dropped (e.g. markers
are not imported) are pruned by the repair pass on next load. Groups whose
members span several storeys are refused (a group lives on one storey).

## Feature semantics

The toolbar adds **features**, not shapes: **+ Staircase**, **+ Room** and
**+ Marker**. Clicking one activates a per-feature tool panel at the top of the
sidebar (Select and ◎ Ref point keep their old roles); keyboard: V select ·
S staircase · R rect · C circle/donut · M marker · F ref point.

Marker kinds are **restroom, elevator, entrance** — entrance and exit are merged
into one kind (the two were never differentiated; old saves with `exit` markers
are migrated on load), and the old **staircase marker kind is gone** (staircase
access is part of the staircase feature, see below). Each kind carries a
position invariant that the editor enforces:

- **Entrances** mark the interface between two venues (the outdoors counts as the
  global venue), so an entrance must sit on/within a venue outline. Points placed
  more than ~1 unit (≈18 cm) from every outline are projected onto the nearest
  venue edge — at placement, while dragging, on nudge/duplicate, and once in a
  repair pass at load (the status bar reports what was moved).
- **Restrooms** are their own venue category (`restroom`, legacy `wc` rooms are
  migrated on load), but they are represented **only by their marker**: every
  restroom venue shows a marker at its centroid automatically (derived at render
  time, never stored, follows venue edits, and exported to SVG), the venue itself
  carries no category shading (it renders like an uncategorised room), and the
  legend lists Restroom once — as its marker row, not a colour swatch. Manual
  restroom markers in saved data are stripped on load.

### Staircases

A staircase is a **line feature** (never a polygon) that spans **exactly two
adjacent floors** — 1→2, 2→3, 3→4, 4→5. A real multi-level stairwell is one run
per storey pair, which is what makes its entrances/exits differentiable: on
storey 2 you see two separate access icons, "↓1" (arrived from 1) and "↑3"
(leads to 3), where the old model showed one undifferentiated staircase.

A run is stored on its **lower floor** as
`{id, name, lo, hi, points, lower, upper}` — `points` is the editable polyline
(the stair run as drawn), `lower`/`upper` are the two access points. Invariants:

- The line renders on **both** floors of its pair; the upper floor sees a
  ◎-ref-aligned mirror (`data-mirrored-from` in exports). Mirrors are fully
  editable — selecting one selects the home run (the panel and readout name the
  storey it lives on), and dragging/node edits apply to the one shared run.
- The lower access icon shows on the lower floor, the upper access icon on the
  upper floor — each badged with the floor it leads to (↑2 / ↓1). Placement
  snaps onto the run; node edits re-project the access points so they always
  sit on the line. The upper access is placed from the upper floor: the panel
  button switches storeys for you.
- Creation: draw the run on the **lower** floor (click each bend, Enter /
  double-click or "Finish run" to end, min 2 points); access points start at
  the run's ends and are re-placed from the panel. On the top storey the tool
  refuses (a run there must be drawn from the storey below).
- Line editing (panel + canvas): drag amber nodes, blue + inserts a node,
  Alt-click (or Delete node) removes one (min 2); once selected, drag the line
  to move the whole run with its access points.
- A run missing an access point renders **red** (editor-only halo + readout
  warning). Red is reserved for errors — the selection outline is the accent
  blue.

Old saves / imports with staircase **venues** (polygons with a `levels` range)
plus `stair` markers are migrated on load: each venue becomes one line run per
adjacent pair (centreline of the old outline), old stair markers inside it
become that pair's access points, and leftovers are stripped — the status bar
reports the migration.

## Icons

Marker glyphs (restroom, staircase, elevator, entrance) are **Google Material
Symbols** (the `wc`, `stairs`, `elevator`, `login` solid variants), drawn as
white discs with kind-coloured glyphs; staircase access icons add the ↑N/↓N
floor badge. The icon paths are embedded inline, so the editor still works fully
offline. License: **Apache 2.0** — free for any use; the license notice is
embedded next to the `GLYPH` constant in `editor_template.html` and in exported
SVGs. (Alternatives checked: Mapbox **Maki**, BSD/CC0 — no notice needed; Font
Awesome Free, CC BY 4.0 — attribution required. Material Symbols matched the
Google Maps look best.)

Support files: `bg-lvl1..5.png` (extracted backgrounds), `editor_template.html`
(build input), `editor-preview-*.png` (placement previews).
