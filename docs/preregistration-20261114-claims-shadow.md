# Preregistration: the claim check, first shadow run (2026-11-14)

This is written and committed before the run. A wrong prediction will be reported as wrong. The
owner approved the build and the run on 2026-11-14 ("Go full permission", then "continue, no caution
shown yet full permission").

## Why

The recompute vote compares one value per ask. An open request is one ask, so the figures that can
be wrong sit in prose. In five of the six recorded runs of the inspection-authorization question
(IA) the vote compared nothing, and two of those answers gave a 3-year period where the rule says 2
(`docs/reviews/2026-11-13-golden-decisions.md`).

The owner chose the direction: have the answer's claims stated as typed values the vote can compare.

## What was built, in shadow

A measurement-only workflow, `answer-and-recompute-claims`. It is the default workflow node for
node, with four nodes added after everything the delivery reads:

1. **`claims`:** a model on the triage tier reads the finished answer and lists the figures it
   relies on, each as a name and a value.
2. **`claims_named`:** a free check. It keeps a claim only if its value is in the answer as written
   and its name does not contain the value. At most 12.
3. **`claims_recompute`:** three blind samples on the recompute tier. Each is shown the request, the
   grounding and the claims' names. None is shown a value or the answer.
4. **`claims_vote`:** the existing free vote, claim by claim.

Shadow means: recorded only. The answer's own call and prompt are unchanged, the delivery reads none
of the four, no caution is shown, and nothing blocks, routes or revises on them. Making any of it
visible or live is a later ruling of the owner's, on evidence.

One thing differs from the vote on asks: the samples learn which claims the answer makes, though not
their values. The owner was told and approved.

## What is run

- Golden IA and Q6, three repeats each, so 6 units.
- `MEASURE_SET=golden`, `MEASURE_WORKFLOWS=answer-and-recompute-claims`.
- **Runner:** `docs/probes/short_workflows_measurement.py`, unchanged. 2 shards, each stopping at
  '$0.10'. Each unit on its own empty knowledge store.
- **Code:** the branch `feat/20261114-claims-shadow` at the commit that adds this file. The owner's
  `.env` of today.
- **Cost:** recorded IA units averaged '$0.019' and Q6 '$0.009'. The four nodes add one small call
  and three samples, so about '$0.15' expected. The caps stop it under '$0.40'.
- **Budget:** inside the owner's '$7' of 2026-11-13. About '$1.82' of it is spent.

## How it is read

- One reader, the architect, reads every answer against `evals/golden/keys.json`, every listed
  claim against the answer, and every sample value against the rule. D50 asks for two readers;
  this is a stated departure.
- For each kept claim the reading says: is the answer's value right, and did the vote flag it. A
  flag on a right value is a false flag. A wrong value not flagged is a miss.
- Text claims are compared as identifiers, with no `same_meaning` behind them yet, so their flags
  are counted apart from the flags on numbers.

## What it must show to be worth keeping

1. **It compares something.** In each IA unit the claim vote compares at least two numeric claims.
   The vote on asks compared nothing in 5 of 6 recorded IA runs.
2. **It sees the two periods.** In each IA unit, the claims include how long the mechanic
   certificate must be in effect (3 years) and, where the answer states it, the actively-engaged
   period (2 years).
3. **Few false flags on numbers.** No more than 1 in 5 numeric claims with a right value is flagged.
4. **A wrong number is flagged.** If any answer states a wrong figure as a kept claim, the vote
   flags it. If no answer is wrong, this is not tested, and the report says so.
5. **The delivery is unchanged.** No delivery carries a caution or a field from the claim check.

## Predictions

1. Every IA unit lists at least 4 claims and keeps at least 3.
2. The samples agree with each other on the 3 years and the 2 years in every IA unit.
3. At least one text claim is flagged for wording only.
4. Q6 gives few claims (0 to 3 per unit): its answer is a logic expression, not figures.
5. The four nodes add under '$0.01' a unit.
