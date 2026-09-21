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
| `architecture` | `deepseek/deepseek-v4-pro` | **StreamLake** | 340 | 285 | blocked 8, escalated 8 | 39 |
| `architecture` | `z-ai/glm-5.3` | **StreamLake** | 1 | 0 | — | 1 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DeepInfra** | 10 | 2 | — | 8 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DigitalOcean** | 12 | 5 | escalated 2 | 5 |
| `engineering` | `deepseek/deepseek-v4-flash` | **GMICloud** | 242 | 233 | blocked 1, escalated 1 | 7 |
| `engineering` | `deepseek/deepseek-v4-flash` | **OpenInference** | 13 | 10 | escalated 2 | 1 |
| `engineering` | `deepseek/deepseek-v4-flash` | **SiliconFlow** | 9 | 6 | — | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **StreamLake** | 10 | 5 | blocked 1, escalated 1 | 3 |
| `engineering` | `google/gemini-2.5-flash` | **GMICloud** | 1 | 0 | — | 1 |
| `triage` | `deepseek/deepseek-v4-flash` | **Alibaba** | 345 | 286 | blocked 9, escalated 8 | 42 |

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

## The intermittent 429, diagnosed 2026-09-20

**It is not the servings, not our request rate, and not our account.** It is
OpenRouter's own upstream capacity for one **(model, provider)** pair. The body
says so, and the harness was discarding the half that said it:

> `deepseek/deepseek-v4-flash is temporarily rate-limited upstream. Please retry
> shortly, or add your own key…`

Controls, same key, same minute:

| probe | result |
|---|---|
| a different model (`deepseek-v4-pro`), unpinned | **OK** |
| the same model via **Alibaba** — triage's pin | **OK** |
| the same model **unpinned** — rotation chose DigitalOcean | **OK** |
| the same model via **GMICloud** | **429** |

`max_tokens` is not the trigger either: a 16,384-token reservation with a short
prompt succeeded on DeepInfra in the same sequence where a *small* request 429'd
on StreamLake.

**Why it looked like an engineering-tier fault.** Every one of the ten 429s
landed on an engineering node — `implement` eight times, `validate` twice — and
none on triage, architecture or research. Three things stacked:

1. `triage` runs the **same model** via **Alibaba**, which was not capacity-
   limited, so triage never failed.
2. `architecture` runs a **different model** entirely, so it was never exposed.
3. **Fallbacks are disabled by design** (§6.1 — pinning is a quality control).
   A pinned tier has nowhere to go when its one provider is short, so a
   transient shortage becomes a dead run. Unpinned, the rotation finds a working
   host immediately — which is why E1 attempt 4 completed, and that was recorded
   at the time as "unpinning helped" without understanding why.

**The pin plus disabled fallbacks converts a transient upstream shortage into a
hard run failure.** That is the mechanism, and it is a property of the
configuration rather than of any serving in the table above.

Repaired the same day (`tests/test_rate_limit_retry.py`): the upstream sentence
now travels with the exception, and a 429 is retried with bounded backoff
because the upstream itself calls the condition transient.

## What it does not yet record

- **Iterations to termination and seconds per call**, which convention 23 ranks
  above speed and below compliance. Both are in the unit records and are a
  natural extension of this file.
- **Why** an error was an error. The terminal is captured; the cause is not.
- **The unpinned arms.** A tier named with an empty value is explicitly unpinned
  and is skipped here, because a rotation is not a serving.
