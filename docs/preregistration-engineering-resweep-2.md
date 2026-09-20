# Pre-registration — engineering serving sweep, second attempt

Committed before any spend. Expectations only, each with its n, per convention 7.
**Supersedes nothing:** `docs/preregistration-engineering-resweep.md` and its two
runs stand as recorded. This is a new sweep because that one cannot be repaired —
its first run measured the harness and its second was stopped at n=1 on five of
six arms.

**Spend envelope: $1.00, ratified by the owner 2026-09-20.** Hard-bounded by the
caps below; the estimate is $0.60.

## The question

**Which serving should the `engineering` tier be pinned to?** That tier runs
`implement`, `validate`, `review` and `feasibility` — five of the flagship's
nodes, and the one whose serving closed B7 (§6.11). The pin is currently
**GMICloud**, standing in `.env` and G-2 ratified on 2026-09-20. It has never
been chosen by a designed comparison: `docs/serving-ledger.md` shows 225 of 233
completed, but that is accumulated blueprint traffic, not a sweep.

## What has changed since the first attempt, and why it matters

Three things, all measured on 2026-09-20, and **each one changes the apparatus**:

1. **A 429 is now retried** — three attempts, doubling backoff, every attempt
   billed (`tests/test_rate_limit_retry.py`, PR #15). In the previous sweeps a
   transient shortage killed a unit outright. **A 429 that survives the retries
   is therefore evidence of a different kind than a 429 was two runs ago**, and
   is the single largest reason this sweep is worth buying rather than re-reading
   the old traces.
2. **The 429 is upstream `(model, provider)` capacity, not a serving defect**
   (§6.16). So an arm that 429s through its retries is reporting *availability*,
   which convention 23 ranks under compliance, not *compliance* itself. The two
   are recorded separately below and must not be collapsed.
3. **`autornd/preflight.py` exists.** It runs free, before any spend, and would
   have caught the model-map drift that killed four E1 attempts.

## Method

B12's shape, deliberately, so the arms compare against
`docs/traces/b12-serving-*.jsonl`: scenario `evals/scenarios/backend_index.yaml`,
workflow `lean`, the B14 model map, `triage:Alibaba` and `architecture:StreamLake`
held still, only the `engineering` provider varying.

**Six arms.** Five are B12's; the sixth is a control.

| arm | role |
|---|---|
| `GMICloud` | the incumbent pin |
| `StreamLake` | cheapest endpoint |
| `OpenInference` | B12 arm; completed 3 of 4 across both previous runs |
| `DeepInfra` | B12 arm |
| `DigitalOcean` | B12 arm; the only arm observed to iterate and not converge |
| `SiliconFlow` | **known-bad control.** Five observations of the same failure: it burns its token budget on reasoning and emits nothing, and the unit expires. If this arm ever passes cleanly, the sweep's apparatus is suspect, not SiliconFlow's compliance |

**Three sessions, n=2 per arm per session — 36 units.** Sessions separated by
**at least three hours**, and **on at least two distinct calendar days** where
the schedule allows.

**Why sessions rather than repetitions.** Every 429 in the committed record falls
inside one two-hour window (§6.16). A single sitting therefore measures an
episode, not a rate, and cannot distinguish a serving that is usually short from
one that was short that afternoon. **If the sessions cannot be spread across
days, the sweep still runs and the reading is recorded as same-day** — weaker
evidence, named as such, rather than a sweep not run.

**Arm order rotates by session.** Session 1 runs the arms as listed; session 2
starts at the second arm; session 3 at the third. The previous sweep always ran
GMICloud first and SiliconFlow last, so arm and position were confounded — a
shortage arriving mid-session would have been attributed to whichever arms sat in
the middle.

**90 seconds idle between units.** Retained from the first amendment. It was
measured *not* to fix the 429 on its own, and is kept because it is nearly free
and removes one variable.

**Free pre-flight before each session:** `python -m autornd.preflight` must report
zero failures, and the run does not start otherwise.

## Predictions — each falsifiable, each with its n

- **S1 — SiliconFlow fails in all six of its units (n=6).** Expiry or empty
  reply, not a 429. *If SiliconFlow passes even once, the control is broken and
  every other reading in this sweep is suspect* — that is what a control is for,
  and it is the prediction most worth being wrong about.
- **S2 — at least four of the six arms complete both units in at least one
  session (n=36).** The first attempt produced 3 completions in 19 units; if that
  rate repeats with the retry in place, the retry is not working in production —
  which nothing has yet shown it does (§6.16: zero post-fix 429 events).
- **S3 — the retry fires at least once and is billed (n=36).** Observable in the
  logs as a `429 … retrying in Ns` warning and in `cost_by_tier` as spend on a
  unit that completed. **If it never fires across 36 units, the repair remains
  unexercised in production and this sweep cannot say it works.**
- **S4 — iterations to termination spread wider than seconds per call (n=36).**
  §6.11's finding replicates: the best-to-worst ratio is larger for iterations
  than for latency. Reported both ways regardless.
- **S5 — GMICloud is not disqualified (n=6).** The ledger's 225/233 is a prior,
  not a result; this predicts the sweep agrees with it. *A GMICloud disqualified
  on six designed units against 233 accumulated ones would be the most
  interesting outcome available and would need its own explanation.*
- **S6 — total spend under $0.60**, against the $1.00 envelope and a hard cap of
  $1.80 from the per-invocation limits.

**No prediction names a winner.** Naming a favourite before a compliance sweep is
the error convention 23 exists to prevent, and the executor has already made the
adjacent error once this week by disqualifying a serving on two failures.

## Command — one per (arm, session), 90 s idle between

    OPENROUTER_PROVIDER_ORDER="triage:Alibaba,architecture:StreamLake,engineering:<ARM>" \
    .venv/bin/python3 -m autornd.evals.cli \
      --scenarios evals/scenarios/backend_index.yaml \
      --workflow lean --repeat 2 --timeout 1200 \
      --max-spend 0.10 --max-spend-sweep 0.30 \
      --results-file docs/traces/sweep3-engineering-<ARM>.jsonl

Eighteen invocations (6 arms × 3 sessions) at `--max-spend-sweep 0.30` cannot
exceed **$5.40** by the caps alone, so **the $1.00 envelope is the binding
limit** and the sweep stops when it is reached, mid-session if necessary. A
session abandoned on the envelope is recorded, not retried.

## The three axes, reported in convention 23's order

1. **Compliance** — does the serving return a reply the schema accepts? A
   schema-refused reply, an empty reply, or a loop that never terminates
   disqualifies regardless of speed.
2. **Availability** — does it answer at all? A 429 surviving three retries is
   recorded here and **not** as a compliance failure (§6.16).
3. **Iterations to termination**, then **seconds per call** — in that order,
   because §6.11 measured iterations moving 4× while latency moved a third.

## Recorded before the run

- **The executor proposes; the owner ratifies.** Whatever this measures, changing
  the standing pin is a G-2 ratification and a G-3 edit. This produces a proposal
  with its evidence, not a new pin.
- **An error is an apparatus reading until it repeats** (convention 18). n=2 per
  arm per session is the minimum that can distinguish one from the other, and
  three sessions is the minimum that can distinguish an episode from a rate.
- **This measures the apparatus, not the harness.** No outcome reopens B013 or
  any closed row.
