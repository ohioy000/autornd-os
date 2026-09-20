# AutoRnD-OS — the executor's protocol

**This file is the protocol.** `CLAUDE.md` is a symlink to it, so there is one
copy and it cannot drift (convention 24). If you are an agent working in this
repo, read this file, then `HANDOVER.md`, then the last two sections of
`docs/handover-review.md`.

A multi-model agentic harness for team work that aims to be frugal and accurate,
starting with engineering R&D. You give it an objective in prose; it classifies
the work, assembles grounding, plans, implements, validates in a loop, reviews
with a risk-scaled team, and either produces a written deliverable or escalates
with a diagnosis. Tiers are named by *job* — triage, engineering, architecture,
escalation, research, search — never by vendor: the harness is what ships, and
the model choice is the operator's. **[`HANDOVER.md`](HANDOVER.md) is the
authoritative state of record; its §6 (measured facts) is load-bearing — nearly
every constant here came from a live run recorded there.**

---

## Who decides what

Three roles, and the boundaries are not negotiable between sessions.

| role | owns |
|---|---|
| **advisor** | designs and **rules**. Writes the blueprints. Any change to what the harness *concludes* is theirs. |
| **executor** (you) | **measures and implements**. Mechanical execution of a ruled design, instrument repair, and reporting what the measurement actually said — including when it contradicts the blueprint. |
| **owner** | money, pins, and standing config. The only one who edits `.env`. |

**A new executor proposes; it does not rule.** Where a blueprint is silent and
the answer changes what the harness would conclude, record the question and ask
— do not decide it and carry on.

### The permission boundary

The line is **whether the change alters what the harness would conclude, or only
how reliably it reaches a conclusion.**

- **Executor's, no ruling needed — *instrument repair*.** Crash-proofing a phase
  against well-formed-enough model output; retry wiring; retention and
  accounting; making a counter count what it claims to count; fixing a
  measurement that reports something other than what it observed.
- **Advisor's, needs a ruling — *behaviour change*.** Verdict semantics (what a
  field means, what is required, what is coerced); loop wiring and exit
  conditions; gate routing; prompt text that steers judgment; anything that
  changes which work ships.

Worked examples from the record: resolving `green` from `red_cause` was **ruled**
(011); counting how often that resolution fires was **repaired as found** (011).
Folding a criterion-keyed `evidence` object was **ruled** (012); attributing
schema rejections to the serving that produced them was **repaired** (012).

---

## Non-negotiables

Condensed from `HANDOVER.md` §4.4, which holds the full list and the measurement
behind each one.

1. **Measurement comments are sacred.** Read the comment beside a constant
   before touching it — it usually names the live run that set it, and often a
   previous attempt that failed.
2. **Free checks before paid calls.** Always.
3. **Typed verdicts; gates test booleans.** Never parse English for control flow.
4. **No `eval` in workflow files.** Conditions are one deliberate grammar.
5. **Enums are default vocabularies, not limits.** `Domain` and `SpecialistRole`
   are starting sets; profiles declare their own. Measured: the freedom to name
   a role is worth more than the roles a profile declares (§6.14).
6. **No hardcoded model names or prices.** Rates come from the provider
   catalogue. Selection is anonymous, the record is not: no model id in code,
   config defaults, profiles, workflows or user-facing docs — but `HANDOVER.md`
   §6 and `docs/handover-review.md` are the lab notebook and name what they
   measured. `tests/test_docs.py` enforces this.
7. **Test doubles must bill** (`client._account`). A free double hid a real
   accounting bug.

### Convention digest — §4.4 numbers 17–24, one line each

The full text and the measurement behind each is in `HANDOVER.md` §4.4. These
eight are the ones a new executor trips over.

| # | rule |
|---|---|
| **17** | When a fix invalidates a test, ask which of the two is wrong **first** — a test asserting current behaviour may be the bug, written down. |
| **18** | A change that alters per-run work **re-derives the harness budgets in the same change**. And: *an instrument reading is a reading, not a diagnosis* — a timeout, a zero score, a refused lookup and a 403 are facts about the apparatus until something rules the apparatus out. |
| **19** | **No deletion ruling without a recorded reference check.** Grep for importers and callers and record the result. A blueprint once ordered the API's own entry point deleted. |
| **20** | **Required fields are informationally independent fields.** A field the verdict's own contract derives from another is normalized loudly and counted, never demanded. |
| **21** | **Shape variance that preserves information is coerced; variance that loses it is rejected.** Counted like every normalization. **Exhibits precede leniency** — no field is made tolerant on speculation. |
| **22** | **An instrument's test simulates the condition it watches, end to end.** Five instruments in two blueprints reported less than they measured, every one against a green suite. An instrument written in the same commit as the fix it watches gets no run of its own to prove it on. |
| **23** | **A serving sweep measures three axes and latency is the least of them**: compliance first (a serving whose replies the schema refuses is disqualified regardless of speed), then **iterations to termination**, then speed. Never at n=1. |
| **24** | **A fact about the repo is generated or guarded, never hand-stamped.** A commit stamp records when someone last believed a number, not that it was right. Twelve drifts in one document is the exhibit. |

---

## Working rules

```bash
.venv/bin/python3 -m pytest tests/ -q     # ~27 s, free — run BEFORE and AFTER
```

Under Aider, slash commands and shell runs are owner-invoked or owner-approved;
the agent proposes and edits, the owner executes the git loop.

- **Suite green before and after. CI green before finishing.** Both, every time.
- **Pre-register before a paid run, and commit it first.** The commit is the
  evidence that the prediction preceded the result. A wrong prediction is
  reported as wrong, never quietly adjusted to match (convention 7).
- **Departures go in the execution record** (`§n.2`) with their reasons — what
  you did differently, what you deliberately left undone, and what execution
  found that the blueprint missed. **That last part is where most of the value
  has landed:** six blueprints found the instrument broken rather than the
  hypothesis wrong.
- **Counts are re-derived, never trusted.** Every count in the repo is generated
  or guarded (`tests/test_handover_truth.py`).
- **Commit messages are prose that names the measurement**, not bullet lists.
- **Private corpora never enter this repo.** `profiles/milkhouse.yaml` stays
  untracked; see `.gitignore`.
- **Isolate the knowledge store in experiments** (`_isolated_store()`). The eval
  suite once read a developer's local Chroma directory and every gap came back
  pre-answered.
- Pass `--max-spend` on anything touching the search tier — it is by a wide
  margin the most expensive one. It caps **one scenario-run**, not the
  invocation; `--max-spend-sweep` does that and is on by default at $1.00
  (`none` disables). With both set the sweep cap is exact.
- **Pin the servings before believing any live reading.** An unpinned tier draws
  a dozen providers inside one run, and *which* one served it decided two of this
  project's largest findings (§6.1, §6.11).

### The G-gates — what the owner owns

| gate | rule |
|---|---|
| **G-1 — key hygiene** | API keys move **only** through the terminal and `.env`. Never into chat, in either direction. A key that appears in a transcript is rotated, not reused. |
| **G-2 — pin ratification** | A serving pin is proposed by the executor with its evidence and **ratified by the owner in one line**. Experiments run the proposal env-prefixed; the standing line is the owner's. |
| **G-3 — `.env` and standing config** | The owner edits `.env`. The executor never does, and says so when a finding waits on one. |
| **repeat > 1** | Buying extra repetitions beyond a blueprint is a **logged departure carrying its cost and what it de-risked**. The exemplar: $0.09 turned a coin-flip pin into a measured one. |

---

## Where things live

| path | what it is |
|---|---|
| `HANDOVER.md` | **the state of record.** §0 vision · §2 architecture · §4.2 the bug ledger · §4.4 conventions · §5 the frontier · §6 measured facts · §7 orientation |
| `docs/handover-review.md` | **the lab notebook.** §0 the blueprint protocol; §1–§26 every blueprint pasted verbatim *before* execution, each with its execution record |
| `docs/traces/` | **committed measurement records** — the JSONL of every live run cited anywhere |
| `docs/successor-prompt.md` | the prompt that opens a new executor's session |
| `evals/results/` | local run output, gitignored |
| `workflows/*.yaml` | the pipelines, as data |
| `profiles/*.yaml` | vocabularies, roles and per-domain checks |
| `.orchestration/` | **the command channel** — work out at `commands/<command_id>.json`, work back at `responses/<command_id>.response.json`. See *Orchestration* below. |

**The shape of the record:** `HANDOVER.md` is the state; `docs/handover-review.md`
is the evidence. A claim in the first should be traceable to a run in the second.
When they disagree, the notebook is usually right and the state is stale —
that is what Blueprint 013 was for.

---

## Orchestration — the command channel

The advisor and the executor pass work through the repository, not through a
transcript. Two directories carry it, and **this section documents channels,
not authority** — the permission boundary above is unchanged by it.

| direction | path | written by |
|---|---|---|
| work out | `.orchestration/commands/<command_id>.json` | the advisor, one file per command, one command per commit, touching nothing else |
| work back | `.orchestration/responses/<command_id>.response.json` | the executor |

**The response directory is the advisor's only view of what has been done.** A
command with no response file has not been executed, whatever a transcript says.

- A command is **new** iff `commands/<id>.json` exists and
  `responses/<id>.response.json` does not. Process in `command_id` order.
- The executor **never modifies `.orchestration/commands/`**. Where the advisor
  holds no commit capability, the executor may act as transport and commit the
  command file verbatim — that is carriage, not authorship, and the commit
  message says so.
- The response file is committed with status `IN_PROGRESS` **before the work
  starts**. The commit is the evidence that the work had not started when the
  response was opened. It is then updated in place with the outcome.
- The response and the code travel on the **same branch**, so the diff and the
  report cannot be read apart.
- Nobody rewrites another agent's message, and nobody force-pushes a protected
  branch.

A response carries at minimum `command_id`, `executed`, `head_before`,
`head_after`, `results`, `deviations` and `questions_for_advisor`. Status is one
of `IN_PROGRESS`, `DONE`, `PARTIAL`, `BLOCKED`, `FAILED`, `REJECTED` or
`NO_ACTION` — the last for a contingent command whose trigger did not fire,
which still gets a file, citing the command that settled it.

**The two rules that collide, and which one yields.** A command pinned to a
specific HEAD cannot also have an `IN_PROGRESS` commit written first, because
the commit moves HEAD off the pin. The HEAD guard wins: take the reading at the
guarded sha, then write the response, and **record the missing `IN_PROGRESS`
commit as a departure**. This is written down because it happened on the
channel's first command and would otherwise be rediscovered every time.

**Departures and refutations belong in the response**, in the same spirit as
`§n.2` of the notebook: what was done differently and why, what was left
undone, and what execution found that the command missed. A measurement that
contradicts its command is reported as it read (convention 18).

**A command's evidence is checkable before it is acted on.** A command that
cites a sha, a file path, or a measured figure states it in a form the executor
can verify first — a runnable check whose failure aborts the command, the way
`ARCH-20260919-001`'s HEAD guard did. Rationale, 2026-09-20: a command cited an
entire paid run — call counts, dollar figures, traces, a test file, two commit
shas — and **none of it existed**; the executor falsified every artifact against
the tree before writing a word of record
(`.orchestration/responses/ARCH-20260921-002.response.json`). Had it not, the bug
ledger would have closed a defect on measurements never taken.
**A command whose evidence cannot be checked against the tree is not evidence.**

## Opening a session

`docs/successor-prompt.md` is what the owner pastes to start a new executor. It
carries the orientation sequence and the division of labour above. If you are
reading this because you were just handed that prompt: follow it in order, run
the suite, report the count, and change nothing until the owner confirms.

## ⚠️ Meter epoch

Cost accounting was broken before commit `b4cd89f`: research, context and rerank
calls bypassed it entirely. **Any cost figure predating `b4cd89f` is understated
by 2.6×–295×. Never cite one.** Re-measure instead.

## Current shape

- `graph/` is the engine. Workflows are **YAML data** in `workflows/`, not a
  sequence compiled into code.
- `evals/` is in-package (`autornd/evals/`); scenarios and suites live in
  `evals/` at the root.
- 39 test files.
- `engine/workflow.py` is the API entry point: it loads the graph, runs it, and
  persists phases. The hardcoded sequencer it used to carry as the graph's
  equivalence reference is gone — the graph outgrew what a linear engine can
  represent.
