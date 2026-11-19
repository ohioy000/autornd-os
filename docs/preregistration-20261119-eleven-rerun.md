# Preregistration: the eleven questions again, the harness beside a frontier model at low effort (2026-11-19)

Pushed before the spend. The owner's word, 2026-11-19: "Do 1-4 and rerun a side by side with the
11 questions could have been a bad run and use fable 5.2 low for comparison". **That is the word
to run. The amount is not yet given.** It is asked for after this file is merged, and nothing is
spent before it.

## Why

The hold-out run (`docs/reviews/2026-11-17-holdout-run.md`) had 13 harness answers not right, on 11
of the 42 questions: X3, X12, X13, X16, X19, X20, X24, X31, X34, X38, X41. The frontier model was
right on all 11 (`docs/reviews/2026-11-18-frontier-direct-holdout.md`).

The owner's reading is that this could have been a bad run. The free analysis of the saved traces
(`docs/reviews/2026-11-19-holdout-misses-classified.md`) says the data lean that way:

- The misses **scatter** and do not cluster. Questions with 0, 1, 2 and 3 not-right answers were
  31, 9, 2 and 0; independent draws at the run's own miss rate give 30.3, 10.5, 1.2 and 0.0.
- Each of the 11 questions was right in at least one of its three draws. Among the other draws of
  the 11, 2 of 22 were not right.
- A lookup that read 3 pages or fewer gave 6 not-right answers in 13 units; one that read 4 or
  more gave 7 in 113 (one-sided Fisher p = 0.0004). Most unread pages gave "no answer within
  25 s".

This run tests it with fresh draws, and sets the frontier model beside the harness at low effort
on the same footing: the same 11 questions, three draws each.

**Selection.** The 11 were chosen because the harness missed on them, so their first-run rate (20
of 33 right, 60.6 percent) is too low by selection alone. A fresh rate on these 11 is unbiased for
these 11. It says nothing about the other 31, which were all right in the first run (93 of 93) and
were chosen, by being left out, for success.

## What is run

**Arm A, the harness as shipped.** `docs/probes/short_workflows_measurement.py` with
`MEASURE_SET=professional-holdout`, `MEASURE_WORKFLOWS=answer-and-recompute`, the 11 question ids,
3 repeats, 3 shards, from a clone of main at the commit that carries this file. The harness code
is unchanged since the hold-out run: the only difference under `autornd/`, `workflows/` and
`profiles/` between the commit that run used and this one is the version string in
`autornd/main.py`. The owner's `.env` as it stands, no setting changed. The new run's `header.json`
is compared with the first run's (`docs/traces/20261117T-holdout-header.json`: the model per tier
and the provider order); any difference is stated in the report. 33 units.

**Arm B, a frontier model asked directly at low effort.** `docs/probes/frontier_direct_probe.py`
with `FRONTIER_SET=professional-holdout`, `FRONTIER_IDS` the 11 ids, `FRONTIER_EFFORT=low`,
`anthropic/claude-fable-5.2`, the provider's web search with up to 5 results, the question as the
only message, at most 8,000 tokens a call. Three passes over the 11, each to its own output file.
33 calls. **A smoke first:** X3, one call, to see that `low` is accepted and what a call costs; it
counts as pass 1's answer to X3.

The two arms run at the same time. The first run's three processes ran at the same time too.

## Money and stops

- **Arm A:** expected '$0.35' (33 units at '$0.0106', the harness's mean on these 11 last time).
  Each of the three processes starts no unit once it has spent '$0.30'. Arm limit '$1.00'.
- **Arm B:** the first run's cost an answer at medium was '$0.0986', and on these 11 '$0.153'.
  Almost all of it is search-result text read ('$0.0085' per 1,000 tokens read against '$0.043'
  per 1,000 written, from a fit to the 42 calls), so **low effort saves at most about '$0.12' a
  pass of 11.** Expected '$1.6' a pass, **about '$4.9' for the three.** The probe starts no call
  once '$5.10' is spent. One call has cost up to '$0.45', so the arm cannot pass about '$5.55'.
- **Total limit proposed: '$6.50'.** If the owner prefers two passes for arm B, the expected cost
  falls by about '$1.6'.
- **If the smoke costs more than '$0.50', or `low` is refused, or no text comes back, arm B is
  held and reported.** The amount is the owner's. Nothing is spent before it is given.

## How it is read

The rule is the hold-out run's, word for word: **an answer is right when every key item is
right.** An item that says "None" or "the document states no such figure" is right only if the
answer says so. A wrong figure beside a right one for the same key item makes the answer wrong.
A wrong claim outside the key items is recorded as `outside_wrong` and does not change the
verdict. A harness unit that ends blocked by its own checks counts as not right.

- **Blind to arm and draw.** Every delivered answer of both arms (up to 66) goes under a code, in
  a shuffled order, to three blind Sonnet readers with the signed keys and this rule. They are not
  shown the first run's verdicts.
- **Two readers (D50).** The executor reads every answer the readers do not mark right, every
  answer where the readers and the free screen disagree, and a random 12 of the right ones, and
  searches the whole of each for each key item. The scorer is a screen, not the result.
- **Measured beside the verdicts:** for the harness, pages read and not read by reason for every
  lookup, with the not-right rate for a lookup that read 3 or fewer against 4 or more, rebuilt by
  `docs/probes/holdout_miss_classification.py`'s method; for both arms, cost, seconds, and
  whether an answer says a figure is unconfirmed.

## The bars

1. **Was it a bad run?** The harness is right on **at least 27 of its 33** fresh answers to the 11
   questions (82 percent). At the harness's overall rate (89.7 percent) a fresh 33 has 27 or more
   right 95 times in 100. If the 11 were as hard as the first run made them look (60.6 percent) it
   has 27 or more right 8 times in 1,000.
   - **27 or more:** the first run's misses on these questions were mostly draws. The 89.7 percent
     stays the best figure for the harness's per-answer rate.
   - **24 to 26:** partly noise, partly these questions. Reported as it reads.
   - **23 or fewer:** these questions are hard for the harness, and the misses are not draws.
2. **Low effort holds up.** The frontier model at low effort is right on **at least 30 of 33**
   (91 percent). At medium it was right on 11 of 11. Met: effort low does not cost accuracy here.
   Missed: the cheaper setting is not equal, and the report says by how much.
3. **Within five points, as before.** The harness's right rate on the 33 is within five percentage
   points of the frontier model's right rate on its 33. This is the 2026-11-18 bar, applied to
   fresh draws.
4. **Cost.** The harness's cost an answer is no more than a quarter of the frontier model's.

## Predictions

1. The harness is right on 27 to 31 of 33. Bar 1 is met.
2. The misses scatter: no question is not-right in more than one of its three fresh draws, with
   X31 and X41 the likeliest exceptions (a stale instrument; a datasheet over the size limit).
3. At least half of the harness's not-right answers come from a lookup that read 3 pages or fewer.
4. Pages that gave no answer in time are about 0.4 a lookup, as in the first run (50 in 126), give
   or take a quarter. If the rate is under half of that, the first run's network was worse.
5. The frontier model at low effort is right on 31 to 33 of 33. Bar 2 is met.
6. Its cost an answer on these 11 is '$0.13' to '$0.17'.
7. Bar 3 is missed again, if the frontier model is right on 32 or 33 of 33 and the harness on 31
   or fewer. Bar 4 is met.

## Limits, stated beforehand

- **Eleven questions, three draws each.** The three draws of one question are not independent. A
  difference of two or three answers is noise.
- **It does not re-measure the other 31 questions.** The clean figure for the harness on all 42 is
  a fresh run of all 42 (about '$1.4' for the harness alone). This run does not give it.
- **Network and time of day are not controlled.** The harness's unread pages are mostly pages that
  gave no answer in 25 seconds, and that depends on the day. The rerun may differ for that reason
  alone, which is part of what it tests.
- **Authors, checkers, readers and the frontier model are of one maker,** as before.
- **One model, low effort, one search setting.** The medium-effort draw of 2026-11-18 is the only
  reference, and it is one draw a question.
- **The harness's side and the frontier side run on the same day this time,** which the first
  comparison did not.
