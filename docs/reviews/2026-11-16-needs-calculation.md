# The needs_calculation switch, and the recompute step on calculations (2026-11-16)

Preregistered in `docs/preregistration-20261116-needs-calculation.md` (#281), pushed before the
spend. The owner granted '$0.26'; '$0.14' was spent.

## The point

- **The switch sorts cleanly.** Asked alone on 69 questions of a known kind: no on all 49
  lookups, yes on all 15 calculations.
- **The gate does what the switch says.** End to end on tier 2's 25 questions, the samples ran
  on the 20 it routed yes and on none of the 5 it routed no.
- **All 25 answers are right,** read against the frozen keys. So the run cannot say whether the
  vote catches a wrong calculation: there was none to catch.
- **The vote raised no false flag.** On 2 of the 15 calculations it compared nothing, and on 3
  it reached no majority on one ask.
- **A calculation costs '$0.0038' an answer** with the step running; a lookup, with the step
  skipped, '$0.0085'.
- **One thing for the owner:** every calculation, right and voted on, still carries the
  caution "No lookup ran". See "For a ruling".

## What was run

| | |
|---|---|
| Part A | `docs/probes/needs_calculation_probe.py`: the switch as shipped, once on each of the 44 professional questions and the 25 tier-2 questions. '$0.0003' |
| Part B | `docs/probes/short_workflows_measurement.py`, tier 2, the default workflow as shipped on main at `0d43ad6`, the owner's `.env` as cleaned that day (the recompute tier on the owner's chosen model, pinned to its maker). 25 answers, all completed. '$0.1405' |

Traces, byte-identical: `docs/traces/20261116T-needs-calculation-*` (switch-alone
`9f83078b70c3…`; end to end shard 0 `b35bdd7d5ec2…`, shard 1 `1dc6aa6fecad…`, and each shard's
phase rows).

**Reading.** A blind Sonnet reader graded all 25 answers against `evals/tier2/keys.json`:
25 right. The tier-2 scorer, run as a screen, passed 24 and failed Q9 on one item, "0 section
headings (3 required)"; the executor read Q9 and its four figures and its three parts are all
there and right. The screen's fail is about layout.

## Part A: the switch alone

| Kind, fixed before the run | Questions | Routed yes | Routed no |
|---|---|---|---|
| Lookup (44 professional, 5 tier-2 LOOKUP) | 49 | 0 | **49** |
| Calculation (tier-2 SANITY, DERIVATION, SPECIFICATION) | 15 | **15** | 0 |
| Procedure (tier-2 PROCEDURE), held to no bar | 5 | 5 | 0 |

The lookups scored 0.00 to 0.01 and the calculations 0.97 to 1.00. Three procedures scored 0.99
(they have the reader work out a figure on the way); two scored 0.54 and 0.64, "unsure", which
takes the safe side and runs the samples.

## Part B: end to end

| | Calculations (15) | Procedures (5) | Lookups (5) |
|---|---|---|---|
| Right, by the reading | 15 | 5 | 5 |
| Samples ran | 15 | 5 | 0 |
| Vote flagged | 0 | 0 | not run |
| Vote compared nothing | 2 (Q4, Q19) | 4 | not run |
| Vote reached no majority on one ask | 3 (Q6, Q8, Q14) | 0 | not run |
| Lookup ran | 0 | 0 | 5 |
| Cost an answer | '$0.0038' | '$0.0082' | '$0.0085' |

## The bars

| Bar | Result |
|---|---|
| 1. Yes on at least 14 of 15 calculations | **Met.** 15 |
| 2. No on at least 44 of 49 lookups | **Met.** 49 |
| 3. The samples ran where the switch said yes and nowhere else | **Met.** 20 and 0 |
| 4. No more than 2 right calculation answers flagged | **Met.** 0 |
| 5. At least half the wrong calculation answers flagged | **Not testable.** No answer was wrong |

## The predictions

| Prediction | Result |
|---|---|
| 1. Bar 1 met, 15 of 15 | **Held** |
| 2. Bar 2 met, with 1 to 3 lookups routed yes | **Wrong.** None was |
| 3. At least two procedures routed yes | **Held.** All five |
| 4. Bar 3 met | **Held** |
| 5. At least 13 of 15 calculation answers right | **Held.** 15 |
| 6. Bar 4 met | **Held** |

## What it means

- **The ruling ships as ruled.** The step runs for calculations and is spared on lookups.
- **What the step is worth on calculations is still not shown.** It agreed with 15 right
  answers, on 10 of them fully. Tier 2's problems are too easy for the answer step to get
  wrong, so the vote had nothing to catch. Ruling D53's 5 of 5 on tier 4 remains the evidence
  that it can.
- **The procedures pay for samples that compare nothing.** Four of five. They are a small part
  of a professional's questions and cost about half a cent each time.

## For a ruling

1. **"No lookup ran" beside a calculation.** All 15 calculations carry: "No lookup ran: figures
   and citations in this answer come from the model's memory and were not checked against a
   source." It is true and off the point: nothing needed looking up, and three blind samples
   agreed. The executor's advice: do not say it when the request was judged to need no sources
   and the vote compared the answer and agreed. That changes what the delivery says, so it is
   the owner's.
2. **Nothing else.** The two repairs named in the sampler report (reading "RFC 7540, RFC 8740"
   as the same identifiers, and reading a sample's values under another key) did not come up
   here: every sample was read, 3 of 3 on all 20 units.

## Limits

- 15 calculations, one answer each, all short textbook problems.
- One blind reader and the scorer as a screen; the executor read only the answer the screen
  failed.
- The recompute model was not compared with another.
