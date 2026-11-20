#!/usr/bin/env python3
"""
build_knowledge.py — turn the factory's written knowledge into a retrieval corpus.

Source of truth: your own reference notes (markdown) plus an optional
standards JSON. Each file is split on its headings; every chunk keeps its file and
heading so an answer can cite where it came from.

This is the retrieval half of the system: the model does not memorise these
facts (weights hallucinate), it quotes them from here.

Usage:
    python scripts/build_knowledge.py /path/to/your/notes --out data/knowledge.jsonl
    python scripts/build_knowledge.py /path/to/repo --stats
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

# files worth retrieving from, relative to the repo root
# Markdown references to retrieve from. Point this at YOUR notes.
SOURCES = [
    "references/joinery-practice.md",
    "references/material-hatching.md",
    "references/drawing-standards.md",
    "references/title-blocks.md",
]

MAX_CHARS = 1200      # a chunk stays retrievable and fits a prompt
TAGS = {
    "joinery-practice": ["joinery", "carpentry", "boards", "plinth", "mitre", "pegboard"],
    "material-hatching": ["hatch", "material", "colour"],
    "drawing-and-bim-standards": ["drafting", "iso", "layers", "dimension"],
    "views-and-sheets": ["sheets", "views", "layout", "title"],
    "title-blocks": ["title-block", "sheet-data"],
    "fabrication-modeling": ["fabrication", "model", "casework"],
    "carpentry": ["carpentry", "workshop"],
    "cnc": ["cnc", "dxf", "cut-list"],
    "furniture-shop-drawing": ["shop-drawing", "assembly", "junctions", "finishes"],
    "costing": ["costing", "quantities"],
    "handoff": ["handover", "handoff"],
}


def slug(p: str) -> str:
    return Path(p).stem.replace("SKILL", Path(p).parent.name)


def chunk(text: str, source: str) -> list[dict]:
    """Split on markdown headings; keep the heading trail as the section."""
    out: list[dict] = []
    current_head = ""
    buf: list[str] = []

    def flush():
        body = "\n".join(buf).strip()
        if len(body) < 80:
            return
        for i in range(0, len(body), MAX_CHARS):
            piece = body[i:i + MAX_CHARS]
            if len(piece) < 80:
                continue
            key = hashlib.sha256((source + current_head + piece[:80]).encode()).hexdigest()[:12]
            out.append({"id": key, "source": source, "section": current_head,
                        "text": piece, "tags": TAGS.get(Path(source).stem, [])})

    for line in text.splitlines():
        if re.match(r"^#{1,4}\s", line):
            flush()
            buf = []
            current_head = line.lstrip("#").strip()
        else:
            buf.append(line)
    flush()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--out", default="data/samaya_knowledge.jsonl")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    root = Path(a.repo)

    rows: list[dict] = []
    missing = []
    for rel in SOURCES:
        f = root / rel
        if not f.exists():
            missing.append(rel)
            continue
        rows.extend(chunk(f.read_text(encoding="utf-8"), rel))

    # the standards file is data, so it is chunked by its top-level key
    std_path = root / "standards" / "standards.json"
    if std_path.exists():
        std = json.loads(std_path.read_text(encoding="utf-8"))
        for key, val in std.items():
            if key.startswith("_"):
                continue
            body = json.dumps(val, ensure_ascii=False, indent=1)
            for i in range(0, len(body), MAX_CHARS):
                piece = body[i:i + MAX_CHARS]
                if len(piece) < 80:
                    continue
                key_id = hashlib.sha256((key + piece[:80]).encode()).hexdigest()[:12]
                rows.append({"id": key_id, "source": "standards/sultan-standards.json",
                             "section": key, "text": piece,
                             "tags": ["standards", "machine-readable"]})

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    print(f"chunks: {len(rows)}  -> {out}")
    for k, v in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {v:4d}  {k}")
    if missing:
        print("missing (skipped):")
        for m in missing:
            print("  " + m)
    if a.stats:
        print("\nsample:", json.dumps(rows[0], ensure_ascii=False)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
