# Pre-registration — B14's demonstration, second attempt

Committed **before any spend**, per protocol. The commit that carries this file
is the evidence that the predictions preceded the result.

**Spend: NOT YET AUTHORISED.** The proposed cap is **$0.31**, inside the
$0.3453 remaining from the $0.50 envelope the owner ratified for
`ARCH-20260922-010`. That envelope was ratified for a run that has already
happened. **This is a different run and needs its own word.** Key balance at
writing: **$4.7100 remaining of $6.00** (usage $1.2900).

## Why this is not a replication

`ARCH-20260922-010` is the comparator, and **the apparatus has changed since**.
This run cannot replicate it and does not claim to:

| | `-010` | this run |
|---|---|---|
| coverage check | shape-classified (B17-R1) | **same** |
| bound terminal | B18 repaired | **same** |
| trace durability | records died with a `git stash -u` | **mirrored outside the working tree** (B20) |
| skip reporting | a fit-rule decline read as *exhaustion* | **named correctly** (B19) |
| sample arithmetic | `n=2` requested, **1 possible**, nothing said so | **warned before the first call** |
| pins | 8 tiers, 4 never run | **same 8, 5 now with live n** |

The `-010` pre-registration is **referenced, not rewritten**. It stands
committed and unedited with three of its seven predictions unscorable.

## The primary question

**Did the loop exhaust because coverage still failed, or for another reason?**

`-010` could not answer it: the per-criterion shapes, the per-iteration coverage
verdicts and the terminal status were all in the records that were destroyed.
The surviving stdout was checked for a terminal, a status, a bound or a ceiling
and **names none of them** — so the question is genuinely open and this run is
not buying an answer it already has.

**The registered prediction: coverage.** `-010`'s coverage line read *"3 of 5
measurable success criteria are not visibly addressed"*, and the free replay of
`-010`'s comparator showed the presence check failing early iterations on
criteria the drafts genuinely had not addressed. So the expectation is that
coverage is **still the binding judge**, on **presence-shaped** criteria rather
than on the prohibition and form ones B17-R1 fixed.

## Method

**Free gates first, all already green at writing:** `python -m autornd.preflight`
→ 14 ok, 0 failing. B19 and B20 closed on `main`. Convention 28 ratified. Corpus
ingested. Working tree clean.

    AUTORND_PROFILE=studio \
    .venv/bin/python3 -m autornd.evals.cli \
      --scenarios evals/scenarios/generalization/gen_marketing_claims.yaml \
      --workflow engineering-rnd --repeat 2 --timeout 1800 \
      --max-spend 0.155 --max-spend-sweep 0.31 \
      --results-file docs/traces/b14-rerun-2-marketing-claims.jsonl

**The caps are chosen so `n=2` is actually reachable**, which is `-010`'s
lesson: `2 × $0.155 = $0.31`, exactly the sweep cap, so the fit rule permits
both units. The pre-spend check will print nothing, and its silence is the
confirmation. `-010` asked for two units under caps that permitted one.

**$0.155 per unit** is just above `-010`'s observed $0.1547, so a unit that
behaves like the last one completes rather than being cut off mid-flight.

**No git command will be run against this repository while the run is in
flight.** That is the specific fault of `-010`. The mirror now makes it
survivable rather than merely forbidden.

## Predictions

- **R1 — two units are produced, n=2.** The sweep reports `2 of 2 units ran`.
  *This tests the `-010` arithmetic lesson, not the harness's competence.*
- **R2 — the primary question is answerable from the trace.** Every unit carries
  a `status`, a per-criterion `shapes` map, and per-iteration coverage. **If the
  trace cannot answer it, this run failed at its only job** and that is reported
  as such regardless of what else it shows.
- **R3 — coverage is still the binding judge, and on PRESENCE-shaped criteria.**
  The criteria that fail are classified `presence`, not `prohibition` or `form`.
  *If a prohibition or form criterion fails again, B17-R1 is wrong and §29.1's
  Phase 2 fires — this time with a committed trace, which `-010` could not
  supply.*
- **R4 — at least one unit reaches a terminal.** `status` non-empty. Weak by
  construction now that B18 is closed, and labelled weak; it is registered
  because it was false before B18 and its absence would mean the repair failed.
- **R5 — the run converges.** `status == "completed"` on at least one unit.
  **This is the one worth being wrong about**, and `-010` refuted its equivalent.
  A second non-convergence is evidence about the pathway, reported with the
  trace, not absorbed as a workflow defect.
- **R6 — B15-2 persists.** Fabricated or unverifiable sources still appear. No
  citation fix has landed; a clean pass is reported **wrong** and is a gift to
  B15's design.
- **R7 — the trace survives.** The mirror holds every record the primary does.
  *Checked by comparing the two files after the run, which is the only honest
  test of B20 on a live run rather than on a simulated unlink.*

**Not predicted, deliberately:** a terminal at iteration 1. That wording was
refuted from free evidence before `-010` and is not resurrected here.

## Standing rules

- Every prediction scored **as it reads**, with its n. A wrong one is reported
  wrong (convention 7).
- **Spend cannot be unspent.** The trace stands as measured.
- The executor has a stake in R3 and R5, having written the code under test.
  Recorded here rather than discovered in the write-up.

---

## Amendment 1 — envelope raised to $0.50 (owner, 2026-09-22)

**Committed before the run, like the registration it amends.**

The owner ratified **$0.50** for this run, above the $0.31 proposed. The sweep
cap moves to **$0.50**; **the per-unit cap stays at $0.155**, and that is not an
oversight.

**Raising the per-unit cap to $0.50 would have re-created the exact defect this
arc just closed.** Under the fit rule a unit starts only if it could not
possibly overrun the sweep cap, so `--max-spend 0.50 --max-spend-sweep 0.50`
permits **one unit**, not two — which is precisely what happened to
`ARCH-20260922-010` and cost half its registered sample. The per-unit cap is the
thing that has to stay small for `n=2` to be reachable.

    --max-spend 0.155 --max-spend-sweep 0.50

`0.50 // 0.155 = 3`, so two units fit with a unit of headroom. The pre-spend
check added by `ARCH-20260922-021` will print nothing, and its silence is the
confirmation that the arithmetic works this time.

**What the extra headroom buys:** it is not a licence to spend more per unit. It
is slack so that a unit running longer than `-010`'s $0.1547 is not cut off
mid-flight by the sweep cap after the first one has already been paid for.
Expected spend is unchanged at roughly **$0.31**, and the predictions are
untouched.
