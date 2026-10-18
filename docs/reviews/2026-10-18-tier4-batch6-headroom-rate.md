# Tier 4, 2026-10-18: batch 6, the headroom rate on unstated traps

Advisor, 2026-10-18, under Ruling D52 (`docs/reviews/2026-10-16-tier4-the-capacity-test.md`) and the owner's instruction "2 first, full permission". This follows option 2 of `2026-10-18-tier4-batch5-unstated-traps.md`. It is a findings record, not a verdict.

## What ran (traces in `docs/traces/`, cited by sha256 prefix)

| run | units | spend | trace |
|---|---|---|---|
| Batch-6 generation: `x-ai/grok-4.7` on generator v4.1, two calls | 2 calls | $0.5286 | `evals/tier4/batch6/raw/` |
| Batch-6 calibration: D-pages (kimi-k3 with the pages) on the seven kept questions | 7 | $0.9619 | `20261018T185019Z-tier4-calibration-batch6.jsonl` (5fb35f12…) |
| Majority vote: 3 flash samples on each of the seven | 21 calls | $0.3965 | `20261018T192122Z-recompute-vote-samples.json` (c782fb7c…) |

**Tier-4 spend to date: $10.34.** That is $8.45 before this record, plus $1.89 for batch 6.

## Who got what right

Correctness is the advisor's reading against `evals/tier4/batch6/verify.py` (D50).

| question | trap | correct | kimi-k3 with the pages (cost, seconds) | flash, 3 blind samples |
|---|---|---|---|---|
| T4-51 pipe insulation | conductivity at the layer mean temperature | KJ-55 | KJ-55 ($0.37, 384 s) | KJ-55 ×3 |
| T4-52 indexing servo | reflected table inertia | A60 | A60 ($0.07, 110 s) | A60 ×3 |
| T4-53 feeder cable | adiabatic fault heating | V95 | V95 ($0.15, 203 s) | V95 ×3 |
| T4-55 belt-driven motor | torque through the ratio | K-55 | K-55 ($0.02, 19 s) | K-55 ×3 |
| T4-56 pinned tie | net section at the hole | PF-80x10 | PF-80x10 ($0.04, 55 s) | PF-80x10 ×3 |
| T4-57 solvent pump | properties at 80 °C | H-280 | H-280 ($0.16, 215 s) | H-280 ×3 |
| T4-58 series reactor | reactance on a 100 kVA base | B-320 | B-320 ($0.15, 229 s) | B-320 ×2, **B-500 ×1 (wrong)** |

**The strong single call solved all seven.** Batch 6 has no headroom question.

## The headroom rate

| set | questions where the strong single call fails | rate | exact 95% interval |
|---|---|---|---|
| generator v4 and v4.1, traps the corpus does not state (batches 5 and 6) | 1 of 10 (T4-42) | 10% | 0.3% to 45% |
| all verified tier-4 questions | 2 of 24 (T4-15, T4-42) | 8% | 1% to 27% |

Both misses are notation traps. T4-58 is a notation trap of the same kind as T4-42, and kimi solved it.
- On T4-58, kimi reasoned for 229 s.
- On T4-42 it answered in 23 s and stopped at the first option that seemed to pass.

**The hypothesis**, exploratory and resting on two points: the strong call fails when it judges a question easy and reasons briefly, not when the trap is unknown to it.

## The vote

Scored mechanically against kimi's seven answers (`recompute_vote.score`), the majority flagged none, and all seven are correct.
- On T4-58, one flash sample picked B-500. The other two picked B-320, so the majority held.
- A single recompute would have flagged kimi's correct T4-58 answer. This is the second time a lone checker would have raised a false alarm that the majority of three absorbed. The first was T4-15's third flash sample, in the earlier record.

| majority of 3 flash recomputes, all tier-4 answers measured | wrong answers flagged | correct answers flagged |
|---|---|---|
| batches 2 and 3 | 3 of 3 | 0 of 9 |
| batch 4 | — | 0 of 3 |
| batch 5 | 1 of 1 | 0 of 2 |
| batch 6 | — | 0 of 7 |
| **total** | **4 of 4** (95% interval 40% to 100%) | **0 of 21** (0% to 16%) |

Individual flash samples were right in 20 of 21 on this batch.

## What this suggests, not yet what it proves

1. **The strong single call with the documents is hard to beat on generated questions.** It fails about one in ten, even when the trap is unstated. Any structure meant to beat it needs a large question set before a difference can show.
2. **The majority vote is the measured check.**
   - It flagged every wrong answer measured and none of 21 correct ones.
   - It costs about $0.02 to $0.11 a question.
   - On this batch it would have flagged no question, so it would have added cost without changing any delivery.
   - Its expected value is the miss rate times the cost of a shipped error.
3. **The pipelines (F, E) are untested on T4-42.** On T4-15, the only headroom question piloted, both failed.

## Caveats

- **Small samples:** two headroom questions in 24, and four wrong answers measured.
- **Different prompts.** Flash ran in the probe's recompute prompt, kimi in arm D-pages's prompt (see the batch-5 record).
- **The serving.** Kimi ran on the ratified InferenceNet FP4 serving (G-2).
- **The generator family** is one: grok. Four of seven batch-6 questions were flagged in advance as probably easy (`evals/tier4/batch6/VERIFY.md`), and all four were solved.
- **The "Torque" row of T4-55 and the "Current" row of T4-58** were read two ways: rated against required, and catalogue against load. These rows are not the selection, which carries the verdict.

## Options for the next step (the owner's call)

1. **Pilot T4-42** (D52 §5): verify-first (F) and the standing pipeline (E) beside D-pages. The registered pilot ceiling is $5.00, and the API key has about $1.92 of its limit left, so this needs a raise.
2. **Repeat kimi on T4-42 three times** (about $0.06 to $1.20) to test the brief-reasoning hypothesis: is its miss stable, or a one-off?
3. **Rule the vote lane's design** on 4 of 4 and 0 of 21: when the harness runs the check, what a flag does (a note under D51, or a revision), and how answers are typed so the vote can compare them.
