# Preregistration: lookup runs, to settle `quote_answers` and recheck IA and Q6 (2026-11-13)

This is written and committed before the run. A wrong prediction will be reported as wrong. The run
spends money, so it waits for the owner to confirm the amount below.

## Why

Two items are still open after the golden test (`docs/reviews/2026-11-13-golden-decisions.md`):

- **A step for `quote_answers`.** It has 11 confident no's, all of them right. The preregistered bar
  is 15, so it needs at least 4 more, and only lookup runs produce them.
- **The two golden errors.** IA r2 and r3 gave a 3-year period where 65.91(c)(2) says 2 years. Q6
  r2 was cut off and still shipped as done. Since then, a cut-off answer ends the run blocked (PR
  #245), and the vote's text flags go to the decision model in shadow. Neither change has been seen
  on a live run.

## What is run

- **Run A, the lookups:** tier-2's five LOOKUP questions (Q2, Q7, Q12, Q17 and Q22), four repeats,
  so 20 units.
  - `MEASURE_SET=tier2`, `MEASURE_WORKFLOWS=answer-and-recompute`.
  - 5 shards, each stopping at '$0.12'.
- **Run B, the recheck:** golden IA and Q6, three repeats, so 6 units.
  - `MEASURE_SET=golden`, `MEASURE_WORKFLOWS=answer-and-recompute`.
  - 2 shards, each stopping at '$0.10'.
- **Runner:** `docs/probes/short_workflows_measurement.py`, unchanged. Each unit runs on its own
  empty knowledge store.
- **Code:** main at the commit the run starts from, named in the report. The owner's `.env` of the
  run's date.
- **Cost, from the recorded units:**
  - Lookup units averaged '$0.0153' (18 units), IA '$0.019' and Q6 '$0.009'.
  - Expected total about '$0.40'.
  - The caps stop it near '$0.80', plus at most one unit per shard past its cap, so under '$1'.
- **Budget:** inside the owner's '$7' of 2026-11-13. About '$1.23' of it is spent.

## How it is read

- **The reading is the result. The screens are not (D50).**
  - Tier-2's scorer screens run A, under the version on main. `docs/probes/tier2_scorer_v4_rescore.py`
    can score the same answers under both .3 and .4.
  - The golden scorer screens run B.
- **One reader, the architect, reads every answer in full.** This departs from D50, which asks for
  two readers.
- **Every `quote_answers` answer is read against its quote,** paired by address as in the tier-2
  run. A confident no is a probability of 0.20 or less. It is right when the quoted passage does not
  answer the question it was asked.
- **The vote, `same_meaning`, the cut-off check, the cost and the time** are read off each unit's
  record.

## What settles each item

1. **A step for `quote_answers`.** The step would mark a quote "found, but not answering". It is
   recommended only if both of these hold:
   - every confident no, here and in the two earlier runs, is right on the reading;
   - there are at least 15 confident no's in all.

   With fewer than 15, the report says the data is still too thin. With one wrong no, the step is
   not recommended. What the step does is the owner's ruling.
2. **IA.** Each answer is read against `evals/golden/keys.json`. The report counts how many state the
   2-year period, and whether the vote or `same_meaning` flagged any that did not.
3. **The cut-off gate.** Every answer whose text stops mid-sentence must end the run blocked with
   "Answer incomplete: it ends mid-sentence", never done. The report also counts any cut-off answer
   the check missed.
4. **`same_meaning` in shadow.** Each question it is asked is read: does the sample state the same
   thing as the answer?

## Predictions

1. Run A gives at least 4 confident no's, and all of them are right on the reading.
2. Most `quote_answers` no's again come from grounding questions about the request or its source,
   which no passage can answer.
3. At least one IA answer again gives 3 years, and neither the vote nor `same_meaning` flags it.
4. No answer ships cut off as done. If a Q6 answer is cut off, its run ends blocked.
5. `same_meaning` answers yes on every Q7, Q12 and Q17 restatement the vote flags, for under
   '$0.001' in all.
