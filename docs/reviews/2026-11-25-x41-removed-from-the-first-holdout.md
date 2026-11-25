# X41 removed from the first hold-out set (version 1.1), 2026-11-25

**Status: owner's instruction in conversation 2026-11-25 ("Remove x41 from questionset"), which is the D44 ratification of a new version.**

## What was found

X41 asks for the ATmega328P's junction-to-ambient thermal resistance and its maximum junction temperature or power dissipation from
"the complete datasheet (DS40002061B, 09/2020)". Its key says none of these is stated. Read on 2026-11-25:

- **The keyed PDF states none.** The datasheet PDF was fetched and read in full (310,048 characters): no thermal resistance, junction
  temperature or dissipation figure. The key is correct about that document.
- **A real page for the same part states one.** Microchip's online documentation (a `ww1.microchip.com` HTML page for the same device family)
  prints Table 37-9, "Thermal Resistance Junction to Ambient 60 degC/W, 28-pin PDIP". Three answers of the page-quality test of 2026-11-25 quoted it,
  the quote recorded `found` on a page the harness read in full; they were scored not right against a key that says there is none.

So the question is not wrong about the PDF and not answerable "right" by a harness that finds the other real page, which is a thing a careful
reader is right to do. A question whose key a correct, grounded answer can contradict does not measure the harness.

## What changed

- `evals/professional/holdout-questions.json` is now version `professional-holdout-1.1`: 41 questions, X41 removed, every other question
  identical (a test compares them), a `changes` record naming what was removed and why.
- `evals/professional/holdout-questions-v1.json` is the set as signed on 2026-11-17, byte for byte (sha256 `c5d4a9da...`, pinned by a test). Every
  earlier reading of 42 questions reproduces from it. The reviews and traces of earlier runs keep their 42 and are not rewritten.
- Side by side, as D44 asks, for the runs already made on X41: the first hold-out asked again (2026-11-24) read 104 of 126 right with X41
  contributing 3 answers (one blocked by a 429, one right, one right); the page-quality run's X41 draws (one blocked, two not right) are outside
  the 126. Counted without X41 the earlier figures are not restated here; a reader who wants them re-scores from the archive.

## What this does not change

The harness: no code. The proofs of absence and "none stated" path remain exercised by X19 and X36, which are right "none stated" cases whose keys
the pages cannot contradict.
