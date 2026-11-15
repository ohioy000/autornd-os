# The typed-queries test: both bars met (2026-11-14)

Preregistered in `docs/preregistration-20261114-typed-queries.md`, pushed before the run. The
figures re-derive with `docs/probes/vague_request_analysis.py` on this test's trace.

## The point

- **A typed list of search queries found the answer's passage in 8 of 10 runs. The code as it is
  found it in 4 of 10.** Both bars were met.
- **The model filled the field as asked.** In all 10 runs the questions looked up were plain
  questions a source can answer ("What are the eligibility requirements to obtain an inspection
  authorization…"). None was a choice between readings. A sentence in the prompt failed at exactly
  this step in the last test.
- **It is a proposal, not a change.** Nothing in main is changed. Ten runs an arm on three
  requests is enough to say it is worth a wider test, not enough to ship it.
- **Cost:** '$0.240' for 20 grounding runs, against '$0.25' expected. About '$2.89' of the
  owner's '$7' is now spent.

## What was run

- The grounding step alone (`workflows/triage-only.yaml`), two arms, three requests, 20 runs. No
  answer was written.
- **Arm `typed_queries`:** the scoping call's JSON gains one field, `lookup_queries`, and the
  lookup asks those in place of the blocking unknowns. The wording is in
  `docs/probes/typed_queries_probe.py`.
- **Code:** main at `cead479`, with the owner's `.env` of the date.
- **Trace,** copied byte-identical: `docs/traces/20261115T-typed-queries-runs.jsonl`, sha256 `9bf74ec3e0a2…`.

## Run by run

Runs in which a quote found on its page held the answer's sentence.

| Request | `now` | `typed_queries` |
|---|---|---|
| IA, the owner's recorded request | 1 of 4 | 3 of 4 |
| V17, lockout strength, written for the test | 0 of 3 | 2 of 3 |
| V22, audiograms for new employees, written for the test | 3 of 3 | 3 of 3 |
| **All** | **4 of 10** | **8 of 10** |

One reader, the architect. D50 asks for two; a stated departure.

## The bars and the predictions

| | Stated | Result |
|---|---|---|
| Bar 1 | `typed_queries` finds the IA passage in at least 3 of 4 | **Met.** 3 |
| Bar 2 | at least 2 more than `now` over all runs, and nowhere fewer | **Met.** 4 more; no request fewer |
| Prediction 1 | the field is filled in at least 9 of 10 runs | **Held, by reading.** 10 of 10; see the departure below |
| Prediction 2 | at least 3 of 4 IA lookups are not a choice between readings | **Held.** 4 of 4 |
| Prediction 3 | `typed_queries` finds the IA passage in at least 3 of 4 | **Held.** 3 |
| Prediction 4 | `now` finds the passage in 4 to 7 of 10 | **Held.** 4 |

## A departure, stated

A late edit meant to record the field's raw contents beside the blocking unknowns did not apply,
and the run went ahead without it. Prediction 1 is therefore read from the questions the lookup
recorded as asked, which in every `typed_queries` run are worded as search questions and in every
`now` run are worded as unknowns. The measure the bars rest on is not affected.

## What the runs showed

- **Why it works.** The search is asked what each reading's answer is, so it quotes the section
  that states it. With the unknowns, it is asked which reading is meant, and quotes whichever it
  meets first.
- **The one IA miss.** The model wrote section numbers into its query that are not the right ones
  ("14 CFR 65.71 through 65.77", the mechanic rules), and the search followed them. A guessed
  citation in a query can lead the search astray. The wording of the field could forbid citing a
  section the request did not name; not tested.
- **The noise is real.** `now` found the IA passage in 0 of 3, then 2 of 4, then 1 of 4 across
  three tests: 3 of 11. One good run of ten for the new arm is not proof.
- **Unread pages.** 43 of 129 quotes were on pages that could not be read, 38 of them on osha.gov,
  the same in both arms.

## What is put to the owner

A change to the scoping call: it returns `lookup_queries`, and the lookup asks those. It changes
what is looked up on every request that has a lookup, so it is the owner's ruling, and it should
not ship on this test alone. The architect's advice is one wider test first:

- the grounding step on about 12 requests, vague and clear, so harm to clear requests would show;
- then full answers on the inspection-authorization request, since a found passage is not yet a
  right answer.

About '$0.60' for both, with a stop stated beforehand.
