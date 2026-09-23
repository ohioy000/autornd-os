# Pre-registration: glossed-criterion attribution rubric

**Registered:** 2026-09-23, before classification.
**Purpose:** Decide whether each of the 38 glossed criteria from ARCH-20260922-038
is ADDRESSED by the validator's evidence, using rules a reader who did not write
the rubric can apply without taste.

## Population

The 38 criteria classified "glossed" by the -038 measurement. These are criteria
the deterministic coverage check abstained on (FORM) where the validator's
evidence had ≥25% term overlap but did not meet the addressed threshold (≥35%
overlap AND a judgment signal). The 132 addressed and 24 unattributable criteria
are held fixed — they are not re-classified. Why: they were measured by the same
instrument and re-classifying them would change the denominator and invalidate
the threshold derivation.

## Rules

A glossed criterion resolves to **ADDRESSED** if and only if ALL THREE of the
following hold for at least one evidence item:

1. **Names the criterion's subject.** The evidence item names or restates the
   condition the criterion asserts — the specific thing to be present, absent,
   counted, structured, or verified. "Names" means the evidence item contains at
   least one content word (not a stopword) that identifies the same concept the
   criterion identifies, and the concept is the criterion's subject rather than
   a coincidence.

2. **States a verdict.** The evidence item contains an explicit pass, fail, or
   equivalent judgment word about the condition: PASS, FAIL, present, absent,
   verified, confirmed, met, not met, compliant, non-compliant, correct,
   incorrect, counted, measured, specified, provided, included, missing, or a
   negation of any of these.

3. **Attributable to this criterion and no other.** The evidence item's subject
   is closer to this criterion than to any other criterion in the same unit's
   success_criteria list. If the evidence item could equally apply to two or more
   criteria, it does not count for any of them.

A glossed criterion that fails any of the three rules resolves to
**NOT ADDRESSED**. Each not-addressed criterion is assigned a gap kind:

- **Gap A — named but no verdict:** the evidence item names the criterion's
  subject but contains no judgment word.
- **Gap B — verdict about a different condition:** the evidence item makes a
  judgment, but about a different aspect of the work than this criterion asserts.
- **Gap C — no evidence item relates:** no evidence item names or relates to the
  criterion's subject (i.e., it should have been classified unattributable by the
  original instrument, and its glossed status is a false positive from term
  overlap noise).

## Taste declaration

Rule 1 ("names the criterion's subject") requires a judgment call: deciding
whether a shared content word identifies the same concept or is a coincidence.
This is the one rule that requires taste. Where it is ambiguous, the criterion is
marked NOT ADDRESSED with a note, and the ambiguous count is reported separately
so the decision can be audited.

## Decision rule

The threshold (Ruling D14) is 81% addressed-or-attributed, which requires at
least 158 of 194 criteria. 132 are already addressed. Therefore the bar is met
if and only if at least 26 of the 38 glossed criteria resolve to ADDRESSED under
this rubric. If 25 or fewer resolve, the typed judgment layer (ARCH-20260922-045)
is required.

81% is inclusive: a rate of exactly 81.0% meets the bar.
