# Tier-3 five-arm question experiment

**Status: runnable (ARCH-20261003-119). The plan is frozen (`frozen-2026-10-03`,
manifest `tier3-2`), the runner is built and proved by a mocked dry run of all
375 units, and execution stops at the owner's two ratification gates. No paid
unit may start until the owner clears both.**

This directory holds the frozen plan for the five-arm experiment over the frozen
tier-2 question set (25 questions, `frozen-2026-10-03`, ratified by the owner's
signoff on 2026-10-03T21:41:20Z). The runner that consumes it is
`evals/tier3/runner.py` (built by ARCH-20261003-119, Ruling D50).

## The design in one paragraph

Twenty-five questions, three repetitions each, five arms: **375 planned question-runs**
(75 per arm). Every unit is one (question, repetition, arm) triple: the question text from
the frozen `evals/tier2/questions.json` is answered under one arm's registered treatment,
inside an isolated knowledge store (`_isolated_store()`, a fresh temporary Chroma
directory per question-run), under one common 600-second deadline, in a seeded interleaved
order (`random.Random(20261003).shuffle` over the enumerated unit list — no arm runs as a
block; the order's sha256 is recorded in the results header and the resume guard
reconstructs it). Every delivered answer is scored by the frozen tier-2 scorer against the frozen
keys. The five arms differ only in their registered treatments — the serving(s), the tools,
the cooperation protocol, and the pipeline itself; the question text, the deadline, the
order, the isolation and the scorer are identical across arms. Every call the runner makes
carries the registered parameters: **max_tokens 8000, temperature 0.3**.

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
serving. Its prompt is arm A's prompt verbatim plus the tool registration — exactly two
registered differences, nothing else. The tool loop's structure is registered: calls 1
and 2 offer the two tools, call 3 offers none (the model must answer); each round's tool
results are inlined into the next call's user message; at most 3 calls and 20 tool
invocations per unit. The fetch tool is **closed-world**: it serves the archived July 1,
2014 editions under `evals/tier2/sources/` and answers any other citation with a typed
not-available result — recorded, not a refusal — and opens no socket (the suite's network
guard is the proof). The recompute tool accepts the registered arithmetic grammar only
(translated written forms, the constants, the whitelisted functions, powers within the
exponent bound); anything else is a typed rejection the model reads as the answer to its
request.

**Arm C** exists because the lab notebook measures two servings with *complementary*
strengths — one measured on engineering convergence (HANDOVER.md §6.9, §6.11: it
converged the build loop), the other on escalation judgment (the 086 escalation shootout,
`docs/traces/086-escalation-shootout.jsonl`: it held escalation 19/20 against 13/20 — a
shootout that graded escalation output, not direct answers to questions). The protocol,
not the models' discretion, decides what is delivered: model 2's check is a **typed
verdict** — `{"concur": boolean, "objections": [string]}` — requested through the
client's JSON response-format handling; the delivered answer is model 1's revised answer
when model 2 objected (one bounded revision round, the objections inlined into the
revision call), or model 1's draft when model 2 concurred. A check that answers in any
other shape is not a verdict: after the bounded retries it is recorded "unavailable" and
the draft is delivered — never a concurrence, never a refusal to deliver. When the
retries spend the last call, the starvation is recorded ("starved") and the draft is
delivered with the objection beside it. There is no voting and no third model.

**Arm D** is the strongest single serving measured in this repository — the same
escalation-tier serving that held 19/20 in the 086 shootout, the strongest measured hold
rate in the lab notebook. The A-vs-D gap bounds what the treatments can possibly recover:
an arm that beats A but not D is a treatment effect inside the inexpensive band, not a
serving effect.

**Arm E** is what the harness ships today, unchanged: the question enters as a scenario
request through the full workflow (triage, engineering, escalation as routed), and the
terminal phase's conclusion is the delivered answer. **Delivered means a completed
terminal's conclusion** (D49, Ruling D50 (3)): a judge-approved draft that no completed
terminal shipped by the deadline is "approved, not shipped" — scored, reported beside the
delivered count, and never counted as delivered.

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
  serving (§6.9, §6.11) and the escalation-tier serving (the 086 escalation shootout,
  19/20 against 13/20, grading escalation output).
- **`TIER3_ARM_D`** — the escalation-tier serving that held 19/20 (086), the strongest
  measured single serving.
- **Arm E** — the standing pins, unchanged, resolved per tier (triage, research, search,
  architecture, engineering, escalation, judge).

A model id is not a system (§6.1): the serving — the model, its provider and its routing —
is what is measured. That is why the pins, not bare model names, are the unit of
ratification, and why the runner records the *resolved* pin (model, provider) for every
unit it executes.

## The two ratification gates (the STOP, mechanized)

1. **Servings.** The owner sets `TIER3_ARM_A`, `TIER3_ARM_B`, `TIER3_ARM_C_1`,
   `TIER3_ARM_C_2` and `TIER3_ARM_D` in `.env` (`TIER3_ARM_B` = `TIER3_ARM_A`).
2. **Spend.** The owner authorizes the total spend: **$90.00 across the 375 planned
   question-runs** (75 units per arm at $0.10/$0.20/$0.20/$0.20/$0.50). This is an
   authorization ceiling, not a predicted cost. **It is not approved by anything in this
   repository, and it must not be assumed to be approved.**

The runner mechanizes the stop. Before any network call it resolves every arm's serving
(arm E's per tier), prints the map with its **fingerprint** (the first 12 hex of the
sha256 of the map's canonical JSON), and refuses to start unless the environment shows
both gates cleared: `TIER3_SERVINGS_RATIFIED` set to that exact fingerprint,
`TIER3_ARM_B` equal to `TIER3_ARM_A`, and `TIER3_SPEND_AUTHORIZED` (or
`TIER3_PILOT_AUTHORIZED` for the pilot) set to at least the ratified ceiling — each
missing gate named in the refusal. The pilot has its own authorization: **50 units**
(arms A and D, one repetition each, seed 20261004) at a **$7.50** ceiling.

## The preflight (free, before the first unit)

The runner runs five cases against the provider catalogue (a free public GET), and a
refusal stops the experiment before any paid call:

1. **The worst case of each arm A–D sequence** against its per-unit ceiling, at the
   guard's own formula: (prompt bytes + the 512-byte chat-template allowance) × the
   prompt rate + max_tokens × the completion rate + the entry's flat per-request
   charge, added once per call, at the registered max_tokens, the
   largest prompt the call can carry, arm B's largest tool result included.
2. **Arm B's serving lists tool support.**
3. **Arm B's largest prompt fits the serving's context window**, bounded in bytes (a
   byte-level tokenizer never emits more tokens than bytes).
4. **Every serving — arm E's tiers included — is in the catalogue and priced on both
   sides of the call.** A serving absent from the catalogue is refused outright. A
   catalogue entry makes the guard blind only for a charge the worst-case bound
   cannot cover (D49: an unknown price is not free): a component priced above the
   rate its side is charged at, or one the bound does not know. The bound covers
   what its own rates already charge — the cache components at or below the prompt
   rate, reasoning at or below the completion rate — adds a flat per-request charge
   once per call, and ignores the image and audio components a text-only call never
   carries. A variant suffix (`:exacto` among them) resolves to its base model's
   catalogue entry: the per-model endpoint confirms the variant is served but
   carries no pricing of its own, so the base entry's published price is the known
   price the bound reads.
5. **The registered max_tokens against the pinned endpoint's max_completion_tokens**
   (the owner's addition): an arm A–D call whose registered max_tokens exceeds the
   endpoint's cap is refused — the client does not clamp, so the call would fail at the
   provider mid-unit, after the spend was committed. Arm E's tiers are reported, not
   refused: arm E runs under the spend guard as it ships, and its tiers' standing
   output caps are printed beside the endpoints' caps.

Catalogue blindness (a missing `supported_parameters`, `context_length`,
`max_completion_tokens`, or pricing) is a **report, not a guess** — named, and the
experiment may proceed with the blindness on the record. The free `worst-case` command
prints arm E's per-tier table: each tier's standing output cap, the guard's worst case
at the catalogue's rates, the per-request charge it adds, the entry that priced a
variant serving, and the spend above which the guard would refuse the call.

## Failure treatment (registered, not improvised)

Refusal, deadline, tool failure, incomplete runs and outstanding liability are all *counted,
not dropped*: the success measures are fractions of the 75 **planned** units per arm, so a
refused, timed-out or incomplete unit is 0 delivered correctness with its cost and latency
recorded. A lookup the closed-world fetch answers "not available" is a recorded reading,
not a failure and not a refusal. Calls that failed after dispatch (the runner's
`unreconciled_liability`, Ruling D45) are included in their unit's cost and in the
total-cost measure. An interruption charges the unit in flight its full ceiling as
unreconciled liability and re-runs it; the resume guard refuses a results file whose
recorded manifest version or order digest differs from this run's.

## The five success measures

1. **Delivered correctness per arm** — the count of the 75 planned units per arm whose
   delivered answer the frozen scorer scores PASS, as a fraction of 75. Two hand
   readings are the primary measure (Ruling D50 (1)): the runner exports a reading sheet
   (every scorer FAIL plus a seeded sample of PASSes, no arm label, blind to the
   treatment) and reports the measures computed scorer-only and again with the readers'
   verdicts where they read, side by side.
2. **Per-question repeat outcomes** — for each question and arm, the 0/3–3/3 distribution
   of its three repetitions. Repeatability is itself a measurement.
3. **Paired wins/losses against A** — per question, each non-A arm's correct-repetition
   count (0–3) against A's: wins/losses/ties across the 25 questions.
4. **Comparison with D** — the same paired measure against the strong reference.
5. **Total cost and latency including failures** — the sum across all 375 units, failures
   and unreconciled liability included; no measure excludes the units that failed.

## The runner

`evals/tier3/runner.py`, on the command line:

```
.venv/bin/python3 -m evals.tier3.runner preflight [--pilot]   # gates + preflight, free
.venv/bin/python3 -m evals.tier3.runner worst-case            # arm-E table, free
.venv/bin/python3 -m evals.tier3.runner dry-run               # mocked runs, free
.venv/bin/python3 -m evals.tier3.runner run [--results-file PATH]      # paid
.venv/bin/python3 -m evals.tier3.runner pilot [--results-file PATH]    # paid
.venv/bin/python3 -m evals.tier3.runner reading-sheet RESULTS_FILE     # free
```

The dry run proves the whole machinery at zero cost: the same runner, a mocked lineup
(placeholder servings by fingerprint), a scripted model whose correct answers are the
recorded real answers where the tier-2 regression record holds them. Its record, under
manifest `tier3-2` (fingerprint `444cba832c69`, order sha256
`6407a7dba3f82a610cc0f30afd6d4f5ee3129fc5f6885492f8064e7d7b76e7c9`):

- **The main run, killed for the resume exhibit:** 40 units, all delivered, then the
  process is killed with the next unit (`('Q20', 2, 'D')`) left in flight.
- **The main run, resumed to the end:** 375 units, **$8.8488 spent — $0.2000 of it the
  in-flight unit's liability charge** — $0.0017 unreconciled liability; statuses 1
  deadline, 371 delivered, 2 incomplete, 1 refusal; delivered correctness A 73/75,
  B 74/75, C 74/75, D 72/75, E 72/75; census: 73 check:concurred, 1 check:objected,
  1 check:unavailable, 1 deadline, 1 tool_failure, 1 delivery:approved-not-shipped,
  1 delivery:no-answer, 73 delivery:shipped, 2 incomplete, 1 refusal.
- **The pilot, resumed to the end:** 50 units, $0.0162 spent, 48 delivered, 1
  incomplete, 1 refusal; A 23/25, D 23/25.
- **The reading sheet:** 55 entries (every FAIL plus the seeded PASS sample, 10 per
  arm); the merge demonstrates both paths — 54 agreements, 1 disagreement, 0 unread.

The mocked dry run writes its results under `evals/results/` (git-ignored scratch);
`reading-sheet` re-exports the sheet from any results file.
