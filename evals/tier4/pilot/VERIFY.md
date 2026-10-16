# Tier-4 pilot batch: verification

Advisor, 2026-10-16. Design: `docs/reviews/2026-10-16-tier4-the-capacity-test.md` (proposed D52).
**Status:** verified; awaiting the owner's freeze (D44). After the freeze, `candidates.json` and `corpus/` stay byte-identical; a change is a new version.

## Provenance

| item | value |
|---|---|
| Generator | `google/gemini-4-argon`, the owner's choice. It is not an arm's pin. |
| Call 1 | Appendix A as first written; `max_tokens` 60000; $0.60. It thought aloud in its output, restarted twice and ended at the token limit. Its last attempt held T4-01 to T4-05 complete (all F1). Raw output: `raw/20261016T210026Z-tier4-pilot-batch.raw.json`, sha256 `316ad6da0a79fca2…`. |
| Call 2 | Appendix A with rules 9 and 10, F2 only, reasoning effort high; `max_tokens` 50000; $0.50. Reasoning used 41,983 tokens, so only T4-06 was written, cut inside its last field. Raw output: `raw/20261016T211321Z-tier4-pilot-batch-f2.raw.json`, sha256 `63d860585a110e75…`. |
| Total spend | $1.10 |

## Verdicts

From `python3 -I evals/tier4/pilot/verify.py`: an independent recomputation of every requirement from the request's formulas (F2: from the corpus pages), and a search of each whole design space.

| id | family, domain | verdict | design space | feasible designs | note |
|---|---|---|---|---|---|
| T4-01 | F1, mechanical (hoist) | **dropped** | 6,100 | **0** | The speed relation gives 4.20 m/s for the stated reference against the 0.42 m/s target, an order-of-magnitude error. No design passes. |
| T4-02 | F1, electrical (buck converter) | verified | 240 | 2 | Q2/L2/250 kHz with 3 or 4 capacitors. Both wrong designs fail as claimed; one's stated ripple and inductor loss are a few % off, its failure unchanged. |
| T4-03 | F1, fluid (glycol loop) | verified, repaired | 12 | 1 | P2 with D = 0.075 m; NPSH margin 0.45%. |
| T4-04 | F1, thermal (plate-fin heat sink) | verified | 15 | 1 | F2 fan, 34 fins. |
| T4-05 | F1, structural (jib boom) | verified | 15 | 1 | S4 with grade G2. |
| T4-06 | F2, fluid (coolant skid; fictional "Vortexia Fluidics" corpus, 3 pages) | verified, repaired | 192 | 1 | VT-50 / FC-300 / VX-200 at 55 Hz. Margins: head 2.9%, NPSH 6.4%, power 5.7%. Its `check` strings pin the reference choices, so grading uses the corpus physics in `verify.py` instead. Both wrong designs fail physically: the 60 Hz design fails cavitation and power; the other used the clean filter drop instead of the fouled one. |

## Repairs (`repairs.json`)

1. **T4-03 request:** a carriage return plus "ho" restored to `\rho`. The generator wrote the LaTeX unescaped in JSON.
2. **T4-06 request:** "must not exceed a 10.0 K temperature rise" became "is sized for exactly a 10.0 K temperature rise". The requirement sizes the flow at exactly 10.0 K with properties at the 40.0 °C mean. The old wording admitted higher flows whose mean temperature falls between table rows, and the corpus gives no rule for interpolating between them.
3. **T4-06 difficulty_rationale:** marked "not provided", because the call ended inside it. It is metadata and never shown to an arm.

## Checked by reading, not by search

- The F2 names (Vortexia Fluidics, KryoSol-45, VortaTube, FiltraCore, VX-Pump) read as invented. No web search was run, and no real product's data matches the corpus tables.
- Some requests run up to 399 words against the prompt's 350. This is accepted, since nothing is missing or ambiguous.

## For the pilot (§5 of the design)

Calibration runs:
- the cheapest and the strongest single calls on T4-02 to T4-05;
- the strongest single call, with the three corpus pages in its prompt, on T4-06.

The pilot run takes up to 4 of the questions a single call fails.
