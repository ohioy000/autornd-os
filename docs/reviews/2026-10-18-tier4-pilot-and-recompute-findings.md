# Tier 4, 2026-10-18: the pilot, batch 3 and the recompute check

Advisor, 2026-10-18, under Ruling D52 (`docs/reviews/2026-10-16-tier4-the-capacity-test.md`) and the owner's instructions of the day: "you edit then launch full permission" and "B then C, full permission". This is a findings record, not a verdict. D52 §5 gives the pilot no verdict, and the samples here are small.

## What ran (all traces in `docs/traces/`, cited by sha256 prefix)

| run | units | spend | trace |
|---|---|---|---|
| Pilot, T4-15: D-pages, verify-first (F), standing pipeline (E) | 3 | $0.6282 | `20261018T022735Z-tier4-pilot-batch2.jsonl` (05e5f56f…) |
| Batch-3 calibration: D-pages on T4-21 to T4-24 | 4 | $0.9683 | `20261018T034225Z-tier4-calibration-batch3.jsonl` (eb31aabb…) |
| Recompute check, single sample: flash and qwen checkers on T4-15, T4-16, T4-04 | 6 calls | $0.1219 | `20261018T032845Z-recompute-check.json` (88828ff6…) |
| Recompute check, replicates: 2 flash and 2 qwen on T4-15 | 4 calls | $0.1520 | `20261018T033306Z-recompute-check.json` (4b2ae7b1…) |
| Majority vote: 3 flash samples each on T4-15 and T4-21 to T4-24 | 15 calls | $0.5390 | `20261018T035714Z-recompute-vote-samples.json` (39e9d34f…) |

The batch-3 generation cost $0.33, and its verification is `evals/tier4/batch3/VERIFY.md`.

**Tier-4 spend to date: $7.82.**
- Generation: $1.73.
- Void calibrations: $2.17.
- Batch-2 calibrations: $1.51.
- Pilot: $0.63.
- Recompute probes: $0.81.
- Batch-3 calibration: $0.97.

## Who got what right

Correctness is the advisor's reading against `verify.py` for each batch, never a scorer (D50).

| question | strong single call (kimi-k3, with the pages) | cheap single call (gemini-flash, with the pages, as the recompute checker) | verify-first (F) | standing pipeline (E) |
|---|---|---|---|---|
| T4-15 (strut; torsional-flexural coupling axis) | wrong, wrong, empty at the cap | correct in **5 of 6** samples | wrong (the same axis error) | no plan: the architecture serving was empty at the 32768 cap three times |
| T4-16 (pump with impeller trim) | correct; one run empty at the cap | correct, 1 of 1 | not run | not run |
| T4-21 (gearhead, dwell-excluded RMS) | correct | correct, 3 of 3 | not run | not run |
| T4-22 (control valve, F_kc against F_L) | correct | correct, 3 of 3 | not run | not run |
| T4-23 (cold plate, glycol factors) | correct | correct, 3 of 3 | not run | not run |
| T4-24 (capacitor bank, altitude derating) | correct | correct, 3 of 3 | not run | not run |
| T4-04 (pilot batch, heat sink) | correct | correct, 1 of 1 | not run | not run |

Of eleven verified tier-4 questions, the strong single call fails only T4-15. Every T4-15 answer from kimi-k3 or from the engineering serving behind F made the same error: EN 1993-1-3's y-y (the axis of symmetry) read as the corpus's y (the minor axis). The cheap model, given the pages and a 32768-token budget, failed none consistently. Its one T4-15 miss in six samples was that same error.

## Which check caught what

Each check was measured against answers whose correctness the reading established: three wrong T4-15 answers, and nine correct answers or verified references.

| check | wrong answers flagged | correct answers flagged |
|---|---|---|
| Verify-first's judge (validate) | 0 of 1. It raised a false "proprietary data" dissent and approved the revision with the error intact. | not measured |
| One blind recompute, flash | 2 of 3 samples flagged all wrong answers. The third sample made the same error and flagged none. | 1 of 3 samples flagged the correct reference |
| One blind recompute, qwen (judge tier) | flagged all, but for wrong reasons: its own answer picked VM-C160 | flagged the correct reference in 2 of 2 |
| **Majority of 3 blind flash recomputes** | **3 of 3** | **0 of 9** |

A disagreement says only that one side is wrong. A single recompute is as good as the checker's own answer. A majority of three independent cheap samples, compared mechanically (`evals/tier4/probes/recompute_vote.py`), separated right from wrong on every answer measured, at about $0.04 a sample.

## What this suggests, not yet what it proves

1. **Headroom is scarce on generated hard questions.** With the documents and room to reason, single calls solve almost all of them. The strong single call failed one question of eleven, on a notation trap.
2. **The standing pipeline fails before its structure acts.** On T4-15 its architecture serving exhausted the 32768-token cap three times, so no plan existed for the judges to work on.
3. **Judging does not catch engineering errors; independent recomputation by majority did.** This repeats tiers 2 and 3 (0 real catches by judges) on hard work, and adds the first structure that helped: three cheap blind recomputes and a vote.
4. **A candidate lane:** answer with the documents, recompute three times on a cheap model, vote, and flag any disagreement. About $0.12 per question beyond the answer, against $0.39 for one strong call and $0.11 or more for a pipeline run that produced nothing.

## Caveats

- **The samples are small:** one headroom question, three checks measured on twelve answers.
- **Family affinity (D52 §10).** Every tier-4 question was written by `google/gemini-4-argon`, and the best performer is gemini-flash, of the same family. T4-15's notation may follow Gemini's conventions. The next batch should come from a generator of another family.
- One reader (the advisor) and one verifier per batch, the advisor's own.
- T4-15's catalogue labels the axis of symmetry x and EN 1993-1-3 labels it y-y. The trap is real, but it is a mapping trap more than a depth-of-physics trap.

## Options for the next step (the owner's call)

1. **Remove the affinity confound:** a batch from a non-Gemini generator, answered by flash, kimi-k3 and the vote.
2. **Measure the vote lane end to end on tier 2:** accuracy and cost of three cheap recomputes and a vote, against the single call, on the 25 frozen questions.
3. **Rule the standing pipeline's next step (D52 §8):** raise the architecture serving's budget for one more try, or narrow and retire it on the evidence so far.
