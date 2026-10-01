# The golden set: where it came from, and how it was checked

The golden set is the one scoreboard Ruling D41 names: six questions that show
whether the harness gives a correct answer quickly, plus one side test. This
file records where each question and key came from and how the advisor checked
them before any run. **The keys and the scorer are written by the advisor. The
executor uses them and reports defects; it never edits them.**

## Sources

- **Q1 to Q5** were generated on 2026-10-01 by an external model that had no
  knowledge of AutoRnD. The owner gave it a prompt written by the advisor,
  which asked for one SANITY, LOOKUP, DERIVATION, SPECIFICATION and PROCEDURE
  question. The prompt required each question to be phrased the way an
  engineer would ask a colleague: no instructions about how to verify or what
  to cite, no traps, and every number in the question except for the lookup.
  The generator's question text is kept verbatim in
  `generator-output-20261001.json`. `keys.json` carries it converted from LaTeX
  to plain text, and a script confirmed that every number in each question is
  unchanged by that conversion.
- **Q6** is the owner's logic-circuit question, sent verbatim. Its key is the
  owner's own answer: positive logic; the forward and aft door signals into an
  OR gate; the OR output and brake-engaged into an AND gate; the AND output
  lights the indicator.
- **IA (side test, not scored as golden)** is the owner's
  inspection-authorization question, sent verbatim with its typos, because a
  real user types that way.

## What the advisor checked

- **Arithmetic keys (Q1, Q3, Q4, Q5):** every figure re-derived from scratch,
  and every one matched: 8.00 V and 2.00 mA; J = 6.135923e-7 m^4, tau_max =
  20.371833 MPa, theta = 0.0101859164 rad; 3.00 mm selected, 60.0 mm^2,
  100 MPa (equality permitted), 150 MPa at 2.00 mm, 3.000e-5 m^3, 0.2355 kg;
  a drop of 0.10 bar against 0.20 bar, which passes. The generator's listed
  wrong answers were re-derived too: pi*d^4/64 gives half of J, and using the
  diameter instead of the radius gives 40.7 MPa.
- **Q2 (lookup):** checked against the text of 29 CFR 1910.146(b): "less than
  19.5 percent oxygen by volume" and "more than 23.5 percent oxygen by volume".
- **IA (lookup):** checked against 14 CFR 65.91, 65.92, 65.95 (LII) and 65.93
  (govinfo, 2024 edition XML, read directly). Paragraph 65.93(a)(2) reads
  "Performed at least two major repairs or major alterations for each 90
  days". The advisor's memory said "inspections of", and the source corrected
  it before the key was written.

## How answers are scored

`score.py` normalises the answer text (case, dashes, the multiplication sign,
superscript exponents, markdown, digit separators, whitespace) and checks every
item: each `all` pattern must match and no `none` pattern may. A question
**passes** when the run shipped (status completed), every item holds (and, for
Q5, the ordered steps appear in order), and it finished within its
`time_target_s`.

**The self-test**, which must stay green before any score is trusted: every
model answer holds every item; every listed wrong answer fails the item it was
written to break; and every alternative phrasing in `variants_must_pass` holds.
These are the "prove by breaking" cases, and they come from the generator's own
list of common mistakes.

## Why not `figures_present`

`figures_present` (`autornd/evals/assertions.py`) searches the run's grounding
and string outputs, not the answer, because the answer is a verdict object.
It cannot score an answer. Applied to 094's cup-line scenario, it could never
fail on `LV-N11N` or `214`, which are in the cupline documents, and could
never pass on `23.995` or `0.00483`, which are derived and appear in no
document. The advisor's 094 command asked for it, which was an error. 094
timed out before it ran, so it never produced a misleading result, and
ARCH-20261001-102 removes it from that scenario.
