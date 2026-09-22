# Architecture — the graph engine

Load when touching `graph/`, `engine/`, node scheduling, loops or gates.

## The request path

```
POST /api/workflows            autornd/api/routes.py
  → WorkflowEngine.execute()   autornd/engine/workflow.py:1  (DB row, status column,
                                 PhaseResult rows, episodic memory afterwards)
  → GraphExecutor(spec, runner, settings_lookup).run(request)
                               autornd/graph/executor.py:124,351
      loads workflows/<name>.yaml      autornd/graph/spec.py:128
      evaluates when / condition / until  autornd/graph/conditions.py:82
  → PhaseRunner, dispatched by name   autornd/graph/adapter.py:168
      kind: ai     → engine/phases.py → specialists/registry.py → routing/openrouter.py
      kind: check  → graph/checks.py   (FREE — no model call)
      kind: gate   → boolean over prior node outputs; may end the run or route
  → ExecutionState{outputs{node_id: verdict}, trace[StepRecord], status, reason}
```

`engine/workflow.py` is on the request path and owns persistence. It reads like
legacy and is not — a design doc once ordered it deleted. `tests/test_live_wiring.py`
pins it.

## Three node kinds

| kind | behaviour |
|---|---|
| `ai` | one or more model calls via `PhaseRunner._phase_<prompt>` |
| `check` | a free deterministic function from `checks.registry` (`graph/checks.py:43`) |
| `gate` | boolean over prior outputs; `on_fail` names **either** a terminal status **or a node to route to** |

Node fields (`autornd/graph/spec.py:76`): `id, kind, depends_on, when, tier,
tier_when, specialist, prompt, schema, max_tokens, check, args, condition,
on_fail, on_fail_reason, body, until, max_iterations, on_exhausted,
on_exhausted_status`.

## Loops, and the mistake they cause

A node with `body` is a loop over that sub-sequence until `until` holds or
`max_iterations` is reached. `max_iterations` may **name a setting**, resolved at
run time. **Every loop must declare a bound at load time** — review and implement
can disagree forever, and the graph is not allowed to express that.

**A loop OWNS the nodes in its `body`** (`autornd/graph/spec.py:22,154,202`).
Ownership takes them off the top-level schedule: they run because the loop runs
them, never because their dependencies were satisfied. The same is true of a
loop's `on_exhausted` target and of a gate's `on_fail` target when it names a node.

This cost a real regression: adding `review` to a rework loop's body **deleted the
first review from the pipeline**, and took the gate depending on it with it. The
symptom is a silently shorter pipeline, not an error. **A phase that must run both
in the main flow and inside a loop needs two node ids** — same prompt, same tier.
That is why `review` and `rework_review` both exist.

## Gates route, they don't only stop

`on_fail: review_rework_loop` sends work back through implement → validate → a
fresh review, and it ships only when every judge agrees. Before this, a blocking
review ended the run with its findings unread — three traces in four died there.
Routing reuses the loop handoff path, so a closed gate and an exhausted loop reach
a recovery sub-graph the same way.

## All judges agree, not just the validator

`judges_agree` (`autornd/graph/checks.py:139`) folds every judge a loop body
produced — `implement.green`, `validate.green`, `coverage.passed`,
`consistency.passed` — into one boolean, and the build loop exits on the fold.
The old exit let a run stop satisfied while the domain reviewer had already
flagged a critical concern; validate turned out to be the judge that was wrong.
The fold records **which judge dissented**, per iteration.

## Conditions are a grammar, not `eval`

`autornd/graph/conditions.py` accepts exactly: `<dotted.path> <op> <literal>`,
`<path>` (truthiness), `not <path>`. Ops: `== != < <= > >= in`. **A missing path
raises** (`conditions.py:56`) — a typo'd `when` that silently skipped a node would
be worse than a loud failure. A test asserts `__import__('os').system(...)` is
rejected.

## Specialist rosters

`specialist:` takes a concrete role name or a roster token: `assigned` (everyone
triage assigned, in parallel), `builders` (assigned minus whoever validates),
`peers` (builders other than the lead), `lead` (the domain lead), `reviewers`
(the risk-scaled review team, `engine/review_composition.py`).

## Everything produced is text

Specialists have no filesystem, shell or repository, and every prompt says so
explicitly via `SPECIALIST_OUTPUT_CONTRACT`
(`autornd/specialists/registry.py:101,136`). Both halves are needed: producing
phases are told their response *is* the deliverable, and assessing phases are told
"it has not been run" is not a defect. Without both, a capable model correctly
reports it cannot reach your filesystem and the validator correctly rejects an
implementation that does not exist — burning every iteration before escalating.

**Corollary for plans:** success criteria must be verifiable *by reading the
implementation*. "reconnect loop applies exponential backoff capped at 60s with
jitter" is checkable; "reconnects within 30s in production" is not, and stalls the
loop forever. A plan that cannot state real criteria returns `ready: false`.
