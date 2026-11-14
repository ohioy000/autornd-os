# The lookup runs, to settle `quote_answers` and recheck IA and Q6 (2026-11-13)

Preregistered in `docs/preregistration-20261113-lookup-quotes.md`, committed before the run.
Figures re-derive from the traces with `docs/probes/lookup_quotes_analysis.py`.

## The point

- **25 of 26 answers were right.** All 20 lookup answers, all 3 logic-circuit answers, and 2 of the
  3 IA answers.
- **`quote_answers` passes its bar.** It gave 10 more confident no's and all 10 are right. With the
  11 from the two earlier runs that is 21, all right, against a bar of 15. A step is now
  recommended. What the step does is the owner's ruling.
- **The one wrong answer was IA r1, and nothing flagged it.** It left out the 2-year period and
  said the rule has no such figure. No answer repeated the 3-year error.
- **`same_meaning` cleared every false flag.** The vote flagged 6 right answers for wording. The
  decision model said "same" on all 6.
- **The cut-off gate was not exercised.** No answer was cut off, so the gate never had to fire.
- **Cost:** '$0.420' for 26 units, against '$0.40' expected. About '$1.65' of the owner's '$7' is
  now spent.

## What was run

- **Run A:** tier-2 Q2, Q7, Q12, Q17 and Q22, four repeats, 20 units, '$0.331'.
- **Run B:** golden IA and Q6, three repeats, 6 units, '$0.089'.
- Workflow `answer-and-recompute`. Each unit on its own empty knowledge store. No unit failed, was
  blocked or left a liability.
- **Code:** main at `f2dd801`, with the owner's `.env` of the date. Started 22:56 UTC.
- **Traces,** copied byte-identical, prefix `docs/traces/20261113T225626Z-lookup-`:

| File | sha256 |
|---|---|
| `runA-header.json` | `129099a475d4…` |
| `runA-shard-0..4.jsonl` (Q2, Q7, Q12, Q17, Q22) | `340b8a1d396f…`, `a4dbbcf5b689…`, `128e152e8d7b…`, `72b6ff21c135…`, `37389eae0880…` |
| `runA-phases-shard-0..4.jsonl` | `fedaffbfc671…`, `e9899620980e…`, `b00fe65de13a…`, `17416f718c95…`, `7304e2afcb39…` |
| `runB-header.json` | `634ab99e77a2…` |
| `runB-shard-0..1.jsonl` (Q6, IA) | `3fadb28a8865…`, `28fa35d3e05a…` |
| `runB-phases-shard-0..1.jsonl` | `f07deb8e7238…`, `5b53eeabc10d…` |

  The shard databases are git-ignored. Their rows are exported one per line in the phases files,
  each citing its database's sha256.

## The reading

One reader, the architect, read the answers against the keys. D50 asks for two readers; this is a
stated departure.

| Question | Right | Notes |
|---|---|---|
| Q2, oxygen limits | 4 of 4 | Less than 19.5 and more than 23.5 percent by volume. |
| Q7, noise table | 4 of 4 | 8, 4 and 2 hours. |
| Q12, water limits | 4 of 4 | 0.010, 4.0 and 10 mg/L, nitrate as nitrogen. |
| Q17, tagout | 4 of 4 | 50 pounds, at least annually. r3 cites the wrong paragraph for the 50 pounds; the figure is right. |
| Q22, audiograms | 4 of 4 | 6 months, 14 hours, 30 days. The paragraph numbers vary between answers; the figures do not. |
| Q6, door light | 3 of 3 | Lamp = (forward OR aft) AND brake, active-high, with the gates named. None cut off. |
| IA | 2 of 3 | r2 and r3 give the 2-year period, r3 quoting 65.91(c)(2). r1 is wrong. |

**IA r1.** It lists "actively engaged" with no period, and adds that 65.91 has "no separately
stated numeric 'recent activity' threshold". The rule says the 2-year period before applying. Its
lookup found 65.95 and the written-test line, not 65.91(c)(2). The vote could not check it (its
samples did not agree with each other), so `same_meaning` was not asked.

**The screens.** The tier-2 scorer, now .4, passed all 20. The golden screen failed Q6 r1 and r2 on
the gate item. Both are right: they name XOR only to rule it out, and the key's pattern fails any
answer that names it.

## What settles each item

1. **A step for `quote_answers`: recommended.** Run A gave 10 confident no's (0.002 to 0.036).
   Read against their passages, all 10 are right:
   - 7 were asked a question about the request itself, such as which edition to consult. No
     passage can answer that.
   - 3 were asked the request's own question, against a passage that is off the point: the
     opening line of the noise rule (twice) and the tagout programme sentence.

   With the earlier 11 that is 21 confident no's, none wrong. Both conditions hold.
2. **IA.** 2 of 3 state the 2-year period. The one that did not was not flagged by the vote or by
   `same_meaning`.
3. **The cut-off gate.** All 26 answers end whole, by the check and by the reading. None shipped
   cut off. The gate has still not been seen to fire on a live run.
4. **`same_meaning` in shadow.** Asked 6 times: Q7 r3 and r4, and Q12 r1 to r4. Each time the
   answer and the samples said the same thing in different words, such as "8 hours; 4 hours;
   2 hours" against "842". It answered yes each time, from 0.975 to 0.996.

## The predictions

| # | Prediction | Result |
|---|---|---|
| 1 | At least 4 confident no's, all right | **Held.** 10, all right. |
| 2 | Most no's come from questions about the request or its source | **Held.** 7 of 10. |
| 3 | At least one IA answer gives 3 years, unflagged | **Wrong.** None gave 3 years. One was wrong another way, and unflagged. |
| 4 | No answer ships cut off as done | **Held,** but untested: none was cut off. |
| 5 | `same_meaning` says yes on every flagged restatement, under '$0.001' | **Held.** 6 of 6. The six calls cost '$0.0005' with all three switches in them. Q17 was never flagged. |

## Other things seen

- **The vote flagged 6 of 20 right lookup answers,** all for wording. It could not check Q2 r3 and
  r4, the three IA answers or the three Q6 answers.
- **Q12's lookups found no quote in any of the 4 runs** (8 of 8 "not found"). The answers were
  right all the same.
- **One grounding question's dash is garbled** in run A's shard 3 (seven places). Not traced.

## What waits for the owner

- **A ruling on the `quote_answers` step.** The bar is met. The step would mark a quote "found,
  but not answering". Whether that only labels the quote, or also drops it from the grounding, is a
  behaviour change.
- **`same_meaning` live.** It has now cleared 6 of 6 false flags here and was right in the replay.
  Letting it clear a flag is also a behaviour change.
