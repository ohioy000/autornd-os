# Pre-registration: live retest on new pins (2026-09-25/26, owner-authorized, no command file)

## Primary question

Does a live run reach a workflow terminal — completed, blocked, or
escalated-with-diagnosis — rather than a runner timeout, now that the two
apparatus failures from -071 are repaired by new pins?

## What changed since -071 (the apparatus, not the loop)

- -071 died at `validate`: reasoning-mandatory serving spent 8000/8000
  tokens before emitting (GMICloud/deepseek-v4-flash), 4 empty replies.
- New pins (owner-set in .env, preflight 14/14 in clean env):
  engineering `xiaomi/mimo-v2.6-flash` via Xiaomi (fp8, $0.14/$0.28 per M,
  structured outputs, optional reasoning);
  architecture `z-ai/glm-5.3-prime` via Alibaba (sole serving, $2.80/$8.80
  per M, reasoning-always-on flagship — planning earns reasoning cost).
- VALIDATE_MAX_TOKENS raised (memory: 28000 per pin decision).

## Budget arithmetic (Ruling D25: sized, not defaulted)

Same sizing as -071: observed -049 cycle 528s for four calls; a convergent
run needs plan + implement + domain_review + coverage + consistency +
validate + judges, plus a rework cycle if the fold dissents. --timeout 1800
is ~2x the observed cycle. Envelope: fresh $1.00 owner-approved; caps
--max-spend 1.00 --max-spend-sweep 1.00. -071 spent $0.0287 for 12 calls;
$1.00 permits ~200+ calls at Flash prices — wall-clock binds first, and a
spend stop would itself be a finding.

## Registered prediction (verbatim)

THE RUN REACHES A TERMINAL, and it is ESCALATED WITH A DIAGNOSIS rather
than completed. Rationale: (1) the -071 killer was the provider, not the
loop — neither bound near (553s < 1800s, $0.0287 << $1.00) — and the new
engineering pin is the opposite budget fit (short structured verdicts,
optional reasoning); (2) the request is hard — the post-fix comparator
reached honest BLOCKED at 539.7s. If the run COMPLETES, refuted in the
favourable direction. If it times out at 1800s with the new pins, the
deadline is not the defect and the loop is.

## Run shape

- Scenario: evals/scenarios/convergence/conv_numeric_consistency.yaml
  (same registered scenario as -049/-071; a modified request would not be
  a replication).
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
