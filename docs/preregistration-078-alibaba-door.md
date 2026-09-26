# Pre-registration: non-prime via Alibaba at full ceiling (2026-09-26, owner-ruled, no command file)

## Primary question

Does non-prime emit at 112k through the provider that served Prime's
green build — isolating the model id as the only variable?

## What changed since 077 (pin, owner-set)

- 077 died in 22s: 404 at 112k via Relace again (filter strips all 39
  doors despite 131072 listings), 4 calls, $0.008. Catalogue-vs-filter
  contradiction now committed twice (076, 077).
- Owner insight: Friendli never served a live call (premium never
  fired) — an unproven door would confound the answer. Alibaba serves
  non-prime at the same 131072 listing AND served Prime's 073 green
  build: same provider, same ceiling, only the model id changes.
  Preflight 14/14 in clean env.
- Code unchanged: all ceilings wired, suite 1017 green. 077 trace
  committed (698fd5c, ledger Relace 2→3).

## Budget arithmetic (Ruling D25: sized, not defaulted)

076 $0.003, 077 $0.008 (dead pre-architecture). At 112k the per-call
cost rises toward 073 levels ($1.27 Prime); non-prime bills cheaper
(≈$1.50/M blended sale). Envelope: fresh $2.00 owner-approved; caps
--max-spend 2.00 --max-spend-sweep 2.00. Timeout 1800. A spend stop is
itself a finding.

## Registered prediction (verbatim)

THE RUN REACHES A TERMINAL, and it is ESCALATED WITH A DIAGNOSIS rather
than completed. Rationale: (1) the 404s track endpoint multiplicity
(39 doors, filter strips all) not the serving — Alibaba passed Prime
at this exact ceiling, so the door opens; (2) the 16k emptiness
travelled with the model (Baidu + Relace, six empties) and 112k is
the first ceiling that can falsify it as a capacity artifact; (3) the
request is hard — honest BLOCKED at 539.7s post-fix. If the run
COMPLETES, refuted in the favourable direction. If non-prime 404s via
Alibaba too, the filter hates the model id (not the door) — Prime
goes back on. If non-prime emits NOTHING at 112k via Alibaba, the
model is ruled out (three servings, configured ceiling, zero bytes)
and Prime goes back on.

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

Workflow terminal verbatim (or stop_reason if none); per-criterion shape
table, abstention count, fold detail; served_by with versioned
answering ids; provider_failures; trace + mirror; n=1 and the $2.00
envelope; the single-variable model verdict.
