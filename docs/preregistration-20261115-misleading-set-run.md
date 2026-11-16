# Preregistration: both lookups on the questions where a summary misleads (2026-11-15)

Written and pushed before the run. The owner's word of 2026-11-15: the 12 keys are signed, the
run is option C of `docs/reviews/2026-11-15-professional-misleading-draft.md`, and the vote's
"compared nothing" caution is said only when nothing else checked the answer.

## What is run

`evals/professional/misleading-questions.json`, version professional-misleading-1, sha256
`684dd75053dab14e…`, approved and frozen. 12 questions, 12 answers each, through the default
workflow (`answer-and-recompute`), in three arms:

| Arm | Settings | What it is |
|---|---|---|
| `now` | `LOOKUP_READS_DOCUMENTS=false` | the lookup that asks a search model for an answer and its quotes |
| `documents` | `LOOKUP_READS_DOCUMENTS=true` | the shipped default: the harness reads the documents |
| `again` | the same, and `LOOKUP_DOCUMENTS_ASK_AGAIN=true` | step 3: a second request for documents on a miss |

432 answers. Everything else is the owner's `.env` of the date and main as merged with this
file.

**Order.** Each arm is two processes. The first process of every arm runs at the same time, then
the second of every arm: three at once, so the arms see the same hours and the same sites, and
no more than three processes fetch from one site.

**Cost.** About '$5.60' expected, the amount the owner approved. Each process stops starting
answers once its own spend reaches its stop: '$0.98' for each `now` process, '$0.83' for each
`documents` process, '$0.93' for each `again` process, '$5.48' in all. A process can pass its
stop by the one answer it is in, about '$0.02'. About '$8.96' is spent before it.

**If the network drops,** blocked answers at no cost are counted as not made, and are made again
inside the same stops. Every completed answer is counted.

## The bars

Answers are read by hand against the keys. An answer is right when every key item is right.

1. **The lookup that reads the documents is right more often:** `documents` is right in at
   least 10 more of 144 answers than `now`.
2. **It harms no question:** on no question is `documents` right in fewer than `now` by more
   than 2 of 12.
3. **No wrong answer carries a "verified" line,** in any arm.
4. **The cautions point:** of the wrong answers of `documents`, at least half carry a caution
   that points at the wrong part (two pages differ, a figure on no page, or the vote
   disagrees); and at least half of its right answers carry no caution.
5. **The second request earns its call:** `again` is right in at least 4 more of 144 answers
   than `documents`, at no more than 15 percent more an answer.

- Bars 1 and 2 met: the default of step 2 stands on a set built to separate the two lookups.
- Bar 1 missed with 2 met: the lookups are not told apart by this set either, and the default
  stands on cost and on quotes found.
- Bar 2 missed: the default is put back to the owner.
- Bar 3 missed: the "verified" line is taken out until it is repaired.
- Bar 5 met: the architect advises switching the second request on. Missed: it stays off.

Read free off the record, whatever the bars say: how often the first request for documents was a
miss in `documents` and in `again`, and which kind (no page read, or no page holding its
pointer).

## Predictions

1. `now` is right in 95 to 115 of 144; `documents` in 115 to 135. Bar 1 is met.
2. Bar 2 is met.
3. Bar 3 is met.
4. Bar 4 is missed on its first half: most wrong answers were handed only the misleading page,
   and nothing in the text handed on shows that.
5. Bar 5 is missed: the second request fires in fewer than one lookup in ten, and `again` is
   within 3 answers of `documents`.
6. M5 (Part 135 rest) and M1 (BasicMed) are the questions most often wrong in `now`.
7. M9 and M10, where last year's and next year's figures stand on the same page, are right at
   least 10 times of 12 in every arm.

## Limits, stated beforehand

- **One reader.** D50 asks for two; a stated departure.
- **12 answers a side is the least the plan allows.** A difference of 2 of 12 on one question is
  inside what one question does from run to run.
- **The set is the architect's own.** It was written to mislead a summary. It says how the
  lookups differ on such questions, not how often such questions are asked.
