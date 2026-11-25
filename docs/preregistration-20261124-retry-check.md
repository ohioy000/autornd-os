# Preregistration: the 504 retry, on the units that the provider failed (2026-11-24)

Pushed alone, before any spend of this run. No answer of this run exists. The owner said "Go for it" on 2026-11-24 to a paid check of
the retry, after the amount was stated ('$0.26' for 16 answers).

## The question

The first hold-out asked again (`docs/reviews/2026-11-24-first-holdout-same-set.md`) left 16 of its 126 units with no answer because the
answer model's provider failed: 13 gateway timeouts (504) and 3 upstream rate limits (429). The branch `fix/20261124-retry-504` (c634f87)
retries a 504 twice (2 s, 4 s). **Does the harness now deliver an answer for those 16 units, and does the retry fire?**

## What is run

The 16 questions whose unit ended on a provider error, **one answer each**: X4 X5 X9 X13 X15 X16 X17 X18 X19 X21 X24 X28 X30 X32 X38 X41.
(X31's draw 2 was blocked by the harness's own rule and is not re-asked.) The tree is `957bc08`, the tree that made the first run, with the
retry applied on top (`git diff 1dc134a c634f87 -- autornd/routing/openrouter.py`), the owner's `.env` unchanged (reader tier on, no pins),
profile `engineering`, workflow `answer-and-recompute`, `MEASURE_SET=professional-holdout`, one invocation.

## Money

Stated before the spend: expected **'$0.26'** (16 answers at the run's mean of '$0.016'); invocation cap 16 x '$0.022' rounded to
**'$0.36'**; **ceiling for the run '$0.45'**. The key had '$9.6' left. Stops: any 404, 402, 403 or key-limit message; a `spend_guard_blind`
entry; a model on the answer seat other than the global answer model or on the triage seat other than the second triage model; the run's
spend past '$0.45'.

## How it is read

The answers join the first run's 109 under new codes, are read blind by one reader, and by me on every not-right answer and on 4 right ones
drawn by seed, before the cautions are looked at. Not right is `wrong` or `partly`. The retry is read from the run's log (the line
"504 for ... retrying") and, where the records carry it, the retry count by class.

## Predictions (written before any answer is read)

* **Delivered: at least 14 of 16.** The provider's failures came in a window; a quiet hour should deliver nearly all.
* **The retry fires on 0 to 2 of the 16.** If the provider is healthy now, no 504 occurs and **the retry is not exercised**: that outcome
  proves only that the new code breaks nothing, not that it rescues a call, and the report says so in those words.
* **Right of those delivered: at least 13 of 16** (the first run's rate on delivered answers was 95 percent).

## What decides, and what does not

* **The retry is said to have rescued a call only if the log shows a 504 retried and that unit delivered.** A delivery with no retry in
  the log is the provider recovering, not the retry.
* **If a 504 retried and still failed after the third attempt,** the 6 s of waiting is too short for this condition, the review says so, and a
  longer wait is a proposal for the owner, not made here.
* **Reported as it reads,** whether it meets the predictions or not.

## Limits

* 16 units, one answer each: no rate can be read from it. A rescue is a count of cases.
* The condition (a provider window) cannot be made to happen. If it does not recur, the retry stays unmeasured and is still in the code,
  tested end to end against a simulated 504.
