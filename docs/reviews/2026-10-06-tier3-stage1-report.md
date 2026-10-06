# Tier 3, stage 1 — report and resolution (advisor, 2026-10-06)

**Run.** `evals/results/20261005T215237Z-tier3-run.jsonl`, run 2026-10-05 from 16:52 to 22:59 local.

| setting | value |
|---|---|
| manifest | `tier3-4` |
| scorer | `frozen-2026-10-03.2` |
| servings fingerprint | `e0dc92a3aecb` |
| order seed | 20261003 |
| selection seed | 20261005 |
| units | 105: questions Q6, Q10, Q14, Q15, Q16, Q17, Q23, each answered 3 times by 5 arms |
| spend | $8.4971 of the owner's $30.00 |
| unreconciled liability | none |

**Readings (Ruling D50).** Correctness is read, not scored.

| reading | reader | PASS | FAIL |
|---|---|---|---|
| 1 | advisor | 55 | 3 |
| 2 | executor (PR #162) | 49 | 9 |

The two readings agree on 52 of the 58 sheet entries. The advisor resolved the other six; see the resolution section. The resolved sheet is `evals/results/20261005T215237Z-tier3-run.reading-sheet.json`. The owner's working document is "Tier 3 Stage 1 — Outcome & Course of Action" (Claude Docs).

## Verdict

1. **The full pipeline (arm E) delivered no answer that holds under the frozen key.**
   - 20 of its 21 units delivered nothing.
   - Its one delivered answer had the right forces, but reported them at 3 significant figures, outside the key's ±0.01 kN tolerance.
   - The single-call arms hold 17–18 of 21 under the same key (19–21 when 3 significant figures are accepted).
   - Paired by question, E lost to arm A on all 7 questions (sign test p = 0.016).
2. **The stage-2 rule is met.** |E − A| is 18 of 21 under both counts, against a threshold of 7. The pipeline question is answered, and stage 2 is the owner's option.
3. **The losses are process, not knowledge.**
   - All 20 non-deliveries took the same route: draft, judge, redraft, escalate, no answer.
   - The plans carried correct numbers.
   - The pipeline failed even an XOR truth table, 3 of 3.
4. **Cost.** Arm E took 86% of the spend: $7.33 for no key-held answer. Arm A paid $0.0081 per held answer. A pipeline unit took 972 s on average, against 10 s for arm A.
5. **The question set sits at the single-call ceiling.** It ranks the pipeline against every other arm. It cannot rank tools, cooperation or a stronger model against the inexpensive call.
6. **The scorer is a screen, not a measure.**
   - 18 of its 22 FAILs read PASS.
   - 5 of its 36 sampled PASSes read FAIL under the strict key; all are the Q23 precision case.
   - Its errors depend on answer format and precision conventions, so they differ by serving.

## Resolved results

### By arm

**Key-strict** is the record's figure. **3 s.f.** accepts 3-significant-figure forces on Q23 (key defect K1).

| arm | treatment | key-strict | 3 s.f. | scorer screen | no answer | $ per key-held answer | mean s |
|---|---|---|---|---|---|---|---|
| A | one call, gemini-3.8-flash | **18/21** | 19/21 | 15/21 | 0 | $0.0081 | 9.8 |
| D | one call, kimi-k3 (strong reference) | **18/21** | 21/21 | 14/21 | 0 | $0.0251 | 20.9 |
| C | Inkling drafts, kimi-k3 checks, Inkling revises | **17/21** | 20/21 | 14/21 | 1 (Together 429) | $0.0254 | 36.8 |
| B | A's serving plus fetch and recompute tools, up to 3 calls | **7/21** | 7/21 | 5/21 | 13 (final-call errors) | $0.0197 | 9.7 |
| E | the full pipeline | **0/21** | 1/21 | 1/21 | 20 (16 escalated, 4 blocked) | — ($7.33 spent) | 971.9 |

No unit reached the 1800 s deadline. No output was truncated, and no liability was left open.

### By question (key-strict, correct of 3)

| question | shape | A | B | C | D | E |
|---|---|---|---|---|---|---|
| Q6 XOR alarm | sanity | 3 | 3 | 3 | 3 | 0 |
| Q10 oven cure check | procedure | 3 | 1 | 3 | 3 | 0 |
| Q14 heater selection | specification | 3 | 2 | 3 | 3 | 0 |
| Q15 extensometer check | procedure | 1 | 0 | 3 | 3 | 0 |
| Q16 thermal expansion | sanity | 3 | 0 | 2 | 3 | 0 |
| Q17 tagout rules (29 CFR 1910.147) | lookup | 3 | 1 | 3 | 3 | 0 |
| Q23 parallel bars | derivation | 2 | 0 | 0 | 0 | 0 |

With 3 s.f. accepted, the Q23 row reads 3, 0, 3, 3, 1.

### Registered measures (key-strict)

- **Repeat outcomes.** Each count is the number of questions at that level.

  | arm | 0/3 | 1/3 | 2/3 | 3/3 |
  |---|---|---|---|---|
  | A | 0 | 1 | 1 | 5 |
  | B | 3 | 2 | 1 | 1 |
  | C | 1 | 0 | 1 | 5 |
  | D | 1 | 0 | 0 | 6 |
  | E | 7 | 0 | 0 | 0 |

- **Paired against A** (wins / losses / ties, exact sign test):

  | arm | wins / losses / ties | p |
  |---|---|---|
  | B | 0 / 6 / 1 | 0.031 |
  | C | 1 / 2 / 4 | 1.0 |
  | D | 1 / 1 / 5 | 1.0 |
  | E | 0 / 7 / 0 | **0.016** |

- **Paired against D:**

  | arm | wins / losses / ties | p |
  |---|---|---|
  | A | 1 / 1 / 5 | 1.0 |
  | B | 0 / 5 / 2 | 0.062 |
  | C | 0 / 1 / 6 | 1.0 |
  | E | 0 / 6 / 1 | **0.031** |

- **Stage-2 rule:** the gap is 18 under both counts.

## The resolution

**Where the readings disagreed.** They disagreed on six Q23 entries: 8, 10, 21, 40, 44 and 53, which are D-r2, D-r1, C-r1, A-r1, E-r2 and C-r2. Each answer derives the exact forces (12,353 N, or 210/17 kN). Its headline then reports them at the inputs' 3 significant figures: 12.4 / 17.6 kN. The frozen key accepts 12.35 / 17.65 kN, ±0.01 kN.

- Reading 1 counted the headline as a rounding of a stated in-tolerance value.
- Reading 2 held that the headline is the answer, and that it falls outside the tolerance.

**The rule adopted is reading 2's:** an item holds only if the answer's headline value falls within the frozen key's tolerance. Two reasons:

- the frozen key governs this run's report (D44);
- the headline is what the person asking receives.

**Applied beyond the sheet.** The rule binds every delivered Q23 unit. Four were unsampled scorer passes, which the advisor read once under the rule. The executor confirms these in its next record task.

| unit | verdict | headline |
|---|---|---|
| A-r2 | PASS | 12.35 / 17.65 kN |
| A-r3 | PASS | 12.35 / 17.65 kN |
| C-r3 | FAIL | the 3 s.f. column (12.4 / 17.6 kN) is bolded, as in entry 53 |
| D-r3 | FAIL | 12.4 / 17.6 kN |

**Key defect K1.** For Q23, the key accepts 3 s.f. for the extension (0.882 mm) and both stresses (61.8 and 176 MPa), but requires ±0.01 kN for the forces. That precision is inconsistent with the question's own 3 s.f. inputs.

- **Fix:** the next key version, after this report (D44), with both figures reported side by side.
- **The defect depends on the serving.** Arm D rounds to 3 s.f. every time, so the strict key costs D three answers, C three and A one.

**Agreements.** The 52 agreements include three genuine Q15 failures: entries 52, 56 and 58, which are A twice and B once. Each states every value and verdict, but omits "zero the readout first, never re-zero", which the key's ordered-check-sequence item requires.

## Findings

**F1. The pipeline fails along one fixed route.**
- Every non-delivery escalated or blocked: 16 escalated, 4 blocked.
- The one delivery took 9 calls, 445 s and $0.085, and never escalated.
- Call counts cluster at 30–31 (12 of 20). The build loop runs to its bound, then escalation, then the recovery loop.
- A failed unit cost $0.25–0.50 and took 613–1639 s, whatever the question.

**F2. Where arm E's money went:**

| share | spent on |
|---|---|
| 53% | engineering: drafts and redrafts |
| 31% | escalation |
| 8.5% | judges |
| 3.5% | planning |

**F3. Lookups block.** All three Q17 units ended blocked: the plan demanded a check against the regulation's text, and the pipeline has no tool to fetch it. Arms A–D answered Q17 from knowledge, 10 of 12 correct.

**F4. The planner writes the exam.** The plan prompt says every later phase is judged against its success criteria "and nothing else". The Q23 plan shows what follows. All five of its numbers were exact. Yet four of its six criteria demanded what the question never asked:
- every arithmetic step written inline;
- two independent routes to each stress;
- a presentation format;
- kill triggers on yielding and eccentricity, which the key's `scope_out` excludes;
- a 60 s measured "falsifier", for a hand calculation.

D43's prompt text against this exists and is not enforced.

**F5. The reviewers grade the invented exam.** Of the 12 findings visible in the log:

| what the finding targeted | count |
|---|---|
| plan-invented content | 9 |
| reviewer-invented scope | 3 |
| a wrong value | 0 |

On Q17, two findings contradicted each other ("50 pounds" against "no less than 50 pounds"). The log is a sample, not a census; see R1.

**F6. Ceiling.** Under the strict key, the single calls hold 17–18 of 21. Their misses are of two kinds:
- **Q15** procedure omission: A twice, B once;
- **Q23** precision (K1): A once, C three times, D three times.

**F7. Arm B measured its loop, not its tools.**
- The tools worked: `recompute` gave typed rejections the model adapted to, and `fetch` was used on Q17.
- But the forced final call, where the tools are withdrawn, failed in 13 of the 17 units that had used tools twice (finish `error`, 0 tokens).
- The record labels those 13 `refusal`; they are not refusals.
- B's delivered answers were 7 of 8 correct.

**F8. Arm C's checker concurred 20 of 20 times.** No draft needed catching, so cooperation is untested on this set.

**F9. The scorer.**
- **False negatives: 18 of 22.**
  - Q10 (10): the hold rule written in the answer's own words.
  - Q15 (7): verdicts in table cells, LaTeX inline delimiters, and the cause named by its reference value.
  - Q14 (1): "exceeds" for "fails".
- **False positives: 5 of 36 sampled under the strict key**, plus C-r3 and D-r3 unsampled. The scorer accepted a value in tolerance in the derivation while the headline sat outside it.
- On the screen, D would have ranked below A.

**F10. Reliability.**
- Judge 429s (38), all absorbed by retries.
- One Together 429 (C-Q16-r2), the only provider error that cost arm C an answer.
- 13 gemini final-call errors (arm B).
- One `KeyError: 'choices'` crash, covered by a retry.
- 13 judge parse-failure retries.
- No deadline cuts.

**F11. Sprawl.** E's one delivered answer runs 7,960 characters, against about 2,000 for arm A's median answer.

**F12. No drift** across the run order.

## Repairs owed

| # | repair |
|---|---|
| R1 | Arm E's record drops the pipeline's internals: plan, criteria, iterations, findings, escalation verdict, tokens. Write them into each unit record. |
| R2 | Arm B's final call withdraws the tools. Keep them declared with `tool_choice: none`, and give `serving_error` its own failure class. |
| R3 | Arm C's answers carry stage scaffolding ("Model 1 — Draft Answer"), so readers can tell the arm. |
| R4 | A reply without `choices` crashes the client. It should be a typed provider failure. |
| R5 | Scorer `.3` covers F9's classes, the strict-headline rule and K1, after this report (D44). |
| R6 | Tier-3 pins in `.env` crash the harness settings. The runner should read `.env.tier3`. |
| R7 | PRs #159 (pace-lookup key) and #160 (typed SSL check, liability booking) are held for the fixes the advisor's review specified. |
| R8 | `run_plan` always plans on the architecture tier. Needs a ruling. |
| K1 | The Q23 force precision in the key; see the resolution. |

## Recommendations

1. **Do not run stage 2.** The answer is in, and the set sits at the single-call ceiling.
2. **Ruling D51 (the yardstick):**
   - pass/fail criteria test only what the request asks, enforced by a free mechanical check;
   - D36's output becomes considerations, never graded requirements (precedent: D48 (2));
   - reviewers judge against the question;
   - no criterion demands a check the pipeline cannot perform;
   - verifiable questions take a fast path: one answer, deterministic checks, one cheap check, or "unresolved".
3. **Re-measure** the fast path on all 25 tier-2 questions × 3 and the repaired pipeline on stage 1's seven × 3, with two readers.
4. **Tier 4:** design tasks scored by rubric, where a single call is not at the ceiling.

## Method

- **Reading 1:** the advisor read every scorer FAIL item by item against the key, and every sampled PASS for a wrong value or verdict.
- **Reading 2:** the executor read independently (PR #162).
- **Arm labels** were hidden on the sheet, except arm C's (R3).
- **Unread units** keep the scorer's verdict, except the four unsampled Q23 units, read under the adopted rule.
- **Paired tests** count correct repetitions per question, with an exact two-sided sign test over the questions that are not tied.
