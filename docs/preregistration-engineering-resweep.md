# Pre-registration — engineering serving re-sweep

Committed before any spend. Expectations only, each with its n, per convention 7
and the working rule that a pre-registration's evidential value is that it
preceded the result.

**Why this exists.** B016 Part E's E1 died twice on 429s from the pinned
engineering serving, GMICloud, each time on an engineering-tier call, with
`implement` taking 183 s and 375 s for a single reply beforehand (§27.2). A
serving that refuses twice is disqualified on compliance before speed is
considered (convention 23). The pin is now **standing** in `.env` (§26), so a
failing pin is durable rather than incidental — which is the cost the
ratification recorded and this sweep is the response to.

**Method — B12's, deliberately.** Same scenario, same workflow, same shape, so
the arms are comparable with `docs/traces/b12-serving-*.jsonl`. Only the
`engineering` provider varies; `triage:Alibaba` and `architecture:StreamLake`
stay pinned so the rest of the pipeline is held still. The model map is B14's,
which is what the pins were settled against — **a pin is not portable without
its map** (§27.2, finding 2).

## Arms — six, n = 2 repetitions each = 12 units

Five are B12's own arms, kept for comparability; the sixth is added on evidence.

| arm | why it is in the sweep |
|---|---|
| `GMICloud` | **the control.** The incumbent pin. Predicted to fail — see P1 |
| `StreamLake` | cheapest endpoint; already the architecture pin |
| `OpenInference` | B12 arm |
| `DeepInfra` | B12 arm |
| `DigitalOcean` | B12 arm |
| `SiliconFlow` | added on evidence: in E1 attempt 4 it returned an **empty reply**, burning all 16,384 tokens on reasoning before emitting nothing (`finish_reason=length`). A compliance failure already observed once |

## Predictions — each falsifiable, each with its n

- **P1 — GMICloud fails or degrades, n=2.** At least one of its two repetitions
  errors, expires, or exceeds 120 s per engineering call. **If both repetitions
  run clean, E1's two 429s were transient, the convention-23 disqualification is
  withdrawn, and this sweep says so.** That is the prediction most worth being
  wrong about.
- **P2 — at least one arm fails on compliance rather than speed, n=12.** A
  schema-refused reply, an empty reply, or a loop that never terminates. B12
  measured this at 1 of 5 arms; SiliconFlow is the standing candidate.
- **P3 — iterations to termination spread wider than latency does, n=12.**
  §6.11's finding replicates: the ratio between the best and worst arm is larger
  for iterations than for seconds per call. Reported both ways regardless.
- **P4 — the cheapest arm is not the best arm.** Price order is StreamLake <
  OpenInference < DeepInfra < GMICloud < SiliconFlow; the compliance-and-
  iterations winner is predicted **not** to be StreamLake. A latency-or-price-only
  sweep would pin the wrong one — that is §6.11's whole lesson.
- **P5 — total spend under $1.00**, against a hard ceiling of $1.80 from the
  caps. Each arm is predicted under $0.15.

**No prediction is made about which arm wins.** Naming a favourite before a
compliance sweep is the error convention 23 exists to prevent.

## Commands — one per arm, run in the order listed

Caps are per invocation: `--max-spend 0.10` bounds one scenario-run,
`--max-spend-sweep 0.30` bounds the arm. Six arms therefore cannot exceed
**$1.80** in total.

    OPENROUTER_PROVIDER_ORDER="triage:Alibaba,architecture:StreamLake,engineering:<ARM>" \
    .venv/bin/python3 -m autornd.evals.cli \
      --scenarios evals/scenarios/backend_index.yaml \
      --workflow lean --repeat 2 --timeout 1200 \
      --max-spend 0.10 --max-spend-sweep 0.30 \
      --results-file docs/traces/resweep-engineering-<ARM>.jsonl

## Recorded before the run

- **An error, an expiry or an empty reply is an apparatus reading, not a verdict
  on the serving, until it repeats** (convention 18). n=2 is the minimum that
  can distinguish the two, and it is the reason this is not run at n=1.
- **The executor proposes; the owner ratifies.** Whatever this measures, a change
  to the standing pin in `.env` is a G-2 ratification and a G-3 edit, and neither
  is the executor's. The sweep produces a proposal with its evidence, not a new
  pin.
- **The outcome does not reopen B016.** This measures the apparatus E1 ran on,
  not the fix E1 tested. B13's ledger row stays open either way.
