# Contributing

The weakest link in this project is data, not code. If you build joinery, your
corrected mistakes are worth more than any model improvement.

## What to send

One JSON object per line (JSONL), three fields:

```json
{"task": "fix", "prompt": "the spec or the question as it was actually asked",
 "answer": "the violations found, then the corrected spec JSON"}
```

`task` is one of:

| task | input | answer | why it matters |
|---|---|---|---|
| `spec` | a request in plain language | unit spec JSON | feeds the DXF generator |
| `fix` | a spec that breaks the rules | violation list + corrected spec | **most valuable** — teaches what is wrong |
| `rule` | a drafting / construction question | the answer, citing file + section | keeps claims traceable |
| `lisp` | a drawing intent | AutoLISP that actually ran | direct CAD output |

## Rules for a submission

1. **Run the gate first.** `.venv/bin/python scripts/validate_spec.py your_spec.json`
   must print `ACCEPT`. The dataset builder re-checks and silently drops failures.
2. **No client material.** No project names, client names, drawing numbers, prices,
   schedules, photos of sites, or anything covered by an NDA. Numbers, dimensions
   and method only.
3. **Real wording.** Write the prompt the way a foreman or a designer actually said
   it, not textbook prose. Mixed Arabic/English is fine and useful.
4. **One case per line.** If a case needs two specs (before/after), use `fix`.
5. **Say what changed.** For `fix`, name the rule that was broken, e.g.
   `rules.yaml › doors.gap_max`.

## How to submit

- **Pull request** against this repo, adding a file under `data/raw/` (name it
  `yourname-YYYY-MM.jsonl`), or
- **Issue** with the file attached if you are not comfortable with git.

A CI job runs `validate_spec.py` on every spec in the change and `build_dataset.py`
over `data/raw`, so a broken pair fails in review rather than in training.

## What happens to it

Accepted pairs go into a training set; the workshop rules they touch are listed in
the build report (`build_report.json`: kept, duplicates, rejected-by-gate, entity
hits). Contributors are credited in the model card unless they ask not to be.

## Licence of contributions

By submitting data you agree it is licensed **CC-BY-4.0** (attribution), and code
under **Apache-2.0**. Do not submit anything you do not have the right to license.
