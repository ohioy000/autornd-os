# Tier-4 batch 3: verification

Advisor, 2026-10-18. **Status: FROZEN on 2026-10-18** by the advisor, on the owner's instruction "B then C, full permission" (D44). The sha256s are in `manifest.json`.

## What changed from batch 2

Generator v3 (`generator-v3.txt`):
- F2 only, with the maker's rules in the corpus;
- the selection rule must pick a different option when the trap is missed, and that option must fail by at least 3%;
- every candidate carries an `option_table`: every catalogue option against every requirement, computed twice, once correctly and once with the trap missed.

One call cost $0.33 and finished on `stop`. Raw output: `raw/20261018T032426Z-F2.raw.json`. All four candidates verified, against one of six in batch 2.

## Verdicts

From `python3 -I evals/tier4/batch3/verify.py`: every option, under the corpus rules, both correctly and with each trap missed.

| id | domain | correct | trap missed selects | how the trap option fails |
|---|---|---|---|---|
| T4-21 | gearhead (Kovel KGD) | KGD-90-10 | KGD-90-08 (RMS torque over the full cycle; the maker excludes dwell at 25% or less) | RMS 72.45 > 67.90 N·m derated thermal limit (6.7%) |
| T4-22 | control valve (Vexor VFC) | VFC-9100-M | VFC-9080-S (F_L used for incipient cavitation instead of F_kc), or VFC-9080-M (stage-interaction K_m missed) | dP_ic 726 < 850 kPa (14.6%); or travel 89.5% > 85% (5.2%) |
| T4-23 | cold plate (Thermovance TVC) | TVC-250-AL | TVC-200-AL (glycol and footprint factors missed, or the inlet temperature used for module 2) | baseplate 97.24 °C > 95.0 °C |
| T4-24 | DC-link capacitor bank (Astradyne EPC) | 5 × EPC-1200-60, $650 | 4 × EPC-1200-60 (altitude thermal multiplier missed), or 4 × EPC-1100-80 (altitude voltage derating missed) | hot spot 110.69 °C > 105 °C; or 951.5 V < 1035 V |

Margins: every requirement is a corpus formula, with no alternative standard method that could flip a verdict. The tightest reference margin is T4-24's voltage, 1035 V against 1038 V; it is exact arithmetic on stated figures.

## Repairs and flags (`repairs.json`)

1. **T4-21 reference values** recomputed (L10h 23,710 h, not 18,574 h). The selection is unchanged.
2. **T4-22 flag.** The corpus states two travel laws. The correct selection and the F_L trap hold under both readings; the missed-K_m trap flips the answer only under the "mandatory" reading. Travel is graded under either reading. The corpus is left as generated.

## For the calibration

D-pages runs once on each of the four questions, under the $2.00 ceiling. A question goes to the pilot when D-pages fails it, read by hand.
