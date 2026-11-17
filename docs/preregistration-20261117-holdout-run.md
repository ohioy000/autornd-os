# Preregistration: the hold-out run (2026-11-17)

Pushed before the spend. The owner's word of 2026-11-17: "Sign all 42 and approve '$2'", in answer to the message that named a limit of '$2' and an expected '$1.30'.

## Why

Every figure so far, the acceptance run's 259 of 264 included, was measured on questions the
harness was shaped against. A harness shaped against 44 questions can score well on them and
badly on the 45th. This run asks the question the earlier ones could not: on questions written
after the harness was fixed, by authors who never saw its answers, in fields the other sets do
not touch, how often is it right, and does the delivery still tell the truth about its own
answers?

## What is run

The hold-out set, `evals/professional/holdout-questions.json`, version `professional-holdout-1`:
42 questions in three groups, written by three agents that had not seen the harness's answers or
its code, then checked one by one against the live pages by two other agents, and signed by the
owner on 2026-11-17. The groups: EU and international law and standards; software, security and
internet standards; physical engineering, units, datasheets and national rules.

Through the default workflow (`answer-and-recompute`) as shipped on main at the commit that
carries this file, with the owner's `.env` as it stands (the provider key reaches the process as
environment variables, never printed). No setting is changed for the run.
**Three answers to each question: 126 answers.** Run by
`docs/probes/short_workflows_measurement.py` with `MEASURE_SET=professional-holdout` and
`MEASURE_WORKFLOWS=answer-and-recompute`, three processes started together. The run's order is
the third repeat last, so a stop reached early drops the third answers first. It runs from a
clone of main, not from the owner's working tree, and writes outside any git tree.

## Money and stops

- Expected: about '$1.30' at '$0.0088' to '$0.011' an answer.
- Each process stops starting answers once its own spend reaches '$0.60'. '$1.80' in all. A
  process can pass its stop by the answer it is in, about '$0.02'. Worst case about '$1.90',
  inside the '$2' stated to the owner.
- Answers not made because a stop was reached are counted as not made and are not rerun here.
- If the network drops, answers blocked at no cost are made again inside the same stops.

## How it is read

- Every answer is read against the signed keys by a blind reader and by the executor (D50: two
  readers; the scorer is a screen and is not the result). **The rule, as the earlier runs used it:
  an answer is right when every key item is right.** An item that says "None" or "the document
  states no such figure" is right only if the answer says so. A reader marks `right` or `wrong`.
  A wrong figure beside a right one makes the answer wrong. Where the two readers differ, the
  answer is shown to both again with the keys, and the difference is reported.
- Cautions and confirmations are read off each unit's record as in the acceptance run
  (`docs/probes/acceptance_run_analysis.py`, which rebuilds them and stops if the rebuild does not
  match the shipped delivery).
- Two cuts are reported. **All questions.** And **questions the harness's own fetch can read**:
  those whose cited passages `verify_keys.py` finds on the live page with the harness's own
  fetch and quote check, 26 of the 42, listed here before the run: X1, X2, X4, X5, X6, X7, X8, X9, X10, X11, X13, X14, X15, X16, X21, X22, X23, X24, X25, X27, X28, X34, X36, X37, X39, X42. A question whose source the harness cannot
  fetch is a real question, and it stays in the first cut.

## The bars

1. **Right on questions nobody tuned for:** at least 100 of 126 answers right (79 percent).
2. **No confirmation beside a wrong figure.**
3. **Right answers come clean:** at least half of the right answers carry no caution.
4. **Wrong answers are marked:** at least half of the wrong answers carry a caution that points at
   the wrong part.
5. **Cost:** an answer costs no more than '$0.015' on average; the run stays within '$2'.
6. **The retry holds:** at most 2 of 126 answers end blocked on an upstream 429 after five
   attempts. (Before the retry went from three to five attempts, 6 of 270 did.)
7. **No group collapses:** each of the three groups is right in at least 70 percent of its answers.

- Bar 1 or 7 missed: reported as it reads. The release notes carry the run's figure and say it
  is the one that counts for new questions. No change follows without a ruling.
- Bar 2 missed: the release is held and the case goes to the owner.
- Bars 3 and 4 missed: reported; the known limits grow by what the run shows.

## Predictions

1. Between 105 and 118 of 126 are right, which is 83 to 94 percent; lower than the in-sample
   98 percent. The first predicted losses: datasheet and table questions the fetch reads badly,
   and the traps, where the right answer is "the document states no such figure".
2. Bar 2 holds: 0 confirmations beside a wrong figure.
3. Bar 4 is the one most likely to miss again, as in the acceptance run.
4. An answer costs between '$0.009' and '$0.013'.
5. 0 or 1 answers end blocked on a 429.
6. The traps and the PDF-table questions are the least often right.

## Limits, stated beforehand

- Three answers a question; the answers to one question are not independent draws.
- 42 questions is a small sample. A figure of 90 percent has a wide margin either side of it.
- The questions were written and checked by language models, then signed by the owner. A
  question one of them got wrong in a way the owner did not see would count against the harness.
  Two readers read every answer, and a disagreement with a key is looked at first.
- Two readers, one of them the executor who ran it. A second human reading is the owner's to ask for.
- Live sites change; a rerun on another day can differ.
