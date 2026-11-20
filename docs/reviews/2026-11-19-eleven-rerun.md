# The eleven questions again, the harness beside a frontier model at low effort, 2026-11-19

Preregistered in `docs/preregistration-20261119-eleven-rerun.md` with two addenda, all merged before
the spend (#305, #306, #307). The owner's amount was '$4.50' in all. **'$3.0122' was spent**
('$0.2898' the harness, '$2.7224' the frontier model). The traces are in
`docs/traces/20261119T-eleven-rerun-*`; the figures rebuild with

    python -I docs/probes/eleven_rerun_analysis.py "docs/traces/20261119T-eleven-rerun-shard-*.jsonl" \
        "docs/traces/20261119T-eleven-rerun-frontier-pass*.jsonl" \
        docs/traces/20261119T-eleven-rerun-reading-codes.json \
        "docs/traces/20261119T-eleven-rerun-reading-blind-verdicts-*.json" \
        docs/traces/20261119T-eleven-rerun-reading-second-reading.json
    python -I docs/probes/eleven_rerun_pages.py docs/traces/20261119T-eleven-rerun- \
        docs/traces/20261119T-eleven-rerun-reading-codes.json \
        "docs/traces/20261119T-eleven-rerun-reading-blind-verdicts-*.json" \
        docs/traces/20261119T-eleven-rerun-reading-second-reading.json

## A deviation first: 11 of the 66 draws were never made

I ran the two arms at the same time, as the preregistration says. The account held only about
'$1.5' of credit, and the provider counts the worst case of every call in flight against the
balance. It refused calls with a 402 ("would exceed your credit"). **5 of the 33 harness units and
6 of the 33 frontier calls never made an answer:** harness X38 draw 2, X12, X19, X31 and X41 draw 3;
frontier pass 2 for X20, X24, X31, X34 and X41, and pass 3 for X38. They cost nothing.

The preregistration did not say what to do with them. **My rule, stated after the fact and not
preregistered: a draw that was refused is not a draw. It is listed and left out of "made".** The
bars are read on the answers made, as addendum 1 has it for the frontier arm. A unit blocked by the
harness's own checks counts as made and not right (X41 draw 2).

The five missing harness draws are not a random five. They are the last units of one shard, and
three are on X12, X31 and X41, the questions that were already failing. That matters for bar 1.

## The point

- **The harness was right on 24 of the 28 answers it made (85.7 percent).** On these 11 questions
  the first run had 20 of 33 (60.6 percent). **Bar 1 (82 percent) is met on the rate.** But the
  bar was written as a count, 27 of 33, and the count cannot be read. If the five missing draws
  came out at the rates their questions have shown across both runs, about 3 of 5 would be right
  and the count would land on 27, the bar's line; the chance it reaches 27 is about 6 in 10 (and
  those rates include the first run, which is biased low by selection). **So "met" is on the rate,
  and thinly.**
- **The first run's misses were mostly draws, with three exceptions.** On 8 of the 11 questions
  (X3, X13, X16, X19, X20, X24, X34, X38) the first run had 8 not-right answers in 24 and this run
  had 0 in 22. On **X12, X31 and X41 the misses repeat: 3 not-right of 5 made draws each**, over
  both runs. The 2026-11-19 report said there was no sign some questions are the hard ones.
  **That was too strong: three of them are, for this harness.**
  - X12: the Table 7 factor. The two draws were wrong in different ways (TI 8, no factor; TI 80,
    a factor of 10 and the wrong limit). Its first-run miss was TI 8 too.
  - X31: the 2015 licence named as the one in force (year 2015), the stale-instrument miss the
    preregistration named. The other four draws gave 2025.
  - X41: the datasheet states no figure; the harness blocks instead of saying "none stated" (known
    limit 12). It was right once and blocked twice in the five made draws.
- **The frontier model at low effort was right on all 27 answers made.** Bar 2 is met. Low effort
  did not cost accuracy here.
- **Bar 3 is missed again:** the frontier model is 14.3 points ahead on rate (100 against 85.7).
- **Bar 4 is met: the harness costs about a tenth of an answer ('$0.0103' against '$0.1008').** It
  is also about ten times slower (107 seconds against 10.5).
- **Low effort is cheaper than medium: '$0.1008' an answer on these 11, against '$0.153' at
  medium on the same 11.**

## Side by side

R right, W wrong, B blocked by the harness's own checks, - not made (a refused call).

| Question | Harness first run (3 draws) | Harness now, draws 1 2 3 | Frontier low, passes 1 2 3 |
|---|---|---|---|
| X3 | 2 right | R R R | R R R |
| X12 | 2 right | W W - | R R R |
| X13 | 2 right | R R R | R R R |
| X16 | 2 right | R R R | R R R |
| X19 | 2 right | R R - | R R R |
| X20 | 2 right | R R R | R - R |
| X24 | 2 right | R R R | R - R |
| X31 | 1 right | R W - | R - R |
| X34 | 2 right | R R R | R - R |
| X38 | 2 right | R - R | R R - |
| X41 | 1 right | R B - | R - R |
| **Right of made** | **20 of 33** | **24 of 28** | **27 of 27** |

Questions not right in 0, 1, 2, 3 of their draws made: 8, 2, 1, 0 (X31 and X41 once, X12 twice).

## The bars and predictions

| | Preregistered | Result |
|---|---|---|
| Bar 1 | harness right on at least 27 of 33 (82%) | **Met on rate:** 24 of 28, 85.7%. The count of 33 is not known (see above) |
| Bar 2 | frontier at low effort right on at least 30 of 33 (91%) | **Met:** 27 of 27 made |
| Bar 3 | harness within 5 points of the frontier | **Missed:** 14.3 points behind |
| Bar 4 | harness cost at most a quarter of the frontier's | **Met:** 0.103 |
| P1 | harness right on 27 to 31 of 33 | Not decidable on a count; 85.7% of 28 sits in that band |
| P2 | no question not right in more than one fresh draw | **Failed:** X12 was not right in both made draws |
| P3 | at least half the not-right answers from a lookup that read 3 pages or fewer | **Met, exactly:** 2 of 4 |
| P4 | pages with no answer in time about 0.4 a lookup, give or take a quarter | **Failed:** 24 in 28 lookups, 0.86 a lookup, twice the first run's 0.40 |
| P5 | frontier right on 31 to 33 of 33 | 27 of 27 made; 6 draws missing |
| P6 | frontier cost '$0.13' to '$0.17' an answer | **Failed:** '$0.1008' (the bound in the preregistration was wrong, addendum 2) |
| P7 | bar 3 missed, bar 4 met | **Held** |

## How it was read

Three blind readers (answers under codes, shuffled, arm and draw hidden) with the signed keys and
the hold-out run's rule. They read the 54 delivered answers in three groups (22, 16 and 16): 20 right and 2 wrong, 16 right,
and 15 right and 1 wrong. **The executor's second reading (D50) read 30 of the 54 in full:** every answer
not marked right (3), every `outside_wrong` (6), the three X41 answers, the other X12 and X31
answers, and a random 12 of the rest (seed 20261119). **No verdict differs from the blind
readers'.** The three wrong answers are X12 draw 1, X12 draw 2 and X31 draw 2, all harness.

Close calls, kept as counted: X24 draw 3 (harness) carries an HA caveat that is wrong and against
its own script ("a 1.24 kubelet becomes IN"), outside the question's fixed apiserver; X16 draw 3
gives the reason from the FAQ and the errata text, a weaker quote of the key's reason but the same
point. A stricter reader might mark those two differently. The two X12 wrongs and the X31 wrong
are not close.

## What the lookups read (harness)

- **Pages read and a miss:** a lookup that read 3 pages or fewer: 6 units, 2 not right. 4 or more:
  22 units, 2 not right (9%). One-sided Fisher p = 0.19. The first run gave p = 0.0004 on 126
  units. **The direction holds, the sample is too small to confirm it.** Mean pages read: right
  4.7, not right 2.8.
- **Timeouts:** 24 pages gave no answer in time in 28 lookups, 0.86 a lookup; the first run had
  50 in 126, 0.40. **The rerun's network (or three processes fetching at once, as before) was
  worse, and the harness still got 85.7%.** The first run's timeouts do not look like a one-off;
  neither is the size of the effect pinned down.
- Other unread pages: HTTP 202 (5), over the size limit (4), 403 (4), 404 (4).

## What the answers say about themselves

Among the 30 answers I read in full, **10 of 13 frontier answers and 3 of 17 harness answers say
a figure is unconfirmed, from memory or to be checked.** A keyword screen over all 54 gives 10 of
27 and 4 of 27, and it undercounts, as it did on the hold-out. **9 of the 27 frontier answers
carry no citation at all**; all 9 were right. At low effort the frontier model often answers from
what it remembers. It was right here, on questions with a stable answer. The harness shows what it
read, and says so when it did not read a page.

## The frontier arm

`low` was accepted on the smoke (X3, pass 1, first call). Every answer's stop reason is `stop`;
mean 7,818 prompt tokens, 800 completion tokens, 196 reasoning tokens. Pass costs: '$1.1213' (11
answers), '$0.6966' (6 answers), '$0.9046' (10 answers). Dearest per question: X31 '$0.21', X20
'$0.17', X38 '$0.165', X12 '$0.16'; cheapest X13 '$0.043'. Served by Anthropic (17), Google
(6) and Azure (4).

## What this changes

- **The 89.7 percent on the 42 stays the best per-answer figure for the harness.** This run,
  unbiased for the 11 questions, gives 85.7 percent on them, within noise of it.
- **Whether the first run was a bad run:** for 8 of the 11 questions, yes, mostly. For three
  (X12, X31, X41) no: the harness is weak on them, and for named reasons.
- **The frontier model is still ahead on accuracy,** and by a margin that three draws of 11
  questions cannot size. The harness costs about a tenth as much an answer, and is about ten times
  slower.
- **Nothing in the harness changed.** The lookup options in
  `docs/reviews/2026-11-19-holdout-misses-classified.md` stay the owner's to rule on. This run
  adds two pointers for that ruling: X41 is limit 12 (say "none stated" instead of blocking), and
  X31 is a stale instrument.

## Limits

- **Eleven questions, three draws, 11 draws not made.** A difference of two or three answers is
  noise. The missing five harness draws are the hardest ones, so the made 28 lean easy.
- **The 402 rule is mine, not preregistered.** Redoing the 11 draws would cost about '$0.65'
  ('$0.05' for the 5 harness units, about '$0.10' for each of 6 frontier calls) and must run one
  arm at a time. About '$1.49' remains under the owner's '$4.50'. **Not run: it needs the owner's
  word.** The harness runner has no way to select exact (question, repeat) units; that is a small
  change to the probe, not to the harness.
- **One model, one effort, one search setting;** authors, checkers, readers and the frontier model
  are of one maker.
- **The first run's 20 of 33 is biased low by how the 11 were chosen;** this run is not.

## Traces

All in `docs/traces/`, byte-identical copies, first 12 of sha256:

| File | sha256 |
|---|---|
| `20261119T-eleven-rerun-shard-0.jsonl` | aa6a84729a15 |
| `20261119T-eleven-rerun-shard-1.jsonl` | ce651bb4bff9 |
| `20261119T-eleven-rerun-shard-2.jsonl` | 69b760e58caf |
| `20261119T-eleven-rerun-phases-shard-0.jsonl` | fddaeaa1c200 |
| `20261119T-eleven-rerun-phases-shard-1.jsonl` | e2596ca998d3 |
| `20261119T-eleven-rerun-phases-shard-2.jsonl` | e1156f71c54e |
| `20261119T-eleven-rerun-header.json` | 9ca64987efe6 |
| `20261119T-eleven-rerun-frontier-pass1.jsonl` | a1810297a2f3 |
| `20261119T-eleven-rerun-frontier-pass2.jsonl` | 64b0b723c9bb |
| `20261119T-eleven-rerun-frontier-pass3.jsonl` | d9bb1c17ef6a |
| `20261119T-eleven-rerun-reading-codes.json` | e1a018ff960e |
| `20261119T-eleven-rerun-reading-blind-verdicts-1.json` | d0ad78a530f1 |
| `20261119T-eleven-rerun-reading-blind-verdicts-2.json` | b3828496331a |
| `20261119T-eleven-rerun-reading-blind-verdicts-3.json` | 220cf79602ca |
| `20261119T-eleven-rerun-reading-second-reading.json` | d7d9346b05f0 |

The new run's header matches the first run's (`20261117T-holdout-header.json`: the model per tier
and the provider order) in every field but the shard stop ('$0.15' here, '$0.6' there), which is a
limit, not a setting. The harness code under `autornd/`, `workflows/` and `profiles/` is the
hold-out run's apart from the version string. The shard files are named as the run wrote them; the
codes file keeps the paths of the day, and the probes join by file name.
