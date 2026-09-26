# Pre-registration: full run on Inkling-small (2026-09-26, owner-ruled, no command file)

## Primary question

Does a full engineering-rnd run reach a workflow terminal with
Inkling-small on architecture — the first (model, serving, ceiling)
triple since Prime that opens the door AND emits?

## What changed since 079 (nothing but scale)

- 079 probe (plan-probe, $0.50 cap, spent $0.02): completed 1/1, plan
  ready with 6 criteria and 2 HONEST blockers, DeepInfra fp8, 8.7k
  completion against the 112k ceiling. Door opens, text comes out,
  firewall holds. Committed (dbcba2b, new ledger row 1/1 completed).
- Pins unchanged (preflight 14/14): architecture
  `thinkingmachines/inkling-small` via DeepInfra, engineering Flash
  via Xiaomi, triage Flash via Alibaba. Code unchanged: all ceilings
  wired, suite 1017 green.

## Budget arithmetic (Ruling D25: sized, not defaulted)

Probe plan call $0.011 for 8.7k completion — ~100x cheaper than
Prime's $1.25 for the same phase. A full build + rework at Inkling
prices should land well under $0.50; $2.00 covers 4x that. Envelope:
fresh $2.00 owner-approved; caps --max-spend 2.00 --max-spend-sweep
2.00. Timeout 1800. A spend stop is itself a finding.

## Registered prediction (verbatim)

THE RUN COMPLETES. Rationale: (1) the probe proved door + emission +
honesty on this exact triple; the full workflow adds implement (Flash,
one green on record), judges (deterministic), and review (wired
ceilings, no truncation class left); (2) every prior full-run death
was apparatus now removed — 16k default (wired), wrong slot (-071),
404 filter (single-door serving), refused lookup (trimmed search).
No apparatus failure remains on the path. If instead the run
ESCALATES WITH A DIAGNOSIS, confirmed in the favourable direction
(the request is hard; honest BLOCKED at 539.7s post-fix). If it dies
on a NEW apparatus fault, the prediction is refuted and the new
fault is the finding.

## Run shape

- Scenario: evals/scenarios/convergence/conv_numeric_consistency.yaml
  (same registered scenario throughout; a modified request would not
  be a replication).
- Workflow: engineering-rnd. Repeat: 1. Timeout: 1800.
- Isolation: knowledge store isolated. No git operation while in flight
  (Ruling D13). Tree clean at commit.
- Departure (owner-authorized): no command file; owner ruled alone
  with full go-ahead. Pre-registration commit is the precedence
  evidence.

## What will be reported

Workflow terminal verbatim; per-criterion shape table, abstention
count, fold detail; served_by with versioned answering ids;
provider_failures; trace + mirror; n=1 and the $2.00 envelope; spend
vs the $0.50 probe-implied projection.
