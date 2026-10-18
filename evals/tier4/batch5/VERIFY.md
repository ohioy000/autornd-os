# Tier-4 batch 5: verification

Advisor, 2026-10-18. **Status: FROZEN on 2026-10-18**, on the owner's instruction "1 first, full permission" (D44).

**Why this batch:** batch 4 showed that flash's strength survives a non-Gemini generator, but every batch-4 trap was a rule the corpus states. This batch tests the open case: a trap the corpus does not state, taken from the answerer's own engineering knowledge.

**The generation:**
- Generator: `x-ai/grok-4.7` again, so it is not of the Gemini family.
- Prompt: generator v4 (`generator-v4.txt`). Rules 8 to 10 are new:
  - the trap must come from the answerer's own knowledge, never from the corpus or the request;
  - it must be drawn from four named sources;
  - it must be fair.
- The `trap` field now carries `source`, `why_missed` and `not_stated`.
- Ids: T4-41 to T4-44.
- Cost: one call, $0.17, effort low, finished on `stop` (`raw/20261018T172910Z-F2.raw.json`).
- A first call was refused with a 402 before any spend: the API key's own limit could not cover `max_tokens` 65536. The rerun used 52000.

**Verdicts** (`python3 -I evals/tier4/batch5/verify.py`, recomputed from the request and the corpus page, not from the generator's table):

| id | trap source | correct | trap missed selects | how the trap option fails |
|---|---|---|---|---|
| T4-41 hoist reducer (Helion WR) | implied load case | WR-260 | WR-220 (rope force m·g, acceleration missed) | torque 1620 < 1729.6 N·m (ratio 0.937) |
| T4-42 inverter (Nordline VL) | notation | VL-42 | VL-25 (RMS current compared with an amplitude rating) | 33 A < 40.5 A crest (ratio 0.815) |
| T4-43 solvent pump (Calder CP) | reference condition | CP-40 | CP-20 (420 kPa converted to head with the water test density) | head 46 < 56.33 m (ratio 0.817) |
| T4-44 post (Pylon PS) | governing mode | **dropped** | — | see below |

In each kept question:
- the reference passes every requirement by at least 3%;
- a lighter or cheaper option fails under the correct method;
- the trap's selection fails under the correct method by more than 3%.

T4-43's cheaper CP-50 fails on NPSH (6.4 > 5.5 m), so the trap is not the only discriminator.

**The trap is unstated** (screened by keyword and read):
- **T4-41:** no word about acceleration, inertia or dynamic load. The request gives the speed-up time as data.
- **T4-42:** the corpus defines I_n as "the amplitude of the permissible sinusoidal output current", which is its notation, and never mentions RMS or a conversion.
- **T4-43:** the corpus prints the water test density beside the head column. That density is the lure, given plainly as data (rule 10).

**Repair:** T4-42's Results rows named "motor RMS current" and "motor crest current", which gives the trap away (rule 8). The rows are now "motor line current", "current compared with I_n" and "I_n". The values and the selection are unchanged (`repairs.json`).

**Dropped: T4-44.**
- **A hint:** its Results rows include "buckling factor of safety".
- **The verdict depends on the method (rule 4).** PS-3, at L/r 135, has a buckling factor of safety of:
  - 3.02 on the Euler load, and 2.65 under AISC E3, both passing 2.5;
  - 2.32 under EC3 curve b, and 2.13 under curve c, both failing.

  The catalogue gives no section type to fix the curve. Repairing it would mean changing catalogue data, which no earlier batch has done.

**Flag:** T4-41's power row reads two ways: 2162 W at the end of the acceleration, or 1962 W steady. Every option passes either way, and the row is not a key row in the vote probe.

**Calibration:** D-pages on T4-41 to T4-43, ceiling $1.20 (3 × the $0.40 per-unit ceiling). It waited on the API key's limit, then ran on 2026-10-18 after the owner raised it. Kimi-k3 failed T4-42 and passed T4-41 and T4-43. See `docs/reviews/2026-10-18-tier4-batch5-unstated-traps.md`.
