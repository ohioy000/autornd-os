# The lookup that reads the documents: the comparison (2026-11-15)

Preregistered in `docs/preregistration-20261115-lookup-reads-documents.md`, pushed before the
run.

## The point

- **It did no harm anywhere and was never worse.** With the harness reading the documents itself,
  107 of 107 professional answers were right, and 7 of 8 on the inspection-authorization
  request.
- **It did not show more right answers than the lookup as it is, because this time the lookup
  as it is was right almost every time too:** 62 of 64 on the harder set, against 47 of 51 this
  morning. Two of the five bars were not met for that reason.
- **It does what it was built for.** Of the quotes on pages that were read, 97 percent were
  found, against 66. The governing passage reached the answer step in at least 73 percent of
  harder-set runs, against 52. It costs 18 percent less an answer.
- **On the owner's own request the pattern held again.** The governing sentence was handed on in
  7 of 8 runs and all 7 answers were right. In the eighth the search named the wrong sections,
  the sentence was not handed on, and the answer was wrong. The lookup as it is was wrong twice
  in 8.
- **One thing got worse: the cautions.** Not one of the 62 harder-set answers came without a
  caution. The cautions were written for a model's hand-picked quotes and misfire on the
  harness's own excerpts.
- **Cost:** '$2.459', inside the '$3' the owner approved. About '$8.96' is spent in all, '$1.96'
  beyond the first '$7'.

## What happened in the run

A network outage on the machine, about a third of the way through the first phase, blocked every
later answer in both arms with a name-lookup error. Blocked answers cost almost nothing. The
harder set was run twice more in both arms, and the other runs were run after the network came
back. Every completed answer is counted, so the harder set has 64 answers as the code is and 62
with the new lookup, not 51 each. A stated departure from the plan.

## The figures

Answers right, read by hand; one reader (D50 asks for two).

| | As the code is | Reads the documents |
|---|---|---|
| Harder set | 62 of 64 | **62 of 62** |
| First set | 45 of 45 (this morning's record) | **45 of 45** |
| Inspection authorization | 6 of 8 | **7 of 8** |
| Cost an answer, harder set | '$0.0142' | '$0.0117' |
| Quotes found, of those on pages read | 106 of 160 | 724 of 743 |
| Quotes on pages not read | 50 | 87 |
| Governing passage in the found text, harder set, at least | 33 of 64 | 45 of 62 |
| Harder-set answers with no caution | 5 of 64 | 0 of 62 |
| Answers carrying a "verified" line, harder set | 18 | 25 |

- The two not right as the code is: one PFOA answer without the rule's own mg/l figure, and one
  answer on the EPUB question that declined to answer for want of grounding.
- The flight-attendant question was right 4 of 4 in both arms. This morning it was 0 of 3 as the
  code is. Same code, same question.
- "At least" for the governing passage: the run's record keeps the first 600 characters of each
  quote and the new lookup's excerpts are up to 1,200, so the count for it is a lower bound.

## The bars

| | Stated | Result |
|---|---|---|
| 1 | harder set: at least 2 more right than `now`; H1 at least 2 of 3 | **Not met.** `now` left only 2 to gain and the new lookup gained both; H1 4 of 4 in both |
| 2 | first set: at least 43 of 45 | **Met.** 45 |
| 3 | inspection authorization: at least 7 of 8 | **Met.** 7 |
| 4 | the governing passage in the text handed on in at least 85 percent of runs | **Not shown.** At least 83 percent over 115 runs; the record cuts the excerpts short |
| 5 | costs no more an answer | **Met.** 18 percent less on the harder set, 17 on the request |

| Prediction | Result |
|---|---|
| 1. Bars 1, 2 and 5 are met | **Wrong on bar 1** |
| 2. Bar 3 is missed by one | **Wrong.** Met |
| 3. Bar 4 lands between 80 and 90 percent | **Held,** as a lower bound |
| 4. Fewer cautions with the new lookup | **Wrong.** More: 121 on 62 answers against 104 on 64 |
| 5. H9 is where the least is handed on | Not read out; H9 was right 4 of 4 |

## What it shows

1. **Reading is solved by this build.** Quotes are the page's own words, so the table, mark and
   stitching mismatches of the last three days do not arise: 19 of 743 quotes on read pages
   failed the check, against 54 of 160.
2. **Finding is better and not finished.** The one wrong answer with the new lookup is the one
   run where the search named sections that do not hold the answer. Asking for documents, with a
   pointer, brought the governing sentence in 7 of 8 runs on the vague request; the lookup as it
   is found it in 9 of 28 over the last two days.
3. **Right answers cannot separate the two on these sets.** Both are near the ceiling here. The
   honest reading of today's 62 of 64 against this morning's 47 of 51, on the same code, is that
   the lookup as it is depends on what the search model happens to summarise, and swings with
   it. The new one hands on the same pages' text whatever the summary would have said.
4. **The cautions need rebuilding for it.** Of 121 cautions on the harder set, 59 say a found
   passage does not state an answer to its question, and 29 that a page was not read. Both are
   true and both are now about the harness's own choice of excerpts, not about the answer. With
   the text in the harness's own hands the question a caution should ask is simpler: is each
   figure of the answer in the text that was handed on. The confirmations of #264 already ask
   that.

## The architect's advice

- **Make it the default, after the cautions are rebuilt for it.** It was never worse, it is
  cheaper, and it removes the cause of three days of repairs. But a delivery that warns on every
  answer is not fit to ship as it stands.
- **Rebuild the delivery around the handed-on text:** say which figures stand in it; warn when a
  figure does not, when handed-on passages give different figures for the same thing, and when
  nothing could be read. Drop the cautions about passages beside the point and about counts of
  quotes. This takes in the four small remedies of the hard run's report, and the removal of the
  passage-over-vote rule.
- **Then the finding half:** fewer pages lost to refusing sites (87 quotes here), and a second
  request for documents when none of the fetched pages holds the pointer's words.
- **And a harder test of right answers.** These sets are now near the ceiling for both lookups.
  The difference will show on questions like this morning's flight-attendant one, where the
  summary misleads; a set built of those is the measurement that can separate them.

Nothing is switched on. `lookup_reads_documents` ships off.
