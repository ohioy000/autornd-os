# Serving ledger — which serving has run which tier, and how it went

**Generated from `docs/traces/*.jsonl`. Do not hand-edit.** Regenerate with:

```bash
.venv/bin/python3 -c "import sys;sys.path.insert(0,'.');\
from tests.serving_ledger import derive,render;print(render(derive('docs/traces')))"
```

`tests/test_serving_ledger.py` regenerates this table and fails if the committed
one has drifted, so it cannot go stale the way a hand-stamped fact does
(convention 24).

## Why this file exists

Which serving works at which tier is **the most expensive fact this project
keeps re-buying.** It was recorded in §6.1's triage table, §6.11's convergence
finding, B4's six-way pin test, the B12 sweep traces, and two pre-registrations
— and in none of them *together*. So every session re-derived it from trace
headers at the cost of a live run. §6.1 still carries a row reading
*"(unrecorded, likely StreamLake)"*.

Every committed trace header already names its model map and its provider pins,
and every unit beneath it names a terminal. **The record was always there; it
was never indexed.** This is that index.

## The ledger

| tier | model | serving | n | completed | other terminals | errors |
|---|---|---|---|---|---|---|
| `architecture` | `deepseek/deepseek-v4-pro` | **StreamLake** | 301 | 257 | blocked 6, escalated 4 | 34 |
| `architecture` | `z-ai/glm-5.3` | **StreamLake** | 1 | 0 | — | 1 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DeepInfra** | 4 | 0 | — | 4 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DigitalOcean** | 6 | 1 | escalated 1 | 4 |
| `engineering` | `deepseek/deepseek-v4-flash` | **GMICloud** | 233 | 225 | escalated 1 | 7 |
| `engineering` | `deepseek/deepseek-v4-flash` | **OpenInference** | 7 | 6 | — | 1 |
| `engineering` | `deepseek/deepseek-v4-flash` | **SiliconFlow** | 3 | 0 | — | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **StreamLake** | 4 | 1 | — | 3 |
| `engineering` | `google/gemini-2.5-flash` | **GMICloud** | 1 | 0 | — | 1 |
| `triage` | `deepseek/deepseek-v4-flash` | **Alibaba** | 306 | 258 | blocked 7, escalated 4 | 37 |

## How to read it, and how not to

**This is not a ranking.** The n column is whatever the blueprints happened to
run, not a designed comparison: an arm with 233 units and one with 3 are not
comparable evidence, and convention 23 still governs — compliance first, then
iterations to termination, then speed, **never at n=1**.

**A pin is not portable without its model.** The tier and the serving alone do
not identify a configuration; the *model* is the third column for that reason.
`architecture`/**StreamLake** reads 257 completed of 301 against
`deepseek/deepseek-v4-pro`, and 0 of 1 against `z-ai/glm-5.3` — the same pin,
a different map, and it fails immediately because StreamLake serves no endpoint
for that model. That single row is the whole lesson.

**An `error` is not a verdict on the serving.** It is an apparatus reading until
something rules the apparatus out (convention 18). The error counts here mix
provider 429s, expiries, malformed model ids and budget stops.

## What it already corrects

`engineering`/`deepseek-v4-flash`/**GMICloud** stands at **225 completed of 233,
with 7 errors** — a ~97% terminal rate over the largest arm in the table. On
2026-09-20 the executor recorded GMICloud as *disqualified on compliance* in
§27.2 on the strength of **two** failures during B016 Part E. Against 233
committed units that call was not close, and it was retracted the same day after
a re-sweep found five other servings failing alongside it and GMICloud itself
completing 90 seconds later.

**Had this table existed, that conclusion would not have been drawn, and the
sweep that corrected it need not have been bought.** That is the argument for
generating the fact rather than re-deriving it, stated in the cost it already
saved nobody.

## What it does not yet record

- **Iterations to termination and seconds per call**, which convention 23 ranks
  above speed and below compliance. Both are in the unit records and are a
  natural extension of this file.
- **Why** an error was an error. The terminal is captured; the cause is not.
- **The unpinned arms.** A tier named with an empty value is explicitly unpinned
  and is skipped here, because a rotation is not a serving.
