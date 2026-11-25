# Preregistration: the final tally on every question made, and the small profile test (2026-11-23)

Pushed before the spend, and alone. **The owner's word of 2026-11-23: "Do that small test dollar cap then, Yes run the full
test now a compilation of all the questions we have created to get a final tally what ever amount necessary"**. The small
test is the one offered the same day (below), with the owner's cap of '$1.00'. For the tally the owner left the amount to me,
so **the amount is mine, stated here before any spend: a ceiling of '$9.00', expected about '$5.0'**, and the owner is told in
the same message that this file is pushed.

## Why

The harness has been measured in parts, on question sets written at different times, under different settings. Today the
owner ruled out the three per-profile pins and the reader tier (`docs/reviews/2026-11-22-holdout2-unpinned-arm.md`), so the line-up
that ships is the one no run has measured end to end. This run asks, on every question the project has made, with that
line-up: how often is the harness right, set by set, and does its delivery tell the truth about its answers? The small test asks
one more thing the unpinned arm left open: the gain of the field profiles and the new triage model over the earlier line-up could
not be split between the two, so the same 56 field questions are answered on the engineering profile and compared with the same
questions on their own profiles, everything else equal.

## What is run

**The shipped line-up is the owner's `.env` as it stands on 2026-11-23, unchanged:** the second triage model with its default
thinking, the global answer model on the engineering tier, **no pin and no reader tier**. Default workflow
`answer-and-recompute`, **one answer a question**, by `docs/probes/short_workflows_measurement.py`, started by
`docs/probes/final_tally_launch.py` (the lanes, the ids and the caps are in its `plan`), from the clean checkout of main's code at
`ccb9d9f` (code identical to main at `1dc134a`), writing outside any git tree.

| Set (runner name) | Questions | Profile | What it is | Used to build the harness? |
|---|---|---|---|---|
| `professional` | 15 (P1-P15) | engineering | the first professional questions with signed keys | yes |
| `professional-hard` | 17 (H1-H17) | engineering | harder questions: unnamed rules, table rows, PDFs, one trap | yes |
| `professional-misleading` | 12 (M1-M12) | engineering | questions where a summary misleads | yes |
| `professional-holdout` | 42 (X1-X42) | engineering | the first hold-out set | yes: its misses shaped fixes |
| `tier2` | 25 (Q1-Q25) | engineering | the first expert questions; a screen exists, the reading is the result | yes |
| `golden` | 2 (Q6, IA) | engineering | golden's own two; its Q1-Q5 are tier-2's Q1-Q5 in another notation and are asked once, under tier2 | yes |
| `tier4` | 24 (T4-...) | engineering | the capacity questions with their catalogue pages in the message; read against their requirement statements | yes |
| `professional-holdout-2` | 174 (Y) | groups 1-9 `engineering`; 10 `legal`; 11 `finance`; 12 `medical`; 13 `science` | the second hold-out set, signed 2026-11-22 | no: unseen until the second run, and no fix has been made from it |

**311 distinct questions.** The field groups (Y127 to Y182, 56 questions) go to the profile of their group, as shipped.
**Arm E, the small test:** those same 56 questions again, on the `engineering` profile. They are not in the tally; they only
answer the question of the profile text. Arm F is the 56 as shipped (the tally's own answers for them).

Twelve processes (lanes) run together (the second run ran seven), 367 answers in all (311 + the 56 of arm E), in 18 invocations of
the runner. **Probe first** (the owner's rule, one capped call per new setting): one question each of `tier2`, `golden`
and `tier4` through the launcher, cap '$0.10' each, only to see that these sets still run under the current code and
settings; the probe is not part of any result and its questions are not re-run for it.

## Money and stops

- **Caps.** An invocation carries a cap of its questions times '$0.022' (at least '$0.30'), 1.6 times the expected cost of
  '$0.0135' an answer; the sum of caps is '$8.04'. A process starts no unit once its own spend has reached its cap and may pass
  it by the unit it is in, so the worst case with one unit past each of the 18 caps is about '$8.6': **under the ceiling of
  '$9.00'**. Expected about '$5.0' (311 answers at '$0.0135' and 56 at '$0.0125').
- **The small test:** arm E is two processes of '$0.45' each, worst case about '$0.96': **inside the owner's '$1.00'**.
- **Answers not made because a cap or a stop was reached are counted as not made and are not re-run here.** An answer blocked at
  no cost by the network (a 429, a 502) is made again once, inside the same caps, by a single further invocation.
- **Stop rules.** Any HTTP 404 in a unit's error; an HTTP 402 or an out-of-credit message; a `spend_guard_blind` entry; any unit
  whose record shows a model served on the engineering seat other than the global answer model, a pinned model anywhere, or any
  call on a reader tier; the sum of spends past '$9.00'; a process past its cap by more than one unit. On a stop the work halts
  and is reported as read.

## How it is read

- Every answer is read against its key by a blind reader and by me (D50: two readers). **An answer is right when every key item is
  right.** A key item that says "None" or "the document states no such figure" is right only if the answer says so. A wrong
  figure beside a right one makes the answer wrong. Where the two differ, both read it again and the difference is reported.
  For `tier2` and `golden` the signed keys are `evals/tier2/keys.json` and `evals/golden/keys.json`, and the screens
  (`scorer.py`, golden's) are reported beside the reading and never as the result. For `tier4` the answer is read against the
  question's requirement statements: right when every requirement is met.
- Cautions and confirmations are read off each unit's record as in the second run (`docs/probes/holdout2_analysis.py`). The stricter
  reading (a wrong claim outside the key) is reported beside the plain one.
- A tally is made for each set and for the whole, **in two groups, because only one set is unseen**: the seven sets used to build the
  harness, and `professional-holdout-2`. Undelivered answers count as made and not right.

## The bars

1. **Right on the unseen set:** at least 138 of the 174 answers of `professional-holdout-2` right (79 percent, the bar of both
   hold-out runs).
2. **No set collapses:** every set, and each group of the second hold-out set, is right in at least 50 percent of its answers.
3. **No confirmation beside a wrong figure.**
4. **Right answers come clean:** at least half of the right answers carry no caution.
5. **Wrong answers are marked:** at least half of the wrong answers carry a caution that points at the wrong part. (Missed in both
   earlier runs; the fix is a separate piece of work in another checkout and does not touch this run's tree.)
6. **Cost:** the whole run within '$9.00'; an answer costs no more than '$0.02' on average over the 311.
7. **The delivery holds:** at most 9 of the 367 answers (2.5 percent) end blocked or raised.
8. **Each seat is served as set:** the engineering seat by the global answer model in every unit that calls it, the triage seat
   by the second triage model in every unit, and no call on a reader tier in any unit.

**The comparison, arm E against arm F, on the 56 questions, by the right count on the key:** `F right - E right` at least
**+4**: the field profiles are **better** than the engineering profile on these questions; between **-3 and +3**: **no
difference shown** (the margin is 3, as in the unpinned arm); at most **-4**: **worse**, reported. It is one answer a question
and 14 a field; the per-field counts are reported as they are.

## Predictions

1. **P1 (bar 1), n = 174.** Between 160 and 172 right (92 to 99 percent): the second run read 169 on a line-up with the reader on
   and the unpinned arm read 42 of 42. About three in four that bar 1 holds with room.
2. **P2 (the tally), n = 311.** Between 265 and 295 right (85 to 95 percent) over all seven sets and the second hold-out set.
   Rough: the used sets are harder on average than the unseen one.
3. **P3 (which set is lowest), n = 8 sets.** `tier4` is the lowest set, at about two in three; it is a different kind of test
   (a design task against requirement statements) and the harness had never been measured on it with its default workflow.
4. **P4 (E against F), n = 56.** No difference shown, about two in three; the field profiles better about one in four; worse
   about one in twelve.
5. **P5 (bar 5), n = all wrong answers.** Misses again.
6. **P6 (cost), n = 367.** The whole run between '$4.0' and '$6.5'; an answer on the engineering seat costs '$0.010' to '$0.018'.
7. **P7 (bar 8), n = 367.** Holds in every unit.
8. **P8 (time), n = 12 lanes.** The longest lane takes between 2 and 3 hours.
9. **P9 (blocked), n = 367.** Between 1 and 9 end blocked; the second run had 4 of 230.

## Limits, stated beforehand

- One answer a question. 311 questions in eight sets, the smallest 2: a set of 12 or 15 is a sample with a margin of tens of points.
  A figure for a set under 25 questions is reported and not read as a rate.
- **Seven of the eight sets were used to build the harness**: their misses shaped fixes, so their rate says what the harness does
  on questions it has been tuned toward, not how it does on new ones. Only `professional-holdout-2` is unseen, and it has been run once.
- The readers are models, as the questions' authors were; the owner signed the keys. A question that one of them got wrong in
  a way nobody saw counts against the harness; a disagreement with a key is looked at first by both readers.
- The lanes run at the same time on the same machine and accounts; twelve lanes is five more than any earlier run, so a provider's
  rate limit may block an answer that seven lanes would not have.
- The reader tier and the pins are off. The earlier runs were measured with the reader on, so a difference from them may come from
  that, and the run cannot say which.
- The small test uses the same 56 questions as the second run's field arms; the questions are not new to the project, though no
  change was made from their answers.
- The tier-4 set is run through `answer-and-recompute` with its pages in the message, as its D-pages arm sends them, which is not
  the test its own runner was built for; its rate is not comparable with the earlier tier-4 reports.
