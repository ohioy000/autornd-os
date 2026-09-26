# Pre-registration: cup-line sensor convergence probe (2026-09-26, owner-ruled, no command file)

## Primary question

Does the loop generalize beyond capacity planning — same workflow,
same roster, a machine-wiring task with derived arithmetic and a real
NPN-vs-PNP trap?

## What changed since 084 (scenario only)

- 084 (conv_numeric_consistency): COMPLETED 1/1, 9 calls, $0.06 —
  first terminal on current main. Committed, pushed, merged (PR #87).
- New scenario (this branch has no code changes): conv_cup_line_sensor
  — Keyence LV-N11N pinned in the request (24 VDC, NPN, 50 mA), 3 ft
  22 AWG (16.1 ohm/1000 ft), three sections (wiring with drop
  arithmetic SHOWN, parts, commissioning), cross-section figure
  agreement, unverified PCB input named not asserted. B7-family:
  numeric consistency (trace 1) + derived arithmetic (trace 2) + a
  real matching trap.
- Roster unchanged (preflight 15/15): Flash triage/Alibaba,
  Inkling-small plan/DeepInfra, GLM-5 build/StreamLake-first,
  failover open. Code unchanged: suite 1018 green at merge.

## Budget arithmetic (Ruling D25: sized, not defaulted)

084 spent $0.06 in 9 calls on the same workflow. Same envelope:
fresh $2.00 owner-approved; caps --max-spend 2.00 --max-spend-sweep
2.00. Timeout 1800. A spend stop is itself a finding.

## Registered prediction (verbatim)

THE RUN COMPLETES with validate green. Rationale: the loop proved
the full path on harder arithmetic (burst-derived storage math,
per-broker justification); drop arithmetic is simpler (one formula,
given inputs) and the NPN trap is exactly the honesty-firewall
behaviour three readings already proved (blockers named, not
fabricated). If the run instead produces a part-number or volt
figure that disagrees across sections, the consistency trap fires
for real — refuted in the informative direction, and the trace
shows which section drifted.

## Run shape

- Scenario: evals/scenarios/convergence/conv_cup_line_sensor.yaml
  (NEW — first outing, not a replication; the workflow and roster
  are the replication).
- Workflow: engineering-rnd. Repeat: 1. Timeout: 1800.
- Isolation: knowledge store isolated. No git operation while in flight
  (Ruling D13). Tree clean at commit (scenario file included).
- Departure (owner-authorized): no command file; owner ruled alone
  with full go-ahead ("let it ripp"). Pre-registration commit is the
  precedence evidence.

## What will be reported

Workflow terminal verbatim; the drop arithmetic as computed
(2 x 3 x 0.0161 x 0.05 ≈ 0.005 V) vs as reported; NPN-vs-PNP
handling (matched or honestly assumed); cross-section figure
agreement; served_by; trace + mirror; n=1 and the $2.00 envelope.
