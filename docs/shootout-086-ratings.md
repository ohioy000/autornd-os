# 086 escalation shootout — ratings (blind to serving during scoring)

6 calls, $0.1949 total (Kimi $0.182, Gemini $0.013). Same system prompt,
max_tokens 65536, temp 0.3, fallbacks OFF. Rubric 1-5: attribution /
least-blast fix / executability / honesty.

## Q1 (073's shape: ceiling vs model vs loop)

- Kimi (2463 tok, $0.0375): 4/4/4/5. Correct ceiling call; concrete fix
  (8k reviewer cap + compact schema + resume-from-review). Symptom +
  cause together; configured 112k value unnamed.
- Gemini (1172 tok, $0.0048): 4/3/3/4. Correct call, exact numbers
  quoted — but directive drifts into doing the implementation's job
  ("emit the capacity plan") instead of directing it.

## Q2 (074-078's shape: model vs serving vs router)

- Kimi (6176 tok, $0.0940): 5/5/5/5. Flawless: model indicted
  (identical empties, two providers), router indicted (39 stripped,
  sibling id proves capacity), serving exonerated, structural flaw
  named (truncation scored as verdict), confound-separating experiment
  designed (replay reasoning-disabled: non-empty confirms model,
  empty quarantines endpoint).
- Gemini (781 tok, $0.0034): 2/2/2/3. Answers a different failure —
  generic verbosity diagnosis, never names Baidu/Relace/Alibaba, the
  404, the 39 endpoints, or the sibling id. Honest non-fabrication
  point; a miss, not a compression.

## Q3 (the job: resolution directive)

- Kimi (3262 tok, $0.0501): 5/5/5/5. Names unwired default,
  misclassification, spend trip; correction targets harness wiring
  with a startup assertion.
- Gemini (1263 tok, $0.0051): 5/4/5/4. Excellent change/NOT-change/
  prediction shape; fix-shape vague (no thread-through mechanism).

## Totals (of 20): Kimi ~19, Gemini ~13. Price: $0.182 vs $0.013.

## Outcome

Prediction (Gemini matches attribution, loses Q3 only): REFUTED —
Gemini matched Q1 but collapsed on Q2 (2/5), the question that IS
the escalation job. Slot stays moonshotai/kimi-k3 via Moonshot AI.
The 8x price gap does not survive a 6-point quality gap on the tier
that fires only when everything else failed. Kimi's Q2 experiment
design alone is worth the insurance premium.

## Second bird (tweaks spotted, proposed not done)

1. Escalation prompt bleed (Gemini Q1): "produce a resolution
   directive" can drift into producing the work. One-line constraint
   ("direct, do not produce") would pin it. Free, behaviour-neutral.
2. No ceiling change: Kimi's longest reply (6176) fits 65k with
   headroom; escalation_max_tokens stands.
