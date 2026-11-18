# Preregistration: a frontier model asked directly on the hold-out questions (2026-11-18)

Pushed before the spend. The owner asked how the harness compares with others of its kind and
then said "Write it up" to the executor's offer of this run. **That is not the word to spend.**
The owner's word and an amount are asked for after this file is merged, and nothing is spent
before them.

## Why

The only measured comparison so far is `docs/reviews/2026-11-17-frontier-direct.md`: a frontier
model asked directly, on 22 questions the harness had been shaped against, was right on all 22
and so was the harness. That says nothing about questions nobody shaped anything against.
`docs/reviews/2026-11-17-holdout-run.md` has the harness's result on 42 such questions: 113 of 126
answers right on the key. This run asks the frontier model the same 42, so the two figures stand
side by side on the same new questions.

There is no measured comparison with other harnesses, and this run does not make one.

## What is run

`docs/probes/frontier_direct_probe.py` with `FRONTIER_SET=professional-holdout`. No harness is in
the path. The setting is the first comparison's, unchanged, and was not chosen with any hold-out
result in view.

- **The model:** `anthropic/claude-fable-5.2`, reasoning effort medium, web search on (the
  provider's web plugin, up to 5 results a search), at most 8,000 tokens a call.
- **The request:** the question as the only message. No system prompt, no instruction about
  sources or format.
- **The questions:** all 42 of `evals/professional/holdout-questions.json` (version
  professional-holdout-1, sha256 first 12 `c5d4a9dad66e`), X1 to X42, once each, in file order.
  The probe refuses a set whose status says draft.
- **A smoke first:** one question (X1), to see the reply's shape and what a call costs.
- **What the probe change was checked with, before this file:** a run with a spending limit of
  zero and no key in its environment lists 42 questions, X1 to X42, makes no call and writes
  nothing; a set name other than `professional-holdout` stops it.
- **A call that fails** (a network error or the provider's error, no answer billed) is asked again
  when the probe is run again, up to twice. **A call that returns no text, or is cut off** (finish
  reason `length` or `content_filter`) is kept as it is, counted as not right, and reported, as
  the harness's blocked answers were.

**The harness's side** is the hold-out run as reported, nothing re-run: 126 answers (three a
question), 113 right on the key (89.7 percent), 97 on the stricter reading, '$0.0108' an answer,
107 seconds an answer. Its three rounds were right on 37, 37 and 39 of 42, counting an answer
blocked by its own checks as not right. These figures were known before this file was written.

## Money and stops

- **The cost of an answer in the first comparison was '$0.071'** (from '$0.032' to '$0.141').
  **Forty-two answers are therefore expected to cost about '$3.00'**, and between '$1.35' and
  '$5.90' if the first comparison's range holds. The executor's first spoken figure, '$0.15' for
  the run, mistook the cost of one answer for the cost of the run and was about twenty times too
  low. This is the figure to approve against.
- **Proposed limit: '$5.00'.** The probe starts no call once '$4.60' is spent. A call can write at
  most 8,000 tokens, about '$0.32', plus what it reads; '$4.60' plus the dearest call seen is
  inside '$5.00'.
- **If the smoke costs more than '$0.30', or returns no text, the run is held and reported.** The
  amount is the owner's.
- Nothing is spent before the owner's word and an amount.

## How it is read

The rule is the hold-out run's, word for word: **an answer is right when every key item is
right.** An item that says "None" or "the document states no such figure" is right only if the
answer says so. A wrong figure beside a right one for the same key item makes the answer wrong. A
wrong claim outside the key items is recorded as `outside_wrong` and does not change the verdict.
Both figures are reported, the key rule's and the stricter one that counts `outside_wrong`, as in
the hold-out run.

- **Two readers (D50).** Three blind readers read the 42 answers under codes, with the key and
  this rule and the verdicts `right` and `wrong` only. The executor reads every answer they do
  not mark right and a random 12 of those they do, and searches the whole of each for each key
  item. Where the two differ, both read again with the keys and the difference is reported.
- **The scorer is a screen, not the result.** No automatic check is a verdict.
- **What each answer shows** is recorded as in the first comparison: whether it names a page, and
  whether it says its figures are unchecked or should be verified.
- **The same cuts as the hold-out run:** all 42; the 26 questions the harness's own fetch can
  read (X1, X2, X4, X5, X6, X7, X8, X9, X10, X11, X13, X14, X15, X16, X21, X22, X23, X24, X25,
  X27, X28, X34, X36, X37, X39, X42) and the 16 it cannot; the five traps (X13, X16, X19, X36,
  X41) and the other 37; the three groups X1 to X14, X15 to X28 and X29 to X42.

## What is compared, and the bars

Reported side by side: answers right, cost an answer, seconds an answer, whether the answer
names a page, and of the wrong answers how many say their figures are unchecked (the harness's
figure is 3 of 9 pointing cautions). Which questions each got wrong is listed, and how many both
got wrong. This is a description. Two bars are held to it:

1. **The harness is not worse by more than five points.** The harness's right rate, 89.7 percent,
   is within five percentage points of the frontier model's right rate on the 42. That is met when
   the frontier model is right on 39 or fewer of 42, and missed when it is right on 40 or more.
2. **The harness is much cheaper.** Its cost an answer, '$0.0108', is no more than a quarter of
   the frontier model's. That is met when the frontier model's cost an answer is '$0.043' or
   more.

- Both met: `docs/MODELS.md` says it, with the figures, for new questions as well as the ones the
  harness was shaped against.
- Bar 1 missed: `docs/MODELS.md` says that on questions nobody shaped anything against the
  frontier model asked directly was right more often, by the figure measured, and the cost and
  record-of-what-was-read arguments carry the case alone. No change to the harness follows
  without a ruling.
- Bar 2 missed: the price argument is corrected to what was measured.
- The frontier model's wrong answers are read for where they fall. If most are on the questions
  the harness's fetch cannot read, that is reported as the harness's limit, not the model's.

## Predictions

1. The frontier model is right on 37 to 41 of 42 (88 to 98 percent), lower than its 22 of 22 on
   the old sets.
2. At least half of its wrong answers fall on the five traps or on X29 to X42 (datasheets, units,
   national rules), where a figure sits in a PDF table that a search snippet may not carry.
3. Its cost an answer is '$0.05' to '$0.09'.
4. It takes 6 to 15 seconds an answer, against the harness's 107.
5. **Bar 2 is met. Bar 1 is about even,** and the executor does not know which way it falls: at
   40 or more right it is missed, and the harness is then worse on new questions by more than
   five points, which will be said plainly.
6. Fewer than half of the frontier model's wrong answers say their figures are unchecked.

## Limits, stated beforehand

- **42 questions, one answer each for the frontier model,** three for the harness. The
  harness's three answers to a question are not independent draws. A difference of two or three
  questions is noise.
- **Authors, checkers, readers and the model are of one maker.** The 42 questions and keys were
  written and checked by models of the maker whose frontier model is asked, then signed by the
  owner; the blind readers are of that maker too. Which way that bends the result is not known.
- **The harness's fetch could not read 16 of the 42 sources,** and the frontier model uses its
  own search. A gap there is partly a gap between two ways of reading a page, and is cut out
  separately for that reason.
- **Different days.** The harness was run on 2026-11-17 and the frontier model on a later day. Live
  pages change, and an answer can differ for that reason alone.
- **One model, one effort, one search setting.** The first comparison found high effort bought
  nothing on 14 questions. Nothing here speaks for another model, or for this one with search off.
- **No other harness is compared.** This is a model asked directly against this harness, on one
  set of questions.
