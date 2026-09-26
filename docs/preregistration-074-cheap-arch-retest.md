# Pre-registration: live retest on cheap architecture pin (2026-09-26, owner-authorized, no command file)

## Primary question

Does a live run reach a workflow terminal — completed, blocked, or
escalated-with-diagnosis — rather than a runner timeout or a spend
stop, now that the architecture tier runs the cheaper non-prime model?

## What changed since 073 (the apparatus, not the loop)

- 073 (Prime via Alibaba, $1.00 cap): full green build, fold agreed 4-0
  with the empty seat quoted live, then the rework-loop review fan-out
  on Flash truncated twice at the unwired 16k and tripped the ceiling
  at $1.27. Deepest path yet on current main.
- Since merged to main: PR #86 (ARCH-20260926-073, merge 8056a86) —
  all-empty retry sequences raise ProviderFailure carrying tier +
  provider; the runner ends blocked naming the serving (stop_reason
  separate per D23); unit record carries provider_failures beside
  rejections_by_tier. No budget, model, workflow, verdict, gate or
  threshold changed. Suite 1013 green.
- New pins (owner-set in .env, preflight 14/14 in clean env):
  architecture `z-ai/glm-5.3` (non-prime) via Baidu — first appearance
  of Baidu on the roster; the same model id premium serves via
  Friendli, kept distinct per serving by the ledger. Engineering
  unchanged: `xiaomi/mimo-v2.6-flash` via Xiaomi (green implementation
  on 073 — first fair reading positive, kept).
- Owner notes catalogue price is list; the model is on sale — the trace
  records whatever was actually billed.

## Budget arithmetic (Ruling D25: sized, not defaulted)

073 spent $1.27 against $1.00 (Prime, output-heavy: 133k completion).
Non-prime is cheaper per token but plan output volume is what it is, so
$2.00 buys roughly 1.5x 073's spend, not 2x its progress. Envelope:
fresh $2.00 owner-approved; caps --max-spend 2.00 --max-spend-sweep
2.00. Timeout 1800 (~2x the observed -049 cycle; wall-clock has never
bound). A spend stop is itself a finding, as 073 proved.

## Registered prediction (verbatim)

THE RUN REACHES A TERMINAL, and it is ESCALATED WITH A DIAGNOSIS rather
than completed. Rationale: (1) every prior death was apparatus, not
loop — wrong slot (-071), unwired plan ceiling (072, repaired), unwired
review ceiling + $1.00 cap (073, partially repaired: ProviderFailure
now names the class, the review node ceiling is still unwired) — and
the code since merged only sharpens the record, changing no verdict
semantics; (2) the request is hard — the post-fix comparator reached
honest BLOCKED at 539.7s. If the run COMPLETES, refuted in the
favourable direction. If it stops on spend or truncates at review
again, the defect is the review ceiling and the cap, not the loop and
not the cheaper model.

## Run shape

- Scenario: evals/scenarios/convergence/conv_numeric_consistency.yaml
  (same registered scenario as -049/-071/072/073; a modified request
  would not be a replication).
- Workflow: engineering-rnd. Repeat: 1. Timeout: 1800.
- Isolation: knowledge store isolated. No git operation while in flight
  (Ruling D13). Tree clean at commit (branch from merged main 8056a86).
- Departure (owner-authorized): no command file; run proceeds on verbal
  authorization, recorded here instead of a response IN_PROGRESS commit.
  Pre-registration commit is the precedence evidence.

## What will be reported

Workflow terminal verbatim (or stop_reason if none); per-criterion shape
table, abstention count, fold detail on empty seat; served_by with
versioned answering ids; provider_failures field (new since 073);
trace + mirror; n=1 and the $2.00 envelope; actual billed rates vs
catalogue list.
