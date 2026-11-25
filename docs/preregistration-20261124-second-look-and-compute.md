# Preregistration: the second look and the computed figure, on the wrong "not stated" answers (2026-11-24)

Pushed alone, before any spend of this run. No answer of this run exists. The owner said "do all three under limit" on 2026-11-24 with
'$2.15' left on the provider account, which is the figure this run stays under.

## The question

Two repairs, on branch `feat/20261124-second-look` (`bfa09d3`), for the wrong "not stated" answers of the first hold-out asked again:

* **The second look** (X35): an ask whose words are on no page read in full gets one more search for that ask alone; a page that has the
  words ends the proof for it.
* **The computed figure** (X26): when the not-stated channel is offered, the answer is first told that a figure whose parts the pages
  print is computed, with the working, and is not "none stated".

**Do they reduce wrong "not stated" answers without making a right "none stated" answer wrong or a right computed one refuse?**
(The third item of the owner's three, stale pages, was replayed free and not built: the supersession wording is in the passages beside 30
of 104 right answers and none of the 5 wrong, and X14's wrong answer never saw the postponement.)

## What is run

The tree `957bc08`-free: a fresh checkout of `bfa09d3` (main with the two repairs), the owner's `.env` unchanged (reader tier on, no pins),
profile `engineering`, workflow `answer-and-recompute`, `MEASURE_SET=professional-holdout`, **3 answers each, 27 answers**, in two
invocations run together:

* **Targets (5 questions, 15 answers):** X26, X35, X3, X31, X18. X26 the computed figure, X35 the page never fetched, X3 the near-empty
  PDF (read as a block now), X31 the one that blocked on an ask it could not satisfy. X18 is a computed-figure question that was right
  every time (2^39 - 256 bits): a control for the instruction.
* **Controls (4 questions, 12 answers):** X19, X36, X41 (right "the document states none" answers: the repairs must not break them) and
  X40 (a unit conversion that was right every time).

## Money

Stated before the spend: expected **'$0.55'** (27 answers at '$0.016', plus the second look's extra search and reading on the asks it
fires for, about '$0.01' each); invocation caps '$0.50' and '$0.40'; **ceiling '$0.90'**. The account has '$2.15'. Stops: any 404, 402, 403 or
key-limit message; a `spend_guard_blind` entry; a model on the answer seat other than the global answer model; the run past '$0.90'.

## How it is read

As the earlier runs (D50): one blind reader on codes that hide the question's draw and arm, and my reading of every not-right answer and 4
seeded right ones before I look at the cautions or the old labels. Not right is `wrong` or `partly`. The second look is read from the
documents' `request` field (2) in the run's records, and the cost from the run's own accounting.

## Baseline (the same questions in the first hold-out asked again, 2026-11-24, the harness before the repairs)

Corrected before any spend (the paragraph first pushed in 38685b8 was loose; this one is read from the stored records). Targets, three
draws each: X26 right, right, **wrong** (the 4 GiB refused); X35 right, right, **wrong** (the 2018 value refused); X3 **wrong** (no figure,
the 33-character PDF), right, right; X31 right, blocked by the harness's own rule, right; X18 right, right, no answer (a 504, later
answered right in the retry check). That is **3 wrong and 1 harness block of 15**, and one provider failure. Controls: X19, X36 and X40
right in every draw that delivered; X41 right, no answer (a 429), right, and partly once in the retry check (it did not commit that the
datasheet states none).

## Predictions (written before any answer is read)

* **Targets:** at most 1 not-right of the 15 answers (baseline 3); X35's second look fires in at least 2 of its 3 draws.
* **Controls:** at most 1 not-right of the 12; X19, X36 and X41 stay "none stated" where they were, and the second look fires on them and finds nothing.
* **X3:** unchanged or blocked (the near-empty page now proves nothing, so a "not stated" claim has no proof); it is not expected to become right.
* **Cost:** '$0.017' to '$0.025' an answer.

## What decides

* **For merging both:** not-right answers among the 12 controls no more than 1, **and** among the 15 targets fewer than the baseline's 3.
* **Hold the second look** if any control that was a right "none stated" becomes wrong; **hold the computed-figure sentence** if X18 or X40
  refuse or compute wrongly in any draw, or any control answer invents a figure for an ask that states none.
* **Reported as it reads,** and a rule changed after the reading is reported as changed after. Not decided here: whether a miss on one question
  is the repair's or a draw's; with 27 answers no rate can be read, only cases.

## Limits

* 27 answers: a count of cases, not a rate. A single draw can flip a question.
* The targets were chosen for having failed, and the first two repairs were designed on them: this is in-sample for X26 and X35.
* The first run and this one are different hours; the provider's condition may differ.
