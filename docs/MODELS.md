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
6. **A frontier model asked directly is just as right, faster, and about six times dearer.**
   On 22 of the professional questions `claude-fable-5.2`, with web search on and no harness,
   was right on all 22 in 8.5 seconds an answer for '$0.071'. The harness is right on the same
   22 in about a minute for '$0.011' (`docs/reviews/2026-11-17-frontier-direct.md`).
7. **More reasoning effort did not change the answers.** The same model at high effort was
   right on 14 of 14, as at medium, for about one and a half times the cost. One call at
   maximum effort cost '$1.05' (`docs/reviews/2026-11-17-frontier-effort-and-seat.md`).

### What the direct comparison changed

Before 17 November this file argued from our own runs alone. The comparison with a frontier
model corrected it in two ways, and both are kept here plainly:

- **A frontier model does not get these questions wrong.** The case for the harness is not
  better answers. It is the same answers for about a sixth of the price, with a record of
  every passage read.
- **The price gap is about six times, not the fifteen to thirty we predicted.** A frontier
  model's answer costs cents, not dimes.

So the thesis is narrower than a reader might hope: **inexpensive models, handed the right
page, match a frontier model on these questions; they do not beat it.** What you buy with the
harness is cost at volume, a checkable record, and freedom from any one model. What you give up
is speed and simplicity.

### Why this holds as cheaper frontier models arrive

- **There is little left for a better answerer to win.** Our question sets are at the ceiling.
  A model that is right 144 times in 144 cannot be beaten on that set, only matched for more or
  less money.
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
- **It does not claim the harness is more accurate than a frontier model.** Asked directly, the
  frontier model was right on every question we put to it. The two are level.
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
