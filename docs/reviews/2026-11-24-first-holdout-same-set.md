# The first hold-out asked again of the harness as it is now, 2026-11-24

Preregistered in `docs/preregistration-20261123-first-holdout-same-set.md` (6441fc7), pushed alone before the spend. The owner's ruling
that set it: keep every addition, no frontier model, compare our harness's outputs on the same set. '$2.03' was spent of a ceiling of
'$2.80' (126 answers, '$0.0161' an answer). Files and sha256 are in
`docs/traces/20261124T-first-holdout-same-set-MANIFEST.sha256`.

## The point

- **The preregistered bars are not met.** Right answers: **104 of 126 (82.5 percent)** against the bar of 119 and the old 113.
  Not-right answers among the 31 questions that were right in every old draw: **4** against the bar of at most 2.
- **But 16 of the 17 answers that were never made are provider failures,** not answers the harness got wrong: 13 gateway timeouts (504,
  "the operation was aborted") and 3 upstream rate limits (429) on the answer model, 13 of the 17 in the third draw. One (X31) was
  blocked by the harness's own rule. The old run had 4 undelivered. **Of the 109 answers made, 104 were right (95.4 percent)**;
  of the old run's 122 made, 113 (92.6 percent). The difference is 5 wrong against 9, p = 0.27 one-sided: **no clear gain, no clear loss.**
- **So the data does not show that the additions raised the first hold-out.** It shows the per-answer rate near 93 to 95 percent on
  both runs, and a reliability problem on the third draw that has nothing to do with the additions.
- **The eleven questions that failed before improved; the 31 that never failed did not stay perfect.** The eleven: 25 right of 26 made
  (96 percent) against 20 of 29 made. The 31: 79 right of 83 made (95 percent) against 93 of 93. Both moves are what picking groups by
  their old result would give by chance (the eleven can only rise, the 31 can only fall), so neither is read as the additions' doing.

## What was run and how it was read

The tree `957bc08` (main with the revised caution fix), the owner's `.env` with the reader tier on, no pins, profile `engineering`,
workflow `answer-and-recompute`, X1 to X42 three draws each in two invocations. Four blind readers read the 109 delivered answers
(codes hide draw and invocation, shuffled): 104 right, 5 wrong. I read the five wrong ones and a seeded sample of 20 right ones
(`random.Random('fx-second-reading-20261124')`) before looking at the old labels or any caution, and agreed with every verdict, so
the blind reading stands unchanged. The 20 right answers were checked against the key from the readers' extracts and keys, not
by re-reading every line of each answer.

## The numbers

| | Now | Old run (2026-11-17) |
|---|---|---|
| Right of 126 (undelivered counted not right, as preregistered) | **104** (82.5 %) | 113 (89.7 %) |
| Answers made | 109 | 122 |
| Right of those made | **104 (95.4 %)** | 113 (92.6 %) |
| Undelivered | 17 (16 provider errors, 1 harness block) | 4 (2 cut off, 2 harness blocks) |
| The eleven, right of made | 25 of 26 | 20 of 29 |
| The 31, right of made | 79 of 83 | 93 of 93 |
| Questions with more / same / fewer right draws | 5 / 23 / 14 | |
| Cost an answer | '$0.0161' | '$0.0108' |
| Seconds an answer | about 180 | 107 |

By draw: draw 1 40 of 42 right; draw 2 38 right and 4 undelivered; **draw 3 26 right, 3 wrong and 13 undelivered**. The recompute vote did
not run on 10 units (the caution says so) and the answer model was unreachable on 16: the third draw was made while the provider was
failing. The run is slower and dearer an answer than the old one for the same reason (waiting, the reader tier's '$0.003').

## The five wrong answers (both readers agree)

| Unit | Question | What is wrong | Cautions shipped |
|---|---|---|---|
| X3, draw 1 | WHO 2021 SO2 24-hour and NO2 annual | No figure given; both asks called "not stated" while the page that holds them was fetched empty | "not stated" on both asks |
| X14, draw 1 | RED Art 3(3) and Delegated Reg 2022/30 | Applies-from date given as 1 August 2024, the superseded original; the 2025 postponement missed | none |
| X26, draw 3 | WebAssembly page size and limits | The i32 maximum in bytes (4 GiB) refused as not stated | "not stated", and others |
| X35, draw 3 | CODATA 2022 Rydberg constant and the 2018 value | The 2018 value refused as not stated | "not stated", and others |
| X39, draw 3 | SPCC capacity ceilings | The 42,000 gallon ceiling defined as aboveground plus buried; the key says completely buried | none |

Three of the five (X3, X26, X35) are a **"not stated" answer for something the sources do state**; each carries the caution that says
the only check behind it was a word search of the pages read in full. Two (X14, X39) are a figure or a definition wrong with no
caution. X14 is the known stale-page weakness. X26 and X35 were made with the recompute vote not running (draw 3).

## What this says about the additions

- **Nothing here supports a gain from the additions on this set, and nothing supports a loss.** The per-answer rate is the same inside
  its noise (95.4 against 92.6 percent made, p = 0.27). The earlier deduction stands: accuracy comes from retrieval, and the
  additions' effect on it is small enough that 126 answers cannot see it.
- **The finding that matters is reliability.** One in eight units delivered nothing, all but one because the answer model's
  provider did not answer, and the harness has no retry for a 504 abort or an upstream 429 beyond its bounded loops. That is
  retry wiring, an instrument repair, and a candidate for the next task; it is **not** done here.
- **The "not stated" refusals are the weakness the earlier test found,** now seen on a third set: X3, X26 and X35. The caution catches
  them, as designed; none of them is stopped.
- **Nothing is removed,** as the owner ruled.

## What is not claimed

- Which addition did what. The code, the model line-up and the provider's condition all moved since 2026-11-17.
- That 95.4 percent is the harness's rate. The 17 units that delivered nothing are left out of it, and the old run's 4 were left out the same way.
- That the first hold-out is a fresh set. It is the set the fixes were made against.
