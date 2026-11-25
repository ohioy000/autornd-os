# Preregistration: the caution fix against fresh wrong answers (2026-11-23)

Pushed alone, before any spend of this run. The launcher's re-ask mode is in the commit before this one; the mode carries no
design (it plans the questions named below). No answer text and no label of the final tally has been read: the tally is still being
made. What has been read from it: a count of stored lookup records (in amendment 1), and, in the mechanical runs of the analysis
on the first run's 79 answers with placeholder labels, counts of stored decision-tier records and the cautions of three answers
that the placeholders called wrong (chosen by their code, not by what they said).

## The question

The caution fix (branch `fix/20261123-caution-flaw`) adds four cautions that read what a delivered answer says about itself, off
its typed fields: an ask with no result, a part the answer called one it could not answer, an ask it reports as not stated in the
document, and an answer text too short for the results listed beside it. On the 681 labelled answers it was designed on they stand
beside 8 of 658 right answers and 5 of 23 not-right ones. That is **in-sample**: the rules were designed after reading the typed
records of those 23. **Does it hold on answers made after it was frozen?** The owner asked for the test on 2026-11-23 and approved
this plan the same day ("I approve that plan perfect").

## What is frozen

* **The design.** The branch's code under `autornd/` and `tests/` as at `b66498e`. The head, `e49a6a1`, adds only the review, a
  probe section and the trace; `git diff b66498e -- autornd tests` is empty, and is run again before the analysis and in the
  report.
* **The truth.** Each answer is read by a blind reader, who is told neither its cautions nor its run, and by the executor on a second
  reading (D50): every not-right answer, every answer a screen flags, and a seeded sample of the rest. Where the two differ the
  executor's reading stands, and the report says so. A scorer is a screen, never the result.
* **What counts as not right:** the reader's verdict `wrong` or `partly`, as in the earlier runs.

## The fresh answers

* **A, the final tally's 367 answers** (`docs/preregistration-20261123-final-tally.md` and its amendment 1), made by main's code
  with no gap cautions; the gaps are replayed over the stored rows. Their reading is the tally's own.
* **B, the re-ask run.** The questions most likely to give wrong answers are asked again so that there are enough wrong answers to
  say what the cautions catch; the tally alone is expected to hold 10 to 20.
  * **Stage 1:** each of the 19 questions that have produced a not-right answer in the four labelled runs, asked three more times:
    H4, H8, H12 (`professional-hard`); P4 (`professional`); X12, X13, X16, X19, X20, X31, X34, X38, X41 (`professional-holdout`);
    Y68, Y124, Y140, Y146, Y149, Y170 (`professional-holdout-2`). These 19 were not right on 23 of the 83 answers made to them
    (28 percent; 3.4 percent over all 681), so about 16 of the 57 are expected not right.
  * **Stage 2:** each question whose tally answer is read not right, three more times, **at most 12 questions** (if more qualify,
    those read `wrong` before those read `partly`, then in the tally's order). The list is written to a file and committed before
    stage 2 is started, and stage 2 is not started if the whole re-ask run's spend would pass '$1.50'.
  * **How they run.** The same tree (`ccb9d9f`), `.env`, profiles and workflow as the tally. One invocation for each tally
    invocation that holds a chosen question, on the profile the question ran on there (the field questions on their own profile,
    not on the engineering profile of the small test), by `docs/probes/short_workflows_measurement.py` with three repeats. They
    start while the tally's resumed units are still being made. **No answer of either is read until both have finished.**

## Money

The owner's approval is for about '$0.8', capped at '$1.50'. Stage 1 is 57 answers at the tally's mean of '$0.0135', about
**'$0.77'**. Each invocation is capped at its answers times '$0.022' with a floor of '$0.10' (nine invocations, caps summing to
'$1.42'). The ceiling for the whole re-ask run, both stages, is **'$1.50'** of spend. The provider key's remaining limit was '$6.45'
at 11:56 UTC, and the tally's resumed units need about '$1.9' more.

## Stops

Any 404; any 402, 403, out-of-credit or key-limit message; a `spend_guard_blind` entry; a model served on the engineering seat other
than the global answer model, on the triage seat other than the second triage model, or any pinned model; any call on a reader tier;
a process past its cap by more than one unit; the re-ask run's spend past '$1.50'. On a stop the work halts and is reported as read,
and nothing is resumed without the owner. A unit that ends blocked or raised is a result (the tally's bar 7 counts such units; here
they are listed).

## How it is measured (free, after both runs have finished)

Blind packets as the tally's: each question one packet holding every delivered answer made to it (the tally's and the re-asks'),
under codes that show neither run nor arm, shuffled, with the signed key. The cautions are rebuilt from the stored phase rows exactly
as the delivery builds them, and a rebuild that does not match the cautions the run recorded stops the analysis; the gap cautions
(`routes._gaps`) are then read off the same rows. Over the fresh answers:

1. **False alarms.** Gap cautions beside right answers: in A, in B, and pooled; each marked right answer is read to say whether the
   caution is true of it.
2. **Catches.** Of the fresh not-right answers, how many carry a gap caution and, for each, whether it **points at the part that is
   wrong** (its ask or text is the one the reader's note and the key say is wrong or missing), marks something else, or marks
   nothing. By kind of caution, and by what was wrong with the answer.
3. **What stays silent.** The fresh not-right answers that carry neither a shipped nor a gap caution, each with why it is wrong.
4. **The decision-tier rule** written down on 2026-11-23 (`docs/probes/final_tally_analysis.py`): no quote judged to state an answer.
5. **Beside the in-sample figures:** 8 of 658 and 5 of 23, always said to be in-sample.

The answers split in the report: answers to questions the 681 covered (258 of the tally's 311 questions, and all of B) and answers
to questions the design never saw (the other 53: the tier-2 set's 25, the tier-4 set's 24, the golden set's 2 and 2 of the second
hold-out's; they are calculation and design questions more than document questions, so the cautions may act differently on them).
B is enriched on purpose, so it is reported by itself as well as pooled.

## Predictions (written before any answer is read)

* **False alarms:** gap cautions beside 1 to 2 percent of fresh right answers, and at most 3 percent pooled. Above 3 percent the
  review is wrong about the rules and they are reported as marking right answers too often.
* **Catches:** the gaps mark fewer than half of the fresh not-right answers, 15 to 35 percent, and where they mark one it points at
  the wrong part in at least 4 of 5.
* **What stays silent:** most not-right answers come clean. The errors the 23 showed (a right figure with a condition left out or
  misstated, a missing second item, two traps) are not visible to a check of typed fields, so the tally's bar 4 and 5 are not met by
  the gaps, as the review says.
* **The re-asks:** about 28 percent not right, so about 16 of 57. Fewer than 8 would say the earlier failures were largely the
  earlier line-up's and not the questions'.

## What decides, and what does not

* **For the fix:** at most 3 percent of the pooled fresh right answers marked, and at least 4 of every 5 not-right answers it marks
  pointing at what is wrong. The catch count is reported with its numbers and **not made a bar**: with so few not-right answers a
  rate has wide bounds, and the report says how wide.
* **Not decided here:** whether to merge. The cautions are the owner's to rule, by precedent of 2026-11-15 and 2026-11-16, and so
  are the two paid levers the review records.
* **Reported as it reads,** whether it meets the predictions or not. A rule changed after the reading is reported as changed after.

## Limits

* B's questions are chosen for having failed, so its answers are harder than a sample of all questions, and the same trap may fail
  again in the same way; its false-alarm figure is for hard questions.
* 258 of A's 311 questions were also among the 681's, so A's answers are fresh and most of its questions are not.
* The tally and the re-asks are made at different hours, and a provider's condition may differ between them; the report says which
  run made each answer.
* Two readers are two readings; a borderline answer (X34 was one in the earlier runs) can fall either side, and is listed.
