# Pre-registration — B14's demonstration, and B15's first test

Committed before any spend. Expectations only, each with its n, per convention 7.

**Spend envelope: to be ratified by the owner before execution.** Proposed
**$0.50**, against a measured comparator of $0.0569 for the same scenario
ungrounded. Key balance at writing: **$5.0432 of $6.00**.

## What this is

B14 is closed as **implemented and guarded, not demonstrated**: no
non-engineering run has ever happened, because until `docs/meridian_studio/`
landed there was no corpus for one. `docs/smartfactory/` cannot serve — its
domains are five shipped enum members.

This run is the demonstration, and it is **a controlled contrast rather than a
first observation**, which is the reason it is worth buying:

| | the comparator | this run |
|---|---|---|
| trace | `b16-e1-marketing-claims-registered.jsonl` | new |
| scenario | `gen_marketing_claims` | **same** |
| profile | `studio` | **same** |
| pins | `triage:Alibaba,architecture:StreamLake,engineering:GMICloud` | **same** |
| model map | B14's map | **same** |
| structural roles | hardcoded engineering | **profile-declared** |
| grounding | **none** — *"Knowledge collection not found"* on every attempt | **the studio corpus, ingested** |

**Two variables move at once — B14's wiring and the presence of grounding — and
that is a limitation of this design, stated here rather than discovered later.**
A result cannot be attributed to one of them alone. What it can establish is
whether the non-engineering path works end to end, which is B14's actual claim.

## Method

**Step 1, free:** ingest the corpus. ChromaDB with local embeddings, so nothing
bills.

    .venv/bin/python3 -m autornd.cli ingest docs/meridian_studio

**Step 2, paid:** the registered E1 command verbatim, to a new results file.

    OPENROUTER_PROVIDER_ORDER="triage:Alibaba,architecture:StreamLake,engineering:GMICloud" \
    AUTORND_PROFILE=studio \
    .venv/bin/python3 -m autornd.evals.cli \
      --scenarios evals/scenarios/generalization/gen_marketing_claims.yaml \
      --workflow engineering-rnd --repeat 1 --timeout 1800 \
      --max-spend 0.50 --max-spend-sweep 0.50 \
      --results-file docs/traces/b14-demo-marketing-claims-grounded.jsonl

**n = 1.** The comparator is n = 1. Both are single observations and the record
will say so; B16 makes a second repetition a *different plan* rather than a
confirmation, which is recorded in its own row.

**Free pre-flight first**, per the standing rule: `python -m autornd.preflight`
must report zero failures.

## Predictions

### Grounding

- **G1 — the corpus loads, n=1.** No *"Knowledge collection not found"* in the
  run log, and `autornd.cli stats` reports a non-zero count before the run.
  *If this fails, everything below is void* — an ungrounded studio run is the
  comparator, not the experiment.

### B14 — the claim under test

- **B14-1 — no shipped engineering structural role appears anywhere in the run,
  n=1.** Neither `test_engineer` nor `systems_architect` in any triage
  `specialists` list, any review team, or any specialist prompt. **A single
  appearance falsifies B14's closure** and the row reopens.
- **B14-2 — at least one profile-declared role appears** among the specialists
  or reviewers: `strategist`, `copywriter`, `editor`, `fact_checker` or
  `seo_analyst`.
- **B14-3 — the run reaches a terminal**, any terminal. A non-engineering run
  that crashes has not demonstrated generalization regardless of who staffed it.

### B15 — its first real test

The comparator invented the product name **"ExpenseFlow"** and presented it as
fact. `house-style.md` now states, in the grounding this run will carry, that an
invented product name presented as fact is the most serious editorial failure
available, and that assumptions must be stated as assumptions.

- **B15-1 — the draft does not present an invented product name as fact.**
  Either no product name is invented, or one is and it is **explicitly marked as
  an assumption**. Judged by reading the committed trace's implement verdict,
  not by a model's self-report.
- **B15-2 — no fabricated source.** Every citation traceable, or the claim
  marked unsourced. The comparator failed this at the citation level while
  passing it at the terminal level.

**If B15-1 holds, it is suggestive and not conclusive**: n=1, and grounding is
confounded with B14's wiring. **If B15-1 fails, that is the stronger result** —
it would show that telling the harness in its own project documentation not to
do the thing does not stop it, which bears directly on how B15 should be fixed.

### Cost

- **C1 — under $0.15**, against $0.0569 for the ungrounded comparator. Grounding
  adds context tokens on every call, so some increase is expected; a figure
  above $0.15 is a finding about what grounding costs, recorded not absorbed.

## Recorded before the run

- **The executor has a stake in B14-1 and B15-1**, having written both the code
  and the corpus. That is the reason this is pre-registered rather than run and
  then described.
- **A wrong prediction is reported as wrong** (convention 7). B15-1 is the one
  most likely to fail and the one most worth failing.
- **No outcome reopens B13.** This measures the generalization boundary and the
  invention boundary, not the honest-refusal mechanism.
