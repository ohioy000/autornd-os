# Pre-registration: full run with failover open (2026-09-26, owner-ruled, no command file)

## Primary question

Does a full engineering-rnd run reach a workflow terminal now that
preferred-first failover is open — Inkling-small planning via
DeepInfra, GLM-5 building via StreamLake-first, Flash triaging via
Alibaba?

## What changed since 082 (code + config, owner-ruled)

- Fix (committed 30bbc76, pushed): new OPENROUTER_PROVIDER_FALLBACKS
  (default shut = hard pins unchanged); set and the payload sends
  allow_fallbacks True — pin tried first, router may serve beyond it.
  Proved live pre-commit: same 112768-token GLM-5 ask via StreamLake,
  404 pinned → 200 through the pin itself ($0.0003). Preflight reports
  the flag; test renamed + extended (fails pre-fix on stash). Suite
  1018 green. 082 trace committed with it (GLM-5 row re-read as
  filter artifact, not serving failure).
- Config (owner-set, preflight 15/15 with new fallbacks line):
  OPENROUTER_PROVIDER_FALLBACKS open. Pins unchanged:
  architecture Inkling-small/DeepInfra, engineering GLM-5/StreamLake,
  triage Flash/Alibaba.

## Budget arithmetic (Ruling D25: sized, not defaulted)

082 spent $0.02 in 6 calls (dead at implement 404). Failover adds no
cost when the pin serves (probe: through StreamLake first try);
a failover serving bills its own catalogue rate, recorded per call.
Envelope: fresh $2.00 owner-approved; caps --max-spend 2.00
--max-spend-sweep 2.00. Timeout 1800. A spend stop is itself a
finding.

## Registered prediction (verbatim)

THE RUN COMPLETES. Rationale: (1) Inkling emits (079, 080, 081 —
three readings); (2) the 404 class is removed by construction —
failover open, pin still first, probe served through the pin;
(3) GLM-5's only remaining unknown is emission shape at 112k, and
reasoning-optional flagships emit (Inkling did; Prime did). If the
run ESCALATES WITH A DIAGNOSIS, confirmed in the favourable
direction (honest BLOCKED at 539.7s post-fix). If GLM-5 emits
NOTHING at 112k with the door open, the model is ruled out with no
confounds left and Prime builds.

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
