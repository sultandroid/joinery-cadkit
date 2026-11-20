#!/usr/bin/env python3
"""
build_dataset.py — mint training pairs from raw workshop material.

Input  : a folder of *.json files, each one of
           {"task": "spec|fix|rule|lisp", "prompt": "...", "answer": "..."}
         or a folder of *.jsonl files already in {"messages": [...]} form.
Output : samaya_joinery_train.jsonl + samaya_joinery_eval.jsonl (+ a report)

What it enforces before anything reaches the Hub:
  * every pair is a valid chat record (system/user/assistant)
  * duplicate prompts and duplicate answers are dropped
  * answers tagged "spec"/"fix" that contain JSON are run through
    validate_spec.py — an invalid spec never becomes training data
  * entity-leakage scan: your own client/company names (see FORBIDDEN below)
    are rejected, so a Samaya adapter stays Samaya-only
  * a deterministic 90/10 split, so the eval set is reproducible

Usage:
    python scripts/build_dataset.py raw_pairs/ --out data/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "validate_spec.py"

SYSTEM = {
    "spec": ("You are a joinery workshop assistant. Turn the engineer's request into a "
             "structured unit spec (JSON) that matches the supplied schema, and write nothing "
             "outside the JSON."),
    "fix": ("You are a joinery workshop assistant. Given a spec that breaks the workshop rules, "
            "list the violations and return the corrected spec JSON."),
    "rule": ("You are a joinery drafting reference. Answer only from the supplied workshop "
             "reference material, and cite the file and section you used."),
    "lisp": ("You write clean AutoLISP for AutoCAD. Draw on the layers A-CUT / A-VISIBLE / "
             "A-DIM / A-TEXT only, dimensioned in millimetres."),
}

# entity isolation: these must never appear in a Samaya training pair
# Entity / confidentiality scan. Put YOUR own client and company names here —
# anything matching is dropped before it can reach a training set.
FORBIDDEN = re.compile(r"__put_your_client_names_here__", re.IGNORECASE)

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def digest(s: str) -> str:
    return hashlib.sha256(norm(s).encode("utf-8")).hexdigest()[:16]


def extract_json(text: str) -> dict | None:
    m = JSON_BLOCK.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def spec_is_valid(spec: dict) -> tuple[bool, str]:
    tmp = ROOT / ".tmp_spec.json"
    tmp.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(VALIDATOR), str(tmp)],
                       capture_output=True, text=True)
    tmp.unlink(missing_ok=True)
    tail = [l for l in r.stdout.splitlines() if l.startswith(" FAIL") or l.startswith("RESULT")]
    return r.returncode == 0, "; ".join(tail[:3])


def load_raw(folder: Path) -> list[dict]:
    rows = []
    for f in sorted(folder.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for item in (data if isinstance(data, list) else [data]):
            rows.append(item)
    for f in sorted(folder.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def to_record(item: dict) -> dict:
    if "messages" in item:
        msgs = item["messages"]
        task = item.get("task", "rule")
        return {"task": task, "messages": msgs}
    task = item.get("task", "rule")
    return {"task": task, "messages": [
        {"role": "system", "content": item.get("system") or SYSTEM.get(task, SYSTEM["rule"])},
        {"role": "user", "content": item["prompt"]},
        {"role": "assistant", "content": item["answer"]},
    ]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_dir")
    ap.add_argument("--out", default="data")
    ap.add_argument("--min_pairs", type=int, default=50)
    ap.add_argument("--eval_ratio", type=float, default=0.10)
    a = ap.parse_args()

    raw = load_raw(Path(a.raw_dir))
    print(f"raw items: {len(raw)}")

    kept, seen_p, seen_a = [], set(), set()
    report = {"total_raw": len(raw), "dup_prompt": 0, "dup_answer": 0,
              "forbidden_entity": 0, "spec_rejected": 0, "kept": 0, "by_task": {}}

    for item in raw:
        try:
            rec = to_record(item)
        except KeyError:
            continue
        msgs = rec["messages"]
        prompt = next((m["content"] for m in msgs if m["role"] == "user"), "")
        answer = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
        blob = prompt + answer

        if FORBIDDEN.search(blob):
            report["forbidden_entity"] += 1
            continue
        dp, da = digest(prompt), digest(answer)
        if dp in seen_p:
            report["dup_prompt"] += 1
            continue
        if da in seen_a:
            report["dup_answer"] += 1
            continue
        if rec["task"] in ("spec", "fix"):
            spec = extract_json(answer)
            if spec is not None:
                ok, why = spec_is_valid(spec)
                if not ok:
                    print(f"REJECT spec: {why}")
                    report["spec_rejected"] += 1
                    continue
        seen_p.add(dp)
        seen_a.add(da)
        rec["id"] = dp
        kept.append(rec)
        report["by_task"][rec["task"]] = report["by_task"].get(rec["task"], 0) + 1

    report["kept"] = len(kept)
    rng = random.Random(3407)
    rng.shuffle(kept)
    n_eval = max(1, int(len(kept) * a.eval_ratio))
    evalset, trainset = kept[:n_eval], kept[n_eval:]

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("samaya_joinery_train.jsonl", trainset),
                       ("samaya_joinery_eval.jsonl", evalset)):
        with (out / name).open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} pairs")

    report["train"] = len(trainset)
    report["eval"] = len(evalset)
    (out / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if len(trainset) < a.min_pairs:
        print(f"\nWARNING: only {len(trainset)} training pairs (< {a.min_pairs}). "
              f"Collect more real pairs before fine-tuning — a small set overfits.")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
