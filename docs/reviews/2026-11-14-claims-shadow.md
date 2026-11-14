# The claim check, first shadow run (2026-11-14)

Preregistered in `docs/preregistration-20261114-claims-shadow.md`, pushed before the run. The
counts re-derive from the traces with `docs/probes/claims_shadow_analysis.py`. Which values are
right is the hand reading below.

## The point

- **The claim check works as a machine and has not yet proved its value.** It met 2 of its 5 bars.
- **It compares where the vote on asks compared nothing.** On IA r2 it checked five figures, among
  them the 3 years and the 2 years, and they agreed.
- **It missed the one real error.** IA r3 says "at least 2 years of the 3-year period" where the
  rule says the 2-year period before applying. The claim kept "2 years" and lost the words that
  make it wrong.
- **It raised false flags on design choices.** A resistor the answer chose is not a fact a blind
  sample can recompute, and the samples chose another.
- **The delivery did not change.** No caution or field came from the claim check. That is the shadow
  holding.
- **Cost:** '$0.147' for 6 units, against '$0.15' expected. The four nodes cost '$0.048' of it,
  '$0.007' to '$0.010' a unit. About '$1.97' of the owner's '$7' is now spent.

It stays in shadow. What to change before the next run is listed at the end.

## What was run

- Golden IA and Q6, three repeats each, 6 units, workflow `answer-and-recompute-claims`.
- **Code:** branch `feat/20261114-claims-shadow` at `28e5f74`, with the owner's `.env` of the date.
  Suite before the run: 1954 passed, 1 skipped, network guard 0. Started 17:30 UTC.
- No unit failed, was blocked or left a liability.
- **Traces,** copied byte-identical, prefix `docs/traces/20261114T173049Z-claims-shadow-`:

| File | sha256 |
|---|---|
| `header.json` | `381ca24b524d…` |
| `shard-0.jsonl`, `shard-1.jsonl` (Q6, IA) | `6f868e871710…`, `4c3884bcba0f…` |
| `phases-shard-0.jsonl`, `phases-shard-1.jsonl` | `633903ad3acf…`, `e5954d3a9239…` |

## Unit by unit

| Unit | Claims listed | Kept | What the claim vote did |
|---|---|---|---|
| Q6 r1 | 12 | 12 | Compared nothing: 2 of 3 samples came back in a shape the vote cannot read |
| Q6 r2 | 12 | 12 | 1 figure agreed, 1 figure flagged, 1 wording flag; 8 claims no sample answered |
| Q6 r3 | 13 | 7 | 2 figures agreed, 2 figures flagged, 1 wording flag |
| IA r1 | 10 | 9 | The 3 years and 2 years not comparable; 1 wording flag |
| IA r2 | 9 | 9 | 4 figures agreed, 1 figure flagged |
| IA r3 | 8 | 5 | 2 figures agreed, the 2 years no consensus, 1 wording flag |

## The reading

One reader, the architect. D50 asks for two readers; this is a stated departure.

**The answers.** IA r1 and r2 are right. IA r3 is wrong on the actively-engaged period, as above;
the golden screen also fails it on that item. All three Q6 answers give the right logic,
(forward OR aft) AND brake. The screen fails Q6 r3 on the known key defect: it names XOR to rule
it out.

**Figures the vote compared: 13.** 9 agreed and all 9 are right. 4 were flagged:

- **3 are false flags.** Q6 r3's LED resistor (330 against the samples' 150 ohms) and LED current
  (10 against 20 mA) are choices the answer made, not facts. Q6 r2's gate delay (10 against 7 ns)
  is a typical datasheet figure that varies by source.
- **1 is arguable.** IA r2 says recent activity is shown "during the 24 months before expiration".
  Two samples said 12 months. The architect's memory of 65.93 is that activity is required in each
  year of the two, so the answer is loose here. Not checked against the rule's text.

**Wording flags: 4,** all on text that says the same thing, such as "both airframe and powerplant
ratings" against "airframe and powerplant". No `same_meaning` stands behind the claim vote yet.

**Samples can be wrong together.** In IA r3 two of three samples gave 18 months for the
actively-engaged period, against the answer's right "2 years". Only the unit mismatch (months
against years) kept that from being a flag on a right value.

## The bars

| # | Bar | Result |
|---|---|---|
| 1 | Each IA unit compares at least two figures | **Missed.** r2 and r3 did. r1 compared none: its values were listed as text ("at least 3 years") |
| 2 | Each IA unit's claims include the two periods | **Met.** All three |
| 3 | No more than 1 in 5 right figures flagged | **Missed.** 3 of 12, or 1 in 4 |
| 4 | A wrong figure is flagged | **Missed.** IA r3's error was not flagged |
| 5 | The delivery is unchanged | **Met.** |

## The predictions

| # | Prediction | Result |
|---|---|---|
| 1 | Every IA unit lists at least 4 claims and keeps at least 3 | **Held.** 10/9, 9/9, 8/5 |
| 2 | The samples agree on the 3 years and the 2 years in every IA unit | **Wrong.** They did in r1 and r2. In r3 two samples said 18 months |
| 3 | At least one text claim is flagged for wording only | **Held.** 4 |
| 4 | Q6 gives 0 to 3 claims a unit | **Wrong.** 12, 12 and 13: the answers added voltages, delays and parts the request never asked for |
| 5 | The four nodes add under '$0.01' a unit | **Held.** |

## What the run teaches

1. **A claim must be a fact, not a choice.** The claims call listed whatever figure the answer
   stated. It should list only what a source or the request fixes.
2. **A value must arrive as a number.** Of 54 kept claims only 9 had a numeric value; the rest
   came as text such as "10 ns" or "at least 3 years". That cost IA r1 its two periods.
3. **A number alone does not carry the error.** "2 years" was right; "of the 3-year period" was
   the error. The claim needs the condition with the figure, or the condition as a claim of its
   own. This is the hard one, and it is the error we set out to catch.
4. **Twelve claims is too many for a small question.** Eight of Q6 r2's twelve got no answer from
   any sample.
5. **Seen again:** a sample that returns a bare result is unreadable to the vote (Q6 r1, 2 of 3).
   The live vote has the same weakness.

Items 1, 2 and 4 are changes to the claims prompt and the free check, inside the shadow. Item 3
is a design question. Item 5 touches the live vote, so it needs the owner.
