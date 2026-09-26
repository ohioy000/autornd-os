# Pre-registration: live retest with all ceilings wired (2026-09-26, owner-ruled, no command file)

## Primary question

Does a live run reach a workflow terminal now that every paid phase —
plan, implement, review — carries its configured ceiling instead of
the 16384 client default?

## What changed since 075 (code, ruled by the owner)

- Owner ruling (verbal, this session): proceed with all fixes to reach
  a successful run. The 072 plan fix is the model: thread the node's
  ceiling to its call, fall back to the phase setting, never touch the
  client default or any verdict/gate/loop semantics.
- Fix (this branch): `run_implement` and `run_review` accept
  `max_tokens` and pass it to `lead.run` / `spec.run`, falling back to
  `plan_max_tokens` (the deliverable is plan-sized — the honest
  ceiling); `_phase_implement` and `_phase_review` thread
  `self._max_tokens(node)`; implement/review/rework_review nodes
  declare `max_tokens: plan_max_tokens`. `Specialist.run`'s 16384
  default untouched.
- Tests: 4 new in `tests/test_node_token_ceilings.py` (8 total) — all 4
  fail pre-fix on source stash, pass after. Suite 1017 green. Counts
  re-derived (1017/55 files).
- Pins unchanged: non-prime via Relace (075's serving — the emptiness
  travelled with the model, but neither serving ever offered more than
  16k, so no serving stands disqualified). This run gives non-prime
  its actual ceiling for the first time.

## Budget arithmetic (Ruling D25: sized, not defaulted)

073 spent $1.27 (Prime, 112k on plan only); 074 $0.15, 075 $0.16
(non-prime, 16k everywhere, dead in 8-10 calls). With 112k on every
phase, per-call cost rises toward Prime-like levels — but non-prime
bills cheaper per token (075: $0.15 for ~100k tokens ≈ $1.50/M
blended, sale price). Envelope: fresh $2.00 owner-approved; caps
--max-spend 2.00 --max-spend-sweep 2.00. Timeout 1800. A spend stop is
itself a finding.

## Registered prediction (verbatim)

THE RUN REACHES A TERMINAL, and it is ESCALATED WITH A DIAGNOSIS rather
than completed. Rationale: (1) all three prior deaths share one cause —
the 16384 default, identical finish_reason=length and completion count
across two models, three servings and three phases — and that cause is
now removed from every phase without touching verdict semantics; (2)
the request is hard — the post-fix comparator reached honest BLOCKED
at 539.7s. If the run COMPLETES, refuted in the favourable direction.
If non-prime still emits nothing at 112k, the model is ruled out on
architecture (two servings, configured ceiling, zero bytes) and Prime
goes back on.

## Run shape

- Scenario: evals/scenarios/convergence/conv_numeric_consistency.yaml
  (same registered scenario throughout; a modified request would not
  be a replication).
- Workflow: engineering-rnd. Repeat: 1. Timeout: 1800.
- Isolation: knowledge store isolated. No git operation while in flight
  (Ruling D13). Tree clean at commit.
- Departure (owner-authorized): no command file; owner ruled alone
  here with full go-ahead. Pre-registration commit is the precedence
  evidence.

## What will be reported

Workflow terminal verbatim (or stop_reason if none); per-criterion shape
table, abstention count, fold detail; served_by with versioned
answering ids; provider_failures (empty means no serving failed);
trace + mirror; n=1 and the $2.00 envelope; the model verdict on
non-prime at a configured ceiling.
