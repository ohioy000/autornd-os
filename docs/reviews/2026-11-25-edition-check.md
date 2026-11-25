# The edition check with the second look, on X35 and its controls, 2026-11-25

Preregistered in `docs/preregistration-20261125-edition-check.md` (4077a21), pushed alone before the spend. Tree `fa77041`
(`feat/20261125-edition-check`: main `300d12a`, the second look, the edition check). **'$0.26' of a ceiling of '$0.40'** for 15 answers
('$0.0175' an answer); no provider error, no spend-guard entry. Files and sha256: `docs/traces/20261125T-edition-check-MANIFEST.sha256`.
Read by the executor alone against the key (the blind reader skipped again, said in the preregistration).

## The point

- **The edition check did what it was made for, and the second look never ran.** In none of the three X35 draws was a proof of absence made
  for the 2018 ask on a 2022-only page (before: such proofs sat behind the wrong refusals). No answer called the 2018 value not stated.
- **The preregistered "shown to work" rule is not met:** the 2018 value was given in 2 of 3 draws (met), but **the second look fired in 0
  of 3** (predicted at least 2): every document of every unit carries `request: 1`.
- **Nothing that was right was lost to a dropped proof.** X19 and X36 name no year in their requests, so the check could not touch them, and
  it did not: their two blocks (below) have another cause.

## Reading

| Question | Draw 1 | Draw 2 | Draw 3 |
|---|---|---|---|
| X35 (target) | **partly**: the 2018 value 10 973 731.568 160 is right, its uncertainty is given as (12), the 2022 one; the key has (21). No page of the run printed the 2018 value (sourced to "an archived table") | blocked by the harness: ask 3 claimed not printed and no proof is allowed | right: 2018 value and (21) from `all_2018.pdf` |
| X38 | right | right | right |
| X19 | right | right | blocked |
| X36 | right | blocked | right |
| X41 | figure from a real Microchip page (not right under the frozen key; see the page-quality review) | right: none stated | right: none stated |

X19 draw 3 and X36 draw 2: blocked on a "not stated" claim with no proof. X19's third draw had no proof for ask 1 (a page that names the words
vetoes), X36's drew none at all. Neither request names a year, so the edition check returned nothing for them. They are the existing
"no proof, no claim" rule, which had not blocked either question in the 12 draws before this run.

## Why the second look did not fire

For X35's blocked draw (ask 3) there were five pages read in full and no proof for the ask. `_asks_on_no_page` needs every page read to be
a proof or a wrong-edition page; one page that merely contains one of the three search words (a version-history page that names the 2018
values) is neither, so the trigger stays off. This is the design of the earlier ruling (any one word present vetoes a proof), carried
into the trigger. It means the second look does not fire on the case it was written for when a page mentions the thing without printing it.
Not changed; recorded as the next question.

## Against the predictions

| | Predicted | Read |
|---|---|---|
| X35 | 2018 value in all 3; second look in at least 2 | value in 2 (one with the wrong uncertainty); second look 0 |
| X38, X19, X36 | 9 of 9 right | 7 right, 2 blocked, 0 wrong |
| X41 | unchanged | one figure from the real page, two none stated |
| Cost | '$0.016' to '$0.022' | '$0.0175' |

## What this says

- The edition check is a safe narrow repair: it removes proofs on pages of another edition, never fired on a control, and turned what would
  have been a wrong refusal into a block or a grounded answer. It did not make X35 reliably right.
- The second look is **unproven**: it has now run on 42 units in two tests and fired on X35 zero times in the one run where it was meant to.
- Merge is the owner's call. My recommendation: merge the edition check. The second look rides along on this branch; it is inert on X35 and
  was held earlier for regressing X31 on landing pages, which the page-quality branch addresses; merge that branch first, then this one.

## Not claimed

That X35 is fixed (one draw partly, one blocked). That the second look helps. A rate (15 answers).
