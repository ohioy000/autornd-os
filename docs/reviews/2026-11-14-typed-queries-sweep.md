# The sweep of the typed search queries: no gain shown (2026-11-14)

Preregistered in `docs/preregistration-20261114-typed-queries-sweep.md`, pushed before the run.

## The point

- **The sweep does not confirm the small test.** On vague requests the typed queries found the
  answer's passage in 9 of 10 runs, and so did the code as it is. The 8 against 4 of the last
  test was mostly chance.
- **On clear requests the typed queries did slightly worse:** 6 of 8 against 8 of 8. Both misses
  were lost after the search, not by it: one to osha.gov, one to a table quoted with rows of dots.
- **Two of the three bars were missed.** The field is not recommended as a replacement for what
  the lookup asks today.
- **All 8 full answers to the owner's request were right** on the condition that earlier answers
  got wrong, 4 in each arm. With the typed queries the passage was found on its page in 4 of 4;
  as the code is, in 2 of 4.
- **One thing does hold across all four tests:** on the owner's own request the typed queries
  found the passage in 8 of 10 lookups, the code as it is in 7 of 17.
- **Cost:** '$0.521' against '$0.63' expected. About '$3.41' of the owner's '$7' is now spent.

## What was run

- **Part 1:** the grounding step alone, two arms, five vague and four clear requests, two
  repeats: 36 runs, '$0.391'.
- **Part 2:** the owner's request through the default workflow, four answers an arm, '$0.131'.
- **Code:** this branch, which is main `7e52e35` with the quote check's mark fix, with the owner's
  `.env` of the date.
- **Traces,** copied byte-identical into `docs/traces/`:
  `20261115T-typed-queries-sweep-runs.jsonl` (sha256 `64ed2d04c7eb…`),
  `…-sweep-answers-now.jsonl` (`1fddbe075ab2…`), `…-sweep-answers-typed.jsonl` (`9dd6d20bc066…`).

## Part 1, run by run

Runs out of 2 in which a quote found on its page held the answer's sentence.

| Request | `now` | `typed_queries` |
|---|---|---|
| IA (vague, the owner's) | 2 | 1 |
| V17 (vague) | 1 | 2 |
| V22 (vague) | 2 | 2 |
| V2 (vague, new) | 2 | 2 |
| V12 (vague, new) | 2 | 2 |
| **Vague, of 10** | **9** | **9** |
| Q2 (clear) | 2 | 2 |
| Q12 (clear) | 2 | 1 |
| Q17 (clear) | 2 | 2 |
| Q22 (clear) | 2 | 1 |
| **Clear, of 8** | **8** | **6** |

## The bars and the predictions

| | Stated | Result |
|---|---|---|
| Bar 1 | on clear requests, at most 1 fewer than `now` | **Missed.** 2 fewer |
| Bar 2 | on vague requests, at least 2 more than `now` | **Missed.** The same |
| Bar 3 | field filled in 16 of 18; no section the request did not give in 8 of 10 vague runs | **Met.** 18 of 18; 9 of 10. In 2 more runs a query named a CFR part, not a section |
| Prediction 1 | bar 1 is met | **Wrong** |
| Prediction 2 | bar 2 is met, by 2 or 3 | **Wrong** |
| Prediction 3 | V12 is found in both arms | **Held.** 2 and 2; the table ruling at work |
| Prediction 4 | V17 stays the hardest | **Held for `now`** (1 of 2), not for the typed arm |
| Prediction 5 | more typed answers than `now` answers are right | **Wrong.** 4 and 4 |

## The misses, read

- **Typed, IA, run 1.** The search answered only the second and third queries, on what a holder
  may do. The eligibility section was not quoted at all.
- **Typed, Q22, run 1.** The search quoted the right sentence five times from osha.gov, which
  cannot be read, and once from a PDF whose text did not match.
- **Typed, Q12, run 2.** The search quoted the table from another site with "..." between rows.
  Words left out are not allowed, so it was not found. The one row that was found was nitrate,
  not arsenic.
- **Now, V17, run 1.** Seven quotes, all on osha.gov.

Three of the four misses are the same two leaks as before: a site that cannot be read, and a
quote the check will not match. The search had the passage in all three.

## Why `now` did so much better than last time

It found the vague passages in 9 of 10 runs here, 4 of 10 in the last test and 6 of 10 in the
one before. Same code path, same requests for three of the five. The quote check's fixes of
today explain little of it: they matter for tables and marked-up quotes. The honest reading is
that ten runs swing this much on their own, and the last test caught a low swing.

## Part 2, the answers

| | `now` | `typed_queries` |
|---|---|---|
| Answers that state 14 CFR 65.91(c)(2) rightly | 4 of 4 | 4 of 4 |
| Answers whose lookup found that passage on its page | 2 of 4 | 4 of 4 |
| Question the lookup asked | a choice between readings in 3, the request itself in 1 | one query per reading in 4 |

One reader, the architect; D50 asks for two. Every answer gave both readings and quoted or
restated the two-year condition correctly. The two `now` answers without the found passage were
right from the search's own summary.

## A slip in the probe, stated

`typed_queries_answers.py` imported the engine before the answer runner had named its scratch
database, so the typed arm's four runs were written to the working folder's default
`autornd.db`. That file held nothing else. It was moved into the results folder beside the
other arm's. The answers and costs are not affected. The probe's order of imports should be
turned round before it is used again.

## The cracks from the last test

| Crack | What was done | Result |
|---|---|---|
| A guessed section number in a query | One sentence added to the field | No section guessed in 9 of 10 vague runs |
| The record did not keep the field | The probe records it | Filled in 18 of 18 |
| Quotes on the page marked not found | The quote check drops emphasis stars and heading hashes (this PR, 8 tests) | 12 of 74 recovered on replay, 0 of 158 found quotes lost |
| The same, where words are left out | **Not changed.** D56 (3) forbids it | 24 more would be found; the owner's ruling |
| Only vague requests tried | Four clear ones added | The field does not help them |
| A found passage is not a right answer | Eight full answers read | All right, in both arms |

## Thoughts on full implementation

1. **Do not replace the lookup's questions with the typed queries.** On clear requests there is
   nothing to gain, and over 36 runs there was no gain on vague ones either.
2. **If it is built, build it narrow, the way the owner first asked:** used only when the scoping
   call itself says the request can be read more than one way, and the blocking unknowns
   otherwise. That is the one place the evidence leans its way: 8 of 10 against 7 of 17 on the
   owner's request across four tests. It costs no extra call. It needs a typed yes-or-no from
   the scoping call, not a reading of its prose.
3. **The larger loss is after the search, and it is the same in every test.** Across today's
   last three tests 128 of 409 quotes were on pages that could not be read, 116 of them on
   osha.gov, and the search had the answer's passage in three of this sweep's four misses. The
   owner's ruling keeps those out of the count; it does not get them checked. The rules
   themselves have a readable copy on ecfr.gov.
4. **One ruling is open:** whether a quote the model broke with a row of dots may be checked
   piece by piece. It would recover 24 of the 52 quotes still marked not found on pages that
   were read. It loosens D56 (3), so it is the owner's.
5. **The answers were right 8 times out of 8.** The wrong answers that began this work were 4 of
   12 on 2026-11-14. Something between then and now moved, or 8 is a lucky draw. Before more is
   built for this request, a plain re-count of its answers on main is the cheaper question.
