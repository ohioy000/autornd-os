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

| tier | model | serving | how | n | completed | other terminals | errors |
|---|---|---|---|---|---|---|---|
| `architecture` | `deepseek/deepseek-v4-pro` | **Alibaba** | rotated | 1 | 0 | — | 1 |
| `architecture` | `deepseek/deepseek-v4-pro` | **Baidu** | rotated | 2 | 1 | — | 1 |
| `architecture` | `deepseek/deepseek-v4-pro` | **DigitalOcean** | rotated | 2 | 1 | blocked 1 | 0 |
| `architecture` | `deepseek/deepseek-v4-pro` | **Novita** | rotated | 2 | 1 | blocked 1 | 0 |
| `architecture` | `deepseek/deepseek-v4-pro` | **SiliconFlow** | rotated | 2 | 1 | blocked 1 | 0 |
| `architecture` | `deepseek/deepseek-v4-pro` | **StreamLake** | rotated | 1 | 1 | — | 0 |
| `architecture` | `deepseek/deepseek-v4-pro` | **StreamLake** | pinned | 346 | 285 | blocked 13, escalated 8 | 40 |
| `architecture` | `thinkingmachines/inkling-small` | **DeepInfra** | pinned | 2 | 1 | blocked 1 | 0 |
| `architecture` | `z-ai/glm-5.3` | **Alibaba** | pinned | 1 | 0 | blocked 1 | 0 |
| `architecture` | `z-ai/glm-5.3` | **Baidu** | pinned | 1 | 0 | blocked 1 | 0 |
| `architecture` | `z-ai/glm-5.3` | **Relace** | pinned | 3 | 0 | blocked 3 | 0 |
| `architecture` | `z-ai/glm-5.3` | **StreamLake** | pinned | 1 | 0 | — | 1 |
| `architecture` | `z-ai/glm-5.3-prime` | **Alibaba** | pinned | 2 | 0 | blocked 2 | 0 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Alibaba** | rotated | 4 | 0 | blocked 2 | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **AtlasCloud** | rotated | 3 | 0 | — | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Azure** | rotated | 2 | 0 | escalated 1 | 1 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Baidu** | rotated | 2 | 0 | blocked 2 | 0 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DeepInfra** | rotated | 6 | 0 | blocked 3, escalated 1 | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DeepInfra** | pinned | 10 | 2 | — | 8 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DigitalOcean** | rotated | 8 | 0 | blocked 1, escalated 1 | 6 |
| `engineering` | `deepseek/deepseek-v4-flash` | **DigitalOcean** | pinned | 12 | 5 | escalated 2 | 5 |
| `engineering` | `deepseek/deepseek-v4-flash` | **GMICloud** | rotated | 5 | 0 | blocked 2 | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **GMICloud** | pinned | 248 | 233 | blocked 6, escalated 1 | 8 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Mancer 2** | rotated | 3 | 1 | — | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **NextBit** | rotated | 3 | 0 | blocked 1 | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Novita** | rotated | 4 | 1 | blocked 1 | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **OpenInference** | rotated | 18 | 2 | blocked 4, escalated 2 | 10 |
| `engineering` | `deepseek/deepseek-v4-flash` | **OpenInference** | pinned | 13 | 10 | escalated 2 | 1 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Parasail** | rotated | 3 | 0 | — | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Phala** | rotated | 4 | 0 | blocked 1 | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **SiliconFlow** | rotated | 2 | 0 | blocked 1, escalated 1 | 0 |
| `engineering` | `deepseek/deepseek-v4-flash` | **SiliconFlow** | pinned | 9 | 6 | — | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **StreamLake** | rotated | 6 | 1 | blocked 2 | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **StreamLake** | pinned | 10 | 5 | blocked 1, escalated 1 | 3 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Venice** | rotated | 4 | 0 | blocked 2 | 2 |
| `engineering` | `deepseek/deepseek-v4-flash` | **Wafer** | rotated | 2 | 0 | — | 2 |
| `engineering` | `google/gemini-2.5-flash` | **GMICloud** | pinned | 1 | 0 | — | 1 |
| `engineering` | `xiaomi/mimo-v2.6-flash` | **Xiaomi** | pinned | 9 | 1 | blocked 8 | 0 |
| `escalation` | `moonshotai/kimi-k3` | **Chutes** | rotated | 1 | 0 | escalated 1 | 0 |
| `escalation` | `moonshotai/kimi-k3` | **DeepInfra** | rotated | 2 | 0 | — | 2 |
| `escalation` | `moonshotai/kimi-k3` | **DigitalOcean** | rotated | 4 | 0 | escalated 1 | 3 |
| `escalation` | `moonshotai/kimi-k3` | **InferenceNet** | rotated | 1 | 0 | — | 1 |
| `escalation` | `moonshotai/kimi-k3` | **Modal** | rotated | 2 | 0 | blocked 1 | 1 |
| `escalation` | `moonshotai/kimi-k3` | **Moonshot AI** | pinned | 14 | 1 | blocked 13 | 0 |
| `escalation` | `moonshotai/kimi-k3` | **Sail Research** | rotated | 4 | 0 | escalated 1 | 3 |
| `escalation` | `moonshotai/kimi-k3` | **Together** | rotated | 3 | 0 | blocked 1 | 2 |
| `premium` | `z-ai/glm-5.3` | **Friendli** | pinned | 8 | 0 | blocked 8 | 0 |
| `premium` | `z-ai/glm-5.3-prime` | **Alibaba** | pinned | 6 | 1 | blocked 5 | 0 |
| `ranker` | `qwen/qwen3-reranker-8b` | **Fireworks** | pinned | 14 | 1 | blocked 13 | 0 |
| `research` | `google/gemini-2.5-flash` | **Google** | rotated | 126 | 68 | blocked 9, escalated 8 | 41 |
| `research` | `google/gemini-2.5-flash` | **Google** | pinned | 14 | 1 | blocked 13 | 0 |
| `research` | `moonshotai/kimi-k3` | **InferenceNet** | rotated | 1 | 0 | — | 1 |
| `research` | `moonshotai/kimi-k3` | **Modal** | rotated | 1 | 0 | — | 1 |
| `search` | `perplexity/sonar` | **Perplexity** | rotated | 54 | 22 | blocked 4, escalated 3 | 25 |
| `search` | `perplexity/sonar` | **Perplexity** | pinned | 14 | 1 | blocked 13 | 0 |
| `search` | `perplexity/sonar-pro` | **Perplexity** | rotated | 30 | 24 | blocked 2, escalated 1 | 3 |
| `triage` | `deepseek/deepseek-v4-flash` | **Alibaba** | pinned | 360 | 287 | blocked 22, escalated 8 | 43 |

## How to read it, and how not to

**This is not a ranking.** The n column is whatever the blueprints happened to
run, not a designed comparison: an arm with 233 units and one with 3 are not
comparable evidence, and convention 23 still governs — compliance first, then
iterations to termination, then speed, **never at n=1**.

**`pinned` and `rotated` are different evidence and are never added together.**
A pinned row is what a serving did when it was *asked*; a rotated row is what it
did when OpenRouter's own routing chose it. The same provider appears in both
columns for `engineering` — GMICloud and DigitalOcean each ran the tier both
ways — and folding them would claim a pin's evidence for rotation's.
**Rotated rows are far noisier by construction**: rotation reaches for a
different provider precisely when the first one failed, so a rotated arm's
errors include the failure that caused the rotation.

**This table was blind until 2026-09-22.** The derivation walked the header's
pins and skipped any tier whose pin was empty, so an unpinned tier produced no
row — and the table carried **three tiers while looking complete**. The tier it
omitted was `escalation`, which §6.10 measures at **70–78% of hard-trace
spend**. The most expensive tier in the system was the one the instrument could
not see, and nothing said so. It is the canonical exhibit for **convention 28**:
*an instrument asserts that it computed its subject before it asserts anything
about it.*

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
