#!/usr/bin/env python3
"""
check_rules.py — drift guard.

rules.yaml must not contain a number that contradicts the factory standards.
This script re-reads data/samaya-standards.json and asserts every value below
still matches. If your standards file is updated,
this fails loudly instead of the drawings quietly going stale.

Usage: python scripts/check_rules.py
Exit code 0 = in sync, 1 = drift (fix rules.yaml).
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RULES = yaml.safe_load((ROOT / "data" / "rules.yaml").read_text(encoding="utf-8"))
_std = ROOT / "data" / "samaya-standards.json"
if not _std.exists():
    print("open edition: no factory standards file present — nothing to drift against.")
    print("RESULT: SKIPPED (add data/samaya-standards.json to enforce this)")
    raise SystemExit(0)
STD = json.loads(_std.read_text(encoding="utf-8"))

# (label, value in rules.yaml, value in the standards file)
PAIRS = [
    ("joinery.carcass_mm", RULES["panel_thickness"]["carcass"][0], STD["joinery"]["carcass_mm"]),
    ("joinery.round_to_mm", RULES["production"]["round_to_mm"], STD["joinery"]["round_to_mm"]),
    ("joinery.marble_mm", RULES["marble"]["thickness"], STD["joinery"]["marble_mm"]),
    ("joinery.skirting_mm", RULES["skirting"]["height"], STD["joinery"]["skirting_mm"]),
    ("joinery.shadow_gap_to_ceiling_min_mm", RULES["shadow_gap"]["to_ceiling_min"],
     STD["joinery"]["shadow_gap_to_ceiling_min_mm"]),
    ("joinery.counter_total_mm", RULES["counter"]["display_total_mm"],
     STD["joinery"]["counter_total_mm"]),
    ("joinery.painted_corners.mitre_deg", RULES["joints"]["mitre_deg"],
     STD["joinery"]["painted_corners"]["mitre_deg"]),
    ("stock_sizes.egger_thickness_mm", RULES["stock_sizes"]["egger"],
     STD["stock_sizes"]["egger_thickness_mm"]),
    ("stock_sizes.mdf_thickness_mm", RULES["stock_sizes"]["mdf"],
     STD["stock_sizes"]["mdf_thickness_mm"]),
    ("stock_sizes.softwood_planed_mm", RULES["stock_sizes"]["softwood_planed"],
     STD["stock_sizes"]["softwood_planed_mm"]),
    ("stock_sizes.hardwood_oak_thickness_mm", RULES["stock_sizes"]["hardwood_oak"],
     STD["stock_sizes"]["hardwood_oak_thickness_mm"]),
    ("dimensions.text_mm", RULES["drafting"]["dimension"]["text_mm"], STD["dimensions"]["text_mm"]),
    ("dimensions.colour", RULES["drafting"]["dimension"]["colour"], STD["dimensions"]["color"]),
    ("dimensions.arrow_mm", RULES["drafting"]["dimension"]["arrow_mm"], STD["dimensions"]["arrow_mm"]),
    ("dimensions.witness_gap_mm", RULES["drafting"]["dimension"]["witness_gap_mm"],
     STD["dimensions"]["witness_gap_mm"]),
    ("dimensions.string_spacing_mm", RULES["drafting"]["dimension"]["string_spacing_mm"],
     STD["dimensions"]["string_spacing_mm"]),
    ("dimensions.overall.text_mm", RULES["drafting"]["dimension"]["overall_text_mm"],
     STD["dimensions"]["overall"]["text_mm"]),
    ("scales.unit_section", RULES["drafting"]["scale"]["unit_section"],
     STD["scales"]["by_content"]["unit_section"]),
    ("scales.construction_detail", RULES["drafting"]["scale"]["construction_detail"],
     STD["scales"]["by_content"]["construction_detail"]),
    ("lines.cut", RULES["drafting"]["lineweights_mm"]["cut"], STD["lines"]["widths_mm"][4]),
    ("lines.visible", RULES["drafting"]["lineweights_mm"]["visible"], STD["lines"]["widths_mm"][2]),
    ("lines.thin", RULES["drafting"]["lineweights_mm"]["thin"], STD["lines"]["widths_mm"][0]),
    ("sheet_notes.fabrication", RULES["sheet_notes"], STD["sheet_notes"]["fabrication"]),
]


def main() -> int:
    bad = 0
    for label, mine, theirs in PAIRS:
        ok = mine == theirs
        # rules.yaml states the dimension colour as a name, the standard as RGB
        if label == "dimensions.colour" and mine == "blue":
            ok = theirs == [0, 0, 255]
        if not ok:
            bad += 1
            print(f"DRIFT {label:38s} rules.yaml={mine!r}  standards={theirs!r}")
        else:
            print(f"  ok  {label:38s} {mine if not isinstance(mine, list) or len(str(mine)) < 40 else ''}")
    print(f"\n{len(PAIRS) - bad}/{len(PAIRS)} in sync")
    if bad:
        print("RESULT: DRIFT — update data/rules.yaml from the standards file")
        return 1
    print("RESULT: IN SYNC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
