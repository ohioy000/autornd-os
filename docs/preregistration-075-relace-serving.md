# Pre-registration: live retest on Relace serving (2026-09-26, owner-authorized, no command file)

## Primary question

Does the non-prime model emit when a different serving answers — is the
074 emptiness the model or was it Baidu?

## What changed since 074 (the apparatus, not the loop)

- 074 (non-prime via Baidu, $2.00 cap, spent $0.15): architecture died
  on the rework implement — 3 x 16384 empty, finish_reason=length,
  ProviderFailure naming Baidu/z-ai/glm-5.3, first live firing of the
  merged #86 instrument. Model and serving confounded (convention 23:
  never n=1) — this run un-confounds them.
- New pin (owner-set in .env, preflight 14/14 in clean env):
  architecture `z-ai/glm-5.3` via Relace. Model id unchanged, door
  changed — if the emptiness travels, it is the model; if it stays on
  Baidu, it was the serving.
- 074 trace committed (34f2d18) with ledger regen (new Baidu row,
  counts 7→8 on touched tiers). Suite 1013 green at last full run.

## Budget arithmetic (Ruling D25: sized, not defaulted)

074 spent $0.15 of $2.00 — the failure was fast and cheap. Same
envelope: fresh $2.00 owner-approved; caps --max-spend 2.00
--max-spend-sweep 2.00. Timeout 1800. A spend stop is itself a finding.

## Registered prediction (verbatim)

THE EMPTINESS TRAVELS WITH THE MODEL: the run dies all-empty on
architecture again, this time naming Relace/z-ai/glm-5.3, for under
$0.50. Rationale: three length-stops with zero bytes emitted is model
behaviour (a reasoner spending its budget before emitting), not a
transport fault — a serving fault would more likely 5xx, 429, or emit
partial text, and Baidu's 16384/16384 triple reads exactly like 072's
Prime truncation with the emission removed. If the run instead BUILDS
(green plan, implement verdicts, fold), refuted in the favourable
direction and Baidu stands disqualified by serving, not the model.

## Run shape

- Scenario: evals/scenarios/convergence/conv_numeric_consistency.yaml
  (same registered scenario as -049/-071/072/073/074; a modified
  request would not be a replication).
- Workflow: engineering-rnd. Repeat: 1. Timeout: 1800.
- Isolation: knowledge store isolated. No git operation while in flight
  (Ruling D13). Tree clean at commit.
- Departure (owner-authorized): no command file; run proceeds on verbal
  authorization, recorded here instead of a response IN_PROGRESS commit.
  Pre-registration commit is the precedence evidence. Same test
  technically (owner): scenario, workflow and repeat unchanged — only
  the serving door moved.

## What will be reported

Workflow terminal verbatim (or stop_reason if none); provider_failures
field naming whichever serving answered; served_by with versioned
answering ids; trace + mirror; n=1 and the $2.00 envelope; the
attribution answer (model or serving) stated with the n=1 caveat.
