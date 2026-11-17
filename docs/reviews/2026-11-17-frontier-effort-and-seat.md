# The frontier model at higher effort, and in the harness's answer seat (2026-11-17)

Preregistered in `docs/preregistration-20261117-frontier-two-more.md` (#287) and its addendum
(#288), each pushed before the spend it covers. '$3.03' was spent.

## The point

- **More reasoning effort bought nothing on these questions.** Asked directly with web search,
  `anthropic/claude-fable-5.2` was right on 14 of 14 at high effort, as it was at medium. High
  cost about one and a half times medium. One call at maximum effort cost '$1.05'.
- **The frontier model could not be run in the harness's answer seat.** On two questions it
  returned no text, and the provider gave the stop reason `content_filter`. The owner dropped
  the run. What trips the filter was not looked for.
- **The owner's hypothesis, that the harness's true use is making frontier models cheaper, was
  not tested,** and what little the blocked runs show points against it as the harness is
  built.
- **What the two days support:** the harness gives the same answers as a frontier model asked
  directly, for about a sixth of the price, with a record of what was read. It is not shown to
  be more accurate. Both were right on every question.

## Run 1: effort, asked directly

`docs/probes/frontier_direct_probe.py`, the same 14 questions drawn by seed from the 22 of the
first comparison, once each. Traces, byte-identical:
`docs/traces/20261117T-frontier-direct-high.jsonl` (`4da6531fd2b3…`) and
`20261117T-frontier-direct-max.jsonl` (`11646b25fc52…`).

| Effort | Right | Cost an answer | Seconds | Answers naming a page | Reasoning tokens an answer |
|---|---|---|---|---|---|
| Medium (2026-11-17, first comparison) | 14 of 14 | '$0.070' | 8.9 | 10 of 14 | under 100 on most |
| High | 14 of 14 | '$0.102' | 10.6 | 12 of 14 | 0 to 1,500 |
| Maximum, one call | 1 of 1 | '$1.05' | 224 | 1 of 1 | about 23,000 |
| The harness as shipped, recorded | every recorded answer | '$0.011' | about 60 | every answer that ran a lookup | |

- **Reading.** A Sonnet reader graded the 14 and the one: all right. The executor screened each
  answer for its key's figures; the two the screen stopped on are the notation and itemising
  cases of the first comparison, and both are right.
- **A stated departure.** The owner asked for maximum effort on 14 questions. The one-question
  smoke cost '$1.05', so 14 would have cost about '$15' against a '$6.00' limit. On the owner's
  word the run was made at high effort within '$5.00'; it cost '$2.48' with the maximum call.
- **The executor's prediction** for maximum effort was 3 to 8 times medium's cost. It was about
  15 times, on one call. For high effort the prediction of '$0.15' to '$0.50' a call was too
  high.

## Run 2: the frontier model in the answer seat, dropped

`docs/probes/frontier_in_harness_probe.py`: the default workflow as shipped, with only the
answer tier changed to the frontier model.

| Question | Effort setting sent | What happened | Cost |
|---|---|---|---|
| P2, truck driver hours | medium | lookup ran, 16 passages found; the answer step returned no text; run ended blocked | '$0.27' |
| M10, the Social Security wage base | none | the same | '$0.27' |

Records: `docs/traces/20261117T-frontier-in-harness-blocked-P2.jsonl` and `…-M10.jsonl`. The
error in both is "model returned no text (provider=Anthropic, finish_reason=content_filter)".

- **It is not a reply in the wrong shape.** The model wrote nothing; a filter stopped the reply.
- **It is not a block on the model or the key.** The same model answered 37 direct calls on the
  same two days.
- **So something in the harness's answer request trips it, and what is not known.** Two things
  in that request are unlike a plain question: it tells the model never to reply that it is
  unable, and it asks for step-by-step reasoning in a field of its own. Both were written for
  inexpensive models that refuse or skip steps. Neither was tested as the cause.
- **No attempt was made to get round the filter.** It is the provider's safeguard.

**On the owner's hypothesis.** Each blocked run spent about '$0.27' on answer-step calls that
returned nothing. If that was three attempts, one attempt cost about '$0.09' for the text
handed on alone, more than the '$0.071' the same model costs for a whole answer asked
directly. The retry count was not confirmed, so this is a pointer and not a measurement. A
harness built around a frontier model, handing on less text, is a different design and was not
tried.

## What follows

- `docs/MODELS.md` gains the effort figures and the note on the answer seat, in this pull
  request.
- **A known limit for the release:** the default answer-step prompt can trip a safety filter
  on at least one frontier model. Anyone who puts such a model in that seat should try one
  request first. Changing the prompt changes what every model in that seat is told, so it is
  the owner's ruling and would need the question sets run again.

## Limits

- 14 questions, one answer each, and one call at maximum effort.
- Every row is at the ceiling for correctness, so only cost and time are shown.
- The filter was met on two questions and not investigated.
- The readers are models of the same maker as the model read.
