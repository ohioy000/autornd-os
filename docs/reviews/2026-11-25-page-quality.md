# Script-built pages read through their own routes: the test, 2026-11-25

Preregistered in `docs/preregistration-20261125-page-quality.md` (82b2466, corrected in 97dde09), pushed before the spend. Tree `1928548`
(branch `feat/20261125-page-quality`). **'$0.31' of a ceiling of '$0.50'** for 21 answers ('$0.0145' an answer); no provider error, no
spend-guard entry. Files and sha256: `docs/traces/20261125T-page-quality-MANIFEST.sha256`.

## The point

- **The mechanism works on both routed sites.** H9 (NVD) **3 of 3 right** with no caution, the answers quoting the JSON record; the stored
  baseline had a wrong "not answered by the grounding" refusal on the 72-character frame. X31 read the 2025 instrument's PDF through the
  route in 2 of 3 draws (both right on all three key items). Dated compilation pages, which are not routed, were refused as shells
  (X31: 4 pages; H9: the NVD search and calculator pages) and none of them was used as a proof.
- **The preregistered rule for merging is not met on its letter:** targets 5 of 6 right (rule met: the one miss does not come from a
  frame), but **controls 2 of 9 not right and 1 blocked** against at most 1. **Neither control miss touches the change:** the shell rule
  fired in no X41, X19 or X36 unit (read from the stored source records), and X41's two answers quote a real page.
- **No hold condition triggered:** no control that was right became wrong because a page was refused as a frame.

## Reading (executor only, key beside the answer; **the preregistered blind reader was not used**: 21 answers, readings clear except X41)

| Question | Draw 1 | Draw 2 | Draw 3 | Note |
|---|---|---|---|---|
| X31 (target) | right | **wrong**: names the 2015 licence as in force | right | Draw 2 read compilations of the 2015 licence and never the 2025 text; a document-choice miss, the known stale-page weakness. Its figures (4 W, 25 mW per 3 kHz) are right |
| H9 (target) | right | right | right | 10.0 and CRITICAL, v2's 9.3 named only as the other version |
| X3 | right | right | **wrong**: "not stated" for the SO2/NO2 levels | The WHO page read was a publication-detail page; the known "not stated" refusal. Carries the "not stated" caution |
| X35 | right | **partly**: asks 1 and 2 right, the 2018 value refused | right | The known refusal on the 2018 value, a wallet-card page searched. Carries the caution |
| X19 (control) | right | right | right | |
| X36 (control) | right | right | right | |
| X41 (control) | blocked by the harness's rule | **not right under the key**: gives θJA 60 °C/W | **not right under the key**: gives 125 °C and 60 °C/W | See below |

**X41.** The frozen key says the datasheet states no thermal figure. Two answers give one, and the table is not invented: the quote
`θJA ... 60 °C/W 28-pin PDIP` is recorded `found` on a Microchip online-documentation page the harness read in full. The key was written
about the datasheet PDF; the harness found a real page outside it. Scored as the key reads (not right), reported as a key-scope question
for the owner, not decided here (compare Y13).

## Against the predictions

| | Predicted | Read |
|---|---|---|
| Targets | 6 of 6 right | 5 of 6 |
| Not expected to change | at most 1 not right | 2 of 6 (X3 once, X35 once, both their known refusals) |
| Controls | at most 1 not right | 2 of 9, plus 1 blocked (X41) |
| Cost | '$0.014' to '$0.020' | '$0.0145' |

Two of the three predictions are missed, both on questions the change does not touch. With 21 answers no rate can be read.

## What this says

- The change does what it was made for on its two sites, and the evidence is per case: H9's wrong refusal became 3 right answers; X31's
  routed reads were both right.
- It leaves the weaknesses it does not address where they were: the "not stated" refusals on pages the harness searched (X3, X35), the
  wrong instrument when the 2025 text is never fetched (X31 draw 2), and X41's key against a page outside the datasheet.
- **Merge is the owner's call.** On the letter, the rule is not met (controls). My recommendation is to merge: the two control misses are
  independent of the diff, the diff's guarded lines are all proven by breaking them, and the 2,687-test suite is green.

## Not claimed

That any rate rose. That X31 is fixed (one of three draws chose the wrong instrument). That dated legislation.gov.au addresses are covered.
