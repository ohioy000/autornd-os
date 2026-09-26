# Pre-registration: non-prime via Relace at full ceiling (2026-09-26, owner-ruled, no command file)

## Primary question

Does non-prime emit at its configured ceiling — with the token count
(not the serving) as the variable, on the pin that already proved the
emptiness travels?

## What changed since 076 (owner-corrected)

- Owner correction, recorded: Relace did NOT fail — the token count
  did. 076 died in 15s on two apparatus faults of its own: the 200k
  search value refused against Sonar's 127072 window (refused_lookups
  1, scores poisoned), and the 404 naming Relace under Context Length
  while the catalogue now shows Relace at 1M/131072 — accepting 112k.
  The 404 is therefore not a serving-capability reading against
  Relace; the run never reached an architecture call on any door.
- Pins: architecture Relace (unchanged, owner-confirmed), non-prime
  model unchanged. Search values owner-trimmed to inside Sonar's
  window. Code unchanged since 076's wiring: all ceilings
  plan/implement/review → plan_max_tokens 112768, suite 1017 green.
  Non-prime at a ceiling its serving accepts is STILL untested — this
  run tests it on the same door as 075, isolating the token count.

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
16k default (072/073/074/075, now wired everywhere), a refused 200k
lookup and an unreached architecture call (076) — and Relace at
131072 max out accepts the 112k ceiling; (2) the request is hard —
the post-fix comparator reached honest BLOCKED at 539.7s. If the run
COMPLETES, refuted in the favourable direction. If non-prime emits
NOTHING at 112k via Relace, the model is ruled out on architecture
(three servings, configured ceiling, zero bytes) and Prime goes back
on — no fourth door.

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
trace + mirror; n=1 and the $2.00 envelope; the token-count verdict on
non-prime at a ceiling its serving accepts.
