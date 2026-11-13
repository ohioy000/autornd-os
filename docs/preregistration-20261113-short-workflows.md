# Preregistration — the short workflows on the tier-2 questions (2026-11-13)

Written and committed before the run. A wrong prediction is reported as wrong.

## What is run

- **Questions:** the 25 frozen tier-2 questions (`evals/tier2/questions.json`), five each of SANITY, LOOKUP, DERIVATION, SPECIFICATION and PROCEDURE.
- **Workflows:** `answer-and-recompute` (the default) and `verify-first`.
- **Repeats:** 3. So 150 units.
- **Runner:** `docs/probes/short_workflows_measurement.py`, five shards, each unit on its own empty knowledge store.
- **Budget:** the owner's word of 2026-11-13, '$7'. Each shard stops starting units at '$1.30' of its own spend, so the run is bounded at about '$6.50' plus one unit per shard. A two-question pilot of four units cost '$0.025' before this was written; its only use here is the cost estimate.
- **Code:** main at `09fa344` plus this branch's one repair (switch records written once).
- **Settings:** the owner's `.env` of this date. The `needs_sources` switch is live; the other five are in shadow.

## What is measured, and how

- **Delivered:** the run ended `completed` with an answer.
- **Scorer:** the tier-2 scorer's verdict on the delivered answer. It is a screen, not the result (D50).
- **Reading:** one reader (the architect) reads every delivered answer the scorer fails, against the key. This departs from D50, which asks for two independent readers; the report says so beside every figure that rests on it.
- **The vote, the switches, the cost and the time** are read off each unit's record.

## Predictions

1. **Delivery.** `answer-and-recompute` delivers in at least 95% of its units; `verify-first` in at least 85%.
2. **Scorer pass rate.** Both workflows land between 60% and 85% of their units, and within 10 points of each other.
3. **The vote, on SANITY and DERIVATION units of `answer-and-recompute`.** It is unchecked in at most 25% of them. Among delivered answers the scorer passes, it flags at most 10%. Among those the scorer fails and the reading confirms wrong, it flags at least half.
4. **`needs_sources`.** It routes yes on at least 90% of LOOKUP units and no on at least 90% of SANITY and DERIVATION units.
5. **`ask_covered`.** At least 95% of asks score 0.8 or above, so it separates nothing on this set.
6. **Cost.** The mean unit costs at most '$0.02' on either workflow, and the whole run at most '$3'.

## What would change a decision

- Prediction 3's last clause failing means the vote does not catch wrong figures often enough to be worth its three calls.
- Prediction 4 failing on SANITY or DERIVATION means the live switch buys lookups the request did not need, and it goes back to shadow.
- `verify-first` passing the scorer more than 10 points above `answer-and-recompute` puts the default workflow in question.

## What this run cannot show

- Three repeats of 25 questions is 75 units a workflow. A difference under about 15 points between the workflows is within noise.
- `chunk_helps` and `finding_answers` are not exercised: each unit starts with an empty store.
- The questions have keys; real requests do not. A scorer pass is not a guarantee of a right answer, and a fail is not a wrong one.
