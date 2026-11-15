# The vague-request test: the sentence did not help (2026-11-14)

Preregistered in `docs/preregistration-20261114-vague-request.md`, pushed before the run. The
figures re-derive with `docs/probes/vague_request_analysis.py`.

## The point

- **The sentence is not proposed.** Told to list each reading as its own question, the lookup
  found the answer's passage in 3 of 10 runs. The code as it is found it in 6 of 10. Both bars
  were missed.
- **The scoping model did not follow the sentence.** In all 4 inspection-authorization runs with
  the sentence, the question looked up was still a choice: "Does the request ask for A, or for
  B?" A sentence in the prompt does not change the shape of what that model writes.
- **The vague request is still not solved.** With the code as it is, the inspection-authorization
  passage was found in 2 of 4 runs here and 0 of 3 in the last test: 2 of 7.
- **Cost:** '$0.208' for 20 grounding runs, against '$0.23' expected. About '$2.65' of the
  owner's '$7' is now spent.

## What was run

- The grounding step alone (`workflows/triage-only.yaml`), two arms, three requests, 20 runs. No
  answer was written.
- **Code:** main at `ebefb99`, with the owner's `.env` of the date.
- **Trace,** copied byte-identical: `docs/traces/20261115T-vague-request-runs.jsonl`, sha256 `f3753c075194…`.

## Run by run

Runs in which a quote found on its page held the answer's sentence.

| Request | `now` | `each_reading` |
|---|---|---|
| IA, the owner's recorded request | 2 of 4 | 0 of 4 |
| V17, lockout strength, written for the test | 2 of 3 | 1 of 3 |
| V22, audiograms for new employees, written for the test | 2 of 3 | 2 of 3 |
| **All** | **6 of 10** | **3 of 10** |

One reader, the architect. D50 asks for two; a stated departure.

## The bars and the predictions

| | Stated | Result |
|---|---|---|
| Bar 1 | `each_reading` finds the IA passage in at least 3 of 4 | **Missed.** 0 |
| Bar 2 | at least 2 more than `now` over all runs, and nowhere fewer | **Missed.** 3 fewer |
| Prediction 1 | `now` finds the IA passage in at most 1 of 4 | **Wrong.** 2 |
| Prediction 2 | at least 3 of 4 IA `now` lookups are a choice between readings | **Held.** 4 |
| Prediction 3 | `each_reading` finds the IA passage in at least 3 of 4 | **Wrong.** 0 |
| Prediction 4 | `now` finds V17 and V22 in at least 2 of 3 each | **Held.** 2 and 2 |

## What the runs showed instead

- **The lookup of a vague request is a coin toss, with or without the sentence.** The same
  request, the same code and nearly the same question found the passage in one run and not the
  next. Ten runs an arm cannot tell 6 from 3 with any confidence; they can tell that the sentence
  is no clear gain.
- **When the passage is missed, the search mostly quoted the other reading.** In 5 of the 6 IA
  runs without the passage, the found quotes were about what a holder may do (65.95, 43.7) or
  about renewal (65.93). In the sixth the search quoted 65.91 itself, but not the sentence that
  holds the answer.
- **The owner's second ruling shows in these runs.** 34 of 99 quotes were on pages that could
  not be read, 31 of them on osha.gov. Under #256 they are said apart and not counted.

## What is left, for the owner

A sentence did not make the scoping model split the readings, so a prompt change is the wrong
tool. Two ways remain, neither built:

1. **A typed field.** The scoping call would return the readings as a list of its own, one
   question each, and the lookup would ask those. The model fills a field more reliably than it
   follows a sentence. It changes what is looked up, so it needs the owner's ruling and its own
   test.
2. **Leave it.** The answer still names both readings when it sees the request is vague, and the
   delivery already says what was and was not checked.

The architect's advice: stop here on the vague request for now. Three tests in a row have not
moved it, and each further one costs about '$0.25'.
