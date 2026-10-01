# Architect 3: session summary, 2026-09-30 to 2026-10-01

A summary written by the third architect, not a transcript. The decisions
themselves live where the protocol puts them: rulings in
`.orchestration/commands/`, execution records in `docs/handover-review.md`, and
runs in `docs/traces/`. Where this summary and those disagree, they win (D7).

## The role

The owner made the third architect **architect and custodian** of the
repository, with write access. That means:

- designing and ruling;
- pushing commands directly to `.orchestration/` (one command per commit, each
  on its own branch);
- checking each PR against its acceptance criteria and merging on green.

The coder works in a separate session, with its own clone and its own memory.
The first two architects had read-only access and worked through the owner by
copy and paste (`architect-1-chat.md`, `architect-2-chat.md`). The owner's
framing:

> *A public, open-source harness for the good of the people. It lets
> non-frontier models answer expert-level questions, and the git history is a
> full record of a system built by agents.*

## The project, as classified in the field

AutoRnD is a **compound AI system**: a workflow-based, multi-model
orchestration harness for knowledge work.

- **Workflow, not agent.** A YAML graph fixes the path. Inside it are routing
  (triage), parallel reviewers, and an evaluator-optimiser loop (implement,
  validate, rework).
- **Role-based specialists**, in the family of MetaGPT, ChatDev and CrewAI.
- **Retrieval- and search-augmented generation** for grounding.
- **LLM-as-judge** for validation and review.
- **An evaluation harness built in.**

What is unusual about it: lab-grade measurement (pre-registration, honest
instruments, n stated); provider-level pinning ("a model id is not a system");
typed verdicts with deterministic gates; and a build by agents under a written
protocol, whose rulings act as architecture decision records.

## What happened

| Command | What | Outcome |
|---|---|---|
| 092 | Put the night of 09-29/30 on the record (13 traces, two executor notes) | Merged, PR #99 |
| 093 | Re-grounding edge, fixed. D36 (the four plan rules) and D37 (one round, novel blockers only) | Merged, PR #100. Review caught a dead novelty check, inverted seeding, and tests that certified their own doubles |
| 094 | First live run on a verifiable question: cup-line sensor plus a fictional corpus | **Correct at the first draft ($0.048). Build judges agreed at $0.070. Then review, rework and escalation spent 86% of the money, rework made the answer worse, and the runner killed it at 3,600 s.** |
| 095 | D38 watchdog: a budgeted run finishes cleanly and points at the last approved answer | Merged, PR #102 |
| 096, 097 | Preflight gate before paid runs; `.gitignore` for every `.env*` file (after a key spill in a local commit) | Merged, PRs #103 and #104 |
| 098 | D37 firing test, 3 runs | D38 worked 3 of 3. D37 never fired: the model already knew the "missing" figure. **The review found real errors in answers the build judges had approved, almost all in content nobody asked for.** |
| 099 | D39: one settings map. The API path crashed on any blocking review | Merged, PR #107 |
| 100, 101 | Answers to the coder's questions; D40 (watchdog pace keyed by node); record repairs | Merged, PRs #108 and #109 |
| — | First two architects' transcripts in `docs/provenance/` | Merged, PR #105 |
| — | Owner's ad-hoc runs (notebook §93) | **IA question:** a research 429 was swallowed, the plan ran blind for 18 minutes, and the run blocked with no answer. **Logic question:** lost when its session ended. |

## The change of direction (2026-10-01)

The owner judged both ad-hoc runs failures, and judged that new features, the
watchdog among them, were muddling the vision. The analysis agreed:

| | 09-26 (084, 085) | Since 09-29 (7 runs) |
|---|---|---|
| Shipped an answer | **2 of 2**, about 3 minutes and 6 cents each | **0 of 7** |
| Lineup (architect / judge) | inkling-small / engineering model | mimo-v2.6-pro / kimi-k2.5 |
| Single plan call | 23–47 s | 102–1,097 s |
| Judging | 92–121 s | 972–3,078 s |

Over the same period, **8 of the architect's 10 commands were instrument or
process work.** The decisions that followed:

1. **D41, the freeze** (confirmed by the owner). No new harness mechanisms until
   a **golden set** passes at least 5 of 6, except fixes for silent failures
   and the measurement needed to score the set.
2. **The golden set.** Five questions written by an external model that knew
   nothing of the harness, plus the owner's logic question, plus the owner's IA
   question as a side test. The architect wrote and checked the keys
   (`evals/golden/`): every figure re-derived, both regulations checked against
   their text, and a self-test proving that right answers pass and listed
   wrong answers fail.
3. **One measurement (102):** the golden set on the current code with the
   09-26 lineup, within $0.50. **Status at the time of writing:** BLOCKED,
   because the preflight gate refuses 3 of the 09-26 pins. Two of those served
   live on 09-26, so the gate itself looks wrong.

## The architect's errors, on the record

- 094's request kept a clause that contradicted its own corpus, and the review
  flagged it as critical.
- 098's list of expected paths missed "the model already knows it".
- `figures_present` searches the grounding, not the answer. The 094 command
  relied on it, and it could never have scored the answer.
- 094's success was stated as "correct" when it was "correct on a 7-item key".
- A regulation's wording was recalled wrongly; the source text caught it before
  the key was written.
- **Instrument work was allowed to crowd out the outcome.** That is the error
  the owner named.

## What the field already knows, and the owner's point

- **Spend effort by difficulty** (test-time compute research). Easy questions
  gain nothing from a heavy pipeline, which is why a fast path is missing.
- **Self-correction without reliable feedback degrades.** That matches 094's
  rework.
- **A panel of diverse cheaper judges can beat one large judge.**
- **Multi-agent failures cluster in specification, verification and
  termination.**
- **Always compare against a simple baseline.** The harness has never been
  measured against one direct call of the same model, and that measurement is
  proposed next.

**The owner's point:** most of this research is 2–3 years old, which in AI terms
is a long time. Treat it as hypotheses to test on our own runs, not as law.
Where it still holds, build around it; where it has aged, that is an
advantage to use.

## Open items

- 102 is blocked on the preflight gate's pin matching. The architect's
  decision is in command 103.
- A direct-call baseline (arm 0) is proposed. It is cheap, and the freeze
  allows it as measurement.
- After the golden result, by evidence: a re-pin for speed (the owner's
  decision), a fast path as the default, research-first answers for lookup
  questions, and loud grounding failures.
- PR #95 (081) is still open and red.
