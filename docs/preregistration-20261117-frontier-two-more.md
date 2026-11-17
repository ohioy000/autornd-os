# Preregistration: two more data points beside the frontier comparison (2026-11-17)

Pushed before the spend. The owner's word, 2026-11-17: "Run another Fable max, 14 questions, to
get another data point, and in parallel run the harness with Fable med as the most intelligent
tier with 22 of the same that were used in the Fable med test that was just done, to get the
final data point and see if this harness's true use is making frontier models cheaper."

**The owner's hypothesis, recorded before any result:** the harness's true use is making
frontier models cheaper.

## What the first comparison found

`docs/reviews/2026-11-17-frontier-direct.md`: asked directly with web search at medium effort,
`anthropic/claude-fable-5.2` was right on 22 of 22, in 8.5 seconds and '$0.071' an answer. The
harness as shipped is right on the same 22 in about a minute for '$0.011'.

## Run 1: the frontier model asked directly, at maximum effort

`docs/probes/frontier_direct_probe.py`, as in the first comparison, with two changes: reasoning
effort `max`, and a call may write up to 32,000 tokens. If the provider refuses `max` as a
value, the highest effort it accepts is used and the report says which.

- **Questions:** 14 of the same 22, drawn from them by the same seed: P2, P5, P7, P15, H4, H5,
  H11, H13, H15, M2, M6, M9, M10, M12. Once each.
- **Limit: '$6.00'.** The probe starts no call once '$4.70' is spent. One call can cost about
  '$1.30' at most.

## Run 2: the harness with the frontier model in its answer seat

`docs/probes/frontier_in_harness_probe.py`: the measurement runner unchanged, the default
workflow as shipped on main at the commit that carries this file, with the answer tier
(`MODEL_ENGINEERING`) set to `anthropic/claude-fable-5.2`, pinned to its maker, reasoning
effort medium. "The most intelligent tier" is read as the seat that writes the answer: it is
the only seat in the default workflow that reasons about the question. Every other tier, the
lookup, the checks and the delivery are as shipped. The owner's `.env` is not changed; the
model is named in the process's environment.

- **Questions:** the same 22, once each, in three processes, one a set.
- **Limit: '$8.00'.** The three processes stop starting units at '$2.30', '$3.00' and '$2.00'.
- **A smoke first,** one question, to see that the effort setting reaches the model and what an
  answer costs. If 22 will not fit in the limit, the run is held and reported.

## How they are read

As before: a Sonnet reader against the signed keys, then the executor. Run 2's answers are
also read for what the delivery says beside them: "verified" lines and cautions.

## What is compared

Four rows for the same questions: the harness as shipped, the frontier model asked directly at
medium effort, the same at maximum effort, and the harness with the frontier model in its answer
seat. For each: answers right, cost an answer, seconds an answer.

**The owner's hypothesis is held to one bar:** the harness with the frontier model in its
answer seat costs less an answer than the frontier model asked directly at medium effort,
'$0.071', and is right as often, within one.

- Met: the hypothesis stands on this evidence, and `docs/MODELS.md` says so.
- Missed on cost: the harness does not make this frontier model cheaper on these questions;
  `docs/MODELS.md` says that.
- Missed on answers: reported with the questions it lost.

## Predictions (the executor's)

1. Maximum effort is right on 14 of 14, as medium was. It costs 3 to 8 times medium's '$0.071'
   and takes 3 to 10 times as long.
2. The harness with the frontier model is right on 22 of 22.
3. **It costs more an answer than the frontier model asked directly, not less:** '$0.12' to
   '$0.30'. The harness hands the answer step more text than a search plugin does, at the
   frontier model's input price, and pays its other tiers besides. So the owner's hypothesis is
   not borne out, on cost.
4. It takes about as long as the harness as shipped, a minute or so.

## Limits, stated beforehand

- One answer a question in each new row. A difference of one or two is noise.
- Every row is at the ceiling for correctness on these questions, so cost and time are what
  this can show.
- Run 2 changes one seat. A harness built around a frontier model (fewer steps, less text
  handed on) is a different design and is not tested here.
- The readers are models of the same maker as the model read.
