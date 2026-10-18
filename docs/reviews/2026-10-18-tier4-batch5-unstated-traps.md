# Tier 4, 2026-10-18: batch 5, traps the corpus does not state

Advisor, 2026-10-18, under Ruling D52 (`docs/reviews/2026-10-16-tier4-the-capacity-test.md`) and the owner's instructions "1 first, full permission" and "raised to 74, go". This follows option 1 of `2026-10-18-tier4-batch4-and-tier2-vote-lane.md`. It is a findings record, not a verdict, and the sample is three questions.

## What ran (traces in `docs/traces/`, cited by sha256 prefix)

| run | units | spend | trace |
|---|---|---|---|
| Batch-5 generation: `x-ai/grok-4.7` on generator v4 | 1 call | $0.1700 | `evals/tier4/batch5/raw/20261018T172910Z-F2.raw.json` |
| Batch-5 calibration: D-pages (kimi-k3 with the pages) on T4-41 to T4-43 | 3 | $0.0797 | `20261018T180951Z-tier4-calibration-batch5.jsonl` (e4e6b76d…) |
| Majority vote: 3 flash samples each on T4-41 to T4-43 | 9 calls | $0.0735 | `20261018T181158Z-recompute-vote-samples.json` (f9ab93b6…) |

**Void runs, $0:** a first calibration and vote launch (`20261018T175054Z`, `20261018T175051Z`) got HTTP 403 on every call. The API key's own limit was spent. The owner raised it, and the gate was set again for the rerun (R11). The void files stay in the git-ignored `evals/results/` and are not evidence.

**Tier-4 spend to date: $8.45.** That is $8.13 before this record, plus $0.32 for batch 5.

## The batch

Generator v4 requires the trap to come from the answerer's own knowledge, never from a rule in the corpus. `evals/tier4/batch5/VERIFY.md` has the verification, one repair and one drop. Three questions were frozen:
- **T4-41:** a hoist's acceleration load, implied and not named.
- **T4-42:** an inverter catalogue whose I_n is an amplitude, while the motor current is RMS.
- **T4-43:** pump head converted from pressure with the solvent's density, not the printed water test density.

## Who got what right

Correctness is the advisor's reading against `evals/tier4/batch5/verify.py` (D50).

| question | correct | kimi-k3 with the pages (one call) | flash, 3 blind samples |
|---|---|---|---|
| T4-41 hoist reducer | WR-260 | WR-260 | WR-260 ×3, 1729.6 N·m, 8648 N |
| T4-42 inverter | VL-42 | **VL-25: wrong**. It compared the 28.64 A RMS motor current with the 33 A amplitude rating | VL-42 ×3, compared 40.5 A |
| T4-43 solvent pump | CP-40 | CP-40 | CP-40 ×3, 56.33 m, NPSH margin 1.3 m |

**T4-42 is the second headroom question** of 17 verified tier-4 questions. The first was T4-15. Both are notation traps, and the cheap model got both right: T4-15 in 5 of 6 samples, T4-42 in 3 of 3.

Kimi's T4-42 answer took 23 s and $0.019 and reasoned briefly. It checked VL-25 first, found 33 ≥ 28.64 and stopped.

## The vote

The majority of 3 flash recomputes was scored mechanically against kimi's answers (`recompute_vote.score`, comparing the key rows of `recompute_vote.py`). It flagged:
- **kimi's T4-42:** selected model VL-25 against the majority's VL-42;
- **neither correct answer.**

The batch-4 kimi answers, scored the same way against the batch-4 vote samples, were also unflagged (0 of 3).

| majority of 3 flash recomputes, all tier-4 answers measured | wrong answers flagged | correct answers flagged |
|---|---|---|
| batches 2 and 3 (record of 2026-10-18) | 3 of 3 | 0 of 9 |
| batch 4 | — | 0 of 3 |
| batch 5 | 1 of 1 | 0 of 2 |
| **total** | **4 of 4** | **0 of 14** |

## What this suggests, not yet what it proves

1. **An unstated trap found headroom where stated rules did not.**
   - Batch 4, whose traps were written in the pages, had none.
   - Batch 5, whose traps the pages do not state, had one in three.
   - Generator v4 is the better instrument for D52's calibration.
2. **The cheap model is not the weak link on these questions.**
   - On both headroom questions, flash with the pages answered correctly where the strong single call did not.
   - Three flash samples cost about $0.02 to $0.11 a question (batches 3 to 5). Kimi's single call costs about $0.02 to $0.39.
3. **The recompute vote is still the only check that has caught an error.** Every wrong answer measured was flagged, and no correct one, at about $0.025 a question on this batch.

## Caveats

- **Small samples:** two headroom questions and four wrong answers in all.
- **Different prompts.** Flash ran in the probe's recompute prompt, kimi in arm D-pages's prompt:
  - flash: the request and the pages, "Compute the design yourself", answer as JSON, with the system line "You are a careful senior engineer";
  - kimi: arm D-pages's own prompt.

  The comparison is of a model in a setting, not of two models under one prompt.
- **The serving.** Arm D is kimi-k3 on the owner's ratified pin (InferenceNet, an FP4 serving; R7, G-2). A different serving of the same model might reason longer.
- **My T4-42 row wording.** I chose "current compared with I_n (A)" for the repair. Kimi read it as a difference (−4.36 A), not as the current compared. The selection, the first key row, carries the verdict either way. The next repair should name the quantity, for example "current checked against I_n (A)".
- One reader (the advisor), and one verifier per batch, the advisor's own.
- The generator family (grok) differs from both answerers. Family affinity, a caveat of D52 §10, does not apply to this batch.

## Options for the next step (the owner's call)

1. **Run the pilot on T4-42** (D52 §5; the batch's registered pilot ceiling is $5.00): verify-first (F) and the standing pipeline (E) beside D-pages. This asks whether either structure catches what the single call missed, as T4-15 asked. F and E failed there.
2. **A larger v4 batch** (4 to 8 questions, about $0.20 to $0.40 to generate) to estimate the headroom rate and widen the vote's measured sample.
3. **Rule the vote lane's design** (an option of the previous record), now with 4 of 4 and 0 of 14 behind it.
