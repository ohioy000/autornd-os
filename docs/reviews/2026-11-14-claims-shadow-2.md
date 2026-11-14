# The claim check, second shadow run (2026-11-14)

Preregistered in `docs/preregistration-20261114-claims-shadow-2.md`, pushed before the run. The
counts re-derive from the traces with `docs/probes/claims_shadow_analysis.py`. Which values are
right is the hand reading below.

## The point

- **No false flag this time.** 17 claims were compared: 7 figures and 8 text claims agreed, and the
  2 wording flags were both judged the same by `same_meaning`. The first run left 7 flags on right claims.
- **But the bar that matters was not tested.** No answer repeated the "2 years of the 3-year
  period" error, so the run cannot say the check would catch it.
- **And the change aimed at that error did not take.** No unit listed the condition as a claim of
  its own. The claims step listed the period (2 years) as before.
- **The "facts, not choices" instruction did not take on Q6 either.** Its units still listed 12
  claims each, mostly parts the answer chose. The samples declined to state them, so none was
  flagged, but they cost three sample prompts each.
- **The samples were wrong together twice more,** on figures the answer had right. A unit mismatch
  kept each from being a flag.
- **The delivery did not change.**
- **Cost:** '$0.120' for 6 units, against '$0.15' expected; the five claim nodes cost '$0.042' of
  it. About '$2.09' of the owner's '$7' is now spent.

It stays in shadow. It no longer raises false alarms on this set, and it has still not shown that
it catches an error.

## What was run

- Golden IA and Q6, three repeats each, 6 units, workflow `answer-and-recompute-claims`.
- **Code:** branch `feat/20261114-claims-shadow-2` at `af0f07c`, with the owner's `.env` of the
  date. Suite before the run: 1969 passed, 1 skipped, network guard 0. Started 18:07 UTC.
- No unit failed, was blocked or left a liability.
- **Traces,** copied byte-identical, prefix `docs/traces/20261114T180715Z-claims-shadow-2-`:

| File | sha256 |
|---|---|
| `header.json` | `381ca24b524d…` (the same line-up as the first run, so the same bytes) |
| `shard-0.jsonl`, `shard-1.jsonl` (Q6, IA) | `0fd0858d2bf4…`, `8dc8ce67be4d…` |
| `phases-shard-0.jsonl`, `phases-shard-1.jsonl` | `556c5975f59c…`, `e2a15f9c1673…` |

## Unit by unit

| Unit | Listed | Kept | What the claim vote did |
|---|---|---|---|
| Q6 r1 | 12 | 12 | 4 text claims agreed (polarity, inclusive OR); 8 got no answer from any sample |
| Q6 r2 | 12 | 12 | 2 text claims agreed; 10 got no answer |
| Q6 r3 | 12 | 12 | Compared nothing: no sample answered any claim |
| IA r1 | 11 | 7 | 3 years and 2 years agreed; 2 text agreed; 2 wording flags, both judged the same |
| IA r2 | 12 | 5 | 3 years, 2 years and 24 months agreed |
| IA r3 | 10 | 6 | 3 years and 8 hours agreed; the 2 years was dropped (see below) |

## The reading

One reader, the architect. D50 asks for two readers; this is a stated departure.

**The answers.** All three IA answers quote 65.91(c)(2) rightly: "actively engaged, for at least
the 2-year period before the date he applies". All three Q6 answers give the right logic. The
screen fails Q6 r1 on the known key defect.

**Compared: 17,** all right on the reading. 7 figures and 8 text claims agreed; 2 text claims
were flagged.

**Flags: 2, both wording,** in IA r1: "14 CFR § 65.95(a)(1)" against the samples' "14 CFR 65.95",
and the fixed-base sentence with and without "reachable". `same_meaning` said yes to both, at 0.96
and 0.99. No flag was left.

**IA r3's 2 years was dropped.** The claims step wrote "at least 2 years"; the answer says "at
least the 2-year period". The free check keeps a value only if it is in the answer as written, so
it dropped the claim. The rule did what it says, and it cost the claim we most wanted.

**The samples were wrong together, twice, by the architect's memory of the rules** (not checked
against their text here):

- IA r3: the answer says Form 337 goes to the FAA within 48 hours. All three samples said 10 days.
- IA r1 and r3: the answer says two major repairs or alterations (per 90 days) for renewal. The
  samples said 5.

Hours against days, and "at least two" against 5, are not comparable to the vote, so neither was
flagged. Had the units matched, each would have been a false flag on a right answer. The same
happened once in the first run (18 months).

## The bars

| # | Bar | First run | This run |
|---|---|---|---|
| 1 | Each IA unit compares at least two figures | Missed | **Met.** 2, 3 and 2 |
| 2 | Each IA unit's claims include the two periods | Met | **Met,** as listed. In r3 the 2 years was then dropped |
| 3 | No more than 1 in 5 right figures flagged | Missed, 3 of 12 | **Met.** 0 of 7 |
| 4 | A wrong claim is flagged | Missed | **Not tested.** No answer was wrong |
| 5 | The delivery is unchanged | Met | **Met.** |
| 6 | No more than 1 in 5 right text claims left flagged | (4 of 10 by the same count) | **Met.** 0 of 10 |

## The predictions

| # | Prediction | Result |
|---|---|---|
| 1 | Q6 units list at most 6 claims each | **Wrong.** 12 each |
| 2 | Every IA unit lists the actively-engaged condition as its own claim | **Wrong.** None did |
| 3 | No design choice is flagged | **Held,** because the samples declined to state them, not because they were left out |
| 4 | A repeated "of the 3-year period" error is flagged | **Not tested.** |
| 5 | `same_meaning` judges at least 3 in 4 wording flags the same | **Held.** 2 of 2 |

## What the two runs say together

1. **What works:** the bound-word reading, `same_meaning` behind the claim vote, reading bare
   samples, and the shadow itself. False alarms went from 7 to 0 on the same six units.
2. **What a prompt did not fix:** the claims step still lists what the answer chose, and does not
   list a condition as its own claim. Two instructions, both ignored by the model on the triage
   tier.
3. **The deeper limit:** a blind sample states these facts from memory and the grounding, and on
   the less common ones (a filing deadline, a renewal count) three samples agreed on a wrong value
   three times in two runs. The answer, which had the lookup's quotes in front of it, was right
   each time. A vote of memories is a weak judge of an answer that read the source.
4. **The error we set out to catch has not been caught or tested.** It appeared once in 6 IA
   answers over the two runs, and the claim lost it.

## What is next

This is the owner's choice; nothing is changed until then.

- **(a) Check each claim against a found quote,** the candidate passed over on 2026-11-14. Point 3
  argues for it: the page is a better judge than three memories. It can reuse the claims step
  built here, and only works where a lookup found the passage.
- **(b) Keep going with the vote:** a stronger model for the claims step, to get conditions and
  drop choices. More cost per run, and point 3 still stands.
- **(c) Stop here** and leave the claim check in shadow as built.

The architect recommends (a), in shadow, built on this claims step.
