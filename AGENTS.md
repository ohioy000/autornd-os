# AutoRnD-OS — the protocol

**This file is the protocol.** There is exactly one copy of it (convention 24). `CLAUDE.md` is the
repo's *derived working rules* — how code is written here — and carries a summary of the
permission boundary that points back to this file. Where the two differ, **this file wins**.
`tests/test_protocol_file.py` scans the tree by content for a second copy. Orientation, in order:
this file, then `HANDOVER.md`, then the last two sections of `docs/handover-review.md`.

AutoRnD-OS is a multi-model agentic harness for engineering R&D; tiers are named by *job*, never by
vendor. **`HANDOVER.md` is the state of record; its §6 measured facts set nearly every constant.**

**We work through one shared GitHub repository, `https://github.com/ohioy000/autornd-os`.** Its `main` is the only source of
truth. Each agent works in its own folder (the advisor in `/home/jb/autornd-os`, the executor in
`/home/jb/autornd-os_clone`), fetches from GitHub, pushes its branch there and delivers by pull
request. Nothing passes between the folders except through GitHub.

## Who decides what

| role | owns | in practice |
|---|---|---|
| **advisor** | designs and **rules**: any change to what the harness *concludes* | writes rulings, and each command as an exact task file; reviews each delivery against its task file; merges verified PRs; never pushes to main, never edits `.env` |
| **executor** | **measures and implements**: a ruled design, instrument repair, and what the measurement said — including when it contradicts the ruling | follows the task file exactly, task by task; opens the response first, works on a branch, proves each fix with a break-proof, re-derives every count, opens the PR |
| **owner** | money, serving pins, standing config; the only one who edits `.env` | authorises every paid run before the spend; ratifies pins and key versions |

**A new executor proposes; it does not rule.** Where a ruling is silent and the answer changes what
the harness would conclude, record the question and ask — do not decide it and carry on. A
measurement that contradicts its command is reported as it read (convention 18), and the work holds
until the advisor rules.

### The permission boundary

The line is **whether a change alters what the harness would conclude, or only how reliably it
reaches a conclusion.**

- **Executor's, no ruling needed — *instrument repair*.** Crash-proofing a phase against
  well-formed-enough model output; retry wiring; retention and accounting; making a counter count
  what it claims to count; fixing a measurement that reports something other than what it observed.
- **Advisor's, needs a ruling — *behaviour change*.** Verdict semantics (what a field means, what is
  required, what is coerced); loop wiring and exit conditions; gate routing; prompt text that steers
  judgment; scorer and key semantics; anything that changes which work ships.

Worked examples: resolving `green` from `red_cause` was **ruled** (011); counting how often that
resolution fires was **repaired as found** (011). Folding a criterion-keyed `evidence` object was
**ruled** (012); attributing schema rejections to the serving that produced them was **repaired**.

## Non-negotiables (condensed from `HANDOVER.md` §4.4, with the measurement behind each)

1. **Measurement comments are sacred.** Read the comment beside a constant before touching it.
2. **Free checks before paid calls.** Always.
3. **Typed verdicts; gates test booleans.** Never parse English for control flow.
4. **No `eval` in workflow files.** Conditions are one deliberate grammar.
5. **Enums are default vocabularies, not limits** — profiles declare their own (§6.14).
6. **No hardcoded model names or prices** outside the lab notebook (`tests/test_docs.py`).
7. **Test doubles must bill** (`client._account`). A free double hid a real accounting bug.

### Convention digest — §4.4 numbers 17–24 and 26–28

| # | rule |
|---|---|
| **17** | When a fix invalidates a test, ask which of the two is wrong **first** — a test asserting current behaviour may be the bug, written down. |
| **18** | A change that alters per-run work **re-derives the harness budgets in the same change**. *An instrument reading is a reading, not a diagnosis*: a timeout, a zero score, a refused lookup and a 403 are facts about the apparatus until something rules the apparatus out. |
| **19** | **No deletion ruling without a recorded reference check** — grep importers and callers, record the result. A blueprint once ordered the API's own entry point deleted. |
| **20** | **Required fields are informationally independent fields.** A field the contract derives from another is normalized loudly and counted, never demanded. |
| **21** | **Shape variance that preserves information is coerced; variance that loses it is rejected**, and counted. **Exhibits precede leniency.** |
| **22** | **An instrument's test simulates the condition it watches, end to end**, proven by breaking the line it guards (a break-proof). Five instruments in two blueprints under-reported against a green suite; an instrument written in the same commit as its fix gets no run of its own to prove it on. |
| **23** | **A serving sweep measures compliance first, then iterations to termination, then speed.** Never at n=1. |
| **24** | **A fact about the repo is generated or guarded, never hand-stamped.** A stamp records when someone last believed a number, not that it was right. |
| **26** | **An instrument's report states what it measured and nothing more.** A reading that can be mistaken for a stronger claim is a defect in the instrument, not its reader. |
| **27** | **A repetition of a plan-dependent contrast is a second sample, never a confirmation.** A ruling asking for `n=2` says which of the two it wants. |
| **28** | **An instrument asserts that it computed its subject before it asserts anything about it.** No evidence must never be reported as no problem. |

## Working rules

```bash
.venv/bin/python3 -m pytest tests/ -q     # ~90 s, free, no network — run BEFORE and AFTER
```

**Repository capability.** The executor holds write capability (Ruling D13): branches, commits,
pushes, pull requests. The advisor commits its own commands and design records on `arch/` branches
and opens PRs for them. Where the advisor cannot commit, the executor carries a command file
verbatim — carriage, not authorship, and the commit message says so.

**Merges.** The advisor merges a PR after verifying it by probe, with all five CI checks green and
the head commit list re-read just before merging. The executor merges when CI is green AND every
acceptance criterion is demonstrated — a permission withdrawn if a guard is found that cannot fail
or cannot pass (conventions 22, 28). Ordered merges stop at the first refusal. Owner-only regardless
of CI: anything touching `.env` or standing config; branch protection; anything whose acceptance CI
cannot see (a live paid run result, a claim about provider behaviour).

**Invariants:** no force-push, except `--force-with-lease` on your own unmerged PR branch after a
rebase a review ordered; no history rewrite on main or a merged branch; no deletion on a protected
branch; no direct push to main; do not stack branches — merge each PR before opening the next —
unless a review orders a stack, and then each tip carries its own re-derived counts and the response
states the merge order (both exceptions owner-ratified 2026-10-11); **no git operation while a paid
run is in flight** (that caused the -010 trace loss); a paid run never starts from a dirty working
tree.

- **Suite green before and after; CI green before finishing.** **Pre-register a paid run and commit
  it first** — the evidence the prediction preceded the result; a wrong one is reported as wrong.
- **Departures go in the record** (notebook `§n.2`, response `deviations`): what changed, what was
  left undone, and what the ruling missed — often the instrument was broken, not the hypothesis.
- **Counts are re-derived from collection, never trusted** — after a rebase too: two branches each
  right at their own tip can merge into a wrong total (`tests/test_handover_truth.py` guards them).
- **Commit messages are prose that names the measurement.** Single-quote cost figures or escape the
  dollar: `$0.06` through `bash -c` reads `(bash.06)` (convention 26).
- **Private corpora never enter this repo** (`profiles/milkhouse.yaml` stays untracked); experiments
  isolate the knowledge store (`_isolated_store()`). `--max-spend` caps one scenario-run on the
  search tier, `--max-spend-sweep` (default $1.00; `none` disables) the invocation. **Pin servings
  before believing a live reading** (§6.1, §6.11).

### The G-gates — what the owner owns

| gate | rule |
|---|---|
| **G-1 — key hygiene** | API keys move **only** through the terminal and `.env`, never into chat in either direction. A key seen in a transcript is rotated, not reused. |
| **G-2 — pin ratification** | A serving pin is proposed with its evidence and **ratified by the owner in one line**. Experiments run the proposal env-prefixed; the standing line is the owner's. |
| **G-3 — `.env` and standing config** | The owner edits `.env`. Nobody else does, and a finding that waits on one says so. |
| **paid runs** | Authorised by the owner before the spend, with a ceiling. Repetitions beyond a ruling are a logged departure carrying their cost and what they de-risked. |

## How the advisor reviews

- **Probes come before handover.** For every property a ruling promises, a small provider-free script
  tries to break it in a scratch worktree — network blocked, placeholder keys, the worktree's own
  code first on `sys.path` — derived from the ruling's falsifier, not the command's test list, while
  the task file can still change. Exhibits: 108–111 met every acceptance criterion with CI green and
  probes found four real defects; the 2026-10-10 round found three more (#160, #168, #171).
- **A full delivery is not redone.** When a delivery matches its task file byte for byte and CI is
  green, the advisor merges it. The suite is not re-run and the probes are not repeated; only a
  deviation is reviewed by probe. Exhibit: commands 124, 127, 128 and 129 were delivered in full,
  and re-checking them found nothing the byte comparison had not.
- **A defect is a hold with the exact change required**, as a complete prompt with the evidence
  quoted. **Every fix names the measurement it serves**; other apparatus work is parked, and after a
  behaviour change lands only run-blocking fixes go in until it is re-measured.
- **Keys are frozen and versioned** (D44): a key change is a new version, every run is re-scored
  under it, and both figures are reported side by side. **Two hand readings are primary; the scorer
  is a screen** (D50).

## Where things live

| path | what it is |
|---|---|
| `HANDOVER.md` | **the state of record.** §0 vision · §2 architecture · §4.2 bug ledger · §4.4 conventions · §5 frontier · §6 measured facts · §7 orientation |
| `docs/handover-review.md` | **the lab notebook.** §0 the blueprint protocol; every blueprint and ruling pasted verbatim *before* execution, with its execution record. A claim in the state must trace to a run here; when they disagree, the notebook is usually right |
| `docs/reviews/` | design records and reports: rulings' full reasoning, stage reports, outside reviews |
| `docs/traces/` | **committed measurement records** — the JSONL of every live run cited anywhere |
| `docs/successor-prompt.md` | the prompt that opens a new executor's session |
| `evals/results/` | local run output, gitignored |
| `workflows/*.yaml` · `profiles/*.yaml` | the pipelines, as data · vocabularies, roles, per-domain checks |
| `.orchestration/` | **the command channel** (below) |

## Orchestration — the command channel

Work passes through the repository, not a transcript. **This documents channels, not authority.**

| direction | path | written by |
|---|---|---|
| work out | `.orchestration/commands/<command_id>.json` | the advisor, one file per command, one command per commit, touching nothing else |
| work back | `.orchestration/responses/<command_id>.response.json` | the executor |

**The response directory is the advisor's only view of what has been done**: no response file, not
executed. The template (`.orchestration/COMMAND_TEMPLATE.json`) and `.orchestration/README.md`
govern shape; this section governs authority and wins where they differ. The template's
**always-in-scope set** (`.orchestration/responses/`, `HANDOVER.md`, `README.md`, `AGENTS.md`,
`CLAUDE.md`, `.claude/context/testing.md`) is **permission, not instruction** — one new test file
turns the count guards red (`tests/test_command_template.py` keeps the set honest).

- A command is **new** iff its command file exists and its response does not; process in
  `command_id` order. The executor **never modifies** `.orchestration/commands/`.
- The response is committed `IN_PROGRESS` **before the work starts** (the commit is the evidence the
  work had not started), then updated in place. Response and code travel on the **same branch**.
  Nobody rewrites another agent's message.
- **On arrival, before executing, the executor checks the command file itself.** **First:** if
  `parent_id` is non-null, a response file for that parent **MUST** exist at
  `.orchestration/responses/<parent_id>.response.json`; a missing one is a `BLOCKED` report naming
  it, and the advisor re-issues the command re-parented (repair commands carry `parent_id: null` and
  name the file they repair). **Second:** every command carries a
  **non-empty `preconditions` array** — an absent or empty array is a `BLOCKED` report on arrival,
  which is the report the channel exists to produce.
- A response carries at minimum `command_id`, `executed`, `head_before`, `head_after`, `results`,
  `deviations` and `questions_for_advisor`; status is `IN_PROGRESS`, `DONE`, `PARTIAL`, `BLOCKED`,
  `FAILED`, `REJECTED` or `NO_ACTION` (an unfired trigger, citing what settled it).
- **When a HEAD pin and `IN_PROGRESS`-first collide**, the HEAD guard wins: read at the pinned sha,
  then write the response, and record the missing `IN_PROGRESS` commit as a departure.

**A command's evidence is checkable before it is acted on.** Each `preconditions` entry is a
`{"command", "expected"}` runnable check, and a command citing a sha, a file path, or a measured
figure **MUST carry one verifying it**. The executor runs every precondition before acting and
aborts on any failure: **a precondition failure is a `BLOCKED` report, not a deviation** — nothing
was done differently, because nothing was done. Exhibit: a command once cited an entire paid run
that never happened; the executor falsified every artifact against the tree first
(`.orchestration/responses/ARCH-20260921-002.response.json`). **A command whose evidence cannot be
checked against the tree is not evidence.**

### How a command is written — the owner's standard

The advisor thinks; the executor works. The advisor does the hard work, so the executor never has
to work anything out: it follows exact tasks and does not design or interpret (owner, 2026-10-25).

- **Every command has a task file,** `.orchestration/prompts/<command_id>.md`, committed with its
  command JSON. The JSON points at the task file, and the task file governs the detail.
- **Direct and sectional** (owner, 2026-10-14): a short purpose, the rules for every task, then
  TASK 0 (branch, preconditions, response `IN_PROGRESS`) to TASK N (finish), then the STOP
  conditions.
- **Each task is fine-tuned** (owner, 2026-10-21): FILES; DO, with exact find → replace text; CHECK,
  an exact command; EXPECT, its exact output; COMMIT, the message. Exact strings, never "...".
- **Complete and self-contained,** with the evidence quoted; never a delta to append (owner,
  2026-10-10).
- **Every EXPECT is real:** the advisor replays the task file from its own text on a fresh copy of
  main and records each CHECK's output before handover.
- **Plain words, short sentences** (owner, 2026-10-25).
- **The owner hands it over in one line:** "Read `.orchestration/prompts/STARTUP.md`, then do
  `.orchestration/prompts/<command_id>.md` task by task."
- **The style is fixed.** The advisor does not change the task-file format, the prompt style or these
  rules as a whole. A problem gets one fix, in place. A change to the style or the rules is the
  owner's to make (owner, 2026-10-29: such changes make the project harder and cost more tokens).

## Practical notes

- **Opening a session:** follow `docs/successor-prompt.md` (the owner pastes it) in order, run the
  suite, report the count, and change nothing until the owner confirms. A new architect starts with
  `.orchestration/prompts/STARTUP-ARCHITECT.md`; a new executor with `.orchestration/prompts/STARTUP.md`.
- **⚠️ Meter epoch:** cost accounting was broken before commit `b4cd89f` (research, context and
  rerank calls bypassed it). **Any cost figure predating `b4cd89f` is understated by 2.6×–295×.
  Never cite one.** Re-measure.
- **Current shape:** 87 test files; `graph/` is the engine, workflows are **YAML data**, experiments
  live in root `evals/` with runner code in `autornd/evals/`; `engine/workflow.py` is the API entry.
- **Discipline:** read before search (at most three discovery calls before opening a file in full);
  parallel reads are fine, parallel writes and side effects are not; when a call starts repeating,
  stop and report — the -010 trace loss began as a repeated git operation; match the owner's shell;
  a tool call is a structured call, never prose pretending to be one.
