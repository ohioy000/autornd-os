# Pre-registration: first fresh live terminal (ARCH-20260923-049, 2026-09-25)

## Primary question

Does a fresh live run on current main reach a terminal status within its
declared bounds? A terminal is completed, blocked, or escalated-with-diagnosis.
"No terminal" is the failure this command exists to detect.

## Registered prediction (verbatim)

The run reaches COMPLETED. Rationale: all six workflows terminate
provider-free and the failure path is bounded at 31 calls against a 41-call
ceiling, so the only live risk is provider variance — a 429, a schema
rejection, or a malformed reply — not loop logic. If the run escalates, the
reason will be provider variance and the trace must name which.

## Cap arithmetic

n=1 at a per-unit cap of $0.25 with a sweep cap of $0.25: 1 × $0.25 = $0.25,
exactly the sweep cap, so the fit rule permits the unit. The envelope is
owner-ratified ($0.25 approved for this run). The pre-spend check prints
nothing when the caps fit; its silence is the confirmation.

## Run shape

- Scenario: evals/scenarios/convergence/conv_numeric_consistency.yaml
  (B7 trace 1 of 4: figures agreeing across sections — exercises plan,
  implement, validate, coverage and the fold end to end).
- Workflow: engineering-rnd. Repeat: 1. Timeout: 3600.
- Command: `.venv/bin/python3 -m autornd.evals.cli --scenarios
  evals/scenarios/convergence/conv_numeric_consistency.yaml --workflow
  engineering-rnd --repeat 1 --timeout 3600 --max-spend 0.25
  --max-spend-sweep 0.25 --results-file
  docs/traces/049-live-terminal.jsonl`
- Pins: standing .env (G-2/G-3 respected — owner holds the file; the run
  reads it, never writes it). Versioned answering ids logged from the trace.
- Knowledge store: isolated (`_isolated_store()`), per the working rules.
- No git operation while the run is in flight (Ruling D13). Tree is clean
  at commit; the mirror is a backstop, not a licence.

## What will be reported

Terminal verbatim (or its absence stated plainly); bound named on
escalation; fold detail quoted on abstention; per-criterion shape table and
abstention count; trace committed with mirror path; n=1 and the ratified
envelope stated. If the run terminates, it is the first fresh live
demonstration: n=1, one request, one observation.
