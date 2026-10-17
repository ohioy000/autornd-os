# Tier-4 batch 2: verification

Advisor, 2026-10-17. Design: `docs/reviews/2026-10-16-tier4-the-capacity-test.md` (Ruling D52).
**Status: FROZEN on 2026-10-17** by the owner's instruction to merge PR #188 ("u merge") (D44).
- `candidates.json`: sha256 `d49afe00c5980691204a5327c88fec1c77243ae1e615fc2a095822a8599eab67`.
- Corpus pages: sha256s per question in `manifest.json`.

The batch stays byte-identical from here on; a change is a new version.

## Why a second batch

The pilot batch (`evals/tier4/pilot/`) stated every formula in its requests. On the void calibration, the strong single call reached the unique correct design wherever it finished reasoning: three of five questions, with the other two on track. Batch 2 uses `generator-v2.txt` instead:
- the requests give data but never the method;
- each candidate names a **trap**, a modelling decision that changes the selected design if missed;
- the verdict must hold under every standard method;
- margins are at least 3%.

## Provenance

| item | value |
|---|---|
| Generator | `google/gemini-4-argon`, the owner's choice, reasoning effort low, `max_tokens` 65536 |
| F1 call | 4 candidates (T4-11 to T4-14), finished on `stop`, $0.134. Raw output: `raw/20261017T025826Z-F1.raw.json` |
| F2 call | 2 candidates (T4-15, T4-16), finished on `stop`, $0.163. Raw output: `raw/20261017T030105Z-F2.raw.json` |
| Total | $0.30 |

## Verdicts

From `python3 -I evals/tier4/batch2/verify.py` for the kept questions; the dropped ones were recomputed by the advisor from their own stated methods.

| id | domain | verdict | finding |
|---|---|---|---|
| T4-11 | bolted flange coupling | **dropped, broken** | Under its own methods every coupling passes: slip safety factors 1.41–2.65 against 1.25, overload shear safety factors 5.5–10.3. The lightest, C1, is correct and the reference C2 is wrong. Its friction torque (1,832 N·m for C2) contradicts its own formula (3,292 N·m). |
| T4-12 | pump suction line | **dropped, not hard** | Valid, but the stated 2.2 m/s velocity limit alone picks DN100 (DN65 is 4.05 m/s, DN80 is 2.62 m/s). The trap only moves one reported NPSH value by about 2%, and the request names the trap. |
| T4-13 | pin-fin heat sink | **dropped, broken** | Every option runs at 52–66 °C against the 95 °C limit. The lightest, HS1, is correct and the reference HS3 is wrong. The request also states the correlation. |
| T4-14 | beam-column | **dropped, broken** | Every section has an interaction ratio of 0.26–0.51 against 1.00. The lightest, W1, is correct and the reference W3 is wrong. The request also states the code formulas. |
| T4-15 | cold-formed channel strut (fictional Voss-Metra corpus) | **kept, meets every rule** | Correct: VM-C180. VM-C160 fails once torsional-flexural buckling is included (lambda 1.336 > 1.30; N_b,Rd 107.1 < 115 kN), yet passes if that mode is missed (the trap: lambda 1.156, 131.3 kN). Margins 2.8% on slenderness and 6.9% on strength. Reference values repaired (see below). |
| T4-16 | centrifugal pump with impeller trim (fictional Kaelen-Vortec corpus) | **kept, flagged** | Correct: KV-100-250 trimmed to 228 mm, under Colebrook, Swamee-Jain and Haaland alike. KV-80-250 fails the POR (by 1%), the trim-corrected NPSH rule (2.364 m available against 2.454 m needed) and the derated motor (17.54 > 16.28 kW). **Flag:** missing those rules does not change the selection, because the rule picks the lowest shaft power and KV-100-250's (16.18 kW) is below KV-80-250's anyway. Kept as a multi-rule calculation; the calibration decides whether it has headroom. Reference values repaired. |

## Repairs (`repairs.json`)

1. **T4-15 reference_design** recomputed. The generator's values contradicted its own corpus: r_y 31.1 mm against sqrt(I_y/A) = 38.7 mm, and N_cr,y 240.3 kN against 373.1 kN. The selection is unchanged.
2. **T4-16 reference_design** recomputed. The generator's trim (225 mm against 228 mm), system head, NPSH and trap-text figures contradicted its own corpus table. The selection is unchanged.

Requests and corpus pages are unchanged from the generator's output.

## Lessons for the next batch

- In "no formulas" mode the generator could not make the constraints bind: three of four F1 candidates were infeasible as hard questions, with every option passing.
- The F2 form held up better, because the maker's rules give each question its structure.
- The next F1 attempt should put maker-style rules in the request, or be generated as F2 with the corpus inlined.

## For the calibration

D-pages, the strongest single call with the question's corpus pages, runs once on T4-15 and once on T4-16, under the $1.00 ceiling in `manifest.json`. A question is kept for the pilot if that call fails it, read by hand.
