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

---

## Execution record — 2026-09-21

**42 calls, 1442 s, $0.1783.** Ran to the scenario's 41-call ceiling without a
terminal. Trace: `docs/traces/b14-demo-marketing-claims-grounded.jsonl`.

### A correction the executor owes before the scores

**G1 was worded against the wrong subsystem, and the executor's first reading of
the result was wrong because of it.** The log carries
*"Knowledge collection not found"* four times, which was read as *the corpus
never arrived* and reported as such. It is not.

There are **two** grounding sources (`knowledge/context.py:1-6`):

1. **Deterministic manifest docs**, read from `docs/` **on disk** by
   `load_docs_context`. **Unaffected by eval isolation.**
2. **ChromaDB semantic retrieval**, which `_isolated_store()`
   (`evals/runner.py:211`) deliberately redirects to a fresh temp directory per
   scenario, so a developer's local store cannot pre-answer a gap.

The warning comes from **(2) only** (`knowledge/store.py:135`). Path (1)
delivered **4,020 characters** — `brand-platform.md` and `house-style.md` — for
the domains triage returned, carrying both the sourcing rule and the invention
rule verbatim. **G1's substance held; its wording tested a different system.**

That the executor's own free pre-check queried the *real* store rather than the
one the run would use made the error easier to make and harder to catch.

### Scores

| prediction | outcome |
|---|---|
| **G1** — corpus loads | **Substance CONFIRMED, wording wrong.** Manifest docs arrived; Chroma retrieval was isolated by design |
| **B14-1** — no shipped engineering structural role anywhere | **CONFIRMED.** triage staffed `['strategist', 'copywriter', 'fact_checker']`. No `test_engineer`, no `systems_architect` |
| **B14-2** — a profile-declared role appears | **CONFIRMED.** Three of them |
| **B14-3** — the run reaches a terminal | **FAILED.** 42 calls against a 41 ceiling, 7 iterations, no terminal |
| **B15-1** — no invented product name presented as fact | **CONFIRMED** — see below |
| **B15-2** — no fabricated source | **NOT CONFIRMED, and probably failed** — see below |
| **C1** — under $0.15 | **FAILED.** $0.1783 |

### B14 is demonstrated

Triage staffed a non-engineering team on a non-engineering brief and **no
shipped engineering role appeared anywhere in the run.** The comparator, on the
identical scenario before B14, did not. **That is B14's claim, observed live.**

### B15-1 is the result worth having

The comparator invented the product name **"ExpenseFlow" and presented it as
fact** — escalation's autopsy named it the failure. This draft carries an
explicit **`## Assumptions`** section, first line:

> *"The product name, specific features, and unique selling propositions have not
> been confirmed by the client. This brief assumes a generic expense-management
> automation product."*

That is exactly what `house-style.md` requires and exactly what the comparator
failed to do. The draft also opens *"This brief serves practitioners"* — the
audience frame is `brand-platform.md`'s, near-verbatim. **The grounding reached
the model and changed the output.**

**Confounded, and n=1.** B14's wiring and the grounding both moved. This is
suggestive, not established.

### B15-2 almost certainly failed

Three proof points, each with a firm, a report title, a date and a deep URL:
Levvel Research, **Aberdeen Strategy & Research**, **PayStream Advisors**.

**The comparator's autopsy named Aberdeen and PayStream as firms whose reports
it had invented.** The same firms reappear here with different titles and
different URLs, none of it verified. **The pattern is the comparator's.** The
draft does mark the sources as secondary, which the house style permits — but
marking a fabricated citation as secondary is not sourcing it.

**So the fix reached the product name and not the citation.** The house style
forbids both. One landed.

### Why it never terminated

`implement.green` was **true**; the loop did not fail on refusal. It failed on
`criteria_addressed` — *"2 of 6 success criteria are not visibly addressed"* —
seven times, and exhausted the call ceiling. **Coverage death, not fabrication
death**, and a different failure from the comparator's.

The run cost **3× the comparator** (42 calls against 22, $0.1783 against
$0.0569) and reached a **worse** outcome. Grounding adds tokens to every call
and appears to have added iterations too; **whether the extra iterations come
from the grounding or from B14's staffing is not separable at n=1.**

### One loose thread

Triage returned domains `['brand_strategy', 'copywriting', 'documentation']`.
**`documentation` is a shipped `Domain` enum member**, returned on a studio run
whose profile declares three non-shipped domains. It is not covered by the
studio manifest, so it contributed no docs. Not investigated here.

### Departures

None. The registered command ran verbatim; the envelope held at $0.1783 of
$0.50.
