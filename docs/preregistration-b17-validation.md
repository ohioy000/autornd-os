# Pre-registration — B17-R1's validation, and B18's first live exercise

Committed **before any spend**. Expectations only, each with its n, per
convention 7. The commit that carries this file is the evidence that the
predictions preceded the result.

**Spend envelope: $0.50, ratified by the owner 2026-09-22.**
Key balance at writing: **$4.8649 remaining of $6.00** (usage $1.1351).

## What this is

The B14 demonstration never terminated. It ran seven iterations, hit the call
ceiling at **42 calls against 41**, spent **$0.1783** — three times the
ungrounded comparator for a worse outcome — and recorded **no terminal status**.
Two defects, both now closed pending this run:

- **B17** — `criteria_addressed` could not read a criterion whose satisfaction
  is an **absence**. Ruled as **B17-R1** (§29), implemented in PR #31.
- **B18** — a bound-stopped run produced no typed terminal. Repaired in PR #33.

This run is the same scenario, same profile, same request, with both fixed.

| | the comparator | this run |
|---|---|---|
| trace | `b14-demo-marketing-claims-grounded.jsonl` | new |
| scenario | `gen_marketing_claims` | **same** |
| profile | `studio` | **same** |
| corpus | `docs/meridian_studio/`, ingested | **same**, 16 chunks confirmed |
| coverage check | term overlap on every criterion | **shape-classified (B17-R1)** |
| bound terminal | none | **typed (B18)** |
| pins | 3 tiers pinned, 5 rotating | **all 8 pinned** |

## ⚠️ The confounds, named before the run rather than after it

**Three things changed at once, not one.** This is stated here so no result can
later be attributed to a single cause without argument:

1. **B17-R1** — the coverage check's classification.
2. **B18** — the bound terminal, plus the loop's dissent suffix.
3. **Four pins that have never run.** `research:Google`,
   `escalation:Moonshot AI`, `ranker:Fireworks` and `premium:Friendli` were set
   2026-09-22 and have **zero live observations**. Only `triage:Alibaba` and
   `engineering:GMICloud` carry live n.

**The reading rule, registered in advance:** a failure in the research or
escalation tier is a **pin** reading first and a B17-R1 reading second. An
escalation tier that returns malformed verdicts is evidence about Moonshot AI,
not about shape classification, and will be reported that way even if it is
inconvenient.

## What is NOT predicted, and why

§29.3 registered the advisor's prediction that **`coverage.passed == true` at
iteration 1**. **That prediction is already refuted**, from free evidence, by
replaying all seven committed iterations of the comparator against the new
check:

```
False False False False False False True
```

True on exactly one — the last. At iteration 1 the draft genuinely had not
addressed criteria 1, 2 and 4 (0.53, 0.37, 0.29), and the presence check was
**right about that**. Restating the iteration-1 wording here would score a
success as a failure. It is deliberately not restated (PR #31's response).

## Method

**Step 1, free.** `python -m autornd.preflight` must report **zero failures**,
and `autornd.cli stats` must report a non-zero chunk count. Both already
confirmed at writing: 14 ok / 0 failing, 16 chunks.

**Step 2, paid.** Verbatim:

    AUTORND_PROFILE=studio \
    .venv/bin/python3 -m autornd.evals.cli \
      --scenarios evals/scenarios/generalization/gen_marketing_claims.yaml \
      --workflow engineering-rnd --repeat 2 --timeout 1800 \
      --max-spend 0.50 --max-spend-sweep 0.50 \
      --results-file docs/traces/b17-validation-marketing-claims-grounded.jsonl

The pins come from the **standing `.env` line**, not an env prefix — that is
what makes this the first exercise of the owner's full eight-tier pin.

**n = 2, and they are two samples, not a repetition.** Convention 27: the plan
regenerates between runs (B16), so the second unit measures a *different
contract*. Two samples are registered because B16 makes criteria shape the very
thing under test, and one draw of the criteria would tell us about one plan.
**Neither unit confirms the other.**

**The binding bound is the call ceiling, not the money.** The comparator hit 41
calls at $0.1783, so the realistic worst case is roughly $0.20 per unit and the
$0.50 sweep cap will not bind. It is set as a hard stop, not as the design.

## Predictions

### The instrument

- **P1 — shape classification fires on live criteria, n=2.** At least one
  criterion in each unit classifies as `prohibition` or `form`, visible in
  `coverage.data.shapes`. *If every criterion classifies as `presence`, this run
  cannot test B17-R1 at all and P2 becomes uninterpretable* — that is a
  **void**, not a pass, and will be reported as one.
- **P2 — the run reaches a terminal, n=2.** `status` is non-empty on every unit.
  **This is a weak prediction and is labelled weak**: B18 guarantees a status
  even on a bound, so P2 can hold while the run still fails to converge. It is
  registered because it is the README's advertised promise and because it was
  false last time.
- **P3 — the run CONVERGES, n=2.** `status == "completed"`, not `blocked` or
  `escalated`. **This is the real test of B17-R1** and the one worth being wrong
  about. A second ceiling death with the fix in place refutes the ruling and
  triggers §29.1's Phase 2, and will be reported as the ruling being wrong
  rather than absorbed as a workflow defect.

### The draft

- **P4 — B15-2 persists, n=2.** Fabricated or unverifiable sources still appear.
  **No citation fix has landed**, so a clean pass here would be reported **wrong
  and is a gift to B15's design** — it would mean grounding reaches citations
  after all.

### Cost and apparatus

- **P5 — under $0.15 per unit.** Against $0.1783 for the comparator's
  non-terminating run and $0.0569 for the ungrounded one. A converging run
  should cost less than a run that exhausted its ceiling.
- **P6 — the four never-run pins serve without incident, n=2.** No 429, no
  schema rejection, no empty reply attributable to `research`, `escalation`,
  `ranker` or `premium`. **Least confident of the six**, and the one whose
  failure is most likely to be misread as B17-R1 failing.
- **P7 — any 429 or retry event is recorded.** §6.16's "never fired in
  production" sentence updates in the same change if the retry fires.

## Standing rules for this run

- Every prediction is scored **as it reads**, with its n stated. A wrong one is
  reported wrong (convention 7).
- **Spend cannot be unspent.** The trace stands as measured and is never
  rewritten. One re-run to rule out an apparatus fault is a **logged departure
  carrying its cost**.
- The executor has a stake in P1 and P3, having written the code. That is
  recorded here, not discovered in the write-up.
