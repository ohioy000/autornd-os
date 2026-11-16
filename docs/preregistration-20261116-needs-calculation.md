# Preregistration: how the needs_calculation switch sorts, and the recompute step on calculations (2026-11-16)

Pushed before the spend. The owner granted '$0.26' on 2026-11-16 ("26 cents granted").

## Why

The owner ruled on 2026-11-16 that the recompute step is off by default and kept for
calculations, with the owner's own choice of recompute model (#278). The switch that decides,
`needs_calculation`, went live on that ruling. How it sorts has been seen on two requests and
never measured. The recompute step with the new model has not been measured on calculations at
all.

## What is run

**Part A, the switch alone.** `docs/probes/needs_calculation_probe.py`: each of 69 questions is
put to the switch as shipped, once, on the decision tier. No answer is made.

| Set | Questions | Kind, fixed here before the run |
|---|---|---|
| The three professional sets | 44 | lookup: the answer is on a page |
| Tier 2, shape LOOKUP | 5 | lookup |
| Tier 2, shapes SANITY, DERIVATION, SPECIFICATION | 15 | calculation |
| Tier 2, shape PROCEDURE | 5 | neither: an ordered procedure. Reported, held to no bar |

**Part B, end to end.** `docs/probes/short_workflows_measurement.py`, `MEASURE_SET=tier2`,
`MEASURE_WORKFLOWS=answer-and-recompute`: the 25 tier-2 questions, one answer each, through the
default workflow as shipped on main at the commit that carries this file, with the owner's
`.env` as cleaned on 2026-11-16. Two shards.

## Money and stops

- Part A: about '$0.01'. Stop at '$0.02'.
- Part B: about '$0.15' at '$0.006' an answer. Each shard stops starting units at '$0.11'.
- All stops together: '$0.24', inside the '$0.26' granted. An answer in flight when a shard
  stops may add about a cent.

## How it is read

- Part A is read off the record: the route for each question.
- Part B's answers are read against the frozen tier-2 keys (`evals/tier2/keys.json`), by a
  blind Sonnet reader and by the executor. The tier-2 scorer is run as a screen and is not the
  result (D50). The vote and the switch are read off each unit's record.

## The bars

1. **The switch keeps the step for calculations:** it routes yes on at least 14 of the 15
   calculation questions.
2. **The switch spares lookups:** it routes no on at least 44 of the 49 lookup questions.
3. **The gate does what the switch says:** in part B the samples ran on every unit the switch
   routed yes and on none it routed no.
4. **The vote does not cry wolf on calculations:** it flags no more than 2 of the right
   answers among the 15.
5. **The vote catches something:** of the calculation answers read as wrong, it flags at least
   half. With no wrong answer, this bar is not testable and is said so.

- Bar 1 missed: the ruling's "kept for calculations" is not what ships; the switch's wording
  or thresholds go back to the owner.
- Bar 2 missed: lookups still pay for samples; the same.
- Bar 3 missed: a defect; repaired as found.
- Bars 4 and 5 are reported to the owner as the step's record on calculations. No change
  follows without a ruling.

## Predictions

1. Bar 1 is met: 15 of 15.
2. Bar 2 is met, with 1 to 3 lookups routed yes, among them a tier-2 LOOKUP question whose
   answer needs a unit converted.
3. The five PROCEDURE questions split: at least two are routed yes.
4. Bar 3 is met.
5. At least 13 of the 15 calculation answers are right, so bar 5 rests on two answers or fewer.
6. Bar 4 is met.

## Limits, stated beforehand

- 15 calculations, one answer each. A difference of one or two is noise.
- One request each in part A. The decision model's probability is taken as given.
- Tier 2's calculations are short textbook problems. A long engineering calculation is not in
  this set.
- The recompute model is not compared with another. This run says what the step does as
  shipped.
