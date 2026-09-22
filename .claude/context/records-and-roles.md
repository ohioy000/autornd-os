# Who decides what, and where it gets written down

Load when deciding whether a change is yours to make, or when recording one.
The full protocol is `AGENTS.md` (currently also at `thisisnottheCLAUDE.md`).

## Three roles

| role | owns |
|---|---|
| **advisor** | designs and **rules**. Any change to what the harness *concludes* is theirs. |
| **executor** | **measures and implements**. Mechanical execution of a ruled design, instrument repair, and reporting what the measurement actually said — including when it contradicts the design. |
| **owner** | money, pins, and standing config. The only one who edits `.env`. |

**An executor proposes; it does not rule.** Where a design is silent and the answer
changes what the harness would conclude, record the question and ask.

## The permission boundary

The line is **whether the change alters what the harness would conclude, or only
how reliably it reaches a conclusion.**

- **Yours, no ruling needed — *instrument repair*:** crash-proofing a phase against
  well-formed-enough model output; retry wiring; retention and accounting; making a
  counter count what it claims to count; fixing a measurement that reports something
  other than what it observed.
- **Needs a ruling — *behaviour change*:** verdict semantics (what a field means,
  what is required, what is coerced); loop wiring and exit conditions; gate routing;
  prompt text that steers judgment; anything that changes which work ships.

Worked examples: resolving `green` from `red_cause` was **ruled**; counting how
often that resolution fires was **repaired as found**. Folding a criterion-keyed
`evidence` object was **ruled**; attributing schema rejections to the serving that
produced them was **repaired**.

## Where the record lives

| path | what it is |
|---|---|
| `HANDOVER.md` | **the state of record.** §2 architecture · §4.2 the bug ledger · §4.4 conventions · §5 the frontier · §6 measured facts |
| `docs/handover-review.md` | **the lab notebook.** Every design pasted verbatim *before* execution, each with its execution record afterwards |
| `docs/traces/` | committed measurement records — the JSONL of every live run cited anywhere |
| `docs/preregistration-*.md` | predictions, committed before the spend they predict |
| `.orchestration/` | the command channel |

**`HANDOVER.md` is the state; `docs/handover-review.md` is the evidence.** A claim
in the first should be traceable to a run in the second. When they disagree, the
notebook is usually right and the state is stale.

**Departures go in the execution record**, with reasons: what you did differently,
what you deliberately left undone, and **what execution found that the design
missed**. That last part is where most of the value has landed — six designs found
the instrument broken rather than the hypothesis wrong.

## The command channel

| direction | path | written by |
|---|---|---|
| work out | `.orchestration/commands/<id>.json` | the advisor — one file per command, one command per commit |
| work back | `.orchestration/responses/<id>.response.json` | the executor |

- **The response directory is the advisor's only view of what has been done.** A
  command with no response file has not been executed, whatever a transcript says.
- A command is **new** iff the command file exists and the response file does not.
  Process in `command_id` order.
- **Never modify `.orchestration/commands/`.**
- The response is committed with status `IN_PROGRESS` **before the work starts** —
  the commit is the evidence that the work had not started. Then updated in place.
- Response and code travel on the **same branch**, so the diff and the report cannot
  be read apart.
- Statuses: `IN_PROGRESS`, `DONE`, `PARTIAL`, `BLOCKED`, `FAILED`, `REJECTED`,
  `NO_ACTION`. A response carries at minimum `command_id`, `executed`,
  `head_before`, `head_after`, `results`, `deviations`, `questions_for_advisor`.

**Check the command before executing it.** A non-null `parent_id` must have a
response file, or it is a `BLOCKED` report naming the missing file. Every command
carries a **non-empty `preconditions` array** of runnable `{"command", "expected"}`
checks; an absent or empty array is `BLOCKED` on arrival. Run every precondition
**before acting** and abort on any failure. **A precondition failure is a `BLOCKED`
report, not a deviation** — nothing was done differently, because nothing was done.

Why: a command once cited an entire paid run — call counts, dollar figures, traces,
a test file, two commit shas — and **none of it existed**. The executor falsified
every artifact against the tree before writing a word of record. Had it not, the
bug ledger would have closed a defect on measurements never taken. **A command
whose evidence cannot be checked against the tree is not evidence.**

**The two rules that collide:** a command pinned to a specific HEAD cannot also
have an `IN_PROGRESS` commit written first, because the commit moves HEAD off the
pin. **The HEAD guard wins** — take the reading at the guarded sha, write the
response, and record the missing `IN_PROGRESS` commit as a departure.

## No deletion without a recorded reference check

Grep for importers and callers and **record the result**. A design document once
ordered the API's own entry point deleted.
