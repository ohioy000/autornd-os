# The second hold-out run, 2026-11-22

The run asked the first hold-out run's question again, on questions written after everything that
came since: on 174 questions nobody tuned for, how often is the harness as shipped right, and does
its delivery tell the truth about its answers? It added one: do the field profiles and their pinned
answer models do better on their fields than the global setup they replace? It was
pre-registered before the spend (`docs/preregistration-20261122-holdout2-run.md`, commit `ccb9d9f`,
pushed 17:16:49 CST; the one-question probe wrote its header at 17:16:58). The owner's word:
"Approved whatever you think necessary", with the amount and the arms left to the author.

## The point

- **169 of the 174 answers made are right on the key** (97.1 percent; 169 of 172 delivered, 98.3
  percent). The bar was 138. The first hold-out run read 113 of 126 (89.7 percent) on its set.
- **Every bar is met except bar 4**, which was predicted to miss. Bar 2 holds, with one case to read
  below. No group is under 92 percent.
- **The comparison reads "no difference shown", at the edge of "better".** On the 56 questions of the
  four field groups, the field profiles with their pinned models were right 55 times and the
  earlier line-up 51: a difference of +4, where +5 is "better". Two of the five that the earlier
  line-up did not get right were upstream rate limits on its triage model (429), not wrong answers.
- **The pinned answer models cost much more.** The 56 answers of the field arms cost '$2.34'; the same
  56 on the earlier line-up '$0.70'. The legal model cost '$0.0258' an answer, the new large model
  '$0.0715' (finance) and '$0.0569' (medicine), against '$0.0129' on the global answer model.
- **'$4.72' for the run** (the probe cost '$0.0115' more, and is not a result), a ceiling of '$7.00'
  stated before. The slowest process took 3 hours 18 minutes (N2).

## What was run

Main at `1dc134a` plus the probe fields of `400de16`, in a clean checkout of `ccb9d9f`; the owner's
`.env` as it stands (the second triage model with its default thinking; the global answer model on
the engineering tier; the three pins), the default workflow `answer-and-recompute`, one answer a
question, by `docs/probes/short_workflows_measurement.py` with `MEASURE_SET=professional-holdout-2`.
Seven processes ran together, each from the same checkout, writing outside any git tree:

| Arm | Questions | Profile | Answer tier served | Made | Delivered | Right | Cost | Seconds an answer |
|---|---|---|---|---|---|---|---|---|
| N1 | groups 1-9, first 59 | engineering | the global answer model | 59 | 57 | 57 | '$0.72' | 153 |
| N2 | groups 1-9, other 59 | engineering | the global answer model | 59 | 59 | 57 | '$0.95' | 201 |
| N3 | group 10 law | legal | the legal model (pinned) | 14 | 14 | 14 | '$0.36' | 228 |
| N4 | group 11 finance | finance | the new large model (pinned) | 14 | 14 | 13 | '$1.00' | 257 |
| N5 | group 12 medicine | medical | the new large model (pinned) | 14 | 14 | 14 | '$0.80' | 190 |
| N6 | group 13 science | science | the global answer model | 14 | 14 | 14 | '$0.18' | 202 |
| O | groups 10-13, the 56 of N3-N6 | engineering | the global answer model | 56 | 54 | 51 | '$0.70' | 128 |

Arm O ran the line-up before today: the earlier triage model, no pins, set in the process
environment only. Groups are the set's own blocks of 14 ids; the 174 questions are Y1 to Y182 less
the 8 the set withholds. `verify_keys.py` found every passage and figure of the drafted set on its
live page on 2026-11-21, so the cut "the questions the harness's own fetch can read" is the whole
set and no second cut is reported.

## How it was read

Every answer was read against the signed keys twice (D50, no screen on this set; the rule as in the
first run: **right when every key item is right**, a trap right only if it says so). Six blind
readers, each model agents given only the question, the signed key and the answers under codes
(`docs/traces/20261122T-holdout2-reading-codes.json` kept back), read 226 delivered answers: 220
right, 4 wrong, 2 partly. I read all six that were not right against the keys, found each as the
blind reader had, and read besides: a script screened all 220 right answers for the key's numbers
(two lacked one in the text, Y168 and Y178, both right when read), the trap-keyed ones for a
statement that the figure is absent, and six more drawn at random (seed 20261122), three of them
from the two readers who marked every answer right. **No verdict was changed; the two readers
agreed on every answer.** That the readers are models, as the authors of the questions were, is a
limit. The stricter reading (a wrong claim outside the key) finds one, in a partly-right answer.

> **Addendum, same day:** the comparison below cannot separate the pins from the profile and triage change. The run that does
> (`docs/reviews/2026-11-22-holdout2-unpinned-arm.md`) found the unpinned global answer model right on 42 of 42 of the same
> field questions against 41 of 42 pinned: the pins are not shown better, and the gain came from the profile and the triage model.

## The bars

| Bar | Result | |
|---|---|---|
| 1. At least 138 of 174 right | **169** (the 2 blocked of N1 count as not right) | Met |
| 2. No confirmation beside a wrong figure | **0 on a wrong figure; 1 beside a partly-right answer** (Y124, below) | Met |
| 3. At least half the right answers carry no caution | **130 of 169** (77 percent) | Met |
| 4. At least half the wrong answers carry a caution that points | **0 of 3** | **Missed**, as predicted |
| 5. Run within '$7.00'; N1 or N2 answer at most '$0.02' | **'$4.72'**; '$0.0127' and '$0.0161' | Met |
| 6. At most 5 of 230 end blocked | **4** | Met |
| 7. Each group right in at least 50 percent | lowest 91.7 percent of made | Met |
| 8. Each seat served as set | **Every N3, N4, N5 unit, and every unit of the others, on exactly its model and provider** | Met (a reading note below) |

By group, right of made: 1: 12 of 13, 2: 14, 3: 14, 4: 11 of 12, 5: 13 of 14, 6: 14, 7: 10, 8: 13,
9: 13 of 14, 10: 14, 11: 13 of 14, 12: 14, 13: 14.

**Bar 2.** The only confirmation beside an answer that was not right is Y124 (N2, partly right). The
confirmation stands on the 25 Hz figure, which is the key's figure; what is missing is the key's
reason (the filter removes input above 25 Hz, so the energy above it is low), and the answer quotes
another sentence of the document as the "exact text". By the bar's words, a confirmation beside a
wrong figure, it holds. It is the nearest thing to a miss and is put here so it can be read.

**Bar 4.** The three not-right answers of the new arms carry no caution. Y68 (N2) and Y124 (N2) are
the traps; Y149 (N4) declares one of its two asks blocked for want of a page the question named. The
fourth caution in the run is on an arm O answer (Y146): two pages gave different figures (85 and 50)
and the harness said so, correctly; the answer still gave no sum.

**Bar 6.** Four units ended blocked: Y13 (N1) a 502 from the provider; Y52 (N1) a JSON that did not
parse; Y161 and Y169 (O) a 429 on the earlier triage model, upstream rate-limited. None was made
again, as the pre-registration says.

**Bar 8, a reading note.** Three completed units of the engineering profile (Y17 and Y39 of N1, Y124
of N2) have no engineering call: their answer was written on the architecture tier, and their triage
read low risk. That is outside the bar's words (nothing was served on the engineering seat but
what was set), and is a lead seated on the architecture tier by the engineering profile; I did not
trace the choice further. It is listed as found, not touched.

## The comparison, arm O against N3 to N6 (56 questions)

| Group | N right | O right | of 14 |
|---|---|---|---|
| 10 law (legal model pinned) | 14 | 13 | |
| 11 finance (new large model pinned) | 13 | 13 | |
| 12 medicine (new large model pinned) | 14 | 13 | |
| 13 science (global answer model, no pin) | 14 | 12 | |
| **Total** | **55** | **51** | **+4** |

By the rule written before the run: **no difference shown** (between -3 and +4). Read as it is:
- Where the arms differ is mostly not the pinned models. Group 13 has no pin and carries the largest
  gap (+2): there the two arms differ only in the triage model and the profile text.
- Two of O's five that were not right are the 429 blocks; without them, O was right on 51 of 54
  delivered (94.4 percent), N on 55 of 56 (98.2 percent). The rule counts a blocked answer as not
  right, and that count is the one above.
- O's other three were: Y140 delivered the single word PLACEHOLDER; Y146 declined to give the sum; Y170
  said the threshold is not stated. N's one miss in these groups is Y149.
- 14 questions a field and one answer each is a very small sample: a gap of 4 is one past the margin
  of 3 that the pre-registration took from the first sweep, where identical arms differed by 2 to 3
  units on 180.
- **Cost against the gain:** the field arms cost 3.3 times as much for the 56 answers. For the
  finance and medicine answers the new large model costs 5.5 and 4.4 times the global answer
  model's cost an answer. Whether four answers in 56 are worth that is the owner's.

## Predictions

| | Said | Read |
|---|---|---|
| P1 | 140 to 158 right | **169**: above the range; the bar held with room |
| P2 | no difference about one in two | **no difference shown (+4)** |
| P3 | bar 2 holds | **holds** (with the Y124 case) |
| P4 | bar 4 misses | **missed (0 of 3)** |
| P5 | '$3.50' to '$6.00'; N4 or N5 answer '$0.03' to '$0.10' | **'$4.72'; '$0.0715' and '$0.0569'** |
| P6 | bar 8 holds in every unit | **holds** |
| P7 | the longest about 3 hours | **3 hours 18 minutes** |
| P8 | traps and PDF-table questions least often right; group 12 among the three lowest | **half right**: two of the three not-right new-arm answers are traps; group 12 was right on all 14 |

## What it says

- The shipped line-up answers questions nobody tuned for at 97 percent on the key, above the first
  run's 90 percent on its own set (different questions, so a comparison of two samples, not of one
  instrument). The second reading found nothing the blind readers missed.
- The traps are still the weak place: a figure that the document does not state was given as one
  (Y68), and a right figure was given with the wrong reason (Y124). The harness did not mark either.
- Wrong or partly right answers still come with no pointing caution (bar 4, as in the first run and
  the acceptance run). The known limits grow by this and no change follows without a ruling.
- Whether the pins are worth their cost is the owner's. This run could not isolate them; the unpinned arm did
  (see the addendum): no gain shown, at 3.1 times the cost.

## Found, not touched

- Three engineering-profile units were answered on the architecture tier; see bar 8.
- The earlier triage model was rate limited upstream twice in arm O (429 after five attempts).
- No unit recorded a spend-guard blind entry. (The decision model was unrated in the catalogue in the
  earlier measurement; this run did not test that again.)
- Studio is still unmeasured on the second triage model's thinking; science now has 14 answers on it.
- The triage call costs about 19 seconds with thinking on, and a question makes two: 153 seconds an
  answer on the global answer model, against 128 on the earlier triage model.

## The record

All byte-identical in `docs/traces/`, prefix `20261122T-holdout2-`; first 16 characters of the
sha256:

| File | sha256 |
|---|---|
| `N1-shard-0.jsonl` | `2a346343c9b2a183` |
| `N2-shard-0.jsonl` | `28e2d064a56321d7` |
| `N3-shard-0.jsonl` | `933cb7f7c3742da0` |
| `N4-shard-0.jsonl` | `204b815c35416dcf` |
| `N5-shard-0.jsonl` | `fa833e3acc3c668a` |
| `N6-shard-0.jsonl` | `fc4642b8e99b64bb` |
| `O-shard-0.jsonl` | `57993d1d8a7ec240` |
| `probe-shard-0.jsonl` | `49bec91ecbded22b` |
| `N1-phases-shard-0.jsonl` | `a30e4705aa9984cd` |
| `N2-phases-shard-0.jsonl` | `77dd1f8635da4d1c` |
| `N3-phases-shard-0.jsonl` | `98811db6b3f925c1` |
| `N4-phases-shard-0.jsonl` | `0d533585de9b6701` |
| `N5-phases-shard-0.jsonl` | `4dd9ab3ad004c184` |
| `N6-phases-shard-0.jsonl` | `8943298483b36a90` |
| `O-phases-shard-0.jsonl` | `be61c8cc50cbd5ea` |
| `reading-codes.json` | `2cff54e69aecb9d8` |
| `analysis.txt` | `5baea107d71159be` |

The six blind readers' verdicts are `reading-blind-verdicts-1.json` to `-6.json`, the second reading
`reading-second-reading.json`, each arm's `-header.json` records the profile, the pins and the
effective model map. The figures come from `docs/probes/holdout2_analysis.py` (REPO CODES VERDICTS
[FINAL]): it rebuilds each delivery's cautions and confirmations from the stored phase rows with
this tree's code and stops if a rebuild does not match the shipped delivery; it matched for all 226.
The `.db` files the runs also wrote are not copied.
