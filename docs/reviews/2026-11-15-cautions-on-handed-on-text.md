# The cautions, rebuilt around the text the harness hands on (2026-11-15)

Step 1 of the plan the owner approved in `docs/carryover-2026-11-15.md`. Free code, no paid
run. Proved on the recorded runs with `docs/probes/handed_on_text_replay.py`.

## The point

- **Right answers come clean far more often.** With the lookup that reads the documents, 30 of
  62 harder-set answers now carry no caution. Before, none did.
- **No recorded wrong answer carries a "verified" line.**
- **A new caution says when two pages disagree.** It fires 5 times in 283 answers, and each time
  the pages do give different figures for one thing. It is the first caution that points at the
  flight-attendant mistake.
- **It does not catch every wrong answer, and it cannot.** Two of the three wrong
  flight-attendant answers now carry no caution at all. Every page they were handed said 9
  hours. A check against the text handed on cannot see that the text is the wrong rule or out of
  date. That is the finding half, step 3.
- **Most cautions left are the vote's.** 129 of the 203 cautions on the 283 answers. This step
  did not touch them.

## What changed

| Before | Now |
|---|---|
| "1 of 2 quoted passages were found…", "2 more quoted passages were on a page that could not be read…" | Dropped. Quotes are no longer counted |
| "…passages do not state an answer to the question they were quoted for" | Dropped. The label on the quote stays in the record |
| A found passage was taken over a vote that disagreed | Removed. A vote that disagrees is always said |
| Nothing said which figure was unchecked | "The answer gives 11 hours for ask 1, and that figure is in none of the passages found on their pages." |
| Nothing said when sources disagreed | "Two pages handed on give different figures for the same thing: 10 on … and 9 on … The first reads: …" The ask gets no "verified" line |
| A lookup that quoted nothing was said to have quoted unreadable pages | Three wordings: it quoted no passage; no page it named could be read; none of its passages was found on its page |
| A quote with carets ("µg/m^3^") was not found | Carets are read as marks, like tildes |
| The record kept 600 characters of each quote | A longer passage is also kept whole, as `whole`. `text` is unchanged |

The "verified" line of #264 is kept as it was, and so is the rule that a vote which could not
compare an ask is not mentioned when that ask is verified.

## How the two new cautions decide

**A figure on no page.** Only for an answer whose value is one number. The number is looked for
by its value in every passage found on its page, with commas dropped and a number written as a
word counted ("nine"). If it is nowhere, the caution names it. A citation such as
"14 CFR 65.91(c)(1)-(5)" is not read: on the recorded runs every such caution stood beside a
right answer.

A figure can be on the page and still not "verified": a single digit needs its word right beside
it ("8 cumulative hours" does not verify 8 hours). Such a figure gets neither line.

**Two pages differ.** Two sentences from different pages count as the same thing when 80 percent
of their words agree in order, they state as many numbers, exactly one number differs, and the
three words before it and two after it are the same. Paragraph labels, section numbers and
amendment marks are not numbers. The settings were read off the recorded runs and the comment
beside them says how:

| Setting | Cautions in 283 answers | |
|---|---|---|
| Word agreement alone, 0.8 | 9 | 4 are not one thing: two power limits of one radio rule (3), two test methods (1) |
| With the words beside the figure | **5** | all one thing |
| The same at 0.9 | 3 | loses the flight-attendant pair, the case this is for |
| The same at 0.7 | 12 | 7 more, none one thing |

The 5: the flight attendant's 10 hours beside 9 (twice; once on a wrong answer, once on a right
one), the ozone standard's 0.070 beside its predecessor's 0.075 (twice), a driver's 10 hours off
duty beside a sister rule's 8.

## The replay

Every completed answer of the day's recorded runs, rebuilt with this tree's code.

| Run | Answers | No caution before | No caution now | Cautions before | Cautions now |
|---|---|---|---|---|---|
| Harder set, first run | 51 | 5 | **18** | 85 | 41 |
| Harder set, lookup as it is | 64 | 5 | **28** | 104 | 48 |
| Harder set, reads the documents | 62 | 0 | **30** | 121 | 39 |
| First set, baseline | 45 | – | 21 | – | 32 |
| First set, reads the documents | 45 | – | 19 | – | 28 |
| Inspection authorization, as it is | 8 | – | 0 | – | 9 |
| Inspection authorization, reads the documents | 8 | – | 2 | – | 6 |

"Before" is from `2026-11-15-professional-hard-run.md` and `2026-11-15-lookup-reads-documents.md`.
A dash means no earlier figure was recorded for that run.

The cautions now, over all 283 answers:

| Caution | Count |
|---|---|
| The vote compared nothing | 71 |
| A figure is on no page | 41 |
| The vote worded an ask differently, and a decision model judged it the same | 31 |
| A lookup ran and nothing was checked (three wordings) | 28 |
| The vote reached no majority | 10 |
| The vote could not compare an ask | 10 |
| The vote disagrees | 7 |
| Two pages differ | 5 |

**A lower bound for the lookup that reads the documents.** The recorded runs kept 600 characters
of each excerpt. A figure past that point reads here as on no page. Live runs keep the whole
excerpt from now on, so fewer of the 41 will fire.

## The recorded wrong answers

| Wrong answer | "Verified" line | A caution that points at it |
|---|---|---|
| Flight attendant, run 3 (9 hours; pages said 10 and 9) | no | **yes, two:** the pages differ, and the vote disagrees |
| Flight attendant, run 1 (the only page found said "nine") | no | **no.** No caution at all |
| Flight attendant, run 2 (two sister rules said 9) | no | **no.** No caution at all |
| Inspection authorization, reads the documents (run 6: sections 65.83 and 65.87 were fetched, not 65.91) | no | no. Only "the vote compared nothing" |
| Inspection authorization, as it is (2 wrong of 8) | no, on any of the 8 | no |

- The plan hoped each wrong answer would carry a pointing caution. **1 of 3 flight-attendant
  answers does, as before.** Runs 1 and 2 used to carry cautions about quotes in general, which
  pointed at nothing. Now they carry none. That is more honest and it is not better.
- The inspection-authorization answers are sentences, not figures. Neither new caution reads
  them.

## Proof

- 15 new tests; 2039 in all (2038 passed, 1 skipped), network guard 0.
- 17 lines broken one at a time; each break failed its test.

## What the architect advises next

1. **Step 2 as planned:** switch `lookup_reads_documents` on by default.
2. **The owner's ruling, before or with step 2:** the vote's "compared nothing" caution stands
   beside 71 of 283 answers, nearly all right. It is the largest caution left. Should it be said
   only when the answer's figure is also on no page?
3. **Step 3 carries the weight for wrong answers.** Preferring the rule's own current text is
   what would have helped runs 1 and 2.

## Added the same day: the vote's "compared nothing" caution

The owner ruled on point 2 above: yes, if the architect believes it is the best way. The
architect does. The caution now stands only beside an answer nothing else checked: no passage
was found on any page, or a figure of the answer is on no page read.

| On the 283 recorded answers | Before the ruling | After |
|---|---|---|
| "The vote compared nothing" | 71 | 16 |
| All cautions | 203 | 148 |
| Harder set, reads the documents: answers with no caution | 30 of 62 | 39 of 62 |

**What it costs, said plainly:** the one wrong inspection-authorization answer with the new
lookup carried only this caution, and now carries none. It was a caution about a vote, on an
answer in words that the vote could not have compared. It did not point at the mistake.
