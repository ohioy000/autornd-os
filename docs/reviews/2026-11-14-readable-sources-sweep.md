# The readable-sources sweep (2026-11-14)

Preregistered in `docs/preregistration-20261114-readable-sources-sweep.md`, with an addendum
written before the re-check. The figures re-derive with
`docs/probes/readable_sources_analysis.py docs/traces`.

## The point

- **Telling the search which sites refuse us works for what it was built for.** Quotes on pages
  that could not be read fell from 9 of 73 to 3 of 64, and in the re-check the search stopped
  quoting osha.gov once it had refused twice. The five rule questions were answered as well as
  before: 19 of 20 with it, 19 of 20 without.
- **Withholding an answer nothing verified did no harm on the rule questions** (20 of 20) and
  was rare: 8 lookup answers withheld in 24 runs, and in only 1 run was everything withheld.
  That one answer was right. So ending a run when nothing is verified would have thrown away a
  right answer the one time it applied.
- **Neither setting fixes the owner's inspection-authorization request, and neither harms it.**
  Across today's 28 answers to it, 5 state the two-year condition wrongly. All 5 are in runs
  whose lookup did not find that sentence on a page. In the 9 runs where it was found, all 9
  answers are right.
- **A correction to what the architect told the owner mid-sweep.** The first reading blamed the
  wrong answers on ecfr.gov being listed after one challenge page. The re-check does not support
  that: with nothing listed, 2 of 8 answers were still wrong. Listing a site on one refusal was
  a flaw and is repaired, but it was not shown to be the cause.
- **Cost:** '$1.444' for 88 answers, under the owner's '$1.75'. About '$4.85' of the owner's
  '$7' is now spent.

## What was run

- **The sweep:** three arms, six questions, four repeats, 72 full answers through the default
  workflow, '$1.160'. `now`: both settings off. `avoid`: `lookup_avoid_unreadable` on.
  `avoid_withhold`: that and `lookup_withhold_unverified` on.
- **The re-check,** `avoid` with the repair: the inspection-authorization request 8 times, Q17
  and Q22 4 times each, '$0.284'.
- **Code:** this branch on main `4819fa0`; the re-check at `d4c65c5`. The owner's `.env` of the
  date.
- **Traces:** 30 files copied byte-identical, `docs/traces/20261115T-readable-*`: for each arm
  the answers, the exported run rows and the header.

## The figures

| | `now` | `avoid` | `avoid_withhold` |
|---|---|---|---|
| Answers passing the screen, of 24 | 23 | 21 | 21 |
| The five rule questions, of 20 | 19 | 19 | 20 |
| The inspection-authorization request, of 4 | 4 | 2 | 1 |
| Quotes on pages not read | 9 of 73 | 3 of 64 | 5 of 63 |
| of those, on osha.gov | 9 | 2 | 3 |
| Answers with at least one quote found on its page | 23 | 21 | 23 |
| Lookup answers withheld | – | – | 8 |
| Runs with every lookup answer withheld | – | – | 1, and it passed |
| Cost | '$0.367' | '$0.413' | '$0.380' |

The screen is not the result (D50). The answers on which the arms differ are the
inspection-authorization ones, and they were read by hand; see below. One reader.

## The bars

| | Stated | Result |
|---|---|---|
| Bar 1 | `avoid` has at most half of `now`'s share of unread quotes | **Met.** 4.7 percent against 12.3 |
| Bar 2 | `avoid` passes at most 1 fewer of 24 | **Missed by the count** (2 fewer), all on one request; see the reading |
| Bar 3 | `avoid_withhold` passes at most 1 fewer of 24 | **Missed by the count** (2 fewer), the same request |
| Bar 4 | neither costs over 25 percent more | **Met.** 12.6 and 3.5 percent |
| Re-check | 7 of 8 inspection-authorization answers right; Q17 and Q22 pass 7 of 8 | **Missed** (6 of 8) and **met** (8 of 8) |

| Prediction | Result |
|---|---|
| 1. `now` has 25 to 40 percent of quotes unread | **Wrong.** 12 percent. These questions name their edition, and the search went to eCFR and govinfo more than in the vague tests |
| 2. Bar 1 is met | **Held** |
| 3. Bar 2 is met | **Wrong by the count** |
| 4. Bar 3 is missed or met narrowly | **Held, for another reason than given.** Q12 was 4 of 4 with withholding |
| 5. A shard's first question is not helped in its first round | **Held.** In the re-check the first two questions quoted osha.gov, the next six did not |

## The inspection-authorization answers, read

The condition is 14 CFR 65.91(c)(2): actively engaged for at least the 2-year period before
applying. The wrong answers say 3 years, or "2 of the last 3 years".

| Runs today | Answers | State it wrongly | Lookup found the sentence on a page |
|---|---|---|---|
| `now`, sweep | 4 | 0 | 2 |
| `now`, the typed-queries sweep earlier | 4 | 0 | 2 |
| typed queries, earlier | 4 | 0 | 4 |
| `avoid` | 4 | 2 | 0 |
| `avoid_withhold` | 4 | 1 | 0 |
| re-check (`avoid`, repaired; nothing was listed) | 8 | 2 | 1 |
| **All** | **28** | **5** | **9** |

- Every one of the 5 wrong answers came from a run whose lookup had not found the sentence.
- Every answer from a run that had found it is right: 9 of 9 today, and 6 of 6 in the records
  read on 2026-11-14.
- Without the sentence the answer is right about three times in four: 14 of 19 today.
- Three more answers failed the screen without stating the condition wrongly: they returned the
  holder's authority as the answer, or cited the right words under the wrong paragraph.

In the re-check no site was listed during the inspection-authorization runs: ecfr.gov had been
read, so its one challenge page did not count. Those 8 runs were in effect the code as it is,
and 2 were wrong. So the gap between `now` (0 of 8 today) and the other arms (5 of 16) is not
shown to be the settings. It may be chance: the lookup found the sentence in 4 of `now`'s 8 runs
and 1 of the others' 16.

## The flaw found and repaired

One refusal listed a site for the rest of the process. On 2026-11-14 ecfr.gov, read all day,
served one challenge page, most likely because nine processes were fetching it at once, and was
listed. **Repair:** a site is listed after two refusals, and never once it has been read in the
process. Two tests, break-proved. In the re-check ecfr.gov served one more challenge page and
was not listed.

## The architect's thoughts

1. **`lookup_avoid_unreadable`: sound, small.** It does what was asked: the refusing site is
   flagged and the search finds a readable copy. It costs about an eighth more. By the count it
   missed its bar, on a request it was shown not to touch. Switching it on is the owner's call;
   the architect would switch it on.
2. **`lookup_withhold_unverified`: not yet.** It did no harm here, but an answer with no found
   passage is right about three times in four, and withholding takes that from the phases with
   nothing to put in its place. It is worth having only once the lookup finds its passage more
   often.
3. **Ending the run when nothing is verified: no.** It would have applied once in 24 runs and
   that answer was right.
4. **The lever that matters is whether the lookup finds the sentence.** 15 of 15 right with it,
   across two days. That is the one result every test today agrees on. The typed queries found
   it in 4 of 4 full answers and 8 of 10 lookups on this request, against 7 of 17 as the code
   is. The narrow build of them, used only when the scoping call says a request has more than
   one reading, is the next thing worth a test: 12 answers each way on this request, about
   '$0.50'.
5. **What a check after the answer could add.** In all 5 wrong answers the lookup had found
   other passages, and the delivery's cautions did not single the wrong figure out. A check of
   the answer's figures against the quotes found would not have caught these either: the right
   sentence was not among them.
