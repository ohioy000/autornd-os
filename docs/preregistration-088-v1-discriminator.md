# Pre-registration 088 — V1 discriminator (ARCH-20260926-081)

Committed BEFORE the run. Author date precedes the run header.

## Registered prediction (from ARCH-20260926-081, verbatim)

(1) On a local-edit contradiction — a single value violating a stated threshold —
V1 CONVERGES, because seeing the artifact makes the edit actionable.
(2) On a derivation-heavy criterion — three or more distinct numeric derivations,
batch-size arithmetic — V1 STILL BLOCKS, because seeing the prior artifact does
not supply the computation.
(3) The regression rate DROPS: a criterion previously judged green does not go
red, because the model edits rather than regenerates, and the -049 green-to-red
on consistency does not recur.
Consequence: V1 partially fixes the class and does not remove the case for V2 on
derivation-heavy items.

## Advisor prediction record (stated so this is read as a hypothesis, not a result)

The last four predictions of the session were refuted or soft — ARCH-20260922-046
(too pessimistic), ARCH-20260923-049 (too optimistic), ARCH-20260923-071
(refuted), and the technical-set difficulty grades (soft). Treat this prediction
as a hypothesis under test.

## Confound named (081 assumption clause), and how this design removes it

The 081 baseline ($0.80, pool BLOCKED) ran on the OLD roster — GLM-5 engineering,
Inkling-small plan, Flash triage (docs/preregistration-087-final-pair.md). The
CURRENT roster is qwen3-235b engineering (DeepInfra), glm-5.3 plan (DigitalOcean),
gpt-5.4 escalation (OpenAI). The roster changed, so a straight D33-on run compared
to the $0.80 baseline confounds D33 with the roster swap. Per the command's
assumption clause, that comparison is not run.

Instead the discriminator is an un-confounded same-roster, same-item A/B:
- **robotics-manipulator** blocked D33-OFF on the current roster this session
  (BLOCKED, ~$0.068, the kappa=17.99-vs-17 self-consistency contradiction). Re-run
  D33-ON on the same roster, same item — D33 is the ONLY change. This is the clean
  isolation the $0.80 baseline cannot provide.
- **conv_pool_sizing** — the command's kappa-shaped baseline item ("every figure
  that appears in more than one section must agree"; baseline "384-against-400").
  Run D33-ON; report the outcome and failure shape (compared to the recorded pool
  baseline with the confound named, not as an isolated D33 contrast).

Deferred: **conv_backfill_migration** (derivation-heavy, prediction 2). Four
convergence units cannot safely fit the $1.20 envelope without a treatment unit
hitting its per-unit cap and being reported as a budget-cut false block. Deferred
to a follow-up, recommended not run here.

## Discriminator (named, per 081)

Per item: CONVERGED (reaches completed) · BLOCKED DIFFERENTLY (blocked, but a
different/more-specific failure, or the artifact visibly held rather than
re-rolled) · BLOCKED IDENTICALLY (same failure at the same point). Primary read:
robotics D33-off (BLOCKED) vs robotics D33-on.

## Regression watch (required)

Every criterion green in an earlier iteration and not green later is reported (the
-049 failure mode). Absence stated if none.

## Envelope and caps (owner-ratified $1.20)

Two units. `--max-spend 0.55 --max-spend-sweep 1.20` — 2 x $0.55 = $1.10 <= $1.20,
so both units are guaranteed to start. Sized above the per-unit baseline because
convergence may take more iterations before it takes fewer.

## Pins / store

Roster from .env (D33 now active), fallbacks off — all US on-pin. Triage rerouted
triage:DigitalOcean (US) for this run only, to dodge the DeepInfra 429 on
deepseek-v4-flash observed twice this session; triage serving does not affect the
convergence behaviour under test. Knowledge store is empty (no ingestion — the
"collection not found" path), so no cross-contamination; effectively isolated.

## Model NOT changed within the contrast

Within the robotics A/B the model is identical (qwen3-235b engineering) between the
D33-off and D33-on runs. The only change is the prompt shape D33 introduced. This
is V1; the model swap is V2 and is not run here.
