# Pre-registration: full run on Inkling-plan + M3-build (2026-09-26, owner-ruled, no command file)

## Primary question

Does a full engineering-rnd run reach a workflow terminal with the
heterogeneous roster — Inkling-small planning via DeepInfra,
MiniMax-M3 building via DeepInfra, Flash triaging via Alibaba?

## What changed since 080 (pins, owner-set)

- 080 (Inkling plan + Flash implement, $2.00 cap, spent $0.03):
  Inkling EMITS (plan parsed after one schema-retry correction, 17k
  completion, $0.024) — model cleared. Flash 404s at the 112k
  implement ask (Xiaomi + DeepInfra fallback stripped) — engineering
  door closed. Committed (66d0c15).
- New pin (owner-set, preflight 14/14): engineering
  `minimax/minimax-m3` via DeepInfra (fp8, 512k max out, $0.28/$1.10,
  100% 30m uptime). Owner's bench read: M3 over GLM-5 and stepfun.
  House caveat recorded (§6.4: M2-era full-budget burn, no text) —
  this run is M3's live hearing against it.
- Architecture unchanged: Inkling-small via DeepInfra (probe 1/1
  completed, 080 plan parsed). Triage Flash/Alibaba settled.
  DeepInfra now serves two tiers — distinct ledger servings, same
  provider noted (Alibaba did the same on 073 without incident).
- Code unchanged: all ceilings wired, suite 1017 green.

## Budget arithmetic (Ruling D25: sized, not defaulted)

080 spent $0.03 in 7 calls (dead at implement). M3 at $0.28/$1.10
vs Flash $0.14/$0.28 — ~4x per token, but the ask is bounded (080's
implement never ran; 073's Flash implementation cost fractions).
Envelope: fresh $2.00 owner-approved; caps --max-spend 2.00
--max-spend-sweep 2.00. Timeout 1800. A spend stop is itself a
finding.

## Registered prediction (verbatim)

THE RUN COMPLETES. Rationale: (1) both live unknowns are now known —
Inkling emits structured plans with honest blockers (079, 080), and
the only remaining question is M3's door + emission, with DeepInfra
listing 512k max out against the 112k ask; (2) every prior full-run
death was apparatus now removed — 16k default (wired), 404 via
Relace/Alibaba on the disqualified non-prime id (replaced), Flash
404 at 112k (replaced). If M3 404s, the filter hates 13-door models
at this ceiling regardless of headroom — GLM-5/StreamLake (8 doors)
is the fallback. If M3 emits NOTHING, §6.4 stands confirmed on the
new generation and GLM-5 is the fallback. If the run ESCALATES WITH
A DIAGNOSIS, confirmed in the favourable direction (honest BLOCKED
at 539.7s post-fix).

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
M3 verdict (door + emission + §6.4 hearing).
