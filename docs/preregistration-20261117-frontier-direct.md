# Preregistration: a frontier model asked directly, beside the harness (2026-11-17)

Pushed before the spend. The owner's word, 2026-11-17: "Do half the questions once, so 22 runs
on Fable med, and internet on, because it will compare to our harness more closely like that."

## Why

`docs/MODELS.md` argues that inexpensive models, handed the right page, are the right choice
for this work. It also says what it has not measured: a current frontier model. This run is the
comparison an outside reader asks for first: why not ask a frontier model directly?

## What is run

`docs/probes/frontier_direct_probe.py`. No harness is in the path.

- **The model:** `anthropic/claude-fable-5.2`, reasoning effort medium, web search on (the
  provider's web plugin, up to 5 results a search).
- **The request:** the question as the only message. No system prompt, no instruction about
  sources or format.
- **The questions:** 22 of the 44 professional questions, once each, drawn by a fixed seed
  (`frontier-direct-20261117`), 7, 9 and 6 from the three sets:
  - `questions.json`: P2, P3, P5, P7, P8, P13, P15
  - `hard-questions.json`: H4, H5, H6, H7, H11, H13, H14, H15, H17
  - `misleading-questions.json`: M2, M6, M9, M10, M11, M12
- **A smoke first:** one question, to see the reply's shape and what a call costs.

**The harness's side** is its recorded answers to the same 22 questions with the lookup that
reads the documents, as read in `docs/reviews/2026-11-15-lookup-reads-documents.md`,
`2026-11-15-professional-hard-run.md` and `2026-11-16-misleading-set-run.md`. The acceptance run
will replace those figures with fresh ones through the API.

## Money and stops

- The executor's estimate to the owner was '$0.20' to '$0.25' a call, about '$5' for 22.
- **Limit: '$6.00'.** The probe starts no call once '$5.60' is spent. A call can write at most
  8,000 tokens, about '$0.32', plus what it reads.
- **If the smoke shows 22 calls will not fit in '$6.00', the run is held and reported.** The
  amount is the owner's.

## How it is read

Each answer is read against the signed key, blind to nothing (there is one arm), by a Sonnet
reader and then by the executor. An answer is right when every key item is right. The reading
also records, for each wrong answer, which figure it gave and whether a page it cited prints
that figure.

## What is compared, and the bars

This is a description, not a contest with a pass mark. Reported side by side for the 22
questions: answers right, cost an answer, seconds an answer, and whether the answer names a
page that can be opened.

1. **The harness is not worse:** it is right on at least as many of the 22 as the frontier
   model, within one.
2. **The harness is much cheaper:** its cost an answer is no more than a tenth of the frontier
   model's.

- Both met: the thesis of `docs/MODELS.md` stands with a measurement behind it, and the figures
  go into that file.
- Bar 1 missed: the thesis is wrong as written for these questions. `docs/MODELS.md` is
  corrected, and which questions the frontier model won is reported to the owner.
- Bar 2 missed: the price argument is corrected to what was measured.

## Predictions

1. The frontier model is right on 19 to 22 of the 22.
2. Any miss is on the set where a summary misleads, on a figure a current official page still
   prints.
3. Its cost an answer is 15 to 30 times the harness's.
4. It takes less time an answer than the harness's 60 or so seconds.
5. Both bars are met.

## Limits, stated beforehand

- **22 questions, one answer each.** A difference of one or two is noise, and one answer says
  nothing about how steady the model is.
- **The readers are models of the same maker as the model being read.** The keys are figures
  and identifiers, which limits how far that can matter; the executor reads every answer too.
- **The harness's side was measured through a probe script on earlier days,** not fresh. The
  acceptance run repairs that.
- **One frontier model, one effort setting, one search setting.** Nothing here speaks for
  another model or for the same model with search off.
- **The draw left out H1,** the one question the harness has answered wrong (from a
  regulator's outdated page). The draw was made by the seed before any result and is kept.
