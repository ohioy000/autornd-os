# Pre-registration — Blueprint 016, Part E

Committed before any spend. Expectations only, one line each with its n,
per the advisor's process ruling on 016: the rationale lives in §27 (the
blueprint, committed before execution) and will live in §27.2.

Pins, both runs, env-prefixed (G-3: nothing standing):
`OPENROUTER_PROVIDER_ORDER="triage:Alibaba,architecture:StreamLake,engineering:GMICloud"`.
Caps are per command, below.

## E1 — gen_marketing_claims, engineering-rnd, AUTORND_PROFILE=studio (n=1 run)

- The terminal is honest either way: `completed` with the citation criteria
  grounded by the B1 override, or a blocked/escalated terminal whose diagnosis
  carries `blocked_on` naming the criterion.
- Zero fabricated sources: every citation in every iteration of the trace is
  traceable to the override lookup; counted from the committed trace.
- If the terminal is shipped: ≤ 299 s and ≤ 13 calls [envelope: §20.1(f), n=1].
- The run does not approach the scenario's 40-call ceiling: under the fix an
  honest terminal arrives in far fewer calls, and the one measured ceiling
  approach on this scenario was the fabrication loop itself (43 calls
  [§24.1(f), n=1]). Reaching the ceiling falsifies the fix's premise.
- The override fires at most once, and only because a criterion demands
  verifiability; `refused_lookups` reads 0.

E1 command (the scenario sets no timeout of its own, so --timeout governs; an
expiry on it is an apparatus reading, convention 18):

    OPENROUTER_PROVIDER_ORDER="triage:Alibaba,architecture:StreamLake,engineering:GMICloud" \
    AUTORND_PROFILE=studio \
    .venv/bin/python3 -m autornd.evals.cli \
      --scenarios evals/scenarios/generalization/gen_marketing_claims.yaml \
      --workflow engineering-rnd --repeat 1 --timeout 1800 \
      --max-spend 0.75 --max-spend-sweep 1.50 \
      --results-file docs/traces/b16-e1-marketing-claims.jsonl

## E2 — lookup-cost regression, triage-only (n = 3 sectors × 2 reps = 6 units)

- Selection rule: the wide scenarios whose files assert `risk: low` —
  predicted exactly three [measured: §6.2 low row, 0/3 lookups, n=3].
  A different count is a finding, recorded, not absorbed.
- Free pre-flight before any spend, enumerating them:

      grep -l "risk: low" evals/scenarios/wide/*.yaml

- Each selected sector spends exactly $0.00 on search lookups in both
  repetitions: no `search` entry in `cost_by_tier`/`calls_by_tier`, and
  `refused_lookups` reads 0.
- One invocation per selected sector, not one full-suite sweep: the reading
  comes from the low-risk sectors alone, and a full sweep pays the other
  sectors' lookups for a reading it does not take. Expected spend is cents
  [estimate: a low-risk triage-only unit makes no lookup — triage plus two
  research calls]. Per sector:

    OPENROUTER_PROVIDER_ORDER="triage:Alibaba,architecture:StreamLake,engineering:GMICloud" \
    .venv/bin/python3 -m autornd.evals.cli \
      --scenarios evals/scenarios/wide/wide_<sector>.yaml \
      --workflow triage-only --repeat 2 --timeout 240 \
      --max-spend 0.05 --max-spend-sweep 0.50 \
      --results-file docs/traces/b16-e2-lowrisk-<sector>.jsonl
