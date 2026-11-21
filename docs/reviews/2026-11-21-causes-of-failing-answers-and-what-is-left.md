# Why answers failed, across every run so far, and what is left to do (2026-11-21)

Written at the owner's request after the reader beta and the tests that followed: read every earlier
run's report and traces, name the causes of the failing answers, and say what else is needed beyond
the fetch limits (60 s, 37.5 MB) and the research tier's medium effort and ceiling (#309, #312, #313).
Free work except where a section says it was measured live; the live spend of 2026-11-20 and 21 is
listed at the end. Sources: `docs/reviews/2026-11-15-*` to `2026-11-19-*`, `docs/traces/20261117T-holdout-*`
and `20261119T-eleven-rerun-*`, and the logs of the runs of 2026-11-20 and 21 (kept in the session
scratchpad, not in the repo; their figures are quoted here).

## The point

- **The failing answers have six causes, and only two are fixed.** Thin lookups (pages not read) are
  loosened by #309. The research tier's runaway reasoning was a cost and time fault, not a
  correctness one, and #312 and #313 fixed it. Four causes stand: an answer that blocks where it
  should say "none stated", a stale official page taken as current, a search that returns the wrong
  family of pages (X12), and an answer cut off mid-sentence.
- **The reader tier shows no benefit.** Same cost and time, and on X12, the question it was built for,
  4 of 5 right with it off and 3 of 5 with it on. Its pages-read gain on X34 is real but did not
  change that answer.
- **The X12 miss is a wrong-pages problem, not an unread-pages one.** Corrected after merge: the first
  text of this review said the Table 7 passage, the factor of 2 for a load area of 1 to 5 m², was lost
  after the pages were read. Read from the ten X12 draws on disk: all three TI 8 answers read only US
  federal rule pages (four, six and five of them: eCFR, govinfo) and no IAEA document; all seven right answers read at least one.
  The three draws that sent the question whole to the search all found the IAEA pages; the seven that
  sent the scoping call's rewrite had lost the word "international", and three of those got US pages only.
- **Time is mostly the answer-writing call and the lookup, money is mostly the lookup.** In the
  hold-out run the answer-writing step was 57 percent of the time (median 51 s) and cost '$0.327'
  of '$1.356'; grounding took '$0.872' of it.

## The causes, with what each cost

Counts are from the reports named; none was re-derived except where marked.

| # | Cause | Where it showed | Status |
|---|---|---|---|
| 1 | **A thin lookup: pages never read** (no answer in 25 s, HTTP 403, over 15 MB) | 6 of the 13 hold-out misses (X19, X20, X31, X34, X38, X41) read 1 to 3 pages; X12 in the rerun read 1 and 2 of 6. Fisher p = 0.0004 on the hold-out, 0.19 on the rerun's 28 | Loosened by #309. X12 now reads 6 of 6 and is right in 4 of 5 today, but X34 still read only 2 of 6 once, with 154 s of grounding |
| 2 | **Blocks where it should say "none stated"** (known limit 12) | X41 blocked twice in the hold-out and rerun and gave an invented 45 degC/W once; X31 draw 1 blocked on clause 43 | Ruled (option C) and built, not yet measured; see the status table below, item 3 |
| 3 | **A stale official page taken as current** (known limit 4) | X31 gave the 2015 licence in two runs; the flight-attendant question gave 9 hours three of three in the hard set; two BasicMed answers in the misleading set | Open. Nothing in the harness detects it |
| 4 | **The search returns the wrong family of pages**: US federal rules where the question asks for the international document | X12 TI 8 (the factor of 2 forgotten): 3 of the 10 draws on disk, each with only US federal pages read (four, six and five) and no IAEA page. The hold-out's wrong draw also cites 49 CFR in its answer; its pages were not kept | Open. A change to what the lookup asks, the owner's ruling |
| 5 | **An answer cut off mid-sentence, then blocked** | X3 (1,713 characters) and X24 (5,917) in the hold-out, 2 of 126, '$0.0085' and '$0.0083' for nothing | Open. Not a token cap, since the answers are short; cause unknown; no retry exists |
| 6 | **The question or the key is at fault, or the call is borderline** | X13 (the key asks what the question does not), X16 (a reason), X34 ("more than 18 m" against "18 m or more"), X19 and X20 (wording) | Measurement noise: about 4 of the hold-out's 9 wrong answers. Not a harness fix |

Operational faults that cost draws or time, not correctness, are separate and mostly closed: 402 refusals
from running two arms at once (11 draws lost), 429 rate limits (6 in the acceptance run), the research
tier's reasoning runaway (a unit at 796 s and '$0.0999'), and an `OverflowError` in the numbers check
on an answer that wrote `10^400` (#311).

## What the live tests of 2026-11-20 and 21 showed

- **The research tier's runaway was general, not one provider's.** At the provider's default
  reasoning the scoping call spent 4,000 to 10,500 tokens on six other hold-out questions and 15,000 to
  30,400 on X12; a different provider ran away 4 of 4 times, and the smaller model 7 of 11. At medium
  it used 650 to 1,030 tokens. Query expansion ran away once as well (24,253 tokens, 189 s).
  Low effort named fewer lookups on the smaller model (X4 from 2 to 0), which medium did not on
  the regular model; this is why medium is the setting, not low.
- **Four units on the new setting were right** (X4, X12, X22, X34), one reading each.
- **The reader tier:** four questions, off 4 right, on 3; X12 three more draws each, off 2 of 3, on 2 of 3.
  Reader calls cost about the same as they save. It hands on 3 to 4 times more quoted text. The X12
  differences follow which pages the search returned, not the reader: the three wrong draws are one with
  the reader off and two with it on, and all three had no IAEA page.
- **The answer-writing call** used 2,711, 9,126 and 4,620 tokens for answers of about 1,000 tokens, in 17
  to 56 s, for '$0.002' to '$0.003'. It is a time cost.
- **A larger model for the answer-writing call** (one draw, X12, `moonshotai/kimi-k3.1-pro`): right, 141 s,
  the unit '$0.0699' against about '$0.018', the call itself 17 to 35 times the price. One draw shows
  no accuracy difference.
- **`tenstorrent/fp8` cannot serve this harness** for the research model: it does not support
  `response_format`, so routing finds no endpoint.

## What is left, in the order the evidence supports

Rulings are the owner's. Each item says what it would cost and what it could be judged on.

1. **A second hold-out set before any of 2 to 5 below.** The 42 questions are used: every change shaped
   by their misses can only be judged on questions it was not shaped against. Authoring, checking every
   key against the live pages and the owner's signing, then about '$1.4' for the harness.
2. **Keep the question's own jurisdiction words in every lookup question** (cause 4). Found free, from
   the ten X12 draws on disk: the 3 wrong draws all had a scoped lookup question with no "international"
   in it and a search that returned only US federal pages; the 3 draws that sent the question whole all
   found the IAEA pages; of 7 scoped draws, 4 found them. Seven right against three wrong on that split is
   p = 0.008 (one-sided), but the grouping was made after seeing the pages and the draws are not a
   designed test, so it is a lead and not a proof. Two ways to act, both a change to what the lookup asks
   and so a ruling: add the question's own words to each scoped lookup question, or search the whole
   question as well. A test costs the grounding only, under '$0.02' a draw (the hold-out's grounding
   averaged '$0.007' a unit; X12 reads more).
3. **"None stated" instead of blocking** (cause 2). Seen in 4 to 5 of about 160 answers on the same two
   questions. Needs a design that does not let an unread page count as "none".
4. **A retry when an answer is cut off** (cause 5), after finding why it ends early. 2 of 126, each
   costing '$0.008' now for nothing. Retry wiring may be an instrument repair; the exit condition is a
   ruling. Asked, not decided.
5. **A way to see a stale instrument** (cause 3): put the question's "as of" date into the lookup, or
   prefer a page that says what it supersedes. Prompt text that steers judgment: a ruling.
6. **Faster PDF reading and one retry of a page that gave no answer.** Downloads take 0.5 to 2 s; the
   PDF text read is the time (19 of 36 pages in 60 s). X34's 154 s of grounding shows it still bites.
7. **Measure the answer-writing call at lower effort** on 4 questions, about '$0.05'. It is 57 percent of
   the time and a cheap model; a lower effort could save a minute a unit, and could cost accuracy.
8. **Pins and prices:** the reader tier has no pin yet (G-2). The larger model's price (output about 17
   times higher) makes it a choice for a premium or escalation tier, not the default.

## Limits

- Counts for the older runs come from the reports above and were not re-derived, except the per-phase
  table (from `20261117T-holdout-phases-shard-*`) and the lookups of the eleven-question rerun.
- Today's tests are one draw per question, mostly, and one reader (me) against frozen keys on a used set.
  They show no clear failure and cannot show a small gain or loss.
- Cause 4 was first written as "the passage is lost after the pages are read" and corrected the same day
  from the pages kept in the run databases of 2026-11-20 and 21 (ten X12 draws). The hold-out and the
  eleven-question rerun kept no page addresses, so for their X12 draws only what the answers cite could be
  checked. The reader's X12 comparison is confounded by which pages the search returned.
- The implement probe spent '$0.0736' against the '$0.06' I stated, because the shard cap is checked
  between units and X12 cost '$0.05' that time (the 24,253-token call). Over by '$0.014'.

## Spend of 2026-11-20 and 21 (all stated before spending)

Reader beta about '$0.30'; provider and Flash scoping tests '$0.384'; cap-versus-effort tests about '$0.10' and
'$0.036'; medium-effort scoping '$0.0269'; four full units '$0.0674'; reader on/off '$0.178' of '$0.20'; implement
probe '$0.0736'; larger-model test '$0.0699' of '$0.10'; whole-question search replay '$0.0176' of '$0.02'.
Credits left '$0.2669' at the last check, so about '$0.249' after the replay.

## Status after the owner's answers of 2026-11-21 (evening)

The list above, as the owner answered it. Items not yet done are kept here so none is lost.

| # | Item | Status |
|---|---|---|
| 1 | A second hold-out set | Prompts written: `docs/holdout-2-prompts.md`. Three authors, two checkers, the owner signs, one run of about '$1.4'. |
| 2 | Ask the whole question too | Built, PR #317 (one more numbered line in the same single search request). **Measured in part, 2026-11-21:** a search-only replay on the three stored scoped questions that had led to US-only pages (three search requests, '$0.0176' of the owner's '$0.02'; nothing fetched, no answer written). With the whole question first, the first six addresses named held IAEA documents in all three (3, 5 and 1 of the six; the trace's own `iaea` field counts every address named, 15 to 17 a call, and the first-six counts come from its `urls`), each with the 2025 edition of SSR-6, which none of the three draws had read. **A lead, not a result:** three requests, on questions picked because they failed (some would do better on a second try with no change), no same-day control, and it counts pages named, not pages read; the 2025 edition is a large PDF and large PDFs still time out at 60 s (item 5). Record: `docs/traces/20261121T-whole-question-smoke.jsonl` (sha256 `d92a059a81b8c6b09efe19fc544faddd57637213cd53dde63783e3deebf90007`), inputs beside it, probe `docs/probes/whole_question_search_replay.py`. A fuller replay (the seven draws that asked scoping's rewrite, both ways, repeated) is about '$0.15' and awaits the owner's amount. |
| 3 | "None stated" instead of blocking | **Ruled by the owner, option C: the harness proves absence itself.** Built: after a lookup reads a page in full, one cheap call lists the words a document would print where it states each figure or verdict the request asks for, code searches the full text of each page read in full, and where none of the words is on a page the grounding carries a line saying so (the page, its size, its hash, the words). It runs where the `context` node opts in (`answer-and-recompute`, `verify-first`); `full-team`, pinned as the graph arm E ran, is unchanged. The answer may say "none stated" for that ask and only for that ask; a claim with no proof ends the run blocked as a blocked ask does. Not measured on a live run yet: it is built and tested with no spend. What it cannot do: a document that names the thing and gives no figure (X13, X19, X36 of the first hold-out) has the words on it, so nothing is proven and the ask still blocks; only a document whose text has none of the words (X41) can be proven. |
| 4 | A retry on a cut-off answer | Built, PR #316: up to three more attempts, in the three workflows that gate on the check. Reading the two answers the hold-out blocked: X3 draw 1 was cut (the model ended the field on "of" inside valid JSON); X24 draw 2 was not (a `jq` line in a code block was read as open math), so the check was repaired. |
| 5 | Faster PDF reading and a retry of an unread page; a lower effort for the answer-writing call; the reader tier's pin or removal | Explained to the owner; to be taken up later. The reader is set in the owner's `.env` with no serving pin. |
| 6 | A way to see a stale official page | Open, needs a ruling. |
