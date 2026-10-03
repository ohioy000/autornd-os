# Scenario request — current pipeline (arm E)

The question enters the harness exactly as the pipeline's own scenarios do (evals/scenarios/golden/*.yaml): the question text is the request, under the experiment's common deadline. The pipeline's own tools, call ceiling and standing risk gates are the treatment; no experiment treatment is applied.

```yaml
id: tier3_q{{QUESTION_ID}}_r{{REPETITION}}
description: Tier-3 experiment arm E — the frozen question answered by the current pipeline
request: |
  {{QUESTION_TEXT}}
timeout: 600
```

The pipeline runs under the standing pins (.env, the owner's): triage, engineering, escalation as routed. The delivered answer is the terminal phase's conclusion, extracted from the run record and scored by the frozen tier-2 scorer like every other arm's answer.
