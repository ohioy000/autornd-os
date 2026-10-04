# Golden timing probe, rerun — pre-registration (2026-10-04)

The PR #152 review's item 4 add-on: rerun golden_q1, golden_q2
and golden_q3 through the pipeline on the owner's CORRECTED
lineup, with the spend guard repaired (PR #153, merged). This
document is committed before the first paid call; the measured
record is appended after the run, in the same file, and
committed again.

## The configuration (fixed before the run)

- Branch `arch/20261004-golden-timing-rerun`, cut from main
  at 7908985 — both review PRs merged (#152 at d311654,
  #153 at 7908985).
- Scenarios: golden_q1, golden_q2, golden_q3 — byte-copies of
  `evals/scenarios/golden/`, held in `/tmp/golden-q123/` so the
  sweep loads exactly the three (the loader does not recurse).
- Workflow `engineering-rnd` (the golden scenarios name no
  workflow of their own).
- Repeat 1, timeout 600 s (the scenarios' own timeout),
  max_calls 40 (the scenarios' own bound).
- Caps: `--max-spend 0.50` (one scenario-run),
  `--max-spend-sweep 1.50` (the invocation — 3 × $0.50, exact).
- Pins: the standing `.env` — the corrected lineup: triage and
  research google/gemini-3.8-flash, engineering
  thinkingmachines/inkling-small (the owner removed the
  `:exacto` suffix after the first reading), architecture
  xiaomi/mimo-v2.6-pro:exacto, escalation
  moonshotai/kimi-k3:exacto, judge
  qwen/qwen3-235b-a22b-2507:exacto, search perplexity/sonar,
  ranker qwen/qwen3-reranker-8b, premium unset; the
  owner-directed caps (plan 14000, escalation 13000, validate
  16000, judge 16000, search 8000/16000); provider order
  engineering:deepinfra/fp8, judge:deepinfra/fp8, fallbacks
  off.
- **Measurement fidelity (a departure from the first probe's
  invocation, recorded):** the shell still exports the OLD
  lineup (engineering qwen/qwen3-235b-a22b-2507, judge
  moonshotai/kimi-k2.5:exacto, premium
  openai/gpt-6.1-sol-pro:exacto, plan 78000, the old provider
  order), and the harness reads environment variables OVER
  `.env`. The invocation therefore removes the stale exports
  for its own process (`env -u ...`), so the `.env` is the
  source of truth. The owner's own runs need a fresh shell for
  the same reason.
- Preflight: run free, not skipped, BEFORE the paid run —
  measured **29 ok, 1 failing**: the engineering endpoint
  (DeepInfra | thinkingmachines/inkling-small-20260730, the
  catalogue's ONLY endpoint for the model) does not list
  `response_format`, which the harness sends on engineering
  calls. The pin serves (that check passed); removing the
  `:exacto` suffix changed nothing (same single endpoint). The
  sweep itself runs with `--skip-preflight` — the owner's
  recorded override — so the results header records
  `{ran: false, override: true}`. Runtime safety net, already
  shipped and tested: a 400 with `response_format` is logged,
  the parameter is dropped, and the call retried
  (`autornd/routing/openrouter.py:694-699`).
- The repaired spend guard (PR #153): on this lineup the
  worst-case table bounds every tier — triage/research
  google/gemini-3.8-flash $0.0766/call (per-request $0.0140),
  search perplexity/sonar $0.0226 ($0.0050), architecture
  $0.0129, engineering $0.0175, judge $0.0057, escalation
  $0.1832 — so the pre-call guard enforces the $0.50 per-run
  ceiling on bounded worst cases, not only on booked costs.
  (The first probe ran under the unrepaired guard, whose
  worst-case table printed "unknown (no rate)" for every tier.)

## The prediction (registered before the first paid call)

1. The results header records `{ran: false, override: true}`;
   the free preflight's findings (29 ok, 1 failing — the
   engineering endpoint's `response_format` declaration) are
   recorded in this document, not in the header.
2. Engineering calls may log the 400-with-response_format
   warning and retry without it; a retried call is not a
   failure. An engineering call that fails after the retry is
   a falsifier.
3. Every unit is bounded: 600 s, 40 calls, max_iterations 5,
   and the deliberation watchdog (Ruling D38) ends a hung run
   by its own terminal.
4. Total spend lands under the $1.50 sweep cap. The first
   probe (the old lineup) spent $0.1064 of $1.50; the
   corrected lineup's tiers are catalogue-priced and bounded
   by the repaired guard.
5. Pace: the plan node (architecture, mimo-v2.6-pro:exacto —
   unchanged since the first probe) is expected at the first
   probe's pace (126–293 s per plan iteration); the
   engineering tier (inkling-small, a small model) is expected
   faster than the old engineering pin; the judge
   (qwen3-235b-a22b-2507:exacto) is new and unmeasured — its
   validating-call pace is the open question. Whether one
   iteration plus one judging round fits the 600 s deadline is
   the measurement the probe exists to make.
6. `PLAN_MAX_TOKENS=14000` binds: the first probe's Q3 plan
   recorded 18,069 completion tokens; under the standing cap a
   Q3-scale plan is truncated at 14,000 tokens.
7. What this probe does NOT predict: whether units ship. The
   first probe shipped 0/3 on pace; the corrected lineup's
   pace is the measurement.

Falsifiers: a second preflight finding (beyond the known
declaration gap); a unit past its 600 s bound or its 40 calls;
a sweep spend above $1.50; a spend-guard refusal; an
engineering call that fails after the 400-retry.

## Caveats carried from the first probe

- The probe runs with an empty knowledge store (no ingested
  collection exists in this environment), so the context node
  takes its no-documentation scoping path and **no search-tier
  call is made** — the 0/3-or-better result reflects pace and
  the pipeline's own bounds, not answer quality.
- The timing figures are unaffected by the store: the plan and
  judge nodes' pace is a property of the servings.
