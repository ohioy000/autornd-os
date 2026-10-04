# Tier-2 candidate set — verification review checklist

Command: **ARCH-20261002-117** (tier 2 of the owner's
three-tier instruction of 2026-10-02): "Register and
independently verify the 25-question set."

**Status: the complete 25-question set is registered,
verified and FROZEN at `frozen-2026-10-03`.** The
owner supplied all 25 questions on 2026-10-03 (the
array the command names, registered verbatim — the
executor generated, screened and selected nothing),
and ratified the tier-2 signoff the same day
("ratify the tier-2 signoff"), covering the
independent verification (all 268 checks) and the
source review (the four archived July 1, 2014
govinfo editions with verbatim quotation matches and
2026-10-01 eCFR stability cross-checks). The freeze
the command orders after review is executed: the
manifest records the signoff (grantor, time, scope,
effect) and carries no freeze blocker. Paid use of
the set is permitted subject to the tier-3 command's
own ratification requirements (ARCH-20261002-118).

## What was delivered

| deliverable | where |
|---|---|
| Candidate export (verbatim, owner-supplied) | `candidate/25GoldenQuestion.json` |
| Model-visible requests (1) | `questions.json` |
| Scorer-only keys, worked answers, wrong-answer examples (3) | `keys.json` |
| Reference source documents (2) | `sources/` |
| Extraction script (1→3 separation) | `extract_candidate.py` |
| Independent verifier (recomputation) | `verify_keys.py` |
| Provider-free scorer (answer scoring) | `scorer.py` |
| Version record (D44-style guard) | `versions.json` |
| Manifest (versions, counts, archives, freeze record) | `manifest.json` |
| This checklist | `REVIEW.md` |

Dataset version / scorer version: the dataset
is `frozen-2026-10-03` (questions.json and
keys.json hash unchanged since the freeze — the
set froze at that entry on the owner's 2026-10-03
signoff, and its content is identical to
`candidate-2026-10-03.3`); the scorer is
`frozen-2026-10-03.2` — the second scorer
repair under the freeze, ordered by the
advisor's PR #152 review of 2026-10-04: the
dataset content did not change, only the
instrument did (see `versions.json` and the
repair records below; every change to the four
versioned files is a new entry naming the
change and its trigger).

## The checks, and their results

All 268 checks of `evals/tier2/verify_keys.py` hold (exit
0); all 263 scorer self-test fixtures hold (exit 0). The
suite guard `tests/test_tier2_keys.py` (17 tests) runs
both instruments on the tree and proves each can fail on
corrupted copies (convention 22);
`tests/test_tier2_regression.py` re-scores the twelve
recorded answers and runs the notation-variant sweep
(Ruling D50 (1); see the repair record below).

The 268 checks are: 6 global checks (G1–G6), 195
per-question checks (Q1.1 … Q25.7), and 67 cross-checks
(X1–X67) that parse `keys.json`'s own value strings and
require agreement with the first-principles recomputation
within the stated tolerances — so `keys.json` is the
single source of key values.

| check | what it verifies | result |
|---|---|---|
| G1 | candidate export hashes to the manifest record | PASS |
| G2 | questions.json, keys.json, manifest agree on count and identities | PASS (25, Q1–Q25) |
| G3 | the command's expected count is met; the set is not frozen | PASS (25 of 25; blocker = pending signoff) |
| G4 | the model-visible file carries no scorer material | PASS (exactly id, shape, domain, question) |
| G5 | the scorer-only file carries no model-visible request | PASS |
| G6 | every question carries required items with tolerances and derivations, wrong answers with reasons | PASS |
| Q1.1–Q1.5 | voltage-divider output and series current recomputed; dimensions; "4 V" and "6 mA" wrong answers falsified | PASS (8.00 V ±0.01; 2.00 mA ±0.01) |
| Q2.1–Q2.12 | archived 2014 PDF/extraction/cross-check XML hash to the record; both 29 CFR 1910.146(b) oxygen definitions matched **verbatim** against the archived July 1, 2014 edition (left-column reconstruction of the two-column typesetting); paragraph-(b) placement; strict operators; volume basis; eCFR stability cross-check; "at or below 19.5%", "at or above 23.5%", "by mass", "mg/m³" wrong answers falsified | PASS |
| Q3.1–Q3.7 | polar second moment J = πd⁴/32, shear stress τ = Tr/J, twist θ = TL/(GJ) recomputed; dimensions; "πd⁴/64", "40.7 MPa", "0.0102 degrees" wrong answers falsified | PASS (6.13592×10⁻⁷ m⁴, 20.3718 MPa, 0.0101859 rad, each ±0.2% rel) |
| Q4.1–Q4.9 | discrete selection (smallest passing thickness from the available strip set), gross area, stress with equality permitted, next-thinner failure, volume, mass; "select 4 mm", "select 2 mm", "235.5 kg" wrong answers falsified | PASS (3.00 mm; 60.0 mm²; 100 MPa at the permitted equality; 2.00 mm fails at 150 MPa; 3.00×10⁻⁵ m³; 0.2355 kg) |
| Q5.1–Q5.11 | logged pressure drop recomputed; verdict follows from the conjunctive criteria; inclusive boundary operator (0.20 bar passes, 0.21 fails); test pressure is 6.00 bar not the 10.0 bar rating; operation order (nine precedences); no-addition rule; five wrong answers falsified | PASS (0.10 bar ±0.001; PASS) |
| Q6.1–Q6.5 | alarm function identified as the exactly-one-pump function (XOR) from the requirement; ordered outputs 0,1,1,0 recomputed for 00,01,10,11; "OR" and "XNOR" wrong answers falsified against the requirement's table | PASS |
| Q7.1–Q7.10 | archived 29 CFR 1910.95 PDF/extraction/cross-check XML hash to the record; Table G-16's caption and column headers located in the archive; the 90/95/100 dBA durations recomputed from the archived table rows (8, 4, 2 h, slow response); rows sit inside Table G-16's own span; eCFR cross-check carries the same rows; "90 dBA permits 2.5 h" and "95 dBA permits 8 h" wrong answers falsified | PASS (8 h, 4 h, 2 h) |
| Q8.1–Q8.7 | layer thermal resistances R = L/(kA), series heat rate Q̇ = ΔT/ΣR, interface temperature from both sides (agreement); dimensions; "200 W" and "40 °C interface" wrong answers falsified | PASS (0.250 K/W, 0.0500 K/W, 133.333 W hot to cold, 26.6667 °C) |
| Q9.1–Q9.7 | minimum passing stiffness k = F/x_max and the discrete selection (10.0 N/mm, equality allowed); extension at the limit passes; next-lower stiffness (8.00 N/mm → 15.0 mm) fails; stored elastic energy U = Fx/2; dimensions; "select 12 N/mm" and "1.44 J" wrong answers falsified | PASS (10.0 N/mm exact; 12.0 mm at the limit; 0.720 J) |
| Q10.1–Q10.6 | setpoint→coupon-band→timer-start order; hold criterion (inclusive 118–122 °C, no restart); logged verdict (119–121 °C inside the band → PASS); cool-to-≤40 °C-then-remove order; "start the timer before the coupon reaches the band" and "restart the timer" wrong answers falsified | PASS (120 °C setpoint, 600 s hold) |
| Q11.1–Q11.6 | output speed n_o = n_i·d_i/d_o recomputed; direction from the open-belt rule (same sense as driver); lossless torque T_o = T_i·n_i/n_o; power conservation; "2700 rpm" and "clockwise output" wrong answers falsified | PASS (300 rpm counterclockwise, 9.00 N m) |
| Q12.1–Q12.11 | archived 40 CFR 141.62 PDF/extraction/cross-check XML hash to the record; the (b)(16), (b)(1) and (b)(7) rows matched against the archive (arsenic 0.010 mg/L, fluoride 4.0 mg/L, nitrate 10 mg/L as nitrogen); eCFR cross-check; the nitrate reporting basis ("as nitrogen") stated; "2 mg/L fluoride", "10 mg/L as chloride", "0.050 mg/L arsenic" wrong answers falsified | PASS |
| Q13.1–Q13.6 | RC time constant, capacitor voltage and resistor current at t = 2τ recomputed (V_C = V₀e⁻², I = (V₀/R)e⁻²); dimensions; "1.353 V" and "1 mA" wrong answers falsified | PASS (τ = 1.00 s; 8.64665 V; +0.135335 mA) |
| Q14.1–Q14.8 | required heat Q = mc_pΔT recomputed; minimum passing power and the discrete selection (1000 W, equality allowed); heating time at the selected power (120 s passes at the limit); next-smaller heater (750 W → 160 s) fails; energy delivered; dimensions; "select 1250 W" and "280 kJ required" wrong answers falsified | PASS (120000 J; 1000 W exact; 120 kJ delivered) |
| Q15.1–Q15.8 | ordered check sequence (zero → 1.000 mm → 2.000 mm → return to zero, without re-zeroing between readings); acceptance criteria (≤0.020 mm and ≤0.010 mm, inclusive); three signed errors recomputed (reading − reference: +0.010, −0.030, +0.005 mm); overall verdict (second reading exceeds 0.020 mm → FAIL); "PASS because the final zero is within limits" and "re-zero before the second reading" wrong answers falsified | PASS (overall FAIL on the second reading) |
| Q16.1–Q16.5 | thermal expansion ΔL = αLΔT and final length recomputed; dimensions; "0.672 mm increase" and "compressive thermal strain" wrong answers falsified | PASS (+0.480 mm; 0.800480 m) |
| Q17.1–Q17.8 | archived 29 CFR 1910.147 PDF/extraction/cross-check XML hash to the record; the attachment-means provision ((c)(5)(ii)(C)(2): no less than 50 pounds) and the inspection provision ((c)(6)(i): at least annually) matched against the archive; eCFR cross-check; "50 kg" and "every two years" wrong answers falsified | PASS (≥50 lb; at least annually) |
| Q18.1–Q18.7 | maximum bending moment M = PL/4, second moment I = bh³/12, bending stress σ = Mc/I, midspan deflection δ = PL³/(48EI) recomputed; dimensions; "I = hb³/12" and "use the cantilever formula" wrong answers falsified | PASS (500 N m; 7.20×10⁻⁷ m⁴; 20.8333 MPa; 1.15741 mm downward) |
| Q19.1–Q19.9 | selected resistance and current recomputed (330 Ω → 20.0 mA, exact); the selection is exact (exactly one available resistor meets the band); 270 Ω (24.4444 mA, fails high) and 390 Ω (16.9231 mA, fails low) rejections recomputed; dissipation P = VI; minimum required rating (≥0.264 W → select 0.500 W); dimensions; "select a 0.250 W resistor" and "use 9.00/R" wrong answers falsified | PASS |
| Q20.1–Q20.8 | start and stabilization order; collection sequence (divert to container, start timer, collect 60.0 s, divert back, stop timer); end sequence (read, stop the pump); reference flow recomputed from the logged collection (11.76 L / 60.0 s = 11.76 L/min); signed indication error recomputed (+2.04082%); logged verdict (|e| ≤ 3.0% → PASS); "-2.0% error" and "stop the pump before diverting" wrong answers falsified | PASS (Q_ref = 11.76 L/min; e = +2.04082%; PASS) |
| Q21.1–Q21.4 | final mixed temperature recomputed (mass-weighted average, 35.0 °C = 308.15 K); dimensions; "50 deg C" and "65 deg C" wrong answers falsified | PASS (35.0 °C) |
| Q22.1–Q22.10 | archived 29 CFR 1910.95 PDF/extraction/cross-check XML hash to the record; the baseline deadline (within 6 months of first exposure at or above the action level), the pre-baseline noise-free period (at least 14 hours without workplace noise), and the retest window (within 30 days) matched against the archived paragraph (g); eCFR cross-check; the mobile-test-van exclusion applied; "baseline within one year", "retest within 21 days" wrong answers falsified | PASS |
| Q23.1–Q23.7 | common strain and extension recomputed; aluminum and steel stresses recomputed (σ = Eε); the force carried by each bar recomputed; dimensions; "each bar carries half the load" and "both bars have the same stress" wrong answers falsified | PASS (δ = 0.882353 mm; 61.7647 MPa; 176.471 MPa; 12.3529 kN; 17.6471 kN) |
| Q24.1–Q24.10 | minimum driven diameter and the discrete selection (D ≥ 2d_i → 240 mm, ratio 3:1 exact); diameter ratio; output speed n_o = n_i·d_i/D_o (500 rpm); open-belt direction (same sense as driver); lossless output torque (12.0 N m); belt linear speed (6.28319 m/s); dimensions; "select 200 mm", "output rotates oppositely", "1.33 N m output torque" wrong answers falsified | PASS |
| Q25.1–Q25.7 | initialization order (0 V → enable → confirm LOW); rising sweep (monotonic increase, record LOW-to-HIGH, continue to 5.00 V, confirm HIGH); falling sweep and shutdown order (monotonic decrease, record HIGH-to-LOW, return to zero, then disable); all four acceptance criteria (2.90–3.10 V and 1.90–2.10 V inclusive, correct endpoint states, one transition per sweep); hysteresis width recomputed (3.04 − 1.96 = 1.08 V); logged verdict (both transitions inside the bands → PASS); "-1.08 V hysteresis width" wrong answer falsified | PASS (width 1.08 V; logged 3.04/1.96 V → PASS) |
| X1–X67 | keys.json's own value strings parsed and required to agree with the first-principles recomputation within the stated tolerances | PASS (single source of key values) |

Scorer self-test (263 fixtures): all 25 model answers
hold every item; 47 equivalent notations the keys list
hold (number words, μg/L, μA, ms, mJ, N mm, kN/m, rev/s,
K, mV, mm⁴, μm, newton-metres, mg N/L, …); 100 tolerance
boundaries hold just inside and fail just past (including
equality-permitted limits and exact selections); all 56
common wrong answers are caught with verdict FAIL; 20
discrete selections hold in both directions (Q9
stiffness 8/10/12, Q14 heater 750/1000/1250, Q19
resistance 270/330/390 and ratings 0.125/0.250/0.500,
Q24 diameter 160/200/240); and 15 wrong answers in the
newly accepted or newly guarded forms are caught (the
repair records below: 10 at `frozen-2026-10-03.1`, 5 at
`frozen-2026-10-03.2`). The scorer scores semantics —
unit conversion and tolerance comparison — not regex
presence.

## Scorer repair record — `frozen-2026-10-03.1`

**Trigger.** Ruling D50 (1), carried by
ARCH-20261003-119: the tier-3 experiment must
measure answers, not formatting, and the tier-2
scorer is repaired as a new version before any
paid unit runs. The diagnosis: the frozen scorer
(`frozen-2026-10-03`) read the *notation* of the
twelve recorded answers (`docs/traces/107-direct-baseline.jsonl`,
`102-golden-arm-b.jsonl`, `106-golden-arm-b.jsonl`
— real provider output, five questions per run)
rather than their content: **7 of the 12 vectors
failed** under the frozen scorer (107 Q4, Q5;
102 Q2, Q4, Q5; 106 Q4, Q5). A scorer that fails
correct answers because they are written in a
different notation measures formatting, not
answers.

**The repair — eight general classes, each a
widening of what the scorer reads, never a
narrowing** (the wrong-answer corpus stays
rejected; class (7) is a read rule, not a
threshold change):

1. **Heading forms** (`_HEADING` in
   `_score_q4`'s sections and
   `_organization`'s heads): bold, italic,
   labeled and numbered headings are read as
   headings, not just markdown `#`.
2. **Plain-digit unit exponents** (`_UNIT_AFTER`):
   `mm2`/`mm3` read as `mm²`/`mm³` (the UNITS
   table already keys both).
3. **Unicode-superscript exponents and digit
   grouping** (`_normalize`): `6.14×10⁻⁷` and
   `30,000` are normalized to the caret form and
   the bare integer.
4. **Inclusive-max operator synonyms**
   (`_NONSTRICT_LESS`, `INCLUSIVE_MAX`): "must
   not exceed", "does not exceed", "up to and
   including" read as the inclusive ≤ the keys
   state.
5. **Q2 every-mention window** (`_score_q2`'s
   `threshold_check`): the threshold is checked at
   *every* mention of the gas — a passing window
   anywhere passes; the fail detail names that
   every mention misstates operator, basis or
   comparison.
6. **Leakage-absence phrasings**
   (`_leakage_absent`): "no visible leakage",
   "zero visible", "leakage: none" read as the
   absence the keys define.
7. **The verdict read, excluding conditional
   clauses** (`_score_q5` item 8): a verdict word
   inside an occurrence-level 40-character
   conditional window is ignored; a line beginning
   with a conditional marker (`if`, `unless`,
   `when`, `then`, `otherwise`, `iff`, `must be`,
   `→`) is a rule line in its entirety; a labeled
   declaration (`Verdict: PASS`) takes precedence
   over the last stated word.
8. **Operation-phrase widening and occurrence-pair
   ordering** (`_phrase_positions`, `_ordered`):
   every occurrence of each operation phrase is
   located (word-boundary stems: `pressuriz` reads
   "pressurize" and "pressurization", both
   American and British `pressuris` stems, and
   `close` reads "closed"), and ordering holds when
   *any* before-occurrence precedes *any*
   after-occurrence.

**Verification** (all recorded in the
`frozen-2026-10-03.1` `versions.json` entry):

- The 12 recorded vectors now score **12/12**
  (frozen: 5/12) — `evals/tier2/regression_12.py`,
  wired into the suite by
  `tests/test_tier2_regression.py`.
- The notation-variant sweep: **52 model-answer
  variants all pass, 42 wrong-answer variants all
  fail** — `evals/tier2/notation_sweep.py` (every
  Q1–Q5 model answer and every Q1–Q5 wrong answer
  rendered in every applicable variant form: five
  heading styles, three exponent forms, two unit
  forms, two grouping separators, eight operator
  synonym classes, five step styles plus a step
  table, verdict before/after the figures, rule
  lines at start/middle/end, plain text).
- The self-test holds **258/258** (248 frozen
  fixtures plus 10 new wrong answers, one in each
  newly accepted form, so every widening is
  guarded by a wrong answer it must still catch).
- `verify_keys.py`'s 268 checks hold (keys.json
  unchanged); `extract_candidate.py` re-run
  reproduces `manifest.json` with exactly one
  field changed (`scorer_version`), and
  questions.json/keys.json byte-identical.

**Scope of the freeze.** The dataset content is
untouched: questions.json and keys.json hash to
the frozen-2026-10-03 entry. Only scorer.py
changed, and the manifest's `scorer_version`
names the new entry while `dataset_version` keeps
the frozen name — the dataset froze; the
instrument was repaired under the freeze.

## Scorer repair record — `frozen-2026-10-03.2`

**Trigger.** The advisor's PR #152 review
(2026-10-04): *hold the merge*; fix two
defects on the same branch, then re-measure
on the owner's actual lineup. The first
defect: an order item must read the answer's
own procedure — "its numbered, bulleted or
'Step n' lines. A mention outside the steps
neither creates an order nor undoes one" —
with the exhibit that Q5's model answer with
its steps reversed, preceded by the question
text verbatim, **scores PASS 9/9 under
frozen-2026-10-03.1**. The second: the Q2
false PASS — "a definition stated as 'less
than 19.0 percent', with '19.5%' named
elsewhere as 'some sources', passes under
both versions."

**Diagnosis of the first defect.** The `.1`
repair (class 8) widened `_ordered` to hold
when *any* before-occurrence precedes *any*
after-occurrence *anywhere in the answer*,
"a mention in a preamble, an equipment list
or a falsifier does not undo the order the
procedure itself states". The question's own
text states the correct order in prose —
"then closing the vent before pressurization",
"After assessing the result, use the release
valve to depressurize and confirm 0 bar gauge
before disconnecting" — so an answer that
restates the question and then states the
procedure *backwards* passes whole: the prose
supplies every order pair. The exhibit is a
wrong answer that the `.1` scorer cannot
catch.

**The repair — procedure scope, a
narrowing of what the order items read**
(`_PROCEDURE_LINE`, `_procedure_lines`,
`_ordered` in `scorer.py`): the order items
now read only the answer's own procedure
lines — numbered (including sub-numbered
`1.1.`), bulleted, and `Step n` lines in the
plain, bold (`**Step n —**`), markdown
(`### Step n —`) and step-table forms the
recorded answers and the notation sweep
write — and no other lines. An answer with no
procedure lines states no order. The phrase
matching itself is unchanged (word-boundary
stems, `re:`-prefixed regexes, either
depressurization spelling); only *which lines
are read* changed. The twelve recorded answers
still score 12/12: every order phrase in all
three recorded Q5 answers (107's numbered
steps, 102's `**Step N —**` lines, 106's
sub-numbered steps, `### Step N —` headings
and checkbox bullets) sits inside a procedure
line, so the strict scope reads what the
loose scope read — and nothing else.

**The exhibit, measured before it was fixed
as a fixture** (the reading the review
predicted): Q5's restated-question-plus-
reversed-steps exhibit scores **FAIL 8/9** —
only "Final operations: assess, depressurize,
confirm zero, disconnect" fails, because
assess-then-depressurize is the exhibit's
only cross-step pair (close-vent and
isolate-timing each sit inside one step).
The same construction is a wrong-answer
fixture for every order question the tree
holds, with the measured readings: **Q5 8/9,
Q10 3/4** ("Setpoint and timer-start order"
fails — setpoint and timer-start sit in
different steps), **Q15 5/6** ("Ordered check
sequence" fails — all four checks sit in
different steps), **Q20 5/6** ("Start and
stabilization" fails — stabilization and
collection sit in different steps; "Collection
sequence" holds because zero-before-divert
sits inside one step and divert-before-collect
still spans two steps in the reversed order).
The self-test grows 258 → 263 fixtures: the
four exhibit fixtures (each pinning every
item's reading, not just the failing one) and
the Q2 threshold fixture below.

**Two findings the review's list did not
match, recorded for the readers** (convention
26 — the report states what execution found):

1. **The review's order-item list is the
   `.1` changelog text, not the tree.** The
   review's parenthetical "(Q10, Q11, Q14,
   Q16, Q19)" repeats the `frozen-2026-10-03.1`
   `versions.json` changelog, which misnames
   the order questions. The tree's order items
   live in the five **PROCEDURE-shaped**
   questions **Q5, Q10, Q15, Q20, Q25**:
   `_ordered` is called by `_score_q5`,
   `_score_q10`, `_score_q15`, `_score_q20`
   and `_score_q25`, and Q11, Q14, Q16 and
   Q19 (SANITY and SPECIFICATION shapes — the
   extraction's own shape column confirms it)
   carry no order item. The fixtures cover
   every order item the tree has; the general
   rule in `_ordered` fixes the order items
   wherever they live, so a future question
   that adds an order item is covered by
   construction.
2. **Q25's order items cannot be falsified
   by this construction — a known weakness.**
   All of Q25's order pairs (0 V → enable →
   confirm LOW; return to zero → disable) sit
   *inside single steps*, so reversing the
   step order changes nothing: the reversed
   exhibit scores **6/6 PASS**. No wrong-answer
   fixture exists for Q25's order items by
   the reversed-steps construction. A Q25
   wrong answer must instead misstate an
   order *within* a step (as the existing
   corpus does for other questions); the
   reversed-steps construction is simply blind
   to Q25's order items. Listed here as a
   known weakness for the readers, per the
   review's instruction.

**Diagnosis of the second defect (the Q2
false PASS).** `threshold_check` located the
threshold *anywhere* in the answer (the
`stated` loop) and then checked the
operator/basis/volume window at every gas
mention — but never required the window to
carry the value. A definition that misstates
its own threshold ("less than 19.0 percent")
with the true threshold named elsewhere
("some sources cite 19.5 percent") therefore
passed: the anywhere-loop found 19.5 and the
window around "deficient" carried the strict
operator, the volume basis and no mass mention.

**The repair — the definition's window must
state its own threshold** (`_threshold_stated`
in `scorer.py`): the 120-character window
around each gas mention must itself carry the
threshold it defines — a percent quantity, or
a unitless volume fraction — or the window is
rejected. The fix is general (a rule about
where a definition's threshold lives, applied
to both gases and every phrasing), so no
known-weakness entry is needed for it beyond
this record. The review's construction now
fails exactly as it should: the deficient
definition fails (its window carries 19.0,
not 19.5), the enriched definition still
passes (its own window carries 23.5), and
the model answer and all three equivalent
notations the keys list (fraction, below/
above phrasing, v/v) still pass. The older
false-PASS construction is added as a
wrong-answer fixture.

**Companion instrument repair (not a versioned
file).** The first `.2` draft failed the
notation sweep: the sweep's heading restyle
re-styled *numbered step lines* as bare
headings (`**Fill with water…**`), stripping
the numbering — which destroyed the procedure
the repaired scorer now reads, so the four
Q5 heading variants scored 6/9. Convention 17
asks which of the two is wrong: the sweep
instrument, not the scorer — a numbered line
is a step line, not a section heading, and
its numbering is the procedure's structure.
`notation_sweep.py`'s `_restyle_headings` now
leaves numbered lines intact (it still re-styles
every true heading form). The sweep's measured
counts are unchanged: **52/52 model-answer
variants pass, 42/42 wrong-answer variants
fail**.

**The review's second defect (the tier-3
fetch tool), repaired on the same branch.**
`fetch_primary_source` (`evals/tier3/runner.py`)
rejected citations copied verbatim from the
questions: the questions wrap each figure in
LaTeX `$` separators (`$29$ CFR § $1910.146(b)$`),
and the three with a paragraph inside the
wrappers (Q2, Q12, Q22) left a trailing `$`
after the paragraph group, defeating the
anchored citation match — so verbatim copies
returned not-available. The wrappers are now
stripped wherever they sit before the anchored
match (the tool's own docstring already
claimed wrapper tolerance; the code now
matches its contract). The guard test uses the
exact wrapped strings extracted from
`questions.json` for all five lookup questions
(Q2, Q7, Q12, Q17, Q22), asserts the set is
exactly those five (convention 28), and
carries the break-proof quoted under it: with
the strip removed, Q2's verbatim citation
`'$29$ CFR § $1910.146(b)$'` returns
not-available. The tier-3 manifest records the
repair as `tier3-3`.

**Verification** (all recorded in the
`frozen-2026-10-03.2` `versions.json` entry):

- The 12 recorded vectors still score **12/12**
  — `evals/tier2/regression_12.py`.
- The notation sweep: **52/52 model-answer
  variants pass, 42/42 wrong-answer variants
  fail** — `evals/tier2/notation_sweep.py`
  (counts unchanged from `.1`).
- The self-test holds **263/263** —
  `evals/tier2/scorer.py --self-test`.
- `verify_keys.py`'s 268 checks hold
  (keys.json unchanged); `extract_candidate.py`
  re-run reproduces `manifest.json` with
  exactly one field changed (`scorer_version`)
  and questions.json/keys.json byte-identical.
- The suite: `.venv/bin/python3 -m pytest
  tests/ -q` green (the tier-2 and tier-3
  guard tests updated to the new version
  names and fixture count).

**Scope of the freeze.** As at `.1`: the
dataset content is untouched — questions.json
and keys.json hash to the frozen-2026-10-03
entry. Only scorer.py changed among the four
versioned files; `notation_sweep.py` (a suite
instrument, not a versioned file) changed as
the companion repair above; `evals/tier3/runner.py`
carries the fetch repair the same review
ordered. The manifest's `scorer_version` names
the new entry while `dataset_version` keeps
the frozen name — the dataset froze; the
instrument was repaired under the freeze.

## Source records (the lookup questions)

Five questions are lookup questions (Q2, Q7, Q12, Q17,
Q22), across four regulations. Each primary text was
fetched and archived with its retrieval date, URL and
content hash, and every claimed verbatim quotation was
matched against that archive. Editions are identified by
the govinfo package identifier and the GPO typesetting
footer on every page — not inferred from a current
webpage. The current eCFR (as of 2026-10-01, fetched via
the versioner API) is used only as the stability
cross-check the command requires ("unchanged for at least
three years"); a single fixed, correctly identified source
snapshot (the pinned July 1, 2014 annual edition) is the
verification basis.

| question | regulation | edition | govinfo URL | retrieved |
|---|---|---|---|---|
| Q2 | 29 CFR §1910.146(b) | Title 29, vol. 5, July 1, 2014 | …/CFR-2014-title29-vol5/pdf/CFR-2014-title29-vol5-sec1910-146.pdf | 2026-10-03T07:59:27Z |
| Q7, Q22 | 29 CFR §1910.95 (Table G-16; paragraph (g)) | Title 29, vol. 5, July 1, 2014 | …/CFR-2014-title29-vol5/pdf/CFR-2014-title29-vol5-sec1910-95.pdf | 2026-10-03 (manifest) |
| Q12 | 40 CFR §141.62(b) | Title 40, vol. 23, July 1, 2014 | …/CFR-2014-title40-vol23/pdf/CFR-2014-title40-vol23-sec141-62.pdf | 2026-10-03 (manifest) |
| Q17 | 29 CFR §1910.147((c)(5)(ii)(C)(2); (c)(6)(i)) | Title 29, vol. 5, July 1, 2014 | …/CFR-2014-title29-vol5/pdf/CFR-2014-title29-vol5-sec1910-147.pdf | 2026-10-03 (manifest) |

Verbatim quotations matched against the archives:

> Q2, paragraph (b): "Oxygen deficient atmosphere means an
> atmosphere containing less than 19.5 percent oxygen by
> volume." / "Oxygen enriched atmosphere means an
> atmosphere containing more than 23.5 percent oxygen by
> volume."

> Q7, Table G-16: the rows pairing 90 dBA with 8 hours,
> 95 dBA with 4 hours and 100 dBA with 2 hours, under
> the column header "Sound level dBA slow response".

> Q12, paragraph (b): fluoride 4.0 mg/L ((b)(1));
> nitrate 10 mg/L as Nitrogen ((b)(7)); arsenic
> 0.010 mg/L ((b)(16)).

> Q17: the attachment means shall have "a unlocking
> strength of no less than 50 pounds" ((c)(5)(ii)(C)(2));
> the procedure shall be inspected "at least annually"
> ((c)(6)(i)) — the archived text carries these figures.

> Q22, paragraph (g): the baseline audiogram within six
> months of first exposure at or above the action level;
> at least 14 hours without exposure to workplace noise
> before the baseline; retest within 30 days.

Stability cross-checks: all four regulations carry the
same provisions verbatim in the current eCFR text as of
2026-10-01 (archived at `sources/ecfr-current-2026-10-01-*.xml`)
— a 12-year span, which satisfies the command's
"unchanged for at least three years" requirement. The
per-question hashes, byte counts and extraction
hashes are recorded in `manifest.json` and guarded by
`tests/test_tier2_keys.py` (which fails if any archive on
disk no longer matches its manifest record).

## Provenance of the candidate questions

The questions were authored by gpt-6.1-sol-pro with
`web_search`, `web_fetch` and shell access, at the owner's
direction (the candidate export records its own provenance).
This is recorded as provenance, not treated as a violation:
the owner supplied the array as CANDIDATE DATA, and the
executor's role under the command is verification, not
generation. **The executor did not generate, screen, or
select any question, and no AI model was queried about the
questions** during verification — the verifier and scorer
are deterministic, provider-free programs.

## Resolved items (the signoff the command required)

The owner ratified the tier-2 signoff on 2026-10-03
(21:41:20Z, in conversation: "ratify the tier-2
signoff"). The ratification covers:

1. **The independent verification.** All 268 checks of
   `evals/tier2/verify_keys.py` hold: every numerical
   key recomputed from first principles, dimensions,
   boundary operators, discrete selections and tolerance
   boundaries checked, all 56 claimed wrong answers
   falsified, and `keys.json`'s own value strings
   cross-checked against the recomputation (X1–X67).
2. **The source review.** The five lookup questions
   (Q2, Q7, Q12, Q17, Q22) are verified against four
   archived July 1, 2014 govinfo editions with every
   claimed verbatim quotation matched character-for-character
   against the archive, editions identified by package
   identifier and GPO typesetting footer (not inferred
   from a current webpage), and each regulation
   stability-cross-checked against the 2026-10-01 eCFR
   (a 12-year span).

The freeze is executed: `manifest.json` records
`frozen: true`, an empty `freeze_blocked_by`, and the
`freeze` record (grantor, time, scope, effect);
`versions.json` carries the `frozen-2026-10-03` entry
and the manifest names it. The dataset content is
unchanged from `candidate-2026-10-03.3` — the freeze
changed only what the instruments report and the
manifest records.

**Not a blank cheque for paid execution of tier 3.**
The signoff permits paid use of the set; the five-arm
experiment (ARCH-20261002-118) remains gated on its
own ratifications: explicit owner ratification of the
serving proposals and of the total spend authorization
before any paid run.

## Not done (out of scope under the command)

- No paid calls were made; no standing configuration was
  changed; `.env` was not touched.
- Tier 3 (the five-arm experiment) remains **NO_ACTION**
  (ARCH-20261002-118): its precondition — "after the
  dataset PR merges and required key/source review is
  complete" — is not met by this unfrozen candidate. No
  manifest for the experiment is frozen here, and no paid
  execution may start without explicit owner ratification
  of the serving proposals and the total spend
  authorization.
