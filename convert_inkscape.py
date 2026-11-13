#!/usr/bin/env python3
"""Convert the Inkscape multi-page floor-plan SVG into editor data.

Input : nyjc-floor-plans.svg  (5 pages, layers lvl 1..5 with background PNGs,
        one 'locations' layer holding named venue shapes)
Output: metadata.json  (venues per floor + embedded background images + scale)
        editor.html    (single-file editor with the converted data embedded)

Re-run any time the SVG changes:
    python convert_inkscape.py

Scale is inferred from the drawing chain: the background images are renders of
the original 1:700 A0 drawings (title-block scale), stretched across the page
width.  --dpi is the resolution at which those background PNGs were produced
(200 by default - verified against the source PDF).  Cross-checks are printed
so a future re-run flags any scale drift.
"""
import argparse, base64, json, math, re, sys
import xml.etree.ElementTree as ET

NS = {"svg": "http://www.w3.org/2000/svg",
      "inkscape": "http://www.inkscape.org/namespaces/inkscape",
      "xlink": "http://www.w3.org/1999/xlink"}
INV = {k: f"{{{v}}}" for k, v in NS.items()}

# venue-type inference from labels (first match wins)
TYPE_RULES = [
    (r"lt\d|lecture theatre|ava",            "lecture-theatre"),
    (r"chem lab|phy lab|bio lab|lab\b|robotics|science", "lab"),
    (r"comp lab|itr\b|computer",             "computer-lab"),
    (r"canteen",                             "canteen"),
    (r"hall\b|auditorium|mpr",               "hall"),
    (r"library|reading",                     "library"),
    (r"music|choir|guzheng|orchestra|band|dance|drama", "music"),
    (r"gym|squash|sports|tennis|court|badminton|track", "sports-hall"),
    (r"wc|toilet|washroom|bathroom|shower",  "wc"),
    (r"stair",                               "stair-hall"),
    (r"lift|elevator",                       "lift"),
    (r"entrance|entry|gate|foyer|lobby",     "lobby"),
    (r"exit|egress",                         "exit"),
    (r"office|staff|hod|council|confab|workroom|alumni|clinic|first aid|counsell", "office"),
    (r"atrium|courtyard|plaza|parade|field|track|playground|open|terrace|concourse|quad", "open-area"),
    (r"store|storeroom|storage",             "store"),
    (r"study|ispace|reading area",           "study-area"),
    (r"art|craft|aep|studio|clep",           "classroom"),
    (r"^\d+-\d+|classroom|tutorial|lecture room|cca|club|society", "classroom"),
]
SKIP_LABELS = {"drum-template"}          # construction templates, not venues

def label_type(label):
    for pat, t in TYPE_RULES:
        if re.search(pat, label, re.IGNORECASE):
            return t
    return "room"

# ---------------------------------------------------------------- transforms
IDENT = (1, 0, 0, 1, 0, 0)
def mmul(A, B):
    """matrix product A·B (A applied after B)"""
    a1, b1, c1, d1, e1, f1 = A
    a2, b2, c2, d2, e2, f2 = B
    return (a1*a2 + c1*b2, b1*a2 + d1*b2,
            a1*c2 + c1*d2, b1*c2 + d1*d2,
            a1*e2 + c1*f2 + e1, b1*e2 + d1*f2 + f1)

def parse_tf(s):
    M = IDENT
    if not s:
        return M
    for name, argstr in re.findall(r"(\w+)\s*\(([^)]*)\)", s):
        v = [float(x) for x in re.split(r"[\s,]+", argstr.strip()) if x]
        if name == "translate":
            T = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "matrix":
            T = tuple(v[:6])
        elif name == "scale":
            T = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a = math.radians(v[0])
            T = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:  # rotate about a point
                M = mmul(M, (1, 0, 0, 1, v[1], v[2]))
                M = mmul(M, T)
                T = (1, 0, 0, 1, -v[1], -v[2])
        elif name == "skewX":
            T = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            T = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            T = IDENT
        M = mmul(M, T)
    return M

def apply(M, x, y):
    a, b, c, d, e, f = M
    return (a*x + c*y + e, b*x + d*y + f)

# ---------------------------------------------------------------- path data
def _nargs(c):
    return {"M":2,"L":2,"H":1,"V":1,"C":6,"S":4,"Q":4,"T":2,"A":7,"Z":0}[c]

def _cubic(p0, p1, p2, p3, t):
    u = 1 - t
    return (u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
            u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1])

def _quad(p0, p1, p2, t):
    u = 1 - t
    return (u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0], u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1])

def flatten_d(d, steps=10):
    """flatten an SVG path 'd' into subpaths of points.
    Handles M/L/H/V/Z absolutely and relatively; C/S/Q/T curves are sampled;
    A (arc) is approximated by its chord midpoint + endpoint."""
    out = []          # ordered tokens: command letters and numbers
    for cmd, num in re.findall(r"([MmLlHhVvCcSsQqTtAaZz])|(-?\d*\.?\d+(?:e[-+]?\d+)?)", d, re.IGNORECASE):
        out.append(cmd if cmd else float(num))

    subpaths, cur = [], []
    pos = start = (0.0, 0.0)
    prev_ctrl = None            # last cubic/quadratic control point (absolute)
    i, cmd = 0, None
    while i < len(out):
        t = out[i]
        if isinstance(t, str):
            cmd, i = t, i + 1
            if cmd in "Zz":
                if cur:
                    subpaths.append(cur)
                    cur = []
                pos = start
                prev_ctrl = None
            continue
        n = _nargs(cmd.upper())
        if n == 0 or i + n > len(out):
            break
        v = out[i:i + n]
        i += n
        rel = cmd.islower()
        C = cmd.upper()

        def A(k):  # absolute of relative
            return (pos[0] + v[k], pos[1] + v[k + 1]) if rel else (v[k], v[k + 1])

        if C == "M":
            p = A(0)
            if cur:
                subpaths.append(cur)
                cur = []
            cur, pos, start, prev_ctrl = [p], p, p, None
            cmd = "L" if cmd == "M" else "l"
        elif C == "L":
            p = A(0); cur.append(p); pos = p; prev_ctrl = None
        elif C == "H":
            x = pos[0] + v[0] if rel else v[0]
            cur.append((x, pos[1])); pos = (x, pos[1]); prev_ctrl = None
        elif C == "V":
            y = pos[1] + v[0] if rel else v[0]
            cur.append((pos[0], y)); pos = (pos[0], y); prev_ctrl = None
        elif C == "C":
            c1, c2, p = A(0), A(2), A(4)
            for k in range(1, steps + 1):
                cur.append(_cubic(pos, c1, c2, p, k / steps))
            pos, prev_ctrl = p, c2
        elif C == "S":
            c2, p = A(0), A(2)
            c1 = (2 * pos[0] - prev_ctrl[0], 2 * pos[1] - prev_ctrl[1]) if prev_ctrl else pos
            for k in range(1, steps + 1):
                cur.append(_cubic(pos, c1, c2, p, k / steps))
            pos, prev_ctrl = p, c2
        elif C == "Q":
            c1, p = A(0), A(2)
            for k in range(1, steps + 1):
                cur.append(_quad(pos, c1, p, k / steps))
            pos, prev_ctrl = p, c1
        elif C == "T":
            p = A(0)
            c1 = (2 * pos[0] - prev_ctrl[0], 2 * pos[1] - prev_ctrl[1]) if prev_ctrl else pos
            for k in range(1, steps + 1):
                cur.append(_quad(pos, c1, p, k / steps))
            pos, prev_ctrl = p, c1
        elif C == "A":
            p = A(5)
            cur.append(((pos[0] + p[0]) / 2, (pos[1] + p[1]) / 2))
            cur.append(p)
            pos, prev_ctrl = p, None
    if cur:
        subpaths.append(cur)
    return subpaths

def longest(subpaths):
    return max(subpaths, key=len) if subpaths else []

def obb_dims(pts):
    """dimensions (w, h) of the minimum-area oriented bounding rectangle"""
    n = len(pts)
    if n < 3:
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return max(xs) - min(xs), max(ys) - min(ys)
    best = None
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        ux, uy = dx / L, dy / L          # edge direction
        us = [p[0] * ux + p[1] * uy for p in pts]
        vs = [-p[0] * uy + p[1] * ux for p in pts]
        w, h = max(us) - min(us), max(vs) - min(vs)
        if best is None or w * h < best[0] * best[1]:
            best = (w, h)
    return best

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", default="nyjc-floor-plans.svg")
    ap.add_argument("--template", default="editor_template.html",
                    help="editor template with the /*__DATA__*/ placeholder")
    ap.add_argument("--out-data", default="metadata.json")
    ap.add_argument("--out-editor", default="editor.html")
    ap.add_argument("--dpi", type=float, default=200,
                    help="resolution of the background PNGs (verified: 200)")
    args = ap.parse_args()

    root = ET.parse(args.svg).getroot()
    W = float(root.get("width")); H = float(root.get("height"))
    pages = root.find(f"{INV['sodipodi'] if 'sodipodi' in INV else '{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}'}namedview")
    # (namespace safe re-fetch)
    for child in root:
        if child.tag.endswith("namedview"):
            pages = child.findall(f"{INV['inkscape']}page")
    page_xy = [(float(p.get("x")), float(p.get("y"))) for p in pages]
    PW, PH = W, H

    def page_of(x, y):
        for i, (px, py) in enumerate(page_xy):
            if px - 3 <= x < px + PW + 3 and py - 3 <= y < py + PH + 3:
                return i + 1
        return 0

    # --- backgrounds per level layer ---
    backgrounds = {}
    for g in root.findall(f"{INV['svg']}g"):
        lbl = g.get(f"{INV['inkscape']}label", "")
        m = re.match(r"lvl\s*(\d+)", lbl)
        if not m:
            continue
        lvl = int(m.group(1))
        img = g.find(f"{INV['svg']}image")
        if img is None:
            continue
        href = img.get(f"{INV['xlink']}href") or img.get("href") or ""
        if href.startswith("data:"):
            try:
                raw = base64.b64decode(href.split(",", 1)[1])
                open(f"bg-lvl{lvl}.png", "wb").write(raw)
            except OSError as e:
                print(f"NOTE: could not write bg-lvl{lvl}.png ({e}) - continuing (editor uses embedded data)")
        backgrounds[lvl] = {"href": href, "x": float(img.get("x") or 0),
                            "y": float(img.get("y") or 0),
                            "width": float(img.get("width") or W),
                            "height": float(img.get("height") or H),
                            "pixels": None}
        try:
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(raw)) if href.startswith("data:") else Image.open(href[7:] if href.startswith("file:") else href)
            backgrounds[lvl]["pixels"] = list(im.size)
        except Exception:
            pass

    # --- scale chain -----------------------------------------------------
    lvl1 = backgrounds.get(1)
    if not lvl1 or not lvl1.get("pixels"):
        print("ERROR: could not read level-1 background dimensions"); sys.exit(1)
    px_per_unit = lvl1["pixels"][0] / PW
    m_per_px = 25.4 / args.dpi * 0.700          # 1:700 drawing at `dpi`
    scale = m_per_px * px_per_unit
    print(f"scale chain: {args.dpi:.0f} dpi render of 1:700 A0  ->  {m_per_px:.5f} m/px"
          f"  x  {px_per_unit:.4f} px/unit  =  {scale:.5f} m per SVG unit")
    print(f"  page covers {PW*scale:.0f} x {PH*scale:.0f} m of the site")

    # --- venues ----------------------------------------------------------
    # venues can live in ANY layer (locations is conventional, but labelled shapes
    # in the lvl N background layers are ingested too); floor comes from the page

    storeys = {str(i): {"rooms": [], "markers": []} for i in range(1, len(page_xy) + 1)}
    skipped, no_floor = [], []

    def add_shape(label, pts):
        if len(pts) < 3:
            skipped.append((label, "fewer than 3 points"))
            return
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        fl = page_of(cx, cy)
        if not fl:
            no_floor.append((label, (cx, cy)))
            return
        st = storeys[str(fl)]
        rid = f"f{fl}-{re.sub(r'[^A-Za-z0-9]+', '-', label.lower()).strip('-')}"
        n = 2
        base = rid
        while any(r["id"] == rid for r in st["rooms"]):
            rid = f"{base}-{n}"; n += 1
        outline = [[round(x, 2), round(y, 2)] for x, y in pts]
        s = 0
        for i in range(len(outline)):
            x1, y1 = outline[i]; x2, y2 = outline[(i + 1) % len(outline)]
            s += x1*y2 - x2*y1
        area_m2 = abs(s) / 2 * scale * scale
        w, h = obb_dims(outline)          # min-area rect: correct for rotated rooms
        st["rooms"].append({
            "id": rid, "name": label, "type": label_type(label),
            "outline": outline,
            "area_m2": round(area_m2, 1),
            "bbox_m": [round(w*scale, 1), round(h*scale, 1)],
            "centroid": [round(cx, 2), round(cy, 2)],
        })

    def collect(el, group_label=None, M=IDENT):
        MC = mmul(M, parse_tf(el.get("transform")))
        lbl = el.get(f"{INV['inkscape']}label") or group_label
        tag = el.tag.split("}")[1]

        def pt(x, y):
            return apply(MC, x, y)

        if tag == "image":
            return
        if tag == "rect":
            x = float(el.get("x") or 0); y = float(el.get("y") or 0)
            w = float(el.get("width") or 0); h = float(el.get("height") or 0)
            if lbl and lbl not in SKIP_LABELS:
                add_shape(lbl, [pt(x, y), pt(x+w, y), pt(x+w, y+h), pt(x, y+h)])
        elif tag in ("circle", "ellipse"):
            cx = float(el.get("cx") or 0); cy = float(el.get("cy") or 0)
            r = float(el.get("r") or 0) if tag == "circle" else float(el.get("rx") or 0)
            ry = float(el.get("ry") or 0) if tag == "ellipse" else r
            if lbl and lbl not in SKIP_LABELS:
                pts = [pt(cx + r*math.cos(2*math.pi*k/28), cy + ry*math.sin(2*math.pi*k/28))
                       for k in range(28)]
                add_shape(lbl, pts)
        elif tag in ("path", "polygon") and lbl and lbl not in SKIP_LABELS:
            if tag == "polygon":
                subs = [[tuple(map(float, xy)) for xy in re.findall(r"(-?[\d.eE+-]+)[, ](-?[\d.eE+-]+)", el.get("points") or "")]]
            else:
                subs = flatten_d(el.get("d") or "")
            pts = longest(subs)
            add_shape(lbl, [pt(*p) for p in pts])
        for ch in el:
            collect(ch, lbl, MC)

    for child in root:
        if child.tag.split("}")[1] in ("defs", "namedview"):
            continue
        collect(child)

    # --- metadata ---------------------------------------------------------
    meta = {
        "site": {
            "name": "Nanyang Junior College",
            "source": f"{args.svg} (Inkscape, 5 pages; venues drawn as named shapes in the 'locations' layer)",
            "source_scale": "1:700 (title blocks of the source drawings)",
            "unit_mapping": (f"1 SVG user unit = {scale:.4f} m - derived from the 1:700 A0 source "
                             f"drawings rendered at {args.dpi:.0f} dpi "
                             f"({25.4/args.dpi*0.7:.4f} m/px x {px_per_unit:.4f} px/unit); "
                             "units are the Inkscape page units of the SVG"),
            "scale_m_per_unit": round(scale, 5),
            "scale_chain": {
                "source_drawing_scale": "1:700",
                "background_render_dpi": args.dpi,
                "background_pixels_per_unit": round(px_per_unit, 4),
                "metres_per_pixel": round(m_per_px, 5),
            },
            "generated_by": "convert_inkscape.py",
            "assumptions": [
                "Venue outlines are the labelled shapes found in ANY layer of the Inkscape SVG (locations layer is conventional), transformed to page coordinates.",
                "Scale derives from the 1:700 title-block scale via the background render resolution; cross-checks printed at conversion time.",
                "Types are inferred from labels (see TYPE_RULES in convert_inkscape.py); adjust there if needed.",
                "No markers are imported - add restrooms/stairs/entrances in the editor.",
            ],
        },
        "storeys": {},
    }
    total = 0
    for i in range(1, len(page_xy) + 1):
        st = storeys[str(i)]
        st["background"] = backgrounds.get(i)
        meta["storeys"][str(i)] = st
        total += len(st["rooms"])
        print(f"floor {i}: {len(st['rooms'])} venues")

    with open(args.out_data, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))

    # --- editor build -------------------------------------------------------
    try:
        tpl = open(args.template, encoding="utf-8").read()
        compact = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        assert "/*__DATA__*/ null" in tpl, "template lacks the /*__DATA__*/ placeholder"
        open(args.out_editor, "w", encoding="utf-8", newline="\n").write(
            tpl.replace("/*__DATA__*/ null", compact))
        print(f"editor built: {args.out_editor} ({total} venues)")
    except FileNotFoundError:
        print(f"NOTE: template '{args.template}' not found - skipped editor build")

    # --- sanity cross-checks ------------------------------------------------
    print("\nscale cross-checks (should be plausible real-world sizes):")
    checks = {}
    for fl in storeys.values():
        for r in fl["rooms"]:
            checks[r["name"]] = r["bbox_m"]
    for name in ("tennis courts", "canteen", "hall", "lt4-lower", "music room"):
        if name in checks:
            b = checks[name]
            print(f"  {name:22s} {b[0]:6.1f} x {b[1]:6.1f} m")
    if skipped:   print(f"\nskipped: {skipped}")
    if no_floor:  print(f"\nWARNING - shapes not matching any page (check transforms): {no_floor}")

if __name__ == "__main__":
    main()
