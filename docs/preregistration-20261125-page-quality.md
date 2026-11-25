# Preregistration: script-built pages read through their own document routes (2026-11-25)

Pushed alone, before any spend of this run. No answer of this run exists. The owner said "do all four suggestions" on 2026-11-24 with
about '$1.7' left on the provider account (my estimate: '$2.15' stated, about '$0.47' spent since).

## The question

Branch `feat/20261125-page-quality` (`1928548`, main `300d12a` plus one commit): the fetch layer routes two script-built sites to their
own document addresses (legislation.gov.au instruments with no date in the address, to the Federal Register's PDF API; NVD CVE pages,
to NVD's JSON API) and refuses any page whose own bytes carry the empty script root and whose text is under 3,000 characters, so it
cannot back a quote or a proof of absence. **Do the two questions that read those sites now answer from the document, without making
any right answer wrong?**

## What is run

The tree `1928548` (a fresh worktree), the owner's `.env` unchanged (reader tier on, no pins), profile `engineering`, workflow
`answer-and-recompute`, **3 answers each, 21 answers**, in two invocations:

* **Targets (2 questions, 6 answers):** X31 (`professional-holdout`: the Radiocommunications class licence on legislation.gov.au) and H9
  (`professional-hard`: the CVSS 3.1 score of CVE-2021-44228 on NVD).
* **Not expected to change (2 questions, 6 answers):** X3 (the 33-character WHO PDF) and X35 (the CODATA page that was never fetched).
  Neither site is routed; they are run to see that nothing got worse, and each stays as it was if it was wrong.
* **Controls (3 questions, 9 answers):** X19, X36, X41, right "the document states none" answers that must stay right.

## Money

Stated before the spend: expected **'$0.34'** (21 answers at '$0.016'); invocation caps '$0.30' and '$0.15'; **ceiling '$0.50'**. Stops: any
404, 402, 403 or key-limit message; a `spend_guard_blind` entry; a model on the answer seat other than the global answer model; the run
past '$0.50'.

## How it is read

As the earlier runs (D50): one blind reader on codes that hide question draw, and my reading of every not-right answer and 4 seeded right
ones before I look at cautions or old labels. Not right is `wrong` or `partly`. Whether a route fired is read from the run's records (the
document's `final_url` and page count), and the cost from the run's accounting.

## Baseline (stored records, harness before the change)

* **X31:** first hold-out asked again: right, blocked by the harness's own rule, right; second-look run: wrong in both delivered draws, on
  proofs made on a 1,770-character frame of the same site (read from the stored records).
* **H9:** `rerunv2c`: refused ("Ask 1 is not answered by the grounding") with a "not stated" caution; `resume1`: right; `H`: blocked by
  the key limit. That is 1 right, 1 wrong refusal on the frame, 1 undelivered.
* **X3:** first hold-out asked again right in 2 of 3, wrong once (no figure); second-look run right in 3 of 3. **X35:** the same, wrong once
  in the first (the 2018 value refused), right in 3 of 3 in the second. **X19, X36, X41:** right in
  every delivered draw except X41 once partly (did not commit that the datasheet states none).

## Predictions (written before any answer is read)

* **Targets:** 6 of 6 right. Both routes fire in every draw that opens the cited page (the documents record shows the API address and a
  page count above 0 for legislation, a JSON page for NVD). No "not stated" caution cites a frame.
* **Not expected to change:** at most 1 not-right of 6, the same kind as before (X3 with no figure, X35 with the 2018 value refused).
* **Controls:** at most 1 not-right of 9, X41's known limit being the likely one.
* **Cost:** '$0.014' to '$0.020' an answer; the PDF of an instrument adds reading time, not much cost.

## What decides

* **For merging the branch:** the 6 target answers are all right **or** the one miss is shown not to touch a routed page; **and** at most
  1 control is not right, and none that was a right "none stated" turned into an invented figure.
* **Hold the branch** if any control that was right becomes wrong because a page it used is now refused as a frame (the reason string says
  "shell"), and name the page.
* **Reported as it reads,** and a rule changed after the reading is reported as changed after. With 21 answers no rate can be read, only
  cases.

## Limits

* X31 and H9 were chosen because they read the two routed sites: in-sample by construction. The branch is not shown to lift any rate.
* A dated legislation.gov.au address is not routed, so a cited dated page still fails as a frame and the question may fall back to the
  blocked note; this run does not test that beyond what the draws happen to cite.
* Different hours, different provider conditions from the baseline.
