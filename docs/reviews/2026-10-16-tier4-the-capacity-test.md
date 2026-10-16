# Tier 4: the capacity test (proposed Ruling D52)

**Status:** proposed by the advisor on 2026-10-16 and awaiting the owner's sign-off. Nothing here runs or spends until the owner approves §12.

**Decision it serves:** whether the pipeline's structure (grounding, a plan, check-and-revise loops and review) recovers answers a single call misses, on work hard enough for a single call to miss. That is success bar S2 (value) from the D51 record §2. No run has tested it yet.

## 1. Why tier 4

Tiers 2 and 3 used workbook-grade questions: every input is given and there is one right answer.

| measured | result | where |
|---|---|---|
| Strongest single call, read by hand | stage 1: 18/21 key-strict, or 21/21 accepting 3 s.f. (K1); starved run: 19–20/20 | `docs/reviews/2026-10-06-tier3-stage1-report.md`; D51 record §12 |
| Cheapest single call | stage 1: 18/21 key-strict, or 19/21 accepting 3 s.f.; starved run: 10–11/12 | the same |
| Full pipeline vs the single call | no win anywhere; 13–60× the cost and 25–100× the time for the same correct answer | the same |
| Judges and checks on these questions | 0 real catches. Every dissent read was false: coverage ×6, validate ×1, review ×3 (starved run); 0 of 12 review findings named a wrong value (stage 1) | D51 record §12 |

On questions a single call already answers, structure can only lose answers. Tier 4 asks the other question: on work a single call gets wrong, does structure get it right?

## 2. What a tier-4 question is

There are two families.

- **F1, everything given but hard to get right.** All data is in the request. Each question has:
  - interlocking decisions, where one choice constrains the next;
  - at least eight dependent computed quantities;
  - selection from finite catalogues given in the request;
  - at least one requirement with a margin under 5%, so a slip early in the chain changes the outcome.
- **F2, the data lives in a corpus.** The request names a fictional product line. Its catalogue tables, curves and rules live only in a fictional corpus profile (`profiles/tier4.yaml`, documents under `docs/tier4/`). The `cupline` profile (`profiles/cupline.yaml`) is the precedent. No model knows this data from training, and no search can find it.

**Rules for every question:**
1. **Closed-world.** Every number the answer needs is in the request or the corpus.
2. **Public.** Questions are generated (§4) and are never the owner's R&D questions, which stay private.
3. **Many valid designs may pass.** A question is graded by its requirements, not against one key.
4. **Every requirement can be checked by recomputation** from the values the answer chooses.
5. **The request asks for a results table at the end,** headed `Results`, with named rows. It is an ask like any other, the same for every arm.

**Example shapes, for illustration only** (the set is generated in §4):
- a bolted joint that must pass slip, separation and fatigue together;
- an active filter from standard component values meeting gain, cut-off and noise;
- a pump and pipe selection against a system curve and suction-margin limits;
- a shaft with a keyway and bearings meeting deflection, stress and life;
- F2: a heat sink chosen from a fictional extrusion catalogue;
- F2: a commissioning procedure from a fictional machine manual's interlock rules.

## 3. How answers are graded

- **The result is two blind hand readings** (D50), from an arm-blind sheet. Each reading records every requirement as held or not held, and whether the reasoning that reaches it is sound.
  - A unit holds when every requirement holds and the results table's values are the ones the answer derived.
  - A missing or garbled table is recorded separately, and the reader grades from the body. Format is not engineering.
- **The screen is a requirement checker.** It reads the `Results` table and recomputes each requirement from the question's formulas and data. It is verified like `verify_keys.py`:
  - the reference design passes every requirement;
  - each known-wrong design fails the requirement it was built to fail.

  The checker is never the reported result. Prediction P8 measures how often it agrees with the readings.

## 4. Building the set

1. **The owner runs the generator prompt** (Appendix A) on a model that is not one of the arms' pins. It produces 20 candidates: 12 F1 and 8 F2. Each candidate carries:
   - the request;
   - the requirements, with their checks;
   - a reference design and a worked solution;
   - two known-wrong designs;
   - for F2, the corpus pages;
   - a difficulty rationale.
2. **The advisor verifies every candidate** independently:
   - every requirement recomputed;
   - the reference design passes and each wrong design fails;
   - the corpus names no real product or firm;
   - no ambiguity.

   A candidate that fails verification is dropped or returned for a fix, never fixed silently.
3. **The owner freezes the verified set** (D44). From then on, requests, requirements and corpus stay byte-identical. A change is a new version, reported side by side.

## 5. Calibration: keep only questions with headroom

- **F1:** the cheapest and the strongest single calls answer each F1 candidate once. A question is kept if, read by hand, either fails it.
- **F2:** the strongest single call answers each F2 candidate once, **with the corpus pages handed to it in the prompt** (oracle retrieval). A question is kept if that call fails it, so F2 measures what structure adds beyond having the data. A single call without the pages cannot answer F2 by construction, so that comparison is not made.
- **Target:** 10 kept questions, at least 6 F1 and at least 4 F2. If fewer than 8 qualify, the set is too easy. Regenerate harder; the bar is never lowered.
- **Selection bias:** the main run uses fresh repetitions, and calibration answers are never pooled into the result. The main run's single-call rate on the kept questions is reported, so any regression to the mean is visible.
- **Cost:** about $3 (cap $5).

## 6. The measurement

The arms use the standing pins (tier-3 fingerprint `e0dc92a3aecb`) unless the owner re-pins first under G-2.

| arm | what it is | F1 | F2 |
|---|---|---|---|
| A | single call, the cheapest serving | yes | no (it cannot have the data) |
| D | single call, the strongest serving; on F2 with the corpus pages in the prompt | yes | yes |
| F | verify-first, with its own grounding. Its first answer is recorded beside its final one, so F-first is a single engineering-tier call with grounding | yes | yes |
| E | the standing pipeline (engineering-rnd), with its own grounding | yes | yes |

**What each comparison isolates:**

| comparison | isolates |
|---|---|
| E vs D | the whole structure against the strongest single call holding all the data |
| E vs F-first | plan, loops and review, with the same tiers and grounding |
| F-final vs F-first | what one check-and-revise adds (prediction 9 of D51, finally with headroom) |

**Plan:**
- 10 questions × 2 repetitions:
  - F1: 6 × 2 × 4 arms = 48 units;
  - F2: 4 × 2 × 3 arms = 24 units;
  - 72 units in total.
- Seeded interleaved order, its digest registered.

**Limits:**
- Deadline: 3600 s per unit.
- Per-unit ceilings, which the preflight sets from measured worst cases and which may rise only with the figures:

  | arm | A | D | F | E |
  |---|---|---|---|---|
  | ceiling | $0.10 | $0.30 | $0.40 | $1.50 |

**Cost:**
- Expected about $15–25: the pipeline is most of it, at about $0.50–1.00 per hard unit.
- Authorisation cap $30.

**Apparatus,** all repaired before this run (#181–#185):
- the credit preflight;
- the stop at the first out-of-credit error, with resume;
- the exact spend gate;
- retries for disconnects and TLS alerts;
- terminal reasons in every record.

## 7. Predictions (pre-registered)

Each is reported as it reads. None is edited after this section is committed (convention 7).

- **P1 Headroom.** At least 8 of the 20 candidates defeat the calibration's single call.
- **P2 The bar.** On the 10 kept questions, D holds at most 13 of 20 units in the main run.
- **P3 Structure adds value.** E holds at least D + 3 units (of 20).
- **P4 The check helps.** F revises at least 4 units, and those revisions go wrong-to-right more often than right-to-wrong.
- **P5 Beyond retrieval.** On F2, E holds at least D + 2 units (of 8). D holds the pages, so this is structure, not lookup.
- **P6 Honesty.** E's and F's unendorsed candidates read wrong more often than their delivered answers.
- **P7 Economy.** E's cost per held answer is at most 30× D's, and its median latency at most 20× D's.
- **P8 The screen.** The requirement checker agrees with the resolved readings on at least 90% of units.

## 8. The decision this run makes

| outcome | what it means | next |
|---|---|---|
| E ≥ D + 3 and P7 holds | Structure pays on hard work. | Routing (P7 of D51) is ruled from the shapes E won. The pipeline is the lane for them. |
| E ≥ D + 3 but P7 fails | It pays in accuracy but not economy. | The owner chooses: an accuracy lane at that cost, or make the pipeline cheaper (a lighter plan, fewer reviewers) and re-test. |
| F-final ≥ E − 1 at no more than 1/5 of E's cost | The smallest structure does the job. | Verify-first is the hard-question lane; the full pipeline narrows or retires. |
| \|E − D\| ≤ 2 | Structure does not pay at these pins. | The product is a single call with verify-first's check as a flag. The pipeline is redesigned before any more spend on it. |
| E ≤ D − 3 | Structure harms even on hard work. | Retire the full pipeline. Verify-first stays only where it holds at least D. |
| P1 fails | The questions are too easy. | Regenerate harder. No main run. |

With 10 questions the readings are paired by question and reported question by question. The thresholds are sized for 20 units per arm and are not tests of significance.

## 9. Fairness to the pipeline

- **Fixed before the run:**
  - coverage is a note (R1);
  - an unsourced "that's false" is a note (R2);
  - the call limit counts grounding (R3);
  - the exact gate (R4);
  - disconnect retries (R5);
  - F's ceiling (R6).
- **Kept as measured, not fixed:**
  - review sprawl: 12 findings on one Q17 answer;
  - false medium-severity findings;
  - escalation cost;
  - the slow architecture serving.

  These are what the run is about.
- **Freeze:** after the pre-registration commit, no harness change except a fix that stops the run working (D51 §7's rule).

## 10. How tier 4 could mislead, and what we would see

| risk | what we would see | guard |
|---|---|---|
| The generator writes in its own style | all arms affected alike | the generator is not an arm's pin |
| The checker false-fails good designs | checker FAILs that read as held | the readings are the result; P8 |
| Regression to the mean after calibration | single calls do better in the main run | fresh repetitions; both rates reported |
| The corpus leaks real data | an arm answers F2 without retrieving | fictional names verified (§4); retrieval logged per unit |
| F2 measures lookup, not structure | E wins F2 only where D lacked the pages | D always holds the pages (§5, §6) |
| The pins drift between calibration and main | different serving fingerprints | the fingerprint is checked at both |
| Too few units to see a difference | gaps inside ±2 | the decision table treats ±2 as "does not pay", not as evidence of harm |

## 11. Sequence, owners and costs

| step | who | cost |
|---|---|---|
| 1. Sign off this design, or amend it | owner | — |
| 2. Command 122: tier-4 tooling. The dataset format, the requirement checker, the verify script, the corpus profile, calibration and main modes, D-with-pages and the reading sheet | executor | $0 |
| 3. Run the generator prompt (Appendix A), in parallel with step 2 | owner | the owner's own model |
| 4. Verify every candidate | advisor | $0 |
| 5. Calibration | owner's gate | about $3 (cap $5) |
| 6. Freeze the 10; pre-register §7–§8 by sha256; mocked dry run of all 72 units | executor, owner signoff | $0 |
| 7. The main run, 72 units | owner's gate | about $15–25 (cap $30) |
| 8. Two blind readings, resolution, verdict against §8 | executor (reading 2, first), advisor (reading 1) | $0 |

## 12. The owner's decisions

1. **The design:** approve, or amend the families, size or arms.
2. **Budget:** calibration cap $5; main-run cap $30. A smaller first pass is possible at 6 questions × 2 repetitions, cap $20.
3. **Generator:** which model runs Appendix A. It must not be one of the arms' pins.
4. **Pins:** unchanged (`e0dc92a3aecb`), or re-pin first under G-2.

## Appendix A: the generator prompt

The owner pastes this into the generating model unchanged. The output goes to the advisor for verification, not into the repository directly.

```
You are writing a benchmark of HARD, CLOSED-WORLD engineering design questions. Each must be answerable from the data given, checkable by recomputation, and hard enough that a careful expert working in a single pass has a real chance of getting at least one requirement wrong.

Produce exactly 20 candidates as one JSON array:
- 12 of family "F1" (all data in the request);
- 8 of family "F2" (the data lives in fictional corpus pages you also write).

Each candidate is an object with these fields:
- id: "T4-01" ... "T4-20"
- family: "F1" or "F2"
- domain: mechanical, electrical, fluid, thermal, structural, or controls
- request: the question exactly as a user would ask it, at most 350 words, SI units. It must end with: "End with a table headed Results with these rows: <row names and units>."
- requirements: a list of 4 to 8 objects, each with:
  - id;
  - statement: plain words;
  - check: an exact formula or condition over the Results values and the given data;
  - tolerance: absolute or relative, or "exact" for a catalogue choice.
- reference_design: the Results values of one design that passes every requirement.
- worked_solution: the full derivation of the reference design, every intermediate value shown.
- wrong_designs: 2 objects, each with values and the requirement ids it fails and why. Make them the mistakes a competent engineer plausibly makes.
- corpus_pages: F2 only. 1 to 3 markdown documents (catalogue tables, curves as tables, rules) holding data the request needs and does not state.
- difficulty_rationale: one or two sentences on where a single pass is likely to slip.

Rules:
1. Closed-world: every number needed is in the request (F1) or the corpus pages (F2). No outside data, no standards the answer must recall.
2. At least 8 dependent computed quantities, and interlocking choices (one selection constrains the next).
3. Selection from finite catalogues given in the data, so checks are exact.
4. At least one requirement with a margin under 5% for the reference design.
5. Several designs may pass. The requirements alone decide, never "match the reference".
6. No trick wording, no ambiguity, no missing data, no contradictory data.
7. F2 corpus pages describe fictional products and firms only. Invent names, so that nothing can be looked up.
8. Vary the domains: at most 4 candidates per domain.
9. Output the JSON array only.
```
