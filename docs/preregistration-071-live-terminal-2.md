# Pre-registration: second live terminal (ARCH-20260925-071, 2026-09-25)

## Primary question

Does a live run on current main reach a workflow terminal — completed,
blocked, or escalated-with-diagnosis — rather than a runner timeout?

## Budget arithmetic (Ruling D25: sized, not defaulted)

Observed -049 cycle: rework_review 81.9s + review 66.9s + implement 208s +
plan 171s = 528s for four calls. A convergent run needs plan + implement +
domain_review + coverage + consistency + validate + judges, and if the fold
dissents, a rework cycle. `--timeout 1800` is roughly 2x the observed cycle
(3.4x the four-call figure); a run needing three cycles would exceed it,
and that itself would be a finding about the loop.

Spend is the binding cap: `--max-spend 1.00 --max-spend-sweep 1.00` on a
fresh $1.00 owner-approved envelope for this run (the command's $0.25
assumption is superseded — the owner granted $1.00). The previous run used
$0.0527 for 12 calls; $1.00 permits roughly 200+ calls, which exceeds what
1800s can buy at observed latencies — so the wall-clock binds first, and a
spend stop would itself be a finding. Do NOT raise either cap without the owner.

## Registered prediction (verbatim)

THE RUN REACHES A TERMINAL, and it is ESCALATED WITH A DIAGNOSIS rather
than completed. Rationale, in two parts. (1) The two causes of the -049
timeout are now fixed on main: rework carries the review findings (-067),
so a rework iteration is informative rather than blind, and a green build
should not be turned red by an unguided re-implement. (2) The request is
hard: the post-fix comparator on the same request reached an honest
BLOCKED terminal at 539.7s, and nothing since has made the request easier,
only the loop more honest. If the run COMPLETES, the prediction is refuted
in the favourable direction and is reported as refuted. If it times out
again at 1800s, the deadline is not the defect and the loop is — reported
as the finding.

## Run shape

- Scenario: evals/scenarios/convergence/conv_numeric_consistency.yaml
  (same registered scenario as -049; a modified request would not be a
  replication).
- Workflow: engineering-rnd. Repeat: 1. Timeout: 1800.
- Command: `.venv/bin/python3 -m autornd.evals.cli --scenarios
  evals/scenarios/convergence/conv_numeric_consistency.yaml --workflow
  engineering-rnd --repeat 1 --timeout 1800 --max-spend 1.00
  --max-spend-sweep 1.00 --results-file
  docs/traces/071-live-terminal-2.jsonl`
- Pins: standing .env (G-2/G-3 respected). Versioned answering ids from trace.
- Knowledge store: isolated (`_isolated_store()`).
- NO git operation while the run is in flight (Ruling D13). Tree clean at
  commit; the mirror is a backstop, not a licence.

## What will be reported

Workflow terminal verbatim (or stop_reason if none — the -066 field,
observed live first time); what the rework implement call received (the
-067 change, observed live first time); per-criterion shape table,
abstention count, fold detail on empty seat; trace + mirror; n=1 and the
$1.00 envelope. If terminal: FIRST fresh live demonstration of a terminal
on current main — n=1, one request, one observation.
