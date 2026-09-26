# Pre-registration: full run on Inkling-plan + GLM-5-build (2026-09-26, owner-ruled, no command file)

## Primary question

Does a full engineering-rnd run reach a workflow terminal with the
heterogeneous roster — Inkling-small planning via DeepInfra, GLM-5
building via StreamLake, Flash triaging via Alibaba?

## What changed since 081 (pins, owner-set)

- 081 (Inkling plan + M3 implement, $2.00 cap, spent $0.03): M3 429s
  upstream through DeepInfra (door OPENS at 112k — 13-door filter fear
  refuted; emission unobserved). Same provider served Inkling clean
  minutes earlier → model-side capacity, not provider. M3 out on
  availability regardless of benches. Committed (c3d628c).
- New pin (owner-set, preflight 14/14): engineering `z-ai/glm-5` via
  StreamLake (fp8, 128-182k max out, $0.60/$1.92). In-family with
  Prime, reasoning-optional, 8 doors, proven provider (346 ledger
  calls on the old v4-pro pin). Pin-swap typo (arch↔engineering
  crossed) caught by preflight twice, corrected, green.
- Architecture unchanged: Inkling-small via DeepInfra (probe 1/1,
  080/081 plans parsed). Code unchanged: all ceilings wired, suite
  1017 green.

## Budget arithmetic (Ruling D25: sized, not defaulted)

081 spent $0.03 in 6 calls. GLM-5 at $0.60/$1.92 vs M3 $0.28/$1.10
vs Prime ~$2.80/$8.80 — mid-priced, flagship-shaped. Envelope:
fresh $2.00 owner-approved; caps --max-spend 2.00 --max-spend-sweep
2.00. Timeout 1800. A spend stop is itself a finding.

## Registered prediction (verbatim)

THE RUN COMPLETES. Rationale: (1) Inkling emits structured plans
with honest blockers (079, 080, 081 — three readings); (2) GLM-5's
door (StreamLake) is roster-proven and its 128k+ listing clears the
112k ask with the single... 8-door caveat recorded — if GLM-5 404s,
the filter's rule is confirmed model-id-level and Prime goes back
on, no further doors tried; (3) every prior full-run death was
apparatus now removed. If the run ESCALATES WITH A DIAGNOSIS,
confirmed in the favourable direction (honest BLOCKED at 539.7s
post-fix).

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
provider_failures; trace + mirror; n=1 and the $2.00 envelope; the
GLM-5 verdict (door + emission at 112k).
