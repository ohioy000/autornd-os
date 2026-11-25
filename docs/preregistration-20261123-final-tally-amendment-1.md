# Amendment 1 to the final tally's preregistration: the units the key's limit stopped are made now (2026-11-23)

Pushed before the spend, and alone, with the launcher's resume mode in the commit before it (the mode carries no design: it reads
which units were stopped and plans them). The preregistration itself, `docs/preregistration-20261123-final-tally.md`, is not edited.

## What happened

The tally started at 10:38 UTC (twelve lanes, 18 invocations of the runner) and every invocation had exited by 11:00 UTC. The
provider's key reached its total limit ('$50.00'), and every request after that got HTTP 403 "Key limit exceeded (total limit)",
instantly and at no cost. Of the 367 answers the preregistration planned, **82 were made** (79 of the tally and 3 of the probe),
**286 were stopped by the limit** (8 of them had spent between '$0.0003' and '$0.0086' before the 403) and **2 ended blocked on a
provider failure** of the triage model (T4-02 and T4-03: no text, `finish_reason=length`). The tally's own spend is **'$0.9093'**
(including '$0.0344' for the three probes).

The preregistration's stop rule names an HTTP 402 or an out-of-credit message; a 403 for a total key limit means the same and was
read as that stop: the work halted and was reported to the owner as read, with nothing spent past the limit. My watcher's pattern
did not name the 403 wording, so it did not stop the lanes by itself; they ran their questions into the refusal and exited, which
cost nothing. The watcher now names it.

## What the owner did

The owner raised the key's total limit to '$58.00' (read from the provider's key endpoint at 11:17 UTC on 2026-11-23: limit 58,
usage '$50.03', remaining '$7.97'; no key value was printed). The owner's instruction of the same day stands: "Yes run the full
test now a compilation of all the questions we have created to get a final tally what ever amount necessary".

## What is decided (mine, stated before any spend)

- **The 286 stopped units are made now, once each,** from the same tree (`ccb9d9f`), the same `.env`, profiles and workflow as the
  first run, in the same lane structure (18 invocations, 12 lanes), into `/home/jb/final-runs/resume1/` (outside any git tree), by
  `docs/probes/final_tally_launch.py resume` (the plan is `resume-plan`: 286 units, 18 invocations, caps summing to '$6.31').
- **The one departure from the preregistration's text:** "answers not made because a cap or a stop was reached are counted as
  not made and are not re-run here" is waived for this stop, because the stop was the key's funds and not the harness, and the
  funds are now provided. The 79 answers already made are not made again. The 2 tier-4 units that ended blocked on a provider
  failure stay blocked answers (bar 7), as the preregistration treats a failure that is not the network's. The single further
  invocation for blocks by the network (a 429, a 502) stands for the resumed units; none of the first run's blocks was one.
- **Nothing else changes:** the questions, the profiles, the one-answer rule, the bars, the predictions and how an answer is read
  are as written. An answer's question has one answer in the tally, from the first run or from this one, and the report says
  which.

## Money

The ceiling for the whole tally stays **'$9.00'**, counted over both runs; '$0.91' of it is spent. The resumed units are expected
to cost about '$3.8' (243 answers at '$0.0135' and the 43 of arm E at '$0.0125'). Caps: each resumed invocation its units times
'$0.022' with a floor of '$0.10'; the tier-4 set at '$0.030' a unit, because the probe's tier-4 answer cost '$0.0209' with its pages in
the message and a cap of '$0.022' would bind on it; arm E at '$0.38' for each of its two processes, so that the small test as a
whole stays inside the owner's '$1.00' ('$0.143' spent, plus two of '$0.38', plus at most a unit past each cap). The caps sum to
'$6.31'; with one unit past each of the 18 caps the worst case is about '$6.85', or about '$7.8' with what is spent: under '$9.00',
and under the key's remaining '$7.97'.

## Stops

The first run's, with HTTP 403 named beside 402: any 404; any 402, 403 or out-of-credit message; a `spend_guard_blind` entry;
a model served on the engineering seat other than the global answer model, a pinned model anywhere, or any call on a reader tier;
the sum of spends past '$9.00'; a process past its cap by more than one unit. On a stop the work halts and is reported as read.

## How it is read, and what is added to the limits

Unchanged, and: **the 79 answers and the 286 are made hours apart**, so a provider's condition may differ between them and the
report says which run made each answer. The caution branch `fix/20261123-caution-flaw`, head `b66498e`, is committed and pushed
**before** any resumed answer exists and before any answer of the tally is read (its review, section 7); the only thing read from
the tally so far is a count of stored lookup records, no answer text and no label.
