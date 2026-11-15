# Preregistration: the sweep of the typed search queries (2026-11-14)

Written and pushed before the run. The owner's word of 2026-11-14: do a sweeping test, look into
the cracks the last test showed and fix them, then give thoughts on full implementation.

## The cracks, and what was done about each before this run

1. **A guessed section number led the search astray** (the one miss on the owner's request). The
   field's wording gains one sentence: "Name no section or paragraph number the request did not
   give." In the probe only.
2. **The record did not keep what the model put in the field.** The probe now records it beside
   the blocking unknowns.
3. **Quotes on the page were marked not found.** A free replay of the 232 quotes that the
   three lookup tests checked on pages still readable: 74 had been marked not found. 10 are found since the table
   ruling. 12 more were on the page word for word under the model's own emphasis stars and
   heading hashes; the quote check now drops those marks (in this branch, with tests). 24 more
   would be found if a row of dots or a heading were allowed to stand for words left out. Ruling
   D56 (3) says nothing may be left out, so that is **not** changed and is put to the owner. The
   rest are mostly PDFs.
4. **Only vague requests were tried.** This sweep adds clear ones.
5. **A found passage is not a right answer.** This sweep adds full answers on the owner's request.

## What is run

**Part 1, the lookup step alone** (`docs/probes/typed_queries_sweep.py`): two arms, `now` and
`typed_queries`, nine requests, two repeats each, 36 runs.

- Five vague: IA, V17, V22 as before; V2 (confined spaces, oxygen) and V12 (drinking water,
  arsenic), written for this sweep.
- Four clear: tier-2 Q2, Q12, Q17 and Q22 as written.
- Measured as before: whether a quote found on its page holds the words of the answer's sentence.

**Part 2, full answers** (`docs/probes/typed_queries_answers.py`): the owner's request through
the default workflow, four answers in each arm, read by hand against 14 CFR 65.91(c).

**Cost.** About '$0.63' expected: '$0.43' for part 1 and '$0.20' for part 2. Stops: '$0.50' on
part 1 and '$0.15' on each arm of part 2, '$0.80' in all. About '$2.89' of the owner's '$7' is
spent before it.

## The bars

1. **No harm to clear requests.** Over the 8 clear runs, `typed_queries` finds the passage in at
   most 1 fewer than `now`.
2. **Gain on vague requests.** Over the 10 vague runs, `typed_queries` finds it in at least 2
   more than `now`.
3. **The field is used as asked.** It is filled in at least 16 of the 18 `typed_queries` runs,
   and in at least 8 of the 10 vague ones no query names a section the request did not give.

Part 2 has no bar: four answers an arm is a reading, not a measurement. The report says how many
answers in each arm state the conditions of 65.91(c) rightly.

All three met: the architect's thoughts on building it follow in the report. Any missed: the
report says which, and the field is not recommended as it stands.

## Predictions

1. Bar 1 is met: the clear requests name their section, so both arms search for the same thing.
2. Bar 2 is met, by less than last time: 2 or 3 more, not 4.
3. V12 is found in both arms now that a table is read row by row.
4. V17 stays the hardest: the search prefers osha.gov, which cannot be read.
5. In part 2, more `typed_queries` answers than `now` answers state 65.91(c)(2) rightly.

## Limits, stated beforehand

- Two repeats a request. A single request's figure means little; the bars are over groups.
- Four of the five vague requests were written by the architect.
- One reader; D50 asks for two, a stated departure.
- Part 1 runs on this branch, so the quote check drops emphasis and heading marks in both arms.
