# Tier-4 batch 6: verification

Advisor, 2026-10-18. **Status: FROZEN on 2026-10-18**, on the owner's instruction "2 first, full permission" (D44).

**Why this batch:** batch 5 found one headroom question in three with traps the corpus does not state. This larger batch estimates that rate and widens the vote's measured sample.

**The generation:**
- Generator: `x-ai/grok-4.7`.
- Prompt: generator v4.1, run as two calls (`generator-v4.1-A.txt`, `generator-v4.1-B.txt`). They differ only in ids and domains.
- **What v4.1 adds to v4,** from batch 5's defects:
  - **rule 4:** where codes differ, the verdict must hold under all of them, and a section or class that picks a code curve is given as data;
  - **rule 11:** the Results rows name neutral quantities;
  - **rule 12:** do not reuse an earlier batch's traps.
- Cost: $0.27 and $0.26, effort low, both finished on `stop` (`raw/`).

**Verdicts** (`python3 -I evals/tier4/batch6/verify.py`, recomputed from the request and the corpus pages, not from the generator's tables):

| id | trap source | correct | trap missed selects | how the trap option fails |
|---|---|---|---|---|
| T4-51 pipe insulation (Calder Kestrel) | reference condition (k at the layer mean temperature) | KJ-55 | KJ-40 | 93.9 > 80 W/m |
| T4-52 indexing servo (Helion Arc) | implied load case (table inertia reflected as J/N²) | A60 | A40 | peak 2.67 > 2.40 N·m |
| T4-53 feeder cable (Harton Vanta) | governing mode (adiabatic fault heating) | V95 | V50 | 573 > 250 °C at the end of the fault |
| T4-54 pump (Bramley Lark) | notation (gauge suction pressure) | **dropped** | — | see below |
| T4-55 belt-driven motor (Northline Kestrel) | implied load case (torque through the belt ratio) | K-55 | K-20 | 22 < 46.9 N·m |
| T4-56 pinned tie (Calder Plainflat) | governing mode (net section at the hole) | PF-80x10 | PF-60x10 | 214 > 155 MPa |
| T4-57 solvent pump (Meridian Helion) | reference condition (properties at 80 °C) | H-280 | H-210 | NPSHa 8.30 < 11.50 m |
| T4-58 series reactor (Lumenford Bay) | notation (x on a 100 kVA base, not the unit's own) | B-320 | B-160 | 3.60 > 3.0% drop |

In each kept question:
- the reference passes every requirement by at least 3%;
- a lighter or cheaper option fails under the correct method;
- the trap's selection fails under the correct method by more than 3%.

T4-53 and T4-58 were also checked by a second standard method, with the same verdicts (`repairs.json`, flags).

**Repair:** T4-55's request said the motor must deliver "the torque and speed the drive imposes on the motor shaft", which names the step the trap tests (rule 8). It now says "drive the mixer at this duty".

**Dropped: T4-54.** With the gauge reading taken as absolute, no pump passes, so missing the trap leaves nothing feasible rather than a different selection (rule 2).

**Flags:**
- **Probably easy:**
  - T4-52's "trap missed" column leaves out the table inertia;
  - T4-55, T4-56 and T4-57 have basic traps.

  They are kept so the headroom rate is estimated over the whole batch.
- **T4-52's hidden requirement text** writes the acceleration formula wrongly but uses the right value (39.27 rad/s²).

**Calibration:** D-pages on the seven kept questions, ceiling $2.80 (7 × the $0.40 per-unit ceiling).
