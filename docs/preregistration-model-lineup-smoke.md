# Pre-registration — the model line-up smoke

Committed before any spend, and alone with its two new requests. Expectations only, each with its n.

**Authorisation (the owner, 2026-11-22): "1 dollar ceiling to test the 2 new models and original models in a small question
set that tests every combo tier models".** This document sets the shape below that ceiling: five runs, each capped as
listed, so the hard ceiling is '$0.99'. A cap reached stops the run and is reported as read; nothing is re-run past the
authorisation. The runs start only after the medical triage arm (`docs/preregistration-medical-examples-fix.md`) has
finished, at the owner's word.

## The line-up under test (the owner's, 2026-11-22; ratified in conversation)

| Profile | Answer tier (`engineering`) | Triage tier |
|---|---|---|
| global default, every profile with no pin | the owner's `MODEL_ENGINEERING` | the owner's `MODEL_TRIAGE` |
| `engineering` | `qwen/qwen4-max` on Alibaba | global |
| `legal` | `z-ai/glm-5.3-flashx-legal` on Z.AI (ratified earlier) | `tencent/hy4-flash` on `tencent/fp8`, default thinking |
| `finance` | `google/gemini-4-hydrogen` on `google-vertex/global` | `tencent/hy4-flash` on `tencent/fp8`, default thinking |
| `medical` | `google/gemini-4-hydrogen` on `google-vertex/global` | global (the medical triage pin is not ratified) |

"The 2 new models" are `qwen/qwen4-max` and `google/gemini-4-hydrogen`, never run in this harness. "The original models" are
the global default (the baseline of the `engineering` pair) and the legal model of the first pin smoke. Every one of the
five tier/model combinations above is called once.

## Free checks already made (2026-11-22, before this commit)

| Check | Read |
|---|---|
| Public catalogue GET, no key | `qwen/qwen4-max`: one endpoint (Alibaba), context 1,000,000, max output 131,072, `response_format` and reasoning supported, rated '$1.425' prompt and '$4.275' completion per million. `google/gemini-4-hydrogen`: Vertex and AI Studio endpoints, context 1,048,576, max output 943,718 on Vertex, `response_format`, `structured_outputs`, reasoning, rated '$1.50' and '$7.50' per million |
| `python -m autornd.preflight` under each of the four profiles, all six pins in the process environment, the run-scoped order below | **51 ok, 0 failing** under `finance`; each pin line is `ok` (`alibaba serves qwen/qwen4-max`, `google-vertex/global serves google/gemini-4-hydrogen`, `z-ai serves z-ai/glm-5.3-flashx-legal`, `tencent/fp8 serves tencent/hy4-flash`) and each pin's parameter line accepts `response_format, max_tokens` |

The worst case of one answer call is its prompt plus the answer tier's output ceiling (32,768 tokens) at the model's
rate, about '$0.27' for hydrogen and about '$0.16' for `qwen4-max`, which is why those caps are what they are.

## The runs

Five invocations, one scenario each, `--repeat 1` (n = 1 per cell), `--workflow answer-and-recompute`, from this tree
(`/home/jb/autornd-os-wt-pins` at the commit that holds this document; `.env` is the shared file through its symlink,
never printed), all six pins in the process environment for every run, so the only thing that differs between the paired
runs A and B is the profile's pin.

| Run | Profile | Request | Cap per run | What it exercises |
|---|---|---|---|---|
| A | `engineering` with **no** `engineering:` pin | `pin_engineering_leak_check` | '$0.05' | the original answer model, the baseline of B |
| B | `engineering` | `pin_engineering_leak_check` | '$0.18' | the new `qwen4-max` seat |
| C | `finance` | `pin_finance_loan_interest` (new) | '$0.33' | hydrogen answer seat, `hy4-flash` triage |
| D | `medical` | `pin_medical_dose_per_kg` (new) | '$0.33' | hydrogen answer seat, global triage |
| E | `legal` | `pin_legal_delay_damages` | '$0.10' | the legal seat again, `hy4-flash` triage |

The sum of the caps is '$0.99'.

```
cd /home/jb/autornd-os-wt-pins
export PYTHONPATH=$PWD
export OPENROUTER_PROVIDER_ORDER="triage:crusoe/bf16,engineering:deepinfra/fp8,escalation:google-vertex/global,search:Perplexity,research:wafer/us,ranker:Fireworks,judge:deepinfra/fp8,premium:,recompute:Anthropic"
PINS="engineering:engineering=qwen/qwen4-max@alibaba,finance:engineering=google/gemini-4-hydrogen@google-vertex/global,medical:engineering=google/gemini-4-hydrogen@google-vertex/global,legal:engineering=z-ai/glm-5.3-flashx-legal@z-ai,finance:triage=tencent/hy4-flash@tencent/fp8,legal:triage=tencent/hy4-flash@tencent/fp8"
# run A uses the same list with the engineering:engineering entry left out
```

Each run: `AUTORND_PROFILE=<profile> PROFILE_MODELS=<pins> python -m autornd.evals.cli --scenarios <file> --workflow
answer-and-recompute --repeat 1 --timeout 900 --max-spend <cap> --max-spend-sweep <cap> --results-file
evals/results/lineup-<run>.jsonl`. The order of `OPENROUTER_PROVIDER_ORDER` leaves out the stale `architecture` entry of the
owner's `.env` (as in the first pin smoke): none of the runs calls that tier, `.env` is not edited and `--skip-preflight`
is not used. **Stop rules:** a failing preflight, any HTTP 404, a `spend_guard_blind` entry on a tier a pin names, a cap
reached, a unit that ends in anything but a terminal, or the `qwen4-max` id anywhere in run A. On a stop the work halts
and is reported as read. A `spend_guard_blind` entry on the `decision` tier is recorded, not a stop (the owner's decision
model is unrated; see Amendment 1 of the first pin smoke).

## Predictions

Each is checked against the unit record (`models_by_function`, `providers_by_function`, `calls_by_tier`, `tokens_by_tier`,
`cost_by_tier`, `rejections_by_tier`, `provider_failures`, `spend_guard_blind`) and the file header.

- **L1 — each answer call is served by its seat, n = 5.** For B, C, D, E the `engineering` tier is exactly one id and one
  provider, those in the table; for A it is the global engineering model. *Any other id on that tier falsifies it.*
- **L2 — triage is served as the table says, n = 5.** `hy4-flash` via Tencent for C and E, the global triage model for A,
  B and D. *`hy4-flash` in D falsifies it (an unratified pin leaked).*
- **L3 — the typed verdicts held on the new seats, n = 3.** B, C and D have no `engineering` entry in `rejections_by_tier`
  and an empty `provider_failures`. About three in four for each; the first Z.AI run had one rejection.
- **L4 — nothing blind or refused, n = 5.** No `spend_guard_blind` on a pinned tier, no 404, each unit `status: completed`.
- **L5 — cost, n = 5.** Each run is under its cap; the five together under '$0.99'. Prior: A about '$0.01', B about
  '$0.05', C and D about '$0.10' each, E about '$0.04', so about '$0.30' in all. The `engineering` tier's cost in B, C, D
  is at most its no-cache figure from `tokens_by_tier` at the rates above and at least half of it.
- **L6 — the arithmetic, n = 3.** `figures_present` holds for C (238,203.20 and 38,203.20), D (276 and 92) and E (48,000).
  A smoke of the call, not of the model: one miss is reported and not read as a defect of the pin.
- **L7 — nothing else moved, n = 1 pair.** The headers of A and B differ in `models.engineering` only.

## Not predicted, and not claimed

Answer quality, how any model compares with another on its field, or anything at n > 1. The answers are copied into the
trace for the owner's hand reading. Every cell is a single observation and the record will say so. The costs read here
are the first measured for the two new models, and are the figure the owner's decision on them can use.

## After

Each result file is copied byte-identical into `docs/traces/` and cited by its sha256 in the ruling record, with the
predictions above scored one by one, as read. The pin lines go into the owner's `.env` only after the merge and the
owner's "yes", and only where the code that declares the key is in every checkout that reads that file.
