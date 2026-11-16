# Preregistration: the recompute step's samples from four models (2026-11-15)

Written and pushed before the run. The owner's word of 2026-11-15: the record does not show the
recompute step is useful yet, its model was never compared with another, and the test is to be
run with the architect's shortlist of four, side by side.

## Why

- The recompute model is a pin in the owner's `.env`, set in the re-tiering of 2026-11-12/13.
  The record holds no comparison behind it.
- Ruling D53's evidence (5 of 5 wrong answers flagged, 1 of 23 right ones) was measured with
  another model as the sampler, on other questions.
- With the present model, on the two professional sets: 3 flags in 96 answers, 1 true and 2
  false. In 2 of the 3 wrong flight-attendant answers all three samples repeated the wrong
  figure.
- The three samples are the largest single line of an answer's cost.

## What is run

`docs/probes/recompute_samplers_probe.py`. One unit is one live answer through the default
workflow as shipped. At its recompute step the configured model makes its three blind samples as
always; then three other models each make three, at the same moment as each other, shown the
very same request, context and asks. The run goes on with the configured model's samples. So for
every answer there are four sets of samples that differ in the model and in nothing else.

- **The four models:** the configured recompute model, and three named in `SAMPLER_MODELS`,
  recorded in the run's header. They were chosen from the public catalogue of the date: from a
  maker no tier uses, not built on a model a tier uses, not described by its maker as its
  frontier or flagship model, at about the configured model's price, and able to return the
  typed reply.
- **The other three are not pinned to a provider.** The owner's pin names a provider of the
  configured model only. Each model reasons at its catalogue default. Both are conditions of
  this test and not proposals.
- **The questions:** the 12 of the set where a summary misleads, and H1 of the harder set. 13
  questions, three answers each: 39 answers, 156 sets of samples.
- **It runs beside the three-arm run** of `docs/preregistration-20261115-misleading-set-run.md`,
  in two processes. The samples fetch no page.

**Cost.** About '$0.95' expected: about '$0.012' an answer as shipped, and about as much again
for the three other models' samples. Each of the two processes stops starting answers once its
own spend, the other models' samples included, reaches '$0.49': '$0.98' in all. A process can
pass its stop by the one answer it is in, about '$0.03'. The architect told the owner "well
under '$1'" before working it out; this is under '$1' and not well under.

## What is read

For each model, over the 39 answers:

1. **Its samples against the key,** read by hand: how many of its samples give the key's
   figure.
2. **The vote it would have given on the answer as delivered,** worked out free by the
   harness's own vote: flags on right answers, flags on wrong answers, and how often it compared
   nothing.
3. **The vote it would have given on the commonly confused figure.** The same samples, voted
   against an answer stating the figure the question is commonly answered with (6,000 pounds for
   M1, 9 hours for H1, and so on, one figure a question, listed in the analysis script before
   the samples are read). A wrong answer is rare with the shipped lookup; this asks of every
   unit whether the model's samples would have caught the likely one.
4. **Cost and time** of its three samples.

## The bars

- **The step is useful on these questions** if some model's vote flags the commonly confused
  figure in at least 75 percent of answers (reading 3) and flags no more than 10 percent of
  right answers (reading 2).
- **A model is advised over the configured one** if it is at least 15 points better on reading
  3 with no more false flags, or within 5 points and at least 30 percent cheaper.
- No model meets the first bar: the architect puts to the owner whether the step should run at
  all on questions of this kind.
- A pin is the owner's (G-2). The report proposes; it changes nothing.

## Predictions

1. Every model's samples give the key's figure in at least 80 percent of cases: the context
   holds the page's own text.
2. Reading 2: no model flags more than 3 of the right answers.
3. Reading 3: the best model flags the confused figure in 60 to 85 percent of answers. What
   holds it back is asks the vote cannot compare, not samples that are wrong.
4. The four models are within 15 points of each other on reading 3. No model is advised over
   the configured one on quality; one may be on cost.
5. On H1, at least one model's samples say 9 at least once.

## Limits, stated beforehand

- **39 answers.** A difference of 3 or 4 between two models is inside the noise.
- **One reader.** D50 asks for two; a stated departure.
- **With the shipped lookup the context usually holds the right passage.** The test says how a
  sampler reads the text handed on. It says little of how a sampler does when the text handed on
  misleads, which is where a different maker should matter most; H1 is the one question here
  that looks at that.
- **Unpinned providers** may serve a model at different precision from call to call.

## Addendum, 2026-11-15: a fifth model, on the owner's word

Written and pushed before any spend on it, while the run above was under way and after a first
look at 11 of its 39 answers. That look is said here because it prompted the addendum: the
configured model and one other returned every sample in the shape the harness reads; the two
others returned most of theirs under another key, so the vote could compare little.

- **The owner's hypotheses, stated before the results:** first, that the document-work model of
  the shortlist would do best because it is built for this; then, on the first look, that the
  small model of a frontier lab is the best small model and should be tested.
- **What is added:** a second batch of the same probe with one other model, named in
  `SAMPLER_MODELS` and recorded in its header: the same 13 questions, three answers each, 39
  answers. Each has the configured model's samples and the fifth model's, on the same request,
  context and asks. It is paired with the configured model, which is in both batches, and not
  with the other three.
- **It is the small model of a frontier lab.** The shortlist left such models to the owner; the
  owner has now asked for it. The mission is non-frontier models, and whether this one counts is
  the owner's to say.
- **It runs after the first batch ends,** so no more than five processes fetch pages at once.
- **Cost:** about '$0.60' expected: an answer as shipped and one more set of samples. Stops of
  '$0.32' on each of two processes, '$0.64' in all. With the first batch that is '$1.62' for the
  sampler test.
- **The probe now keeps the context each unit's samples were shown,** so a model added after
  this can be tested on the same units for the cost of its samples alone.
- **One free reading is added for every model:** the recorded samples voted again by a reader
  that takes the values whatever key they sit under. It separates a model that does not know
  the figure from one that does not follow the reply's shape. The bars above are read on the
  harness as it is; this reading is reported beside them.
