# Preregistration: the claim check, second shadow run (2026-11-14)

This is written and committed before the run. A wrong prediction will be reported as wrong. The
owner approved the three changes and the run on 2026-11-14 ("Go for all 3").

## Why

The first shadow run met 2 of its 5 bars (`docs/reviews/2026-11-14-claims-shadow.md`). It missed
the one real error, flagged design choices, and could not compare a value written as "at least 3
years". This run repeats it after the changes, on the same six units and the same bars, so the two
can be compared.

## What changed since the first run

1. **The claims call lists facts, not choices.** It leaves out what the answer chose or designed.
2. **A condition is a claim of its own.** When a figure holds only with a condition the answer
   attaches, such as the period it must fall within, the condition is listed in the answer's words.
   This is aimed at the missed error: "2 years of the 3-year period".
3. **A number behind a bounding word is that number.** "at least 3 years" is 3 years. Free.
4. **`same_meaning` stands behind the claim vote.** A claim flagged on text is put to the decision
   model with the claim's name and both wordings. Stored under its own keys; the delivery does not
   read them.
5. **A bare-result sample is read.** This one is live: it changes the vote on asks too. Replayed
   free over the 130 recorded units of 2026-11-13 and 14, no stored vote changes its result
   (`docs/probes/bare_sample_replay.py`).

The limit stays at 12 claims. The first run's unanswered claims were design choices, which change 1
removes; the limit is judged again on this run.

Everything else is as before: recorded only, no caution shown, nothing blocks, routes or revises.

## What is run

- Golden IA and Q6, three repeats each, 6 units, as in the first run.
- `MEASURE_SET=golden`, `MEASURE_WORKFLOWS=answer-and-recompute-claims`, 2 shards, each stopping at
  '$0.10'.
- **Code:** branch `feat/20261114-claims-shadow-2` at the commit that adds this file.
- **Cost:** the first run cost '$0.147'. About '$0.15' expected; the caps stop it under '$0.40'.
- **Budget:** inside the owner's '$7'. About '$1.97' of it is spent.

## How it is read

As in the first run: one reader, the architect (a D50 departure), every answer against the key,
every claim against the answer, every flag judged. A flag counts only if it is left after
`same_meaning`: a text flag the decision model judged the same is not a flag.

## The bars, unchanged, and one added

1. Each IA unit compares at least two figures.
2. Each IA unit's claims include the two periods.
3. No more than 1 in 5 right figures is flagged.
4. A wrong claim is flagged. If no answer is wrong, this is not tested, and the report says so.
5. The delivery is unchanged.
6. **Added:** no more than 1 in 5 right text claims is left flagged after `same_meaning`.

## Predictions

1. Q6 units list fewer claims than before (12, 12, 13): at most 6 each.
2. Every IA unit lists the actively-engaged condition as a claim of its own.
3. No design choice is flagged.
4. If an IA answer repeats the "of the 3-year period" error, the condition claim is flagged and
   stays flagged after `same_meaning`.
5. `same_meaning` judges at least 3 in 4 wording flags the same.
