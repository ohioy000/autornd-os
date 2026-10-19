# Dunce Arch Self-Assesment

The advisor (the third architect), 2026-10-19, at the owner's request: a full report on what has been done from the project's start to now, the goal, the directive and a realistic timeline, on which the owner will decide whether the advisor keeps the position. It is recorded as delivered.

## 1. The goal

The owner's vision, as `HANDOVER.md` §0 records it: **"A harness for team work that can be frugal and accurate, starting with engineering R&D."**

In practice, models that aren't top-tier, given structure (grounding, outward research, free checks), should answer expert engineering questions **at least as well as one call to the same class of model, and recover some of the answers that one call gets wrong**.

D51 turned that into five success bars:

| bar | means |
|---|---|
| S1 no harm | Where one call gets it right, the harness does too. |
| S2 value | Where one call gets it wrong, the harness recovers some. |
| S3 honesty | When it can't verify an answer, it says "unresolved" instead of shipping it. |
| S4 economy | Cost stays within a stated multiple of one call. |
| S5 record | Every number reproduces from the repo. |

The owner's stated core feature is **outward research**, which ingests real sources so the model doesn't make things up.

## 2. What has been done, start to now

The repo began on 2026-09-12. As of 2026-10-19 it holds 1,031 commits and 187 merged PRs (89 in September, 98 in October).

| period | who | what |
|---|---|---|
| 09-12 → 09-30 | architects 1 and 2 | Built the harness: API, graph engine, YAML workflows, the 31-node engineering pipeline, research and search tiers, risk gate, judges, budgets. Rulings D1–D35. |
| 09-30 → 10-03 | the advisor | Two outside reviews (10-02). The advisor fixed what they confirmed: runs that lost their record, the open money-spending endpoint, unbounded runs, spend-guard gaps, empty validations counting as passes (commands 108–116). |
| 10-03 → 10-06 | the advisor and the coder | Froze a 25-question test set and built the tier-3 runner. **Stage 1 (10-05, $8.50): the pipeline got 0 of 21 right; one call got 18.** |
| 10-10 → 10-14 | the advisor and the coder | D51: judges grade against the request, not criteria the planner invented. Added the verify-first workflow (#176). |
| 10-15 | the run | The re-measurement (121) **ran out of provider credit at unit 52 of 246**. Partial result: verify-first's first answers were 18 of 18 correct, but false judge objections blocked them. The owner chose no re-run. |
| 10-15 → 10-16 | the advisor and the coder | Fixed those false blocks and the run's tooling (R1–R6, #180–#185). |
| 10-16 → 10-18 | the advisor | Tier 4, the hard-question test: design, tooling, a pilot and 6 question batches, ending with 24 verified questions ($10.50). **Finding: no judge ever caught an error; three cheap blind recomputes and a majority vote caught 5 of 5.** |
| 10-18 → 10-19 | the advisor and the coder | D53: that vote built into the harness (#208, merged 10-19, **not yet reviewed by the advisor** when this report was written). |

**Spend:** the runs the advisor can account for since 10-05 cost about $22. The API key's lifetime usage, all architects included, is $70.72.

## 3. Where it stands against the goal

| bar | status |
|---|---|
| S1 no harm | **Not met.** The flagship pipeline failed (0 of 21), and nothing has been re-measured since the fixes. |
| S2 value | **Not shown.** The vote *detects* errors (5 of 5); nothing yet *corrects* them. |
| S3 honesty | Partly: verify-first holds back unendorsed answers, and the vote flags disagreements. |
| S4 economy | The pipeline costs 13–60× one call. One answer plus the vote costs about 1.1–1.5×. |
| S5 record | Met. |
| Outward research | **Not started on the advisor's watch.** No fetch tool, no source verification, 1 lookup per run. It has been on the plan since 10-02. |

## 4. What went wrong on the advisor's watch

- **The advisor spent 10-16 → 10-18 running test batches** instead of building, and the last batch the advisor recommended found nothing.
- **Retrieval, the owner's core feature, sat untouched** for 17 days.
- **Defects the advisor introduced:**

| defect | what it cost |
|---|---|
| The advisor's tier-4 design gaps | two void calibration runs, $2.17 |
| The advisor's command 122 wording made the runner refuse the verify-first arm | a fix PR (#196) |
| The advisor's review of #181 missed a crash | a coder fix (#183) |
| The advisor accepted a broken question (T4-31) by hand | the verify script caught it |
| The advisor misread the key limit | a void launch |
| The advisor's wording for the T4-42 repair | the vote's only false flag |
| A self-matching start-up check in command 123 | a fix PR (#207) |

## 5. The directive

1. **Stop measuring for its own sake.** No new question batches or probes. A paid run happens only when a build needs it to ship.
2. **Review #208.** The vote is already built.
3. **Rule D54 (no spend):**
   - retire the 31-node pipeline from closed questions;
   - make `answer-and-recompute` the candidate default.

   The owner signs off.
4. **Make the vote correct errors, not just flag them.** One test run (about $2) shows whether a single revision fixes flagged answers without giving in on right ones. If it passes, the coder adds "one revision on a flag".
5. **Build retrieval,** in two coder commands:
   - fetching real sources, with versions;
   - checking that a quoted passage actually appears in its source, plus the federal-regulations (eCFR) adapter.
6. **One measurement of record at the end:**
   - the final workflow against one call on the closed questions (S1, S4) and the 24 hard questions × 3 repeats (S2);
   - two blind readings;
   - about $15–20.
7. **Write up the results.** The owner picks the default workflow.

## 6. Timeline

This assumes about one day per coder command, which is what command 123 took, and no credit stoppages.

| dates | step |
|---|---|
| 10-19 → 10-20 | #208 reviewed; D54 ruled |
| 10-20 → 10-22 | revision test ($2) → command 124 built and merged |
| 10-22 → 10-28 | retrieval: commands 125 and 126, each with review |
| 10-28 → 10-30 | measurement of record ($15–20), two readings |
| 10-31 → 11-02 | verdict, docs, the owner's default choice |

**Realistically it finishes 10-31 to 11-03.** Retrieval is the least-known build and could slip it by a week.

## 7. What the advisor needs from the owner

- **Raise the key limit by about $25.** About $1.76 is left.
- **The owner's sign-off on D54.**
- **The owner's call on whether the advisor stays** to run this plan.
