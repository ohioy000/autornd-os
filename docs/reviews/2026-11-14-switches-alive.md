# The alive check of the two new live switches (2026-11-14)

Preregistered in `docs/preregistration-20261114-switches-alive.md`, pushed before the run. The
figures re-derive from the traces with `docs/probes/switches_alive_analysis.py`.

## The point

- **Both switches are alive.** On a real paid run, each one changed the delivery the way #249 says,
  and only the delivery.
- **`same_meaning` cleared 5 vote flags,** in 2 Q7 and 3 Q12 units. Each vote ends `flagged: false`
  with `flagged_by_vote: true`, and a caution says the ask was worded differently. The stored vote
  rows still say what the vote found.
- **`quote_answers` labelled 9 quotes** as not answering their question, in 7 of the 8 units, each
  with a caution that counts them. The one unsure answer and the one confident yes labelled nothing.
- **Every label matches its decision record:** 0 mismatches over 8 units.
- **All 8 answers are right,** and every label is right on the reading.
- **Cost:** '$0.170' for 8 units, against '$0.17' expected. The decision calls were '$0.00075' of
  it. About '$1.82' of the owner's '$7' is now spent.

## What was run

- Tier-2 Q7 (noise table) and Q12 (water limits), four repeats each, 8 units.
- Workflow `answer-and-recompute`, 4 shards with a '$0.06' stop each. Each unit on its own empty
  knowledge store. No unit failed, was blocked or left a liability.
- **Code:** main at `4055983`, with the owner's `.env` of the date. Preflight 34 ok, 0 failing.
  Suite before the run: 1930 passed, 1 skipped, network guard 0. Started 16:29 UTC.
- **Traces,** copied byte-identical, prefix `docs/traces/20261114T162951Z-switches-alive-`:

| File | sha256 |
|---|---|
| `header.json` | `663ecca5dc5b…` |
| `shard-0..3.jsonl` | `b8bef0984eca…`, `fb9b1634712c…`, `bc052e7f8786…`, `63c6b691c16f…` |
| `phases-shard-0..3.jsonl` | `3b40cbdf4215…`, `68f8e7af767a…`, `55646d034f05…`, `f1cbde31b9eb…` |

  The shard databases are git-ignored. `docs/probes/export_shard_db.py` exports their rows, one per
  line, into the phases files; each workflow line cites its database's sha256. Run again on the
  databases, it gives the committed files byte for byte.

## Unit by unit

| Unit | Cost | `same_meaning` | Vote after | `quote_answers` | Labelled |
|---|---|---|---|---|---|
| Q7 r1 | '$0.0262' | not asked | not flagged | 3 no | 3 |
| Q7 r2 | '$0.0196' | yes on ask 1 | cleared | 1 no | 1 |
| Q7 r3 | '$0.0116' | yes on ask 1 | cleared | 1 no, 1 unsure | 1 |
| Q7 r4 | '$0.0197' | not asked | not flagged | 1 no, 1 yes | 1 |
| Q12 r1 | '$0.0270' | yes on ask 3 | cleared | 1 no | 1 |
| Q12 r2 | '$0.0225' | yes on ask 3 | cleared | 1 no | 1 |
| Q12 r3 | '$0.0217' | not asked | not flagged | 1 no | 1 |
| Q12 r4 | '$0.0220' | yes on ask 3 | cleared | none found | 0 |

"Not asked" means the vote flagged nothing, so there was nothing to clear.

## The reading

One reader, the architect, read every answer, every cleared pair and every labelled quote. D50 asks
for two readers; this is a stated departure.

**The answers.** All 8 are right. Q7: 8, 4 and 2 hours. Q12: 0.010, 4.0 and 10 mg/L, nitrate as
nitrogen. The tier-2 screen (version .4) passed all 8 as well, and it is a screen, not the result.

**The 5 cleared pairs.** Each one says the same thing in other words:

- Q7 r2 and r3, ask 1: "90 dBA: 8 hours; 95 dBA: 4 hours; 100 dBA: 2 hours" against the samples'
  "8, 4, 2" hours. Yes at 0.970 and 0.965.
- Q12 r1, r2 and r4, ask 3: "as Nitrogen (as N)" against "as Nitrogen". Yes at 0.992, 0.994 and
  0.992.

The decision model was shown the samples' own words. The vote's record holds them squashed into an
identifier ("842", "ASNITROGEN").

**The 9 labelled quotes.** None of them states what its question asks:

- 4 were asked the request's own question (the three durations). Their passages are the noise rule's
  opening line (twice), the table's title alone, and its column headings ending at "8 ....." with no
  level beside it.
- 2 were asked for the figures themselves (Q7 r2, Q12 r2). Their passages are the noise rule's
  opening line and the line saying which systems the limits apply to.
- 3 were asked about the request rather than the subject: which edition is the one to retrieve,
  whether a limit was amended after 2014, and the exact text of the 2014 edition. Their passages
  are the opening line, a monitoring rule for nitrate and the section's title.

**The two quotes left unlabelled.** Both are the table itself, rows 8–90 to 2–100. Asked the
durations question in Q7 r4, it was a confident yes (0.990). Asked in Q7 r3 whether the 2014
edition is the source to retrieve, it was unsure (0.539) and kept unlabelled, the safe side.

## What counts as alive, item by item

1. **`same_meaning`: alive.** In all 5 units it was asked, `cleared` held exactly the asks with a
   confident yes. With nothing left, `flagged` was false, `flagged_by_vote` true, no caution said
   the vote disagrees, and the stored vote row still said `flagged: true` and carried no `cleared`.
2. **`quote_answers`: alive.** In all 8 units, the quotes with `answers_question: false` were
   exactly the found quotes with a confident no, and the caution gave that count ("3 of the 3
   passages found in their pages do not state an answer…"). The unsure answer labelled nothing.
3. **Labels only: held.** All 8 units ran the same 12 phases in the same order and ended completed.
   Nothing was blocked, routed or revised on either switch.
4. Both switches gave confident answers, so neither falls under item 4.

**The probe can fail.** `switches_alive_analysis.py` was run against `autornd/api/routes.py` with
each of its label lines broken in turn: with the quote label removed it reports 7 mismatches, with
nothing cleared 5, and with `flagged` kept true 10. Restored, it reports 0.

## The predictions

| # | Prediction | Result |
|---|---|---|
| 1 | At least one Q7 unit labels a quote | **Held.** All 4 did. |
| 2 | At least three Q12 units clear a flag, vote ends unflagged | **Held.** 3 of 4; Q12 r3 was not flagged. |
| 3 | Every label matches its record | **Held.** 0 mismatches. |
| 4 | All 8 answers right | **Held.** |
| 5 | Decision calls under '$0.001' in all | **Held.** '$0.00075' for 24 calls. |

## Other things seen

- **Q12's lookups found quotes this time:** 3 of its 4 units found one (last run: 0 of 4). None of
  the found passages states a limit, so every one was labelled.
- **In 5 of the 8 deliveries, every found passage was labelled.** The answers were right from the
  model's own knowledge, and the cautions now say the quotes do not back them. That is the label
  doing its job. It also shows that a found quote is weak evidence by itself.
- **3 of the 9 labels came from grounding questions about the request,** such as which edition to
  retrieve. No passage can answer those. The pattern is the same as in the lookup runs (7 of 10).

## What is next

The alive check closes item 1 of the carryover (`docs/carryover-2026-11-14.md`). The main open
problem is item 2: errors in an answer's prose that the vote cannot see. Its two candidates there
(more of the answer stated as typed results, or each claim checked against a found quote) each
change what the harness concludes, so the choice is the owner's.
