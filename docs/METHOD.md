# Method — why a model must not draw

## The failure mode this design removes

Ask a language model for "a 600x720 base unit drawing" and it will produce a
plausible paragraph, or a block of DXF-looking text, or coordinates that do not
close. Nothing in that output is wrong in a way you can point at, and nothing in it
is right in a way you can check. In a workshop that is worse than useless.

The fix is not a better model. It is a narrower contract.

## Three layers, three owners

1. **Language model** — owns the mapping from messy human request to a fixed schema.
   This is genuinely hard and genuinely what a model is for: mixed Arabic/English,
   half-stated sizes, "same as the last one but 100 wider".
2. **Validator** (`scripts/validate_spec.py`) — owns correctness. Deterministic,
   no model, reads `data/rules.yaml`. It answers one question: may this be built?
3. **Generator** (`scripts/gen_dxf.py`) — owns geometry. Deterministic, 1:1 mm,
   layers and dimension style fixed, sheet scale chosen to fit.

Because layer 2 rejects with a list of reasons, the model can be asked again with
that list. The loop converges on something buildable instead of something fluent.

## What the fine-tune is actually for

| Learnable by prompting | Learnable by fine-tuning |
|---|---|
| a rule you can quote in the prompt | the exact schema, key order, vocabulary |
| general joinery knowledge | your house style: how you write a note, what you never say |
| — | refusing to answer outside the sources, and citing them |
| — | the shape of a `fix` answer: violations first, then the corrected spec |

So the model is trained on **pairs**, not on documents. Facts stay in files and are
retrieved; form is what gets baked into weights.

## Data collection, in order of value

1. **`fix` pairs** — a spec or drawing that was wrong, the rule it broke, the
   correction. These are the only pairs that teach judgement. Harvest them from
   site queries, RFIs, workshop rejections, and rework.
2. **`spec` pairs** — an existing drawing, stripped back to the request that would
   reproduce it, plus the spec JSON. Verify by generating the drawing and comparing
   dimensions with the original.
3. **`rule` pairs** — the questions your juniors actually ask, answered with the file
   and section. These teach the model to cite instead of invent.
4. **`lisp` pairs** — scripts that ran, with the sentence that produced them.

Sizes that matter: **300 pairs is the floor, 1500 is comfortable.** Below ~100 the
model learns the answer's shape and gets its numbers wrong — which looks like
progress in a demo and fails on the shop floor. Always hold back ~10 % as an eval
set and gate on the spec pass rate, not on the loss.

## Training recipe that fits free hardware

- Base: `Qwen2.5-Coder-7B-Instruct` (Apache-2.0). Code-tuned, so it already knows
  JSON and Python; you are teaching house style, not programming.
- 4-bit QLoRA, r=16, alpha=32, all linear layers: ~6 GB of VRAM, fits a free 16 GB
  T4, runs a full pass in minutes on a few hundred short pairs.
- 1–3 epochs, lr 2e-4, cosine. More epochs on a small set produces a model that
  repeats one answer.
- After training, fuse and convert to GGUF so it runs offline on a workshop PC.

## Evaluation gate

Promote a run only if, on the held-out set:

1. ≥ 90 % of generated specs pass `validate_spec.py` on the first attempt;
2. the generated DXF opens and its dimensions match the spec;
3. no answer cites a file, section or rule that does not exist.

Loss curves lie about this; the gate does not.

## Retrieval, not memory

Keep a corpus built from your own notes (`build_knowledge.py`) and put the top
chunks in the prompt. Then the model quotes your standard instead of remembering
it. A model that recites a clause number from memory will eventually invent one —
and a clause number that does not exist is worse than no answer at all.
