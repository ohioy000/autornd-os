# Carryover: 2026-11-14 to 2026-11-15

For whoever picks this up next. It says what these two days found, what is live and what is
switched off, and the plan the owner approved on 2026-11-15. Main is at `10c39f4`. The suite is
2024 tests (2023 passed, 1 skipped), network guard 0. Pull requests #251 to #268 were merged.

## The goal

A **general** harness that lets low-cost models answer expert questions correctly and says
honestly what it checked. The owner's target is professional use: precise questions that name
their rule or standard. Work on vague requests was dropped on the owner's word.

## What the two days found

1. **The root of the wrong answers is what text reaches the answer step.** The lookup was one
   call to a search model that chose the pages, summarised them and quoted them; the harness only
   checked the quotes afterwards. With the governing source's own text handed on, 8 of 8 answers
   were right on two questions that had been wrong 8 times
   (`docs/reviews/2026-11-15-root-cause.md`).
2. **The root has two halves.** *Reading:* hand on the pages' own words. *Finding:* decide which
   pages to fetch. The first is built; the second is better and not finished.
3. **A passage found on its page can be out of date or from the wrong rule.** A regulator's own
   FAQ said nine hours where the rule has said 10 since 2022, and was found word for word
   (`docs/reviews/2026-11-15-professional-hard-run.md`).
4. **Small lookup tests mislead.** The same code scored 0 of 3 and 4 of 4 on one question the
   same day, and 47 of 51 then 62 of 64 on one set. Set at least 12 runs a side on anything that
   matters.
5. **Dead ends, parked:** the claim check (a check after the answer cannot supply a sentence the
   lookup never found); typed search queries as a patch on the old lookup; holding back
   unverified lookup answers; ending a run when nothing is verified.

## What is live

| Change | Since |
|---|---|
| A quoted table is read row by row by the quote check | #256 |
| A quote on a page that could not be read is not counted against the lookup, and is said apart | #256 |
| The quote check drops a search model's own marks: stars, heading hashes, tildes, a backslash before a mark, a leading list mark | #259, #264 |
| `lookup_avoid_unreadable`: a site that refuses twice, and was never read, is named to later lookups | #261 |
| `confirmations` in the delivery: asks whose figures stand in a found passage; the vote's could-not-compare cautions are dropped for them | #264 |
| ~~A found passage is taken over a disagreeing vote~~ Removed in step 1 | #264 |
| Cautions rebuilt around the text handed on: a figure on no page, two pages that differ, quotes no longer counted | step 1 |

## What is built and switched off

| Setting | What it does | Why it is off |
|---|---|---|
| `lookup_reads_documents` | The search model is asked where the answer is written; the harness fetches those pages and hands on stretches of their own text as quotes (`_ask_documents`, `_excerpts` in `autornd/knowledge/research.py`) | Never worse than the old lookup (107 of 107 professional answers, 7 of 8 on the owner's request), 18 percent cheaper, 97 percent of quotes found against 66. **On by default since step 2** |
| `lookup_withhold_unverified` | A lookup answer with no found passage stays in the record and out of the phases | An unverified lookup answer was still right about three times in four |

Also in the tree, for measurement only: `workflows/answer-and-recompute-claims.yaml` (the claim
check, in shadow).

## The question sets

| Set | File | State |
|---|---|---|
| First professional set, 15 questions | `evals/professional/questions.json` | Frozen, professional-1 |
| Harder professional set, 17 questions | `evals/professional/hard-questions.json` | Frozen, professional-hard-1 |

`evals/professional/verify_keys.py REPO [FILE]` checks every key passage on its live source. The
answer runner takes them as `MEASURE_SET=professional` and `professional-hard`. Neither has an
automatic screen: a run is read by hand against the keys.

## The plan, approved by the owner on 2026-11-15

In this order. Steps 1 to 3 are free code. Step 4 is a paid run with the owner's approval of
'$3'.

### Step 1. Rebuild the cautions around the text the harness hands on

**Done 2026-11-15.** See `docs/reviews/2026-11-15-cautions-on-handed-on-text.md`. Step 2 is next.

- **Say** which figures of the answer stand in the handed-on text (the confirmations of #264).
- **Warn** when a figure of the answer does not stand in it.
- **Warn** when handed-on passages give different figures for the same thing. This is the
  flight-attendant case, and the first caution that would have pointed at a wrong figure.
- **Warn** when nothing could be read.
- **Drop** the caution that a found passage does not state an answer to its question, and the
  cautions that count quotes found.
- **Absorb the four small remedies** of `docs/reviews/2026-11-15-professional-hard-run.md`:
  remove the rule that takes a found passage over the vote; the sources-differ caution above;
  read carets as marks ("m^3^"); fix the wording when a lookup quotes nothing (today it says
  "no page it quoted could be read").
- **Prove it free, before it ships,** on the recorded runs in `docs/traces/20261115T-documents-*`
  and `20261115T-professional-*`, with `docs/probes/verified_by_source_replay.py` as the model:
  right answers should mostly come clean, and the recorded wrong answers should each carry a
  caution that points at the wrong part. No wrong figure may carry a "verified" line.
- Where the code is: `_cautions`, `_backed`, `_stands`, `_over_the_vote`, `_confirmations` in
  `autornd/api/routes.py`; the dashboard shows both lists.
- One thing to settle in the build: the run's record keeps only the first 600 characters of each
  quote (`SOURCE_RECORD_QUOTE_CHARS`), and the new lookup's excerpts run to 1,200. A check of
  figures against the handed-on text needs the whole excerpt in the record.

### Step 2. Switch the new lookup on by default

**Done 2026-11-15.** The suite keeps the older lookup, by a stated choice in `tests/conftest.py`:
46 tests drive that lookup's quote check, second round and record. Step 3 is next.

`lookup_reads_documents: bool = True` in `autornd/config.py`, with the measurement in its
comment, `tests/conftest.py` to match, and the one test that asserts the default.

### Step 3. Finish the finding half

- **Fewer pages lost to refusing sites.** 87 quotes were on unread pages in the comparison. The
  refusing sites are already remembered; the document request should be told them from the first
  call, and osha.gov's rules have readable copies on ecfr.gov.
- **A second request for documents** when none of the fetched pages holds the search model's own
  pointer words, or no page could be read. Once, as the old lookup asked once more.
- The one wrong answer of the comparison is the test case: the search named sections 65.83 and
  65.87 where the answer is in 65.91.

### Step 4. A sharper test, '$3' approved

- Both lookups are near the ceiling on the two professional sets, so those cannot separate them.
- **Write a set of questions where a summary misleads,** like the flight-attendant one: a rule
  that changed recently while older pages still stand; a figure that differs between sister
  rules; an official page that disagrees with the rule's text; a rule superseded by a later one.
  Each key is written from the live source and checked by `verify_keys.py`. **The keys need the
  owner's sign-off before any run** (D44).
- **Run both lookups on it,** at least 12 answers a question a side, with the amount and a stop
  stated in a preregistration pushed before the run, inside the '$3'.

## Money

About '$8.96' is spent. The owner first set '$7', then approved '$3' for the comparison
('$2.459' was used), and on 2026-11-15 approved a further '$3' for step 4. The owner has said the
budget is not to hold the work back. Every paid run still states its amount and stop before it
spends.

## Things that bite

- **Waiting for a run with `pgrep -fc` inside the same shell hangs:** it matches itself. Wait on
  the logs' line counts.
- **A probe must name its database before it imports the engine,** or its rows go to the
  default `autornd.db` (`docs/probes/root_cause_probe.py` shows the order).
- **More than about five processes fetching ecfr.gov at once draws challenge pages.**
- **The network can drop mid-run.** A run of "blocked" answers at zero cost with a name-lookup
  error is the machine, not the harness. Count completed answers and rerun the rest.
- **A new model-call site must be registered** in `tests/prompt_capture.py` and the prompt
  fixtures re-captured with `WRITE_GOLDEN=1`; a new setting must be listed in
  `tests/conftest.py`; the general profile forbids engineering-only words in prompts.
- **The free figure check in `professional_baseline_analysis.py` is a pointer, not the result.**
  It called three wrong answers right. Read the answers.

## Waiting on the owner

- **A quote broken by a row of dots:** may it be checked piece by piece? It loosens D56 (3). It
  matters less once the new lookup is the default, since its quotes are the page's own words.
- **A second reader.** Every reading in these two days had one reader. D50 asks for two.
