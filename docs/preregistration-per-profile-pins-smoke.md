# Pre-registration — the per-profile pin smoke

Committed before any spend, and alone. Expectations only, each with its n.

**Authorisation (the owner, 2026-11-21): up to $3.00, for one pin smoke test and nothing else.** This document sets the
shape below that ceiling: six runs, each capped at '$0.40', so the hard ceiling is '$2.40'. A cap reached stops the run
and is reported as read; nothing is re-run past the authorisation.

## What this is, and what it is not

A profile can now name its own model for a tier (`PROFILE_MODELS`, empty by default). The first pin proposed is a legal
profile's answer tier on the one legal-named model the catalogue lists. **This smoke is the evidence the owner needs to
ratify that pin (G-2): which model served the answer, whether its typed verdicts held, what it cost. It is not a claim
that the pinned model answers legal requests better.** No prediction below is about quality; the answers are kept for
the owner to read by hand, and no scorer verdict is reported as a result.

## Free checks already made (2026-11-21, before this commit)

| Check | Read |
|---|---|
| Public catalogue GET (no key), the pinned id | listed once in 476 models; one endpoint, Z.AI (`z-ai/fp8`, fp8, status 0); context 1,048,576; max output 131,072; rated per million tokens '$0.37' prompt, '$1.25' completion, '$0.075' cached prompt; supports `response_format`, `structured_outputs`, `reasoning`, `reasoning_effort`, `temperature`, tools. **Rated, so the spend guard is not blind.** |
| `python -m autornd.preflight` with `AUTORND_PROFILE=legal` and the pin in the process environment | `pin legal:engineering  z-ai serves <the id>`, `params legal:engineering via z-ai  z-ai/fp8 accepts response_format, max_tokens`: both ok |
| The same preflight, no pin, the owner's own profile | **2 failing, and they are not this work's:** `pin architecture  gmicloud/bf16 does not serve xiaomi/mimo-v2.6-pro:exacto — with fallbacks disabled this is a 404`, and the matching params line (the model's endpoints now are `deepinfra/fp8, primalabs/fp8, streamlake, xiaomi/fp8`). The owner's `.env` pins that tier to a provider that no longer hosts it. |
| The same preflight with the run-scoped order below (architecture entry left out), under `legal` and under `general`, the pin in the process environment | **36 ok, 0 failing** under each; `params architecture  unpinned` |

**The finding that waits on the owner (G-3).** The architecture entry of `OPENROUTER_PROVIDER_ORDER` in the owner's `.env`
is stale, and the eval CLI refuses any sweep while preflight fails (exit 3). Any run of the architecture tier on that
serving would 404 under hard pins. Re-pinning is a serving pin (G-2) and is not made here; the owner is told, with the
four providers that serve it now.

**What this smoke does about it, for these runs only.** Neither workflow it runs calls the architecture tier. Each
invocation passes `OPENROUTER_PROVIDER_ORDER` in the process environment with that one entry left out (the router
decides that tier, which these runs never call), and every other entry exactly as the owner has it. `.env` is not edited,
`--skip-preflight` is not used, and the effective order is in each results file's header.

## The runs

Six invocations, one scenario each, `--repeat 1` (n = 1 per cell), default workflow named on the command line. The
scenarios: `gen_contract_threshold` (existing; a statutory deadline the writer may not know, so it reaches the lookup)
and two new, committed with this document in `evals/scenarios/pin_smoke/`: `pin_legal_termination_clause` (drafting; no
source, no calculation) and `pin_legal_delay_damages` (a calculation whose payable figure, 48,000 pounds, does not
depend on how the days are counted). Each is run once under `AUTORND_PROFILE=legal` and once under `AUTORND_PROFILE=general`,
with **the same `PROFILE_MODELS` in the environment both times**, so the only thing that differs between the paired runs
is the profile.

```
cd /home/jb/autornd-os-wt-pins        # the tree this document is committed in; .env is the shared file, via symlink, never printed
export PYTHONPATH=$PWD
export OPENROUTER_PROVIDER_ORDER="triage:crusoe/bf16,engineering:deepinfra/fp8,escalation:google-vertex/global,search:Perplexity,research:wafer/us,ranker:Fireworks,judge:deepinfra/fp8,premium:,recompute:Anthropic"
export PROFILE_MODELS="legal:engineering=z-ai/glm-5.3-flashx-legal@z-ai"
for P in legal general; do
  for S in evals/scenarios/generalization/gen_contract_threshold.yaml \
           evals/scenarios/pin_smoke/pin_legal_termination_clause.yaml \
           evals/scenarios/pin_smoke/pin_legal_delay_damages.yaml; do
    AUTORND_PROFILE=$P .venv/bin/python3 -m autornd.evals.cli --scenarios $S \
      --workflow answer-and-recompute --repeat 1 --timeout 900 \
      --max-spend 0.40 --max-spend-sweep 0.40 \
      --results-file evals/results/pin-smoke-$P-$(basename $S .yaml).jsonl
  done
done
```

(`.venv/bin/python3` is the advisor's interpreter at `/home/jb/autornd-os/.venv/bin/python3`.) The free preflight runs at
the start of each invocation and refuses the sweep on any failure. **Stop rules:** a failing preflight, any HTTP 404 on a
call, any `spend_guard_blind` entry, a cap reached, or a unit that ends in anything but a terminal: stop, report as read,
spend no more. The runs are made from a clean tree and no git operation touches it while one runs; results are copied
byte-identical into `docs/traces/` and cited by sha256.

## Predictions

Each is checked against the unit record (`models_by_function`, `providers_by_function`, `calls_by_tier`,
`tokens_by_tier`, `cost_by_tier`, `rejections_by_tier`, `provider_failures`, `spend_guard_blind`) and the file header.

- **S1 — the answer call is served by the pin, n = 3.** In each of the three runs under `legal`, `models_by_function`
  for the `engineering` tier is exactly one id and it is the pinned id (or that id followed by a date or version suffix,
  which is then quoted as read), and `providers_by_function` for that tier is the one Z.AI provider. *One other model, or
  a second model, in any of the three falsifies it.*
- **S2 — it does not leak, n = 3.** In each of the three runs under `general`, with the same pin in the environment,
  the `engineering` tier is served by the global engineering model (the id the header's `models` names), never the pinned
  one. *The pinned id in any `general` run falsifies it, and is the worst result this smoke can return.*
- **S3 — only the engineering tier moved, n = 3 pairs.** The header's `models` differs between the paired runs in the
  `engineering` entry only, and the triage and recompute tiers are served by the same models and providers in both runs of
  a pair.
- **S4 — the typed verdicts held on the pin, n = 3.** `rejections_by_tier` has no `engineering` entry and
  `provider_failures` is empty in each `legal` run (no schema rejection, no length stop, no empty reply on the pinned call).
  Run under `general` the same is predicted, as the baseline the pin is read against.
- **S5 — nothing blind or refused, n = 6.** No unit carries a `spend_guard_blind` entry, no unit's error names a 404 or a
  refused call, and each reaches `status: completed`.
- **S6 — the pinned model's cost is its catalogue rate, n = 3.** For each `legal` run the `engineering` tier's cost is at
  most the no-cache figure from `tokens_by_tier` at the rates above (prompt × '$0.37' + completion × '$1.25', per million),
  and at least half of it (cached prompt tokens are billed at a fifth).
- **S7 — spend, n = 6.** Each run costs under '$0.40' and the six together under '$1.50' (the prior for this workflow is
  a few cents a run without a lookup and up to a few tens of cents with one; this is the loosest of the predictions, and
  the figure is reported whatever it is).
- **S8 — the answer to the calculation is right, n = 2.** `pin_legal_delay_damages` states 48,000 pounds as payable under
  both profiles (the free `figures_present` check). *This is a smoke of the call, not of the model: one miss is reported
  and is not read as a defect of the pin.*

## Not predicted, and not claimed

Answer quality, citations, risk readings, how the pinned model compares with the global one on legal work, or anything
at n > 1. The answers are copied into the trace for the owner's hand reading. Every cell is a single observation and the
record will say so.

## After

Each result file is copied byte-identical into `docs/traces/` and cited by its sha256 in the ruling record
(`docs/reviews/2026-11-21-per-profile-pins-and-tuned-prompts.md`) with the predictions above scored one by one, as read.
The pin line goes into the owner's `.env` only on the owner's "yes" and the merge, and only where the code that declares
the key is already in every checkout that reads that file.
