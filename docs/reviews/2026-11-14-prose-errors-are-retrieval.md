# The prose errors are a retrieval problem (2026-11-14)

A free reading of the committed traces, done before the paid replay the owner approved ("Go full
permission"). The replay was not run: the stop rule set beforehand was met without it. Nothing was
spent. The figures re-derive with `docs/probes/ia_quotes_vs_errors.py`.

## The point

- **Every wrong answer to the inspection-authorization question lacked the passage.** In all 4
  recorded wrong answers, the lookup never fetched the sentence of 14 CFR 65.91(c)(2) that states
  the 2-year period.
- **Every answer that had the passage was right:** 6 of 6.
- **So a check of claims against found quotes cannot catch these errors.** There is no passage to
  check them against. It is not built.
- **The work moves to retrieval:** why the lookup fetched the wrong section.

## The table

12 completed IA answers are on record, from four runs of 2026-11-13 and 14.

| | Passage among the found quotes | Passage not found |
|---|---|---|
| Answer right on the period | 6 | 2 |
| Answer wrong on the period | 0 | 4 |

The 2 answers that were right without the passage wrote it from the model's memory. The 4 wrong
ones did the same and got it wrong: "3-year period" twice, "2 years of the 3-year period" once,
and once no period at all.

## What the lookups fetched in the wrong runs

- 14 CFR 65.95, the privileges of an authorization holder, in three of the four.
- FAA guides and advisory circulars on major alterations.
- Never 65.91, which holds the eligibility conditions the request asks for ("qualifications").

Their grounding questions were about scope, such as whether "inspection auth" means the Part 65
authorization. None asked what the eligibility conditions are. In the runs that were right, the
lookup quoted 65.91(c) whole.

## What this settles

The stop rule, told to the owner before this reading: build the claim-against-quote check only if
it could flag at least 3 of the 4 recorded wrong answers; otherwise stop, and move to retrieval if
the passage was never fetched. It can flag 0 of 4. Stopped.

With the two shadow runs of the claim check (`docs/reviews/2026-11-14-claims-shadow.md` and
`-2.md`), the day's finding is one sentence: on this question the answer is as good as what the
lookup fetched, and no check after the answer made up for a passage that was not there.

## What is next, for the owner

One question is on record and small: 12 answers to one request. Before any change:

1. **Check it holds elsewhere, free.** Read the other recorded lookup answers (tier-2's five lookup
   questions, 40 units) the same way: was the passage that holds the answer among the quotes?
2. **Then look at what the lookup is asked.** The grounding questions come from a model's reading
   of the request. In the wrong runs they asked about scope and not about the thing requested. A
   change there alters which sources are fetched, so it is a ruling.

The claim check stays in shadow as built, off the default workflow, and is not run again without
the owner's word.
