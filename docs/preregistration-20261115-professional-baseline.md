# Preregistration: the professional set's baseline (2026-11-15)

Written and pushed before the run. The owner's word of 2026-11-15: "Looks good run it".

## What is run

- The professional set, version professional-1, frozen on the owner's approval:
  `evals/professional/questions.json`, sha256 `2e41878c1e06…`. Fifteen lookup questions in
  fifteen fields.
- Main as it stands, through the default workflow (`answer-and-recompute`), by
  `docs/probes/short_workflows_measurement.py` with `MEASURE_SET=professional`. One arm. Site
  flagging is on, as it is on main since #261.
- **Three answers to each question: 45 answers,** in three processes.
- **Cost.** About '$0.90' expected. Each process stops at '$0.32', '$0.96' in all. About '$4.85'
  of the owner's '$7' is spent before it.

## What is measured

This is a baseline, so there are no bars: it says where main stands, and the next fix is chosen
from it.

1. **Right answers.** Each answer is read by hand against its key: every key item stated
   rightly, or which one is not. A free check of the key's figures in the answer's text points
   the reading; it is not the result (D50).
2. **Whether the lookup found the governing sentence.** A quote found on its page that holds the
   key's passage, or its figures.
3. **Where a passage was lost,** when it was: the search did not quote it, the page could not be
   read, or the quote was not matched.
4. **What the delivery said:** the cautions on each answer, and whether the recompute vote
   compared anything.
5. **Cost and time** for each answer.

## Predictions

1. At least 40 of 45 answers state every key item rightly. These are clear questions that name
   their rule.
2. Where an answer is wrong, its lookup did not find the governing sentence.
3. The lookup finds the governing sentence in at least 35 of 45 runs.
4. P8 is the question that quotes osha.gov; with site flagging on, at most 1 of its 3 runs ends
   with no quote found.
5. The recompute vote compares nothing on at least 5 of the 15 questions.
6. P11 or P14 draws an answer from an older edition at least once.

## Limits, stated beforehand

- Three answers a question. One question's figure means little; the set's does.
- One reader, the architect. D50 asks for two; a stated departure.
- Eleven of the fifteen sources are on one site.
