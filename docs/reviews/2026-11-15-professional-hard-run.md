# The harder professional set's first run: 47 of 51 right, and what the changes did (2026-11-15)

Preregistered in `docs/preregistration-20261115-professional-hard-run.md`, pushed before the run.
The owner's question for it: did the recent changes help, or make more trouble than they are
worth.

## The point

- **47 of 51 answers are right, 1 is right in its figure and wrong in its form, 3 are wrong.**
  Read by hand against the keys.
- **All 3 wrong answers are one question, H1,** and wrong the same way: 9 hours of rest for a
  flight attendant, where the rule has said 10 since 2022. The regulator's own FAQ page still
  says nine, two sister rules still say 9, and the search quoted those. Each was found on its
  page, word for word. **A passage found on its page can be out of date, or from the wrong
  rule.** Nothing in the harness checks for that.
- **The recent changes did no harm in this run, and little good.** No "verified" line stood
  beside a wrong figure. But this run shows how one could, and how the rule that takes a found
  passage over the vote could silence a true alarm. The architect advises taking that rule out.
- **The trap was answered rightly 3 times of 3,** and every format was read: the EPUB, both
  PDFs, the CSV. The search found the EPUB edition every time.
- **Cost:** '$0.754' against '$0.80' expected. About '$6.17' of the owner's '$7' is now spent.

## What was run

- `evals/professional/hard-questions.json`, version professional-hard-1, sha256
  `5a06619d3bce…`: 17 questions, three answers each, through `answer-and-recompute` on main
  `0212510` with the set's runner entry. The owner's `.env` of the date.
- **Traces,** copied byte-identical: `docs/traces/20261115T-professional-hard-*` (`shard-0`
  `5ca466cb22db…`, `shard-1` `cc8a98069dc4…`, `shard-2` `a9dbfa29307f…`, the exported run rows
  and the header).

## The reading

One reader, the architect. D50 asks for two; a stated departure.

| Question | Right of 3 | Note |
|---|---|---|
| H1 flight-attendant rest | **0** | 9 hours, three times. The rule says 10 |
| H2 driver alcohol limit | 3 | |
| H3 small drone weight | 3 | each says "less than", not "55 or less" |
| H4 UK annual leave | 3 | one gives 5.6 weeks without the 4 + 1.6 behind it |
| H5 VFR minimums (table) | 3 | |
| H6 DNS limits | 3 | |
| H7 silica limits | 3 | |
| H8 PFOA limit (table, 2024) | 2 | one gives 4.0 ppt as "how the rule lists it"; the rule lists 0.0000040 mg/l |
| H9 CVE score (JSON) | 3 | |
| H10 status code 425 (CSV) | 3 | |
| H11 Previous Question (EPUB) | 3 | |
| H12 LM317 datasheet (PDF) | 3 | |
| H13 SI Brochure (PDF) | 3 | |
| H14 glider fuel reserve (the trap) | 3 | each says the section sets none for gliders |
| H15 flash point 65 °C (reasoning) | 3 | |
| H16 trucker's break (colloquial) | 3 | |
| H17 public dose limits | 3 | |
| **All** | **47 of 51** | plus 1 partly right, 3 wrong |

## H1, the one that went wrong

The three runs went wrong three different ways, and each says something.

| Run | What the lookup found on a page | What happened |
|---|---|---|
| 1 | The regulator's FAQ: "at least nine consecutive hours" | The search also quoted the current rule's 10-hour sentence, and the quote check marked that one **not found**. The outdated page was the only verified source |
| 2 | Two sister rules (fractional ownership, commuter operations), both "at least 9", and the FAQ | The search never quoted the airline rule's own paragraph. Right words, wrong rule |
| 3 | The current rule's 10 hours, **and** the FAQ's nine, **and** the 2012 edition's 9 | The answer chose 9. Two of three vote samples said 10, and the vote flagged the answer. A true alarm |

- In runs 1 and 2 all three vote samples also said 9. The samples share the model's memory of
  the old rule, so the vote agreed with a wrong answer.
- The delivery's cautions on runs 1 and 2 were about quotes in general. Nothing pointed at the
  figure.

## What the recent changes did

**The "verified" lines and the dropped vote cautions (#264).** Rebuilt both ways from the same
runs:

| | Without | With |
|---|---|---|
| Cautions on the 51 answers | 87 | 85 |
| Answers with no caution | 4 | 5 |
| Answers carrying a "verified" line | – | 8 |
| "Verified" lines beside a wrong figure | – | **0** |

- All 8 answers with a line are right. On harder questions the line appears much less often than
  on the first set (34 of 45), because the governing passage is found less often.
- **A near miss.** In H1 the found passages said "9 consecutive hours" and "nine consecutive
  hours". The wrong answer's 9 was not counted as backed only because a single digit must have
  its word right beside it, and "consecutive" stood between. Had the limit been 12 hours, the
  wrong answer would have carried a "verified" line. The line says the figure stands in a found
  passage, which would have been true, and would have misled.
- **The rule that takes a found passage over the vote would then have silenced run 3's true
  alarm.** It has never fired on any of 184 recorded answers. Its one near case would have been
  harmful.

**The quote check's fixes (#256, #259, #264).** They held: no passage was matched that should
not have been. But harder sources brought new misses. 60 of 181 quotes were read and not
matched, against 11 of 92 on the first set:

- a superscript written with carets ("µg/m^3^"): it cost H7 its passage in 3 runs of 3;
- a table whose first line lacks its opening bar, so it is not read as a table (H8);
- a JavaScript page whose text the fetch does not see (H9: 0 of 8 quotes);
- a table quoted with "<br>" inside its cells (H12).

**Site flagging (#261).** On in every run, so there is no comparison. It behaved: no site that
had been read was listed. 22 quotes were on pages not read, 9 of them osha.gov.

**A defect of the architect's own, from #256.** When a lookup quotes nothing at all, the
delivery says "no page it quoted could be read". It should say that nothing was quoted. Seen
twice (H13). Wording only.

## The vote

Two flags in 51 answers: one true (H1, run 3) and one false (H11: three samples said "majority",
the rule of the US House, against the manual's two-thirds). Over the two professional runs: 3
flags in 96 answers, 1 true and 2 false.

## The predictions

| | Stated | Result |
|---|---|---|
| 1 | 36 to 45 of 51 right | **Wrong.** 47 |
| 2 | the trap right at least 2 of 3 | **Held.** 3 |
| 3 | the EPUB edition quoted at most 1 run of 3; answer right at least 2 | **Wrong, and held.** Quoted and found 3 of 3; right 3 |
| 4 | unnamed rules find their passage in at least 20 of 30 runs | **Missed.** About 18, by the free figure check |
| 5 | H1 or H8 draws the older figure at least once | **Held.** H1, three times |
| 6 | no confirmation beside a wrong figure | **Held,** narrowly; see the near miss |
| 7 | at most half the wrong answers carry a caution that points at the wrong part | **Held.** 1 of 3 |

## What the architect advises

Free code, each the owner's ruling because it changes what the delivery says or what counts as
checked:

1. **Take out the rule that puts a found passage over the vote.** Never useful on the record,
   and harmful in the one case that came near.
2. **Do not say "verified" when the found passages disagree.** If one found passage holds the
   answer's figure and another holds a different figure for the same thing, say that the sources
   differ, as a caution. That is the H1 case, and it is the first caution that would have
   pointed at the wrong figure.
3. **Read carets as marks,** like the tildes: "m^3^" for "m3". It would have kept H7's passage.
4. **Fix the wording** when a lookup quotes nothing.

And the larger matter, not a quick fix: **the harness trusts a passage because it is on a page,
not because the page is current or is the right rule.** An official page that was never updated
defeated the lookup, the quote check and, twice, the vote. Preferring the rule's own text over a
page about the rule, and noticing when found sources disagree, is the next core problem this run
points to.
