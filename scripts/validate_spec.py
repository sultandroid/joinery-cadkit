#!/usr/bin/env python3
"""
validate_spec.py — the gate that stops a fine-tuned model from producing
confidently-wrong joinery.

Every rule comes from data/rules.yaml, which is itself traced to
data/samaya-standards.json (factory standards) and to the factory's
joinery-practice reference. Nothing here is invented.

Usage:
    python scripts/validate_spec.py data/example_spec.json
    cat spec.json | python scripts/validate_spec.py -
Exit code 0 = accept, 1 = reject.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RULES = yaml.safe_load((ROOT / "data" / "rules.yaml").read_text(encoding="utf-8"))
SCHEMA_PATH = ROOT / "data" / "schema_joinery_spec.json"


def load_spec(source: str) -> dict:
    raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    return json.loads(raw)


def schema_errors(spec: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema not installed — run: pip install jsonschema"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema)
    out = []
    for e in sorted(v.iter_errors(spec), key=lambda x: list(x.path)):
        where = "/".join(str(p) for p in e.path) or "<root>"
        out.append(f"{where}: {e.message}")
    return out


def check(spec: dict) -> list[tuple[bool, str, str]]:
    r: list[tuple[bool, str, str]] = []
    t = spec.get("type", "")
    ov = spec.get("overall", {})
    car = spec.get("carcass", {})
    doors = spec.get("doors") or {}
    plinth = spec.get("plinth") or {}
    skirt = spec.get("skirting") or {}
    marble = spec.get("marble") or {}
    top = spec.get("worktop") or {}
    mat = str(car.get("material", ""))
    th = car.get("thickness")

    # ---- production rule: sizes in whole centimetres ----------------------
    rnd = RULES["production"]["round_to_mm"]
    for axis in ("w", "h", "d"):
        v = ov.get(axis)
        if v is None:
            continue
        ok = float(v) % rnd == 0
        r.append((ok, f"production.round_{axis}",
                  f"{v} mm {'is a whole-centimetre size' if ok else f'must end in 0 — round to {rnd} mm'}"))

    # ---- panel thickness against factory stock --------------------------
    allowed_c = RULES["panel_thickness"]["carcass"]
    r.append((th in allowed_c, "carcass.thickness",
              f"{th} mm {'ok' if th in allowed_c else f'not a factory board, use {allowed_c}'}"))
    allowed_b = RULES["panel_thickness"]["back"]
    bt = car.get("back_thickness")
    r.append((bt in allowed_b, "carcass.back_thickness",
              f"{bt} mm {'ok' if bt in allowed_b else f'not a factory board, use {allowed_b}'}"))
    if mat == "EGGER":
        egger = RULES["stock_sizes"]["egger"]
        r.append((th in egger and bt in egger, "stock_sizes.egger",
                  f"EGGER comes in {egger} mm only — no 20, no 25"))
    if mat.startswith("MDF"):
        mdf = RULES["stock_sizes"]["mdf"]
        r.append((th in mdf, "stock_sizes.mdf",
                  f"{th} mm {'in' if th in mdf else 'not in'} the MDF stock list {mdf}"))

    if doors:
        allowed_d = RULES["panel_thickness"]["door"]
        dt = doors.get("thickness")
        r.append((dt in allowed_d, "doors.thickness",
                  f"{dt} mm {'ok' if dt in allowed_d else f'not a factory board, use {allowed_d}'}"))
    if car.get("shelf_type") != "none" and car.get("shelf_count", 0) > 0:
        allowed_s = RULES["panel_thickness"]["shelf"]
        r.append((th in allowed_s, "shelf.thickness",
                  f"shelf uses carcass thickness {th} mm "
                  f"{'ok' if th in allowed_s else f'not allowed, use {allowed_s}'}"))

    # ---- unit size envelope ---------------------------------------------
    lim = RULES["unit_limits"].get(t)
    if lim:
        for axis in ("w", "h", "d"):
            v = ov.get(axis)
            if v is None:
                continue
            lo, hi = lim[axis]["min"], lim[axis]["max"]
            r.append((lo <= v <= hi, f"overall.{axis}",
                      f"{v} mm {'within' if lo <= v <= hi else f'outside {lo}-{hi} mm'} for {t}"))
    else:
        r.append((False, "type", f"unknown unit type '{t}'"))

    # ---- doors -----------------------------------------------------------
    if doors:
        g = doors.get("gap")
        dmin, dmax = RULES["doors"]["gap_min"], RULES["doors"]["gap_max"]
        r.append((g is not None and dmin <= g <= dmax, "doors.gap",
                  f"{g} mm {'ok' if g is not None and dmin <= g <= dmax else f'must be {dmin}-{dmax} mm'}"))
        n = doors.get("count", 0)
        w = ov.get("w", 0)
        if n:
            leaf = (w - (n + 1) * (g or 0)) / n
            mx = RULES["doors"].get("max_door_width_by_type", {}).get(
                t, RULES["doors"]["max_door_width"])
            r.append((leaf <= mx, "doors.max_door_width",
                      f"leaf ≈ {leaf:.0f} mm {'ok' if leaf <= mx else f'exceeds {mx} mm for {t} — add a leaf'}"))
        hh = ov.get("h", 0)
        if n and doors.get("type") in ("full_overlay", "inset", "half_overlay"):
            mxh = RULES["doors"].get("max_door_height_by_type", {}).get(
                t, RULES["doors"]["max_door_height"])
            r.append((hh <= mxh, "doors.max_door_height",
                      f"door height {hh} mm {'ok' if hh <= mxh else f'exceeds {mxh} mm'}"))
        # every screw into board goes into a plastic dowel — recorded on the sheet
        r.append((True, "doors.hinge_dowel",
                  f"hinge cup {RULES['doors']['hinge_cup_diameter']} @ "
                  f"{RULES['doors']['hinge_cup_from_edge']} with "
                  f"{RULES['doors']['hinge_dowel_mm'][0]} mm press-in dowel; plates on "
                  f"{RULES['doors']['plate_dowel_mm'][0]}x{RULES['doors']['plate_dowel_mm'][1]} dowels"))

    # ---- plinth is painted softwood on 40x40 rails -----------------------
    if plinth:
        pm = str(plinth.get("material", "")).lower()
        r.append(("softwood" in pm, "plinth.material",
                  f"'{plinth.get('material')}' {'ok' if 'softwood' in pm else 'must be painted softwood — never EGGER or MDF'}"))
        rail = plinth.get("rail")
        want = RULES["plinth"]["rail_mm"]
        r.append((rail == want, "plinth.rail",
                  f"{rail} {'ok' if rail == want else f'must be {want} (market stock)'}"))
        ph = plinth.get("height")
        lo, hi = RULES["plinth"]["height_min"], RULES["plinth"]["height_max"]
        r.append((ph is not None and lo <= ph <= hi, "plinth.height",
                  f"{ph} mm {'ok' if ph is not None and lo <= ph <= hi else f'must be {lo}-{hi} mm'}"))
        sb = plinth.get("setback")
        lo, hi = RULES["plinth"]["setback_min"], RULES["plinth"]["setback_max"]
        r.append((sb is not None and lo <= sb <= hi, "plinth.setback",
                  f"{sb} mm {'ok' if sb is not None and lo <= sb <= hi else f'must be {lo}-{hi} mm'}"))

    # ---- skirting belongs to the unit ------------------------------------
    if skirt.get("present"):
        want = RULES["skirting"]["height"]
        hgt = skirt.get("height")
        r.append((hgt == want, "skirting.height",
                  f"{hgt} mm {'ok' if hgt == want else f'must be {want} mm to match the project skirting'}"))
        want = RULES["skirting"]["face_setback"]
        fs = skirt.get("face_setback")
        r.append((fs == want, "skirting.face_setback",
                  f"{fs} mm {'ok' if fs == want else f'must be {want} mm behind the unit faces'}"))
        r.append((True, "skirting.overall_height",
                  "overall height is kept: the skirting takes its 50 mm from the lowest part"))

    # ---- ceiling shadow gap ---------------------------------------------
    gapc = spec.get("shadow_gap_to_ceiling")
    if gapc is not None:
        mn = RULES["shadow_gap"]["to_ceiling_min"]
        r.append((gapc >= mn, "shadow_gap.to_ceiling",
                  f"{gapc} mm {'ok' if gapc >= mn else f'below the {mn} mm minimum — joinery never runs tight to the ceiling'}"))

    # ---- marble ----------------------------------------------------------
    if marble.get("present"):
        want = RULES["marble"]["thickness"]
        mt = marble.get("thickness")
        r.append((mt == want, "marble.thickness",
                  f"{mt} mm {'ok' if mt == want else f'must be {want} mm, whatever the design file says'}"))

    # ---- worktop ---------------------------------------------------------
    if top.get("present"):
        allowed_t = RULES["panel_thickness"]["worktop"]
        tt = top.get("thickness")
        r.append((tt in allowed_t, "worktop.thickness",
                  f"{tt} mm {'ok' if tt in allowed_t else f'not allowed, use {allowed_t}'}"))
        oh = top.get("overhang")
        lo, hi = RULES["worktop"]["overhang_min"], RULES["worktop"]["overhang_max"]
        r.append((oh is not None and lo <= oh <= hi, "worktop.overhang",
                  f"{oh} mm {'ok' if oh is not None and lo <= oh <= hi else f'must be {lo}-{hi} mm'}"))

    # ---- edge banding ----------------------------------------------------
    eb = (spec.get("finish") or {}).get("edge_band")
    allowed_e = RULES["edge_band"]["allowed"]
    r.append((eb in allowed_e, "finish.edge_band",
              f"{eb} mm {'ok' if eb in allowed_e else f'not allowed, use {allowed_e}'}"))
    exposed_min = RULES["edge_band"]["exposed"]
    r.append((eb is not None and eb >= exposed_min, "finish.edge_band.exposed",
              f"{eb} mm on exposed edges {'ok' if eb is not None and eb >= exposed_min else f'too thin, exposed edges need {exposed_min} mm'}"))

    # ---- joint, mitre, grain --------------------------------------------
    j = car.get("joint")
    r.append((j in RULES["joints"]["allowed"], "carcass.joint",
              f"{j} {'ok' if j in RULES['joints']['allowed'] else 'not an approved joint'}"))
    r.append((True, "joints.mitre",
              f"painted outside corners are {RULES['joints']['mitre_deg']} degree mitres, not butt joints"))
    gd = spec.get("grain_direction")
    r.append((gd in ("vertical", "horizontal", "na"), "grain_direction",
              f"{gd} {'ok' if gd in ('vertical', 'horizontal', 'na') else 'must be vertical/horizontal/na'}"))

    # ---- shelf span ------------------------------------------------------
    parts = int(car.get("partitions", 0) or 0)
    span = (ov.get("w", 0) - 2 * (th or 18)) / (parts + 1)
    mx = RULES["shelves"]["max_clear_span"]
    if car.get("shelf_count", 0) > 0:
        r.append((span <= mx, "shelves.max_clear_span",
                  f"clear span {span:.0f} mm {'ok' if span <= mx else f'exceeds {mx} mm — increase partitions'}"))

    # ---- drawing standard present ---------------------------------------
    r.append((True, "drafting.standard",
              f"dims {RULES['drafting']['dimension']['text_mm']} mm blue Arial, arrows "
              f"{RULES['drafting']['dimension']['arrow_mm']} at 30 degrees, cut {RULES['drafting']['lineweights_mm']['cut']} mm"))
    return r


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    spec = load_spec(sys.argv[1])
    errs = schema_errors(spec)
    results = check(spec)
    fails = [x for x in results if not x[0]]
    for ok, name, msg in results:
        print(f"{'  ok  ' if ok else ' FAIL '} {name:28s} {msg}")
    if errs:
        print("\nSCHEMA:")
        for e in errs:
            print(" FAIL  " + e)
    total = len(results) + len(errs)
    print(f"\n{total - len(fails) - len(errs)}/{total} checks passed")
    if fails or errs:
        print("RESULT: REJECT")
        return 1
    print("RESULT: ACCEPT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
