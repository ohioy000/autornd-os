# The second look and the computed-figure instruction, tested 2026-11-25

Preregistered in `docs/preregistration-20261124-second-look-and-compute.md` (38685b8, corrected in ff26c88), pushed before the spend. The tree is
`feat/20261124-second-look` at `bfa09d3`. '$0.47' spent of a ceiling of '$0.90' (27 units, '$0.017' a unit). Files and sha256:
`docs/traces/20261125T-second-look-MANIFEST.sha256`.

## The point

- **The preregistered rule for merging is not met, and no hold condition was triggered.** Targets: 3 not-right of 15 against a baseline of 3 (the
  bar was fewer than 3). Controls: 12 of 12 right (the bar was at most 1 not right).
- **Neither repair is shown to help, and neither is shown to harm.** The questions the repairs were for moved both ways by draw: X35 3 of 3 right
  (baseline 2 of 3) and X3 3 of 3 right (baseline 2 of 3), X26 2 of 3 (the same), X31 now 0 of 2 delivered (baseline 2 of 2).
- **The second look fired on 6 of 27 units** (X35 once, X18 twice, X19 twice, X41 once), and every one of those 6 answers was right. It did not
  fire on X31 or X26. X35's wrong draw of the earlier run is not reproduced here, and in its other two draws the look did not fire, so the repair
  is not what made X35 right in this run's draws 2 and 3; draw 1, where it fired, is right.
- **X31's two wrong answers are the known tiny-page weakness, not the repairs.** The 2025 licence page the lookup read is 1,770 characters (a
  landing page with no text), and the "EIRP and PSD not stated" claims stand on proofs searched on it and on its older versions (1,770 to
  2,081 characters). The shipped caution now prints that size ("the largest page searched had ... characters"); a reader sees 17,638 or 28,861,
  which is the largest page, not the right one. X31 is a flaky question: right, blocked, right in one run and blocked, wrong, wrong in another.
- **X26 is still wrong once, with a different error:** its i64 maximum is given as 2^37 - 1 pages, the JS embedding cap, with 2^48 only as an
  alternative. Not a "not stated" refusal, and the instruction about computing does not address it.

## The numbers

| | Baseline (first hold-out re-run) | This run |
|---|---|---|
| X26 (computed figure) | right, right, wrong | wrong, right, right |
| X35 (page never fetched) | right, right, wrong | right, right, right |
| X3 (near-empty PDF) | wrong, right, right | right, right, right |
| X31 (tiny page) | right, blocked, right | blocked, wrong, wrong |
| X18 (computed control) | right, right, no answer | right, right, right |
| Controls X19, X36, X40, X41 | right in every delivered draw | right in all 12 |
| Not right, 15 targets | 3 wrong and 1 block | 3 wrong and 1 block |

## What it says

- **Do not claim the repairs work.** The preregistered bar was not met and the draws are too few. The second look is cheap (6 of 27 units paid
  for it, nothing wrong came of it) but unproven; the computed-figure sentence did not stop X26's different error.
- **What is left on X31 is real:** a proof made on a page that holds no text. The cut of 200 characters does not catch a 1,770-character landing
  page. A site whose text is rendered by script (legislation.gov.au `/text`) needs the fetch to take the original PDF, or the proof to refuse a
  page that is a small fraction of its siblings'. That is a proposal, not made here.
- **Merge:** by the rule written beforehand, hold both repairs. They are on a branch and not merged.
