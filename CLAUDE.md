# AutoRnD-OS — global rules

<!-- Derived from the codebase. Every rule below traces to a cited file:line.
     Deeper material lives in .claude/context/ and is loaded on demand. -->

A multi-model agentic harness for engineering R&D teamwork: a prose objective goes
in, and a YAML-defined workflow graph triages, grounds, plans, implements,
validates in a loop, reviews, and either ships a written deliverable or escalates
with a diagnosis. Python 3.11+ / FastAPI / Pydantic v2 / SQLAlchemy 2 async +
aiosqlite / ChromaDB, talking to any OpenAI-compatible endpoint
(`autornd/routing/openrouter.py:151`).

> **This file is the working rules — how the code is written. It is not the
> protocol.** `AGENTS.md` is the protocol: who decides what, the permission
> boundary between instrument repair and behaviour change, the G-gates, and the
> command channel. **Read `AGENTS.md` before changing anything that alters what
> the harness concludes**, and see `.claude/context/records-and-roles.md` for the
> short version. There is exactly one copy of the protocol; point at it rather
> than quoting it.

---

## The permission boundary — read this before you change anything

Inlined here on 2026-09-22 because `CLAUDE.md` stopped being a symlink to
`AGENTS.md`, and the protocol stopped being loaded automatically with it. This
is a summary that points at the protocol, **not a second copy of it** — where
this and `AGENTS.md` differ, `AGENTS.md` wins.

**Three roles.** The **advisor** designs and *rules*. The **executor** *measures
and implements*. The **owner** holds money, serving pins and standing config, and
is the only one who edits `.env`. **A new executor proposes; it does not rule.**

**The test, and it is the whole boundary:** does the change alter **what the
harness would conclude**, or only **how reliably it reaches a conclusion?**

| yours — *instrument repair* | needs a ruling — *behaviour change* |
|---|---|
| crash-proofing a phase against well-formed-enough model output | verdict semantics — what a field means, what is required, what is coerced |
| retry wiring, retention, accounting | loop wiring and exit conditions |
| making a counter count what it claims to count | gate routing |
| fixing a measurement that reports something other than what it observed | prompt text that steers judgment, or anything changing which work ships |

Worked examples from the record: resolving `green` from `red_cause` was **ruled**;
counting how often that resolution fires was **repaired as found**. Folding a
criterion-keyed `evidence` object was **ruled**; attributing schema rejections to
the serving that produced them was **repaired**.

**Where a design is silent and the answer changes what the harness would
conclude, record the question and ask — do not decide it and carry on.**

**The G-gates are the owner's, and are not waivable by an executor:** API keys
move only through the terminal and `.env` (**G-1**); a serving pin is proposed
with evidence and ratified by the owner (**G-2**); the owner edits `.env` and
standing config, and the executor says so when a finding waits on one (**G-3**).
**A paid run needs the owner's authorisation, stated before the spend.**

Work arrives and returns through `.orchestration/` — see
`.claude/context/records-and-roles.md` for the channel, the response contract and
the statuses.

---

## Naming conventions

- **Files and modules:** `snake_case.py`, one concern per module, grouped into
  packages by job — `graph/`, `engine/`, `knowledge/`, `routing/`, `models/`,
  `specialists/`, `evals/`, `api/`.
- **Functions and variables:** `snake_case`. Module-private helpers take a single
  leading underscore and are genuinely not imported elsewhere — `_natural_key`,
  `_fold_evidence` (`autornd/models/verdicts.py:346,358`), `_canonical_unit`,
  `_classify` (`autornd/graph/checks.py:106,346`).
- **Classes:** `PascalCase`. Pydantic verdicts end in `Verdict`
  (`TriageVerdict`, `ImplementVerdict`, `ValidateVerdict` —
  `autornd/models/verdicts.py:85,229,404`). Custom exceptions end in `Error`
  and subclass the closest builtin, not bare `Exception`: `ConditionError(ValueError)`
  (`autornd/graph/conditions.py:27`), `SpecError(ValueError)`
  (`autornd/graph/spec.py:48`), `UnknownPromptError(KeyError)`
  (`autornd/graph/adapter.py:43`), `BudgetExceeded(RuntimeError)`
  (`autornd/routing/openrouter.py:133`).
- **Tests:** `tests/test_<subject>.py`, grouped into `class Test<Behaviour>`
  (211 such classes across 54 files, e.g. `tests/test_green_resolution.py:37`).
- **Vocabulary terms** (domains, specialist roles) are normalised to
  `lower_snake_case` through `normalise_key()` before any comparison
  (`autornd/models/verdicts.py:24`). Never compare raw model output to a literal.
- **Workflow and profile identifiers** are `kebab-or-snake` YAML filenames whose
  stem is the name used on the CLI: `workflows/engineering-rnd.yaml`,
  `profiles/studio.yaml` selected by `AUTORND_PROFILE=studio`.

## Core code patterns

- **`from __future__ import annotations` at the top of every module** (27 of 34
  non-empty files; the exceptions are empty `__init__.py`s). Built-in generics
  only — `dict[str, int]`, `list[str]`, `X | None`. `typing.Dict/List/Optional`
  appears 5 times against 232 built-in uses; do not add more.
- **Async by default on any I/O path.** Provider calls, DB sessions, phase
  handlers and the graph executor are all `async def`; SQLAlchemy is used in its
  async style with `AsyncSession` and `Mapped[]` models.
- **Typed verdicts, never prose.** Every model-calling phase returns a Pydantic
  model and control flow tests its fields. See `.claude/context/verdicts.md`.
- **Logging is stdlib `logging` with a module-level
  `logger = logging.getLogger(__name__)`** (`autornd/engine/phases.py:37`,
  `autornd/profiles.py:14`, `autornd/specialists/registry.py:10`, and 6 more).
  **Never `print()` from library code** — the only two live in `preflight.py`,
  which is a CLI report (`autornd/preflight.py:152`).
- **API errors are `HTTPException(status, "message")`** raised inline with a
  plain human sentence, no custom error envelope
  (`autornd/api/routes.py:47,409`). Successful responses wrap the payload in a
  `{"data": ...}` envelope (10 sites in `routes.py`).
- **Registries over conditionals.** Deterministic checks register via a
  `@check("name")` decorator into `checks.registry`
  (`autornd/graph/checks.py:43,46`); phases dispatch by name with
  `getattr(self, f"_phase_{node.prompt}")` and raise `UnknownPromptError` when
  missing (`autornd/graph/adapter.py:168`). Adding a capability means adding a
  registered function, not a new branch.
- **Comments explain *why*, and frequently cite the run that set the value.**
  `config.py`, `checks.py` and `ci.yml` are the models for this: a constant
  carries the measurement that chose it. Match this density when you touch them.

## Build & validation commands

```bash
.venv/bin/python3 -m pytest tests/ -q          # full suite, ~45 s, no network, no spend
.venv/bin/python3 -m pytest tests/test_graph.py -q   # one file
pip install -e ".[dev]"                        # the only dependency manifest is pyproject.toml
uvicorn autornd.main:app --port 8100           # run the API
```

- Use the interpreter path explicitly — **`pytest` is not on PATH**
  (`CONTRIBUTING.md`).
- **There is no linter, formatter or type-checker configured.** No ruff, black,
  mypy or flake8 in `pyproject.toml` or `ci.yml`. Do not invent a gate that
  doesn't exist; match surrounding style by hand.
- CI (`.github/workflows/ci.yml`) runs four things and all must pass: pytest on
  3.11/3.12/3.13, an editable install from project metadata with an import smoke,
  a built wheel carrying its package data, and a Docker build that boots the
  container and asserts `/api/health` reports `degraded` honestly.

## On-demand context

| Load | When |
|---|---|
| `.claude/context/architecture.md` | Touching `graph/`, `engine/`, node scheduling, loops, or gates |
| `.claude/context/verdicts.md` | Changing a verdict schema, a required field, or how model output is coerced |
| `.claude/context/cost-and-budgets.md` | Anything that makes, prices, retries or bounds a provider call |
| `.claude/context/workflows-and-profiles.md` | Authoring or editing `workflows/*.yaml` or `profiles/*.yaml` |
| `.claude/context/testing.md` | Writing tests, especially guards and instrument tests |
| `.claude/context/evals.md` | Running or changing anything under `evals/` or `autornd/evals/` |
| `.claude/context/records-and-roles.md` | Deciding *whether* a change is yours to make, or recording one |

## Hard rules

1. **Run `.venv/bin/python3 -m pytest tests/ -q` before starting and again before
   finishing. Green both times, and CI green before a PR.** The suite is free and
   takes under a minute (`CONTRIBUTING.md`).
2. **Never parse English for control flow.** Gates test booleans; a `skipped`
   flag is a typed field, not a substring match on an error message. This rule
   was bought back: `ScenarioRun.skipped` was decided by substring-matching
   `("not applicable", "sweep budget exhausted")`, and fixing the message
   silently turned skipped units into units that had run.
3. **No `eval`, and no new condition syntax.** `graph/conditions.py` implements
   one grammar — `<dotted.path> <op> <literal>`, truthiness, or `not <path>` —
   and a missing path **raises** rather than evaluating false
   (`autornd/graph/conditions.py:56,82`). A test asserts
   `__import__('os').system(...)` is rejected.
4. **No hardcoded model names or prices anywhere in code, config defaults,
   profiles, workflows or user-facing docs.** Rates come from the provider
   catalogue at startup (`autornd/routing/openrouter.py:590,644`); tiers are
   named by job (triage, engineering, architecture, escalation, research, search,
   ranker, premium) and ship empty (`autornd/config.py:26-40`).
   `tests/test_docs.py` enforces this and will fail your PR.
5. **Free checks before paid calls.** If a question is decidable deterministically,
   decide it in `graph/checks.py` and don't spend on it.
6. **Read the comment beside a constant before changing it.** Most name the live
   run that set them and often a previous attempt that failed
   (`autornd/config.py:57,66,72`). Changing the number without addressing the
   comment discards the measurement.
7. **When a change invalidates a test, ask which of the two is wrong first.**
   A test asserting current behaviour may be the bug, written down. Two tests in
   this repo had enshrined a wrong error message and were corrected, not appeased.
8. **Never commit secrets, and never put an API key in a transcript.** Keys move
   through the terminal and `.env` only; `.env.example` carries placeholders.
   A key that appears in a transcript is rotated, not reused.
9. **Private corpora never enter this repo.** `profiles/milkhouse.yaml` stays
   untracked; see `.gitignore`.
10. **Commit messages are prose naming what was measured or changed**, not bullet
    lists. `git log` is the house style reference.
11. **Schema changes to the DB are destructive — there is no Alembic.** Say so
    explicitly when you propose one (`autornd/database.py`, tables created from
    metadata at startup).

## Miscellaneous / Gotchas

<!-- Running list — add entries as you discover things the agent repeatedly misunderstands -->
- **`pytest` is not on PATH.** Always `.venv/bin/python3 -m pytest`.
- **`config.py` validates the six required model tiers at import time and exits
  if any is unset.** Anything that imports `autornd.*` outside the test suite
  needs `MODEL_TRIAGE`/`ENGINEERING`/`ARCHITECTURE`/`ESCALATION`/`RESEARCH`/`SEARCH`
  in the environment. `tests/conftest.py:9` injects placeholders before the first
  import — which is why the CI matrix job deliberately does *not* set them.
- **`pyproject.toml` needs `[tool.setuptools.packages.find] include = ["autornd*"]`.**
  Without it, flat-layout discovery sees `evals/ profiles/ workflows/` beside
  `autornd/` and fails the build outright. Don't "tidy" that block away.
- **`dashboard.html` is read off disk at request time** and must stay declared in
  `[tool.setuptools.package-data]`, or every built install serves a
  `FileNotFoundError` from `/`. `workflows/` and `profiles/` are deliberately
  *not* package data — they resolve relative to the package directory, which is
  why the Dockerfile installs editable.
- **A loop owns the nodes in its `body`**, which takes them off the top-level
  schedule (`autornd/graph/spec.py:22,154`). Adding an existing node to a loop
  body deletes it from the main flow silently — no error, just a shorter
  pipeline. A phase needed in both places needs **two node ids**.
- **The API entry point is `engine/workflow.py`, not just `graph/executor.py`.**
  It owns the DB row, the status column and episodic memory. It looks like dead
  legacy and is not; `tests/test_live_wiring.py` pins it.
- **Cost figures predating commit `b4cd89f` are understated 2.6×–295×** —
  research, context and rerank calls bypassed the meter entirely. Never cite one;
  re-measure.
- **`api_host` defaults to `127.0.0.1` on purpose** — there is no rate limiting
  and calls cost real money. The Dockerfile passes `--host 0.0.0.0` on its own
  command line (`autornd/config.py:11-20`).
- **`evals/results/` is git-ignored; `docs/traces/` is tracked.** A `git stash -u`
  during a live run once took the directory entry of an untracked results file
  under `docs/traces/` while the writer held the inode, and every completed unit
  record went to a deleted file. Don't run git operations against the tree while
  a paid run is writing into it.
