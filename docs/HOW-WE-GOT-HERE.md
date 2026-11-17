# How AutoRnD got here, and why it looks the way it does

For a reader who opens this repository and wonders three things: how a five-phase agent
pipeline became a short one that reads documents, why there are about two thousand tests, and
why the rules describe an architect writing exact task files for a coder. Every figure here
comes from the record and names where it stands.

## The short version

- **It started as a big team of models and ended as a short, careful path.** The first version
  ran five phases and seven specialists. Measured honestly, that pipeline delivered 0 of 21
  answers where a single call got 17 or 18. Almost everything since has been taking away what
  did not earn its cost and keeping what a measurement showed to work.
- **What works is plain.** Find the document the answer is written in, fetch it, hand its own
  words to an inexpensive model, and say honestly what was checked. On 44 precise professional
  questions that is right nearly every time, for about a cent an answer.
- **The tests are there because the instruments lied.** Again and again a green test suite sat
  beside a meter, a counter or a scorer that was reporting something other than what happened.
  Each guard in the suite was bought by one of those.
- **The architect-and-coder form is how the project stayed honest with several agents and one
  owner.** A design is written down before it is built, the builder cannot change what the
  harness concludes, and money, keys and model choices stay with a person.

## From point A to point B

| When (2026) | What changed | What caused it |
|---|---|---|
| 12 Sep | **Version 0.1.0.** A fixed sequence of triage, plan, implement, validate and review, with seven specialists and an escalation step. 85 tests | The starting idea: a team of models reviews its own work (`CHANGELOG.md`) |
| 12–26 Sep | **The workflow became a file.** A pipeline is a YAML graph of model calls, free checks and gates. Every model reply is a typed verdict | So that a change of pipeline is a change of data, and control flow never reads prose |
| mid Sep | **The cost meter was repaired.** Several call paths were never counted | Costs had been understated by 2.6 to 295 times (`HANDOVER.md` §6) |
| 29 Sep – 1 Oct | **A freeze.** No new mechanism until a small golden set passes | 0 of 7 runs had shipped, and 8 of 10 commands were repairs to instruments (Ruling D41) |
| 2 Oct | **Outside reviews.** An open, money-spending endpoint, runs with no time or spend limit, an empty validation that passed | Two outside reviewers; the claims were checked against the code and most held (`docs/reviews/2026-10-02-consultant-reviews.md`) |
| 5 Oct | **The honest comparison.** The full pipeline delivered 0 of 21; a single call got 17 to 18 of 21. The pipeline took 972 seconds a question against 10 | The first tiered evaluation with frozen questions and keys (`docs/reviews/2026-10-06-tier3-stage1-report.md`). The plans had the right numbers; the losses were process |
| 10–15 Oct | **The request is the yardstick.** Judges may judge only against what the request asked. A short workflow, `verify-first`, appears | Ruling D51, from that comparison |
| 16–19 Oct | **Judges out, recompute in.** Three blind recomputations and a vote | On hard calculation questions judges made no real catch; the vote caught 5 of 5 wrong answers with 1 false flag in 23 (Ruling D53) |
| 21–28 Oct | **Generality first.** The team belongs to a profile; the default is general | The owner's direction: a general harness, not one tuned to a demo |
| 28–29 Oct | **Quotes are checked against their pages.** The harness fetches each page and looks for the passage | Ruling D56: a citation had only ever been the provider's word |
| 11–14 Nov | **The default became one answer and its checks,** with no plan, judge or loop. Small yes/no decision switches. Cautions on the delivery | An audit found a judge could not block an answer on a wrong number. On 150 tier-2 answers none delivered was wrong |
| 15 Nov | **The root cause.** What text reaches the answer step matters most. With the governing section's own words handed on, 8 of 8 answers were right on two questions that had been wrong 8 times | `docs/reviews/2026-11-15-root-cause.md`. The lookup now asks where the answer is written and reads the pages itself: 107 of 107 professional answers right, quotes found 97 percent of the time against 66, and 18 percent cheaper |
| 16 Nov | **Finishing.** The recompute vote kept only for calculations; everything in shadow or switched off removed, about 2,400 lines | On real wrong answers the samples repeated the answer's mistake and the vote flagged none (`docs/reviews/2026-11-16-recompute-samplers.md`) |

**The pattern.** Each large mechanism (the plan, the specialists' review, the judges, the
validate loop, and for lookups the recompute vote) was a second model looking at the first
one's work. Measured on real answers, a second model shown the same material either repeated
the mistake or objected to the wording. What moved the results was not more opinions. It was
better input: the page's own words.

## Where it stands

- **The default path:** triage, the request's asks, a lookup that reads the documents, one
  answer with typed values, two gates that can stop a run, free checks, and for a calculation
  three blind recomputations and a vote (`README.md`).
- **The latest reading** (`docs/reviews/2026-11-16-misleading-set-run.md`): 432 answers on a
  set built from questions where a summary misleads, read blind against signed keys. The
  shipped lookup was right in 144 of 144. No wrong answer in any arm carried a "verified" line.
- **Cost:** about '$0.011' an answer for a lookup and '$0.004' for a calculation
  (`docs/reviews/2026-11-16-needs-calculation.md`).
- **Beside a frontier model:** asked 22 of the same questions directly, with web search, a
  frontier model was right on all 22, about seven times faster and about six times dearer
  (`docs/reviews/2026-11-17-frontier-direct.md`). The harness matches it; it does not beat it.
- **What it does not do.** It cannot tell a stale official page from a current one when
  nothing in the text shows it. It checks figures, not conditions written in words. Some sites
  refuse to be read. The question sets are now near the ceiling, so they can no longer show
  whether a further change helps. These are listed in the README under "Limitations".

## Why there are so many tests

About 2,000 tests in 90 files, running in under three minutes with no network and no spend.
The reason is one sentence from the record: **"Five instruments in two blueprints were found
reporting less than they measured, every one against a green suite"** (`HANDOVER.md` §4.4).

A harness like this is a measuring instrument. Its product is a claim: this answer was checked,
this run cost that much, this configuration passed. If the meter is wrong, every decision made
from it is wrong, and nothing looks broken. These are the cases that taught it:

| What happened | What it hid or cost | The guard today |
|---|---|---|
| The cost meter counted only one call path | An eight-sector run read '$0.0025' and had cost '$0.7366' | `tests/test_spend_guard.py`; a test double must bill like the real client |
| A "skipped" unit was decided by matching words in an error message | When the message was reworded, skipped units counted as run | `tests/test_repeat_and_fit_rule.py`. Rule: never parse English for control flow |
| The test suite itself called the provider | Five real calls with the owner's key inside green tests | A network guard: every run ends "0 non-loopback attempt(s)" (`tests/test_hermetic_suite.py`) |
| A `git stash -u` during a paid run | The results file was taken from under its writer; the record was lost | No git operation in a tree while a paid run writes into it |
| Counts in the documents drifted | The README said 339 tests when there were 501 | `tests/test_handover_truth.py` and `tests/test_docs.py` derive every count from the source |
| A guard that could not fail | A pattern matched nothing, and three deliberate breaks all printed "passed" | `tests/test_guards_can_fail.py`; every guard is proven by breaking the line it protects |
| A frozen scorer held all its own fixtures | It passed 5 of 12 real answers that two readers had judged correct | The scorer is a screen; two readings are the result (Ruling D50); `evals/tier2/regression_12.py` |
| A configured token limit never reached its call | Three truncated plans, '$0.44', no verdict | `tests/test_node_token_ceilings.py` |
| A spend stop was recorded as a review finding | A correct answer was refused | The worst case of a call is reserved before it is sent (Ruling D45) |
| A loop asked one judge of three | It exited "satisfied" while the work was not green | `tests/test_all_judges_exit.py` |
| A module ruled dead was imported on every request | It was nearly deleted on the word of a diagram | `tests/test_live_wiring.py` |
| A timeout was read as a diagnosis | "The loop does not converge" rested on runs that died before reaching the loop | The rule: a reading is a reading, not a diagnosis |

Two habits come from this and explain the suite's size:

- **Every guard is proven by breaking what it guards.** The line is broken, the test is seen to
  fail, the line is restored. A guard nobody has seen fail is a guard nobody knows works.
- **A fact that cannot be checked is deleted, not trusted.** Counts, model lists and tables in
  the documents are either derived from the code by a test or they are not stated.

The same habits govern the measurements: the keys are frozen and signed before a run, a run is
written down with its bars and its predictions before any money is spent, answers are read
blind, and the trace is kept byte for byte with its checksum.

## Why an architect and a coder

The rules in `CLAUDE.md` and `AGENTS.md` describe three roles. They are kept as written, on the
owner's word, because they shaped the project.

- **The advisor (architect)** designs, rules and reviews.
- **The executor (coder)** measures and implements.
- **The owner** holds the money, the keys and the model choices, and is the only one who edits
  the live configuration.

**How it came about.** The first two architects were chat sessions with read-only access to the
repository. The owner carried their designs to the coding agents by hand
(`docs/provenance/README.md`). Things were lost in the carrying, so two rules followed:

- **A ruling exists only when it is in a file in the repository.** A conversation is a draft.
- **Each design is written in full before it is built,** and its outcome is recorded after.
  That is the command channel in `.orchestration/`: 85 commands and 124 responses between
  19 September and 29 October.

**The boundary.** One question decides who may change what: does the change alter **what the
harness would conclude**, or only **how reliably it reaches a conclusion?** Repairing a counter
is the executor's. Changing what a verdict means needs a ruling. This stops the easiest failure
of an agent that builds and measures its own work: making the number better by changing what
the number means.

**Why the task files are so exact.** Each task carries the text to find, the text to replace it
with, a check to run and the result to expect. The record shows what looser commands cost:

- A command once cited a whole paid run that had never happened. The executor found every
  artifact missing.
- Work was recorded as landed while the main branch had not moved.
- Four deliveries met every acceptance criterion with CI green, and a review by probing still
  found four real defects in them (`AGENTS.md`).

So the architect does the thinking and proves each task on a clean copy first, the coder
applies it, and a delivery that matches its task file byte for byte is merged without being
done again.

**The advisor is held to the same standard.** The record keeps the architect's own mistakes: a
command whose wording made a runner refuse an arm, a missed crash in a review, and a
self-assessment that scored "no harm: not met" (`docs/reviews/Dunce-Arch-Self-Assesment.md`).

**What changed at the end.** After 29 October the relay stopped running. The owner worked with
one agent that designs, builds, measures and reports, with subagents for reading and research.
The rules did not change: a behaviour change still goes to the owner, a paid run still needs
the owner's word and a preregistration first, and everything is delivered by pull request.

## Where to read more

| For | Read |
|---|---|
| What the harness does and how to run it | `README.md` |
| The models chosen, and why | `docs/MODELS.md` |
| The rules of work | `CLAUDE.md`, `AGENTS.md` |
| The measured facts and the numbered rulings | `HANDOVER.md` §6, `docs/handover-review.md` |
| Each measurement, with its bars and its result | `docs/preregistration-*.md` and `docs/reviews/` |
| The first architects' conversations | `docs/provenance/` |
| A map of this folder | `docs/README.md` |
