# Joinery CAD kit — teach a model to draw joinery properly

An open toolkit for fine-tuning a small language model so it turns a carpentry /
joinery request into **drawable, checkable output**: a validated unit spec (JSON)
that a deterministic generator turns into a DXF sheet.

The model does not draw. It writes a spec; the gate checks it; the generator draws
it. That separation is the whole idea, and it is what makes the output reviewable.

```
request (Arabic / English)
        │  fine-tuned LLM
        ▼
unit spec JSON  ── validate_spec.py ──▶ reject → the model retries with the failure list
        │ accept
        ▼
gen_dxf.py ──▶ DXF: elevation + plan + section A-A on a titled sheet
```

## What is here

```
data/rules.yaml                  the rules the gate enforces — EDIT THIS for your shop
data/schema_joinery_spec.json   the contract between model and generator
data/sample_pairs.jsonl         12 open teaching pairs (spec / fix / rule / lisp)
data/example_spec.json          a good spec  → ACCEPT
data/example_spec_bad.json      a broken spec → REJECT
scripts/validate_spec.py        schema + geometry + hardware + drafting gate
scripts/gen_dxf.py              spec → DXF on an ISO sheet, scale picked to fit
scripts/build_dataset.py        raw pairs → clean train/eval sets + report
scripts/build_knowledge.py      markdown notes → retrieval corpus
scripts/check_rules.py          optional drift guard against a standards file
docs/METHOD.md                  why this design, and how to collect data that helps
```

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install ezdxf jsonschema pyyaml

# 1. the gate
.venv/bin/python scripts/validate_spec.py data/example_spec.json        # ACCEPT
.venv/bin/python scripts/validate_spec.py data/example_spec_bad.json    # REJECT, with reasons

# 2. the drawing
.venv/bin/python scripts/gen_dxf.py data/example_spec.json out/unit.dxf --sheet a1

# 3. build a dataset from your own pairs
.venv/bin/python scripts/build_dataset.py data/raw --out data/
```

Open `out/unit.dxf` in AutoCAD / BricsCAD / LibreCAD. Layers: `A-CUT`, `A-VISIBLE`,
`A-HIDDEN`, `A-CENTRE`, `A-DIM`, `A-TEXT`, `A-HATCH`, `A-FRAME`.

## Why the gate is the product

A language model will happily produce a 25 mm carcass on a shop that stocks 8 and
18, a 7 mm door reveal, or a shelf that sags. `validate_spec.py` refuses those before
they reach a drawing, and prints why. Numbers live in `data/rules.yaml`, so the gate
follows your practice instead of an opinion.

Current checks: whole-centimetre sizes · board stock · unit envelope per type ·
door reveals, leaf widths and heights · plinth material and rails · skirting ·
ceiling shadow gap · stone thickness · edge band · joints and mitres · grain
direction · shelf clear span with partitions · drafting standard present.

## Contributing data (the point of this repo)

The bottleneck is not code, it is **real, corrected cases**. If you work in a
joinery shop, the most valuable thing you can send is a mistake that actually
happened and how it was fixed.

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Short version:

1. One JSON object per line, `{"task": "spec|fix|rule|lisp", "prompt": "...", "answer": "..."}`.
2. Every `spec` / `fix` answer must pass `validate_spec.py` first.
3. No client names, no project documents, no prices. Numbers and method only.
4. Open a pull request, or an issue with the file attached.

## Models trained with this kit

A QLoRA adapter on Qwen2.5-Coder-7B is trained and used in-house; the workshop data behind
it is proprietary, so the adapter itself is not published. Everything needed to reproduce
the method is here.

- Base: `unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit` (Apache-2.0), ~6 GB in 4-bit, so it fits
  a free 16 GB GPU.

Training runs on a free Kaggle T4 (~30 GPU-hours a week) or on paid HF Jobs
(T4 $0.40/h). Full recipe in `docs/METHOD.md`.

## Honest limits

- A fine-tune teaches **format and behaviour**, not facts. It will invent a rule
  number it never saw. That is why answers cite a file and section, and why the
  validator — not the model — has the last word.
- 300–1500 real pairs is the usable range. A few dozen gives you a model that
  copies the answer shape and gets the numbers wrong; measure it before trusting it.
- House rules here are a template. Two workshops legitimately disagree; change the
  file, do not argue with the model.

## Licence

Apache-2.0 for code and rules template; CC-BY-4.0 for the sample pairs.
