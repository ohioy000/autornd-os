# Preregistration: the typed-queries test (2026-11-14)

Written and pushed before the run. The owner's word of 2026-11-14: "Go", after asking whether the
vague-request problem had been met before in TypeScript.

## The question

A sentence in the scoping prompt did not make the lookup ask each reading of a vague request
(`docs/reviews/2026-11-14-vague-request.md`). Published TypeScript research tools (dzhng's
deep-research, LangChain.js's multi-query retriever) do not rely on a sentence: the model fills a
typed list of search queries, one per item, and those are searched. Our scoping call returns
unknowns, and for a vague request the unknown looked up is "does it mean A or B?".

**Does a typed list of search queries, filled by the scoping call, find the answer's passage more
often than looking up the blocking unknowns?**

## What is run

- The grounding step alone (`workflows/triage-only.yaml`), by
  `docs/probes/typed_queries_probe.py`. No answer is written.
- **Two arms.** `now`: the code as it is. `typed_queries`: the scoping call's JSON gains one
  field, `lookup_queries`, worded in the probe, and the lookup asks those. If the field comes back
  empty the blocking unknowns are used, as now. Inside the probe only.
- **The same three requests and repeats as the last test:** IA 4, V17 3, V22 3. 20 runs.
- About '$0.25' expected; the probe stops at '$0.40'. About '$2.65' of the owner's '$7' is spent
  before it.
- **Measured,** as before: whether a quote found on its page holds the words of the sentence that
  states the answer.

## The bars

The same as the last test, so the two can be read side by side.

1. On IA, `typed_queries` finds the passage in at least 3 of 4 runs.
2. Over all 10 runs, `typed_queries` finds it in at least 2 more than `now`, and on no request in
   fewer than `now`.

Both met: the field is put to the owner as a change to the scoping call, with a wider test before
it ships. Either missed: it is not proposed, and the architect's advice to stop on the vague
request stands.

## Predictions

1. The model fills the field: in at least 9 of the 10 `typed_queries` runs the questions looked up
   come from `lookup_queries`.
2. In at least 3 of the 4 IA `typed_queries` runs no question looked up is a choice between
   readings. This is the step the sentence failed at.
3. `typed_queries` finds the IA passage in at least 3 of 4.
4. `now` finds the passage in 4 to 7 of 10 runs: it found 6 last time and the lookup is noisy.

## Limits, stated beforehand

- Ten runs an arm. Last time the same arm of the same code gave 0 of 3 and then 2 of 4 on IA, so
  a small gap means nothing; that is why bar 2 asks for 2 more and nowhere fewer.
- Two of the three requests were written by the architect.
- A found passage is not a right answer. One reader; D50 asks for two, a stated departure.
- The osha.gov pages cannot be read, so V17 and V22 depend on the search quoting eCFR.
