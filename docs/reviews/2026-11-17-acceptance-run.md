# The acceptance run on the final configuration, 2026-11-17

Preregistered in `docs/preregistration-20261117-acceptance-run.md` (#291), pushed before the
spend. The owner's word of 2026-11-17: "1 approved", at a limit of '$4'.

## The point

- **259 of 264 answers are right** by the rule the preregistration states (every key item
  right). **248 of 264** by the stricter marks the blind readers gave first. Both clear the bar
  of 240. See "How it was read" for the difference.
- **No confirmation stood beside a wrong figure.** The one wrong figure carried a caution that
  said it was on no page, and no confirmation.
- **Five bars met, one missed.** Bar 4, that half of the wrong answers carry a caution that
  points, is missed: 1 of 5.
- **It cost '$2.32'** for the 264 answers, an answer about '$0.0088', and took about 82 seconds
  an answer with six processes running at once. The limit was '$4'.
- **The set the earlier runs built to separate the lookups, the misleading set, came out 72 of
  72.** The hard set 99 of 102, the first set 88 of 90.

## What was run

Main at `757aad1`, the default workflow (`answer-and-recompute`), the owner's `.env` as
cleaned on 2026-11-16, no setting changed. The three frozen professional sets, six answers to
each of 44 questions, in six processes (two a set) started together. The runner is
`docs/probes/short_workflows_measurement.py`, which takes each answer and its delivery from
`_detail`, the API's own builder; it is not a call to the HTTP port. The caution list in each
record is the shipped one. The confirmation is not recorded by the runner, so it was rebuilt
from the stored phase rows by `docs/probes/acceptance_run_analysis.py`, which stops if the
rebuilt cautions differ from the recorded ones for any answer. They matched for all 264.

**Six answers were blocked** by the provider's upstream 429 rate limit (`openai/gpt-oss-120b is
temporarily rate-limited upstream`) at about no cost: P5, P12, P15, H14, H16 and M1, one each.
The preregistration says blocked answers at no cost are counted as not made and made again, and
names a network drop. A rate limit is the same kind of event, and the shards had stopped far
short of their caps, so each was made again once (`20261117T-acceptance-redo-*`). That is an
extension of the stated rule, and is said here. The six answers that stand for them are 6 of the
264.

## The bars

| Bar | Result | |
|---|---|---|
| 1. At least 240 of 264 right | **259** (248 on the stricter marks) | Met |
| 2. No confirmation beside a wrong figure | **0** | Met |
| 3. At least half the right answers carry no caution | **197 of 259** (76 percent) | Met |
| 4. At least half the wrong answers carry a caution that points | **1 of 5** (5 of 16 on the stricter marks) | **Missed** |
| 5. An answer at most '$0.015', the run within '$4' | **'$0.0088'**, '$2.32' | Met |
| 6. Each set right in at least 85 percent | 97.8, 97.1 and 100 percent | Met |

| Set | Questions | Right (rule) | Right (stricter marks) | An answer |
|---|---|---|---|---|
| professional | 15 | 88 of 90 | 86 of 90 | '$0.0089' |
| professional-hard | 17 | 99 of 102 | 95 of 102 | '$0.0087' |
| professional-misleading | 12 | 72 of 72 | 67 of 72 | '$0.0087' |

## How it was read

Two readers (D50). Six blind Sonnet readers read the 44 packets, 264 answers, under codes that
hide the run. The executor then read every answer the blind readers did not mark right, the 22
answers where the free figure check and the blind reader disagreed, and a random dozen marked
right. All twelve of the dozen are right. Nine of the 22 disagreements were notation: the figure
check looked for "12" in four answers that wrote 540 x 10^12, and for dotted addresses in five
that wrote the range in CIDR form; all nine are right. The other 13 were answers the blind readers
had marked not right, taken up below.

**The difference between 248 and 259 is mine.** The packets told the readers to mark "partly"
when the key figures are right and an extra claim is wrong. The preregistration says an answer
is right when every key item is right. Eleven answers were marked "partly" for a wrong claim
outside the key (a wrong dotted mask in a table, a wrong history aside, a wrong claim about
which aircraft a rule leaves out), and on the second reading they are right by the rule, with
the notes kept. Five answers stay not right because a key item is missing or wrong:

| Question | What is wrong |
|---|---|
| H12 | The absolute maximum input-output differential given as 35 V; the key is 40 V |
| H8 | Gives 4.0 ng/L, but not the form the rule lists it in, 0.0000040 mg/l |
| H4 | 5.6 weeks and 28 days, but not the four weeks and 1.6 weeks that make it up |
| P4 (two answers) | The right figures, with the business-day count defined wrongly, which moves the deadline |

Both columns are in the tables above and both clear the bars. The verdicts and the second
reading are kept in `docs/traces/20261117T-acceptance-reading-*`.

**What the readers noted outside the key.** Roughly 30 of the 264 answers carry a wrong or
doubtful claim outside what was asked (an invented author for an RFC, a wrong rule about
another carrier, an arithmetic slip in a comparison). A rough count from free-text notes, not a
measurement. The checks read the figures the question asks for; they do not read the rest, and
the answers are long.

## What the delivery said

- **177 of 264 answers carry a confirmation** (the figures stand in a passage found on its
  page). **None stands beside a wrong figure.** One caution to keep in view: the two P4 answers
  carry a confirmation for "3 business days" and "3 years", which are right, while their
  definition of a business day is wrong. A confirmation is about words on a page, as the README
  says, and cannot see what a figure means.
- **63 answers carry a caution; 59 of them point** (two pages differ, or a figure is on no
  page). **58 of the pointing cautions are on right answers.** So 22 percent of right answers
  carry an alarm that did not turn out to matter. In the cases read, the pages that differ are
  older editions of the same section, and the answer was right in spite of them.
- **Of the five wrong answers, one carried a pointing caution:** H12's 35 V, "in none of the
  passages found on their pages". The other four are omissions or a misdefined term, which the
  figure checks do not read. Bar 4 rests on five answers, and its miss is a miss on that kind of
  error, not on wrong figures.

## Predictions

| | Predicted | Result |
|---|---|---|
| 1 | 245 to 258 right | **Held on the stricter marks (248); one above on the rule (259)** |
| 2 | No confirmation beside a wrong figure | **Held** |
| 3 | Wrong answers cluster where an older figure is widely quoted | **Wrong.** The five are an omission, a form, a datasheet figure, and a misdefined term. None is an older figure |
| 4 | Bar 4 the likeliest miss; at most half the wrong carry a pointing caution | **Held** |
| 5 | An answer between '$0.010' and '$0.014' | **Wrong.** '$0.0088', cheaper than predicted |
| 6 | Fewer than 10 blocked or not made | **Held.** 6, made again |

## What it says for the release

- The configuration that ships is right on the key in 259 of 264 answers on these sets, for about
  nine tenths of a cent an answer. The README and MODELS.md carry that as this run's result,
  with the set it was measured on.
- These are the sets the harness was shaped against, not a hold-out. The figure is not a
  forecast for a question nobody has seen.
- The known limits grow by three, written beside the release: a right figure can come with a wrong
  claim beside it; a pointing caution is raised on about a fifth of right answers; a confirmation
  cannot see what a figure means.

## Limits

- Six answers a question from the same search model and sites; they are not independent draws.
- Two readers, one of them the executor who ran it. A second human reading is the owner's to ask
  for.
- The 429 rule extension above.
- The roughly-30 count of side claims is from free-text notes.

## Traces

Copied byte-identical from `evals/results/20261117T-acceptance-*` into `docs/traces/`, cited by
sha256 (first 12 characters). The `phases-` files are the rows of each shard's database, exported
by `docs/probes/export_shard_db.py`; the databases are git-ignored. The readers' codes, six
verdict files and the second reading sit beside them as `20261117T-acceptance-reading-*`.

| File | sha256 |
|---|---|
| `20261117T-acceptance-hard-header.json` | c74f09d3811f |
| `20261117T-acceptance-hard-phases-shard-0.jsonl` | 98abe4a2fbf8 |
| `20261117T-acceptance-hard-phases-shard-1.jsonl` | 3a8e7f88ca9c |
| `20261117T-acceptance-hard-shard-0.jsonl` | 924681aa46f2 |
| `20261117T-acceptance-hard-shard-1.jsonl` | 8756e4bbe661 |
| `20261117T-acceptance-mislead-header.json` | 02f955c77093 |
| `20261117T-acceptance-mislead-phases-shard-0.jsonl` | 35e1e7b2f18c |
| `20261117T-acceptance-mislead-phases-shard-1.jsonl` | 14242e6bf62c |
| `20261117T-acceptance-mislead-shard-0.jsonl` | 9d282db02072 |
| `20261117T-acceptance-mislead-shard-1.jsonl` | e473b4764268 |
| `20261117T-acceptance-prof-header.json` | 223b8af42e9c |
| `20261117T-acceptance-prof-phases-shard-0.jsonl` | c056f8cb2ef1 |
| `20261117T-acceptance-prof-phases-shard-1.jsonl` | f7bca6369c7f |
| `20261117T-acceptance-prof-shard-0.jsonl` | 05ec58ea70cb |
| `20261117T-acceptance-prof-shard-1.jsonl` | 97f05426e8af |
| `20261117T-acceptance-reading-blind-verdicts-1.json` | cf204c24923f |
| `20261117T-acceptance-reading-blind-verdicts-2.json` | 769f534e8eb3 |
| `20261117T-acceptance-reading-blind-verdicts-3.json` | 3d6fe16b52d4 |
| `20261117T-acceptance-reading-blind-verdicts-4.json` | 2e56476db6a1 |
| `20261117T-acceptance-reading-blind-verdicts-5.json` | e1ab17584fc4 |
| `20261117T-acceptance-reading-blind-verdicts-6.json` | 58024663fd6d |
| `20261117T-acceptance-reading-codes.json` | 3f659e5d8412 |
| `20261117T-acceptance-reading-second-reading.json` | 56faa67324f9 |
| `20261117T-acceptance-redo-hard-phases-shard-0.jsonl` | 644f99cc6182 |
| `20261117T-acceptance-redo-hard-shard-0.jsonl` | 4b7cf977abd9 |
| `20261117T-acceptance-redo-mislead-phases-shard-0.jsonl` | 4bd9a882f293 |
| `20261117T-acceptance-redo-mislead-shard-0.jsonl` | d21e0b70a902 |
| `20261117T-acceptance-redo-prof-phases-shard-0.jsonl` | 9d69952e05a5 |
| `20261117T-acceptance-redo-prof-shard-0.jsonl` | b8039e884a4c |
