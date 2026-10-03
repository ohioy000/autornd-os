# Tier-2 candidate set — verification review checklist

Command: **ARCH-20261002-117** (tier 2 of the owner's
three-tier instruction of 2026-10-02): "Register and
independently verify the 25-question set."

**Status: the complete 25-question set is registered and
verified. The set is NOT frozen.** The owner supplied all
25 questions on 2026-10-03 (the array the command names,
registered verbatim — the executor generated, screened
and selected nothing). The count discrepancy that blocked
the first registration is resolved; the remaining freeze
blocker is the signoff the command requires: owner or
qualified-reviewer signoff on this verification and the
source review before paid use. See "Unresolved items"
below.

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
| Manifest (versions, counts, archives, blockers) | `manifest.json` |
| This checklist | `REVIEW.md` |

Dataset version / scorer version: `candidate-2026-10-03.3`
(see `versions.json`; every change to the four versioned
files is a new entry naming the change and its trigger).

## The checks, and their results

All 268 checks of `evals/tier2/verify_keys.py` hold (exit
0); all 248 scorer self-test fixtures hold (exit 0). The
suite guard `tests/test_tier2_keys.py` (17 tests) runs
both instruments on the tree and proves each can fail on
corrupted copies (convention 22).

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

Scorer self-test (248 fixtures): all 25 model answers
hold every item; 47 equivalent notations the keys list
hold (number words, μg/L, μA, ms, mJ, N mm, kN/m, rev/s,
K, mV, mm⁴, μm, newton-metres, mg N/L, …); 100 tolerance
boundaries hold just inside and fail just past (including
equality-permitted limits and exact selections); all 56
common wrong answers are caught with verdict FAIL; 20
discrete selections hold in both directions (Q9
stiffness 8/10/12, Q14 heater 750/1000/1250, Q19
resistance 270/330/390 and ratings 0.125/0.250/0.500,
Q24 diameter 160/200/240). The scorer scores semantics —
unit conversion and tolerance comparison — not regex
presence.

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

## Unresolved items (freeze blockers)

1. **Owner or qualified-reviewer signoff (the remaining
   blocker).** Deterministic arithmetic verification is
   **not** independent subject-matter approval. The
   recomputation proves the keys follow from the stated
   inputs and formulas; it does not prove the questions
   are the right questions, that the formulas are the
   right models of the domains, or that the archived
   edition is the edition each question intends. Per the
   command, owner or qualified-reviewer signoff on this
   verification and the source review is required before
   the set freezes and before any paid use. The signoff
   is recorded as pending in `manifest.json`
   (`freeze_blocked_by: review-pending …`); the set
   stays unfrozen until it is granted.
2. **Source review of the lookup questions.** The five
   lookup questions' quotations were matched against the
   archived July 1, 2014 editions and stability-checked
   against the 2026-10-01 eCFR. A qualified reviewer
   should still read the archived sources beside the
   keys (not just the machine match) before signoff —
   the match proves the quotation is in the archive, not
   that the question asks the right thing of it.

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
