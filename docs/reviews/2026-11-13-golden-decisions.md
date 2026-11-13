# The golden questions, to settle four choices (2026-11-13)

Preregistered in `docs/preregistration-20261113-golden-decisions.md`, committed before the run.
Figures re-derive from the traces with `docs/probes/golden_decisions_analysis.py`.

## The point

- **12 of 15 answers were right. 3 were wrong.** Two of the owner's IA answers gave a 3-year period
  where the rule says 2 years. One logic-circuit answer was cut off mid-sentence and never named
  its gates.
- **The vote caught none of the three.** It flagged nothing in 15 runs. The IA error sat in the
  prose, and the vote compares only typed values.
- **Batch 2 did not run.** The preregistered rule runs it only if batch 1 has fewer than three
  wrong answers. It had three.
- **Recommended:** a decision model for the vote's text comparisons, in shadow (option (c)), and a
  new tier-2 scorer version. **Not yet:** a `quote_answers` step (too few confident no's) and a new
  harder set (the golden set already finds errors).
- **Cost:** '$0.171' for 15 units, and '$0.00007' for the replay. About '$1.23' of the owner's '$7'
  is now spent.

## What was run

- **Batch 1:** golden Q2, Q4, Q5, Q6 and the side test IA, from `evals/golden/keys.json` version 1.
  Workflow `answer-and-recompute`, three repeats each, 15 units. Five shards, one question each,
  each unit on its own empty knowledge store.
- **Code:** main at `4c0f80e` plus the runner's two settings (`aa6ed07`). The owner's `.env` of
  this date. Run from 18:00 to 18:06 UTC.
- **The same-meaning replay:** the vote's ten text disagreements from the tier-2 run, and the six
  contrary pairs the preregistration wrote, put to the decision tier through the real
  `Switchboard`. Batch 1 had no disagreements to add.
- **Traces,** copied byte-identical:

| File | sha256 |
|---|---|
| `docs/traces/20261113T180026Z-golden-batch1-header.json` | `0d738ec21f6e…` |
| `…-shard-0.jsonl` (Q2) | `b0e9234297e8…` |
| `…-shard-1.jsonl` (Q4) | `e7b99c8c17d9…` |
| `…-shard-2.jsonl` (Q5) | `26ee8aafcf96…` |
| `…-shard-3.jsonl` (Q6) | `dd7d987cd8b6…` |
| `…-shard-4.jsonl` (IA) | `5304356b50f4…` |
| `…-phases-shard-0..4.jsonl` | `a848848f29e3…`, `513c5868c795…`, `fffd76d83a05…`, `d8d942f699de…`, `aa3a47f6ff98…` |
| `docs/traces/20261113T181530Z-same-meaning-replay.json` | `10a46c845226…` |

  The shard databases are git-ignored. Their rows are exported one per line in the phases files,
  each citing its database's sha256.

## The reading

One reader, the architect, read all 15 answers in full against the golden keys. D50 asks for two
readers; this is a stated departure.

| Question | r1 | r2 | r3 | Notes |
|---|---|---|---|---|
| Q2, oxygen limits | right | right | right | All quote "less than 19.5" and "more than 23.5 percent oxygen by volume" from the 2014 text. |
| Q4, tie strip | right | right | right | 3.00 mm; the 2.00 mm strip fails at 150 MPa; 0.2355 kg. |
| Q5, leak test | right | right | right | Every step in order; drop 0.10 bar; PASS. |
| Q6, door light | right | **wrong** | right | r1 and r3: lamp = brake AND (forward OR aft), positive logic, an OR gate and an AND gate. r2 is cut off. |
| IA | right | **wrong** | **wrong** | r1: 2-year period, quoted from the fetched rule. r2 and r3: "3-year period". |

**IA r2 and r3.** Both say the applicant must have been "actively engaged, for at least the 3-year
period" before applying. The rule says 2 years (65.91(c)(2)). Their typed result named only the
citation, such as `14 CFR 65.95(a)(1)`. r3 also quotes 65.95 with words the rule does not contain.
r2's record says it checked only 65.95(a)(1).

**Q6 r2.** The delivered answer stops at character 1948, mid-sentence: "…reads as ". The text never
names a gate. Its typed results do name `74HC32 (OR) + 74HC08 (AND)`, and `done` and `green` were
both true. The model wrote the cut text itself; the harness does not clip it. No caution says the
answer is incomplete. Counted wrong: what the reader receives fails the key's gate item.

**The screens against the reading:**

| | right answers it failed | wrong answers it held |
|---|---|---|
| Golden scorer, 15 answers | 1 (Q6 r3) | 0 |
| Tier-2 scorer, the 9 answers to Q2, Q4, Q5 | 5 (Q4 r1, r2, r3; Q5 r2, r3) | none was wrong |

Every miss is form. Q6 r3 writes "exclusive-OR … explicitly rejected", which trips the key's
none-pattern. Tier-2's misses: plain-line headings it did not count; the selected size not found,
or the width taken for it; the gauge resolution (0.05 bar) or the limit (0.2 bar) read as the
logged drop; and "Close the high-point vent", plainly stated, not found.

## The predictions

| # | Prediction | Result |
|---|---|---|
| 1 | Q6 right in at least 2 of 3 | **Held.** 2 of 3. |
| 2 | IA wrong on a core item in at least 1 of 3 | **Held.** 2 of 3, both on IA.2. |
| 3 | `needs_sources` yes 6 of 6 on Q2 and IA, no 9 of 9 on the rest | **Held.** Lookups ran on exactly those 6. |
| 4 | The vote flags at least one right Q6 or IA answer | **Wrong.** It flagged nothing. See below. |
| 5 | Batch 2 has at least 3 wrong answers | **Not tested.** Batch 2 did not run. |
| 6 | Batch 1 at most '$0.40' | **Held.** '$0.171'. Batch 2 not run. |

## The vote

It compared something in 6 of 15 runs and flagged none. Why it compared nothing in the other 9:

- **Q6, all three:** both of Q6's asks were typed `step`. The vote compares only `value` and
  `verdict` asks, so it could never look at Q6. On r2, also, none of the three samples came back as
  a results list. 4 of Q6's 9 samples came back in a shape the vote does not read: a bare result,
  or keys of their own. They count as neither parsed nor failed.
- **IA r1 and r3:** the three samples did not agree with each other on the one ask.
- **Q2 r1 and r2:** the samples wrote `< 19.5`. The vote's number reader does not read a number
  after `<`, so there was no consensus. The operator is the very thing the question asks for.
- **Q4 r1 and r3:** no ask was typed `value` or `verdict`; all were steps, constraints or format.

**On IA, no option for the vote would have caught the error.** The wrong period lived only in the
prose. And the recompute samples, asked the same thing, invented requirements of their own: "2
years out of the previous 4", "a written recommendation from employer", "good moral character".
The rule has none of these.

## The same-meaning replay

The question, as preregistered: "Do the two values state the same thing for this ask?" Thresholds
0.80 and 0.20.

| Pairs | yes | no | probabilities |
|---|---|---|---|
| 10 real disagreements, tier-2 run | 9 | 1 | 0.150 to 0.998 |
| 6 contrary pairs | 0 | 6 | 0.000 to 0.124 |

The one real no is `at least 1` against `at least annually` (0.150). That typed value does not say
"annually" on its own; the tier-2 report called it a poor typed value. Read either way, the rule
holds: yes on 9 of 10, or on 9 of 9, of the pairs that say the same thing. And no yes on any pair
that differs. The closest contrary pair was nitrogen against nitrate ion, at 0.124.

## What settles each choice

1. **The vote's text comparisons: (c) is recommended.** Both preregistered conditions hold. Ask the
   decision model, in shadow, only when a text ask disagrees. This replay cost '$0.00007' for 16
   pairs. Two limits: six contrary pairs, written by the architect, are a small test. And the vote
   has not yet caught a wrong answer in either run, so this removes false flags; it adds no catches.
2. **A step for `quote_answers`: still too thin.** Batch 1 added 2 confident no's, both right on
   the reading, making 11 of 11. The preregistration asks for 15. Batch 2 would likely have added
   few: its pages come with the question, so few lookups would run. More LOOKUP runs would add
   them.
3. **A tier-2 scorer version: recommended.** Tier-2's scorer failed 5 of the 9 right answers to Q2,
   Q4 and Q5, all on form. The golden scorer held all 9. A new version would be a
   `evals/tier2/versions.json` entry under D44's rules, held against `regression_12.py` and the 35
   answers of the tier-2 run. The keys stay frozen.
4. **A harder set: not recommended now.** Batch 1 had three wrong answers in 15. The owner's own
   golden questions, IA and Q6, already find errors. They can go into the next measurement as
   they are.

## What else the run found

These are findings, not changes.

- **A cut-off answer ships as done.** Q6 r2 ended mid-sentence with `done` and `green` true and no
  caution. `ask_covered` gave 0.55 (unsure) on "logic, polarity, and gates". A check for this
  would change what ships, so it is the owner's ruling.
- **The `ask_covered` clip explains only part of its low scores.** On Q5 r2, at 9265 characters,
  two of its three low scores fall on asks answered past the 6000-character cut. The third, "no
  visible water leakage during the hold" (0.13), is answered at character 1992, inside the cut. So
  the head-and-tail repair held from the tier-2 run would not fix every low score.
- **`quote_answers` is asked questions no passage can answer.** On IA, the grounding's questions
  were about the request's scope, such as "Whether 'inspection auth' refers to Part 65…". It was
  unsure on 7 of 9.
- **Unreadable samples are not counted.** A sample that comes back in the wrong shape counts as
  neither parsed nor failed. Counting it is instrument repair, mine, held with the clip repair.

## Cost and time

| | |
|---|---|
| batch 1 total | '$0.1707' |
| by question | IA '$0.0584'; Q2 '$0.0339'; Q4 '$0.0267'; Q6 '$0.0264'; Q5 '$0.0253' |
| seconds per unit: mean, median, max | 135, 118, 246 |
| replay | '$0.00007' |
| spent of the owner's '$7' | about '$1.23', of which this run '$0.171' |

No unreconciled liability was recorded.

## What this run cannot show

- **One reader.** D50 asks for two.
- **Five questions, three repeats.** Three wrong answers is enough for the batch-2 rule, not for a
  rate.
- **The replay's contrary pairs are few and hand-written.**

## For the owner

Each of these changes what the harness concludes, or what ships, so none is made here.

1. **The vote's text comparisons:** option (c), the decision model in shadow, when a text ask
   disagrees.
2. **A tier-2 scorer version** for SPECIFICATION and PROCEDURE form misses.
3. **Whether a cut-off answer may ship as done.**
4. **`quote_answers`:** wait for at least 4 more confident no's from LOOKUP runs.

Mine, held for the next measurement: the `ask_covered` head-and-tail clip, now known to explain only
part of its low scores, and a count of unreadable samples.
