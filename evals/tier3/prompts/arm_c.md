# Technical question — two-model cooperation

Two models cooperate to answer one question under a fixed protocol: model 1 drafts, model 2 independently checks, model 1 revises once if model 2 objects. The protocol decides what is delivered; neither model chooses to defer or override.

## QUESTION

{{QUESTION_TEXT}}

## STAGE 1 — model 1 drafts

Derive the answer from the question's stated assumptions. Show every numerical step and state every assumption you use. Give a draft conclusion that answers every part the question asks, in one place, clearly labelled.

## STAGE 2 — model 2 checks (independently)

You are checking model 1's draft against the question — not against an answer of your own, and not for agreement. Check: every stated assumption is used as stated; every numerical step is correct; every part the question asks is answered; the draft's conclusion follows from its steps.

MODEL 1'S DRAFT:

{{MODEL_1_DRAFT}}

Then answer with the typed verdict and nothing else — a JSON object with exactly two fields:

{"concur": true, "objections": []}

when the draft holds on every check, or

{"concur": false, "objections": ["..."]}

when it does not, with one objection per list entry, each naming which step, which assumption, which figure, and what the question's text requires instead. concur is true exactly when objections is empty; a non-empty objections list means the draft does not hold.

## STAGE 3 — model 1 revises (only if model 2 objected)

Model 2's objections are below. Revise the draft to address each one, or show why the draft already holds. The revised answer is the delivered answer; it must answer every part the question asks, in one place, clearly labelled.

MODEL 2'S OBJECTIONS:

{{MODEL_2_OBJECTIONS}}

There is no voting and no third model. If model 2 concurred, the draft is delivered unchanged.
