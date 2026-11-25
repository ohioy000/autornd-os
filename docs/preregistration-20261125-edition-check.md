# Preregistration: the edition check with the second look, on X35 and its controls (2026-11-25)

Pushed alone, before any spend of this run. No answer of this run exists. The owner ruled "Yes to both" on 2026-11-25 to the proposal
`docs/proposals/2026-11-25-edition-check.md`: the edition check and the second look. About '$1.4' is left on the provider account (my estimate:
'$1.7' before the page-quality test, '$0.31' spent since).

## The question

Branch `feat/20261125-edition-check` (`fa77041`: main `300d12a`, the second look `83db0c0`, the edition check): **does X35 now give the CODATA 2018
value, and does anything that was right stay right?** A proof of absence now counts only on a page that carries a year the request names and
the ask's search words repeat; a page of another edition counts as "no page that has the words", so the second look searches again.

## What is run

The tree `fa77041` (a fresh worktree), the owner's `.env` unchanged (reader tier on, no pins), profile `engineering`, workflow
`answer-and-recompute`, `MEASURE_SET=professional-holdout`, **3 answers each, 15 answers**, one invocation:

* **Target:** X35 (the 2018 value refused in 2 of the last 9 draws, 3 of the 9 earlier on the first set).
* **Checks that must stay right:** X38 (the 2009 value; its two dropped proofs are on an 11th edition table of contents), X19 and X36 (right "none
  stated" answers). X41 (the thermal figure, a known key-scope question after the page-quality test) is run as the fourth control and read for what it is.

## Money

Stated before the spend: expected **'$0.27'** (15 answers at '$0.016', plus the second look on the asks it fires for); one invocation capped at
**'$0.40'**, which is the ceiling. Stops: any 404, 402, 403 or key-limit message; a `spend_guard_blind` entry; a model on the answer seat other than
the global answer model; the run past '$0.40'.

## How it is read

By the executor against the signed key with the answer beside it (the blind reader is skipped again, as in the page-quality test, and said so),
every not-right answer and every X35 answer in full. Not right is `wrong` or `partly`. Whether the second look fired is read from the documents'
`request` field (2) in the run's records, and what the edition check dropped from the proofs in the run's source records (a quote or proof url
with the year missing is not listed as a proof).

## Baseline (stored records, the harness before the change)

X35: first hold-out asked again right, right, wrong (2018 refused); second-look run right in 3 of 3; page-quality run right, partly (2018 refused),
right. X38: right in every draw of the first hold-out asked again. X19, X36: right in every delivered draw. X41: right in 2 of the first
three, then (page-quality run) blocked once and two answers giving the real Microchip page figure against the key.

## Predictions (written before any answer is read)

* **X35:** all three draws give the 2018 value; the second look fires in at least 2 of the 3 draws.
* **X38, X19, X36:** 9 of 9 right.
* **X41:** unchanged from the page-quality run (a figure from the real page, or blocked); the edition check does not touch it (the request names no year).
* **Cost:** '$0.016' to '$0.022' an answer.

## What decides

* **The edition check is shown to work on X35** if the 2018 value is given in at least 2 of 3 draws **and** the second look fired in at least 2.
* **Hold the edition check** if any X38, X19 or X36 answer that is right in the baseline is not right here **and** the cause is a proof the check
  dropped (read from the records). A miss from another cause is reported as that.
* **The second look**: held again if it fires on a draw whose answer is then not right where it was right (the X31 reading of 2026-11-25 is why: it
  regressed on tiny pages, which the page-quality branch, not part of this tree, addresses).
* **Reported as it reads,** and a rule changed after the reading is reported as changed after. With 15 answers no rate can be read, only cases.

## Limits

* In-sample for X35: the proofs this rule drops were found on it. X38 was not chosen for failing.
* The tree does not carry the page-quality branch, so X31-like landing pages still count as pages here.
* Different hours and provider conditions from the baseline; three draws a question.
