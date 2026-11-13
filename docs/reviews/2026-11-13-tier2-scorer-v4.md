# Tier-2 scorer version frozen-2026-10-03.4, for the owner to approve (2026-11-13)

On the owner's word of 2026-11-13, "yes to all 3". The proposal was a new scorer version that stops
failing right answers for how they are laid out. The keys stay frozen, and the owner approves the
version before it counts. It counts when its pull request is merged. Until then, main scores with
frozen-2026-10-03.3.

The figures come from `docs/probes/tier2_scorer_v4_rescore.py` and
`docs/probes/tier2_scorer_v4_breakproof.py`. Both are free and run offline.

## The point

- **37 of 40 right answers now pass.** The old scorer failed 40 answers that one reader read as
  right: all 35 of its failures in the 2026-11-13 tier-2 run, and 5 of the 9 golden Q2, Q4 and Q5
  answers. D50 asks for two readers, so one is a stated departure.
- **No answer got worse.** Across all 287 recorded tier-2 answers in `docs/traces`, no answer fails
  an item it passed before. 222 pass under .3 and 268 under .4.
- **The hand-read sheet still agrees.** All 58 entries of the 2026-10-05 tier-3 reading sheet agree
  with their resolution under both versions.
- **The keys are unchanged.** `questions.json`, `keys.json` and `verify_keys.py` are byte-identical,
  and only `scorer.py` changed.

## What it now reads

Each repair is a general rule for a layout the answers used. None is a special case for one answer.

| Form | Example from a right answer |
|---|---|
| Headings set between rules, named sections, plain title lines | `=== Section 1: Pulley Selection ===` |
| Units joined by `*` or `.` | `500 N*m`, `0.500 kN.m`, `N\cdot m` |
| A repeating decimal's ellipsis | `24.444... mA` |
| A bare `C` after a number | `120 C` |
| A ratio as `3.00:1`, or a ratio line ending at 3 | `d2/d1 = 240/80 = 3.00` |
| A verdict said beside its figure | `greater than the 22.0 mA upper limit, so 270 ohm is rejected` |
| Pass and fail words besides "pass" and "fail" | `rejected`, `satisfies`, `permitted` |
| Q4's thickness read by sentence, never the fixed width | `20.0 mm x 3.00 mm x 500 mm` |
| A numbered step is not a results heading | `10. Assess the result against the acceptance criteria. ...` |
| A compared figure is a limit, not the result | `within the 0.20 bar limit` |
| Sub-numbered and lettered steps | `2.4 Close the vent.`, `S1.`, `**P1 —` |
| The answers' own words for steps (Q20, Q25) | `adjust`, `steady`, `simultaneously`, `LOW→HIGH` |
| A truth table as rows | `0 1 \| 1`, `01 -> 1` |

## What it does not fix

Three right answers still fail: Q15 answer-and-recompute r2, Q15 verify-first r1 and Q19
verify-first r2. In each, the results-section rule links the wrong figure to the item: a reference
position, a side analysis, or the selected rating. That rule was set by Ruling R5
(ARCH-20261003-119), so changing it is a separate ruling. I tried one narrow fix: ending a figure's
context at a semicolon. It fixed one item and no answer's verdict, so I dropped it.

## Other answers that move

There are 13 older answers that nobody had read. 9 of them now pass. Each already had every number
right. Five passed only once their section headings were read, and I checked those headings by hand.
The other 4 fix some items but still fail. Three of those are Q25 answers short on substance (no HIGH
confirmed at 5 V, or no return to 0 V before shutdown). The fourth is the Q23 answer whose forces are
rounded out of tolerance. Its stresses now read 61.8 and 176 MPa instead of the 93 and 265 MPa
allowables.

One test changed with this. `tests/test_tier3_runner.py` pins the 2026-10-15 remeasure report. Under
.4, two of its five revised units, Q19 r1 and Q9 r2, score right to right instead of wrong to wrong.
They had only lost their organization item to `=== 1. ... ===` headings that .3 could not read. The
test now states both readings.

## Checks

- `verify_keys.py`: 268/268 checks pass.
- `scorer.py --self-test`: 333/333 fixtures pass. 42 are new: each form above in a right answer,
  plus a wrong answer in the same form, which fails.
- `regression_12.py`: 12/12 pass.
- `notation_sweep.py`: 52/52 model-answer variants pass, and 42/42 wrong-answer variants fail.
- `extract_candidate.py`, re-run in a copy, reproduces `manifest.json`, `questions.json` and
  `keys.json` byte for byte.
- The break-proof breaks each of the 37 new lines in turn. Each break fails the fixture written for
  it: 37 of 37.
- Suite: 1922 passed, 1 skipped, network guard 0.
