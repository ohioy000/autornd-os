# Where the hold-out misses fell, 2026-11-19

Free work: no provider call. It reads the byte-identical traces of the hold-out run
(`docs/traces/20261117T-holdout-*`) and was asked for after the frontier comparison, to find out
what the harness's 13 not-right answers had in common. The figures rebuild with

    python -I docs/probes/holdout_miss_classification.py

## A correction first

The report of 2026-11-18 said the harness missed 13 answers "on 11 questions" the frontier model
answered right, and that the misses were "mostly of what was read". Both were written as if the 11
questions were hard for the harness. **They were not, mostly.** Every one of the 11 was right in
at least one of its three harness draws. The misses are scattered draws, and the owner's guess that
it could have been a bad run is what the traces support. That report, `docs/MODELS.md` and the
one-page handover are corrected in the same pull request.

## The point

- **The misses scatter.** 13 of 126 answers were not right (10.3 percent), on 11 of 42 questions.
  If every draw failed alone at that rate, the number of questions with 0, 1, 2 and 3 not-right
  answers would be 30.3, 10.5, 1.2 and 0.0. Observed: 31, 9, 2 and 0. There is no sign that some
  questions are the hard ones. Among the other draws of the 11 questions, 2 of 22 were not right.
- **A thin lookup goes with a miss.** When the lookup read 3 pages or fewer, 6 of 13 units were
  not right (46 percent). When it read 4 or more, 7 of 113 were (6 percent). One-sided Fisher
  exact p = 0.0004. The pages not read were mostly pages that gave no answer within 25 seconds
  (50 of the 89 unread), then HTTP 403 (16) and over the 15 MB limit (7).
- **What the harness's rate is.** About 90 percent an answer, with the misses falling where the
  draw was unlucky. That is a finding about reliability, not about question difficulty.
- **The frontier model's 42 of 42 was one draw a question.** If its true rate were 97 percent, 42
  in 42 would come 28 times in 100. Its own scatter is not measured. The rerun of 2026-11-19
  (`docs/preregistration-20261119-eleven-rerun.md`) gives it three draws on 11 questions.

## The 13, by what the record shows

| What | Answers | Pages read |
|---|---|---|
| **Wrong, with a thin lookup** | X19 draw 2, X20 draw 1, X31 draw 2, X34 draw 3, X38 draw 2, X41 draw 2 | 1, 2, 3, 3, 1, 3 of about 6. Unread: no answer in time for X19, X20, X34, X38 and X41; HTTP 403 for X31 |
| **Blocked: the answer was cut off** | X3 draw 1, X24 draw 2 | 6 and 6 |
| **Blocked: the ask could not be satisfied** | X31 draw 1 (the text of clause 43 was not among the 5 pages read), X41 draw 1 (the datasheet states no such figure; the harness blocks rather than say "none", known limit 12) | 5 and 5 |
| **Wrong with 5 or 6 pages read** | X12 draw 3 (a transport index of 8, the factor forgotten), X13 draw 1 (the key's second item is not asked by the question, a fault of the key), X16 draw 3 (a borderline reason) | 5, 6, 6 |

In two of the thin lookups an ask was left out of the answer as well: X34 draw 3 gave 3 values
where the other draws gave 4, and X38 draw 2 gave 2 where the others gave 3. In both, the missing
item is the one a page not read would have supplied.

Three things the table does not show. The cause: the pages not read may have timed out because of
that day's network, because three processes fetched at once, or because the sites were slow.
Whether more pages read would have made these answers right. And whether the first run's timeouts
would recur. The rerun measures the last.

## What would change this, and whose it is

These are the options the evidence points at. **None is made here.** The owner's standing word is
that any lookup change is a new design and needs a ruling. Options 1 and 2 are the closest to
`CLAUDE.md`'s "how reliably it reaches a conclusion" and the owner may rule them instrument
repairs; a longer time limit still changes which pages are read, so I have not assumed it.

1. **A longer fetch time limit, or one retry of a page that gave no answer.** `FETCH_TIMEOUT_SECONDS`
   is 25. Its own comment in `autornd/knowledge/fetch.py` says it "is still a judgment, not a
   measured optimum", set after pages gave no answer in 10 s. This is the option the strongest
   figure points at: 50 of the 89 unread pages. It costs run time.
2. **A retry when the answer is cut off.** Two of 126 answers ended blocked for being cut off
   mid-sentence. A cut-off answer costs '$0.0083' to '$0.0085' and delivers nothing.
3. **Say "none stated" instead of blocking.** Known limit 12 of the release notes, seen on X41.
4. **Read more pages, or different ones, for a lookup.** `MAX_FETCHES` is 8. Nothing here says
   whether more would help.

**If any is made, the 42 hold-out questions stop being a hold-out.** A change shaped by their
misses can only be judged on questions it was not shaped against. That needs a second hold-out
set: questions written by a process that has not seen the answers, keys checked against the live
pages and signed by the owner, and a run of about '$1.4' for the harness. The first set took
authoring, a check of every key against the live pages, and the owner's signing
(`docs/reviews/2026-11-17-holdout-set-draft.md`). No second set is started; it follows a ruling to change the
lookup, and not before.

## Limits

- Small numbers: 13 not-right answers. The pattern is strong (p = 0.0004) but the cause is not shown.
- Pages read is counted from the lookup's own record. It does not say which page held the answer.
- The classification is mine, from the traces. A different reader might put X12 or X16 elsewhere.
- Whether the harness's misses and the frontier model's are alike in kind is not known: the
  frontier model had none to look at.
