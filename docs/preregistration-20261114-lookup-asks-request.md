# Preregistration: does looking up the request's own question fetch the answer's passage (2026-11-14)

This is written and committed before the run. A wrong prediction will be reported as wrong. The
owner asked for a specific test of the flaw on 2026-11-14, and for a directive used only where it is
needed.

## The flaw, as the code has it

The lookup does not search for what the request asks. It searches for the scoping call's "blocking
unknowns": what the request leaves unspecified (`autornd/knowledge/context.py`, `analyze_request`
and `build_phase_context`). The request's own question is looked up only when a lookup is demanded
and the scoping call named no unknown.

So for a request that asks for facts from a source, whether the passage that states the answer is
fetched depends on a search about something else happening to return it. All 4 recorded wrong
answers to the inspection-authorization question were written without that passage
(`docs/reviews/2026-11-14-prose-errors-are-retrieval.md`).

## The test

`docs/probes/lookup_asks_request_probe.py`. The grounding step alone, through the real engine
(`workflows/triage-only.yaml`), each run on its own empty knowledge store. No answer is written.

- **Arm `now`:** the code as it is.
- **Arm `request_first`:** the request itself is the first lookup question, followed by the first
  two blocking unknowns. Three questions at most, as now. Done by wrapping one function inside the
  probe; main's code is not changed.
- **Requests:** golden IA, and tier-2's lookup questions Q2, Q12, Q17 and Q22. Three repeats each
  per arm, so 30 runs.
- **Measured:** is the passage that states the answer among the quotes the quote check found on
  their pages. The passage is recognised by words of its governing sentence, fixed here:
  "actively engaged" (IA), "19.5" (Q2), "0.010" (Q12), "50 pounds" (Q17), "6 months" or "14 hours"
  (Q22).
- **Cost:** a grounding run is one scoping call and up to three searches. About '$0.30' expected.
  The probe starts no run once '$0.50' is spent.
- **Budget:** inside the owner's '$7'. About '$2.09' of it is spent.

One reader, the architect, reads the found passages of every run to check the word match did not
count a passage that does not state the answer. D50 asks for two readers; a stated departure.

## What would justify a directive

The directive would be: when a lookup is demanded (the request asks for its sources in words, or
the live `needs_sources` switch says yes), the request's own question is looked up first. It
applies to no other request, and it adds no lookup: the limit stays at three.

It is proposed to the owner only if both hold:

1. `request_first` finds the passage in at least 12 of its 15 runs;
2. it finds it in at least 4 more runs than `now` does.

If `now` already finds it in 12 or more, the flaw is not what loses the passage, and the report
says so. Making the directive live is the owner's ruling either way.

## Predictions

1. `now` finds the passage in fewer than 10 of 15 runs.
2. `request_first` finds it in at least 12 of 15.
3. Q12 is the hardest: its lookups found no limit-stating passage in 4 of 4 runs on 2026-11-13.
4. `request_first` costs no more than `now` on average, within 20 percent.
