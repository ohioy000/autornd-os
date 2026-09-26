# Pre-registration: non-prime via Friendli at full ceiling (2026-09-26, owner-ruled, no command file)

## Primary question

Does non-prime emit when a serving that accepts 112k answers — is the
074/075 emptiness the model or was it two servings that never offered
more than 16k?

## What changed since 076 (pins, owner-set)

- 076 died in 15s before any architecture call: Relace 404s non-prime
  above 16k (`Filter by Context Length removed ... relace ...`), and
  the 200k search value was refused against Sonar's 127072 window.
  Neither reading touches the model — non-prime at a configured
  ceiling is STILL untested.
- Catalogue check (free, this session): Friendli serves `z-ai/glm-5.3`
  at 1M context / 943718 max out — accepts 112k with headroom. Same id
  premium already uses via Friendli, so the door is proven on the
  roster. Owner moved the architecture pin there; preflight 14/14 in
  clean env.
- Code unchanged since 076: all ceilings wired (plan/implement/review
  → plan_max_tokens 112768), suite 1017 green. This run is the same
  test with a door that opens.
- 076 trace committed (8b65610) with ledger regen (Relace 1→2).

## Budget arithmetic (Ruling D25: sized, not defaulted)

074 $0.15, 075 $0.16 (both dead in ≤10 calls at 16k). At 112k the
per-call cost rises toward 073 levels ($1.27 Prime) — non-prime bills
cheaper per token (≈$1.50/M blended sale on 075), so $2.00 should
cover a full build plus rework. Envelope: fresh $2.00
owner-approved; caps --max-spend 2.00 --max-spend-sweep 2.00. Timeout
1800. A spend stop is itself a finding.

## Registered prediction (verbatim)

THE RUN REACHES A TERMINAL, and it is ESCALATED WITH A DIAGNOSIS rather
than completed. Rationale: (1) every death to date is apparatus — the
16k default (072/073/074/075, now wired everywhere), a 404 on a door
that never offered 112k (076), a refused 200k lookup (076) — and no
serving has yet refused non-prime at a ceiling it accepts; (2) the
request is hard — the post-fix comparator reached honest BLOCKED at
539.7s. If the run COMPLETES, refuted in the favourable direction. If
non-prime emits NOTHING at 112k via Friendli, the model is ruled out
on architecture (three servings, configured ceiling, zero bytes) and
Prime goes back on — no fourth door.

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
answering ids; provider_failures (empty means no serving failed);
trace + mirror; n=1 and the $2.00 envelope; the model verdict on
non-prime at a ceiling its serving accepts.
