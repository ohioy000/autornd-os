# Pre-registration: live retest with the plan ceiling wired (2026-09-26, owner-authorized, no command file)

## Primary question

Does a live run reach a workflow terminal — completed, blocked, or
escalated-with-diagnosis — rather than a runner timeout, now that the
plan node's token ceiling actually reaches its call?

## What changed since 072 (the apparatus, not the loop)

- 072 died at `plan`: three architecture calls each filled 16384
  completion tokens and truncated mid-JSON ($0.44, zero verdicts), while
  `.env` granted `PLAN_MAX_TOKENS=112768` and the workflow declared
  `max_tokens: plan_max_tokens` on the plan node.
- Fix (committed `dd8fe3a`, pushed): `_phase_plan` threads
  `self._max_tokens(node)` into `run_plan`, which resolves a named
  setting or falls back to `plan_max_tokens`; `Node.max_tokens` widened
  to `int | str`. New `tests/test_node_token_ceilings.py` (4 tests):
  3 of 4 fail pre-fix on stash, 4 of 4 pass after. Suite 1005 green.
- Pins unchanged: engineering `xiaomi/mimo-v2.6-flash` via Xiaomi,
  architecture `z-ai/glm-5.3-prime` via Alibaba (preflight 14/14 in
  clean env). Prime has never had its 112k; Flash has never had a
  single call. Neither has had a fair reading.

## Budget arithmetic (Ruling D25: sized, not defaulted)

Same sizing as -071/072: observed -049 cycle 528s for four calls; a
convergent run needs plan + implement + domain_review + coverage +
consistency + validate + judges, plus a rework cycle if the fold
dissents. --timeout 1800 is ~2x the observed cycle. Envelope: fresh
$1.00 owner-approved; caps --max-spend 1.00 --max-spend-sweep 1.00.
Caveat, stated: Prime at 112k is output-heavy (072: 6193 prompt vs
49152 completion, 8:1 facing the $8.80/M side), so per-call cost may
exceed 072's $0.44 — the $1.00 cap is exact either way, and a spend
stop would itself be a finding.

## Registered prediction (verbatim)

THE RUN REACHES A TERMINAL, and it is ESCALATED WITH A DIAGNOSIS rather
than completed. Rationale: (1) both prior deaths were apparatus, not
loop — -071's validate burn (wrong slot for a reasoner), 072's plan
truncation (right slot, 16k leash with 112k configured) — and both are
now repaired without touching any verdict semantics; (2) the request is
hard — the post-fix comparator reached honest BLOCKED at 539.7s. If the
run COMPLETES, refuted in the favourable direction. If it times out at
1800s with the ceiling wired, the deadline is not the defect and the
loop is.

## Run shape

- Scenario: evals/scenarios/convergence/conv_numeric_consistency.yaml
  (same registered scenario as -049/-071/072; a modified request would
  not be a replication).
- Workflow: engineering-rnd. Repeat: 1. Timeout: 1800.
- Isolation: knowledge store isolated. No git operation while in flight
  (Ruling D13). Tree clean at commit.
- Departure (owner-authorized): no command file; run proceeds on verbal
  authorization, recorded here instead of a response IN_PROGRESS commit.
  Pre-registration commit is the precedence evidence.

## What will be reported

Workflow terminal verbatim (or stop_reason if none); per-criterion shape
table, abstention count, fold detail on empty seat; served_by with
versioned answering ids; trace + mirror; n=1 and the $1.00 envelope.
