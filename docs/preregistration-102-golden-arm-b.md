# Pre-registration — ARCH-20261001-102: the golden set on arm B (the 09-26 lineup)

Committed BEFORE any spend. Branch `arch/20261001-102-golden-arm-b`; the
setup is at `321ec33` (seven scenarios byte-identical to evals/golden/keys.json).

## Predictions and decision rule (the advisor's, verbatim)

P1, preflight passes on every 09-26 pin. P2, at least 5 of 6 golden questions SHIP (status completed). P3, at least 5 of 6 golden questions PASS (shipped, every item, within target). P4, every shipped golden run is within its time target. P5, the golden sweep costs at most $0.42 and each run at most $0.07. P6, triage reads low or medium on at least 2 of the 3 simplest questions (Q1, Q3, Q6). P7, sprawl persists on this lineup: the median ratio of answer to model-answer length is above 10. P8 (side test), the IA run ships with all six core items. DECISION RULE: 5 or 6 golden passes means the 09-30 lineup was the regression, D41's condition is met, and the next work is the owner's standing re-pin (G-2) and the fast-path question. 3 or 4 passes means arm C (the 09-26 code at f94e62d, its own virtualenv, the same prefix) runs on the failed questions only, after a NEW owner authorisation. Fewer than 3 means a design problem, and D41 turns into the redesign of the default path.

## Owner's authorisation, verbatim

The paid step: "The paid step has my go ahead" (2026-10-01), on the
command's proposed caps. Then, choosing among the BLOCKED options in the
response ("1. Run arm B anyway, skipping preflight with the override
recorded"): "1".

So the caps and flags are: the golden sweep with `--max-spend 0.07
--max-spend-sweep 0.42 --skip-preflight`, then the IA side test with
`--max-spend 0.08 --max-spend-sweep 0.08 --skip-preflight`. Total at most
$0.50. The override is recorded in each results header as `{ran: false,
override: true}`.

## Known before spend

- **P1 is already REFUTED.** Under the arm B prefix the gate reads 26 ok
  and 3 failing: architecture via DeepInfra, escalation via 'Moonshot AI',
  and research via 'Google'. The run proceeds only on the owner's
  override, because 084 and 085 served research via Google and
  architecture via DeepInfra with these exact pins on 09-26.
- **A dead pin will show as a provider failure or a 404.** Either is a
  reading, not an error. No pin is substituted.

## Run shape

- Arm B as an environment prefix only, never written to `.env`. The
  effective settings are recorded in notebook 94.1.
- Detached with `setsid nohup`, sequential: the golden sweep, then the IA
  side test.
- No git operation while a run is in flight.
