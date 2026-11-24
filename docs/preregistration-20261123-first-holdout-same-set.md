# Preregistration: the first hold-out asked again of the harness as it is now (2026-11-23)

Pushed alone, before any spend of this run. No answer of this run exists. Nothing from the first hold-out has been read for this run
beyond what is already recorded (`docs/reviews/2026-11-17-holdout-run.md`, `2026-11-19-holdout-misses-classified.md`).

## The question

The owner asked on 2026-11-23 whether the additions made to the harness add accuracy, was shown a deduction from stored data
that left three weak spots (the reader comparison is small, the gain from 89.7 percent to 96 to 97 percent crosses two different
question sets, and there is no clean switch-off test), and then ruled: **keep all the additional functions, no frontier model
is needed, compare the outputs of our harness on the same set.** The same set is the first hold-out (`evals/professional/holdout-questions.json`,
42 questions, X1 to X42), on which the harness read **113 of 126 right (89.7 percent)** in its three draws a question on 2026-11-17.
This run asks it again, three draws a question, with everything now in it, and compares like with like.

## What is run

* **The harness with every addition on.** The tree `/home/jb/autornd-os-wt-v2run` at `957bc08` (main plus the revised caution fix,
  which includes the proofs of absence with their words made at thinking off), the owner's `.env` unchanged (the reader tier on,
  the decision tier, the recompute vote, the second triage model, the global answer model; **no profile pins**), profile
  `engineering`, workflow `answer-and-recompute`, as the first hold-out ran.
* **The questions:** X1 to X42, **3 draws each, 126 answers**, in two invocations of
  `docs/probes/short_workflows_measurement.py` run together (X1 to X21 and X22 to X42), `MEASURE_SET=professional-holdout`.
* **Nothing else changes** between the old run and this one that I can hold fixed: the question text, the signed key, the profile,
  the workflow and the runner are the same files. What differs is the harness's code since 2026-11-17 and the provider's condition.

## Money

Stated before the spend. Expected **'$2.1'** (126 answers at the tally's mean of '$0.0135' plus about '$0.003' an answer for the reader
tier); each invocation capped at its 63 answers times '$0.022', **'$1.39'**; **ceiling for the run '$2.80'**. The provider key has
'$11.60' of its limit left (read 2026-11-24 01:07 UTC). Stops: any 404, 402, 403, out-of-credit or key-limit message; a
`spend_guard_blind` entry; a model on the answer seat other than the global answer model, on the triage seat other than the second
triage model, or any pinned model; a reader model other than the one in `.env`; an invocation past its cap by more than one unit; the
run's spend past '$2.80'. On a stop the work halts and is reported as read.

## How it is read

As the earlier runs (D50): each question is one packet holding its three answers under codes that show neither run nor draw (and
none mixed in from other runs, so the reader cannot tell which answer is which); five blind readers read the key against the answers
and give `right`, `partly` or `wrong` with a note; the executor makes a second reading of every not-right answer and of 20 right
answers drawn by seed, **before looking at any caution or at the old run's labels**; where the two differ the executor's reading
stands and the report says so. **Not right is `wrong` or `partly`.** The scorer is a screen, never the result. The old run's
per-draw readings are used only after both readings of this run are final.

## What is compared

1. **All 42 questions:** right answers of 126 now, against 113 of 126.
2. **By question, paired:** how many questions have more right draws now, the same, or fewer (sign test).
3. **The eleven questions that had a not-right answer in the old run** (X3, X12, X13, X16, X19, X20, X24, X31, X34, X38 and X41, as in
   `docs/probes/eleven_rerun_analysis.py`) **and the other 31:** right draws of each group now against then.
4. **Cost and time an answer**, against '$0.0108' and 107 seconds.
5. **What the not-right answers are**, one line each, and for each whether it is one of the weaknesses already on record (a page
   too small to be the document, a stale page, a thin lookup).

## Predictions (written before any answer is read)

* **Right: 118 to 123 of 126 (94 to 98 percent).** The old figure's misses were scattered draws of a thin lookup; the lookup is
  now retried and read in parallel by the reader tier, and X41, the one that failed every time, is right through the typed channel.
* **The eleven:** at most 3 not-right answers of 33 (the old run had 13 of the 126 in all, 2 of the 22 other draws of them).
* **The 31:** at most 2 not-right answers of 93. A rise past that would be a regression of the additions, not of the questions.
* **Cost:** '$0.014' to '$0.018' an answer.

## What decides

* **The additions are said to have raised the first hold-out when:** (1) right answers are **at least 119 of 126 (94.4 percent)**,
  five points above the old figure, and (2) **no more than 2 not-right answers fall among the 31** that were right in every old draw.
* **If (1) is missed,** the rise from 89.7 to 96 to 97 percent between the two hold-outs is put down to the question sets and the
  report says so. **If (2) is missed,** the additions cost accuracy on questions that used to be answered right and the report names them.
* **Whatever the result, nothing is removed:** the owner's ruling is to keep every addition. The result sets what the README, the
  handover and the memory may say about accuracy.
* **Reported as it reads,** whether it meets the predictions or not. A rule changed after the reading is reported as changed after.

## Limits

* **In-sample.** The X questions are the set the harness was last improved against: the proofs of absence were designed from X41, the
  retry from the cut-off answers, the reader tier from the thin lookups. A rise here shows the fixes work on what they were made for;
  it is **not** the fresh figure. The second hold-out (96.0 percent in the tally, 167 of 174) is the fresh one.
* **The whole harness, not one addition.** Between the two runs the code, the model line-up and the provider's condition all moved. The
  comparison cannot say which addition did what, and the report does not claim it.
* **Three draws a question are not independent of each other** (the old run's misses scatter; the same hour, the same provider state).
  The interval on 126 answers is wide: at 120 of 126 (95.2 percent) the 95 percent bounds are about 90 and 98.
* **One reading of 20 right answers by the executor** is a sample, not every right answer.
