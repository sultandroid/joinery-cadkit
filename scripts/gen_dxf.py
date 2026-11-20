#!/usr/bin/env python3
"""
gen_dxf.py — deterministic DXF generator for Samaya joinery units.

The fine-tuned model never draws. It emits a spec (JSON); this script draws it.

Everything here follows the factory standard now, not invented defaults:
  * line weights, layer use, dimension style, text sizes, scales, sheet notes
    → data/samaya-standards.json  (your own standards file, optional)
  * joinery rules → data/rules.yaml (edit it to match your workshop)

Workflow: geometry is modelspace 1:1 in mm; the sheet frame, title block and
every annotation is drawn at the same 1:1 by multiplying the printed size by the
plot scale, so plotting the sheet at 1:N is geometrically exact.

Views: front elevation, plan (below it, first angle), section A-A.

Usage:
    python scripts/gen_dxf.py data/example_spec.json out/BU-01.dxf
    python scripts/gen_dxf.py spec.json out.dxf --scale 20 --sheet a1
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import ezdxf
import yaml
from ezdxf.enums import TextEntityAlignment

ROOT = Path(__file__).resolve().parent.parent
RULES = yaml.safe_load((ROOT / "data" / "rules.yaml").read_text(encoding="utf-8"))
_std_path = ROOT / "data" / "samaya-standards.json"
if _std_path.exists():
    STD = json.loads(_std_path.read_text(encoding="utf-8"))
else:
    # open edition: no factory standards file, derive the few values we need
    _d = RULES["drafting"]
    STD = {
        "dimensions": {"color": [0, 0, 255], "arrow_mm": _d["dimension"]["arrow_mm"]},
        "sheet_notes": {"fabrication_heading": "FABRICATION NOTES",
                        "standards_heading": "STANDARDS",
                        "fabrication": RULES["sheet_notes"], "standards": []},
        "sheets": {"sign_off": {"checked_by": ""}},
    }
DRAFT = RULES["drafting"]
L = DRAFT["layers"]
DIMR = DRAFT["dimension"]
TXT = DRAFT["text"]
LW = DRAFT["lineweights_mm"]

# printed sheet sizes in mm (the title block in the repo is A0, 1189 x 841)
SHEETS = {"a0": (1189.0, 841.0), "a1": (841.0, 594.0), "a2": (594.0, 420.0)}
TB_PANEL_MM = 155.0
TB_MARGIN_MM = 10.0



# ISO 5455 series plus the whole-number scales the house rule allows for filling a sheet
ISO_SCALES = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 100]


def choose_scale(spec: dict, sheet: str) -> int:
    """Pick the smallest ISO 5455 scale that still fits every view on the sheet,
    so the drawing fills the sheet instead of sitting in a corner (house rule:
    one view per sheet sized to fill it)."""
    w = float(spec["overall"]["w"]); h = float(spec["overall"]["h"]); d = float(spec["overall"]["d"])
    car = spec["carcass"]
    ph = float((spec.get("plinth") or {}).get("height", 0) or 0)
    top = spec.get("worktop") or {}
    tp = float(top.get("thickness", 0) or 0) if top.get("present") else 0.0
    toh = float(top.get("overhang", 0) or 0) if top.get("present") else 0.0
    skirt = spec.get("skirting") or {}
    sh = float(skirt.get("height", 0) or 0) if skirt.get("present") else 0.0
    total_h = ph + h + tp + sh
    notes_h = 7 * 4.4
    for S in ISO_SCALES:
        gap = 30 * S
        dy = DIMR["string_spacing_mm"] * S
        content_w = (w + 2 * toh) + gap + (d + toh) + 2.6 * dy
        content_h = total_h + dy + (d + toh) + 26 * S + dy + notes_h * S
        avail_w = (SHEETS[sheet][0] - TB_PANEL_MM - 2 * TB_MARGIN_MM - 20) * S
        avail_h = (SHEETS[sheet][1] - 2 * TB_MARGIN_MM - 20) * S
        if content_w <= avail_w and content_h <= avail_h:
            return S
    return 100


def aci(rgb) -> int:
    """nearest AutoCAD index colour for an RGB triplet from the standards file"""
    table = {0: (0, 0, 0), 1: (255, 0, 0), 2: (255, 255, 0), 3: (0, 255, 0),
             4: (0, 255, 255), 5: (0, 0, 255), 6: (255, 0, 255), 7: (0, 0, 0),
             8: (128, 128, 128), 9: (192, 192, 192)}
    best, dist = 7, 1e18
    for k, c in table.items():
        d = sum((a - b) ** 2 for a, b in zip(rgb, c))
        if d < dist:
            best, dist = k, d
    return best


def setup(scale: int):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    doc.header["$LUNITS"] = 2
    msp = doc.modelspace()

    lay = {"cut": (LW["cut"], 7), "visible": (LW["visible"], 7),
           "hidden": (LW["hidden"], 8), "centre": (LW["centre"], 8),
           "dim": (LW["thin"], aci(STD["dimensions"]["color"])),
           "text": (LW["thin"], 7), "hatch": (LW["thin"], 8),
           "frame": (LW["visible"], 7)}
    for key, (lw, colour) in lay.items():
        doc.layers.add(L[key], color=colour, lineweight=int(round(lw * 100)))
    doc.layers.get(L["hidden"]).dxf.linetype = "DASHED"
    doc.layers.get(L["centre"]).dxf.linetype = "CENTER"

    for name, font in (("SAMAYA", "arial.ttf"), ("SAMAYA-BOLD", "arialbd.ttf")):
        if name not in doc.styles:
            doc.styles.add(name, font=font)

    for name, txt_mm, lw, bold in (("SAMAYA", DIMR["text_mm"], LW["thin"], False),
                                   ("SAMAYA-OVERALL", DIMR["overall_text_mm"], LW["cut"], True)):
        ds = doc.dimstyles.duplicate_entry("EZDXF", name)
        ds.dxf.dimlfac = 1.0
        ds.dxf.dimdec = 0
        ds.dxf.dimzin = 8
        ds.dxf.dimtxt = txt_mm * scale
        ds.dxf.dimasz = DIMR["arrow_mm"] * scale
        ds.dxf.dimexe = DIMR["witness_extension_mm"] * scale
        ds.dxf.dimexo = DIMR["witness_gap_mm"] * scale
        ds.dxf.dimgap = 1.5 * scale
        ds.dxf.dimlunit = 2
        ds.dxf.dimtad = 1
        ds.dxf.dimtih = 0
        ds.dxf.dimtoh = 0
        dim_colour = aci(STD["dimensions"]["color"])   # blue, house deviation from ISO
        ds.dxf.dimclrd = dim_colour
        ds.dxf.dimclre = dim_colour
        ds.dxf.dimclrt = dim_colour
        ds.dxf.dimtxsty = "SAMAYA-BOLD" if bold else "SAMAYA"
        ds.dxf.dimlwd = int(round(lw * 100))
        ds.dxf.dimlwe = int(round(lw * 100))
    return doc, msp


def rect(msp, x, y, w, h, layer):
    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                       close=True, dxfattribs={"layer": layer})


def dims(msp, p1, p2, base, scale, angle=0, overall=False):
    msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle,
                       dimstyle="SAMAYA-OVERALL" if overall else "SAMAYA",
                       dxfattribs={"layer": L["dim"]}).render()


def label(msp, text, x, y, scale, mm=TXT["note_mm"], style="SAMAYA", layer=None):
    msp.add_text(text, height=mm * scale,
                 dxfattribs={"layer": layer or L["text"], "style": style}).set_placement(
                     (x, y), align=TextEntityAlignment.LEFT)


def section_mark(msp, x, y, half, scale, tag="A"):
    msp.add_line((x, y - half), (x, y + half), dxfattribs={"layer": L["cut"]})
    h = half * 0.3
    msp.add_line((x, y - half), (x + h, y - half + h), dxfattribs={"layer": L["cut"]})
    msp.add_line((x, y + half), (x + h, y + half - h), dxfattribs={"layer": L["cut"]})
    label(msp, f"{tag}-{tag}", x - 18 * scale, y + half + 3 * scale, scale,
          mm=TXT["heading_mm"], style="SAMAYA-BOLD")


def draw_title_block(msp, W, H, scale, meta):
    """Field labels copied from the repo's A0 title block (title-blocks/)."""
    S = scale
    m = TB_MARGIN_MM * S
    rect(msp, 0, 0, W, H, L["frame"])
    rect(msp, m, m, W - 2 * m, H - 2 * m, L["frame"])
    px = W - m - TB_PANEL_MM * S
    msp.add_line((px, m), (px, H - m), dxfattribs={"layer": L["frame"]})

    def put(text, x_mm, y_mm, size=2.5, bold=False):
        label(msp, text, px + x_mm * S, y_mm * S, S, mm=size,
              style="SAMAYA-BOLD" if bold else "SAMAYA", layer=L["frame"])

    def hline(y_mm):
        msp.add_line((px, y_mm * S), (W - m, y_mm * S), dxfattribs={"layer": L["frame"]})

    put("samaya-factory.com", 2, 5, 3, True)
    put("This drawing is the property of Samaya Factory. Do not scale. "
        "Check all dimensions on site before fabrication.", 2, 12, 2)
    hline(18)
    put("APPROVED BY", 2, 21); put(meta.get("approved_by", "ASK"), 2, 24, 3)
    put("PROJECT NO.", 88, 21); put(meta.get("project_no", "P-XXXX"), 88, 24, 3)
    hline(30)
    put("DESIGNED BY", 2, 33); put("CHECKED BY", 88, 33)
    put(meta.get("designed_by", "ASK"), 2, 36, 3)
    put(meta.get("checked_by", ""), 88, 36, 3)
    hline(42)
    put("SCALE", 2, 45); put("DATE", 88, 45)
    put(f"1:{S}", 2, 48, 3); put(meta.get("date", ""), 88, 48, 3)
    hline(54)
    put("DRAWING NO.", 2, 57); put("REV", 128, 57)
    put(meta.get("drawing_no", "A-2001"), 2, 61, 7, True)
    put(meta.get("rev", "0"), 128, 61, 5)
    hline(73)
    put("DRAWING TITLE", 2, 76)
    put(meta.get("drawing_title", ""), 2, 80, 4, True)
    hline(87)
    put("PROJECT", 2, 90)
    put(meta.get("project_name", ""), 2, 94, 3.5)

    hline(118)
    put("REVISIONS", 2, 121, 3, True)
    put("REV      DESCRIPTION                                     DATE", 2, 125, 2.2)

    hline(132)
    put(STD["sheet_notes"]["fabrication_heading"], 2, 135, 3, True)
    y = 139.0
    for line in RULES["sheet_notes"]:
        put(line, 2, y, 2.2)
        y += 3.2
    put(STD["sheet_notes"]["standards_heading"], 2, y + 1, 3, True)
    y += 4.5
    for line in STD["sheet_notes"]["standards"]:
        put(line, 2, y, 2.2)
        y += 3.2
    put("CLIENT", 2, y + 3)
    put(meta.get("client", "SAMAYA FACTORY"), 2, y + 6, 3.5)
    put("CONSULTANT", 2, y + 11)
    put("SAMAYA FACTORY - TECHNICAL OFFICE", 2, y + 14, 3)
    return px


def draw(spec: dict, scale: int, sheet: str = "a0"):
    doc, msp = setup(scale)
    S = scale
    sheet_w, sheet_h = SHEETS[sheet]
    W, H = sheet_w * S, sheet_h * S

    w = float(spec["overall"]["w"]); h = float(spec["overall"]["h"]); d = float(spec["overall"]["d"])
    car = spec["carcass"]; t = float(car["thickness"]); bt = float(car["back_thickness"])
    doors = spec.get("doors") or {}
    n = int(doors.get("count", 0)); gap = float(doors.get("gap", 2))
    dt_ = float(doors.get("thickness", 18))
    plinth = spec.get("plinth") or {}
    ph = float(plinth.get("height", 0) or 0)
    psb = float(plinth.get("setback", 0) or 0)
    skirt = spec.get("skirting") or {}
    sh = float(skirt.get("height", 0) or 0) if skirt.get("present") else 0.0
    top = spec.get("worktop") or {}
    tp = float(top.get("thickness", 0) or 0) if top.get("present") else 0.0
    toh = float(top.get("overhang", 0) or 0) if top.get("present") else 0.0
    parts = int(car.get("partitions", 0) or 0)
    uid = spec.get("unit_id", "UNIT")
    total_h = ph + h + tp

    meta = {
        "project_no": spec.get("project_no", "P-XXXX"),
        "project_name": spec.get("project_name", "SAMAYA FACTORY - WORKSHOP"),
        "drawing_title": f"{uid} - {str(spec.get('type','')).replace('_',' ').upper()} "
                         f"{w:.0f} x {h:.0f} x {d:.0f}",
        "drawing_no": spec.get("drawing_no", "A-2001"),
        "rev": spec.get("rev", "0"),
        "date": dt.date.today().isoformat(),
        "checked_by": STD["sheets"]["sign_off"]["checked_by"],
        "client": spec.get("client", "SAMAYA FACTORY"),
    }
    draw_title_block(msp, W, H, S, meta)

    # ---------- view placement: centred, filling the drawing area ----------
    gap = 30 * S
    dy = DIMR["string_spacing_mm"] * S
    notes_h = 7 * 4.4 * S
    content_w = (w + 2 * toh) + gap + (d + toh) + 2.6 * dy
    content_h = total_h + sh + dy + (d + toh) + 26 * S + dy + notes_h
    avail_w = (sheet_w - TB_PANEL_MM - 2 * TB_MARGIN_MM - 20) * S
    avail_h = (sheet_h - 2 * TB_MARGIN_MM - 20) * S
    x0 = TB_MARGIN_MM * S + 10 * S + max(0.0, (avail_w - content_w) / 2) + toh
    y0 = TB_MARGIN_MM * S + 14 * S + notes_h + max(0.0, (avail_h - content_h) / 2) + (d + toh) + 12 * S
    gap_paper = gap

    # ================= FRONT ELEVATION =================
    ex, ey = x0, y0
    if sh:
        rect(msp, ex, ey, w, sh, L["visible"])
    if ph:
        rect(msp, ex + psb, ey + sh, w - 2 * psb, ph, L["visible"])
    rect(msp, ex, ey + sh + ph, w, h, L["cut"])
    for i in range(1, parts + 1):
        xc = ex + t + (w - 2 * t) * i / (parts + 1)
        for off in (-t / 2, t / 2):
            msp.add_line((xc + off, ey + sh + ph), (xc + off, ey + sh + ph + h),
                         dxfattribs={"layer": L["cut"]})
    if n == 1:
        rect(msp, ex + gap, ey + sh + ph + gap, w - 2 * gap, h - 2 * gap, L["visible"])
    elif n > 1:
        leaf = (w - (n + 1) * gap) / n
        for i in range(n):
            rect(msp, ex + gap + i * (leaf + gap), ey + sh + ph + gap,
                 leaf, h - 2 * gap, L["visible"])
    if tp:
        rect(msp, ex - toh, ey + sh + ph + h, w + 2 * toh, tp, L["visible"])
    if n and doors.get("hinge_side") in ("left", "right", "both"):
        cup = RULES["doors"]["hinge_cup_diameter"] / 2
        off = RULES["doors"]["hinge_cup_from_edge"]
        xs = []
        if doors["hinge_side"] in ("left", "both"):
            xs.append(ex + gap + off)
        if doors["hinge_side"] in ("right", "both"):
            xs.append(ex + w - gap - off)
        for x in xs:
            for f in (0.12, 0.88):
                msp.add_circle((x, ey + sh + ph + h * f), cup, dxfattribs={"layer": L["hidden"]})

    dims(msp, (ex, ey), (ex + w, ey), (ex + w / 2, ey - dy), S)
    dims(msp, (ex + w, ey), (ex + w, ey + total_h + sh),
         (ex + w + 1.2 * dy, ey + (total_h + sh) / 2), S, angle=90, overall=True)
    if ph:
        dims(msp, (ex + w, ey + sh), (ex + w, ey + sh + ph),
             (ex + w + 2.4 * dy, ey + sh + ph / 2), S, angle=90)
    if tp:
        dims(msp, (ex - toh, ey + total_h + sh), (ex + w + toh, ey + total_h + sh),
             (ex + w / 2, ey + total_h + sh + dy), S, overall=True)
    section_mark(msp, ex + w / 2, ey + sh + ph + h / 2, h * 0.3, S)
    label(msp, f"{uid}  FRONT ELEVATION  1:{S}", ex, ey - 14 * S, S)

    # ================= PLAN (below the elevation, first angle) =================
    py = ey - (d + toh) - 30 * S
    if tp:
        rect(msp, ex - toh, py, w + 2 * toh, d + toh, L["visible"])
    rect(msp, ex, py + toh, w, d, L["cut"])
    msp.add_line((ex, py + toh + bt), (ex + w, py + toh + bt), dxfattribs={"layer": L["visible"]})
    for i in range(1, parts + 1):
        xc = ex + t + (w - 2 * t) * i / (parts + 1)
        msp.add_line((xc, py + toh + bt), (xc, py + toh + d), dxfattribs={"layer": L["cut"]})
    if n:
        msp.add_line((ex, py + toh + d - dt_), (ex + w, py + toh + d - dt_),
                     dxfattribs={"layer": L["visible"]})
        if n > 1:
            leaf = (w - (n + 1) * gap) / n
            for i in range(1, n):
                xx = ex + gap + i * (leaf + gap) - gap / 2
                msp.add_line((xx, py + toh + d - dt_), (xx, py + toh + d),
                             dxfattribs={"layer": L["visible"]})
    dims(msp, (ex, py), (ex + w, py), (ex + w / 2, py - dy), S)
    dims(msp, (ex + w, py + toh), (ex + w, py + toh + d),
         (ex + w + 1.2 * dy, py + toh + d / 2), S, angle=90, overall=True)
    section_mark(msp, ex + w / 2, py + toh + d / 2, d * 0.3, S)
    label(msp, f"{uid}  PLAN  1:{S}", ex, py - 14 * S, S)

    # ================= SECTION A-A =================
    sx = ex + w + max(2 * toh, 25) + gap
    sy = ey + sh
    rect(msp, sx, sy + ph, d, h, L["cut"])
    rect(msp, sx, sy + ph + h - t, d, t, L["cut"])
    rect(msp, sx, sy + ph, d, t, L["cut"])
    rect(msp, sx, sy + ph, bt, h, L["visible"])
    sc = int(car.get("shelf_count", 0))
    if sc and car.get("shelf_type") != "none":
        for i in range(sc):
            yy = sy + ph + t + (h - 2 * t) * (i + 1) / (sc + 1) - t / 2
            rect(msp, sx + bt, yy, d - bt, t, L["cut"])
    if tp:
        rect(msp, sx - toh, sy + ph + h, d + toh, tp, L["visible"])
    if ph:
        rect(msp, sx + psb, sy, d - psb, ph, L["visible"])
    dims(msp, (sx, sy), (sx + d, sy), (sx + d / 2, sy - dy), S)
    dims(msp, (sx + d, sy), (sx + d, sy + total_h), (sx + d + 1.2 * dy, sy + total_h / 2),
         S, angle=90, overall=True)
    label(msp, f"{uid}  SECTION A-A  1:{S}", sx, sy - 14 * S, S)

    # ================= unit notes under the sheet =================
    ny = (TB_MARGIN_MM + 2) * S + 6 * 4.4 * S
    lines = [
        f"UNIT {uid}   TYPE {spec.get('type')}   OVERALL {w:.0f} x {(total_h + sh):.0f} x {d:.0f} mm"
        f"   (W x Overall H x D)   CARCASS H {h:.0f}",
        f"CARCASS {car.get('material')} {t:.0f}   BACK {bt:.0f}   JOINT {car.get('joint')}"
        f"   SHELVES {car.get('shelf_count')} {car.get('shelf_type')}   PARTITIONS {parts}",
        f"DOORS {n} x {dt_:.0f} {doors.get('type','-')}   REVEAL {gap:.0f}"
        f"   HINGE {RULES['doors']['hinge_cup_diameter']} cup @ {RULES['doors']['hinge_cup_from_edge']}"
        f" + {RULES['doors']['hinge_dowel_mm'][0]} dowel"
        f"   PLINTH {RULES['plinth']['material']} {RULES['plinth']['rail_mm'][0]}x{RULES['plinth']['rail_mm'][1]}",
        f"SKIRTING {sh:.0f} high, face {RULES['skirting']['face_setback']} behind unit faces"
        f"   FINISH {spec['finish']['exterior']} / {spec['finish']['interior']}"
        f"   EDGE BAND {spec['finish']['edge_band']}   GRAIN {spec.get('grain_direction')}",
        f"SIZES IN WHOLE CENTIMETRES ({RULES['production']['round_to_mm']} mm)"
        f"   TOLERANCE {RULES['tolerances']['linear']}   DOOR REVEAL {RULES['tolerances']['door_reveal']}"
        f"   DIMENSIONS TO CARCASS FACE, NOT TO FINISHED VENEER",
    ]
    x = (TB_MARGIN_MM + 30) * S
    for line in lines:
        label(msp, line, x, ny, S, mm=3.2)
        ny -= 4.4 * S
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--scale", type=int, default=0,
                    help="plot scale denominator (10 = 1:10); 0 = pick the smallest ISO scale that fits")
    ap.add_argument("--sheet", default="a0", choices=sorted(SHEETS), help="printed sheet size")
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    scale = a.scale or choose_scale(spec, a.sheet)
    doc = draw(spec, scale, a.sheet)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out)
    print(f"wrote {out}  ({out.stat().st_size} bytes, sheet {a.sheet.upper()} at 1:{scale})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
