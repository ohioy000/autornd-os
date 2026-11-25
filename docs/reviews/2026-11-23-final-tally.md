# The final tally and the caution fix's fresh test, 2026-11-23

The owner asked for "the full test now, a compilation of all the questions we have created, to get a final tally, whatever
amount necessary", then for the caution fix to be tested "on a run with all the wrong answers if you think that is the most
useful way". Both were pre-registered before their spend: `docs/preregistration-20261123-final-tally.md` with its amendment 1
(the provider key's limit stopped the first run; the owner raised it and the unmade 286 units were resumed), and
`docs/preregistration-20261123-caution-test.md`. Every figure below is read off the records in `docs/traces/20261123T-final-*`
(182 files, listed with their sha256 in `20261123T-final-MANIFEST.sha256`, itself `b4192342d9de7a9897044ca4ed3835ad26ac8d16b723d8c09c8a530d57eafb83`).
The figures come from `docs/probes/final_tally_analysis.py`; its output is `20261123T-final-analysis.txt`, sha256
`850521a6a562b14113ddbb26978b5bbe4613b3c0234266ff01809509e67f6016`. A scorer is a screen, never the result: two readings are.

## The short version

- **292 of 311 questions right** (93.9 percent), one answer each, on the shipped line-up with **the three pins and the reader
  tier off**. On the unseen set, **167 of 174** (96.0 percent; bar 138). The second run read 169 with the reader on.
- **Seven of the eight bars hold; bar 5 (wrong answers carry a caution that points at the wrong part) is missed**, as in both
  earlier runs and as predicted. Bar 3 holds on the tally and fails by hand on the re-asks (below).
- **The whole tally cost '$4.27'** of a stated ceiling of '$9.00': '$0.0116' an answer.
- **The reader tier is not shown to hurt, and may help a little.** See "The reader" below.
- **The caution fix on answers made after it was frozen:** it marks 1.9 percent of right answers (limit 3) and 9 of 30 not-right
  answers; read by hand, 7 of those 9 point at the part that is wrong (the bar was 4 in 5, so one answer short). Whether to merge is the owner's.

## What was run

The checkout `ccb9d9f` (code unchanged since the second run), the owner's `.env` with the pins and the reader tier removed,
the default workflow `answer-and-recompute`, one answer a question: 311 questions in eight sets (the professional set, hard,
misleading, hold-out, tier 2, golden, tier 4 and the second hold-out) plus the 56 field questions asked again on the
engineering profile (arm E, the small test). The first run (10:38 to 11:00 UTC) was stopped by the provider key's limit after 82 answers;
the owner raised the limit and the other 286 units were resumed from 11:22 UTC and finished a little after 13:20 UTC. Every
question has one answer, from the first run or the resume; `20261123T-final-reading-codes.json` says which.

## The bars (written beforehand)

| Bar | Result | Held? |
|---|---|---|
| 1. Right on the unseen set, at least 138 of 174 | **167 of 174** (96.0%) | yes |
| 2. No set or group under 50 percent | lowest set tier 4, 19 of 24 (79.2%); lowest group 84.6% | yes |
| 3. No confirmation beside a wrong figure | **tally: 0 of 13** (its two confirmations, Y115 and Y88, sit beside right figures); **the re-asks: 3 of 17** (Y115 twice, Y124 once, read by hand: the confirmed figure is the wrong one) | holds on the tally, fails on the re-asks |
| 4. Right answers come clean, at least half | 217 of 292 (74%) | yes |
| 5. Wrong answers carry a caution that points, at least half | 5 of 13 carry one of the two phrases; **by hand 2 clearly point (Y13, Y170) and 1 arguably (T4-42)**; X31's points at a right figure and T4-58's at computed figures | **no** |
| 6. Cost within '$9.00', at most '$0.02' an answer | '$4.27'; '$0.0116' an answer | yes |
| 7. At most 9 of 367 blocked or raised | 6 of 311 (five provider failures that returned no text, one blocked on an ask it cannot satisfy); arm E 0 | yes |
| 8. Each seat served as set | 0 units off; 0 calls on a reader tier | yes |

By set (made, right): professional 15/15, hard 17/17, misleading 12/12, hold-out 37/42, tier 2 23/25, golden 2/2, tier 4 19/24,
second hold-out 167/174. The seven sets used to build the harness: 125 of 137 (91.2%); the unseen set 167 of 174 (96.0%).
Undelivered answers count as made and not right.

**Predictions.** P1 (160 to 172 on the unseen set) held at 167. P2 (265 to 295 of 311) held at 292. P3 (tier 4 lowest) held.
P4 (field profiles against engineering: no difference) held. P5 (bar 5 missed) held. P6 ('$4.0' to '$6.5') held at '$4.27'. P7 held.
P9 (1 to 9 blocked) held at 6. P8 (longest lane 2 to 3 hours) was not timed to the minute; the resume ran about two hours.

**Arm E against arm F on the 56 field questions:** F right 55, E right 56, F minus E = **-1**: no difference shown (the rule:
+4 or more better, -3 to +3 none, -4 or less worse). One question, in group 13, separates them. The field profiles cost
'$0.661' for the 56 answers and the engineering profile '$0.607'.

**Routing by the decision tier** (361 delivered tally answers): the calculation switch sent 91 to the three-sample recompute and
266 past it (it ran on 95); the lookup switch ran a lookup on 324. Quote labels on 365 of 412 right answers and 28 of 30 not-right
ones, so as before they do not separate right from wrong. The untuned rule "no quote judged to state an answer" marks 29 percent
of right answers and 50 percent of not-right ones: not a caution instrument.

## The reader

The owner asked whether removing the reader tier hurts. The record said no whole-set run with it off had been made; this is that run.

- **The count:** 167 of 174 against 169 with it on, a difference of -2 on one draw each. Of the seven second-hold-out answers read
  not right now (Y9, Y13, Y37, Y68, Y88, Y115, Y170), two (Y68, Y170) were also not right with the reader on, and five were right
  then. Four questions not right then are right now (Y124, Y140, Y146, Y149). So it is churn of five against four.
- **A lead on mechanism, free, read off stored lookups:** for Y115 and Y88 the earlier reader-on run's handed-on text contains the
  answer's wording ("5 minutes"; "three calendar years" or "next audit") and the tally's does not, and both answers were then wrong
  or missing that item. That is what the reader is for: a passage the word-matching stretches miss. It is a regular-expression
  check on one draw each, not a measurement; Y9, Y13 and Y37 do not look like reader effects.
- **So:** not shown to hurt in aggregate; possibly worth about one to two answers in 174; no more. Putting it back (about
  '$0.0028' an answer) is the owner's call.

## The caution fix, on answers made after it was frozen

The design is the branch's code at `b66498e` (`git diff b66498e -- autornd tests` is empty); the head adds only the review and a
probe. The cautions were rebuilt from the stored rows and each rebuild matched the delivery's recorded cautions. 442 answers: A, the
tally and arm E (361); B, the 84 re-asks (81 delivered): stage 1 asked the 19 questions that had produced a not-right answer three
more times, stage 2 the 9 other questions whose tally answer read not right (the other 4 had been asked in stage 1; the
preregistration said "each", this is the one departure). The whole re-ask run cost '$1.09' of '$1.50'.

| | answers | right | not right | gap beside right | gap beside not right | shipped or gap, not right |
|---|---|---|---|---|---|---|
| A, tally and arm E | 361 | 348 | 13 | 7 (2.0%) | 5 of 13 | 11 of 13 |
| on questions the 681 covered | 313 | 303 | 10 | 7 (2.3%) | 5 of 10 | 8 of 10 |
| on questions it never saw | 48 | 45 | 3 | 0 | 0 of 3 | 3 of 3 |
| B, the re-asks | 81 | 64 | 17 | 1 (1.6%) | 4 of 17 | 11 of 17 |
| pooled | 442 | 412 | 30 | **8 (1.9%)** | **9 of 30 (30%)** | 22 of 30 |

In-sample, on the 681 it was designed on: 8 of 658 right and 5 of 23 not right. The fresh figures are close to those, which is
what a design that generalises would show.

**Against the predictions.** False alarms 1 to 2 percent and at most 3 pooled: **held** (1.9). Catches 15 to 35 percent: **held**
(30). At least 4 of 5 of the marked not-right answers point at the wrong part: **by hand, 7 of 9, one short** (the two that mark
another ask: Y68 `af6310da` marks ask 2 where the wrong part is ask 1's headline value, and Y170 `3108c5c5` marks the
location constraint where the wrong part is the threshold). "Most not-right answers stay silent": **did not hold**: 8 of 30 carry
neither a shipped nor a gap caution (X14; Y124 re-ask; Y68 three times; Y115 twice; Y88 once), 22 of 30 carry one. But the
shipped ones are mostly "that figure is in none of the passages", which is true of every computed figure, so how often they
point is mixed. The re-asks were not right 21 percent of the time (stage 1: 8 of 54, 15 percent; prediction 28).

**What the 8 right answers that got a gap are.** Six say "no result for ask N" where the answer's prose does give the value
(Y4, Y89, Y104, X22, Y158, Y129): true of the typed field, harmless to the reader. Two (X36, X19 re-ask) are right answers whose
key says "none is stated", which the answer states: the gap reads that as "could not answer". That is the one real weakness the
fresh test shows: **the rule cannot tell "could not answer" from "correctly says none is stated"**, and the trap questions are
where it fires wrongly.

**The verdict as the preregistration framed it:** at most 3 percent of right answers marked: met. At least 4 in 5 of the marked
not-right answers pointing: 7 of 9, **not met** by one answer, on 9 answers whose bounds are wide. The decision to merge is
the owner's (the cautions are, by the precedent of 2026-11-15 and 2026-11-16).

## What stays wrong, and what the readers disagreed on

Thirty answers were not right across the two runs; the keys' own misses were: a figure with a condition left out or misstated
(X8's final-report clock, Y9's Article 4 for 4(2), Y88's retention), a missing second item, a refusal to commit ("blocked" on X41
twice), a trap answered from memory (Y68 wheel; X14 yes), and the tier-4 designs that miscompare a current (T4-42) or report
drops without the power factor (T4-58).

- **Readers.** Fifteen blind readers (one read the wrong chunk and was redone; its output is kept apart) and two more for the
  re-asks, then the executor on a second reading of every not-right answer, every screen flag (all seven were false flags) and a
  seeded sample of 30 right ones. They differ on one answer: **Y145 `f84a406d`**, which gives 99.5 percent over one year and 1-in-200 with the right arithmetic but says
  the Directive does not state a ruin frequency; the blind reader said wrong, I read it right (borderline). It is counted right.
  **X20 `3ab7797a`** says "superseded" and never "withdrawn 14 May 2024"; both readings not right (borderline). The re-read of nine
  old answers in stage 2 agreed with the first reading on eight (the ninth moved from partly to wrong).
- **A key the owner may want to look at.** Y13's key says the EU-level threshold is EUR 1,000,000. Three of the four answers made to it name a newer
  figure (EUR 5,000,000 twice, EUR 12,000,000 once, citing the Listing Act amendment) and the fourth
  gives 1,000,000 and lists a 12 million figure as context. I followed the signed key and counted them not right. If the law
  changed, the key is stale; a key change is a new key version the owner ratifies (D44), not mine.

## Disclosures

- **What was seen before the reading.** Mechanical test runs of the analysis, before any reading, printed counts of stored
  decision-tier records, the cautions of three answers that placeholder labels called wrong and the gap cautions of five
  first-run answers; none showed an answer's text or a real label. The second reading was made from packets and the screen, not from cautions.
- **My viewer cut answers at the first `---` inside their text** during the second reading. I found it when two sampled answers
  looked too short, re-extracted every answer correctly, and re-checked the verdict-bearing ones (X8, Y170, Y161, Y140, Y145,
  Y124): no verdict changed. The blind readers read the packets themselves and were not affected.
- **Depth of the sample reading.** Ten of the 30 sampled right answers were read in the answer text; the other 20 and the 18 right
  answers of stage 2 were checked against the key by the readers' stated values, the reference design (tier 4) and the screen's
  number-presence test. The 22 not-right answers and the 7 flagged were read in full.
- **The one departure from the preregistration** is the 9 questions of stage 2 against "each" of 13 (above).
- **Ceiling.** The provider key's limit was raised twice by the owner ('$58', then '$68'); '$54.17' of it is used.

## Limits

One answer a question, and most sets are small; a figure for a set under 25 questions is reported, not read as a rate. Seven of
eight sets were used to build the harness. The re-asks are asked of questions chosen for having failed, so their false-alarm
figure is for hard questions, and 258 of the tally's 311 questions were among those the fix was designed on. The tally and the
re-asks were made hours apart. The reader's effect is a lead on two answers. Two readers are two readings.

## For the owner

1. **Merge the caution fix?** Its rules and the in-sample and fresh figures are above; it adds four typed cautions and changes
   what a delivery says, so it is a ruling, and nothing is merged.
2. **Put the reader back?** About '$0.0028' an answer; a possible gain of one or two answers in 174.
3. **Y13's key** (above).
4. **The proof-of-absence lead:** the second triage model returned search words for few of the units it was asked about; a diagnostic of
   about '$0.002' is unrun and waits for a yes.
5. **Pull requests** for the evals branch and the caution branch are not opened.
