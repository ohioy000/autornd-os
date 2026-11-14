# Preregistration: an alive check of the two new live switches (2026-11-14)

This is written and committed before the run. A wrong prediction will be reported as wrong. The
owner asked for the run on 2026-11-14 ("Run alive check of the two new switches").

## Why

`same_meaning` and `quote_answers` were made live as labels in #249. They are tested offline only.
This run checks that each one acts in a real delivery, the way #249 says:

- **`same_meaning`:** a confident yes lists the ask in the vote's `cleared`. The vote is `flagged`
  only if a disagreement is left. What the vote found stays in `flagged_by_vote` and
  `disagreements`. A caution says the ask was worded differently.
- **`quote_answers`:** a confident no gives that quote `answers_question: false`, and a caution
  counts such quotes.
- **Both:** labels only. The stored phase rows are unchanged, and the run ends as it would have.

It is not a measurement of how often either switch is right. It is a check that the wiring works
live.

## What is run

- Tier-2 Q7 (noise table) and Q12 (water limits), four repeats each, so 8 units.
  - Q7 because, in the lookup run of 2026-11-13, 3 of its 4 units had a confident `quote_answers`
    no and 2 had a vote flag `same_meaning` said yes to.
  - Q12 because all 4 of its units had a vote flag `same_meaning` said yes to.
- `MEASURE_SET=tier2`, `MEASURE_WORKFLOWS=answer-and-recompute`.
- **Runner:** `docs/probes/short_workflows_measurement.py`, unchanged. Each unit on its own empty
  knowledge store. 4 shards, each stopping at '$0.06'. Each shard holds 2 units.
- **Code:** main at `4055983`, with the owner's `.env` of today. Preflight 34 ok, 0 failing.
- **Cost, from the recorded units:** Q7 averaged '$0.017' and Q12 '$0.024', so about '$0.17'
  expected. The caps stop it near '$0.30', and under '$0.50' at worst.
- **Budget:** inside the owner's '$7' of 2026-11-13. About '$1.65' of it is spent.

## How it is read

- The runner's line per unit records what the API returns (`_detail`): the vote with `cleared`,
  and the cautions. The per-quote label is read by building the same detail again from each
  shard's database, with no call.
- Each shard's database is exported a row per line, as in the earlier runs, so the stored rows can
  be compared with the delivery.
- **One reader, the architect,** reads each answer against the key, each cleared pair, and each
  labelled quote against its question. D50 asks for two readers; this is a stated departure.

## What counts as alive

1. **`same_meaning`.** For every unit: the asks in `cleared` are exactly the asks whose
   `same_meaning` record is a confident yes (0.80 or more). Where all disagreements are cleared,
   `flagged` is false and `flagged_by_vote` is true, and no caution says the vote disagrees. The
   stored `recompute_vote` row still says what the vote found.
2. **`quote_answers`.** For every unit: the quotes with `answers_question: false` are exactly the
   found quotes whose `quote_answers` record is a confident no (0.20 or less), and the caution
   gives that count. An unsure answer labels nothing.
3. **Labels only.** Every unit ends as it would have without the labels: no unit blocked, routed
   or revised on either switch.
4. If a switch is never asked a question that ends confident, it was not seen alive. The report
   says so; it does not count as a pass.

## Predictions

1. At least one Q7 unit labels a quote as not answering.
2. At least three Q12 units clear a vote flag, and their vote ends `flagged: false`.
3. Every label matches its record, as in 1 and 2 above. No mismatch.
4. All 8 answers are right: 8, 4 and 2 hours for Q7; 0.010, 4.0 and 10 mg/L for Q12.
5. The decision calls cost under '$0.001' in all.
