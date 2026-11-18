# The hold-out run, 2026-11-17

The run asked the question the earlier ones could not: on 42 questions written after the harness
was fixed, by authors that never saw its answers, how often is it right, and does its delivery
still tell the truth about its own answers? It was preregistered before the spend
(`docs/preregistration-20261117-holdout-run.md`). The owner signed the 42 keys and approved a limit
of '$2'.

## The point

- **113 of the 126 answers made are right on the key** (89.7 percent; 113 of the 122 delivered,
  92.6 percent). On the stricter reading, where a wrong claim outside the key counts, 97.
- **A confirmation stood beside a wrong figure once.** Bar 2 is missed. The preregistration says
  the release is held and the case goes to the owner. It is in "What it says for the release".
- **A wrong answer was rarely marked.** Of nine, three carried a caution that pointed at the wrong
  part. Bar 4 is missed again, as predicted.
- **The other five bars are met:** right at least 100 of 126, right answers coming clean, cost,
  the 429 retry, and no group under 70 percent.
- **'$1.355' for the run, '$0.0108' an answer, 107 seconds an answer.**

## What was run

Main at `2213945`, the default workflow (`answer-and-recompute`), the owner's `.env` as it stands,
no setting changed. The hold-out set, `evals/professional/holdout-questions.json`, version
professional-holdout-1 (sha256 `c5d4a9dad66e` first 12 characters), 42 questions, three answers
each, 126 units, in three processes started together from a clone of main. The runner is
`docs/probes/short_workflows_measurement.py` with `MEASURE_SET=professional-holdout`. The
delivery of each answer comes from `_detail`, the API's own builder. The confirmation is not
recorded by the runner, so `docs/probes/acceptance_run_analysis.py` rebuilt it from the stored
phase rows; the script stops if the rebuilt cautions differ from the recorded ones, and they
matched for all 122 delivered answers.

Four units ended blocked by the harness's own checks, and no answer was delivered for them. None
was a 429.

| Question | Why blocked | Cost |
|---|---|---|
| X3 | the answer was cut off: it ended on the word "of" | '$0.0085' |
| X24 | the answer was cut off: it ended inside open inline maths | '$0.0083' |
| X31 | the implementation named an ask it could not satisfy (the power spectral density limit) | '$0.0097' |
| X41 | the implementation named an ask it could not satisfy (a thermal resistance the datasheet does not give) | '$0.0106' |

They count as not right in the first figure above. The preregistration's rule to make blocked
answers again was for answers blocked at no cost by the network; these cost money and are the
harness's own judgment, so none was made again. **X41 is a trap whose right answer is "the
datasheet states none"; the harness blocked rather than say so.**

## The bars

| Bar | Result | |
|---|---|---|
| 1. At least 100 of 126 right | **113** (97 on the stricter reading) | Met on the key; not met on the stricter reading |
| 2. No confirmation beside a wrong figure | **1** (X31), and one more arguable (X34) | **Missed** |
| 3. At least half the right answers carry no caution | **80 of 113** (71 percent) | Met |
| 4. At least half the wrong answers carry a caution that points | **3 of 9** | **Missed** |
| 5. An answer at most '$0.015', the run within '$2' | **'$0.0108'**, '$1.355' | Met |
| 6. At most 2 blocked on a 429 after five attempts | **0** | Met |
| 7. Each group right in at least 70 percent | 95.1, 92.7 and 90.0 percent of delivered | Met |

| Group | Questions | Right of delivered | Right of made |
|---|---|---|---|
| EU and international law and standards | X1 to X14 | 39 of 41 | 39 of 42 |
| Software, security and internet standards | X15 to X28 | 38 of 41 | 38 of 42 |
| Physical engineering, units, datasheets and national rules | X29 to X42 | 36 of 40 | 36 of 42 |

| Cut | Answers made | Delivered | Right |
|---|---|---|---|
| All 42 questions | 126 | 122 | **113** |
| The 26 the harness's own fetch can read (listed in the preregistration) | 78 | 77 | **74** (94.9 percent of made) |
| The 16 it cannot read | 48 | 45 | **39** (81.3 percent of made) |
| The 5 trap questions (X13, X16, X19, X36, X41) | 15 | 14 | **10** |
| The other 37 | 111 | 108 | **103** |

The harness does worse where it cannot read the cited page, and worse on traps. Neither gap is
large enough to rest much on with 42 questions.

**The stricter reading.** The preregistration says an answer is right when every key item is
right, and also that "a wrong figure beside a right one makes the answer wrong". The second
sentence is ambiguous. I read it as: two different figures given for one key item, with no
saying which is the answer. A wrong claim outside the key items is noted and does not change the
verdict, as in the acceptance run. The blind readers recorded 16 of the 113 right answers as
carrying a wrong claim outside the key. If those count, 97 of 126 are right. **That figure is the
blind readers' marks and I did not read those 16 claims again.**

## How it was read

Two readers (D50). Three blind readers (Sonnet) read the 42 packets, 122 answers, under codes
that hide the run. They were given the preregistration's rule word for word and the verdicts
`right` and `wrong` only. They marked 113 right and 9 wrong.

The executor read every answer the blind readers did not mark right (9) and 24 marked right: the
12 the script drew at random and the 12 where the free figure check and the blind reader
disagreed on a right answer. **All 33 agree with the blind readers.** I read the start of 12 of
the 24, and for all 24 I searched the whole answer for each key item's figure or phrase; the
search found every item.

I made one error and caught it. My first display of each answer stopped at the first horizontal
rule inside it, so I had read part of some answers. One answer looked as if it gave no reason; the
whole answer gives it. I fixed the display and read all nine wrong answers again over their whole
text. All nine stay wrong.

Two of the nine are borderline, and I say so: X16 (a reason taken from the Understanding
document rather than the Recommendation's own note) and X34 ("more than 18 m" where the key says
"18 m or more", with the answer itself saying the comparator is unconfirmed). One more is a fault
in the key's design: X13's key asks where the 250-person figure stands (Article 30(5)), which the
question does not ask. The same fault was found and removed from six other keys before signing.
By the rule it is wrong, and it is counted wrong.

| Question | What is wrong |
|---|---|
| X12 | The transport index given as 8.0 and the limit as 10; the key is 16 and 50. A caution said the figure 8 is on no page |
| X13 | Right that the GDPR sets no headcount threshold; does not say where the 250 figure stands |
| X16 | Right that 4.1.1 is removed; the reason given is not the one the Recommendation gives |
| X19 | Right that every value is organization-defined; says part b is a mandatory automatic lock, where it is a choice of actions |
| X20 | 17 and 14 families right; says Revision 2 is "Superseded, not Withdrawn" and that the PDF carries no banner; the PDF cover says withdrawn |
| X31 | 4 W and 25 mW per 3 kHz right; names the 2015 licence as the one in force, where the 2025 licence is |
| X34 | 11 m and 30 m right, date right; "more than 18 m" for the second stair, where the key is "18 m or more" |
| X38 | 2 seconds and 3.5 ft/s right; the 2009 buffer interval left "NOT ANSWERED" |
| X41 | Gives 45 degC/W and 150 degC; the datasheet states neither. Two cautions said the figures are on no page |

## What the delivery said

71 answers carried a confirmation, and 36 carried a caution. 28 of the 113 right answers
carried a pointing caution, mostly because an older edition of the rule stood among the pages
found.

**Confirmations on wrong answers.** Three of the nine carried one:

- **X31, the clear case.** The confirmation reads "The figures this answer gives for ask 2, 3
  stand in a passage found on its page." Ask 3 is the year, and the answer gave 2015. The 2015
  licence page is still served and carries that year, so the line is true and the tick stands
  beside a wrong figure. This is the known limit that a stale official page that looks current is
  not caught (item 4 of the release notes), now with a tick beside it.
- **X34.** The figures 11, 30 and 18 are each on the page and each is right. The wrong part is
  the word "more than". A confirmation of figures cannot see a comparator. I count this
  arguable, not a miss.
- **X38.** The confirmation covers ask 2, 3.5 ft/s, which is right. The wrong part is the ask
  the answer left open. Not a wrong figure.

**Pointing cautions on wrong answers.** Three of the nine: X12 and X41, where the wrong figure is
on no page, and X16, where two pages differ. The other six carried none: a missing item (X13,
X19, X38), a wrongly named instrument or status with the page found still printing it (X31,
X20), and a comparator (X34). The checks read figures, not prose, so a wrong word or a missing
item gets no caution.

## Predictions

| Prediction | Result |
|---|---|
| 1. 105 to 118 of 126 right, lower than in-sample | **Held:** 113 |
| 2. Bar 2 holds | **Failed:** X31 |
| 3. Bar 4 is the one most likely to miss again | **Held:** 3 of 9 |
| 4. An answer costs '$0.009' to '$0.013' | **Held:** '$0.0108' |
| 5. 0 or 1 blocked on a 429 | **Held:** 0 |
| 6. Traps and PDF-table questions are the least often right | **Held in part:** traps 10 of 15 against 103 of 111; the 16 the fetch cannot read 39 of 48 against 74 of 78 |

## What it says for the release

- **The figure for new questions is 113 of 126, about 90 percent, and 97 of 126 on the stricter
  reading.** It is lower than the 98 percent on the sets the harness was shaped against, as it
  should be. The release notes carry both.
- **Bar 2 is missed.** The preregistration, written before the spend, says: "Bar 2 missed: the
  release is held and the case goes to the owner." The release is held. No tag is made and no
  version is named until the owner decides.
- **What the miss is.** One answer in 122 put a tick beside a year taken from a superseded
  instrument whose page is still served. In the acceptance run no confirmation stood beside a
  wrong figure in 259 right and 5 wrong answers. The two results together say a confirmation
  beside a wrong figure is rare, and not absent.
- **What a fix would be.** It is not mine to make: any change that withholds or changes a
  confirmation alters what the harness concludes and needs a ruling. The owner can choose to
  release with the limit stated, to hold for a ruling on a guard, or to treat the line as not
  covering a year or a name.
- **The 429 retry held:** none of 126 units ended blocked on a rate limit.

## Limits

- 42 questions and three answers each. The answers to one question are not independent draws. A
  figure of 90 percent has a wide margin either side of it.
- The questions and keys were written and checked by language models, then signed by the owner.
  The checkers found ten faults and all were fixed before signing; a fault they did not see
  would count against the harness. X13's key had one of the kind they found in six others (an
  item the question does not ask), and they passed it.
- Two readers, one the executor who ran it. A second human reading is the owner's to ask for.
- Live sites change. A rerun on another day can differ.
- The run was made from a clone of main with the owner's settings passed as environment variables.

## Traces

Copied byte-identical from `evals/results/20261117T-holdout/` into `docs/traces/`, cited by sha256
(first 12 characters). The `phases-` files are the rows of each shard's database, exported by
`docs/probes/export_shard_db.py`. The readers' codes were kept from them; the blind verdicts and
my second reading are the last four.

| File | sha256 |
|---|---|
| `20261117T-holdout-header.json` | 750343b8bd40 |
| `20261117T-holdout-shard-0.jsonl` | c4004666a5e1 |
| `20261117T-holdout-shard-1.jsonl` | 4687581cae5b |
| `20261117T-holdout-shard-2.jsonl` | 0c0d7703f522 |
| `20261117T-holdout-phases-shard-0.jsonl` | c8fc09e48ae9 |
| `20261117T-holdout-phases-shard-1.jsonl` | bc9d527c1564 |
| `20261117T-holdout-phases-shard-2.jsonl` | c800ee61fdb7 |
| `20261117T-holdout-reading-codes.json` | 6d6d25e31dcd |
| `20261117T-holdout-reading-blind-verdicts-1.json` | 5e2c9c78cf5b |
| `20261117T-holdout-reading-blind-verdicts-2.json` | 2217434b8f11 |
| `20261117T-holdout-reading-blind-verdicts-3.json` | c7d5fad46aa0 |
| `20261117T-holdout-reading-second-reading.json` | 2dc16f375351 |

To rebuild the figures: copy the shards and phases files back to
`evals/results/20261117T-holdout/` and run

    python -I docs/probes/acceptance_run_analysis.py . docs/traces/20261117T-holdout-reading-codes.json \
        "docs/traces/20261117T-holdout-reading-blind-verdicts-*.json"
