# Tier-4 batch 4: verification

Advisor, 2026-10-18. **Status: FROZEN on 2026-10-18**, on the owner's instruction "1 then 2, full permission" (D44).

**Why this batch:** the generator is `x-ai/grok-4.7`, not of the Gemini family, so it tests whether the cheap single call's strength on batches 2 and 3 was a family affinity with their Gemini generator. It used generator v3 unchanged, ids T4-31 to T4-34. One call: $0.16, finished on `stop`.

**Verdicts** (`python3 -I evals/tier4/batch4/verify.py`):

| id | correct | trap missed selects | how the trap option fails |
|---|---|---|---|
| T4-31 coupling (Nordling ND-Flex) | ND-C50 | ND-C35 (continuous torque as the basis) | T_allow 57.4 < T_req 82.5 N·m |
| T4-32 contactor (Helion HC) | HC-50 | HC-40 (enclosure factor missed) | 28.9 < 32 A |
| T4-33 viscous pump (Pellam PP) | PP-2 | PP-1 (water ratings used) | Q_del 0.00533 < 0.006 m³/s |
| T4-34 heatsink (Varmex VX) | VX-320 | VX-250 (horizontal factor missed) | R_sa 0.675 > 0.56 K/W |

**Flag:** every trap is a rule the corpus states explicitly. These are rule-application questions, shorter and easier than batch 3. There are no repairs.
