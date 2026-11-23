# The caution flaw: what a delivered answer says about itself (2026-11-23)

**Status.** Owner-directed in conversation, 2026-11-23: "create a plan to fix the warning flaw and implement if possible".
Implemented on `fix/20261123-caution-flaw`, cut from `main` at `1dc134a`. **Not merged, no pull request.** The cautions are the
owner's to rule: the owner approved the plan that rebuilt them on 2026-11-15
(`docs/reviews/2026-11-15-cautions-on-handed-on-text.md`) and ruled one caution out on 2026-11-16
(`docs/reviews/2026-11-16-week1-removals.md`, item C). So this is a proposal with its measured effect, and the merge is the
owner's. Nothing here spent money: every figure below is a replay of records already on disk, and `docs/probes/caution_replay.py`
reproduces each one.

"The warning flaw" is read as the one the second hold-out run reported as the only bar missed: **a wrong or partly right answer
comes with no caution pointing at what is wrong** (`docs/reviews/2026-11-22-holdout2-run.md`, bar 4). The suite also ended each
run with one pytest warning, a class-level `asyncio` mark on a class that holds one async test and one that is not. That is fixed
too, in its own commit, because the phrase could mean it.

## 1. The flaw, measured

The labelled pool is every delivered answer of four runs that two readers judged against signed keys: the first hold-out
(2026-11-17, 122 answers), the acceptance run (2026-11-17, 264), the eleven-question rerun (2026-11-19, 27) and the second
hold-out with its unpinned arm (2026-11-22, 268). **681 answers: 658 right, 23 not right** (17 wrong, 6 partly right). The
rerun's 27 answers of a frontier model are left out: no harness run stands behind them, so there is no delivery to caution. The
cautions are rebuilt from the stored phase rows exactly as the delivery builds them, and each rebuild equals the cautions the run
recorded, for all 681 (the probe stops if one differs).

| The caution as shipped, by kind | right answers (658) | not-right answers (23) |
|---|---|---|
| any caution | 167 (25.4%) | 8 (34.8%) |
| a figure on no page | 52 (7.9%) | 5 (21.7%) |
| two pages give different figures | 108 (16.4%) | 3 (13.0%) |
| a caution of the recompute vote | 50 (7.6%) | 5 (21.7%) |
| no lookup ran, or nothing was read | 5 (0.8%) | 0 |

An answer can carry several kinds. A caution of any kind stands beside 25 percent of the right answers and 35 percent of the ones
that were not right, which tells a reader almost nothing. The commonest, "two pages give different figures", stands beside 16
percent of the right and 13 percent of the not-right: it does not separate them. The figure-on-no-page and the vote cautions lean
the right way (about 8 against 22 percent) but fire on few answers. **The delivery reads the vote and the pages. It never read
what the answer says about itself.**

## 2. Three causes, read from the code

1. **The answer's own typed fields are not read.** `routes._detail` builds the cautions from the vote and the pages handed on.
   `blocked_on`, `not_stated`, the answer text and the asks that have no result are in the stored rows and in none of the
   cautions. A `blocked_on` entry that names no ask is, by D51 (5), a note the run completes on, and nothing showed it: Y149
   declared its second ask unanswerable and shipped with no caution.
2. **Two free checks run and their findings are thrown away.** `criteria_addressed` (does the answer mention each ask) and
   `numbers_consistent` (do the answer's figures agree with the request's) run beside every answer; the workflow says "a flag is a
   note on the delivery, nothing more" (`workflows/answer-and-recompute.yaml`), but a check's output is not persisted
   (`graph/adapter.py`: "a check's output is not otherwise persisted"; only the vote and the lookup's pages are), so neither reaches
   `_detail`. Replayed, `criteria_addressed` finds an ask missing on 24 right answers and 3 not right; `numbers_consistent` finds a
   conflict on 23 right and 2 not right. Section 5 says why neither is worth surfacing.
3. **The cautions that fire are mostly about something else.** On Y146 the "two pages give different figures" line stood beside a
   wrong answer and said, truly, that two pages give 85 and 50 (the haircuts of two classes of asset, which the answer used
   correctly). The wrong part, a sum the answer declined to give and called "not stated", had no caution. The run's review says it
   the same way: "the harness said so, correctly; the answer still gave no sum".

## 3. What is built

`routes._gaps(verdicts, request)`, appended after the existing cautions in `_detail`; two small public helpers in
`graph/checks.py` (`numbered_asks`, which numbers the anchored asks as `asks_anchored` does but without its side effect, and
`asks_named`, which reads which asks a list of typed entries names, the way the recompute vote reads them). Four cautions, each
read off a typed field, **none off prose**:

| Caution | Fires when | Reads |
|---|---|---|
| The answer gives no result for ask N: "..." | an ask of kind value or verdict has no typed result and no claim that the document states none | `asks`, `results`, `not_stated` |
| The answer marks part of the request as one it could not answer: ... | any `blocked_on` entry is delivered (one that names an ask ends the run blocked, so these name none) | `blocked_on` |
| The answer says ask N is not stated in the document. The only check behind that is a search ... | the answer claimed "none stated" for ask N and the gate accepted it | `not_stated` |
| The text of this answer is only N words long, so it may not state the results listed for it | typed results exist and the text has fewer than 30 words | `results`, `summary` |

The limit of 30 words has a measurement behind it: the shortest of the 658 right answers has 70 words; of the 23 not right, one
has 1 (Y140, the single word `PLACEHOLDER`) and the next shortest has 135. An answer that typed no results is never told it left
an ask without one: only `answer-and-recompute` asks for results, and an empty list cannot tell "not asked" from "typed nothing".

`tests/test_answer_gaps.py` (30 tests) pins each rule, the numbering against `asks_anchored`, the quote and number-as-text forms a
result may name its ask by, and carries two real recorded units whole through `_detail` (Y140 and Y149). **16 of 16 guarded
lines were broken one at a time and each broke a test; the files were restored byte-identical.** 17 existing tests built a
delivery with typed results beside the one-word answer `"a"`, which the new rule rightly calls a gap; their stand-in answer is
now as long as an answer is (rule 7: the fixture was wrong, not the rule).

## 4. What it measures (replay of the 681)

| | right (658) | not right (23) |
|---|---|---|
| a caution as shipped | 167 (25.4%) | 8 (34.8%) |
| **a gap caution (new)** | **8 (1.2%)** | **5 (21.7%)** |
| either | 173 (26.3%) | 12 (52.2%) |
| neither, so it comes clean | 485 (73.7%) | 11 (47.8%) |

By kind, right | not right: no result 3 | 2; could not answer 4 | 2; not stated 2 | 2; text too short 0 | 1.

The five not-right answers it marks are Y149 (ask 2 declared unanswerable and given no result), Y140 (the single word
`PLACEHOLDER` beside two typed results), Y146 (the sum declined and called "not stated"), Y170 (the threshold called "not stated",
both asks) and X38 (ask 3 given no result and declared unanswerable). **Each new caution names the ask or the text the answer got
wrong**, which the shipped ones did not: Y146's only caution pointed at something else.

The eight right answers it marks are X41 (twice, in the first hold-out and in the rerun), X36, Y28, Y129 and Y132, which left an
ask without a result or called a part one they could not answer, and Y151 and Y180, which called an ask not stated. Each says so
itself in a typed field and was judged right (several of these are traps, where saying so is the right answer), so the caution
restates something true. It is still a false alarm for a reader who did not need telling, and it is counted as one.

**What this is not.** It is in-sample. The rules were designed after reading the typed records of all 23 not-right answers, so 5
of 23 is an optimistic figure, not a rate. The false-alarm side is the sturdier one: 8 of 658. The fresh test is the final tally's
new answers, read by two readers after this commit is frozen (section 7).

## 5. What free checks cannot fix

**Eleven of the 23 come clean: no shipped caution and no gap caution.** They are X13, X19, X20, X31 and X34 of the first hold-out;
H4, H8 and P4 (twice) of the acceptance run; Y68 and Y124 of the second. In the typed record each looks like a right answer: every
ask that wants a result has one, nothing is blocked and nothing is declared not stated. (Why each was wrong is in the review of its
run. Y68 and Y124 are the second run's two traps: a figure the document does not state was given as one, and a right figure was
given with the wrong reason.) Three cheaper ideas were measured on the same pool and fail:

| Idea | Right answers it marks | Not-right answers it marks | Verdict |
|---|---|---|---|
| the answer hedges in its own prose ("could not confirm", "inferred", "please verify"; analysis only, prose is never read for control flow) | 168 of 658 (25.5%) | 4 of 23 (17.4%) | no separation |
| `criteria_addressed` surfaced as it stands | 24 (3.6%) | 3 (13.0%): X41, Y140, Y146, each already cautioned | adds none to the answers that come clean |
| `numbers_consistent` surfaced as it stands | 23 (3.5%) | 2 (8.7%): Y149 (already cautioned) and X20 (silent) | one silent wrong answer bought with 23 right ones marked |

So a typed "I am unsure" channel built from the model's own hedging would stand beside a quarter of the right answers. **The
silent half needs new information, and that costs money.** Two levers, neither built, neither measured, both the owner's to rule
because each changes what is delivered:

* **A. A reader per ask.** A cheap model is handed the answer's value and the passage the lookup found for the ask and says
  whether the passage states it. Its cost is unmeasured; it sits between the decision tier's whole spend an answer in the second
  hold-out run ('$0.00013': '$0.036' over 268 answers) and the reader tier's ('$0.0028': '$0.756' over 268). Measuring it is a
  replay over the 681 stored rows, about '$0.09' to '$1.9' of calls, and **needs the owner's amount stated first.** It can only
  see what the passages handed on show: a trap like Y68, where the document states no figure and the answer gave one, is the
  case the proof of absence below was built for.
* **B. A second answer from another model, compared on the typed results.** About '$0.0085' more an answer (the engineering tier's
  mean spend per delivered answer in the second hold-out run: '$2.29' over 268), so it about doubles the answer tier's spend. The
  recompute vote is this design for calculations: it ran on 72 of the 658 right answers and 4 of the 23 not right, and flagged 7 of
  those 72 and 2 of those 4 (X12, twice). It has not been measured on look-ups.

## 6. Found and not touched (each needs a ruling, none is decided here)

* **A `blocked_on` entry that names no ask completes the run** (D51 (5), by design). Y149 and X38 are the two cases. Whether an
  unnumbered entry should end the run blocked is a gate-routing ruling. The new caution makes the entry visible and nothing more.
* **The proof of absence is only as wide as the words a model lists.** Y170's words were formula-style terms ("E > 1 EeV" and the
  like) that the pages do not print as strings; "EeV" or "UHECR" alone would have vetoed the proof. `knowledge/absence.py` says so
  in its own header ("it is only as wide as the words"). Asking the model for names and not formulas is prompt text that steers
  judgment.
* **A lead, not confirmed: the words for a proof of absence are recorded for few units on the shipped triage model.** Counting the
  units whose lookup read a document and that had an ask of a kind a document can answer: in the second hold-out run the words
  (`searched` in the lookup's record) are recorded for 11 of 199 on the shipped triage model (2 proofs) and for 49 of 49 on the
  earlier one (36 proofs); among the 89 units the final tally ran before the key's limit stopped it, 3 of 67 (the count reads
  stored lookup records only, no answer text and no label). The denominator also holds units whose pages were not read in full and so never reached the call, so 11 of
  199 is a lower bound on the share; 49 of 49 on the same count says that cannot explain the gap. `name_terms` swallows a failure
  with a log line and no count (`knowledge/absence.py`, the `except Exception` in `name_terms`), and a unit where it returned
  nothing leaves no record. One capped call on the shipped triage model through `name_terms`'s own prompt would say whether it
  returns words; it costs about '$0.001' and waits on the key (the final tally is stopped on the key's limit).
* **`PLACEHOLDER`** is in no prompt, schema or profile of this tree (searched under `autornd/`, `profiles/`, `workflows/` and the
  switches). The verdict has no reasoning field, so the origin of the text is not recorded.
* **Bar 4 counts a "pointing" caution by a phrase match** (`docs/probes/holdout2_analysis.py`, `POINTING`, on the evals branch).
  The four new sentences are not in that list; a later analysis must read them as pointing by reading, as the review of Y146 had
  to.

## 7. How this is evaluated, and what the owner decides

1. **Frozen before the fresh answers are read.** This branch's head, committed before any answer of the final tally
   (`docs/preregistration-20261123-final-tally.md` on `evals/20261122-holdout2-harness-run`) is read, is the design. The only
   thing read from the tally before it is the lookup-record count in section 6. The tally's answers were made by main's code
   (without the gaps); the gaps are replayed over their stored rows, and the blind readers' labels (made with no knowledge of the
   gaps) are the truth. Any rule changed after that reading is reported as changed after it.
2. **What decides.** For the gaps: right answers marked at no more than 3 percent, and every not-right answer they mark pointing
   at the part that is wrong, read by hand. The old bar 4 (half the wrong answers marked, pointing) is not expected to be met by
   free checks and is not the test of this branch.
3. **The owner rules** on: merging the four cautions; levers A and B (each with an amount, before any spend); the two questions in
   section 6 that are gate-routing and prompt matters.

## 8. The boundary, classified (CLAUDE.md "The permission boundary")

| Change | Class |
|---|---|
| the four cautions in the delivery | delivery text; nothing routes on it and no answer changes, but the cautions are the owner's by precedent (2026-11-15, 2026-11-16): **a ruling** |
| `checks.numbered_asks`, `checks.asks_named` (new, public, unused by any gate) | instrument, additive |
| the 17 test fixtures' stand-in answer | test fixture, rule 7 |
| the class-level `asyncio` mark removed from a class holding one async and one sync test (`pyproject.toml` has `asyncio_mode = "auto"`; the async test still runs, and two guarded lines were broken to prove it) | test hygiene |
| counts 2,627 tests in 109 files to 2,657 in 110 | re-derived from `pytest --collect-only` |

## Replaying this

```
python -I docs/probes/caution_replay.py REPO TRACES_DIR [TRACES_DIR ...]
```

`REPO` is the tree to replay (this branch). The traces are the committed ones: `docs/traces/` of `main` holds the first three
runs, and the second hold-out's (`20261122T-holdout2-*`) are on branch `evals/20261122-holdout2-harness-run`; give both
directories. The probe prints every table above (the shipped cautions by kind, the new ones, the two discarded checks, the
hedging count, the words, the vote) and every not-right answer and every right answer that gets a gap. The output of the run
recorded here is `docs/traces/20261123-caution-replay.txt`.
