# The models: what we chose, how the choices changed, and why they stand

AutoRnD ships with no model named anywhere a user reads first. Tiers are named by job, every
tier ships empty, and you put in what your provider serves. This file is the one place that
names what **we** ran, tier by tier, and argues why we think those choices are right today.
It lives under `docs/` because the project's rule keeps model names and prices out of the
README and the configuration template.

Every figure comes from the record and says where it stands. Where the record does not say why
a model was chosen, this file says so instead of inventing a reason.

## The thesis

**For the questions this harness is built for, the model that writes the answer is not what
decides whether the answer is right. What it is given to read decides it.** So we buy
inexpensive models for every job, spend the effort on getting the right page in front of them,
and pin who serves each one.

The evidence, in the order we met it:

1. **A strong model and an inexpensive one were close as single calls.** On 21 frozen
   engineering questions one call to `gemini-3.8-flash` held 18 under the strict key, and one
   call to `kimi-k3`, the strongest serving we measured, also held 18, at three times the cost
   an answer. Counted more loosely, accepting three significant figures, it was 19 against 21
   (`docs/reviews/2026-10-06-tier3-stage1-report.md`). On the harder tier-4 questions the two
   were level, and the strong call failed one of eleven on a notation trap.
2. **More models looking at the answer did not help.** The full team of that day delivered 0 of
   21 for '$7.33'. Judges on three tiers made no real catch. A second model shown the same
   material repeats the mistake or objects to the wording (`docs/reviews/2026-11-16-recompute-samplers.md`).
3. **The text handed on is what moved the result.** On two questions that had been answered
   wrong 8 times from a search model's summary, the same inexpensive model was right 8 of 8
   once it was handed the governing section's own words (`docs/reviews/2026-11-15-root-cause.md`).
4. **With that in place the answers are right nearly every time.** 107 of 107 professional
   answers, then 144 of 144 on a set built from questions where a summary misleads, read blind
   against signed keys (`docs/reviews/2026-11-16-misleading-set-run.md`). The final
   configuration was then run once on all three sets, six answers to each of 44 questions:
   259 of 264 right on the key (248 on a stricter reading), for about '$0.009' an answer
   (`docs/reviews/2026-11-17-acceptance-run.md`). The five that are not right are an omission, a
   form, a datasheet figure and a misdefined term; none is an older figure.
5. **A small model from a frontier lab, tried in one seat, was level and dearer.** In the
   recompute seat `claude-haiku-5.5` and the model it replaced each scored 9 of 13, at one and
   a half times the cost.
6. **On the questions we shaped the harness against, a frontier model asked directly is just as
   right, faster, and about six times dearer.** On 22 of the professional questions `claude-fable-5.2`, with web search on and no harness,
   was right on all 22 in 8.5 seconds an answer for '$0.071'. The harness is right on the same
   22 in about a minute for '$0.011' (`docs/reviews/2026-11-17-frontier-direct.md`).
7. **More reasoning effort did not change the answers.** The same model at high effort was
   right on 14 of 14, as at medium, for about one and a half times the cost. One call at
   maximum effort cost '$1.05' (`docs/reviews/2026-11-17-frontier-effort-and-seat.md`).
8. **On 42 new questions, a frontier model asked directly was more accurate, faster, and about
   nine times dearer.** The same model, with web search on and no harness, was right on all 42
   (one draw each) in 11.2 seconds an answer for '$0.0986'. The harness was right on 113 of its 126 answers
   (89.7 percent) in 107 seconds for '$0.0108'. These questions were written after the harness
   was fixed, by authors that never saw its answers
   (`docs/reviews/2026-11-18-frontier-direct-holdout.md`).
### What the direct comparison changed

Before 17 November this file argued from our own runs alone. The comparison with a frontier
model corrected it in two ways, and both are kept here plainly:

- **A frontier model does not get these questions wrong.** The case for the harness is not
  better answers. It is the same answers for about a sixth of the price, with a record of
  every passage read.
- **The price gap is about six times, not the fifteen to thirty we predicted.** A frontier
  model's answer costs cents, not dimes. On the 42 new questions it was about nine times.
- **On new questions the frontier model is the more accurate** (added 18 November). It was right
  on 42 of 42 against the harness's 113 of 126, ten points apart. The first two points above
  were measured on questions the harness was shaped against, where both were at the ceiling.
  The hold-out shows the gap that shaping hid. The harness's misses scatter across draws: each
  of the 11 questions it missed was right in at least one of its three draws. A lookup that read
  three pages or fewer was not right in 6 of 13 units, against 7 of 113 when it read four or
  more (`docs/reviews/2026-11-19-holdout-misses-classified.md`). The frontier model had one draw
  a question. A rerun of those 11 questions (19 November) gave the harness 24 right of 28 answers
  made (85.7 percent, against 60.6 percent the first time) and the frontier model at low effort 27
  of 27, at about a tenth of the cost an answer for the harness. On 8 of the 11 the first run's
  misses were draws; on three (the transport index, the instrument in force, a datasheet that
  states no figure) the harness is weak. Eleven of the 66 draws were never made, because the
  provider refused calls for credit (`docs/reviews/2026-11-19-eleven-rerun.md`).

So the thesis is narrower than a reader might hope: **inexpensive models, handed the right
page, match a frontier model on the questions the harness was shaped against, and on new
questions they are about ten points behind it. They do not beat it on either.** What you buy
with the harness is cost at volume, a checkable record, and freedom from any one model. What you
give up is speed, simplicity and, on new questions, about ten points of accuracy.

### Why this holds as cheaper frontier models arrive

- **On the sets we shaped it against, there is little left for a better answerer to win.** Those
  question sets are at the ceiling. A model that is right 144 times in 144 cannot be beaten on
  that set, only matched for more or less money. On new questions there is room: the harness
  was right on 113 of 126, and a frontier model asked directly on 42 of 42.
- **The answer step is a small part of the bill.** A lookup answer costs about '$0.011' and a
  calculation about '$0.004' (`docs/reviews/2026-11-16-needs-calculation.md`). In the 144
  lookup answers of 15 November the answer step was about 16 percent of the cost and grounding
  (the search, the scoping and the briefing) about 59 percent, worked out from the phase rows
  of `docs/traces/20261115T-misleading-documents-phases-shard-*.jsonl`. Halving the answer
  model's price moves an answer's cost by under a tenth of a cent.
- **The failures that remain are not failures of intelligence.** The wrong answers we still see
  come from a stale official page that looks current, from a sister rule quoted word for word,
  and from sites that refuse to be read. A stronger model handed the wrong page states the
  wrong page's figure with more confidence, not less. The last run's five misses were of another
  kind: a figure given without the parts that make it, a form of a figure not given, a datasheet
  figure misread, and a term defined wrongly beside a right figure. The checks read the figures
  asked for and not the prose around them.
- **Serving matters as much as the model, and we control it.** The same model served by five
  providers classified 22 to 33 of 36 test cases correctly (`HANDOVER.md` §6.1). Open-weight
  models can be pinned to one provider at one precision. That choice is ours to make and to
  measure.
- **Nothing here depends on one lab.** Every tier is a job with a model id in a file. If a
  cheaper frontier model becomes the better buy for a seat, it is a one-line change, as the
  recompute seat showed.

### What this thesis does not claim

- **We could not run a frontier model as the answer step inside today's harness.** We tried
  on 17 November: the model returned no text and the provider reported a content filter, on
  two questions. Something in our answer request trips it; we did not look for what. So this
  file makes no claim about the harness making a frontier model better or cheaper.
- **It does not claim the harness is as accurate as a frontier model on questions it was not
  shaped against. On those it is less accurate.** Asked directly, the frontier model was right
  on every question we put to it: 22 of 22 on the questions the harness was shaped against, and
  42 of 42 on new ones. On the same 22 the harness's acceptance answers were right 131 of 132,
  so the two were equivalent there and the samples are too small to say more. On the 42 new
  questions the harness was right on 113 of 126, and the gap of ten points is outside what one
  answer's noise explains.
- **It does not claim the harness is the better buy for everyone.** For a handful of questions
  a frontier model with search is simpler and faster. The harness earns its keep at volume, or
  where the record of what was read matters.
- **It is a claim about precise questions whose answer is written on a page that can be read,**
  and about short calculations. It is not a claim about open design work or long reasoning,
  where the tier-4 results suggest a strong model may earn its price.
- **"As of now" is meant.** The comparison should be run again when prices or the question
  sets change.

## The configuration as last recorded

From the header of the run of 2026-11-16
(`docs/traces/20261116T-needs-calculation-end-to-end-header.json`).

| Tier | Its job | Model | Served by |
|---|---|---|---|
| triage | classify the request, list what it asks | `openai/gpt-oss-120b` | crusoe, bf16 |
| engineering | write the answer | `deepseek/deepseek-v4.1-flash-1017` | deepinfra, fp8 |
| research | scope the request, brief the answer step | `z-ai/glm-5.3` | wafer |
| search | name the documents the answer is written in | `perplexity/sonar` | Perplexity |
| ranker | order stored passages | `qwen/qwen3-reranker-8b` | Fireworks |
| recompute | three blind recomputations, for calculations only | `anthropic/claude-haiku-5.5` | Anthropic |
| decision | the four yes/no switches | `perplexity/pplx-decider-v1.2` | not pinned |
| architecture | plans, in the longer workflows only | `xiaomi/mimo-v2.6-pro:exacto` | gmicloud, bf16 |
| escalation | failure autopsy, in the longer workflows only | `google/gemini-4-argon` | google-vertex |
| judge | review, in the longer workflows only | `qwen/qwen3-235b-a22b-2507:exacto` | deepinfra, fp8 |
| premium | an independent second check | none | |

The default workflow uses the first seven. The last four serve the longer workflows that are
still offered by name.

## How each choice changed

### Search: the clearest case for the cheaper model
- `sonar-pro`, then `sonar` from 14 September.
- **Why:** over three repetitions the two tied exactly, 3.67 of 8 each. The cheaper one cost
  '$0.0062' a lookup against '$0.0510' and took half the time (`HANDOVER.md` §6.3).
- **What changed later is its job.** Since 15 November it is asked where the answer is written,
  not what the answer is, and the harness reads the pages itself. The model no longer has to be
  right about the answer, only about where to look.

### Engineering: the seat that writes the answer
- `minimax-m3` → `deepseek-v4-flash` → `mimo-v2.6-flash` → `glm-5` → `qwen3-235b` →
  `inkling:exacto` → `deepseek-v4.1-flash` (13 November).
- **Why the early changes:** each was a failure to return an answer at all. One model spent all
  16,384 tokens reasoning and returned no text. One serving returned an empty object three
  times. One returned 404 on a long request. `glm-5` was the first to complete a full run.
- **Why the later changes:** the record does not say. They were the owner's choices in the
  live configuration.
- **What we learned:** in this seat a model fails by returning nothing or by a provider's
  limits, far more often than by reasoning badly.

### Triage
- `deepseek-v4-flash` → `gemini-3.8-flash` (30 September) → `gpt-oss-120b` (13 November).
- **Why the first pin:** a sweep of 36 cases, three times each, across five providers of one
  model. Three qualified and the fastest was taken. Cheap servings rated risk too low, which is
  the dangerous direction.
- **Why the later changes:** the record does not say.

### Recompute
- `gemini-3.8-flash` (October) → `meta/muse-ember` (13 November) → `claude-haiku-5.5`
  (16 November, the owner's choice).
- **The evidence for the step:** on hard calculation questions a vote of three blind
  recomputations flagged 5 of 5 wrong answers and 1 of 23 right ones (Ruling D53).
- **The test of the model** (`docs/reviews/2026-11-16-recompute-samplers.md`): of four models
  on 39 answers the configured one was best. Two others knew the figures and put them in a
  reply shape the harness does not read. On a second batch of 13, Haiku was level with it at
  one and a half times the cost.
- **The larger finding:** the model was the wrong question. On answers read from a document the
  samples read the same text and made the same mistake. The step now runs only for
  calculations.

### Decision
- `pplx-decider-v1.2`, added 13 November. It returns a probability and no text.
- **Evidence:** 0.00 on a request that needs no source and 0.98 to 1.00 on eight that do. Asked
  whether a request needs a calculation: no on 49 of 49 lookups, yes on 15 of 15 calculations
  (`docs/reviews/2026-11-16-needs-calculation.md`). A full set of its questions costs a small
  fraction of a cent.

### Research and ranker
- **Research:** `gemini-2.5-flash` → `gemini-3.8-flash` → `glm-5.3`. The record calls the
  first pick "interim and unmeasured" and gives no reason for the changes.
- **Ranker:** `qwen3-reranker-8b` throughout. It has never been compared with another.

### The tiers the default no longer uses
- **Architecture.** `glm-5.3` returned a plan-shaped stub with nothing in it across four
  providers. `deepseek-v4-pro` spent whole token budgets and returned nothing on hard plans.
  `inkling-small` and then `mimo-v2.6-pro` were the first to return real plans.
- **Escalation.** `kimi-k3` won a blind shootout, about 19 of 20 against 13 of 20 for a model
  a fourteenth of its price (`docs/shootout-086-ratings.md`). It was the one seat where the
  dear model clearly earned its cost, and it took 70 to 78 percent of a hard run's spend. The
  move to `gemini-4-argon` in November is not explained in the record.
- **Judge.** Five models in one night, from '$0.50' a pass down to a fraction of a cent. Then
  the finding that ended the seat: across three tiers of questions a judge made no real catch.
- **Premium.** A frontier model sat here in September as an independent check. It was left
  empty on purpose from 3 October: "no frontier model sits inside" the measured pipeline.

### A profile's own model: one legal pin, proposed, not ratified (2026-11-21)
- **The model.** `z-ai/glm-5.3-flashx-legal`, listed in the public catalogue on 21 November (about three
  weeks old) and the only domain-named model among the 476 listed. One endpoint, Z.AI (`z-ai/fp8`, fp8).
  Context 1,048,576 tokens, output ceiling 131,072. The same price as `glm-5.3-flashx`: '$0.37' a million
  tokens in, '$1.25' out. It accepts typed output, reasoning and tools.
- **The pin proposed.** `PROFILE_MODELS=legal:engineering=z-ai/glm-5.3-flashx-legal@z-ai`: the legal
  profile's answer tier and no other tier, no other profile. It waits on the owner (G-2); no `.env` carries it.
- **What the smoke read** (`docs/preregistration-per-profile-pins-smoke.md`; seven runs, '$0.1521' in all; one run
  for each cell, so each figure is one observation). Under the legal profile the model that replied to the
  answer call was the pinned one in all three runs, served by Z.AI, and billed at its catalogue rate to within
  0.3 percent. One of the three replies was rejected once against the verdict's schema and the retry was
  accepted. The three runs cost '$0.0402', '$0.0418' and '$0.0100'. The same requests under the general
  profile, with the same pin in the environment, never reached it, and under the engineering profile the
  answer stayed on the engineering model above.
- **Not measured.** Whether its answers are better than the engineering model's on legal questions, on any
  question set with signed keys, or at more than one run a request. The smoke is evidence of serving, cost and
  typed output, not of quality.

### A second triage model, read with its thinking off and on (2026-11-22)
- **The model.** `tencent/hy4-flash`, released 16 November; one endpoint, Tencent (`tencent/fp8`, fp8). Context 1,048,576,
  output ceiling 65,536, typed output and reasoning supported. '$0.035' in and '$0.1405' out per million tokens, against
  '$0.09' and '$0.36' for the model it was read against.
- **What it did on the triage seat** (wide suite, 36 sectors, five repeats, 180 units an arm; the evidence is
  `docs/reviews/2026-11-22-triage-model-hy4-flash.md`). Zero rejected replies and zero provider failures in 1,760 units.
  With its thinking off: about 60 completion tokens, 2.2 to 2.4 seconds, '$0.0031' to '$0.0036' an arm, and 6 units below a
  risk floor on the old guide where the first model had 0. With its default thinking: 2,800 to 4,500 tokens, 17.6 to 25.1
  seconds, '$0.0718' to '$0.0907' an arm, and 0 units below a floor on the old guide (171 meeting the bounds, the limit).
- **A repeat with default thinking** of the old guide, the finance text and the legal text, 180 units each ('$0.2454'):
  the old guide 1 unit below a floor and 171 meeting the bounds, finance 1 and 173, legal 0 and 173, so the two field
  texts held in both runs and the old guide as a baseline held in both.
- **The medical text after its examples were fixed**, default thinking, 180 units ('$0.1176', 26.6 seconds a unit, no errors): 2 units
  below a floor (both the semiconductor sector) and 173 meeting the bounds, dentistry `high` on 5 of 5. One run.
- **Two models in the catalogue, never run in this harness before 2026-11-22** (free reads only): `qwen/qwen4-max`, one endpoint (Alibaba),
  context 1,000,000, output ceiling 131,072, typed output and reasoning, '$1.425' in and '$4.275' out per million; and
  `google/gemini-4-hydrogen`, Vertex and AI Studio endpoints, context 1,048,576, output ceiling 943,718 on Vertex, typed output and
  reasoning, '$1.50' in and '$7.50' out per million. Both pass preflight as pins. Run once each in the line-up smoke
  (`docs/reviews/2026-11-22-model-lineup-smoke.md`): `qwen4-max` via Alibaba, one question, '$0.0078' for the answer call; hydrogen via
  Google on a finance and on a medical question, '$0.0216' and '$0.0599' for the answer call; no rejected replies and no provider
  failures. The spend guard could not bound `qwen4-max` (its cache-write rate, '$1.78' per million, is above its prompt rate) nor the
  global answer model (time-of-day price overrides), so both ran unbounded; it bounded hydrogen, the legal model and `hy4-flash`.
- **The first model at high reasoning effort** ('$0.2567', three arms): finance 9 units below a floor and legal 8, against
  24 and 10 at its default effort and 1 and 0 to 1 for this model with thinking on; 10 seconds a unit and '$0.079' to
  '$0.090' an arm. More thinking alone did not bring those texts within the margin.
- **Not measured.** Anything but triage; a repeat of the medical or the thinking-off arms. A pin for `finance` and `legal`
  is proposed in the record and is the owner's (G-2).

### The line-up on 174 unseen questions (2026-11-22)
- **What ran.** The owner's line-up as shipped: `tencent/hy4-flash` with its default thinking on the triage seat, the global
  answer model (`deepseek/deepseek-v4.1-flash-1017`, DeepInfra) on the engineering seat, and the three pins: the legal model
  (`z-ai/glm-5.3-flashx-legal`, Z.AI) for legal, `google/gemini-4-hydrogen` (Google) for finance and medical. The default
  workflow, one answer a question, on `professional-holdout-2`; the evidence is `docs/reviews/2026-11-22-holdout2-run.md`.
- **Right on the key:** 169 of 174 answers made (14 of 14 legal on the legal model, 13 of 14 finance and 14 of 14 medicine on
  the large model, 14 of 14 natural science and 114 of 118 of the engineering groups on the global answer model).
- **What a whole answer cost, all tiers together:** '$0.0125' to '$0.0161' an answer on the arms that use the global answer
  model; '$0.0258' with the legal model; '$0.0715' (finance) and '$0.0569' (medicine) with the large model. Run total
  '$4.72' for 230 answers.
- **Against the line-up before today** (the same 56 field questions, the earlier triage model and no pins): 55 right against
  51, no difference shown by the rule written before the run (+5 was "better"). Two of the earlier line-up's five were
  upstream 429s on its triage model. The field arms cost '$2.34' for the 56 answers, the earlier line-up '$0.70'.
- **Served as set** in every unit: the pins' own provider each time, no rejected replies, no spend-guard blind entry.
- **The pins apart from the profile and the triage model** (the same 42 law, finance and medicine questions, the global answer
  model and no pin, `docs/reviews/2026-11-22-holdout2-unpinned-arm.md`, '$0.69'): 42 of 42 right against 41 of 42 for the pinned
  arms, so no gain shown for the pins at 3.1 times the cost; the gain of the line-up over its predecessor came from the field
  profiles and the new triage model.
- **Not measured.** More than one answer a question; a harder set, where a larger model could show a difference this one could
  not; anything but this one set.
- **The owner's ruling of 2026-11-23:** the three pins and the reader tier are removed from the owner's `.env` (the code for
  both stays, empty by default); the second triage model and the field profiles stay.

### The line-up with the pins and the reader off, on 311 questions (2026-11-23)

- **What ran:** the shipped line-up after the owner's ruling (global answer model on every engineering seat, the second triage model on every triage seat, no pin, no reader call), the default workflow, one answer a question, on 311 questions in eight sets and the 56 field questions again on the engineering profile; `docs/reviews/2026-11-23-final-tally.md`, '$4.27'.
- **Result:** 292 of 311 right; 167 of 174 on the unseen second hold-out set against 169 with the reader on and the pins; no difference shown between the field profiles and the engineering profile on the 56 (-1). Two of the seven unseen misses (Y115, Y88) carried the answer's wording in the earlier reader-on run's handed-on text and not in this one: a lead, not a measurement, that the reader may be worth one or two answers in 174.
- **Served as set** in every unit; five units ended on a provider failure (the model returned no text, finish reason length at 16,384 completion tokens, provider Tencent), one blocked on an ask it could not satisfy; 6 of 311, the bar allowed 9.
- **Not measured:** more than one answer a question; the reader on over a whole set in the same run.

## What the changes have in common

- **Most early changes were forced by a model returning nothing,** not by a model being wrong:
  empty replies, truncation, 404s on long requests, rate limits at one provider.
- **The pin is part of the choice.** A model id without its provider and precision is half a
  configuration.
- **A reply in the wrong shape looks like a model that knows nothing.** Two of six models in
  the recompute test knew the answers and were unreadable.
- **The dear model earned its place once,** in escalation, in a workflow the default no longer
  runs.

## What we have not measured

- A frontier model as the answer step inside today's harness, or more than one answer a
  question from a frontier model asked directly.
- Either side on questions hard enough to separate them. Every set is at the ceiling for both.
- The ranker and the research tier against any alternative.
- The reasons for the re-tiering of 12 and 13 November, which the record does not hold.
- The recompute step with its present model on a calculation the answer step gets wrong: on
  15 calculations every answer was right, so there was nothing for it to catch.

## If you are choosing your own

1. **Start with the least expensive model that returns the reply shape reliably.** Run
   `python -m autornd.preflight`; it checks each model and pin against the catalogue for free.
2. **Pin a provider for each tier,** and prefer full precision for the seat that writes the
   answer.
3. **Spend on the search tier's instructions and on readable sources before you spend on a
   stronger answerer.**
4. **Measure on your own questions with signed keys,** and read the answers. Our sets and
   scripts are in `evals/professional/` and `docs/probes/`.
