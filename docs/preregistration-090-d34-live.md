# Pre-registration 090 — D33+D34 live test on the working roster

Committed before the run. First paid test of forced reasoning (D34) + revise-own-
artifact (D33) together, on the first fully-runnable roster.

Roster (from .env): triage deepseek-v4-flash @ DigitalOcean, engineering
qwen3-235b @ Nebius, architecture glm-5.3 @ DigitalOcean, escalation
gpt-6.1-sol-pro @ OpenAI, research gemini-2.5-flash @ Google, search sonar @
Perplexity. Fallbacks off, all US/EU hosts watched to run without 429 this
session (Nebius EU for engineering). Ceilings: plan/validate 16k, escalation 90k.

Items: conv_pool_sizing (kappa item) + robotics-manipulator, timeout 1500.
Cap: --max-spend 0.55 --max-spend-sweep 1.20 (owner-ratified envelope).

Prediction (held loosely; recent predictions have been refuted/soft):
- D34's reasoning field gives qwen a CoT runway to catch numeric inconsistency
  before emitting. Expect the consistency dissent to appear LATER or resolve,
  and fewer green->red regressions than the D33-only run (088, which escalated
  both, robotics regressing).
- Best case: at least one item CONVERGES (completed). Base case: still escalates
  but with the contradiction caught earlier / fewer wasted iterations.
- If both still escalate identically, D34 (synthetic reasoning) is insufficient
  for the hard class and the lever moves to Option 1 (heterogeneous judge) /
  Option 2 (real reasoning at implement).
Baseline to compare: 088 (D33-only, both escalated, ~$0.33, robotics regressed).
