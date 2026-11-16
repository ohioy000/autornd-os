# The recompute step's sampler, and then the step itself (2026-11-16)

Preregistered in `docs/preregistration-20261115-recompute-samplers.md`, with two addenda, each
pushed before its spend. The owner stopped the test on 2026-11-16 with the words "we need to
look at the recompute as a whole rather than multiple models, cart before horse". This report
gives what the test found up to that point, and then the look at the whole step that followed.

## The point

- **The model was the wrong question.** Every model tested knew the key's figure nearly every
  time. They differed in whether the harness could read their reply, and little else.
- **The configured model was the best of the first four, not the worst.** It was the only one
  over the preregistered bar.
- **The bar itself did not hold up.** It asked whether a model's samples would catch an answer
  that states the commonly confused figure. On the real wrong answers of the three-arm run the
  samples made the same mistake as the answer, and the vote flagged none.
- **The owner's ruling, on that evidence:** the recompute step is off by default and kept for
  calculations (pull request #278). The recompute model is the owner's pin.
- **Cost:** '$1.02' recorded, against '$1.76' planned. Two answers were in flight when the
  second batch was stopped; at most '$0.03' more.

## What was run

`docs/probes/recompute_samplers_probe.py`: a live answer through the default workflow as
shipped; at its recompute step each other model makes three blind samples on the very same
request, context and asks as the configured one. 13 questions with signed keys: the 12 of the
set where a summary misleads, and H1 of the harder set.

| Batch | Models beside the configured one | Answers | State |
|---|---|---|---|
| First | `tencent/hy3`, `minimax/minimax-m3.1-flash`, `upstage/solar-pro4` | 39 of 39 | complete |
| Second | `anthropic/claude-haiku-5.5`, `qwen/qwen3.8-omni-flash` | 13 of 39 | stopped by the owner |

The configured model was `meta/muse-ember` in both. The other models ran with no provider pin
and at their catalogue defaults, as preregistered.

**Traces,** copied byte-identical: `docs/traces/20261115T-samplers-*` (first batch: shard-0
`a652ee2362fb…`, shard-1 `4a31b264a7bc…`), `20261115T-samplers-b-*` (second: shard-0
`e0c7d03dce79…`, shard-1 `9f42ec8ced3e…`) and `20261115T-samplers-smoke-*`. Every figure below
comes from `docs/probes/recompute_samplers_analysis.py` on those files.

## The first batch: 39 answers, four models

All 39 delivered answers hold the key's figure. No model's samples gave the commonly confused
figure, on any question, H1 included.

| Model | Samples in the shape asked | Samples with the key's figure, any shape | Would flag the confused figure | Flags on the answers as delivered | Compared nothing | Cost, 39 sets | Seconds a set |
|---|---|---|---|---|---|---|---|
| `meta/muse-ember` | 117 of 117 | 117 | **31 of 39** | 3 | 4 | '$0.107' | 8 |
| `minimax/minimax-m3.1-flash` | 116 of 117 | 117 | 28 of 39 | 1 | 8 | '$0.087' | 3 |
| `tencent/hy3` | 13 of 117 | 111 | 22 of 39 | 0 | 17 | '$0.123' | 46 |
| `upstage/solar-pro4` | 12 of 117 | 104 | 9 of 39 | 0 | 29 | '$0.126' | 6 |

- **Two models do not follow the reply's shape.** Solar puts its values under "answers" or
  "asks" where "results" is asked for; Hy3 returns one bare result. The harness reads neither,
  so their votes compare little.
- **Read whatever key the values sit under** (the reading added by the first addendum, free):
  Solar would flag the confused figure in 28 of 39, with 2 flags on right answers. Hy3 stays
  at 22 of 39, because its one bare result covers only the first ask.
- **Every flag on a delivered answer was false.** All 39 answers were right. The configured
  model's three are one artefact: the answer said "RFC 7540, RFC 8740" and the samples
  "75408740". MiniMax's one is a sample that was wrong about the Part 135 reduction.

## The second batch: 13 answers, stopped

| Model | Samples in the shape asked | Would flag the confused figure | Flags as delivered | Cost, 13 sets | Seconds a set |
|---|---|---|---|---|---|
| `meta/muse-ember` | 39 of 39 | 9 of 13 | 1 | '$0.028' | 7 |
| `anthropic/claude-haiku-5.5` | 39 of 39 | 9 of 13 | 1 | '$0.042' | 8 |
| `qwen/qwen3.8-omni-flash` | 39 of 39 | 7 of 13 | 1 | '$0.033' | 38 |

Thirteen answers show no difference between the configured model and Haiku except cost. All
three flagged the same right answer, on the same wording artefact.

## The bars and the predictions

| Bar | Result |
|---|---|
| The step is useful: some model flags the confused figure in at least 75 percent and no more than 10 percent of right answers | **Met as written,** by the configured model alone: 79 percent and 8 percent. **And not to be relied on;** see the next section |
| A model is advised over the configured one | **None.** MiniMax is 7 points behind and 19 percent cheaper; the bar was within 5 points and 30 percent |

| Prediction | Result |
|---|---|
| 1. Every model's samples give the key's figure at least 80 percent of the time | **Held,** read in any shape: 89 to 100 percent. By the figure check, not read by hand; a stated departure |
| 2. No model flags more than 3 right answers | **Held.** 3, 1, 0, 0 |
| 3. The best model flags the confused figure in 60 to 85 percent | **Held.** 79 percent |
| 4. The four are within 15 points of each other | **Wrong.** 79 to 23 percent as the harness reads them. The gap is the reply's shape |
| 5. On H1 some model's samples say 9 at least once | **Wrong.** None did |

**The owner's hypotheses, stated before the results.**
- That the document-work model (Solar) would do best because it is built for this: **not
  borne out.** Last as the harness reads it; level with MiniMax and behind the configured
  model when read in any shape.
- That the small model of a frontier lab (Haiku) is the best small model: **not shown.**
  Level with the configured model on 13 answers, at one and a half times the cost.
- That the configured model was the worst that could have been picked: **not borne out.** It
  was the best of the first four.

## The step as a whole

The owner's point was that the model is the cart and the step is the horse. The three-arm run
gives the step's record on real answers: phase 1, 215 delivered answers, each read blind against
its key, each with the vote as shipped (`docs/reviews/2026-11-16-misleading-set-run.md` has the
full run).

| | Count |
|---|---|
| Answers not right | 4 |
| Of those, flagged by the vote | **0** |
| Right answers flagged | 15 of 211 |
| Right answers flagged and cleared by the same-meaning switch | 11 more |
| Right answers where it compared nothing | 41 |
| The samples' share of a run's cost | '$0.16' to '$0.18' of '$0.83' to '$0.91' for 72 answers: about a fifth, and more than the answer step |

- **The wrong Part 135 answer:** all three samples said 12 hours too. They read the same
  paragraphs and made the same mistake.
- **The two stale BasicMed answers:** the samples agreed with the answer on the asks they could
  compare.
- **The 15 flags:** 14 are the "RFC 7540, RFC 8740" wording artefact. The fifteenth is a right
  answer where all three samples were wrong.

**Why the bar misled.** It scored the samples against an answer that states the confused
figure while the samples are right. That supposes the answer and the samples go wrong apart.
On a question a document answers they do not: an error comes from the text handed on, and the
samples are handed the same text.

**Where the step was proven,** Ruling D53's 5 of 5 on tier 4, the questions were calculations.
There an error is the model's own slip and a second attempt does differ.

**It is the judges' finding again.** D53 replaced the judges because across tiers 2 to 4 they
made no real catch and every dissent read was false. A second model shown the same material
either repeats the mistake or objects to the wording.

## What follows

- **Done, by the owner's ruling (#278):** the recompute step runs only for a request the new
  `needs_calculation` switch judges to need a calculation.
- **Not measured:** how that switch sorts lookups from calculations. It is week 1 of the
  handover's plan, with the owner's word, for cents.
- **The recompute model** is the owner's pin. The owner has said Haiku. On this evidence it is
  level with the configured model at one and a half times the cost, and neither has been
  measured on calculations.
- **If the step is kept for calculations,** two repairs found here apply to it: the vote should
  read "RFC 7540, RFC 8740" and "75408740" as the same identifiers, and the samples' reply
  should be read whatever key its values sit under. Both change what the vote concludes, so
  both are the owner's ruling.

## Limits

- 39 answers in the first batch and 13 in the second. Differences of 3 or 4 are noise.
- The samples' figures were checked by a free figure check, not read by hand.
- One reader for this report. The three-arm run's answers were read blind by Sonnet readers
  and re-read in part by the architect.
