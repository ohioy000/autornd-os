# Preregistration: the field questions with the global answer model and no pins (2026-11-22)

Pushed before the spend, and alone. **The owner's word of 2026-11-22: "Yes run it with the dollar cap"**, in answer to the
finding that the second hold-out run could not separate the pins from the field profiles and the new triage model.
**The amount is the owner's: '$1.00'.** The three arms below carry caps summing to '$0.90'; with one unit past each cap
the worst case is about '$0.96'. Expected about '$0.60'.

## Why

`docs/reviews/2026-11-22-holdout2-run.md` compared the field arms N3 to N6 (field profile, new triage model, the pins
on three of them) with arm O (engineering profile, earlier triage model, no pins) and read +4, "no difference shown".
Those arms differ in three things at once, so that figure is not the pins' effect. The arm that isolates the pins is the
same questions, the same field profile and the same triage model, with **no pin**: the global answer model on the
engineering seat. Group 13 (science) already is that arm, because the science profile has no pin (N6). This run makes it
for the three groups that have one.

## What is run

The same checkout as the second run (`ccb9d9f`, code unchanged since), the owner's `.env` as it stands, one answer a
question, default workflow `answer-and-recompute`, `MEASURE_SET=professional-holdout-2`; **only `PROFILE_MODELS` is set,
to empty, in the process environment**, so nothing else differs from N3 to N5.

| Arm | Questions | Profile | Answer tier | Triage | Cap |
|---|---|---|---|---|---|
| U3 | group 10 law, Y127 to Y140 | `legal` | the global answer model (no pin) | the second triage model | '$0.30' |
| U4 | group 11 finance, Y141 to Y154 | `finance` | the global answer model (no pin) | the second triage model | '$0.30' |
| U5 | group 12 medicine, Y155 to Y168 | `medical` | the global answer model (no pin) | the second triage model | '$0.30' |

42 answers, three processes together. Processes start no unit once their own spend reached the cap. Answers not made
because of a stop are counted as not made. Blocked at no cost by the network (a 429, a 502): made again inside the cap.

## Reading

As in the second run: every answer is read against the signed keys by blind readers and by me; right when every key item
is right; traps right only if said. Answers are coded and shuffled, the codes kept back.

## The comparisons (rules written now)

Three right counts on groups 10 to 12 (42 questions): **P** the pinned arms N3 to N5 (14 + 13 + 14 = 41 right of 42
made), **U** this run, **O** the earlier line-up (13 + 13 + 13 = 39 right, 2 blocked).

- **The pins' effect: P minus U.** At least +4: the pins are **better** than the global answer model on these fields.
  Between −3 and +3: **no difference shown**. At most −4: **worse**. (The margin of 3 is the first sweep's spread between
  identical arms, 2 to 3 units on 180; 42 questions is smaller than 56, so the band is a little narrower on the upside.)
- **The profile and triage effect: U minus O**, reported with the same bands, with group 13 (N6 minus O, +2) beside it.
- Cost an answer for each arm, reported beside P and U.
- Where one side is a miss of one question, that is one unit: the per-field counts are reported as they are, with that said.

## Stop rules

A unit whose record shows a model served on the engineering seat other than the global answer model; any HTTP 404; a
`spend_guard_blind` entry; a process past its cap by more than one unit; the whole run past '$1.00'. On a stop the work
halts and is reported as read.

## Predictions

1. **P1 (P − U), n = 42.** No difference shown, about two in three; the pins better about one in five; worse about one in
   ten. The second run left 3 of 42 not right under the pins and the global model has not been seen on these three
   fields with the new triage model.
2. **P2 (U right), n = 42.** Between 37 and 41 right.
3. **P3 (cost), n = 42.** The three arms together cost between '$0.45' and '$0.80'; an answer costs '$0.012' to '$0.018'.
4. **P4 (serving), n = 42.** Every unit served on the global answer model, as set.

## Limits, stated beforehand

- One answer a question; 14 questions a field. A difference of 1 or 2 is a single question.
- The arms ran at different times from the second run's; the questions are the same and the model's replies vary run to
  run, so a repeat of one setting would differ from itself by a unit or two.
- The questions have been seen by this project's measurement once; no answer from the second run was used to write them.
