# Preregistration: the acceptance run on the final configuration (2026-11-17)

Pushed before the spend. The owner's word of 2026-11-17: "1 approved", to the acceptance run
proposed in the message that named a limit of '$4'.

## Why

The release should rest on one run of the configuration that ships, not on the runs of the
configurations it was reached through. Since the last answers were measured the lookup has been
cut to one, the claims workflow and the four shadow switches are gone, `needs_calculation` is
live, the recompute model is the owner's choice, and the "No lookup ran" caution is dropped
beside calculations. No run has covered all of that at once.

## What is run

The three professional sets, frozen and signed, through the default workflow
(`answer-and-recompute`) as shipped on main at the commit that carries this file, with the
owner's `.env` as cleaned on 2026-11-16. No setting is changed for the run.

| Set | File | Questions |
|---|---|---|
| professional | `evals/professional/questions.json` | 15 |
| professional-hard | `evals/professional/hard-questions.json` | 17 |
| professional-misleading | `evals/professional/misleading-questions.json` | 12 |

**Six answers to each question: 264 answers.** Run by `docs/probes/short_workflows_measurement.py`,
which runs each unit through the real engine and reads the delivery from `_detail`, the same
builder the API uses, so the cautions and confirmations recorded are the ones a caller would see.
It is the path the earlier professional runs used, so the figures can be set beside theirs. It
is not a call to the HTTP port.

**Processes.** Each set is two shards, six processes in all, started together, so all see the
same hours and the same sites. No more than six processes fetch at once, and no more than two
from one set's sites.

## Money and stops

- Expected: about '$3.00' at the shipped rate of about '$0.011' an answer. The hard set may cost
  a little more an answer.
- Each process stops starting answers once its own spend reaches its stop: '$0.62' for each
  professional shard, '$0.72' for each hard shard, '$0.52' for each misleading shard. '$3.72' in
  all.
- A process can pass its stop by the answer it is in, about '$0.02'. Worst case about '$3.84',
  inside the '$4' the owner approved.
- If a stop is reached before a shard's answers are done, the answers not made are counted as
  not made and are not rerun in this run. The report says how many.
- If the network drops, blocked answers at no cost are counted as not made and are made again
  inside the same stops.

## How it is read

- Every answer is read against the frozen keys by a blind Sonnet reader and by the executor
  (D50: two readers; the scorer is a screen and is not the result). An answer is right when every
  key item is right; H14-type absence items are right only if the answer says so. Where the two
  readers differ, the answer is shown to both again with the keys, and the difference is
  reported.
- Cautions and confirmations are read off each unit's record. A caution "points" when it names
  the wrong part: two pages differ, a figure on no page, or the vote disagrees.

## The bars

1. **Right nearly every time:** at least 240 of 264 answers are right.
2. **No confirmation beside a wrong figure:** no wrong answer carries a "verified" line or any
   confirmation. One would count against what shipped in #264.
3. **Right answers come clean:** at least half of the right answers carry no caution.
4. **Wrong answers are marked:** at least half of the wrong answers carry a caution that points
   at the wrong part.
5. **Cost:** an answer costs no more than '$0.015' on average, and the run stays within '$4'.
6. **No set collapses:** each set is right in at least 85 percent of its answers.

- Bar 1 or 6 missed: reported as it reads. The release notes carry the run's figure, not an
  older one. No change follows without a ruling.
- Bar 2 missed: the release is held and the case goes to the owner.
- Bars 3 and 4 missed: reported as the record of the delivery's honesty; the known limits grow by
  what the run shows.
- Bar 5 missed on cost: the cost per answer in the README and MODELS.md is the run's.

## Predictions

1. Between 245 and 258 of 264 are right. The first set about 88 of 90, the hard set about 92 to
   96 of 102, the misleading set about 70 to 72 of 72.
2. Bar 2 holds: 0 confirmations beside a wrong figure.
3. The wrong answers cluster on the questions where an older figure is widely quoted, and on
   the question where the search does not quote the governing paragraph.
4. Bar 4 is the one most likely to miss: a stale page gives a wrong figure with no caution. At
   most half the wrong answers carry a pointing caution.
5. An answer costs between '$0.010' and '$0.014'.
6. Fewer than 10 answers are blocked or not made.

## Limits, stated beforehand

- Six answers a question; the answers to one question are not independent draws, since the same
  search model and the same sites stand behind each. A question the harness gets wrong, it tends
  to get wrong most times.
- The sets are the ones the harness was shaped against. They are not a hold-out, and the figure
  is not a forecast for questions nobody has seen. The earlier comparison with a frontier model
  was on these questions too.
- Two readers, one of them the executor who ran it. A second human reading is the owner's to
  ask for.
- Live sites change; a rerun on another day can differ.
- The run is not compared with another configuration. It says what ships.
