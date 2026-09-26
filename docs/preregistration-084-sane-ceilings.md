# Pre-registration: full run with sane ceilings + failover (2026-09-26, owner-ruled, no command file)

## Primary question

Does a full engineering-rnd run reach a workflow terminal with every
ask inside its serving's window — Inkling-small planning via
DeepInfra, GLM-5 building via failover-first, Flash triaging via
Alibaba?

## What changed since 083 (config, owner-set)

- 083 (failover open, $2.00 cap, spent $0.02): failover WORKS — no
  404, router served a 204800-window GLM-5 door. Then the 250000
  output ask 400d on arithmetic (6318 prompt + 250000 ask >
  204800 window). Committed (627d4f7).
- Owner trimmed VALIDATE/ESCALATION/SEARCH ceilings to inside real
  windows. Preflight 15/15. Pins unchanged (Inkling/DeepInfra,
  GLM-5/StreamLake-first, Flash/Alibaba). Code unchanged: all
  ceilings wired, failover flag live, suite 1018 green.

## Budget arithmetic (Ruling D25: sized, not defaulted)

083 spent $0.02 in 6 calls. All asks now fit their windows, so spend
goes to tokens, not refusals. Envelope: fresh $2.00 owner-approved;
caps --max-spend 2.00 --max-spend-sweep 2.00. Timeout 1800. A spend
stop is itself a finding.

## Registered prediction (verbatim)

THE RUN COMPLETES. Rationale: every death to date is apparatus, and
every apparatus fault is now removed — 16k default (wired), 404
filter (failover), 250k arithmetic refusal (trimmed ceilings),
rate-limit (transient, M3 abandoned), wrong slot (-071). Inkling
emits (three readings); GLM-5's door opens (probe + 083 failover).
The loop itself has never failed. If the run ESCALATES WITH A
DIAGNOSIS, confirmed in the favourable direction (honest BLOCKED at
539.7s post-fix). Only a NEW apparatus fault refutes.

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
count, fold detail; served_by with versioned answering ids (failover
servings named if any); provider_failures; trace + mirror; n=1 and
the $2.00 envelope.
