# Reading 2 — the D51 re-measurement (executor, 2026-10-15)

Ruling D50's second reading, written blind: from the committed measurement
(`docs/traces/20261015T140229Z-tier3-remeasure.jsonl`, sha256
`33ad32b8b7fdd5c103cff152fba22fa34969503671f7ff7407f4333c62be5a4f`) and
the report and reading sheet the runner derived from it, before the advisor's
reading 1 is opened. The sheet's entries carry no arm labels by rule; this
reading names arms only where the report's own tables do.

## 1. What ran

All 246 planned units were attempted and recorded — 75 each for arms A, D, F
and 21 for arm E′, in the registered seeded order (order sha256
`0fab509676897668994534599dde9581d001b5cc6d4f1e9cdb1b46adc9080065`,
present in the results header). The sweep spent **$2.2343 of the $15.00
authorization**; the fit rule never bound (zero budget stops); no unit was
silently dropped. The scorer was frozen-2026-10-03.3, keys v1, K1 not ruled —
the key-strict and 3 s.f. columns agree on every delivered unit, so the
unruled K1 changed nothing in this sample.

## 2. The failure census — one apparatus fact

**194 of 246 units (79%) ended `incomplete`.** Their stop reasons are a single
apparatus fact, not ninety-nine harness defects: 77 units ended on OpenRouter
`402 Insufficient credits`, 41 on `402 would exceed your available credits
given your current in-flight requests`, and 76 ended `blocked` — the pipeline
finished without an answer after zero successful model calls. The provider's
account exhausted its credits around unit 52: the first 51 units all delivered
(with one more landing later), and every unit after that point failed on the
402s or blocked downstream of them. Per convention 18 a 402 is a fact about
the apparatus until something rules the apparatus out; nothing here rules the
harness out — the failure treatment recorded every unit, in its arm's
denominator, with its class.

## 3. What the delivered sample shows

Delivered-correct of **delivered** (endorsed answers only; the five F units
that delivered unendorsed candidates and the one E′ candidate are scored in
the sheet and carried in the unresolved-candidates table, not counted as
delivered): A 8/12 (0.667), D 17/20 (0.850), F 11/13 (0.846), E′ 1/1.
Against **planned** units the same figures are 0.107 / 0.227 / 0.147 / 0.048 —
but those denominators are failure-dominated, so the of-planned column measures
the credit exhaustion, not the arms. The delivered sample is the plan's first
~52 interleaved units — an early-order slice, not the seeded population.

The prediction exhibits, as they read on this sample:

- **Prediction 3 (unanchored blocks):** the exhibit is real but starved — 5 F
  units carry exactly one unanchored coverage-judge block each (Q9 r2, Q10 r1,
  Q10 r2, Q19 r1, Q23 r1; ask null, empty quote, hazard false), E′ 0 of 21.
- **Prediction 7 (unresolved candidates):** F carried 5 unendorsed candidates,
  2 of them wrong (candidate-wrong rate 0.40); E′ carried 1 (Q17 r3), correct.
- **Prediction 8 (repetition agreement vs correctness):** zero-information —
  no question's three repetitions agreed on quantities in any arm
  (agree_held 0 everywhere; disagreements dominated: D 12 held / 1 missed,
  F 7/6, E′ 1/1). With most repetitions failing outright, agreement never arose.
- **Prediction 9 (F first vs final answer):** untestable — zero F units
  revised (the verify loop never reached a revision on this sample).
- **Cost:** the report's per-arm medians ($0.00, ~1 s) are failure-dominated
  and not comparable to stage 1. The only comparable figures are the delivered
  units' mean costs: A $0.0081, D $0.0122 (against stage 1's $0.0124 median),
  F $0.0084, E′ $0.0283 — but E′ rests on one unit and F's mean mixes arms of
  the workflow that did and did not complete.

## 4. What this run cannot show

The nine pre-registered predictions stand **untested**. The re-measurement was
designed to test them on 246 units; it measured 52. Every rate above rests on
1–20 units per arm, drawn from the plan's early interleaved order, and the two
predictions that need the verify loop's revision behaviour (8, 9) have no
revisions to read. This reading does not interpret the per-arm correct rates as
evidence about the arms, the workflow, or D51's verdict — the sample cannot
carry that weight, and the early-order bias means even the direction of any
difference is unmeasured.

## 5. The re-run condition

The apparatus behaved as designed throughout; the pre-registered guards all
held (order digest, scorer version, both pre-registration digests in the
header, the re-measurement gate's own $15.00 ceiling). The re-run needs one
external input the executor does not hold: the provider account topped up. The
run spent $2.23 before the 402s began, so the account held roughly that much
usable credit at launch; a full 246-unit re-run at the stage-1-like burn the
pre-registration predicted (~$12.95 expected, $15.00 authorized) needs the
account funded well above the authorization. Until then, the measurement of
record is the trace above — a complete, honest record of a run the provider's
balance ended early.
