---
license: cc-by-4.0
language:
  - en
  - ar
task_categories:
  - text-generation
tags:
  - joinery
  - carpentry
  - cad
  - dxf
  - autocad
  - shop-drawings
  - qlora
  - structured-output
pretty_name: Joinery CAD kit — teach a model to produce buildable specs
size_categories:
  - n<1K
---

# Joinery CAD kit

An open kit for teaching a small language model to turn a carpentry/joinery request
into **drawable, checkable output** — a validated unit spec (JSON) that a
deterministic generator turns into a DXF sheet.

The model does not draw. It writes a spec; a validator checks it against the
workshop rules; the generator draws it. That separation is what makes the output
reviewable, and it is the point of the kit.

```
request → LLM → unit spec JSON → validate_spec.py → gen_dxf.py → DXF
                                   └ reject → model retries with the failure list
```

- Code, docs and CI: https://github.com/sultandroid/joinery-cadkit
- Method (why not let the model draw): `docs/METHOD.md`
- How to contribute cases: `CONTRIBUTING.md`

## Files

```
data/rules.yaml                 rules the gate enforces — edit for your shop
data/schema_joinery_spec.json   contract between model and generator
data/sample_pairs.jsonl         12 open teaching pairs (spec / fix / rule / lisp)
data/example_spec.json          good spec  → ACCEPT
data/example_spec_bad.json      broken spec → REJECT
scripts/validate_spec.py        the gate: stock, envelope, reveals, plinth, spans, drafting
scripts/gen_dxf.py              spec → DXF on an ISO sheet, scale chosen to fit
scripts/build_dataset.py        raw pairs → clean train/eval + report (dedupe, entity scan, gate)
scripts/build_knowledge.py      markdown notes → retrieval corpus
scripts/check_rules.py          optional drift guard against a standards file
```

## Contribute a case

The bottleneck is not code, it is real corrected cases. The most valuable pair type
is `fix`: a spec or drawing that was wrong, the rule it broke, and the correction.

```json
{"task": "fix",
 "prompt": "the spec as it was actually asked",
 "answer": "violations found, then the corrected spec JSON"}
```

Rules: it must pass `scripts/validate_spec.py`, no client or project material, no
prices, real wording (mixed Arabic/English welcome). Open a PR on GitHub or here on
the Hub. Contributions are CC-BY-4.0.

## Honest limits

A fine-tune teaches format and behaviour, not facts — it will invent a rule number
it never saw. That is why answers cite a file and section, and why the validator has
the last word. Below ~100 pairs you get a model that copies the answer shape and
gets the numbers wrong; 300–1500 real pairs is the usable range.
