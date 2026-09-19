# Changelog

All notable changes to AutoRnD will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

Everything below happened after 0.1.0 and none of it was recorded until now.
The entry is written as prose rather than a bullet list because most of these
changes are only meaningful with the measurement that forced them.

**The workflow became a file.** The five-phase sequencer is gone from the
critical path. A pipeline is now a YAML graph in `workflows/`, built from three
node kinds — `ai` (model calls), `check` (free deterministic functions) and
`gate` (booleans over prior outputs) — with loops that carry an `until`
condition, a bounded iteration count and explicit exhaustion semantics, so a
build loop that gives up hands off to an escalation autopsy rather than simply
stopping. Conditions are one deliberately tiny grammar, not `eval`;
configuration must not execute code. Four workflows ship, and comparing two of
them is a measurement anyone can run. A hardcoded sequencer was kept beside the
graph as an equivalence reference for most of that work; it has since been
retired, for the reasons recorded below.

**An eval harness, so rules come from data.** Scenarios are YAML with
expectations written *before* the run; assertions are free and make no model
call; a bounded runner enforces per-scenario spend and call ceilings and reports
cost and calls per tier; suites repeat, because the same request has passed on
one run and failed on the next. Each scenario gets an isolated knowledge store,
after the discovery that research ingests what it finds and so grounded every
scenario after the first.

**Outward research, as a default rather than an option.** The harness writes its
own queries, ranks what it retrieves, briefs the phases that follow, and looks
outward for what the documentation does not cover. It asks the local store
before it pays for anything, and it ingests what it finds, so a fact is looked
up once and free thereafter. The reason it exists is a measurement: asked which
charger IC a board used, a capable model named the wrong part confidently and
without hedging; asked an RF limit it conflated two units 2.15 dB apart, the
difference between a compliant transmitter and a failed certification. Both
wrong answers sounded exactly as certain as the right ones, so there is no
confidence signal to gate a lookup on.

**Search cost was cut 44% by changing its shape, not its budget.** Low-risk work
looks nothing up; only gaps that would change the answer are looked up; and
every remaining gap rides in exactly one request, because the fee is charged per
request rather than per question. Token budgets scale with risk — a wrong figure
in medium-risk work is recoverable and in critical work it is not. Measured
across 36 sectors, $0.0999 to $0.0562 per workflow, almost entirely from four
requests becoming one.

**Domains and roles became open vocabularies.** Both were closed enums. With
`Domain` enforced, nine of twelve subjects had no fitting value and eight came
back `hardware` — civil engineering as "hardware", buffer chemistry as
"documentation". A closed list does not produce an honest refusal; it produces a
least-wrong label. Projects now declare `domains:` and `roles:` in a profile, an
undeclared role resolves to a synthesized generalist, and the shipped enums are
defaults rather than limits.

**Review composition is derived, not tabulated.** The review team is built from
the specialists triage actually assigned, scaled by risk. The old static table
returned every shipped role at critical risk, which meant seven engineers
reviewing a records retention schedule.

**Review gates the run.** `ship: false` now blocks rather than being recorded and
surfaced while the workflow completes anyway.

**`unrecallable` is a separate axis from risk.** A signed rollout to forty
thousand devices harms nobody and breaches no rule, so it is not critical — but
it cannot be taken back. It earns one extra independent review pass instead of
inflating its risk level.

**Cost accounting moved onto the client, and the old numbers were wrong.**
Spend, call counts and serving provider are recorded per tier inside the client,
so no call path can avoid being priced, with optional call and spend ceilings
enforced at the same place. This fixed a meter that had been counting only one
of four paths: research, grounding and reranking were all free as far as the
totals were concerned, and rerank cost was read into a debug log and discarded.
An eight-sector grounding run metered at $0.0025 actually cost $0.7366.
**Every cost figure in this project's history before that fix is understated by
between 2.6x and 295x and should not be cited.**

**Providers can be pinned per tier, and it turns out to matter.** One sweep saw a
single tier served by five different providers. Pinning each and re-running the
identical suite scored 35/36 at one end and 28/36 at the other, for twelve times
the price — and the cheap serving did not fail randomly, it under-classified risk
on the same three consequential sectors every repetition. An unpinned score is
partly a record of who answered, so pinning is a precondition for calibrating
anything. Pins are per tier because tiers run different models and no provider
serves them all.

**Packaging was unusable and is now fixed.** `pip install -e .` failed at build
on flat-layout package discovery, so it never reached the missing runtime
dependency behind it, and no built wheel contained the dashboard template.
`pyproject.toml` is the single dependency manifest, `requirements.txt` is gone,
and CI grew a job that installs from project metadata, imports the startup path
and checks a built wheel carries its package data — because the test suite runs
against the source tree and is structurally incapable of seeing a packaging
fault.

**Bounded, pinned, and able to keep its own records.** `--max-spend` only ever
capped one scenario-run, so a sweep of thirty-six scenarios at three repetitions
could spend thirty-six times what the flag implied; `--max-spend-sweep` now caps
the whole invocation and defaults to a dollar. Building it exposed six error
handlers that swallowed a budget abort and let a run keep spending after it had
been told to stop — including two that would have marked a working ranker dead
for the rest of the process.

Two long-standing calibration complaints turned out not to be what they were
recorded as. One sector had been blamed on the risk guide for months and was the
serving: pinned to a capable provider it passes, pinned to a cheap one it fails
every time, and nothing in the guide needed changing. The materiality gate was
recorded as an ineffective cost lever; it is ineffective as a cost lever and
does not need to be one, because the work whose gaps are immaterial already
classifies as low risk and never looks anything up. It stays as a question-count
cap, which protects the token budget of the questions that do get asked.

The cost meter, silently broken before the accounting fix and never checked
against anything outside itself, now agrees with the provider's own books to
within a third of a percent across a third of a dollar of live spend.

Evals keep what they buy. Every unit appends a JSON record carrying the typed
verdicts, the assertion outcomes, the per-tier cost and which provider served
each tier, flushed as it is written — so an interrupted sweep no longer discards
what it has already paid for, and a failing sector can be diagnosed months later
without reproducing it.

**The independent pass was observed running**, for the first time, inside a
complete workflow — a minimal probe shape reaches it by construction, and the
trace is kept as the regression case.

**Three phases could not retry.** The client validates a reply against a schema
and retries with a note saying what was rejected, but the implement and
escalation phases never passed their schema in, so a single malformed reply
ended a run outright — and a review's findings loop read a key off raw items,
crashing on exactly the shapes the finding schema had been widened to accept.
Two of four convergence traces had been dying on the first of these and being
read as convergence failures, which is how a diagnosis came to rest on evidence
that never reached the thing it was evidence about. All three are repaired, with
tests pinning every schema-bearing phase's call site, and errors now carry the
provider's own message instead of only a status code.

**The search tier's cheap sibling ties the expensive one** across three
repetitions — identical mean, identical per-repetition sequence — at an eighth
of the cost per lookup. A larger token budget on the cheap model costs nothing
and recovers fewer figures, so the accuracy curve measured on one model does not
transfer to the other.

**Evals keep per-iteration history**, so whether an implementation changes
between attempts is answerable from a finished run. It does change, by thousands
of characters, and still fails a different criterion each round.

**The build loop stops when its judges agree.** It used to exit on the
validator alone, and was measured exiting satisfied while the implementation sat
red in the same state — a domain reviewer had flagged a critical concern and the
exit did not look. Reading the validator's own evidence showed it was the judge
that was wrong: it marked a criterion passed while stating in the same sentence
that the test case had been changed away from what the criterion asked for. Each
loop now folds every judge its own shape produces, and the free checks carry the
same weight as the paid ones.

**Two silences closed.** When a reviewer's critical concern flipped an
implementation red, the next attempt was told only that a concern had been
flagged — the reviewer's actual words went onto a field nothing downstream read;
they now travel with the reason. And a lookup the provider refuses is swallowed
so the workflow survives, which is right and was silent: a whole evaluation once
scored zeros that were indistinguishable from a model finding nothing. Refusals
are counted where they are swallowed and the report says so.

**The assessment contract now fixes the success criteria.** Saying a criterion
is wrong is legitimate; passing work against a criterion quietly amended is a
false assessment, and a false pass is the expensive direction because it ends
the loop.

**The search tier's cheap sibling ties the expensive one** at three repetitions
— identical mean, identical per-repetition sequence — for an eighth of the cost
per lookup. A larger token budget on the cheap model costs nothing and recovers
fewer figures, so the accuracy curve measured on one model does not transfer to
another in the same family.

**Review's findings have somewhere to go.** A blocked review used to end the
run with its findings recorded and nothing able to read them. A closed gate can
now route instead of ending, so the work goes back through implement, validate
and a fresh review, and ships only when every judge agrees. Two silent channels
were opened on the way: the validator returned one failing criterion at a time
while its own evidence already held a verdict for each of them, and a blocking
review wrote nothing to the failure log at all. Both now travel to the next
attempt, in their authors' own words. Every loop must declare a bound at load
time — review and implement can disagree indefinitely, and the graph can no
longer express that.

**The planning phase has a ceiling of its own**, where it had been running on a
generic default while burning full-budget retries that returned nothing.

**The equivalence reference is retired.** A hardcoded sequencer was kept beside
the graph so the two could be compared call for call, and it earned its place
for a long time. It stopped: silent through a change to how loops exit, two
wrong attempts at mirroring behaviour it lacked the inputs for, an
order-dependent defect in its own suite, and finally a gate that routes work
back into a loop — which a linear engine cannot represent at all.

**A run now records what it measured.** Three instruments were found reporting
something other than what they observed, none of them visible to a green suite.
The schema retry had logged every rejected reply correctly and for free since
its clause ordering was fixed, and every line went to a stderr redirect and died
there — so the malformed-reply rate, asked for across nine runs, could be
computed from three. It is a field in the results file now, split by tier and by
serving, beside the count of verdicts normalised from their own stated cause. A
build-loop iteration records which judge blocked the exit, which it had claimed
to do for sixty-four iterations while reading attributes off a plain dict. And a
gate that routes work to a recovery sub-graph is no longer billed for the time
that sub-graph spends: one gate had been reading 1,573 seconds of an 1,800-second
run, in the per-phase table that exists precisely so an expired run does not have
to be bought twice to say what was slow.

**The build loop converges, and what fixed it was not the loop.** The oldest
open problem in the project — recorded for seven development cycles as "the
build loop does not converge on complex requests" — is closed. It carried six
different names on the way: an untested premise, an exit condition, a feedback
channel, a wall clock, a missing verdict field, and a wall clock again. Five of
them were about the workflow. The answer was the tier: the one that runs
implement, validate and review had never been pinned to a particular serving,
and pinning it turned two test cases that had never once completed into finished
deliverables in under five minutes each. The mechanism is not speed. Per-call
latency improved by about a third, while the number of iterations the work
needed fell from eight to two and from four to one — a serving does not only run
at a speed, it converges at a rate, which is the same lesson this project
learned about classification accuracy and had not thought to apply here. Three
of the four test cases finish with a written deliverable or a diagnosis naming a
real contradiction in their own plan; the fourth did before this cycle began.

Two schema changes landed with it, both earned by a live failure rather than
proposed. A verdict that names why it failed no longer has to also say that it
failed, and a verdict returning its evidence as an object keyed by criterion has
that folded into lines rather than refused three times. Both are counted, by
kind, in the results file — because a leniency that hides how often it fires
cannot be withdrawn later on evidence.

**The way this project is built is now part of it.** For fifteen development
cycles the working method lived in conversation: an advisor designing and ruling,
an agent measuring and implementing, and an owner holding the money and the
standing configuration. That method produced almost everything in this changelog,
including most of its corrections — the recurring pattern was not a wrong
hypothesis but a broken instrument, found while testing something else. With the
agent being replaced, the method has been written down as files rather than
carried in a transcript: one protocol document describing who decides what and
where the line falls between repairing a measurement and changing a behaviour,
and one bootstrap prompt that orients a new agent from the repository alone. Two
open defects are staged with their evidence and their unanswered questions, and
deliberately left undesigned, because choosing between the options would change
a cost model that was measured rather than assumed.

**A feature commit deleted most of the state-of-record document, and the
guards caught it.** `aac0324`, whose subject names only the gate routing it
added, also removed 1,435 lines of `HANDOVER.md` without mentioning the
deletion — the architecture, the state, the bug ledger, the conventions, the
measured facts and the orientation, leaving the vision and the executive
summary. The document that both the protocol file and the bootstrap prompt
send a new agent to read no longer contained the sections they name. Five
documentation guards in `tests/test_handover_truth.py` failed and the suite
stayed red on the main branch for three days across two commits. Every one of
the five failed because the claim it watches was **absent**, not because a
number had drifted: no guard caught a stale count, and all five caught a
missing document — which is a stronger result than the guards were written
for. The same commit left a placeholder in the header where a commit sha
belongs, a stamp that resolves to no object at all; that is the failure mode
the convention against hand-stamped facts was written against, appearing in
the document that states the convention. The text was restored from the last
green commit and every guarded number re-derived forward against the tree
rather than copied back, the suite returned to green, and restoring the
document surfaced a wiring asymmetry in the flagship pipeline that no record
had stated — the honest-refusal gate runs in the build loop and not in the
rework or recovery loops, so work blocked after a review reaches no gate that
can report it. That one is recorded and left for a ruling.

The suite stands at **712 tests** as of `c442c5f`, up from 85 at 0.1.0.

## [0.1.0] — 2026-09-12

### Added

- Multi-model agentic workflow engine with 5-phase sequencer (triage, plan, implement, validate, review)
- 7 engineering specialists with profile-driven system prompts
- Reasoning-model escalation autopsy — recovery when the implement/validate loop exhausts
- Risk-based review team composition (critical → all specialists, low → single specialist)
- Plan feasibility gating — specialists review the plan before implementation tokens are spent
- Project profile system — YAML-based domain grounding with per-specialist context overrides
- Profile-aware knowledge store with ChromaDB semantic retrieval
- Episodic memory — workflow outcomes stored for future context
- REST API with sync and async workflow submission
- Dashboard with chat interface, workflow table, and profile selector
- API key authentication middleware (optional, bearer token)
- OpenRouter multi-model routing client with cost tracking and retry logic
- CLI for doc ingestion (`init-knowledge`)
- Docker support with volume mounts for profiles and docs
- Example profile (SmartFactory) with sample docs
- Full test suite (85 tests)
