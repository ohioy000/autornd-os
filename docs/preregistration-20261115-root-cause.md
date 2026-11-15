# Preregistration: the root-cause test (2026-11-15)

Written and pushed before the run. The owner's word of 2026-11-15: find the root of the issue,
not the small fixes.

## What two days of tests point to

Every wrong answer on record came from a run in which the right text did not reach the answer
step, or reached it beside a wrong text with nothing to tell them apart:

- The inspection-authorization request: 5 wrong of 28, all in runs whose lookup had not found
  the rule's sentence. Right 15 of 15 when it had.
- The flight-attendant question: 3 wrong of 3. The current rule's sentence was quoted in two
  runs; in one the quote check rejected it, in the other it stood beside an outdated official
  page and an old edition, and the answer took the old figure.

And every repair so far has been to the same part: tables, stars, hashes, tildes, carets, lists,
unread sites. They are all symptoms of one design. **The harness does not read the source. It
asks a search model to read it, summarise it and quote it from its own reading, and then checks
whether the quoted words can be found on the page.** So:

- which pages are read is the search model's choice (an FAQ, a sister rule, a site that refuses);
- what is quoted is the search model's retelling (marked up, stitched, cut), and a third of such
  quotes failed the check on the harder set;
- the answer step reads the summary, and learns what the page says only through it.

**The hypothesis:** the root is what text reaches the answer step. If the harness itself fetches
the source and hands on its own words, the answers come right.

## The test

`docs/probes/root_cause_probe.py`, full answers through the default workflow, on the two
questions that have gone wrong: the hard set's H1 and the inspection-authorization request.
Three arms, four answers a question in each, 24 answers. Main's code is not changed.

- **`oracle`:** no search. The harness fetches the governing section and hands on its text. The
  upper bound. If answers are still wrong with the right text in front of the model, retrieval
  is not the root and the hypothesis is wrong.
- **`fetched`:** the real lookup, then the harness fetches the pages that lookup cited and hands
  on excerpts of their own text, chosen by the request's words. The realistic form: no knowledge
  of the right page is given.
- **`fetched_primary`:** the same, with two sentences saying the rule's own current text governs
  over a page about it or an older edition, and to say so when the texts differ.

**What it is compared with,** from the record: H1 as the code is, 0 right of 3. The
inspection-authorization request as the code is, 23 right of 28.

**Cost.** About '$0.50' expected. Six runs, each stopping at '$0.13', '$0.78' in all, inside the
'$0.83' left of the owner's '$7'. The owner has said the budget is not to hold the work back; a
larger test would still be stated with its amount first.

## The bars

1. **`oracle` is right in at least 7 of 8.** Met: the root is what reaches the answer step.
   Missed: it is not, and the report says what the wrong answers did with the right text.
2. **`fetched` is right in at least 6 of 8,** and on H1 at least 2 of 4. Met: the harness
   fetching what the search cites is enough without knowing the right page.
3. **`fetched_primary` is right on H1 in at least 3 of 4.** Met: when texts differ, a plain rule
   of precedence settles it.

## Predictions

1. Bar 1 is met, 8 of 8.
2. On the inspection-authorization request `fetched` is right 4 of 4: its section is nearly
   always among the pages cited.
3. On H1 `fetched` is right at most 2 of 4: the outdated FAQ and the current rule will both be
   in front of the model.
4. Bar 3 is met.
5. `oracle` is the cheapest arm: it pays for no search.

## Limits, stated beforehand

- Two questions, four answers each. This tests a hypothesis about a cause; it does not measure a
  build.
- One reader; D50 asks for two, a stated departure.
- The excerpts are chosen by shared words, the simplest way there is. A build would choose them
  better.
