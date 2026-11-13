# Preregistration — the golden questions, to settle four choices (2026-11-13)

Written and committed before the run. A wrong prediction is reported as wrong.

## Why

The tier-2 run (`docs/reviews/2026-11-13-short-workflows-measurement.md`) found no wrong answer.
That left four of the owner's choices with nothing to decide on: the vote's text comparisons, a
step for `quote_answers`, a new scorer version, and a harder set. The owner said on 2026-11-13: "do
5 questions from golden set then do 5 more if you need more data". This run does that, and says
first what result settles each choice.

## What is run

- **Batch 1: five golden questions** from `evals/golden/keys.json`, version 1.
  - **Q2, Q4, Q5.** These are tier-2's Q2, Q4 and Q5 word for word, so the two scorers can be set
    side by side on the same answers.
  - **Q6**, the owner's logic-circuit question.
  - **IA**, the owner's inspection-authorization question, the side test. Q6 and IA have not been
    run since the harness changed.
- **Workflow:** `answer-and-recompute` only. The vote, `ask_covered` and `quote_answers` run only
  there.
- **Repeats and units:** three repeats, so 15 units in batch 1.
- **Batch 2, only if batch 1's reading finds fewer than three wrong answers:** five tier-4
  questions whose trap the catalogue does not state. They are T4-15, T4-41, T4-42, T4-43 and T4-58.
  Each is sent with its own catalogue pages after the registered separator, as tier-4's D-pages arm
  sends them. The same workflow and three repeats give 15 more units.
- **Runner:** `docs/probes/short_workflows_measurement.py` with `MEASURE_SET=golden` or `tier4`
  and `MEASURE_WORKFLOWS=answer-and-recompute`. There are five shards, and each unit runs on its
  own empty knowledge store.
- **Budget:** inside the owner's '$7' of 2026-11-13, of which '$1.05' is spent. Each shard stops
  starting units at '$0.30', so a batch is bounded at about '$1.50' plus one unit per shard.
- **Code:** main at `4c0f80e`, plus the runner's two settings.
- **Settings:** the owner's `.env` of this date.

## How it is read

- **Screens, never the result (D50).** The golden scorer screens every golden answer. Tier-2's
  scorer also screens Q2, Q4 and Q5. Batch 2 has no screen.
- **The reading.** One reader, the architect, reads every delivered answer in full, not only those
  a screen fails. Golden answers are read against the golden keys. Tier-4 answers are read against
  each question's `reference_design` and `worked_solution`, checked by its batch's `verify.py`.
  This departs from D50, which asks for two readers.
- **The vote, the switches, the cost and the time** are read off each unit's record.
- **The same-meaning replay.** After the runs, each text-against-text disagreement the vote records
  is put to the decision model, with the samples' own words. That covers tier-2's ten and these
  runs'. It is asked one yes/no question: *"Do the two values state the same thing for this ask?"*

  > **yes:** "They state the same fact, figure or verdict, even in other words or with more
  > detail."
  > **no:** "They state a different fact, figure or verdict, or one contradicts the other."

  The thresholds are 0.80 and 0.20, the same as every switch. The same question is also put to
  these six contrary pairs, written now from the flagged asks. In each, the second value means
  something different:

  1. "same direction as the driver" / "opposite direction to the driver"
  2. "not the same direction as the driver" / "same direction"
  3. "XOR: Alarm = A ⊕ B = A'B + AB'" / "XNOR"
  4. "as Nitrogen (as N)" / "as nitrate ion (as NO3)"
  5. "at least annually (no less than once every 12 months)" / "at least every two years"
  6. "8 h at 90 dBA; 4 h at 95 dBA; 2 h at 100 dBA" / "8; 2; 1"

  The replay is paid, at under a cent.

## What settles each choice

1. **The vote's text comparisons.** The same-meaning question, option (c), is recommended only if
   both of these hold:
   - It answers yes on at least nine in ten of the disagreements the reading finds the same.
   - It never answers yes where the meanings differ: every contrary pair, and every real
     disagreement the reading finds different.

   One yes on a differing pair rules (c) out, because it would hide the very catch the vote exists
   for. Then the choice is between the other two:
   - **(b), compare numbers only**, if no text flag in either run caught a wrong answer.
   - **(a), leave it**, if a text flag did catch one.
2. **A step for `quote_answers`.** A step that marks a quote "found, but not answering" is
   recommended only if both of these hold:
   - Every confident no, here and in the tier-2 run, is right on the reading.
   - There are at least 15 confident no's in all; the tier-2 run gave 9.

   With fewer than 15, the report says the data is still too thin. With one wrong no, the step is
   not recommended.
3. **A scorer version.** Where the reading finds an answer right, the report counts how often each
   scorer fails it. A new tier-2 scorer version is recommended if the tier-2 scorer again fails right
   answers on form and the golden scorer holds them.
4. **A harder set.** Recommended if batch 1's reading finds fewer than three wrong answers in 15.
   Batch 2 is then the first data from it.

## Predictions

1. **Q6** is right in at least two of its three runs. The key is the forward and aft door signals
   into an OR gate, then the OR output and brake-engaged into an AND gate, in positive logic.
2. **IA** is wrong on at least one core item in at least one of its three runs. The golden record
   shows the pipeline's IA draft carrying fabricated quotations.
3. **`needs_sources`** answers yes on Q2 and IA (6 of 6) and no on Q4, Q5 and Q6 (9 of 9).
4. **The vote** flags at least one Q6 or IA answer the reading finds right, since both are text.
5. **Batch 2**, if it runs, has at least three wrong answers in 15. Among them, the vote flags at
   least half of the wrong ones and at most one of the right ones.
6. **Cost:** batch 1 at most '$0.40'; batch 2 at most '$1.00'.

## What this run cannot show

- **Small numbers.** Five questions, three repeats each, so 15 units a batch.
- **One reader.**
- **The tier-4 pages are supplied.** A real request would have to retrieve them.
