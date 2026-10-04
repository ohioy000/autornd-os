# Golden timing probe — pre-registration (2026-10-04)

The owner's authorized add-on to ARCH-20261003-119 (kept off 119's
branch because 119 is free-only): a $1.50-ceiling timing probe of
golden_q1, golden_q2 and golden_q3 through the current pipeline on
the owner's standing lineup. This document is committed before the
first paid call; the measured record is appended after the run, in
the same file, and committed again.

## The configuration (fixed before the run)

- Branch `arch/20261004-golden-timing-probe`, cut from main at
  7a7fc6a — the pipeline as it ships.
- Scenarios: golden_q1, golden_q2, golden_q3 — byte-copies of
  `evals/scenarios/golden/`, held in `/tmp/golden-q123/` so the
  sweep loads exactly the three (the loader does not recurse).
- Workflow `engineering-rnd` (the golden scenarios name no workflow
  of their own).
- Repeat 1, timeout 600 s (the scenarios' own timeout), max_calls 40
  (the scenarios' own bound).
- Caps: `--max-spend 0.50` (one scenario-run), `--max-spend-sweep
  1.50` (the invocation — 3 × $0.50, exact).
- Pins: the standing `.env` — the owner's lineup (triage and research
  google/gemini-3.8-flash, engineering qwen/qwen3-235b-a22b-2507,
  architecture xiaomi/mimo-v2.6-pro:exacto, escalation
  moonshotai/kimi-k3:exacto, judge moonshotai/kimi-k2.5:exacto,
  search perplexity/sonar, ranker qwen/qwen3-reranker-8b), with the
  owner-directed caps (plan 14000, escalation 13000, validate 16000,
  judge 16000, search 8000/16000). No env prefix: the standing line
  is the owner's (G-2), and the harness preflight resolves it.
- Preflight: run, not skipped. Measured before the run: **31 ok,
  0 failing** — the engineering pin's endpoint (nebius/fp8) lists
  `response_format`, so the refusal the owner anticipated against the
  earlier inkling-small pin does not apply to the standing lineup.
  No override.

## The prediction (registered before the first paid call)

1. The preflight passes and the results header records
   `{ran: true, override: false, passed: true}`.
2. Every unit is bounded: each scenario's own timeout (600 s) and
   max_calls (40) and the pipeline's loop bounds (max_iterations 5)
   apply, so no unit runs past its bound, and the watchdog ends a
   hung run by its own terminal.
3. Total spend lands under the $1.50 sweep cap. The 102 golden sweep
   (2026-10-01, the 09-26-era lineup) cost $0.0264 / $0.0844 /
   $0.0719 on Q1 / Q2 / Q3; the current lineup's priced tiers are of
   the same order, and the three `:exacto` tiers' rates are unknown
   to the catalogue (the arm-E unboundable finding, reported under
   119's questions), so the caps — not a prediction — are the real
   bound. The spend guard is blind for the unboundable tiers, so a
   single call is bounded only by its booked cost after it lands;
   the per-run and sweep caps are enforced on the booked figures.
4. Q1 (a computation with a definite answer) is the most likely of
   the three to ship; Q2 and Q3 route through the research and
   search tiers, whose behavior under this lineup is unmeasured.
5. What this probe does **not** predict: the per-unit times. The
   lineup changed on every tier since 102, and the 09-29 lineup's
   recorded pipeline units (plans of 409–1,097 s, judging of
   972–3,078 s) cannot complete inside the 600 s deadline — which
   lineage the current lineup's timing resembles is the measurement
   the probe exists to make.

Falsifiers: a preflight failure or an override in the header; a unit
past its 600 s bound or its 40 calls; a sweep spend above $1.50; a
spend-guard refusal.

## The measured record (2026-10-04)

**The preflight: 31 checks passed, no override** — the results
header records `{ran: true, override: false, passed: true}`, so
prediction 1 held. The CLI's worst-case table printed
`unknown (no rate)` for every tier: the client rates only
catalogue entries priced on both sides with no charge beside
prompt and completion tokens (D49), and under the owner's
lineup every tier is unrated — four carry charges beside the
token rates (web_search on the triage and research servings,
web_search on search, input_cache_read on engineering) and
three `:exacto` pins are served but unpriced. The guard was
therefore blind for every call in this sweep, and the caps were
enforced on booked costs only. The tier-3 runner's `worst-case`
table reports the same fact per tier ("no worst case the guard
can bound"); the two instruments agree.

**The sweep: 0/3 shipped, 0/3 passed. 21 calls, 1660.5 s,
$0.1064 of the $1.50 sweep cap (7.1%).** No spend-guard
refusal: no unit was skipped, no call was refused, and no
per-run cap ($0.50) was approached — the largest unit cost
$0.0401. Predictions 2 and 3 held (every unit bounded by its
own watchdog terminal, written inside the 0.4 s reserve; spend
far under the cap). Prediction 4 was refuted: Q1 did not ship.

Per unit (the owner's fields, from the unit records):

| unit | shipped | total s | plan node s | plan completion tokens | judge s | calls | cost |
|---|---|---|---|---|---|---|---|
| golden_q1 | no — blocked, no answer | 461.3 | 126.0 | 6,111 | 290.9 (1 billed call) | 8 | $0.0394 |
| golden_q2 | no — blocked, no answer | 599.6 | 293.1 | 13,901 | 273.8 (cancelled, unbilled) | 7 | $0.0270 |
| golden_q3 | no — blocked, no answer | 599.6 | 282.5 | 18,069 | 271.6 (cancelled, unbilled) | 6 | $0.0401 |

Calls by tier, per unit: Q1 triage 1, research 2, architecture 1,
engineering 3, judge 1; Q2 triage 1, research 2, architecture 1,
engineering 3, judge 0; Q3 triage 1, research 2, architecture 1,
engineering 2, judge 0. The plan node is the architecture tier's
one call per unit, so the architecture tier's completion tokens
are the plan node's. Cost by tier across the sweep: architecture
$0.0349, judge $0.0205, triage $0.0203, research $0.0178,
engineering $0.0129. Served by: architecture via Xiaomi,
engineering via Nebius, judge via SiliconFlow, research and
triage via Google AI Studio.

**How each unit ended** (the deliberation watchdog, Ruling D38,
fired in all three):

- **Q1** stopped at 461.27 s, rule `not_started`: the judge
  call at `validate` (iteration 2) was not started — its measured
  pace was 290.861 s and only 138.333 s of the 600 s budget
  remained before the 0.4 s reserve. No implementation was agreed
  by the build judges; the latest implementation is unjudged.
- **Q2** stopped at 599.60 s, rule `cancelled`: the judge call
  at `validate` (iteration 1) was cancelled at 599.603 s,
  leaving the 0.4 s reserve to write the terminal; unjudged.
- **Q3** stopped at 599.60 s, rule `cancelled`: the same shape,
  cancelled at 599.604 s; unjudged.

The delivery state is `no answer` in all three — not even
"approved, not shipped": the build judges never agreed on an
implementation (`watchdog.approved.agreed` false, `index`
null), so score_trace reads no answer.

**The pace finding — the measurement the probe existed to make.**
Under the owner's current lineup the plan node (architecture
tier) runs 126–293 s per iteration and writes 6,111–18,069
completion tokens (~16–21 s per 1k tokens), and the judge's
validating call runs 271–291 s (~34 s per 1k tokens, 8,590
completion tokens in Q1's one billed judge call). One plan
iteration plus one judging round is 397–584 s — at or past the
600 s deadline — so a second judging round never fits, and the
watchdog ends the run before the build judges agree. This is the
09-29 lineage's behavior (plans of 409–1,097 s and judging of
972–3,078 s, which the command's evidence recorded as unable to
complete a plan and a judging round inside the common deadline),
not the 09-26 lineage's (Q1 at 90.7 s, 3/6 shipped in 102).
Prediction 5's open question is answered: the current lineup
resembles the 09-29 lineage on the deadline dimension.

**The implication for arm E.** Arm E runs this pipeline under the
standing pins with the common 600-second deadline. Measured
here: under the owner's current lineup an arm-E unit ends blocked
by the watchdog with an unjudged implementation — a "no answer"
— so arm E would measure the lineup's latency, not the
pipeline's answer quality. Which lineup arm E runs remains the
owner's decision (G-2); this is the measurement that decision
now has.

**The caveat (the environment).** The probe ran with an empty
knowledge store — no ingested collection exists in this
environment ("Knowledge collection not found", once per context
round). The context node therefore ran its no-documentation
scoping path (1,232–1,741 characters of scoping context per
unit, `grounded: true` by the node's own verdict), and **no
search-tier call was made in any unit** — where 102's Q2 (the
same confined-space question) made one. The lookup question's
grounding path (knowledge retrieval and the search tier) was not
exercised, and Q2's CFR text was not retrieved in this run (it
was not retrieved in 102 either — that run's own record declared
the source missing). The 0/3 result reflects pace, not answer
quality: no unit reached a delivered answer, so no ungrounded
answer shipped. The timing figures are unaffected — the plan and
judge nodes' pace is a property of the servings, not of the
store.

**The record is kept**: `evals/results/probe-20261004-golden-q123.jsonl`
(git-ignored scratch, 105,605 bytes — the header plus the three
unit records; `evals/results/` is ignored, so no mirror was
needed and no git operation can unlink it mid-run). The sweep's
own summary, verbatim:

```
workflow: engineering-rnd   repetitions: 1
scenario                    rate  calls    secs   flaky assertions
--------------------------------------------------------------------------------------------
golden_q1                    0/1      8   461.3   ended blocked 1; status 1/1 — stopped by the deliberation watchdog (Ruling D38): the judge call at 'validate' (iteration 2) was not started: this node's pace is 290.861s and only 138.333s of the 600s budget remain before the 0.4s reserve; no implementation was agreed by the build judges; the latest implementation is not approved (unjudged)
golden_q2                    0/1      7   599.6   ended blocked 1; status 1/1 — stopped by the deliberation watchdog (Ruling D38): the judge call at 'validate' (iteration 1) was cancelled at 599.603s of the 600s budget, leaving the 0.4s reserve to write this terminal; no implementation was agreed by the build judges; the latest implementation is not approved (unjudged)
golden_q3                    0/1      6   599.6   ended blocked 1; status 1/1 — stopped by the deliberation watchdog (Ruling D38): the judge call at 'validate' (iteration 1) was cancelled at 599.604s of the 600s budget, leaving the 0.4s reserve to write this terminal; no implementation was agreed by the build judges; the latest implementation is not approved (unjudged)
--------------------------------------------------------------------------------------------
0/3 scenarios passed their assertions every repetition (runs ended blocked 3)  ·  21 calls  ·  1660.5s  ·  $0.1064
spend by tier: architecture $0.0349, judge $0.0205, triage $0.0203, research $0.0178, engineering $0.0129
served by: architecture via Xiaomi, engineering via Nebius, judge via SiliconFlow, research via Google AI Studio, triage via Google AI Studio

sweep budget: $0.1064 of $1.5000
```

score_trace's reading of the same file:

```
Q1   FAIL (no answer)   blocked    no answer              items[] 461.268s/300s $0.0394/0.5 risk=medium sprawl=None scope_out=None
Q2   FAIL (no answer)   blocked    no answer              items[] 599.604s/300s $0.027/0.5 risk=critical sprawl=None scope_out=None
Q3   FAIL (no answer)   blocked    no answer              items[] 599.605s/300s $0.0401/0.5 risk=medium sprawl=None scope_out=None

0/3 PASS · 0/3 shipped · median sprawl None · total $0.1065 · key v1
```
