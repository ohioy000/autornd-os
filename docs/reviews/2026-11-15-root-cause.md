# The root: what text reaches the answer step (2026-11-15)

Preregistered in `docs/preregistration-20261115-root-cause.md`, pushed before the run.

## The point

- **The hypothesis held.** When the harness itself fetched the governing section and handed on
  its own words, all 8 answers were right: 4 of 4 on the flight-attendant question, which had
  been 0 of 3, and 4 of 4 on the inspection-authorization request.
- **It was also the cheapest and the cleanest arm.** About '$0.005' an answer on the
  flight-attendant question against about '$0.015' as the code is, because no search is paid
  for, and those four answers carried no caution at all.
- **The root has two halves, and the test separates them.**
  1. **Reading.** Handing on the pages' own text, in place of a search model's retelling, fixed
     the flight-attendant question outright: 4 of 4 in both realistic arms, with the outdated
     FAQ still among the pages. The model reads a rule's text rightly when it is given the text.
  2. **Finding.** It did not fix the inspection-authorization request: 2 of 4. In both wrong
     runs the search never cited the governing section, so the harness faithfully fetched the
     wrong pages. Which pages are read is still the search model's choice.
- **Cost:** '$0.331' for 24 answers. About '$6.50' of the owner's '$7' is spent.

## The figures

Answers right, read by hand; one reader (D50 asks for two).

| | As the code is (record) | `oracle` | `fetched` | `fetched_primary` |
|---|---|---|---|---|
| H1, flight-attendant rest | 0 of 3 | 4 of 4 | 4 of 4 | 4 of 4 |
| Inspection authorization | 23 of 28 | 4 of 4 | 2 of 4 | 4 of 4 |
| Cost an answer, H1 | about '$0.015' | '$0.005' | '$0.012' | '$0.014' |

| | Stated | Result |
|---|---|---|
| Bar 1 | `oracle` right in at least 7 of 8 | **Met.** 8 |
| Bar 2 | `fetched` right in at least 6 of 8, H1 at least 2 of 4 | **Met, at the line.** 6; H1 4 |
| Bar 3 | `fetched_primary` right on H1 in at least 3 of 4 | **Met.** 4 |
| Prediction 1 | bar 1 at 8 of 8 | **Held** |
| Prediction 2 | `fetched` right 4 of 4 on the inspection-authorization request | **Wrong.** 2. Its section was not among the pages cited in the two wrong runs |
| Prediction 3 | `fetched` right at most 2 of 4 on H1 | **Wrong.** 4. With the rule's own text in front of it the model took the rule over the FAQ unprompted |
| Prediction 4 | bar 3 met | **Held** |
| Prediction 5 | `oracle` is the cheapest arm | **Held** |

## What each arm shows

- **`oracle`** answers "is retrieval the root?" Yes. With the right text, no answer was wrong,
  on the two questions where the harness has been wrong 8 times.
- **`fetched` on H1** answers "does the model need a rule of precedence?" Not here. The same
  outdated FAQ that won three times when the model saw a summary lost four times when the model
  saw the rule's text beside it. The two sentences of `fetched_primary` added nothing on H1.
- **`fetched` on the inspection-authorization request** shows the half that remains. The wrong
  answers said "2 of the preceding 24 months" and "3 years": the model filling in from memory
  what no fetched page told it.
- **`fetched_primary` on that request was 4 of 4,** but the two sentences cannot be the reason:
  they say which text governs, and cannot bring a page that was not fetched. The search happened
  to cite the governing section in three of those four runs, against none of the two wrong
  runs of `fetched`. Chance, on four answers.

## What this means for the design

Today's lookup is one call to a search model that chooses the pages, reads them, summarises
them and quotes them. The harness checks the quotes afterwards. Two days of repairs went into
that check. The root is upstream of it:

1. **The harness should read the sources itself and hand on their own words.** It already
   fetches every page and reads every format. It uses that only to check quotes. Handing the
   fetched text to the answer step makes quotes exact by construction, so the whole family of
   mark, table and stitching mismatches stops mattering, and an outdated page is read beside
   the rule's text and not in place of it.
2. **The harness should decide what to fetch, by the request's own question.** Ask the search
   for documents, not for an answer; fetch what it returns; choose the passages itself. The
   typed search queries of 2026-11-14 belong here: they were the one change that brought the
   governing section more often, and they failed only as a patch on the old lookup.
3. **What then is left for a check:** whether the answer's figures are in the text it was
   given. That check becomes simple and strict, because the text is the harness's own.

## What it does not show

- Two questions, four answers each. It tests a cause. It is not a measurement of a build.
- The excerpts were chosen by shared words, which a misspelt, vague request defeats. A build
  must choose passages better; that is part of the second half.
- Nothing here says how the design does on questions the harness already gets right. The two
  frozen professional sets, 32 questions, are there to answer that.

## What the architect proposes

Build the lookup the other way round, as a new workflow beside the default one, so nothing
live changes until it is measured: search for documents, fetch them, hand on their text. Then
run both frozen professional sets and the inspection-authorization request through both
workflows. About 100 answers each way; about '$3' with a stop stated before the run. It needs
the owner's word and an amount beyond the '$7'.
