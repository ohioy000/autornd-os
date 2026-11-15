# Preregistration: the vague-request test (2026-11-14)

Written and pushed before the run. The owner's third word of 2026-11-14: a test for the vague
request.

## The question

For the inspection-authorization request the lookup brought the wrong section in 5 of 6 runs
(`docs/reviews/2026-11-14-lookup-asks-request.md`). In every one of those runs the scoping call
named one blocking unknown of the same shape: "whether the request means (a) the requirements to
hold the authorization or (b) what its holder may do". That choice is what the search was asked.
No page answers a question about what the asker meant.

**Does it help to look up each reading as its own question instead of the choice between them?**

## What is run

- The grounding step alone, through the real engine (`workflows/triage-only.yaml`), by
  `docs/probes/vague_request_probe.py`. No answer is written.
- **Two arms.** `now`: the code as it is. `each_reading`: one sentence added to the scoping
  prompt, inside the probe only: "When a blocking unknown is which of two or more readings of the
  request is meant, do not list the choice between them. List each reading as its own question,
  worded so a published source can answer it."
- **Three requests.** IA, the owner's recorded request, 4 repeats. V17 and V22, written for this
  test in the same manner from tier-2 Q17 and Q22, 3 repeats each. Their wording is in the probe.
- **20 runs.** About '$0.23' expected at the last test's cost per run; the probe stops at '$0.40'.
  About '$2.44' of the owner's '$7' is spent before it.
- **Measured:** whether a quote found on its page holds the words of the sentence that states the
  answer. The words are fixed in the probe: "actively engaged" (14 CFR 65.91(c)(2)), "50 pounds"
  (29 CFR 1910.147(c)(5)(ii)(C)(2)), "6 months" or "14 hours" (29 CFR 1910.95(g)(5)).

## The bars

1. On IA, `each_reading` finds the passage in at least 3 of 4 runs.
2. Over all 10 runs, `each_reading` finds it in at least 2 more than `now`, and on no request in
   fewer than `now`.

Both met: the sentence is put to the owner as a change to the scoping prompt. It is not built
here. Either missed: it is not proposed, and the report says what the runs showed instead.

## Predictions

1. `now` finds the IA passage in at most 1 of 4 runs.
2. In at least 3 of the 4 IA `now` runs the question looked up is a choice between readings.
3. `each_reading` finds the IA passage in at least 3 of 4.
4. `now` finds the V17 and V22 passages in at least 2 of 3 runs each: they are less vague than IA.

## Limits, stated beforehand

- One recorded vague request and two written by the architect. Three requests cannot show the
  sentence is safe in general; they can show it is worth a wider test.
- A found passage is not a right answer. This test writes no answer.
- One reader, the architect, reads the matched passages. D50 asks for two; a stated departure.
- The run uses main with #256, so a table quote is read row by row. None of these three answers
  is a table.
