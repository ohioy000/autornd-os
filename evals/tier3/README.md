# Tier-3 five-arm question experiment (ARCH-20261002-118)

**Status: manifest frozen, awaiting the owner's two ratifications. No paid unit may start.**

This directory holds the frozen plan for the five-arm experiment over the frozen tier-2
question set (25 questions, `frozen-2026-10-03`, ratified by the owner's signoff on
2026-10-03T21:41:20Z). The plan is complete and executable; execution is stopped at two
ratification gates that only the owner can clear.

## The design in one paragraph

Twenty-five questions, three repetitions each, five arms: **375 planned question-runs**
(75 per arm). Every unit is one (question, repetition, arm) triple: the question text from
the frozen `evals/tier2/questions.json` is answered under one arm's registered treatment,
inside an isolated knowledge store (`_isolated_store()`, a fresh temporary Chroma
directory per question-run), under one common 600-second deadline, in a seeded interleaved
order (`random.Random(20261003).shuffle` over the enumerated unit list — no arm runs as a
block). Every delivered answer is scored by the frozen tier-2 scorer against the frozen
keys. The five arms differ only in their registered treatments — the serving(s), the tools,
the cooperation protocol, and the pipeline itself; the question text, the deadline, the
order, the isolation and the scorer are identical across arms.

## The arms

| arm | treatment | pin env | model calls | tools | ceiling/question-run |
|---|---|---|---|---|---|
| A | inexpensive single call, request only | `TIER3_ARM_A` | 1 | none | $0.10 |
| B | the same serving as A + primary-source acquisition and recomputation | `TIER3_ARM_B` (= A's value by design) | up to 3 (the tool loop) | `fetch_primary_source`, `recompute` (both deterministic, no judgment) | $0.20 |
| C | complementary-model cooperation: model 1 drafts, model 2 independently checks, model 1 revises once if model 2 objects | `TIER3_ARM_C_1`, `TIER3_ARM_C_2` | 3 | none | $0.20 |
| D | stronger single call, request only — the strong reference | `TIER3_ARM_D` | 1 | none | $0.20 |
| E | the current pipeline under the standing pins (.env, the owner's, unchanged) | standing pins | up to 40 (the pipeline's own ceiling) | the pipeline's own, under its standing risk gates | $0.50 |

**Arm B** is the treatment-isolation arm: because `TIER3_ARM_B` must equal `TIER3_ARM_A`
(the owner sets both to the same value), any A-vs-B difference is the tools, not the
serving. Its prompt is arm A's prompt verbatim plus the tool registration.

**Arm C** exists because the lab notebook measures two servings with *complementary*
strengths — one measured on engineering convergence (HANDOVER.md §6.9, §6.11: it
converged the build loop), the other on escalation judgment (docs/handover-review.md
§086, the 2026-09-28 shootout: it held escalation 19/20). The protocol, not the models'
discretion, decides what is delivered: model 2's objections are recorded in the transcript;
the delivered answer is model 1's revised answer when model 2 objected (one bounded
revision round), or model 1's draft when model 2 concurred. There is no voting and no
third model.

**Arm D** is the strongest single serving measured in this repository — the same
escalation-tier serving that held 19/20 in §086, the strongest measured hold rate in the
lab notebook. The A-vs-D gap bounds what the treatments can possibly recover: an arm that
beats A but not D is a treatment effect inside the inexpensive band, not a serving effect.

**Arm E** is what the harness ships today, unchanged: the question enters as a scenario
request through the full workflow (triage, engineering, escalation as routed), and the
terminal phase's conclusion is the delivered answer.

## The serving proposals (pending the owner's ratification)

Non-negotiable 6 forbids model ids in code, config, profiles, workflows and user-facing
docs — so this file and the manifest name **pin environment variables**, not servings. The
proposals were made in conversation on 2026-10-03, with their evidence, and are ratified
by the owner setting the env-prefixed pins in `.env` (G-2: experiments run the proposal
env-prefixed; the standing line is the owner's). The selection criteria, with the
lab-notebook evidence each rests on:

- **`TIER3_ARM_A`** — the harness's triage-tier serving: the cheapest tier the harness
  uses productively, measured to classify reliably when pinned (HANDOVER.md §6, the
  triage-reliability measurement; the standing triage pin's evidence).
- **`TIER3_ARM_B`** — identical to `TIER3_ARM_A`'s value, by design (the arm isolates
  the tool treatment).
- **`TIER3_ARM_C_1` / `TIER3_ARM_C_2`** — the complementary pair: the engineering-tier
  serving (§6.9, §6.11) and the escalation-tier serving (§086, 19/20).
- **`TIER3_ARM_D`** — the escalation-tier serving that held 19/20 (§086), the strongest
  measured single serving.
- **Arm E** — the standing pins, unchanged.

A model id is not a system (§6.1): the serving — the model, its provider and its routing —
is what is measured. That is why the pins, not bare model names, are the unit of
ratification, and why the runner records the *resolved* pin (model, provider) for every
unit it executes.

## The two ratification gates (the STOP)

1. **Servings.** The owner sets `TIER3_ARM_A`, `TIER3_ARM_B`, `TIER3_ARM_C_1`,
   `TIER3_ARM_C_2` and `TIER3_ARM_D` in `.env` (`TIER3_ARM_B` = `TIER3_ARM_A`).
2. **Spend.** The owner authorizes the total spend: **$90.00 across the 375 planned
   question-runs** (75 units per arm at $0.10/$0.20/$0.20/$0.20/$0.50). This is an
   authorization ceiling, not a predicted cost. **It is not approved by anything in this
   repository, and it must not be assumed to be approved.**

The experiment does not start without both gates cleared in one line each by the owner.
The runner that consumes this manifest mechanizes the stop: it refuses to start unless the
environment shows both gates cleared (the pin variables set, and `TIER3_SPEND_AUTHORIZED`
set to the ratified dollar amount).

## Failure treatment (registered, not improvised)

Refusal, timeout, tool failure, incomplete runs and outstanding liability are all *counted,
not dropped*: the success measures are fractions of the 75 **planned** units per arm, so a
refused, timed-out or incomplete unit is 0 delivered correctness with its cost and latency
recorded. A unit whose lookups were all refused (arm B's fetch tool) is a poisoned reading,
recorded as such beside its score. Calls that failed after dispatch (the runner's
`unreconciled_liability`, Ruling D45) are included in their unit's cost and in the
total-cost measure.

## The five success measures

1. **Delivered correctness per arm** — the count of the 75 planned units per arm whose
   delivered answer the frozen scorer scores PASS, as a fraction of 75.
2. **Per-question repeat outcomes** — for each question and arm, the 0/3–3/3 distribution
   of its three repetitions. Repeatability is itself a measurement.
3. **Paired wins/losses against A** — per question, each non-A arm's correct-repetition
   count (0–3) against A's: wins/losses/ties across the 25 questions.
4. **Comparison with D** — the same paired measure against the strong reference.
5. **Total cost and latency including failures** — the sum across all 375 units, failures
   and unreconciled liability included; no measure excludes the units that failed.

## What is not here yet

The execution machinery — the runner that consumes this manifest (build the 375-unit plan,
shuffle with the recorded seed, execute each unit under its arm's treatment inside
`_isolated_store()`, score with the frozen scorer, write the ResultsLog, compute the
success measures) — is the next step after ratification. It is free work (mocked-client
tests cost nothing) and can be built and tested before the first paid unit; a mocked
dry-run of the full 375-unit plan (zero cost) is the natural pre-registration check.
