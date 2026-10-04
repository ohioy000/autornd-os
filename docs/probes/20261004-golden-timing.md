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

## The measured record

(appended after the run)
