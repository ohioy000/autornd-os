# The short workflows on the tier-2 questions — what the run showed (2026-11-13)

The predictions were written first: `docs/preregistration-20261113-short-workflows.md`, commit
`0cc26fc`. This report holds each one to its words.

## The point

- **No delivered answer was found wrong.** The scorer passed 75% and 77%. One reader read all 35
  answers it failed, and every one is right. The scorer missed headings, units written as `N*m`, a
  word such as "rejected" for "fails", and steps it could not find in order. The 114 answers it
  passed were not read.
- **The vote flagged 10 asks in 9 runs, all on right answers.** Every flag compared text with text
  that said the same thing in more words. No number was ever flagged wrongly.
- **The live `needs_sources` switch skipped 69 lookups the old risk rule would have paid for.** All
  69 were on questions that need no source, and every one of those answers was right.
- **`verify-first` cost about half as much and was as right.** That does not trigger the
  preregistered rule, which asked whether it *passed* more.
- **Spent: '$1.03' of the owner's '$7'**, plus '$0.025' for the pilot. No shard reached its
  '$1.30' stop.

## What was run

The 25 frozen tier-2 questions through `answer-and-recompute` and `verify-first`, three times
each: 150 units, five shards, each unit on its own empty knowledge store. Code: main at `09fa344`
plus the one repair on this branch. Settings: the owner's `.env` of this date, with
`needs_sources` live and the other five switches in shadow. The models and provider order are in
the header trace below.

Traces, byte-identical copies of the runner's files:

| File | sha256 |
|---|---|
| `docs/traces/20261113T091013Z-short-workflows-header.json` | `d0cd24738ec5b141fa332c0dbbf946ce06894e275452defbee4445b65cd64f46` |
| `docs/traces/20261113T091013Z-short-workflows-shard-0.jsonl` | `9a73345bce1ee37245690e8822f086d11c606d53cf9f7e09aeaf77371481a6bd` |
| `docs/traces/20261113T091013Z-short-workflows-shard-1.jsonl` | `ec910462067cd9fe1e6a068b411bd8ebf1404145b3347876a26c0017459a2968` |
| `docs/traces/20261113T091013Z-short-workflows-shard-2.jsonl` | `4bb9ccfebe1c28084586d37bf91f80677a9801fa26a35218235661b0496f19b0` |
| `docs/traces/20261113T091013Z-short-workflows-shard-3.jsonl` | `ed13f7bfae8afa937cd2f4a3b1cfe9cbcd8664452a69f47516f374cc65cf3091` |
| `docs/traces/20261113T091013Z-short-workflows-shard-4.jsonl` | `41eace7714cdcc2a329b49c7fade0a0d0cc980ef0d8c5f0a81ee02d0fca3dc29` |

Each shard's scratch database is git-ignored (`*.db`), so its rows are exported one per line to
`docs/traces/20261113T091013Z-short-workflows-phases-shard-N.jsonl`. This is derived, not
byte-identical: every workflow row carries the sha256 of the database it came from. These files
hold the quotes' words, which the runner's own lines do not.

Every figure below comes from `docs/probes/short_workflows_analysis.py`, which reads only these
files:

    python3 -I docs/probes/short_workflows_analysis.py docs/traces/20261113T091013Z-short-workflows

## The predictions

| # | Prediction | Result | Held? |
|---|---|---|---|
| 1 | Delivery: answer-and-recompute ≥ 95%, verify-first ≥ 85% | 75/75 (100%) and 74/75 (99%) | Held |
| 2 | Scorer pass between 60% and 85%, within 10 points | 56/75 (75%) and 58/75 (77%), 2 points apart | Held |
| 3a | Vote unchecked ≤ 25% (SANITY+DERIVATION, answer-and-recompute) | 3/30 (10%) | Held |
| 3b | Vote flags ≤ 10% of scorer passes there | 1/29 (3%) | Held |
| 3c | Vote flags at least half of answers the reading confirms wrong | No answer was confirmed wrong | **Not tested** |
| 4 | `needs_sources` yes on ≥ 90% of LOOKUP, no on ≥ 90% of SANITY and DERIVATION | yes 30/30; no 30/30 and 30/30 | Held |
| 5 | `ask_covered` ≥ 0.8 on at least 95% of asks | 337/347 (97%) | Held |
| 6 | Mean unit ≤ '$0.02' on either workflow; whole run ≤ '$3' | '$0.0089' and '$0.0048'; '$1.03' | Held |

Prediction 2 held only because the scorer fails right answers in two shapes. On the reading, the
share of right answers is 75/75 and 74/75. The one gap is a unit that was blocked, not wrong.

Against "what would change a decision":

- **3c failing would have said the vote is not worth its three calls.** It could not fail: there was
  nothing wrong to catch. What the run does show is a cost: the vote caught nothing and put false
  flags on 9 of 75 deliveries.
- **4 did not fail**, so `needs_sources` stays live.
- **verify-first did not pass more than 10 points above** the default. It came out 2 points above
  on the scorer and 1 point below on the reading, so the preregistered rule does not put the
  default in question.

## The reading

One reader, the architect, read every delivered answer the scorer failed, against
`evals/tier2/keys.json`. **This departs from D50, which asks for two independent readers; every
figure in this section rests on one reading.** I read 21 answers in full. For the 14 longer answers,
I checked every item the scorer failed by finding the lines that carry it. Items the
scorer passed were taken as passed. The 114 answers the scorer passed were not read.

**All 35 are right.** Why the scorer failed each one:

| Units | Item the scorer failed | What the answer says |
|---|---|---|
| Q4 A&R r3; Q14 A&R r1, VF r2; Q19 VF r1; Q24 A&R r1, r3 | three sections | three sections, headed by plain lines or "Section 1 —", not Markdown |
| Q4 VF r1 | selected dimensions | 20.0 × 3.00 × 500 mm, set out on three lines |
| Q5 A&R r2 | logged pressure drop | 0.10 bar; the scorer took the 0.20 bar limit as the headline |
| Q5 A&R r3 | vent closed before pressurising | step 2.6 closes it "BEFORE ANY PRESSURIZATION" |
| Q6 VF r1 | ordered outputs | 00 → 0, 01 → 1, 10 → 1, 11 → 0, written as a labelled list |
| Q9 A&R r2; Q19 A&R r1, r3 | failure verdict on the rejected option | "rejected", with the limit it breaks |
| Q10 A&R r3 | setpoint, log range, removal threshold | all present, written as "120 C" without the degree sign |
| Q14 VF r3 | the selected heater passes | "Yes — equality", "explicitly permits" |
| Q15 A&R r2, VF r1 | signed errors | +0.010, −0.030 and +0.005 mm; the scorer took figures from the trend analysis that follows |
| Q18 A&R r2, VF r1, VF r2 | maximum bending moment | 500 N·m, written `N*m` or `N.m` |
| Q19 VF r2 | rejection, dissipation, rating | "FAILS the upper current limit"; 0.132 W; ≥ 0.264 W; 0.500 W |
| Q20 A&R r1, r2, r3, VF r1, r2 | the order of the bench steps | every step in the instruction's order; reference flow 11.76 L/min; +2.04%; PASS |
| Q24 A&R r2, VF r2, VF r3 | ratio, output torque | 3.00:1 and 12.0 N·m, written `N*m`, `N.m` or in bold |
| Q25 A&R r1, r2, r3, VF r1, r2, r3 | start and stop order, bands | 0 V before enabling and before disabling; both bands as inequalities; 1.08 V; PASS |

Right, but each carries something the instruction did not give:

- **Q10 A&R r3** adds an approach setpoint before 120 °C, and a downward setpoint correction during
  the hold. Its made-up times sit in a column headed "Example", not in the log.
- **Q25 VF r3** lets a sweep that chattered be repeated once. The instruction gives no repeat, but
  this log's verdict does not depend on it.
- **Q25 VF r2** runs to 27,311 characters, including a Python bench script.

The misses are form, not substance. Of the 35, 31 lie in SPECIFICATION and PROCEDURE, three in
DERIVATION and one in SANITY. A scorer change would be a new `evals/tier2/versions.json`
entry under the rules in `.claude/context/evals.md`. It is listed below for the owner, not made here.

## The vote

answer-and-recompute, all shapes: unchecked in 25 of 75 runs (33%). It flagged 8 of 56 scorer
passes and 1 of 19 scorer fails, and all nine flagged runs are right answers. These are the ten
flagged asks:

| Unit | The answer's value | The samples' majority |
|---|---|---|
| Q6 r3 | `XOR: Alarm = A ⊕ B = A'B + AB'` | `AXORB` (3 of 3) |
| Q24 r1 | `same direction as the driver` | `SAMEDIRECTION` (2 of 3) |
| Q7 r1, r2 | `8 h at 90 dBA; 4 h at 95 dBA; 2 h at 100 dBA` | `842` (3 of 3) |
| Q12 r1, r2, r3 (ask 3) | `as Nitrogen (as N)` | `ASNITROGEN` (3 of 3) |
| Q12 r2 (ask 1) | `arsenic 0.010; fluoride 4.0; nitrate 10 (as N)` | `ARSENIC0010FLUORIDE40NITRATE10` (2 of 3) |
| Q17 r2 | `at least annually (no less than once every 12 months)` | `ATLEASTANNUALLY` (3 of 3) |
| Q17 r3 | `at least 1` | `ATLEASTANNUALLY` (3 of 3) |

Each is text against text, matched exactly after both are upper-cased and stripped to letters and
digits. The answer says the same thing in more words. The last one is fair on its face: "at least
1" is a poor typed value, though the answer's prose says "annually". No comparison of numbers
flagged a right answer.

A free rule does not fix this safely. "The answer contains the majority" clears six of the ten,
but it also clears `not the same direction as the driver`. Changing what the vote flags changes
what the harness concludes, so it is the owner's ruling. Options are listed at the end.

## The switches

**`needs_sources`, live.** It answered yes on 30 of 30 LOOKUP units, and no on every unit of the
other four shapes: 30, 30, 30 and 29. The 30th PROCEDURE unit was blocked before the switch ran.
Lookups ran on 30 of 30 LOOKUP units and on none of the others.

The old rule looks up anything triage does not rate low. Triage rated 70 of the non-LOOKUP units
medium, high or critical; eight DERIVATION units were rated critical. One of the 70 was blocked
before the switch was asked. On the other 69, the switch said no and no lookup ran. Two LOOKUP units rated low got their lookup because the switch said yes,
which is the case the owner's ruling was made for.

A lookup cost about '$0.009' here. LOOKUP units carry about '$0.010' outside their phase rows,
against about '$0.001' for the rest. So the 69 skipped lookups are worth roughly '$0.6'. That is an
estimate: it assumes each would have cost what the 30 that ran did.

**`hard_request`, shadow.** It answered yes on every DERIVATION and SPECIFICATION unit, no on
every LOOKUP unit, and was split on SANITY and PROCEDURE. Every answer was right, so it predicted
nothing here. Nothing reads it yet.

**`ask_covered`, shadow.** 337 of 347 asks scored 0.8 or above, as predicted. The ten below that
come from four units, Q5 r1, Q10 r2, Q10 r3 and Q25 r2. All four are among the 14 answers longer
than the switch's evidence cap of 6,000 characters (`MAX_EVIDENCE_CHARS`,
`autornd/routing/switches.py`). The asks it doubted are the verdict and the criteria, which those
answers put at the end, past the cut.

The constant's comment says a text's opening shows what it bears on. That is true of a passage,
but not of a whole answer, and this is a defect in what the switch is shown. **The proposed repair:**
for an answer, keep its opening and its end inside the same bound; for a passage, keep the opening.
That is instrument repair, since the switch is in shadow and nothing acts on it. It is held for the
next measurement, under the rule that fixes are tied to one.

**`quote_answers`, shadow.** It answered 10 yes, 9 no and 1 unsure. Each answer was paired with its
quote from the exported rows, and all 20 paired by address. On one reading, all 19 confident answers
are right:

- **The nine no's.** In four, a scope or general paragraph was quoted where values were wanted. In
  the other five, the passage was judged against a question about the request or its source rather
  than the subject, such as "Which physical copy or database of the July 1, 2014 edition will be
  used". No passage can answer that.
- **The ten yes's.** Each passage states a figure its question asks for. The question about
  audiograms asks three things: the 6-month deadline, the 14-hour quiet period and the 30-day retest
  window. A passage giving any one of them answers it.

No step reads this switch yet (`switches/default.yaml`), so making it live would change nothing
until a step is given something to do on a confident no. One choice would be to keep the quote as
found but mark it as not answering. What that step does is the owner's ruling. On this sample, a
step acting on a confident no would have made nine right calls and no wrong one.

The questions about the request are a finding of their own. Six of the twenty quotes were judged
against one, counting the unsure. The grounding lookup asks questions that no source can answer,
and they cost search calls.

**`chunk_helps` and `finding_answers`** were not asked: each unit started with an empty store, as
preregistered.

## Cost and time

| | answer-and-recompute | verify-first |
|---|---|---|
| total | '$0.6696' | '$0.3596' |
| mean, median, max per unit | '$0.0089', '$0.0073', '$0.0222' | '$0.0048', '$0.0028', '$0.0180' |
| seconds: mean, median, max | 108, 103, 320 | 91, 78, 363 |

No unreconciled liability was recorded. The three recompute samples cost '$0.28' of the default
workflow's '$0.67'.

## The one unit that did not deliver

Q20 verify-first r3 ended `blocked`. A chat call to the triage tier was answered 429 ("temporarily
rate-limited upstream") after the client's own retries, before the switch was asked. The run cost
'$0.0002', kept no liability and stopped honestly. One unit in 150 is not a pattern; it is
recorded here and nothing is changed.

## What this run cannot show

- **One reader.** Two readers are the standard (D50). And the 114 scorer passes were not read, so a
  wrong answer the scorer passed would not be seen.
- **This set no longer separates the workflows.** Every delivered answer was right, so the vote and
  `hard_request` had nothing to catch. A difference between workflows needs harder questions.
- **75 units a workflow.** A difference under about 15 points is noise.
- **The questions have keys; real requests do not.**

## For the owner

Each of these changes what the harness concludes, or which work ships, so none is made here.

1. **The vote's text comparisons.** These flagged 9 of 75 deliveries, all of them right. The
   options:
   - **(a)** Leave it. The flag is a note, and a reader sees it as a caution.
   - **(b)** Compare numbers only, and record a text ask as not compared. This loses the chance to
     catch a wrong verdict word.
   - **(c)** Ask a decision model, in shadow first, whether the answer's text and the majority's say
     the same thing. Ask only when a text ask disagrees.

   My recommendation is (c): replaying these ten costs under a cent and would show whether it
   separates.
2. **A step for `quote_answers`.** On this run all 19 of its confident answers were right. The
   question is what a confident no should do to a quote. Live, it does nothing until that step
   exists.
3. **The scorer's form misses** on SPECIFICATION and PROCEDURE. A new scorer version under D44's
   rules, held against `regression_12.py` and these 35 answers, would make the screen useful on
   those two shapes again.
4. **A harder set** if the workflows, the vote or `hard_request` are to be compared at all.

The `ask_covered` evidence repair is mine to make, and it waits on the next measurement.
