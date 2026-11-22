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

## Amendment 1 — after the first run, before any further spend (2026-11-21)

**What run 1 read.** `legal` × `gen_contract_threshold` (n = 1) completed for '$0.0402' in 24 calls. The answer call (the
`engineering` tier) was served by the pinned id via Z.AI and by nothing else (S1 holds for this run); its cost, '$0.0301'
for 11,293 prompt and 20,716 completion tokens, is the catalogue's no-cache figure to the cent (S6 holds); no schema
rejection and no provider failure (S4 holds); the header records the profile and the pin and shows the pin in
`models.engineering`. It stopped the sweep on the stop rule written above, because the unit carries three
`spend_guard_blind` entries, all of the **`decision` tier**: the owner's global `MODEL_DECISION` is not listed in the
public catalogue (no id of that name among 476 models, Perplexity's listed ids being the sonar family), so the guard cannot
rate it. The three decision calls cost '$0.0002' in all, the unit is billed from what the provider reports, and every run
of this workflow makes those calls. **S5 as written ("no unit carries a `spend_guard_blind` entry") is falsified, at n = 1,
by a tier that is not the pin's.** It is a finding that waits on the owner (G-3): the decision model is unrated.

**The owner's ruling (2026-11-21, asked in conversation after run 1): amend and run the other five.**

**The amended stop rule.** A blind entry on a tier other than the pinned one is recorded and reported in the ruling
record, not a stop. Everything else stands: a failing preflight, any HTTP 404, a blind entry **on the `engineering`
tier** (the pinned call), a cap reached, a unit that ends in anything but a terminal, and the pinned id appearing in any
`general` run. **S5 is restated** as: no blind entry on the `engineering` tier, no 404 or refused call, and each unit
`status: completed`, in all six; the original wording is scored falsified and the restatement is scored besides it. The
caps (`--max-spend 0.40`, `--max-spend-sweep 0.40`), the six runs, the pin, the process-environment order and every other
prediction are unchanged. Spent so far: '$0.0402' of the '$3.00'; the remaining five are expected to cost about '$0.25'.
The remaining runs, in this order: `general` × `gen_contract_threshold` (the pair of run 1, the leak check), then
`legal` and `general` × the two new requests.

## Amendment 2 — after the six runs, before any further spend (2026-11-21)

**What the six runs read** (n = 1 per cell; spent '$0.1455' of the '$3.00'). All six completed. Under `legal` the answer
call was served by the pinned id via Z.AI in all three runs and by nothing else; its cost is the catalogue's no-cache
figure (the billed cost is 1.000, 1.000 and 0.997 of it). Under `general` the pinned id appears in none of the three.
The paired headers differ in `models.engineering` only. **Two things the predictions did not foresee:**

1. **Under `general` the answer call is not on the engineering tier.** All three `general` runs have no `engineering`
   call and one `architecture` call, which is the answer. `general` declares no domains, `lead_for_domain` is documented
   to return the profile's system-view role for a domain nobody mapped, and that role (the planner) is on the
   architecture tier. So S2's second half, "served by the global engineering model", is **not observable** in a `general`
   run, and the leak part of S2 (the pinned id is absent) holds only trivially: the pin's tier was not called there.
   This is how `general` was built and is not changed here.
2. **The pinned model's typed verdict was rejected once.** In `legal` × `pin_legal_termination_clause` the harness
   rejected one engineering reply against the verdict's schema (`rejections_by_tier: {engineering: 1}`, served by Z.AI)
   and the retry was accepted; the other two `legal` runs had none. **S4 is falsified as written, at n = 3** (predicted
   none); `general` had none, as predicted.

**The added arm.** The check the owner needs is whether the pin leaks into the tier it overrides on a profile that
**does** call that tier, the engineering profile (every other profile is unaffected by construction, and the owner's own
profile is the one to be sure of). One run: `AUTORND_PROFILE=engineering`, the same pin in the environment, the same
order, the new request `pin_engineering_leak_check` (a firmware question, so triage names the firmware domain and the
lead it maps to is on the engineering tier). Same caps (`--max-spend 0.40 --max-spend-sweep 0.40`), same amended stop
rules, one run, n = 1, no repeat.

- **S9 — the engineering profile is not touched by the legal pin, n = 1.** `models_by_function` for the `engineering`
  tier is exactly one id, the global engineering model the header's `models.engineering` names, and the pinned id appears
  nowhere in the record. *The pinned id anywhere falsifies it and is the worst result this smoke can return.* If triage
  does not name a domain led by an engineering-tier role, the engineering tier is not called, the check was not
  exercised, and that is reported as read; the run is not repeated.

Everything else is unchanged. The spend of this run is expected to be a few cents.
