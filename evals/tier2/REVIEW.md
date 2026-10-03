# Tier-2 candidate set — verification review checklist

Command: **ARCH-20261002-117** (tier 2 of the owner's
three-tier instruction of 2026-10-02): "Register and
independently verify the 25-question set."

**Status: PARTIAL — 5 of 25 questions registered and verified.
The set is NOT frozen.** The supplied candidate array holds 5
questions; the command and its $90.00 aggregate ceiling are
written for 25. The remaining 20 must be supplied by the
owner or advisor: the command forbids the executor (and any
AI model) from generating, screening, or selecting questions.
See "Unresolved items" below.

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

Dataset version / scorer version: `candidate-2026-10-03.2`
(see `versions.json`; every change to the four versioned
files is a new entry naming the change and its trigger).

## The checks, and their results

All 61 checks of `evals/tier2/verify_keys.py` hold (exit 0);
all 64 scorer self-test fixtures hold (exit 0). The suite
guard `tests/test_tier2_keys.py` (17 tests) runs both
instruments on the tree and proves each can fail on corrupted
copies (convention 22).

| check | what it verifies | result |
|---|---|---|
| G1 | candidate export hashes to the manifest record | PASS |
| G2 | questions.json, keys.json, manifest agree on count and identities | PASS (5, Q1–Q5) |
| G3 | the count discrepancy is recorded; the set is not frozen | PASS (5 vs 25, blocker named) |
| G4 | the model-visible file carries no scorer material | PASS (exactly id, shape, domain, question) |
| G5 | the scorer-only file carries no model-visible request | PASS |
| G6 | every question carries required items with tolerances and derivations, wrong answers with reasons | PASS |
| Q1.1–Q1.2 | voltage-divider output and series current recomputed from the stated inputs | PASS (8.00 V ±0.01; 2.00 mA ±0.01) |
| Q1.3 | dimensions: V·Ω/Ω is volts; V/Ω is amperes | PASS |
| Q1.4–Q1.5 | wrong answers "4 V output" and "6 mA current" are genuinely wrong under the stated assumptions | PASS (each is the upper-resistor-only quantity, far outside tolerance) |
| Q2.1–Q2.3 | archived 2014 PDF, its text extraction, and the stability-cross-check XML each hash to the manifest record | PASS |
| Q2.4–Q2.5 | both 29 CFR 1910.146(b) definitions matched **verbatim** against the archived July 1, 2014 edition (left-column reconstruction of the two-column typesetting) | PASS (character-for-character, modulo whitespace) |
| Q2.6–Q2.8 | strict operators ("less than"/"more than", not "at or below"/"at or above"), volume basis (not mass), and the stability cross-check against the 2026-10-01 eCFR | PASS (identical text across a 12-year span) |
| Q2.9–Q2.12 | wrong answers "at or below 19.5%", "at or above 23.5%", "by mass", and "mg/m³" are genuinely wrong | PASS |
| Q3.1–Q3.3 | polar second moment J = πd⁴/32, shear stress τ = Tr/J, twist θ = TL/(GJ) recomputed | PASS (6.13592×10⁻⁷ m⁴ ±0.2% rel; 2.03718×10⁷ Pa ±0.2% rel; 0.0101859 rad ±0.2% rel) |
| Q3.4 | dimensions: m⁴, Pa, rad | PASS |
| Q3.5–Q3.7 | wrong answers "J = πd⁴/64", "40.7 MPa", "0.0102 degrees" are genuinely wrong | PASS |
| Q4.1–Q4.3 | discrete selection (smallest passing thickness from the available strip set), stated dimensions, gross area | PASS (3.00 mm; 60.0 mm²) |
| Q4.4 | stress check with equality permitted (100 MPa allowable, 100 MPa computed passes) | PASS |
| Q4.5–Q4.7 | next-thinner strip (2.00 mm) fails at 150 MPa; volume; mass | PASS (2.00e-5 m³; 0.2355 kg ±0.0005) |
| Q4.8 | three-section organization (selection / strength / volume-and-mass) | PASS |
| Q4.9 | wrong answers "select 4 mm", "select 2 mm", "235.5 kg" are genuinely wrong | PASS |
| Q5.1 | logged pressure drop recomputed (6.00 → 5.90 bar) | PASS (0.10 bar ±0.001) |
| Q5.2 | verdict follows from the stated conjunctive criteria | PASS (PASS) |
| Q5.3 | acceptance boundary operator: the limit itself passes, one hundredth past it fails | PASS (inclusive "no more than 0.20 bar") |
| Q5.4 | the specified test pressure is 6.00 bar, not the 10.0 bar component rating | PASS |
| Q5.5 | worked answer carries the prescribed operation order (nine precedences) | PASS |
| Q5.6 | no-addition rule and conjunctive acceptance criteria stated | PASS |
| Q5.7–Q5.11 | wrong answers "test at 10.0 bar", "start timing while raising pressure", "pump during the hold", "fail because the final pressure is below 6.00 bar", "disconnect before confirming zero" are genuinely wrong | PASS |
| X1–X11 | keys.json's own value strings parsed and required to agree with the first-principles recomputation within the stated tolerances | PASS (single source of key values) |

Scorer self-test (64 fixtures): all five model answers hold
every item; every equivalent notation the keys list (mV, kPa,
N/mm², mrad, cm³, g, minutes, volume fractions, v/v,
below/above phrasing) holds; tolerance boundaries hold just
inside and fail just past; all 15 common wrong answers are
caught; the discrete selection holds in both directions; the
acceptance-criterion boundary operator is enforced ("no more
than 0.20 bar" passes, "below 0.20 bar" fails). The scorer
scores semantics — unit conversion and tolerance comparison —
not regex presence.

## Source record (Q2, the lookup question)

| field | value |
|---|---|
| Regulation | 29 CFR §1910.146(b), permit-required confined spaces |
| Edition | Title 29, volume 5, annual edition revised as of July 1, 2014 |
| Edition-identification basis | The section PDF starts mid-standard and carries no volume title page; the edition is identified by the govinfo package identifier `CFR-2014-title29-vol5` (the annual edition of Title 29, volume 5, revised as of July 1) and corroborated by the GPO typesetting date in every page footer ("Aug 01, 2014", file `29V5.TXT`). The edition is **not** inferred from a current webpage. |
| URL | https://www.govinfo.gov/content/pkg/CFR-2014-title29-vol5/pdf/CFR-2014-title29-vol5-sec1910-146.pdf |
| Retrieved | 2026-10-03T07:59:27Z |
| PDF | 525,632 bytes, SHA-256 `a53232848d11f1ad891a54b39e7e334c43a1b8bcaccac0403f04250e7b45fc3f` |
| Text extraction | `pdftotext -layout` (Poppler); 157,342 bytes, SHA-256 `f8bd471e64a5a8e57e503556a5bd55bc0f533c3e12891a63410eb0de9cf70612`; committed as `sources/CFR-2014-title29-vol5-sec1910-146.txt` so CI needs no pdftotext |

Verbatim quotations matched against the archive (both in
paragraph (b), left column of the two-column typesetting):

> "Oxygen deficient atmosphere means an atmosphere containing less than 19.5 percent oxygen by volume."

> "Oxygen enriched atmosphere means an atmosphere containing more than 23.5 percent oxygen by volume."

Stability cross-check (the command requires lookup sources
unchanged for at least three years): both definitions are
identical in the current eCFR text as of 2026-10-01, fetched
via the eCFR versioner API
(`https://www.ecfr.gov/api/versioner/v1/full/2026-10-01/title-29.xml?part=1910&section=1910.146`,
retrieved 2026-10-03T08:05:53Z, 84,744 bytes, SHA-256
`d3dc555e5e783af729b8243ba7932aff576daac7562817c4ddc038d5ef8eb182`,
archived at `sources/ecfr-current-2026-10-01-sec1910-146.xml`)
— a 12-year span, which satisfies the requirement. A single
fixed, correctly identified source snapshot (the pinned July 1,
2014 annual edition) is the verification basis; the current
eCFR is used only as the stability cross-check, not as the
edition of record.

## Provenance of the candidate questions

The five questions were authored by gpt-6.1-sol-pro with
`web_search`, `web_fetch` and shell access, at the owner's
direction (the candidate export records its own provenance).
This is recorded as provenance, not treated as a violation:
the owner supplied the array as CANDIDATE DATA, and the
executor's role under the command is verification, not
generation. **The executor did not generate, screen, or
select any question, and no AI model was queried about the
questions** during verification — the verifier and scorer are
deterministic, provider-free programs.

## Unresolved items (freeze blockers)

1. **Count discrepancy (the blocker).** The command and its
   $90.00 aggregate ceiling are written for a 25-question set
   ($1.20 per question-run ceiling × 375 planned question-runs
   = $90.00). The supplied candidate array holds **5**
   questions. With 5 questions the same per-question-run
   ceilings correspond to an aggregate of $18.00 (75
   question-runs), not $90.00. The remaining 20 questions must
   be supplied by the owner or advisor; the command forbids
   the executor and any AI model from generating, screening,
   or selecting them. The set is registered unfrozen;
   `manifest.json` carries the blocker and `versions.json`'s
   ruling text names the resolution path (a new entry when the
   set freezes).
2. **Independent subject-matter signoff.** Deterministic
   arithmetic verification is **not** independent
   subject-matter approval. The recomputation proves the keys
   follow from the stated inputs and formulas; it does not
   prove the questions are the right questions, that the
   formulas are the right models of the domains, or that the
   archived edition is the edition the question intends. Per
   the command, owner or qualified-reviewer signoff is
   required before any paid use of this set.
3. **Source review.** Only Q2 is a lookup question among the
   five supplied; the other four are derivation/specification/
   procedure/sanity questions whose "sources" are the stated
   inputs and standard formulas. If the remaining 20 include
   further lookup questions, each needs the same treatment:
   primary text fetched and archived with retrieval date, URL,
   and content hash, and every claimed verbatim quotation
   matched against that archive.

## Not done (out of scope under the command)

- No paid calls were made; no standing configuration was
  changed; `.env` was not touched.
- Tier 3 (the five-arm experiment) remains **NO_ACTION**
  (ARCH-20261002-118): its precondition — "after the dataset
  PR merges and required key/source review is complete" — is
  not met by this unfrozen 5-question candidate. No manifest
  for the experiment is frozen here, and no paid execution
  may start without explicit owner ratification of the serving
  proposals and the total spend authorization.
