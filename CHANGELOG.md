# Changelog

All notable changes to AutoRnD will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

Added (2026-11-23, the owner's instruction to plan and implement a fix for the warning flaw; on a branch, for the owner's ruling):
the delivery says what the answer itself leaves open, read off its typed fields and never off its prose. An ask of kind value or
verdict with no typed result and no claim that the document states none, a `blocked_on` note the run completed on, an ask the
answer reports as not stated (with what the check behind that was), and an answer text under 30 words beside typed results each
add a caution that names the ask or the text. Replayed over the 681 labelled answers of four runs, the new cautions stand beside
8 of the 658 right answers (1.2 percent) and 5 of the 23 that were not right, each pointing at the part that was wrong, where the
shipped cautions stand beside 25 percent of the right and 35 percent of the not-right and rarely at the wrong part; 11 of the 23
still come clean. The five are in-sample, and the review says why free checks cannot reach the rest and what two paid levers would
cost to measure. 30 new tests, each of 16 guarded lines broken once. Nothing is paid for and no answer changes. The record is
`docs/reviews/2026-11-23-caution-flaw.md`, and `docs/probes/caution_replay.py` reproduces every figure from the committed traces.

Fixed (2026-11-23): the suite's one warning, a class-level asyncio mark on a class that holds one async test and one that is not.

Changed (2026-11-22, the owner's ruling: "make sure any model can be used for any tier ... plug and play"): the spend guard bounds
any catalogue price at its highest rate instead of leaving a model blind. The worst case now takes, for each side of a call, the
highest rate across the entry and its time-of-day or prompt-size `overrides`, with every cache component counted on the prompt
side and the reasoning rate on the completion side; only a charge it cannot read (a component it does not know, a price that does
not parse) leaves a model unrated, and the log names it. The tier-3 and tier-4 preflights read the same function. Read on the live
catalogue of 2026-11-22: 476 of 476 entries are bounded where 12 were blind to a component the bound did not know, and two of the
five answer models of the line-up smoke had been running unbounded. Five tests that enshrined "unrated above its side's rate" are
rewritten and 15 new tests pin the shapes, each guarded line broken once.

Added (2026-11-21, the owner's instruction): a profile can name its own model for a tier. `PROFILE_MODELS`
(empty by default) reads `<profile>:<tier>=<model-id>[@<provider>]`, comma separated; a pin changes that tier for
that profile and no other, does not carry through `base:`, and brings its own serving. Every place that reads a
tier reads the pin first, the start-up check confirms and rates every profile's pin, preflight checks each pin
(and learned the reader tier it was missing), the eval run's header records the effective model map, the
profile and the pins, and a unit's record now names the model each reply came from beside its provider
(`models_by_function`). With the setting empty nothing changes: every accessor equals the old expression across
all ten profile files. The README has a new section, Choosing Models.

Added (2026-11-21, the owner's instruction): four field profiles, `legal`, `finance`, `medical` and `science`,
each a standalone team with three subjects, five roles, its own examples and a constraint that its output is a
draft for a qualified person to review and is not advice. None names a model.

Changed (2026-11-21, the owner's instruction): the prompts are written in the profile's words where they were
written in engineering's. The triage risk guide's worked examples, the sentence that defines a hazard, the
decision switches' questions, the phrases that mean a request asks for its sources and the escalation prompt's
names and labels are now profile words (29 framing keys became 35). Engineering and the profiles built on it
send exactly what they sent: every prompt site, captured under all of them, is byte-identical to the build
before. `general` is now the universal profile, with examples from several fields where it taught with
physical-engineering ones, so a checkout that ran with no profile set now sends different examples; set
`AUTORND_PROFILE=engineering` for engineering R&D. `studio` and the four field profiles teach with their own.
The risk guide's rules are the same text under every profile.

Measured (2026-11-21, '$0.2251' of the owner's '$1.00'): the triage risk guide under each profile on the wide suite,
36 sectors at five repeats, against main's text. By the rules written beforehand, `studio` and `science` held; the
tuned text of `legal`, `finance` and `medical` did not (10, 24 and 18 of 180 units read a sector below its risk
floor, against none for the control, with a margin of 3), because their examples hold no physical-hazard case and
the profile then read such requests low; and `general` met the risk bounds on 169 units against 174 (2 past the
margin, all of them over-calls, none below a floor). Those four texts are held for the owner's ruling and are not
claimed to hold. Engineering is unaffected. See `docs/reviews/2026-11-21-per-profile-pins-and-tuned-prompts.md`.

Measured (2026-11-22, '$0.9275' in all with the repeat and the effort test below, the owner's instruction): the same suite and the same held texts with a different
triage model, its thinking off and on. With its thinking off that model under-called more than the first (41, 51 and 15
units below a floor for finance, medical and legal, and 6 for the old guide); with its default thinking the old guide held
(0), and the finance and legal texts read within the margin of it (1 and 1) while medical still read dentistry below its
floor (6 units, in an arm cut at its spend cap); `general` held in both. Default thinking cost two to three times the first
model per run and took about 19 seconds a call. A repeat of the old guide, finance and legal with default thinking ('$0.2454',
three complete arms) held again (the old guide 1 unit below a floor and 171 meeting the bounds, finance 1, legal 0), so by the rule
written beforehand the finance and legal texts are supported on that model with its default thinking. The first model was then read at high reasoning effort
('$0.2567', three arms, 11 units lost to the provider's rate limit): finance 9 units below a floor and legal 8 (24 and 10 at its
default effort), so more thinking alone did not bring the texts within the margin and the second model reads them better at the
same amount of thinking. The medical examples were then fixed after the dentistry readings were read (a material or device chosen for a
procedure on a patient is now a high example) and read in one arm with default thinking ('$0.1176', 180 units, no errors): 2 units below a
floor, 173 meeting the bounds, dentistry read `high` on 5 of 5 repeats, so by the rule written beforehand the medical text is supported on
that model at one run (the dentistry result is not independent, the fix having been written after its readings). Nothing ships on it. A model line-up
smoke (a '$1.00' ceiling, five runs, '$0.1183' spent) then ran each tier and model combination once: the global answer model, a newly listed
large model on the engineering profile, another on finance and on medical, the legal model, each served by its one provider with typed output intact
and its answer cost equal to the catalogue figure; the spend guard could not bound two of the five answer models (the global one for time-of-day
price overrides, the newly listed large one for a cache-write rate above its prompt rate), which is the subject of a separate change. See
`docs/reviews/2026-11-22-model-lineup-smoke.md` and `docs/reviews/2026-11-22-triage-model-hy4-flash.md`.

Changed (2026-11-22, the owner's sign-off): the second hold-out set, `evals/professional/holdout2-questions.json` (`professional-holdout-2`), is signed and frozen with 174 questions, down from the 181 of the draft: the owner signed the keys (D44) and ruled that the questions a Haiku reading found really defective be dropped. Haiku (a different model family from the two that wrote and checked them) read all 181 once, groups 1 to 9 on 2026-11-21 ('$2.3669', 125 questions, the catalogue's price for it was five times too low and the run stopped at the budget) and groups 10 to 13 on 2026-11-22, with the checkers now told the date ('$1.663', 56 questions): 134 OK and 47 FIX. About a dozen of the FIX verdicts were the date premise the checkers had taken for the future, and many others were wording nits or notes that call the answer correct; seven were real and were dropped, `Y10` (a confusion note mislabels a date), `Y55` (it names ECMA-404 passages that were not supplied), `Y87` (omits that the rule applies only to installations after 13 August 2007), `Y93` (puts a frequency-window passage under the Quebec variance), `Y96` (calls a use requirement a scope sentence), `Y97` (a trap that says no numeric limit is stated, where the same section gives a table in dBuV) and `Y107` (says each container where the paragraph covers containers of 2 lb or less for motor-vehicle air conditioning). With `Y48`, held back by the script, 8 ids are withheld and each says why in the file's `withheld`. The runner accepts the set now (its status no longer says Draft) and still refuses a draft. `tests/test_holdout2_draft.py` became `tests/test_holdout2_set.py` (7 tests: the file's sha256 is the signed one, the ids, the withheld reasons, the status, the registration and the runner's draft refusal; each of 5 guarded lines proven by breaking it, 5 of 5 fail their test, files restored). Authoring and checks cost '$8.1881' in all of the '$8.6' the owner approved ('$6.6', then about '$2' more). No harness test was run, at the owner's word to hold it. Counts re-derived: 2,338 tests in 101 files.

Changed (2026-11-22, the owner's ruling that the checkers be told the date): the checker calls of `evals/professional/write_holdout.py` now say "TODAY is <the run's date>. The pages below were fetched today or in the days just before it." after the first paragraph of the tail added to Prompt B; nothing else about Prompt B or what the checkers check changes, and the author's prompt is untouched. The author was told the date (Prompt A's `{DATE}`) and wrote "as in force on 2026-11-21"; the checkers were not, took it for a date in the future, and held questions back for it: about a dozen of the 33 FIX verdicts of the Haiku reading of groups 1 to 9 on 2026-11-21, and the Flash readings' "as in force on a future date". 2 new tests; each of 3 guarded lines proven by breaking it (3 of 3 fail their test, files restored). Counts re-derived: 2,336 tests in 101 files.

Added (2026-11-21): the second hold-out set as a draft, `evals/professional/holdout2-questions.json` (`professional-holdout-2`, status "Draft, not approved"), 181 questions of the 182 asked, `Y1` to `Y182` without `Y48`, thirteen groups of 14: the six areas of the first set, three engineering subjects, and law, finance, medicine and natural science, written and checked by models through `evals/professional/write_holdout.py`. Each of the 181 passed the code check (every cited passage found word for word on its page by the harness's quote check, every non-derived figure of its key on a cited page) and two readings by the worker with whole pages, and `evals/professional/verify_keys.py` found every passage and figure of the 181 on the live pages on 2026-11-21 ('181 of 181 hold'). `Y48` was held back after two repair rounds, for a nit in its key ("(dimensionless)" added to a numeric answer). 50 PDF pages of 9 groups were opened and extracted again with PDFium before the last readings. The set is registered in `docs/probes/short_workflows_measurement.py` as `professional-holdout-2` and the runner refuses it while its status says Draft (D44): the owner signs the keys first. `tests/test_holdout2_draft.py` (5 tests) pins the draft's shape, its registration and the refusal, each proven by breaking it (4 of 4 fail their test, files restored). The authoring cost '$4.1581' in all, of the '$6.6' the owner approved. Counts re-derived: 2,334 tests in 101 files.

Fixed (2026-11-21, found on the second run of the second hold-out's checks; instrument repair): in `evals/professional/write_holdout.py` a check call no longer cuts the pages it carries where a smaller call would carry them whole, and a repair's re-check is no longer skipped over an older saved one. Every question of a group used to go to the checker in one call with each page given an equal share of 2,400,000 characters, so on the 182-question set the checkers answered "the page is cut here, I could not check" about 15 questions in 4 groups (the MiFIR, PSD2 and EMIR texts, two eCFR parts) whose passages code had already found word for word on the page, and that held them back; `check_batches` now packs the questions into calls while their pages, counted once each, fit inside the limit (a question whose pages alone pass it goes by itself and is cut as before), the second reading goes through the batches the other way round, and one file holds every batch's verdicts. And `check_group` skipped a re-check whose file was saved, so the second repair round's questions were never read again and the first round's verdicts stood for them; the repair now forces its re-check. Nothing about what a verdict means or which question is accepted changed. 7 new tests, each of the 7 guarded lines proven by breaking it (7 of 7 fail their test, files restored). Counts re-derived: 2,329 tests in 100 files.

Changed (2026-11-21, the owner's ruling that the PDFium swap be built): a PDF is now read by PDFium (the `pypdfium2` package) and no longer by pypdf. The reading processes of `autornd/knowledge/pdf_read.py` (a worker per stripe of pages, `pdf_worker.py`) run PDFium for every PDF, one process for a small one (under 250,000 bytes) and `workers()` stripes for a large one; pypdf in a thread is kept only for where processes cannot start. Measured on the 16 sample PDFs that gave no answer in earlier runs, alone on this laptop with 4 processes: PDFium 0.3 to 3.4 s against 3.8 to 130 s for pypdf in one thread, 9 to 39 times faster (the largest, 2.8 million characters, 3.4 s against 130 s); read together under the fetch's 60 s as a lookup does, six PDFs once not read in time were all read by 2.8 s and six heavy ones by 7.1 s (traces `docs/traces/20261121T-pdfium-read.jsonl`, sha256 54c52084765f2f499d3e9f9eb3b6f791c7e034fd92cb87d59b2e572a17771c98). PDFium is not thread-safe (two threads at once crashed the process), so it only runs in a process, and a process killed by a signal is a failed read named `WorkerExit-<signal>`. A document with a password is named from PDFium's own error code, and one locked only against editing opens without a word as before. Its text differs from pypdf's: the mark it leaves where a line ended in a hyphen is written as the hyphen, line ends are line feeds, and spaces fall elsewhere, so 53 of the 356 passages the second hold-out's extract kept from pypdf text (13 of 35 PDFs) are not found word for word in it, and all 53 are found once whitespace is ignored (`docs/traces/20261121T-pdfium-passage-parity.jsonl`, sha256 b5d2c123c5335218f68c1d5afe0a6cb68f82764ebb666ace6dd3873f736430cb): the PDF pages of the questions run are opened and extracted again after this merges. Tests: 8 new, 10 changed lines proven by breaking them (10 of 10 fail their test, files restored). Counts re-derived: 2,322 tests in 100 files.

Added (2026-11-21, the owner's instruction to add legal, finance, medical and science as new subject selections with as many questions each as before, to take the author's ceiling to 130,000 tokens and to change the author model): `evals/professional/write_holdout.py` has four new groups of 14, 10 law, 11 finance, banking, securities and tax, 12 medicine and clinical practice and 13 natural science, so the set is thirteen groups, `Y1` to `Y182`; each is described by its topics and by the free publishers at stable addresses to draw on (group 9's lesson), and the medical and science groups name the areas Prompt A already lists as covered. The author's ceiling (write and fix, and the plan's model) is 130,000 completion tokens; the worker's stays at 65,536, which its endpoint cannot pass. The model change is on the command line, as always. Smoke test of group 10, run before this change was merged, on the new author at its default thinking, pinned to its cheapest 4-bit endpoint: the plan named 30 documents in 1,625 tokens ('$0.0138', thinking-off honoured), 22 opened and gave passages, the write of 14 questions used 24,598 tokens in 148 s and finished ('$0.2086'; the earlier author at default thinking spent all 65,536 tokens on thought and returned nothing), two readings by the worker at default thinking took 8,501 and 11,108 tokens ('$0.0178' for both), nothing was flagged by code or by either reading, and the 14 questions were read by hand against the sources. The whole group cost '$0.2544'. The three new tests of the line-up were widened from three groups to seven and the ceiling test now names both ceilings. Counts re-derived: 2,314 tests in 100 files.

Changed (2026-11-21, the owner's instruction for the questions run of the second hold-out: not to cap the
tokens, to let it cook, and not to tinker with how hard a model thinks): in
`evals/professional/write_holdout.py` the author's ceiling (the write and the fix) and the worker's (the
extract and the checks) are now 65,536 completion tokens each, the most either pinned endpoint gives
(the provider's public catalogue, 2026-11-21), where they were 48,000 and 16,000; and `--effort-author`
and `--effort-check` now default to `default`, which sends no reasoning option, so the provider's own
setting applies, where they were medium and low. The reasons for the old numbers: a write with thinking
on spent all 48,000 tokens on thought and returned nothing ('$0.0642'), and one check at the low level
was cut at 16,000 where the others used 11,000 to 15,000. The plan keeps its 5,000-token ceiling and its
thinking off, and the extract keeps its thinking off, as measured; a level given on the command line is
still sent as it was given. The reply wait of 900 s holds for a reply at the new ceiling (about 550 s at
the slowest rate measured). 9 new tests, and each of the 22 guarded lines was proven by breaking it (22 of
22 fail their test, files restored byte-identical). Counts re-derived: 2,310 tests in 100 files.

Changed (2026-11-21, the third live stage of the second hold-out's authoring): the description of group 9
(civil, structural and geotechnical engineering) in `evals/professional/write_holdout.py` now names the
families of address a model can recall: the eCFR texts of 23, 33 and 44 CFR, the Building Regulations
approved documents on structure and ground, USGS reports at pubs.usgs.gov and NIST technical notes at
nvlpubs.nist.gov. Of the 30 documents the plan named for that group, 22 were addresses that do not exist
(HTTP 404, deep file paths of FHWA, FEMA and NRCS made up from memory) and four more rounds opened one
page each (11 of 95 named), where the other groups opened 13 to 30 of their first 30. Nothing else changes and no
test changes: the tests that guard the groups' detail and numbers hold as they were. Counts unchanged:
2,301 tests in 100 files.

Fixed (2026-11-21, the second live stage of the second hold-out's authoring): with thinking off, the
author model still named far more documents than the plan asked for, 91 and 161 where 30 were asked, and
five of nine replies stopped at the 12,000-token limit and were thrown away whole ('$0.0761' for
nothing, '$0.2484' in all on the authoring so far, inside the owner's '$3'). The plan now keeps what a
reply finished before its cut (a new `plan_entries`, which also reads a whole reply as before), takes
no more documents than were asked for (every page taken is paid for again when the worker copies
passages out of it), asks for exactly the number wanted with a reason of under 15 words each, and has a
ceiling of 5,000 tokens, since a reply of 30 documents is about 2,500: a reply that runs on now costs
under '$0.01' and is still used. `ask` refuses a cut reply as before unless its caller says it can use
what came before the cut, and only the plan does. 14 new tests, and each of the 11 guarded lines was
proven by breaking it (11 of 11 fail their test). Counts re-derived: 2,301 tests in 100 files.

Fixed (2026-11-21, found by the first live stage of the second hold-out's authoring): the plan call of
`evals/professional/write_holdout.py` asked the author model for a low level of thinking and the endpoint
ignored it, so all nine replies spent the whole 12,000 tokens on thought and returned nothing ('$0.1365'
for nothing). One probe each at off, minimal and none, capped at 4,000 tokens, showed that only off
answers (31 documents in 2,405 tokens, '$0.0033'; the other two were cut off with an empty reply, as low
had been), so the plan call now asks for no thinking. The worker model does honour levels (a
checker-shaped call used 71, 368 and 415 tokens at off, low and medium), so its settings stay. The test
that pinned the low level held the setting that does not work and was corrected, not appeased. 4 guarded
lines proven by breaking them (4 of 4 fail their test). Counts unchanged: 2,287 tests in 100 files.

Changed (2026-11-21, the owner's word: "Add to the line up 3 more engineering subjects and be more
detailed than ie electrical systems"): the second hold-out set's line-up in
`evals/professional/write_holdout.py` gains three groups of 14, so the set is nine groups and 126
questions, `Y1` to `Y126`, three times the first hold-out. Group 7 is electrical power systems and
installations, group 8 mechanical, thermal and materials engineering, group 9 civil, structural and
geotechnical engineering. Each is described by its topics and by the kinds of publisher, in 83 to 87
words and not by a label, because the plan call names documents from that text alone and a long list
is what spreads them over the whole subject. The default of `--groups` listed only 1 to 6 and would
have left the three out; it now lists every group in the line-up. Nothing was run with money, and the
authoring had not started, so its cost rises by half. 8 new tests (the line-up and its numbers, the
detail, no shared area, the default, the area and the ids reaching the author, the area reaching the
plan call), and each of the 17 guarded lines was proven by breaking it (17 of 17 fail their test; one
case of the runner matched two lines at first and was made exact). Counts re-derived: 2,287 tests in
100 files.

Added (2026-11-21, the owner's ruling, option C of the "none stated" question: the harness proves
absence itself, and only a proof lets an answer say it; this is known limit 12 of the 0.2.0 release
notes): after a lookup has read a page in full, one cheap call (the triage tier, about '$0.00015' a call
in the hold-out run) lists, for each ask of kind value or verdict, the words a document prints where it
states the answer, and code searches the whole text of each page read in full for them. Where none of the
words is on a page, the grounding carries a line saying so, naming the page, its size, its hash and the
words searched. The search ignores case, spacing, hyphens, a line break in the middle of a word,
ligatures and the many ways a page prints a degree sign or a dash; at least three words are needed and
every one must be absent; a page that timed out, was refused or was read in part proves nothing. The
answer step is offered a typed field, `not_stated`, only where a proof exists, and a proof is made only
where the workflow's context node opts in (`none_stated: true` on the `context` node of
`answer-and-recompute` and `verify-first`; `full-team`, whose file is pinned as the graph arm E ran,
is unchanged, so its grounding, its cost and its prompt read as they did and it still blocks); the check
`blocked_on_unmet` accepts a claim for an ask that has a proof and ends the run blocked on a claim for
one that has none, as it does for a blocked ask, counting both kinds of refusal; with no proof the
prompt is byte-identical to what it was. What it does not do: a proof is a fact about one page as
fetched and only as wide as the words listed, so a document that names the thing and gives no figure
(by their keys, X13, X19 and X36 of the first hold-out are such documents) has the words on it and the
ask still blocks the run; only a document whose text has none of them, as the ATmega328P datasheet has
none of the thermal words (X41), can be proven. Nothing was run with money and no live run has been made:
141 new tests (76 for the search and the words, 61 for the check, the field, the prompt, the workflows
and the whole graph end to end, 4 for the page count a PDF read in processes now reports), and each of
the 134 guarded lines was proven by breaking it on the final tree (134 of 134 fail their own test; at
the first pass, before the opt-in moved to the context node, six did not: three were gaps in the tests
and three were mistakes in the runner's cases, and tests were added or the cases corrected). Counts
re-derived: 2,279 tests in 100 files; the full suite is 2,278 passed and 1 skipped, network guard 0.

Added (2026-11-21, the owner's word: "a full re test with a new set that's twice the size ... write
a simple script using my env so I don't have to show the api key"): `evals/professional/write_holdout.py`,
which writes the second hold-out set (84 questions, six groups of 14) with two models named on its
command line, each pinned to the provider tag given with no fallback, and checks it. Code opens each
page with the harness's own fetch (waiting longer than the harness's 60 s, so the set is not made only
of pages the harness reads quickly); the helper model copies passages out of the pages and code finds
each word for word; the author writes the 14 questions of a group from those passages with Prompt A of
`docs/holdout-2-prompts.md` as written; code finds every cited passage and every figure of the key on
the cited pages; two checks with Prompt B read what passes; one repair round follows; a question reaches
the draft only if both checkers say OK, and every other is listed with its reason. The key is read by the
harness's own client and never by the script (a test reads the source to prove it); money is counted
from a ledger across runs and no call starts that could pass the amount given; `--dry-run` asks nothing
and estimates the cost. 54 tests with no network and no spend, each guard proven by breaking its line
(37 of 37). No call has been made yet: a paid stage needs the owner's word and an amount.

Changed (2026-11-21, the owner's word: "if you think the pdf fix can be done with code great, make
sure it's not a model issue"): a PDF of 250,000 bytes or more is read by up to one process per core
(at most eight) instead of by one thread, each process taking every n-th page and the pages joined
in order; the text is exactly the one-process text (compared on 12 real PDFs). It is not a model
issue: no model is called while a page is read, and read in a process with no network each of 16
PDFs that had gone unread took 8.9 to 134.4 s four at a time on a two-core laptop (3.7 to 47.1 s
for the 12 also read alone on an idle machine), 78 to 100% of it cpu time, so the time is pypdf's
parse. A thread cannot be stopped, so a read that ran past the 60 s limit went on burning the core; a
process is killed when the limit runs out, at most one process per core runs at once across all the
PDFs of a run, and a page that ran out of time now says how far it got ("no answer within 60 s (read
N of M pages)"). Read together under the 60 s limit on a two-core laptop, six IAEA PDFs gave 1 read
before and 6 after (all by 23.5 s), and six heavy ones (three datasheets of 555, 653 and 653 pages,
SP 800-53, a 323-page specification and a 228-page building regulation) gave 0 before and 3 after.
The limit is unchanged, a PDF that still runs out of time still hands on nothing, and where processes
cannot be started the PDF is read in a thread as before. The records are `docs/traces/20261121T-pdf-read-onecore.jsonl`
(sha256 `d25dc068242d2ff942d435213bb1b2c30c345785d3286758fb4a5ded3aa2734a`) and
`docs/traces/20261121T-pdf-read-old-vs-new.jsonl` (sha256
`ca71a0b486d42f1bb4a45e08ea97bfa061e7bfd4917e668c5188bffec064a05a`); the probe is
`docs/probes/pdf_read_benchmark.py`.

Changed (2026-11-21, the owner's word: "also scope the whole question if it's still frugal"): the
first lookup of a run asks the whole request as well as the gaps scoping or the briefing named, as one
numbered line in the same request, through `lookup_questions`; a request past 1,500 characters is a
brief and stands aside, and a request that is already a gap is not asked twice. It stays one search
request that reads at most six pages, so the only cost is one more line of text. Found by reading the
ten X12 draws kept from 2026-11-20 and 21: the three draws that asked the whole question all read IAEA
pages; of the seven that asked scoping's rewrite, which no longer said "international", three read only
US federal rules and gave the wrong answer. The two later lookups (the override's and the second
round's) are unchanged. Measured in part, the same day and with the owner's approved amount, by
replaying the search step alone on the three scoped questions that had led to US-only pages (three
search requests; no page fetched, no answer written): with the whole question first, the first six
addresses named held IAEA documents in all three (3, 5 and 1 of the six), each with the 2025 edition of
SSR-6, which none of the three draws had read. A lead and not a result: three requests, on questions
picked because they failed, with no same-day control, counting pages named and not pages read. The
record is `docs/traces/20261121T-whole-question-smoke.jsonl` (sha256
`d92a059a81b8c6b09efe19fc544faddd57637213cd53dde63783e3deebf90007`), its inputs sit beside it, and
`docs/probes/whole_question_search_replay.py` reads them.

Changed (2026-11-21, the owner's ruling: a retry, three attempts at least, "to have slack for the
routers"): the implement node of the three workflows that gate on a cut-off answer
(`answer-and-recompute`, `verify-first`, `lean`) writes a cut-off answer again, up to three more
times, before the gate sees it, through a new node argument `cut_retries`; a workflow that does not
set it is unchanged, and a text still cut after the last attempt ends the run blocked exactly as
before. Found by reading the two answers the hold-out blocked as cut off (X3 draw 1, X24 draw 2):
X3's is cut, its `summary` field ending on the word "of" inside valid JSON, so the model ended it and
the retry is the fix; X24's is not, it ended on a whole sentence and the check misread two `\(` in a
`jq` line of a code block as open inline math, so `answer_ends_whole` now counts math delimiters
outside code only (an instrument repair: it reported a cut-off where there was none). Both answers
read from their records in the tests; each guarded line shown to fail them when removed.

Changed (2026-11-21, the owner's ruling: medium for the research tier): query expansion and the
briefing ask for medium reasoning effort too, as the request-scoping call already did. A probe the
same day found query expansion at the provider's default taking 24,253 tokens, 189 s and '$0.034' on X12,
where an earlier probe of the same call had used 1,123; the 32,768 ceiling kept it from failing but not
from taking three minutes.

Changed (2026-11-21, the owner's ruling: correctness first): the research tier has its
own output ceiling, `RESEARCH_MAX_TOKENS`, 32,768 where it was chat_json's 16,384, and the
request-scoping call asks for medium reasoning effort. Found in the reader beta: at the
provider's default reasoning the scoping call spent 4,000 to 30,400 tokens (X12: 15,000 or
more, twice returning nothing at the old cap), which cost 650 s and '$0.08' on one unit; at
medium it used 650 to 1,030 tokens, grounding on X12 took 98 s, and four hold-out units run
through it (X4, X12, X22, X34) were each right against the frozen keys, by one reading. The
other two research calls follow in the entry above. A pin test the same day showed the
runaway on three providers and on the Flash model, so it is not a bad provider.

Fixed (2026-11-20, found in the reader beta): an answer that wrote a power
too large for a float, such as "10^400" or "1e999", made the numbers check raise
OverflowError and blocked the whole workflow; such a figure is now skipped as no
figure to compare. The reader model is also asked not to reason, because with
reasoning on it spent its whole output budget thinking and returned nothing;
`chat()` takes an optional `reasoning` argument, absent from the request unless given.

Measured, not changed: on 2026-11-18 a frontier model asked directly, with web
search, was right on all 42 hold-out questions where the harness was right on
113 of its 126 answers, at about nine times the cost an answer. The 0.2.0
claim of equivalent accuracy with a frontier model holds only for the questions
the harness was shaped against. The report is
`docs/reviews/2026-11-18-frontier-direct-holdout.md`; `docs/MODELS.md` and the
release notes are corrected. Two probes changed: the frontier probe asks the
hold-out set on request, and the blind-reading packet builder reads its rows.

Measured, not changed (2026-11-19): the harness's hold-out misses scatter
across draws instead of clustering on questions, and a lookup that read three
pages or fewer was not right in 6 of 13 units against 7 of 113 for four or
more (`docs/reviews/2026-11-19-holdout-misses-classified.md`). The README now
says who the harness is for and that it is less often right than a frontier
model on new questions; the release notes' conditions for 1.0 are brought in
line with the owner's decision to build no guard.

Measured, not changed (2026-11-19, later): the eleven questions the harness
missed were asked again, three draws each, beside a frontier model at low
effort. The harness was right on 24 of the 28 answers it made (85.7 percent,
against 60.6 percent the first time) and the frontier model on 27 of 27, so the
first run's misses were mostly draws on eight questions and repeat on three
(X12, X31, X41). Eleven draws were refused by the provider for credit and are
reported as not made. `docs/reviews/2026-11-19-eleven-rerun.md`; two probes
added to rebuild the figures.

Added (2026-11-20, the owner's ruling): a reader tier, `MODEL_READER`, off when
empty. When set, the long pages a lookup fetched are cut into the six stretches
that share the most words with the question, each goes to its own call of a
small fast model, all at once, and the model copies back up to three passages
word for word. A passage counts only where the page holds it, by the same quote
check as before; nothing is summarised. It adds to the stretches chosen by
shared words and replaces none. It makes the lookup choose better stretches of a
long page; it does not make the PDF text come sooner, which is where the time
goes. Its effect on answers is not measured.

Changed (2026-11-20, the owner's ruling): the fetch layer waits up to 60 s for a
page instead of 25 s, and reads a page up to 37.5 MB instead of 15 MB. In the
eleven-question rerun 24 of 28 lookups had a page that gave no answer in 25 s
and four documents were cut for size. Measured free on six such lookups, the
downloads take 0.5 to 2 s and the time goes on reading the PDF text, so a longer
limit reads more pages (19 of 36 at 60 s against 15 at 25 s) but a faster read
would read more; that is not done. The effect on answers is not measured: the 42
hold-out questions are now a used set and a second hold-out set is needed to
judge it.

## [0.2.0] — 2026-11-17

Everything below happened after 0.1.0 and none of it was recorded until now.
The entry is written as prose rather than a bullet list because most of these
changes are only meaningful with the measurement that forced them.

**The workflow became a file.** The five-phase sequencer is gone from the
critical path. A pipeline is now a YAML graph in `workflows/`, built from three
node kinds — `ai` (model calls), `check` (free deterministic functions) and
`gate` (booleans over prior outputs) — with loops that carry an `until`
condition, a bounded iteration count and explicit exhaustion semantics, so a
build loop that gives up hands off to an escalation autopsy rather than simply
stopping. Conditions are one deliberately tiny grammar, not `eval`;
configuration must not execute code. Four workflows ship, and comparing two of
them is a measurement anyone can run. A hardcoded sequencer was kept beside the
graph as an equivalence reference for most of that work; it has since been
retired, for the reasons recorded below.

**An eval harness, so rules come from data.** Scenarios are YAML with
expectations written *before* the run; assertions are free and make no model
call; a bounded runner enforces per-scenario spend and call ceilings and reports
cost and calls per tier; suites repeat, because the same request has passed on
one run and failed on the next. Each scenario gets an isolated knowledge store,
after the discovery that research ingests what it finds and so grounded every
scenario after the first.

**Outward research, as a default rather than an option.** The harness writes its
own queries, ranks what it retrieves, briefs the phases that follow, and looks
outward for what the documentation does not cover. It asks the local store
before it pays for anything, and it ingests what it finds, so a fact is looked
up once and free thereafter. The reason it exists is a measurement: asked which
charger IC a board used, a capable model named the wrong part confidently and
without hedging; asked an RF limit it conflated two units 2.15 dB apart, the
difference between a compliant transmitter and a failed certification. Both
wrong answers sounded exactly as certain as the right ones, so there is no
confidence signal to gate a lookup on.

**Search cost was cut 44% by changing its shape, not its budget.** Low-risk work
looks nothing up; only gaps that would change the answer are looked up; and
every remaining gap rides in exactly one request, because the fee is charged per
request rather than per question. Token budgets scale with risk — a wrong figure
in medium-risk work is recoverable and in critical work it is not. Measured
across 36 sectors, $0.0999 to $0.0562 per workflow, almost entirely from four
requests becoming one.

**Domains and roles became open vocabularies.** Both were closed enums. With
`Domain` enforced, nine of twelve subjects had no fitting value and eight came
back `hardware` — civil engineering as "hardware", buffer chemistry as
"documentation". A closed list does not produce an honest refusal; it produces a
least-wrong label. Projects now declare `domains:` and `roles:` in a profile, an
undeclared role resolves to a synthesized generalist, and the shipped enums are
defaults rather than limits.

**Review composition is derived, not tabulated.** The review team is built from
the specialists triage actually assigned, scaled by risk. The old static table
returned every shipped role at critical risk, which meant seven engineers
reviewing a records retention schedule.

**Review gates the run.** `ship: false` now blocks rather than being recorded and
surfaced while the workflow completes anyway.

**`unrecallable` is a separate axis from risk.** A signed rollout to forty
thousand devices harms nobody and breaches no rule, so it is not critical — but
it cannot be taken back. It earns one extra independent review pass instead of
inflating its risk level.

**Cost accounting moved onto the client, and the old numbers were wrong.**
Spend, call counts and serving provider are recorded per tier inside the client,
so no call path can avoid being priced, with optional call and spend ceilings
enforced at the same place. This fixed a meter that had been counting only one
of four paths: research, grounding and reranking were all free as far as the
totals were concerned, and rerank cost was read into a debug log and discarded.
An eight-sector grounding run metered at $0.0025 actually cost $0.7366.
**Every cost figure in this project's history before that fix is understated by
between 2.6x and 295x and should not be cited.**

**Providers can be pinned per tier, and it turns out to matter.** One sweep saw a
single tier served by five different providers. Pinning each and re-running the
identical suite scored 35/36 at one end and 28/36 at the other, for twelve times
the price — and the cheap serving did not fail randomly, it under-classified risk
on the same three consequential sectors every repetition. An unpinned score is
partly a record of who answered, so pinning is a precondition for calibrating
anything. Pins are per tier because tiers run different models and no provider
serves them all.

**Packaging was unusable and is now fixed.** `pip install -e .` failed at build
on flat-layout package discovery, so it never reached the missing runtime
dependency behind it, and no built wheel contained the dashboard template.
`pyproject.toml` is the single dependency manifest, `requirements.txt` is gone,
and CI grew a job that installs from project metadata, imports the startup path
and checks a built wheel carries its package data — because the test suite runs
against the source tree and is structurally incapable of seeing a packaging
fault.

**Bounded, pinned, and able to keep its own records.** `--max-spend` only ever
capped one scenario-run, so a sweep of thirty-six scenarios at three repetitions
could spend thirty-six times what the flag implied; `--max-spend-sweep` now caps
the whole invocation and defaults to a dollar. Building it exposed six error
handlers that swallowed a budget abort and let a run keep spending after it had
been told to stop — including two that would have marked a working ranker dead
for the rest of the process.

Two long-standing calibration complaints turned out not to be what they were
recorded as. One sector had been blamed on the risk guide for months and was the
serving: pinned to a capable provider it passes, pinned to a cheap one it fails
every time, and nothing in the guide needed changing. The materiality gate was
recorded as an ineffective cost lever; it is ineffective as a cost lever and
does not need to be one, because the work whose gaps are immaterial already
classifies as low risk and never looks anything up. It stays as a question-count
cap, which protects the token budget of the questions that do get asked.

The cost meter, silently broken before the accounting fix and never checked
against anything outside itself, now agrees with the provider's own books to
within a third of a percent across a third of a dollar of live spend.

Evals keep what they buy. Every unit appends a JSON record carrying the typed
verdicts, the assertion outcomes, the per-tier cost and which provider served
each tier, flushed as it is written — so an interrupted sweep no longer discards
what it has already paid for, and a failing sector can be diagnosed months later
without reproducing it.

**The independent pass was observed running**, for the first time, inside a
complete workflow — a minimal probe shape reaches it by construction, and the
trace is kept as the regression case.

**Three phases could not retry.** The client validates a reply against a schema
and retries with a note saying what was rejected, but the implement and
escalation phases never passed their schema in, so a single malformed reply
ended a run outright — and a review's findings loop read a key off raw items,
crashing on exactly the shapes the finding schema had been widened to accept.
Two of four convergence traces had been dying on the first of these and being
read as convergence failures, which is how a diagnosis came to rest on evidence
that never reached the thing it was evidence about. All three are repaired, with
tests pinning every schema-bearing phase's call site, and errors now carry the
provider's own message instead of only a status code.

**The search tier's cheap sibling ties the expensive one** across three
repetitions — identical mean, identical per-repetition sequence — at an eighth
of the cost per lookup. A larger token budget on the cheap model costs nothing
and recovers fewer figures, so the accuracy curve measured on one model does not
transfer to the other.

**Evals keep per-iteration history**, so whether an implementation changes
between attempts is answerable from a finished run. It does change, by thousands
of characters, and still fails a different criterion each round.

**The build loop stops when its judges agree.** It used to exit on the
validator alone, and was measured exiting satisfied while the implementation sat
red in the same state — a domain reviewer had flagged a critical concern and the
exit did not look. Reading the validator's own evidence showed it was the judge
that was wrong: it marked a criterion passed while stating in the same sentence
that the test case had been changed away from what the criterion asked for. Each
loop now folds every judge its own shape produces, and the free checks carry the
same weight as the paid ones.

**Two silences closed.** When a reviewer's critical concern flipped an
implementation red, the next attempt was told only that a concern had been
flagged — the reviewer's actual words went onto a field nothing downstream read;
they now travel with the reason. And a lookup the provider refuses is swallowed
so the workflow survives, which is right and was silent: a whole evaluation once
scored zeros that were indistinguishable from a model finding nothing. Refusals
are counted where they are swallowed and the report says so.

**The assessment contract now fixes the success criteria.** Saying a criterion
is wrong is legitimate; passing work against a criterion quietly amended is a
false assessment, and a false pass is the expensive direction because it ends
the loop.

**The search tier's cheap sibling ties the expensive one** at three repetitions
— identical mean, identical per-repetition sequence — for an eighth of the cost
per lookup. A larger token budget on the cheap model costs nothing and recovers
fewer figures, so the accuracy curve measured on one model does not transfer to
another in the same family.

**Review's findings have somewhere to go.** A blocked review used to end the
run with its findings recorded and nothing able to read them. A closed gate can
now route instead of ending, so the work goes back through implement, validate
and a fresh review, and ships only when every judge agrees. Two silent channels
were opened on the way: the validator returned one failing criterion at a time
while its own evidence already held a verdict for each of them, and a blocking
review wrote nothing to the failure log at all. Both now travel to the next
attempt, in their authors' own words. Every loop must declare a bound at load
time — review and implement can disagree indefinitely, and the graph can no
longer express that.

**The planning phase has a ceiling of its own**, where it had been running on a
generic default while burning full-budget retries that returned nothing.

**The equivalence reference is retired.** A hardcoded sequencer was kept beside
the graph so the two could be compared call for call, and it earned its place
for a long time. It stopped: silent through a change to how loops exit, two
wrong attempts at mirroring behaviour it lacked the inputs for, an
order-dependent defect in its own suite, and finally a gate that routes work
back into a loop — which a linear engine cannot represent at all.

**A run now records what it measured.** Three instruments were found reporting
something other than what they observed, none of them visible to a green suite.
The schema retry had logged every rejected reply correctly and for free since
its clause ordering was fixed, and every line went to a stderr redirect and died
there — so the malformed-reply rate, asked for across nine runs, could be
computed from three. It is a field in the results file now, split by tier and by
serving, beside the count of verdicts normalised from their own stated cause. A
build-loop iteration records which judge blocked the exit, which it had claimed
to do for sixty-four iterations while reading attributes off a plain dict. And a
gate that routes work to a recovery sub-graph is no longer billed for the time
that sub-graph spends: one gate had been reading 1,573 seconds of an 1,800-second
run, in the per-phase table that exists precisely so an expired run does not have
to be bought twice to say what was slow.

**The build loop converges, and what fixed it was not the loop.** The oldest
open problem in the project — recorded for seven development cycles as "the
build loop does not converge on complex requests" — is closed. It carried six
different names on the way: an untested premise, an exit condition, a feedback
channel, a wall clock, a missing verdict field, and a wall clock again. Five of
them were about the workflow. The answer was the tier: the one that runs
implement, validate and review had never been pinned to a particular serving,
and pinning it turned two test cases that had never once completed into finished
deliverables in under five minutes each. The mechanism is not speed. Per-call
latency improved by about a third, while the number of iterations the work
needed fell from eight to two and from four to one — a serving does not only run
at a speed, it converges at a rate, which is the same lesson this project
learned about classification accuracy and had not thought to apply here. Three
of the four test cases finish with a written deliverable or a diagnosis naming a
real contradiction in their own plan; the fourth did before this cycle began.

Two schema changes landed with it, both earned by a live failure rather than
proposed. A verdict that names why it failed no longer has to also say that it
failed, and a verdict returning its evidence as an object keyed by criterion has
that folded into lines rather than refused three times. Both are counted, by
kind, in the results file — because a leniency that hides how often it fires
cannot be withdrawn later on evidence.

**The way this project is built is now part of it.** For fifteen development
cycles the working method lived in conversation: an advisor designing and ruling,
an agent measuring and implementing, and an owner holding the money and the
standing configuration. That method produced almost everything in this changelog,
including most of its corrections — the recurring pattern was not a wrong
hypothesis but a broken instrument, found while testing something else. With the
agent being replaced, the method has been written down as files rather than
carried in a transcript: one protocol document describing who decides what and
where the line falls between repairing a measurement and changing a behaviour,
and one bootstrap prompt that orients a new agent from the repository alone. Two
open defects are staged with their evidence and their unanswered questions, and
deliberately left undesigned, because choosing between the options would change
a cost model that was measured rather than assumed.

**A feature commit deleted most of the state-of-record document, and the
guards caught it.** `aac0324`, whose subject names only the gate routing it
added, also removed 1,435 lines of `HANDOVER.md` without mentioning the
deletion — the architecture, the state, the bug ledger, the conventions, the
measured facts and the orientation, leaving the vision and the executive
summary. The document that both the protocol file and the bootstrap prompt
send a new agent to read no longer contained the sections they name. Five
documentation guards in `tests/test_handover_truth.py` failed and the suite
stayed red on the main branch for three days across two commits. Every one of
the five failed because the claim it watches was **absent**, not because a
number had drifted: no guard caught a stale count, and all five caught a
missing document — which is a stronger result than the guards were written
for. The same commit left a placeholder in the header where a commit sha
belongs, a stamp that resolves to no object at all; that is the failure mode
the convention against hand-stamped facts was written against, appearing in
the document that states the convention. The text was restored from the last
green commit and every guarded number re-derived forward against the tree
rather than copied back, the suite returned to green, and restoring the
document surfaced a wiring asymmetry in the flagship pipeline that no record
had stated — the honest-refusal gate runs in the build loop and not in the
rework or recovery loops, so work blocked after a review reaches no gate that
can report it. That one is recorded and left for a ruling.

The suite stands at **712 tests** as of `c442c5f`, up from 85 at 0.1.0.

**The default became one answer and its checks.** Since November the workflow a
request runs by default has no plan, no judge and no loop: triage, the request's
asks, a lookup, one answer with typed values, two gates that can stop a run, and
free checks. The longer workflows are still offered by name. An audit had found
that a judge could not block an answer on a wrong number, and three tiers of
questions had shown no real catch by a judge.

**The lookup reads the documents itself.** The search tier is asked where the
answer is written, not what it is. The harness fetches those pages and hands
their own words to the answer step, and every passage is recorded with whether
it was found on its page. The lookup that asked a search model for an answer
and its quotes was measured against this one and removed.

**The delivery says what was checked.** An answer comes with "verified" lines
for figures that stand in a found passage, and cautions that name a figure on
no page, two pages that differ, or nothing read. Small yes/no decision switches
on an optional decision tier guard the steps that cost more.

**The recompute vote is kept for calculations.** On answers read from a
document its samples read the same text and repeated the answer's mistake. It
now runs only for a request judged to need a calculation.

**Less of it.** The claim check, four switches that only recorded, the second
request for documents, the withholding of unverified answers and episodic
memory were measured or found unused, and taken out. A run left in flight by a
stopped server ends blocked when the server next starts.

**The story and the model choices are written down:** `docs/HOW-WE-GOT-HERE.md`
and `docs/MODELS.md`, with a map of the record in `docs/README.md`.

**The final configuration was run once on all three professional sets.** Six
answers to each of 44 questions, 264 in all, read blind by two readers against
signed keys: 259 were right on the key (248 on a stricter reading) for about
nine tenths of a cent an answer, and no confirmation stood beside a wrong
figure. The one bar missed is that wrong answers were rarely marked: of five,
only the wrong figure carried a caution that pointed at it. The report is
`docs/reviews/2026-11-17-acceptance-run.md`. The page now fits a phone, and the
Docker image has been built and run by hand.

**A cold start from the README, and what it found.** An agent that had only the
README cloned, installed, started the server and built the image. It ran, in
about five minutes. It also found that the image build copied the working `.env`
into the image, so the provider key was readable by anyone given the image: a
`.dockerignore` now keeps every `.env*` file except the template out, proven by
building from a tree that holds three of them. The README now says what the
first start looks like, which Python it needs, and where the database lands.
The dashboard's Workflows table no longer reads '-21600s ago' in a browser west
of Greenwich, and its greeting no longer promises a plan step the default
workflow does not have. A run through the Docker image with a real key, called
from a signed-in browser, finished in 68 seconds for 'eight tenths of a cent'.

**The database is versioned, and the harness met questions it was not shaped for.** A
`schema_version` stamp and numbered migrations bring an older database forward in place, and a
database from a newer release is refused with a plain sentence. The rate-limit retry went from
three attempts to five. A hold-out set of 42 questions, written by authors that never saw the
harness's answers and signed by the owner, was run once at '$1.355': 113 of 126 answers right on
the key, 97 on a stricter reading, none blocked by a rate limit. Two of seven preregistered bars
were missed. One confirmation stood beside a wrong year taken from a superseded licence, and of
nine wrong answers three carried a caution that pointed at them. The release was held for the
owner on the first. The report is `docs/reviews/2026-11-17-holdout-run.md`.

## [0.1.0] — 2026-09-12

### Added

- Multi-model agentic workflow engine with 5-phase sequencer (triage, plan, implement, validate, review)
- 7 engineering specialists with profile-driven system prompts
- Reasoning-model escalation autopsy — recovery when the implement/validate loop exhausts
- Risk-based review team composition (critical → all specialists, low → single specialist)
- Plan feasibility gating — specialists review the plan before implementation tokens are spent
- Project profile system — YAML-based domain grounding with per-specialist context overrides
- Profile-aware knowledge store with ChromaDB semantic retrieval
- Episodic memory — workflow outcomes stored for future context
- REST API with sync and async workflow submission
- Dashboard with chat interface, workflow table, and profile selector
- API key authentication middleware (optional, bearer token)
- OpenRouter multi-model routing client with cost tracking and retry logic
- CLI for doc ingestion (`init-knowledge`)
- Docker support with volume mounts for profiles and docs
- Example profile (SmartFactory) with sample docs
- Full test suite (85 tests)
