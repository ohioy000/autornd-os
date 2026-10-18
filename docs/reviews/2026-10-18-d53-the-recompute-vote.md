# The recompute vote in the harness (Ruling D53)

**Status:** Ruling D53, issued by the advisor on 2026-10-18 on the owner's instruction "1 then 3, full permission" (option 3 of `2026-10-18-tier4-batch6-headroom-rate.md`).
- **Implementation:** command ARCH-20261018-123.
- **Not decided here:** what a flag *routes* to (§6). It waits on the measurement in §7.

**Decision it serves:** how the harness checks a delivered answer, given that its judges have never made a real catch and an independent recompute has caught every wrong answer measured.

## 1. The evidence

| check | wrong answers flagged | correct answers flagged | where |
|---|---|---|---|
| Judges: validate, review, coverage (tiers 2–4) | 0 real catches. Every dissent read was false. | — | D51 record §12; the tier-4 pilot (F's validate approved T4-15's error and raised a false "proprietary data" dissent) |
| One blind recompute, flash | 2 of 3 | 1 of 3 on T4-15; it would also have flagged kimi's correct T4-58 | `2026-10-18-tier4-pilot-and-recompute-findings.md`; batch 6 |
| **Majority of 3 blind recomputes, flash, typed named fields** | **5 of 5** | **1 of 23**. The one false flag is a field whose name was ambiguous (below). | records of 2026-10-18 (batches 2–6); the T4-42 repeats below |
| Majority of 3, free-text verdict words (tier 2) | — (no wrong values to catch) | 5 of 22. Values only (exploratory): 1 of 22 | `2026-10-18-tier4-batch4-and-tier2-vote-lane.md` |

**The T4-42 repeats.** Kimi-k3 got T4-42 wrong in calibration, so its call was repeated three times, byte-identical (`evals/tier4/probes/repeat_unit.py`, $0.16; trace `docs/traces/20261018T193358Z-repeat-T4-42.json`, 33c1e1c2…).

| sample | selection | time | right? |
|---|---|---|---|
| calibration | VL-25 | 23 s | wrong |
| repeat 1 | VL-42 | 142 s | right |
| repeat 2 | VL-42 | 76 s | right |
| repeat 3 | VL-25 | 32 s | wrong |

- **The miss is a coin flip, not a stable blind spot:** 2 of 4 right. The two misses are the two shortest answers, which supports the brief-reasoning hypothesis on four points.
- **Scored against the batch-5 vote samples,** the vote flagged:
  - **repeat 3, the miss** (selection VL-25 against the majority's VL-42);
  - **repeat 1, a right answer.** It read the row "current compared with I_n (A)" as a difference (−5.5 A); the samples read it as the current (40.5 A).

  That row name was the advisor's own wording, from batch 5's repair, and the batch-5 record already called it ambiguous. The false flag comes from an ambiguous field, not an engineering error.

**What the evidence says:**
- **Check independently; don't judge.** The recompute has caught every wrong answer measured, and no judge has caught one.
- **Use a majority, not a single recompute.** One recompute is only as good as its checker's own answer. The majority has absorbed both lone checker errors measured.
- **Compare typed fields named by the request, never free text.** Typed fields gave 1 false flag in 23, and that one came from an ambiguous field name. Free verdict words gave 5 in 22.
- **The vote cannot see an omission.** On tier 2, three answers that left out a required procedure were not flagged, and could not be.

## 2. The ruling

1. **A new optional tier, `recompute`** (`MODEL_RECOMPUTE`). It ships empty, like the other tiers (hard rule 4). When it is unset, the vote records a skip:
   - `skipped: true`, `flagged: false`, and a plain reason;
   - never an approval-shaped value (the D48 (3) precedent).

   It is optional in `config.py`'s sense: unset turns the feature off, and nothing breaks.

2. **Typed results on the answer.** `ImplementVerdict` gains `results: list[ResultValue]`, defaulting to empty.
   - `ResultValue` is `{ask, value, unit}`:
     - `ask` names an anchored ask by its number or its quote, the way `blocked_on` does (D51 (5));
     - `value` is a number or an identifier string;
     - `unit` is a string, empty for an identifier.
   - The implement prompt asks for one entry per anchored ask of kind `value` or `verdict`, carrying the result the summary states.
   - An answer whose `results` is empty, or names no anchored ask, is **unchecked**: a counted note, never a flag.

3. **The recompute node** (`kind: ai`, `tier: recompute`, `prompt: recompute`, `schema: RecomputeVerdict`, which is `{results: list[ResultValue]}`).
   - **Three independent samples**, declared in the workflow (`args: {samples: 3}`), not a `.env` setting.
   - **Each sample sees:**
     - the request;
     - the grounding context;
     - the anchored asks of kind `value` and `verdict`.
   - **No sample sees** the answer, the plan, any judge's output or another sample.
   - Each sample is one call through the reservation path, with its own worst case reserved and released by identity (D45, D47).
   - `max_tokens` is a setting, `recompute_max_tokens`, defaulting to 32768. That is the cap the tier-4 samples ran at, and none truncated.

4. **The vote** is a free check, `recompute_vote`, registered in `checks.registry`. For each anchored ask the answer's `results` names:
   - **Identity values** (an ask of kind `verdict`, or any non-numeric value) compare after dropping case, spacing and punctuation, with "×" or a count's "x" read as a separator. That is the rule of `evals/tier4/probes/recompute_check.py` `ident`, measured on 25 answers.
   - **Numbers** compare within a **relative tolerance of 3%**, the probe's `TOL`, and only when the units match after `normalise_key`. A unit mismatch makes that ask `no_consensus`, never a flag.
   - **The majority** is a value matched by at least 2 of the samples that answered the ask. With no majority, the ask is `no_consensus`: a counted note, never a flag.
   - **A disagreement** is an ask whose majority exists and differs from the answer's value. `flagged` is true iff there is at least one disagreement.
   - **Fewer than 2 samples parseable** makes the whole vote `unchecked`: `flagged: false`, counted.
   - **Output (typed):**
     - `flagged`, `skipped` and `unchecked`;
     - `disagreements: [{ask, answer, majority, support}]`;
     - `no_consensus: [ask]`;
     - `samples_parsed`.

5. **A flag is a note on the delivery, in this phase.**
   - The run's status is whatever the workflow decides without the vote.
   - The vote's verdict is recorded in the run's outputs and returned with the delivery, so the reader sees, for example: "three independent recomputes disagree on ask 3: the answer gives VL-25, the majority VL-42 (3 of 3)".
   - It never blocks, routes or revises (§6).
   - Under D51 a dissent anchored to an ask may block, but no revision after a flag has been measured. Routing on a flag is ruled only on §7's data.

6. **Where it runs: a new workflow, `answer-and-recompute`.** It is not the standing default; `AUTORND_WORKFLOW` is the owner's standing config (G-3). Its nodes, in order:
   - triage;
   - asks, then `asks_anchored`;
   - context;
   - one `implement` on the engineering tier with no plan, as in verify-first;
   - `blocked_check`, then `blocked_gate`;
   - the free `coverage` and `consistency` checks, as notes;
   - `recompute`;
   - `recompute_vote`.

   **There is no judge and no loop:** the evidence in §1 gives the judge nothing, and a revision is unmeasured. The engineering-rnd and verify-first workflows are unchanged.

## 3. What this costs

- Three recompute calls per run, on the tier the owner sets.
- With gemini-flash on tier 4, three samples cost $0.02 to $0.11 a question (batches 3 to 6).
- On tier 2's short questions, three cost about $0.02.

## 4. What it will not do

- **It cannot catch an omission.** A missing procedure step, section or ask has no value to disagree on. That needs a different check.
- **It cannot catch an error all three samples share.** T4-15's third flash sample made the answerer's own axis error. The majority guards against one shared error, not three.
- **It needs typed results.** An answer that states its results only in prose is unchecked, not passed.
- **It cannot tell an error from an ambiguous ask.** When the request's words admit two readings, a right answer can disagree with the majority (the T4-42 repeat 1). This is one reason a flag is a note in this phase, and why the delivery shows the values that disagree, so the reader can see which case it is.

## 5. Fairness

- The vote compares the answer with three answers to the same question. It never compares with a key.
- The samples see exactly what the answerer saw, except the answerer's own reasoning.

## 6. Not ruled here

1. **What a flag routes to.** Options:
   - one revision shown the disagreement;
   - an escalation;
   - a hold for the reader.
2. Whether the vote checks the standing pipeline's deliverable.
3. Whether `answer-and-recompute` becomes the default.

## 7. The next measurement (before §6 (1) is ruled)

A revision probe, provider-paid, on the owner's authorisation. The answerer is shown the vote's disagreement and asked to re-derive the disputed result, not to adopt the majority. The probe runs on:
- **the recorded wrong answers:** kimi's two T4-42 misses, and the three wrong T4-15 answers the vote was measured on in `2026-10-18-tier4-pilot-and-recompute-findings.md`;
- **recorded correct answers** given a fabricated disagreement, to test whether the answerer gives in.

The prediction, set before the spend: a revision fixes at least 4 of the 5 wrong answers and gives in on at most 1 of 6 correct ones. A revision that gives in more often than that does not route; the flag stays a note.
