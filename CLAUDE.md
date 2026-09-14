# AutoRnD-OS — Multi-Model Agentic Engineering Harness

You describe an objective in prose. The harness classifies the work, assembles
grounding, plans, implements, validates in a loop, reviews with a risk-scaled
team, and either produces a written deliverable or escalates with a diagnosis.

Two things define it:

- **The workflow is data.** The pipeline is a YAML graph in `workflows/`, not a
  sequence compiled into the engine. Copy a file and change it.
- **No model is chosen for you.** Tiers are named by job, never by vendor. There
  are zero model names and zero hardcoded prices in this codebase; rates are
  learned from the provider catalogue at startup.

Domain grounding is configurable per project via `profiles/*.yaml`. The harness
ships with an empty knowledge store on purpose.

## Stack

Python 3.11+ · FastAPI · SQLAlchemy 2.0 async + aiosqlite · Pydantic v2 ·
httpx · ChromaDB · PyYAML · PyJWT · pytest (`asyncio_mode = "auto"`)

Models are reached over the OpenAI chat-completions protocol via OpenRouter, so
any compatible endpoint works.

## Layout

```
autornd/
  graph/        spec.py (Node/WorkflowSpec) · executor.py (gates, loops, state)
                adapter.py (node → phase dispatch) · conditions.py · checks.py
  engine/       phases.py (every prompt) · review_composition.py
                workflow.py (legacy sequence, kept as the graph's equivalence ref)
  knowledge/    context.py (grounding) · research.py (outward lookup) · store.py
                episodic.py
  routing/      openrouter.py (client, tiers, accounting, budgets, provider pins)
  models/       verdicts.py (all phase schemas) · workflow.py · user.py
  specialists/  registry.py (built-in + profile roles) · base.py
  evals/        scenario.py · assertions.py · runner.py · cli.py
  api/          routes.py · auth.py · templates/dashboard.html
  config.py     Settings + RUNTIME_MUTABLE · profiles.py · cli.py · main.py

workflows/      engineering-rnd (full) · lean · triage-only · triage-classify
evals/          scenarios/ (core) · scenarios/wide/ (36 sectors, opt-in)
                grounding/ (8 sectors graded against published figures)
tests/          17 files, 501 tests, ~9s
```

## Pipeline

`triage → context → plan → feasibility → plan_ready → build_loop → review →
review_clean → independent_check`

`build_loop` repeats `implement → domain_review → coverage → consistency →
validate` until `validate.green`, then hands off to `escalation → recoverable →
recovery_loop`. `coverage` and `consistency` are free deterministic checks that
run *before* the paid validator.

Node kinds: **`ai`** (model call), **`check`** (free function from
`checks.registry`), **`gate`** (boolean over prior outputs; may end the run).
`specialist:` takes a role or a roster — `assigned`, `builders`, `peers`,
`lead`, `reviewers`.

## Tiers

Six required — **triage, engineering, architecture, escalation, research,
search**. Two optional — **ranker** (native rerank; falls back to listwise then
embedding distance) and **premium** (the independent pass; falls back to the
architecture tier, and refuses when that would be the engineering model).

Every tier is set by environment variable and validated against the provider
catalogue at startup. Choose **non-reasoning** models for the tiers that fill a
schema: a model that reasons at length can spend its whole output budget before
emitting anything, which has been observed to fail a run outright. Escalation is
the one tier where reasoning earns its keep.

## Invariants — do not break these

1. **Every non-obvious constant carries the measurement that set it.** Read the
   comment before changing a value; it usually names the live run behind it and
   often a previous attempt that failed.
2. **Free checks before paid calls.** Always.
3. **Typed verdicts; gates test booleans.** Never parse English for control flow.
4. **Enums are default vocabularies, not limits.** `Domain` and `SpecialistRole`
   are starting sets. Profiles declare their own; an undeclared role resolves to
   a generalist rather than raising. A closed enum for anything a user's domain
   might extend is an anti-pattern here — measured, it turned civil engineering
   into "hardware" for 8 of 9 unmatched subjects.
5. **No `eval` in workflow files.** `conditions.py` is one deliberate grammar:
   `<dotted.path> <op> <literal>`. Missing paths raise rather than silently
   evaluating false.
6. **All spend is accounted on the client.** `OpenRouterClient` holds
   `spend`/`calls` per tier and enforces budgets inside `_account()`, so no call
   path can avoid being priced. Test doubles must bill too (`client._account`) —
   a free double hid this exact bug.
7. **Never hardcode a model name or a price.**
8. **A risk floor is never waivable.** A ceiling may be, via a scenario's
   `risk_ceiling_waived` field with a stated reason. `risk_at_most: critical` is
   vacuous and must not be written.
9. **Write eval expectations before running**, then report mismatches honestly —
   including when the expectation was wrong.
10. **Isolate the knowledge store in experiments.** Research ingests what it
    finds, so one scenario otherwise grounds the next.
11. **Pin the provider when measuring.** The same model id served by different
    providers scored 28/36 against 33/36 on one suite at a 12× price spread, and
    the cheap serving under-classified safety-critical risk every repetition. An
    unpinned score is partly a record of who answered.
12. **Private corpora never enter this repo.** See `.gitignore`.

## Commands

```bash
uvicorn autornd.main:app --reload --port 8100     # API + dashboard
pytest tests/ -q                                  # 501 tests, ~9s, free

python -m autornd.cli init-knowledge --profile example
python -m autornd.cli {ingest|stats|query}

# calibration: 108 calls, minutes, under two cents
python -m autornd.evals.cli --scenarios evals/scenarios/wide \
  --workflow triage-classify --repeat 3 --max-spend 0.10

# factual accuracy against published figures
python -m autornd.evals.cli --scenarios evals/grounding \
  --workflow triage-only --repeat 1 --max-spend 0.30
```

Always pass `--max-spend` on anything touching the search tier; it is the most
expensive tier by a wide margin.

## Style

No linter is configured. Match the surrounding code: 4-space indent,
`from __future__ import annotations`, type hints throughout, ~88-column soft
wrap, module docstrings that explain rationale rather than restate the code.
Commit messages are prose explaining the measurement, not bullet lists.

Deeper context, measured numbers and the open punch list live in
[`HANDOVER.md`](HANDOVER.md) and [`docs/handover-review.md`](docs/handover-review.md).
