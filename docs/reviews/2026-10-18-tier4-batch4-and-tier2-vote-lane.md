# Tier 4, 2026-10-18: the non-Gemini batch, and the vote lane on tier 2

Advisor, 2026-10-18, under Ruling D52 (`docs/reviews/2026-10-16-tier4-the-capacity-test.md`) and the owner's instruction "1 then 2, full permission". This record follows options 1 and 2 of `2026-10-18-tier4-pilot-and-recompute-findings.md`. It is a findings record, not a verdict, and the samples are small.

## What ran (all traces in `docs/traces/`, cited by sha256 prefix)

| run | units | spend | trace |
|---|---|---|---|
| Batch-4 calibration: D-pages (kimi-k3 with the pages) on T4-32 to T4-34 | 3 | $0.0829 | `20261018T164435Z-tier4-calibration-batch4.jsonl` (9877d1ff…) |
| Majority vote: 3 flash samples each on T4-32 to T4-34 | 9 calls | $0.0651 | `20261018T164638Z-recompute-vote-samples.json` (e7b9c7c9…) |
| Vote lane on tier 2: 4 flash calls on each of the 25 frozen questions | 100 calls | $0.6449 | `20261018T170701Z-vote-lane-tier2.json` (063f11fd…) |

Batch 4's generation cost $0.16 and is recorded in `evals/tier4/batch4/VERIFY.md`.

**Spend to date:**
- Tier 4: $8.13. That is $7.82 before this record, plus $0.31 for batch 4.
- Tier-2 vote lane: $0.64.

## Step 1: a batch from a non-Gemini generator

Batch 4 was written by `x-ai/grok-4.7` with generator v3 unchanged. One question of four was dropped as broken (T4-31). Correctness below is the advisor's reading against `evals/tier4/batch4/verify.py` (D50).

| question | correct | kimi-k3 with the pages | flash, 3 blind samples |
|---|---|---|---|
| T4-32 contactor | HC-50 | HC-50 | HC-50 ×3, I_allow 36.125 A in all three |
| T4-33 viscous pump | PP-2 | PP-2 | PP-2 ×3, Q_del 0.006396 m³/s in all three |
| T4-34 heatsink | VX-320 | VX-320 | VX-320 ×3, R_sa 0.525 K/W in all three |

**What it shows:**
- Both single calls solved every question, so calibration keeps none.
- Flash's strength is not only a family affinity with the Gemini generator: it holds on questions written by another family.
- The batch does not settle whether T4-15 was an affinity effect. VERIFY.md flags every batch-4 trap as a rule the corpus states explicitly. These are rule-application questions, easier than batch 3, with no notation trap like T4-15's.

**The tally:**
- Of 14 verified tier-4 questions, the strong single call fails one (T4-15).
- On batch 4 the vote had nothing to catch: all nine samples were unanimous and right.

## Step 2: the vote lane on tier 2

**Design** (`evals/tier4/probes/vote_lane_tier2.py`):
- Each question was rendered exactly as tier-3 arm A renders it (`evals/tier3/prompts/arm_a.md`), with one change: a suffix asking for a closing fenced JSON block, `{"values": [...], "verdicts": [...]}`.
- Four flash calls ran per question. Sample 1 is the delivered answer; samples 2 to 4 are the checkers.
- The designed rule flags an answer in two cases:
  - fewer than two checkers report a value within 3% of one of its values;
  - fewer than two checkers report the same set of verdict words.
- The rule was fixed before the run.

**Correctness of the delivered answer** is the advisor's reading of sample 1 against `evals/tier2/keys.json`, item by item (D50).
- **22 of 25 are complete and correct.**
- **25 of 25 have every value and verdict correct.**
- The three misses are Q15, Q20 and Q25. Each asks to "write the … check", and the key requires the ordered procedure. Each answer computes the result and verdict correctly but omits the procedure.
- The organisation items (Q14, Q19, Q24) were read loosely, as grouping rather than exact section titles.

**The scorer, as a screen:** 16 PASS and 9 FAIL. Six of the nine FAILs are correct answers (Q4, Q5, Q10, Q18, Q19, Q24), and the other three are the incomplete ones. All 16 PASSes read correct.

| rule | flagged | incomplete answers flagged | correct answers flagged |
|---|---|---|---|
| Designed: values and verdict sets | Q4, Q9, Q12, Q19, Q22 | 0 of 3 | 5 of 22 |
| Values only (**exploratory, chosen after seeing the data**) | Q19 | 0 of 3 | 1 of 22 |

**Why the flags were false:**
- The verdict comparison compares free text. "as N" against "as Nitrogen" (Q12). Checkers leaving the verdict list empty (Q22). Selection words included in some answers and not others (Q4, Q9, Q19).
- The one values-only flag (Q19) came from two checkers that left out the 0.264 W minimum rating. They reported only the selected 0.500 W.

**Cost:** $0.0064 a call. Three checkers add about $0.019 a question on tier 2's short answers, against about $0.12 on tier 4's.

**A confound the probe introduced:**
- The JSON suffix may have narrowed the answers toward values and verdicts.
- The same model, with the same prompt and without the suffix, has tier-3 answers in `docs/traces/`. A keyword screen of them (not a reading) found:
  - Q25: 2 of 2 mention enabling and disabling the supply and the monotonic sweep (`20261015T140229Z-tier3-remeasure.jsonl`);
  - Q15: 3 of 3 mention zeroing, a weaker sign (`20261005T215237Z-tier3-run.jsonl`);
  - Q20: 0 of 1 mention the return tank.
- So the procedure omissions should not be charged to flash in full.

## What this suggests, not yet what it proves

1. **Tier 2 measures the lane's false-flag cost, not its catch rate.** Flash got every value right, so there was nothing numerical to catch. The only catch evidence is still tier 4's 3 of 3 on T4-15.
2. **The vote works on named fields, not on free text.**
   - On tier 4 the request names its result rows, and the vote compared those rows: 0 of 9 correct answers flagged.
   - On tier 2 free verdict words gave 5 of 22 false flags.
   - A lane in the harness would need the request's asked quantities as typed fields before it votes.
3. **The vote is blind to omissions.** Three answers that left out a required procedure were not flagged, and could not be: the checkers agreed on every number. Completeness against the request needs a different check.

## Caveats

- One reader (the advisor), and one delivered sample per question.
- The values-only rule was chosen after the data was seen. It is a hypothesis for the next measurement, not a result.
- The suffix confound above applies to step 2's completeness figures, not to its values.

## Options for the next step (the owner's call)

1. **The open case, a trap the corpus does not state:** a small non-Gemini batch whose trap is a convention of the governing standard, not a rule written in the pages (generator v4). It would be answered by kimi-k3, flash and the vote. A batch of four should cost about $0.50.
2. **Rule the vote lane's design before any harness change:**
   - typed result fields taken from the request;
   - a flag as a note, not a veto (D51);
   - completeness as a separate check.

   This changes what the harness would conclude, so it is a ruling, not a repair.
3. **Rule the standing pipeline's next step (D52 §8):** this is unchanged from the previous record.
