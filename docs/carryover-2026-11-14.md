# Carryover: 2026-11-11 to 2026-11-14

For whoever picks this up next. It says what changed in these four days, what is in progress, and
where the project is headed. Main is at `5c408d1`. The suite is 1931 tests, green, network guard 0.

## The goal

A **general** harness for engineering R&D teamwork: a team gives it a request in plain words and it
returns a written answer they can rely on, or says plainly why it could not. It runs on low-cost
models, so the checks around the model matter more than the model.

Two rules steer the work:

- **General first.** Fix what would fail on any team's request before tuning for our test questions.
- **Frugal.** Decide with free code where possible, then with a cheap yes/no question, and only then
  with an expensive model call.

## What changed, by theme

18 pull requests were merged, #232 to #249.

**The audit and the default workflow (#232, #233)**
- A full audit of the harness. Its first fixes: the API now returns the answer itself, and the
  recompute vote and research steps were repaired.
- The default workflow no longer runs judges. It answers once, then recomputes the answer's values
  three times blind and votes.

**Sources and lookups (#235, #236, #238, #239)**
- A request that asks for citations always gets a lookup.
- The fetch reads books, documents and database answers, with wider limits.
- A stored chunk too far from the question (distance above 0.81) is not offered as evidence.
- A dropped connection while reading a reply is retried.
- The delivery carries **cautions**: plain sentences on what was not checked.

**The recompute vote (#237, #241)**
- The answer states its results as typed values, so the vote has something to compare.
- The vote now says "not comparable" when it cannot compare, not "agreed".

**Decision switches (#240, #242, #245, #249)**
- A new optional **decision tier**: a small model that answers narrow yes/no questions with a
  probability, for a fraction of a cent each.
- Switches are declared in `switches/default.yaml`. Each one guards a costly step, has a safe side
  for "unsure", and ships in shadow (recorded, nothing acts on it) until the owner rules it live.
- Live now, each by the owner's ruling:
  - `needs_sources`: runs or skips the grounding lookup.
  - `same_meaning`: clears a vote flag that is only a difference in wording.
  - `quote_answers`: labels a quote that is on its page but does not answer its question.
- Still in shadow: `hard_request`, `ask_covered`, `chunk_helps`, `finding_answers`.

**A cut-off answer is blocked (#245)**
- A free check reads the end of the answer. If it stops mid-sentence the run ends blocked, not done.
- It has not yet been seen to fire on a live run.

**Measurement (#243, #244, #246, #247, #248)**
- Three paid runs, each preregistered before it ran:
  - 150 tier-2 units across the short workflows.
  - Golden batch 1: 12 of 15 right.
  - The lookup runs: 25 of 26 right.
- The tier-2 scorer is at version `.4`. It reads the layouts right answers use. The keys are
  unchanged.
- Preflight matches serving pins correctly and knows the recompute tier (#234, #238).

**Configuration**
- The owner's `.env` was re-tiered during the audit: model per tier, provider pins, a decision
  model and a recompute model. The run headers in `docs/traces/` record the line-up used.

## Money

The owner set '$7' for measurement on 2026-11-13. About '$1.65' is spent: about '$1.23' before
the lookup runs ('$1.03' on the 150 units, '$0.17' on golden batch 1, the rest small), then '$0.42'. A paid run needs the owner's word on the amount first.

## What we are working on

1. **Seeing the two new live switches on a real run.** They are tested offline. The next paid run
   should confirm a cleared flag and a labelled quote in a real delivery.
2. **The errors nothing catches.** The wrong answers of these runs sat in prose: a wrong period, a
   missing condition. The vote compares typed values, so it missed them. This is the main open
   problem. Candidates: have the answer state more of its claims as typed results, or check each
   claim against a found quote.
3. **Votes that compare nothing.** On open questions (IA, Q6) the samples do not agree with each
   other, so the vote is silent. The delivery says so in a caution, but the answer goes unchecked.
4. **The cut-off gate** needs one live firing to be trusted.
5. **Moving more switches to live,** one at a time, each on its own evidence: `ask_covered` next.

## Waiting on the owner

- **The three scorer misreads** left from `.4` (Q15 twice, Q19 once). The architect recommends
  leaving them: they cost three hand readings per run and change nothing a user sees.
- **A second reader.** Every reading in these four days had one reader. The rule (D50) asks for two.

## Known small defects, not fixed

- The golden key for Q6 fails any answer that names XOR, even to rule it out.
- One grounding question had a garbled dash in a stored trace (lookup run A, shard 3). Not traced.
- Q12's lookups found no quote in 4 of 4 runs; the answers were right from memory.

## Where to read more

| For | Read |
|---|---|
| The rules of work | `CLAUDE.md`, then `AGENTS.md` |
| The latest results | `docs/reviews/2026-11-13-lookup-quotes.md` |
| The golden test and the four choices | `docs/reviews/2026-11-13-golden-decisions.md` |
| The 150-unit run | `docs/reviews/2026-11-13-short-workflows-measurement.md` |
| The scorer change | `docs/reviews/2026-11-13-tier2-scorer-v4.md` |
| The switches and their rulings | `switches/default.yaml` |
