# Preregistration: the revised caution fix, on new answers (2026-11-23)

Pushed alone, before any spend of this run. No answer of this run exists. The owner asked on 2026-11-23, after the final tally, to
"work more with the caution fix, try to lock down the main weakness and complete the fix", to put the reader tier back, to
check any key that looks wrong by an independent reader, and to run the proof-of-absence diagnostic ("4 do it").

## What was found, free, before this run (all from the stored rows of the tally and the re-asks)

1. **The gap "no result for ask N" beside right answers is one cause.** All six right answers that carried it had a constraint as
   ask 1 and one typed result per ask wanted, numbered 1.. by the model's own count, so the result for the value ask was filed
   under the constraint. Every not-right answer that carried it had fewer results than asks wanted. Rule now on the caution
   branch (`957bc08`): a result that names an ask wanting none stands in for one open ask.
2. **The words for a proof of absence were never made.** The call that names them uses the cheapest tier, a reasoning model; at its
   default it spent the whole 2000-token budget thinking and returned no text, three tries, on each of three requests probed
   (about '$0.0026'). The failure is swallowed (`name_terms` returns no words), so the lookup went on with no proof for 188 of the
   199 eligible units of the second hold-out run. With thinking off the same three requests came back in 48 to 76 tokens at about
   '$0.00002', with the words the key of X41 lists; medium effort and a budget of 6000 returned nothing. Fix on the branch: thinking
   off for that call. This is the main weakness' root: with no proof, a right "the document states none" had only the blocked note.
3. **Keys checked by independent readers** (not shown the key or our answers; primary texts fetched): Y115, Y170 and Y68 hold;
   Y88 holds for the standard it names (PRC-024-3), whose successor is now in force; **Y13 is stale** (see the review).

## The test

Same tree as the tally with the revision only (`autornd/` differs from the tally's tree by the gap cautions and the two changes above),
same `.env` with `MODEL_READER` restored by the owner's instruction (the reader tier is on, as it was before the 2026-11-23 removal),
profiles and workflow `answer-and-recompute`; each question on the profile it ran on in the tally.

* **Group A (8 questions, 3 answers each, 24):** the questions whose right answers carried a gap: Y4 Y89 Y104 Y129 Y158 (second
  hold-out), X22 X36 X19 (first).
* **Group B (15 questions, 3 each, 45):** the questions with a not-right answer in the tally or the re-asks: X12 X14 X20 X31 X41 X8,
  Y115 Y124 Y170 Y37 Y68 Y88 Y9, T4-42 T4-58. (Y13 is left out: its key is stale.)
* **Control (40 questions, 1 each):** a seeded sample (`random.Random('v2-control-20261123')`) of the 282 questions every one of
  whose tally answers were read right, outside A, B and Y13. The lists are `docs/probes/caution_v2_main.json` and
  `caution_v2_control.json`.

Answers: 109. Expected spend about **'$1.5'** at the tally's mean of '$0.0135' (the reader tier adds about '$0.003' an answer,
so up to '$1.8'); **ceiling '$2.50'** for the whole run, each invocation capped at its answers times '$0.022' (floor '$0.10').
The provider key had about '$13.8' of its limit left. Stops as the earlier runs (any 404, 402, 403, key-limit message, blind guard, a
model on a seat other than the global answer model and the second triage model, a reader model other than the one restored, an invocation
past its cap by more than one unit, the total past '$2.50'). Answers are read blind by two readers as before (D50), the executor
second-reading every not-right answer, every screen flag and a seeded sample; cautions are read only after the reading is fixed.

## Predictions (written now)

* **Proofs:** words are named for at least **60 percent** of the units whose lookup read a page in full (11 of 199 before).
* **False alarms:** gaps beside at most **3 percent** of the right answers of A and the control together; **none** of the form "no
  result for ask N" beside a right answer unless it has fewer typed results than value or verdict asks.
* **The weakness:** of the right answers in A that say the document states none (X36, X19), at least half now say it through the
  typed "not stated" channel and not the blocked note, and the caution they then carry is the "not stated" one, with the proof's page named.
* **Catches:** gaps beside at least **30 percent** of the not-right answers of B, at least 4 of 5 of those pointing at the wrong part by
  hand. B's not-right rate is expected near 28 percent.
* **A risk, said now:** with proofs working, an answer may say "the document states none" where the document does state it (the proof
  is only as wide as the words). Any such answer is listed with its words and the page.

## What decides, and what does not

The revised fix is called complete if: false alarms at most 3 percent, pointing at least 4 of 5, and proofs for at least 60 percent.
A miss is reported as read, with the cause. Not decided here: whether to merge (the owner's), and Y13's key (the owner's under D44).
The accuracy of the answers, with the reader on and the absence words working, is reported next to the tally's for the same
questions and is not a bar.
