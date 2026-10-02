# Pre-registration — ARCH-20261002-107: the direct-call baseline

Committed BEFORE any spend.

## Setup

- `evals/golden/baseline.py`: one call per question (Q1-Q6, IA) to the
  engineering tier, under arm B's prefix (z-ai/glm-5 via StreamLake).
- System message, exactly: "You are an expert engineer. Answer the
  question directly, correctly and concisely."
- The user message is the request from keys.json, byte for byte.
- max_tokens 4000, temperature at the client default.
- No plan, grounding, criteria, review or retry on content.
- Scored with `evals/golden/score.py`, unchanged.
- Caps: $0.02 per call, $0.10 in total. The 104 guard is armed; the
  catalogue is loaded first.

## Predictions and decision rule (the advisor's, verbatim)

P1, at least 5 of 6 direct answers hold every item of their key. P2, every direct call takes at most 60 s and costs at most $0.01. P3, the median sprawl ratio is below 5. P4 (side test), the direct IA answer holds at least 5 of its 6 core items, from the model's own knowledge with no lookup. DECISION RULE: 5 or 6 means the pipeline is not what makes these answers correct; the redesign's first ruling (D44) is a fast path (answer directly, then one cheap check, and escalate to the full pipeline only when the check fails), with D36's plan rules kept for the full pipeline's design work. 3 or 4 means a fast path for the questions that held, and the planner is examined on the rest. Fewer than 3 means the planner adds real correctness, so the redesign targets the planner's blocker posture instead.

## Spend gate

The owner's one-line authorisation, stating the caps, is quoted in the
response before the run's trace is committed.
