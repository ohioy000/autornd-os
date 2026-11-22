# The model line-up smoke, five runs (2026-11-22)

**Status:** owner-directed in conversation 2026-11-22 ("1 dollar ceiling to test the 2 new models and original models in a
small question set that tests every combo tier models"). Spend **'$0.1183'** of the '$1.00'. Pre-registration:
`docs/preregistration-model-lineup-smoke.md` (committed before the spend, and amended three times, each before the spend it
governs). Every cell is **one run (n = 1)**; this is evidence of serving, typed output, cost and the guard, **not of answer
quality**, and no scorer verdict is reported as a result.

## What ran

| Run | Profile | Triage model (provider) | Answer model (provider) | Cost | Seconds | Calls |
|---|---|---|---|---|---|---|
| A | `engineering`, no pin (the original models) | the earlier triage model (Crusoe) | the global answer model (DeepInfra) | '$0.0058' | 98 | 10 |
| B | `engineering` with the `qwen4-max` pin | `hy4-flash` (Tencent) | `qwen/qwen4-max` (Alibaba) | '$0.0131' | 91 | 10 |
| C | `finance` | `hy4-flash` (Tencent) | `google/gemini-4-hydrogen` (Google) | '$0.0241' | 52 | 10 |
| D | `medical` | `hy4-flash` (Tencent) | `google/gemini-4-hydrogen` (Google) | '$0.0648' | 123 | 10 |
| E | `legal` | `hy4-flash` (Tencent) | `z-ai/glm-5.3-flashx-legal` (Z.AI) | '$0.0105' | 93 | 10 |

The answer tier's cost: A '$0.0019', B '$0.0078', C '$0.0216', D '$0.0599', E '$0.0066'. Hydrogen's two questions cost 3 to 9
times the others'; the one medical question cost the most because its answer was the longest (7,541 completion tokens).

## Predictions, scored (as amended)

- **L1, each answer call served by its seat, n = 5: holds.** One id and one provider on the `engineering` tier in every run.
- **L2, triage as the table says: holds** (restated in Amendment 2: `hy4-flash` via Tencent in B to E; A on the earlier model).
- **L3, typed verdicts held on the new seats, n = 3: holds.** B, C and D have no rejection and no provider failure (and E and A
  none either).
- **L4, nothing blind on a pinned model: falsified at A and B, holds at C, D and E.** The guard is blind to the global answer
  model (A) and to `qwen4-max` (B) because their catalogue prices carry what the guard could not bound. A is not a pin; B is.
  Both stopped the sweep as written and are the reason for the separate change below.
- **L5, cost: holds.** Every run is under its cap and the five together under '$0.99' ('$0.1183', against a prior of about
  '$0.30'). The answer tier's cost is the catalogue's no-cache figure to the cent in B, C, D and E (ratio 1.00), and half of it in
  A (cached prompt tokens).
- **L6, the arithmetic: D holds (276 and 92 present), E holds (48,000 present), C missed, and the miss is the instrument, not the
  model.** `figures_present` reads the run's **researched text** (the grounding), not the answer; run C's answer states the
  closing balance as £238,203.20 and the interest as £38,203.20, which the recompute tier's three samples agreed on, and neither
  is in its grounding. My scenario for C used the check wrongly; it is not re-run.
- **L7, nothing else moved, one pair: not a clean pair.** A and B differ in the answer model **and** the triage model (Amendment 2).

## Found, not touched here

- The guard was blind to two of the five answer seats. The change that bounds any catalogue price at its highest rate is a
  separate branch and pre-registered tests; this record does not claim it.
- `figures_present` reads grounding, not the answer (above); a scenario that asks for a computed figure should be checked on the
  answer, or on the recompute tier's results. Not changed.
- The recompute and decision models stay blind to the guard in every run (their prices carry a prompt-size override and are
  unlisted, respectively); the first of the two is covered by the change above, the second is not in the catalogue.

## Traces (sha256)

| File in `docs/traces/` | sha256 |
|---|---|
| `lineup-smoke-A.jsonl` | `3ba6e7f030fa89777c3a59f78a7d2ae954f38754644a7358902aea533e134ca8` |
| `lineup-smoke-B.jsonl` | `a6cbd6a955f188bcf08b939f1e1672c35beea2259ecd1f297bb025753e03c265` |
| `lineup-smoke-C.jsonl` | `6df62bcbe81cbc4c7df877182beea88d60c2238f8d64352d16c64455a2bf47cd` |
| `lineup-smoke-D.jsonl` | `81ebcff39929982f7b7afc31addc0713ab1fde626ed4fab6da4a13c35220ff01` |
| `lineup-smoke-E.jsonl` | `5342420dd95ca04cd9bbaabea667631340f89bd4d52daa73666b2918fba88cb0` |
