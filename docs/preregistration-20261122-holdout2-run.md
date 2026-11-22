# Preregistration: the second hold-out run, on the shipped line-up (2026-11-22)

Pushed before the spend, and alone. **The owner's word of 2026-11-22: "Approved whatever you think necessary"**, in answer
to the message that asked for an amount and the arms and named the questions' set and the line-up. The owner left both to me, so
**the amount is mine, stated here before any spend: a ceiling of '$7.00', expected about '$4.70'**, and the owner is told in
the same message that this file is pushed.

## Why

The first hold-out run (`docs/reviews/2026-11-17-holdout-run.md`) found 113 of 126 answers right (97 on the stricter
reading) on questions nobody had tuned for, and its misses shaped the fixes since. Everything since (the PDF reader, per-profile
pins and prompts, a second triage model as the default, new answer models for three profiles, the spend guard's bound on any
price) has been measured on parts, never together on questions written after it. The second hold-out set is the first set
written after all of it: `professional-holdout-2`, 174 questions signed and frozen by the owner on 2026-11-22
(`evals/professional/holdout2-questions.json`, sha256 pinned in `tests/test_holdout2_set.py`). This run asks the same question as
the first: on those questions, how often is the harness as shipped right, and does its delivery tell the truth about its answers?
It adds one: did the field profiles and their pinned answer models do better on the fields they were made for than the global
setup they replace?

## What is run

The shipped line-up is the owner's `.env` as it stands on main at the commit carrying this file (`MODEL_TRIAGE` the second
triage model with its default thinking, the global answer model on the engineering tier, the three pins of `PROFILE_MODELS`),
unchanged. Default workflow `answer-and-recompute`, **one answer a question**, by `docs/probes/short_workflows_measurement.py`
with `MEASURE_SET=professional-holdout-2` (which records, since this commit, the profile, the pins, and the models and providers
that served each unit). Questions go to the profile of their group, the groups being the set's own (`docs/holdout-2-prompts.md`:
ids Y1 to Y14 are group 1, and so on in blocks of 14):

| Arm | Questions | Profile | Answer tier | Triage |
|---|---|---|---|---|
| N1, N2 | groups 1 to 9, 118 questions (59 each) | `engineering` | the global answer model | the second triage model |
| N3 | group 10 law, Y127 to Y140 | `legal` | the legal model (pinned) | the second triage model |
| N4 | group 11 finance, Y141 to Y154 | `finance` | the new large model (pinned) | the second triage model |
| N5 | group 12 medicine, Y155 to Y168 | `medical` | the new large model (pinned) | the second triage model |
| N6 | group 13 natural science, Y169 to Y182 | `science` | the global answer model | the second triage model |
| O | groups 10 to 13, the 56 questions of N3 to N6 | `engineering` | the global answer model | **the earlier triage model, set in the process environment** |

Arm O is the line-up before today, applied to the same 56 questions: `MODEL_TRIAGE`, the `triage` entry of the provider order
and `PROFILE_MODELS` (unset) are the only things set in the process environment, and the effective map is in each header.
**Probe first** (the owner's own rule: one capped call per new setting): one question, Y1, under `engineering`, cap '$0.10',
only to see that the record carries the new fields; it is not part of any result and is not re-run.

Seven processes run together (N1 to N6 and O), each from the clone of main at the committed hash, writing outside any git tree.
Processes start no unit once their own spend has reached their cap, which they may pass by the unit they are in (the largest
unit is expected near '$0.15' for the two large-model arms).

## Money and stops

| Process | Cap | Expected |
|---|---|---|
| N1, N2 | '$1.00' each | '$0.80' to '$0.90' each (59 answers at about '$0.014') |
| N3 legal | '$0.80' | '$0.30' |
| N4 finance, N5 medicine | '$1.20' each | '$0.8' to '$1.6' each (hydrogen answers cost '$0.02' to '$0.06' a question in the smoke) |
| N6 science | '$0.50' | '$0.20' |
| O | '$1.00' | '$0.65' |

Sum of caps '$6.70', the worst case with one unit past each cap about '$7.00': the ceiling stated above. Expected total about
'$4.70'. Answers not made because a stop was reached are counted as not made and are not re-run here. If the network drops,
answers blocked at no cost are made again inside the same caps. **Stop rules:** any unit whose record shows a model served on
a tier that its profile does not pin (the pinned id absent from a pinned arm, or present in an unpinned one); any HTTP 404
in a unit's error; a `spend_guard_blind` entry on a pinned model; a process past its cap by more than one unit. On a stop,
the work halts and is reported as read.

## How it is read

- Every answer is read against the signed keys by a blind reader and by me (D50: two readers; there is no screen on this set).
  **The rule, as the first hold-out run used it: an answer is right when every key item is right.** An item that says "None"
  or "the document states no such figure" is right only if the answer says so. A wrong figure beside a right one makes the
  answer wrong. Where the two readers differ, the answer is shown to both again with the keys, and the difference is reported.
  The stricter reading (a wrong claim outside the key) is reported beside it, as in the first run.
- Cautions and confirmations are read off each unit's record as in the first run
  (`docs/probes/acceptance_run_analysis.py`).
- Two cuts are reported: all 174, and the questions the harness's own fetch can read (`verify_keys.py`, as in the first run).

## The bars

1. **Right on questions nobody tuned for:** at least 138 of the 174 answers of N1 to N6 right (79 percent, the first run's bar).
2. **No confirmation beside a wrong figure.**
3. **Right answers come clean:** at least half of the right answers carry no caution.
4. **Wrong answers are marked:** at least half of the wrong answers carry a caution that points at the wrong part.
5. **Cost:** the whole run within '$7.00'; an N1 or N2 answer costs no more than '$0.02' on average.
6. **The delivery holds:** at most 5 of the 230 answers end blocked or raised (a 429 after five attempts included).
7. **No group collapses:** each of the thirteen groups is right in at least 50 percent of its answers.
8. **Each seat is served as set:** in every N3, N4 and N5 unit the engineering tier is served by exactly its pinned model and
   provider, and in every other unit by the global answer model.

**The comparison (arm O against N3 to N6), on the 56 questions, by the right count on the key:**
`N right − O right` at least 5: the field profiles and their pinned models are **better** than the global setup on these fields;
between −3 and 4: **no difference shown** (the margin is 3, the first sweep's spread between identical arms being 2 to 3 units
on 180); at most −4: **worse**, reported, and the pins and profile texts are the owner's to reconsider. It is one answer a
question, 14 questions a field, and the per-field counts are reported as they are with that said.

- Bar 1 or 7 missed: reported as it reads. No change follows without a ruling.
- Bar 2 missed: the case goes to the owner before anything else.
- Bars 3 and 4 missed: reported; the known limits grow by what the run shows.
- Bar 5 missed on cost: reported, with the arm and the tier that caused it.
- Bar 8 missed: stop, as the stop rules say.

## Predictions

1. **P1 (bar 1), n = 174.** Between 140 and 158 right (80 to 91 percent); lower than the first run's 90 percent on the
   harder fields and the traps, higher than the bar. About two in three that bar 1 holds with room.
2. **P2 (the comparison), n = 56.** No difference shown (between −3 and 4), about one in two; better about one in four; worse about one in four.
3. **P3 (bar 2), n = 174.** Holds: 0 confirmations beside a wrong figure; about three in four.
4. **P4 (bar 4), n = 174.** Misses, as it did in the first run and the acceptance run.
5. **P5 (cost), n = 230.** The whole run costs between '$3.50' and '$6.00'; an N4 or N5 answer costs '$0.03' to '$0.10'.
6. **P6 (bar 8), n = 230.** Holds in every unit.
7. **P7 (time), n = 7 processes.** The longest takes about 3 hours: the second triage model's thinking costs about 19 seconds a
   triage call, and a question makes two.
8. **P8 (where it is wrong), n = 174.** The traps ("the document states no such figure") and the PDF-table questions are the
   least often right, as in the first run; group 12 (medicine) is among the three lowest groups.

## Limits, stated beforehand

- One answer a question; 174 questions is a sample, and 14 a field a very small one. A figure of 85 percent has a margin of
  several points either side of it.
- The questions were written and checked by language models, then signed by the owner. A question one of them got wrong in a way
  the owner did not see counts against the harness; a disagreement with a key is looked at first by both readers.
- Arms N1 to N6 are not one controlled arm: each group runs on its profile, so the three pins and the two profiles that carry
  none are measured together with the questions of their field. Only the comparison on groups 10 to 13 isolates the line-up.
- The arms run at the same time on the same machine and provider accounts; the second triage model's provider served five lanes
  at once in an earlier study with no upstream 429.
- The second triage model's thinking makes each answer slow; a person waiting on one would wait about 40 seconds longer.
