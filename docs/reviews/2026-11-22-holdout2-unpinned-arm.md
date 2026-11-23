# The second hold-out run, the unpinned arm, 2026-11-22

The second hold-out run could not tell the pins from the field profiles and the new triage model: its field arms
differed from the earlier line-up in all three at once, and it read +4, "no difference shown". The owner said so, and
authorised the run that separates them with "Yes run it with the dollar cap" and a cap of '$1.00'. It was pre-registered
before the spend (`docs/preregistration-20261122-holdout2-unpinned-arm.md`, commit `6365d28`, pushed 22:03:01 CST; the arms
started at 22:03:10 CST). The record of the second run is `docs/reviews/2026-11-22-holdout2-run.md`.

## The point

- **42 of 42 right.** The law, finance and medicine questions answered by the global answer model with no pin, on their
  own field profiles and the new triage model: every key item right in every answer, read blind and again by me.
- **The pins are not shown better.** Pinned arms 41 right of 42 (N3 to N5), unpinned 42 of 42: a difference of −1, which the
  rule written beforehand reads as **no difference shown** (between −3 and +3).
- **The pins cost 3.1 times as much for it.** '$2.16' for the pinned 42 answers, '$0.69' unpinned.
- **So the +4 of the second run came from the profile and the triage model, not the pins.** Unpinned against the earlier
  line-up on these 42 questions: 42 right against 39, +3, and science (no pin, so already an unpinned arm) read +2.
  Together with science, the field profiles and the new triage model took 56 questions from 51 right to 56 right.
- **'$0.6929' for the run** of a cap of '$1.00', all 42 answers delivered, no stop rule met.

## What was run

The checkout of the second run (`ccb9d9f`, code unchanged), the owner's `.env` as it stands, the default workflow, one
answer a question, `MEASURE_SET=professional-holdout-2`, with only `PROFILE_MODELS` set, to empty, in the process
environment. Three processes together:

| Arm | Questions | Profile | Answer tier served | Right | Cost | Cost an answer | Seconds an answer | Answers with a caution |
|---|---|---|---|---|---|---|---|---|
| U3 | group 10 law, Y127 to Y140 | legal | the global answer model | 14 of 14 | '$0.2599' | '$0.0186' | 247 | 9 |
| U4 | group 11 finance, Y141 to Y154 | finance | the global answer model | 14 of 14 | '$0.2324' | '$0.0166' | 217 | 6 |
| U5 | group 12 medicine, Y155 to Y168 | medical | the global answer model | 14 of 14 | '$0.2006' | '$0.0143' | 186 | 1 |

Serving (the stop rule and prediction P4): every unit's triage on the second triage model; 41 of 42 units' engineering
seat on the global answer model through its set provider, and one (a medicine unit) answered on the architecture tier
with no engineering call, as three units of the second run were. No 404, no blind guard entry, no blocked unit.

## How it was read

Three blind readers, one a field, read the 42 answers under codes (`docs/traces/20261122T-holdout2-unpinned-reading-codes.json`
kept back), by the rule of the second run: right when every key item is right. All 42 came back right. A run that reads
42 of 42 gets a hard second look, so I screened all 42 for the key's numbers (none missing) and for the one trap key (Y151: right,
it says Part 3 imposes no ratio on a Federal branch), read against their keys the answers the second run's record said were
likeliest to fail (Y145, Y146, Y149, Y140) and five more drawn at random by seed 20261123 (Y163, Y168, Y158, Y137, Y138).
**No verdict changed.** Y149 commits to 4.0 and 5.5 percent for 2014 and to 4.5 and 6.0 percent in the cited text, where
the pinned arm's answer declined the second pair; Y146 gives 68, 15 and the sum 83. The readers are models, as the
question writers were; the limit stands.

## The comparisons, by the rules written before the run

| Comparison | Right counts | Difference | Reads |
|---|---|---|---|
| The pins' effect: pinned (N3 to N5) against unpinned (U3 to U5), groups 10 to 12 | 41 against 42 | −1 | **No difference shown** |
| Profile and triage: unpinned against the earlier line-up (O), groups 10 to 12 | 42 against 39 | +3 | no difference shown, one short of the band's end of +4 |
| Groups 10 to 13 together: unpinned arms and science (N6) against the earlier line-up | 56 against 51 | +5 | **better** by the second run's rule (+5), and it is the profile and the triage model, not the pins; two of the earlier line-up's five were upstream 429s on its triage model |

By field, pinned / unpinned / earlier line-up: law 14 / 14 / 13, finance 13 / 14 / 13, medicine 14 / 14 / 13.

Said plainly, as one answer a question on 14 questions a field: **the unpinned arm missed nothing, so the pins had no room to
add**, and the one pinned miss (Y149, N4) is a question the unpinned arm got right. A repeat of either setting would differ
from itself by a unit or two.

## Predictions

| | Said | Read |
|---|---|---|
| P1 (pins' effect) | no difference shown about two in three | **no difference shown (−1)** |
| P2 (unpinned right) | 37 to 41 | **42**: above the range |
| P3 (cost) | '$0.45' to '$0.80'; '$0.012' to '$0.018' an answer | **'$0.69'**; '$0.0143' to '$0.0186' (law a little above) |
| P4 (serving) | every unit on the global answer model | **41 of 42**, the other written on the architecture tier |

## What it says

- On these three fields, with this triage model and these profiles, the global answer model answered every question right.
  The pinned legal and large models did not beat it, and cost 1.4 times (law) to 4.3 times (finance) more an answer than
  the same field unpinned. The pins are the owner's (G-2), and this is the evidence for them: **no gain shown on
  42 questions, at 3.1 times the cost.** It does not say they are worse, or that they never help: 14 questions a field is
  a small sample, and a harder set could show a difference this one cannot.
- The second run's gain over the earlier line-up came from the field profiles and the new triage model: 5 more right in 56
  (51 to 56) with no pin in any of the arms that make it.
- The pins can be kept as options and left out of the shipped `.env`, or kept: no change follows without the owner's ruling.

## The record

Byte-identical in `docs/traces/`, prefix `20261122T-holdout2-`; first 16 characters of the sha256:

| File | sha256 |
|---|---|
| `U3-shard-0.jsonl` | `c08e7701646400b4` |
| `U4-shard-0.jsonl` | `8faeeea3c695ed60` |
| `U5-shard-0.jsonl` | `053948e05499346d` |
| `U3-phases-shard-0.jsonl` | `2c02c735a7fc1661` |
| `U4-phases-shard-0.jsonl` | `60c098256ade2ff4` |
| `U5-phases-shard-0.jsonl` | `10d430de499b637a` |

The headers (`U3-header.json` to `U5-header.json`) record the profile and the empty pins; the codes, three blind verdict
files and the second reading are `unpinned-reading-*`.
