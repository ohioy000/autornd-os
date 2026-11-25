# Preregistration: DSpace frames followed to their file, on X3 and its controls (2026-11-25)

Pushed alone, before any spend of this run. No answer of this run exists. The owner authorised the whole remaining balance on 2026-11-25
("full amount is okayd for your use"); this run is capped far below it. About '$1.1' was left (my estimate).

## The question

Branch `fix/20261125-dspace-frames` (`03d648f`, main `53020e0` plus one commit): a page under 200 characters of text and under a tenth of its
bytes that loads a script is a frame and is not read, and a frame whose root is `<ds-app>` (DSpace 7: iris.who.int and others) is followed through
the repository's API to the file it stands for. **Does X3 now read the WHO guidelines PDF and give the 2021 SO2 24-hour and NO2 annual levels, and
does anything that was right stay right?** Root cause, read 2026-11-25 over the stored runs and live: the model named the right WHO PDF but the
fetch returned a 755-byte frame recorded as fetched with 33 characters, so the 7 MB guidelines were never read.

## What is run

Tree `03d648f` (a fresh worktree), the owner's `.env` unchanged (reader tier on, no pins), profile `engineering`, workflow
`answer-and-recompute`, `MEASURE_SET=professional-holdout`, two invocations:

* **A, the target:** X3, **3 draws** (3 answers).
* **B, checks, 1 draw each:** X31 (the legislation route and the frame rule on a question that reads legislation.gov.au), X35, X38, X19, X36 (5 answers).

## Money

Stated before the spend: expected **'$0.15'** (8 answers at '$0.018'); A capped at '$0.15', B at '$0.15'; **ceiling '$0.30'**. Stops: any 404, 402, 403
or key-limit message; a `spend_guard_blind` entry; a model on the answer seat other than the global answer model; the run past '$0.30'.

## How it is read

By the executor against the signed key with the answer beside it (the blind reader is skipped, as in the two earlier tests of this day, and said
so). Whether the DSpace route fired is read from the run's source records: a document at an `iris.who.int` address with a page text of 100,000 or
more characters. A page refused as a frame is read from the quote reason "shell".

## Baseline (stored records, the harness before the change)

X3: first hold-out asked again wrong, right, right; second-look run right in 3 of 3; page-quality run right, right, wrong. That is 2 wrong of 9, both
"not stated" refusals made while the WHO PDF address was a 33-character frame. X31, X35, X38, X19, X36: right in the draws that delivered, with the
known blocks and the X35 2018 refusal (the edition check has since merged).

## Predictions (written before any answer is read)

* **X3:** 3 of 3 right (SO2 24-hour 40 and NO2 annual 10 micrograms per cubic metre); the route fires in at least 2 of the 3 draws.
* **B:** 5 of 5 right or blocked by the existing no-proof rule; none wrong because a page was refused as a frame.
* **Cost:** '$0.014' to '$0.025' an answer; reading a 650,000-character PDF adds reading time and a few reader-tier calls.

## What decides

* **The fix is shown to work on X3** if at least 2 of 3 answers are right **and** the route fired in at least 2 of the 3 draws.
* **Hold the fix** if any check that is right in the baseline is wrong here because a page it used was refused as a frame (the reason says "shell"),
  naming the page.
* **Reported as it reads,** a rule changed after the reading is reported as changed after. With 8 answers only cases can be read.

## Limits

* In-sample for X3. The fix is the repository route and a general frame rule; it does not read other site families.
* A draw that never names an iris.who.int address does not exercise the route and says nothing about it.
* Different hours and provider conditions from the baseline.
