# The professional set's baseline: 45 of 45 right, 38 of them with a caution (2026-11-15)

Preregistered in `docs/preregistration-20261115-professional-baseline.md`, pushed before the run.
`docs/probes/professional_baseline_analysis.py . docs/traces 20261115T-professional-baseline-`
re-derives the counts that point the reading.

## The point

- **Every answer was right.** All 45 state every item of their key rightly, read by hand: 15
  questions in 15 fields, three answers each, on main as it stands.
- **The lookup found the governing sentence in 39 of 45 runs,** and the search had quoted it in
  43.
- **The delivery warned on 38 of the 45 right answers.** Only 7 came with no caution. One
  caution said the recompute vote disagreed with the answer; the answer was right and the vote's
  samples were wrong.
- **So on clear professional questions the harness's problem is no longer wrong answers. It is
  warnings that do not tell a right answer from a wrong one.**
- **Cost:** '$0.568' against '$0.90' expected, about '$0.013' an answer, 66 seconds each on
  average. About '$5.42' of the owner's '$7' is now spent.

## What was run

- The professional set, version professional-1, sha256 `2e41878c1e06…`, three answers a
  question, through `answer-and-recompute`. Main `53cbfae` with the set's runner entry; site
  flagging on. The owner's `.env` of the date.
- **Traces,** copied byte-identical: `docs/traces/20261115T-professional-baseline-*`, the answers
  (`shard-0` `dd1ce9d82da9…`, `shard-1` `b4e30b970608…`, `shard-2` `98abb03a80d6…`), the exported
  run rows and the header.

## The reading

One reader, the architect, read every answer's statement of every key item. D50 asks for two
readers; a stated departure.

| | Result |
|---|---|
| Answers stating every key item rightly | 45 of 45 |
| Lookup found the governing sentence on its page | 39 of 45 |
| Search quoted it at all | 43 of 45 |
| Quotes found on their pages | 73 of 92 |
| Quotes on pages not read | 8: 4 challenge pages on ecfr.gov, 2 osha.gov, 2 missing pages |
| Quotes read and not matched | 11 |

One blemish in a right answer: P4, third answer, gives the right periods and then "corrects" the
question's citation to a paragraph the current rule does not use. The figures are right; the
aside is wrong.

No answer drew on an older edition: P11 gave 0.070 ppm and P14 gave 15 characters every time.

## The cautions

| Caution | Times | True of a wrong answer? |
|---|---|---|
| The vote compared nothing | 10 | No answer was wrong |
| The vote reached no majority on an ask | 8 | No |
| The vote worded an ask differently | 8 | No |
| The vote could not compare an ask | 2 | No |
| The vote disagrees with this answer | 1 | **No. The answer was right** |
| Some quoted passages not found; the rest unverified | 10 | No |
| Quoted passages on a page that could not be read | 8 | No |
| A found passage does not state an answer to its question | 10 | No |

- **The one disagreement** is P6, third answer: 15 rems for the lens of the eye, which is the
  rule. Two of the three blind samples said 2 rems. Samples agreeing on a wrong value has now
  been seen four times in two days.
- **29 of the 57 cautions are the vote saying it could not do its work.** These answers are
  mostly prose with figures inside, and the vote compares typed values.
- **The quote cautions are true but not about the answer.** In most of those runs another quote
  of the same sentence was found.

## The predictions

| | Stated | Result |
|---|---|---|
| 1 | at least 40 of 45 right | **Held.** 45 |
| 2 | a wrong answer's lookup missed the sentence | **Not tested.** No answer was wrong |
| 3 | the lookup finds the sentence in at least 35 of 45 | **Held.** 39 |
| 4 | P8 ends with no quote found at most once | **Held.** Never; eCFR's copy was found all three times |
| 5 | the vote compares nothing on at least 5 questions | **Held.** 7 questions, 10 answers |
| 6 | P11 or P14 draws on an older edition | **Wrong.** Never |

## Why the 11 unmatched quotes were not matched

Read one by one: a subscript written with tildes ("O~3~"), a numbered-list mark before the
sentence ("1.", "1\."), a bullet star, a heading line followed by a paragraph that does not
follow it on the page, two grids from pages that print them differently, and three passages
stitched from separate paragraphs. The first three are the search model's own marks, the same
kind as the stars and hashes dropped on 2026-11-14.

## The next core problem, as the architect sees it

**A warning on 38 of 45 right answers teaches the reader to ignore warnings.** That is worse in
professional use than an occasional wrong answer with a warning on it, because the warning is
the only thing that tells the two apart.

Three things would move it, in the architect's order. None is built; each changes what the
delivery says, so each is the owner's ruling.

1. **Say what was verified, not only what was not.** When a figure in the answer stands in a
   passage found on its page, the delivery can say so, and the vote's "compared nothing" for
   that figure adds nothing. On this baseline that is the case in at least 39 of 45 answers. It
   is free code and can be proven on these 45 recorded answers before it ships.
2. **Do not let a vote overrule a found passage.** The P6 false alarm is two samples from memory
   against a sentence found on the regulator's page. A found passage should outrank the vote.
   Also provable on the record.
3. **Drop three more of the model's marks in the quote check:** the subscript tildes, a list mark
   at the start, and a backslash before a full stop. About 4 of the 11 unmatched quotes.

**What this baseline cannot say:** how the harness does on questions it gets wrong, because it
got none wrong. The set is easy for it: each question names its rule. Harder professional
questions, where the rule is not named or the answer is a table or sits in a PDF, are the next
set worth writing.
