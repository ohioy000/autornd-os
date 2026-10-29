# AutoRnD-OS — working rules

<!-- Derived from the codebase. Every rule below cites a file and a symbol, never a line number, so a
     grep finds it and it cannot drift. Deeper material lives in .claude/context/, loaded on demand. -->

A multi-model agentic harness for engineering R&D teamwork: a prose objective goes in, and a
YAML-defined workflow graph triages, grounds, plans, implements, validates in a loop, reviews, and
either ships a written deliverable or escalates with a diagnosis. Python 3.11+ / FastAPI /
Pydantic v2 / SQLAlchemy 2 async + aiosqlite / ChromaDB, talking to any OpenAI-compatible endpoint
(`autornd/routing/openrouter.py`).

**We work through one shared GitHub repository, `https://github.com/ohioy000/autornd-os`; its `main` is the truth.** Fetch
from it, push branches to it, and deliver by pull request. The advisor's folder is
`/home/jb/autornd-os`; the coder's is `/home/jb/autornd-os_clone` (see `AGENTS.md`).

> **This file is how code is written here. `AGENTS.md` is the protocol** — who decides what, the
> permission boundary, the G-gates, the command channel, how deliveries are reviewed. **Read
> `AGENTS.md` before changing anything that alters what the harness concludes.** There is exactly one
> copy of the protocol; point at it rather than quoting it. `.claude/context/records-and-roles.md`
> is the short version.

## The permission boundary — read before you change anything

A summary that points at the protocol, not a second copy of it; where the two differ, `AGENTS.md`
wins. **Three roles:** the **advisor** designs, rules and reviews; the **executor** measures and
implements; the **owner** holds money, serving pins and standing config and is the only one who edits
`.env`. **A new executor proposes; it does not rule.**

**The test, and it is the whole boundary:** does the change alter **what the harness would
conclude**, or only **how reliably it reaches a conclusion?**

| yours — *instrument repair* | needs a ruling — *behaviour change* |
|---|---|
| crash-proofing a phase against well-formed-enough model output | verdict semantics — what a field means, what is required, what is coerced |
| retry wiring, retention, accounting | loop wiring and exit conditions |
| making a counter count what it claims to count | gate routing; scorer and answer-key semantics |
| fixing a measurement that reports something other than what it observed | prompt text that steers judgment, or anything changing which work ships |

Worked examples: resolving `green` from `red_cause` was **ruled**; counting how often that resolution
fires was **repaired as found**. **Where a design is silent and the answer changes what the harness
would conclude, record the question and ask — do not decide it and carry on.** When a measurement
contradicts the command, report it as it read and hold the work.

**The G-gates are the owner's and not waivable:** keys move only through the terminal and `.env`
(**G-1**); a serving pin is proposed with evidence and ratified by the owner (**G-2**); the owner
edits `.env` and standing config, and a finding that waits on one says so (**G-3**). **A paid run
needs the owner's authorisation, stated before the spend.** Work arrives and returns through
`.orchestration/` — see `.claude/context/records-and-roles.md`.

## Arch to Coder — the owner's standard

The architect (advisor) thinks; the coder (executor) works. The task-file format is in `AGENTS.md`,
"How a command is written". A new architect starts with `.orchestration/prompts/STARTUP-ARCHITECT.md`.

1. **The architect does the hard work.** The coder follows exact tasks and never has to work
   anything out.
2. **Every command is a task file:** ordered tasks, each with exact find → replace text, a CHECK,
   its real EXPECT and a commit. Complete and self-contained, never "...".
3. **Write simply,** to the owner and to the coder.
4. **Write the next command without being asked.**
5. **Keep the style.** Do not change the prompt style, the task-file format or the rules as a
   whole. Fix one problem in place. A change to the style or the rules is the owner's.
6. **Do not redo a full delivery.** If it matches the task file byte for byte and CI is green,
   merge it. No suite re-run, no new probes.
7. **Merge through a PR on green; never push to main.**

## Naming conventions

- **Modules:** `snake_case.py`, one concern per module, grouped by job — `graph/`, `engine/`,
  `knowledge/`, `routing/`, `models/`, `specialists/`, `evals/`, `api/`. A module-private helper takes
  one leading underscore and is genuinely not imported elsewhere (`_natural_key`, `_fold_evidence` in
  `models/verdicts.py`; `_canonical_unit`, `_classify` in `graph/checks.py`).
- **Pydantic verdicts end in `Verdict`** (`TriageVerdict`, `ImplementVerdict`, `ValidateVerdict`).
  **Custom exceptions subclass the closest builtin, never bare `Exception`:**
  `ConditionError(ValueError)` (`graph/conditions.py`), `SpecError(ValueError)` (`graph/spec.py`),
  `UnknownPromptError(KeyError)` (`graph/adapter.py`), `BudgetExceeded(RuntimeError)` and its
  `SpendGuardRefused` (`routing/openrouter.py`).
- **Tests:** `tests/test_<subject>.py`, grouped into `class Test<Behaviour>`
  (`tests/test_green_resolution.py`, `TestTheTruthTable`). Test names state the behaviour as a sentence.
- **Vocabulary terms** (domains, specialist roles) go through `normalise_key()` (`models/verdicts.py`)
  before any comparison. **Never compare raw model output to a literal.**
- **Workflow and profile identifiers** are YAML filename stems used on the CLI:
  `workflows/full-team.yaml`; `profiles/studio.yaml` selected by `AUTORND_PROFILE=studio`.

## Core code patterns

- **`from __future__ import annotations` at the top of every non-empty module.** Built-in generics
  only — `dict[str, int]`, `list[str]`, `X | None`; do not add `typing.Dict/List/Optional`.
- **Async on every I/O path:** provider calls, DB sessions, phase handlers and the graph executor are
  `async def`; SQLAlchemy runs async with `AsyncSession` and `Mapped[]` models.
- **Typed verdicts, never prose.** Every model-calling phase returns a Pydantic model and control flow
  tests its fields — see `.claude/context/verdicts.md`.
- **Logging:** stdlib, `logger = logging.getLogger(__name__)` per module. **Never `print()` from
  library code** — only the CLI entry points print (`autornd/cli.py`, `autornd/evals/cli.py`,
  `autornd/preflight.py`).
- **API errors are `HTTPException(status, "message")`** with a plain human sentence and no custom
  envelope; successful responses wrap the payload in `{"data": ...}` (`autornd/api/routes.py`).
- **Registries over conditionals.** Deterministic checks register with `@check("name")` into
  `checks.registry` (`graph/checks.py`); phases dispatch by name via
  `getattr(self, f"_phase_{node.prompt}")` and raise `UnknownPromptError` when missing
  (`graph/adapter.py`). A new capability is a registered function, not a new branch.
- **Comments explain *why* and cite the run that set the value.** `config.py`, `checks.py` and
  `ci.yml` are the models: a constant carries the measurement that chose it. Match that density.
- **Accounting is by identity.** A call that reserved a worst case releases exactly its own
  reservation; a call that failed after dispatch keeps its own worst case as unreconciled liability
  (D45, D47 in `routing/openrouter.py`). Any new post site goes through the same reservation path.

## Build & validation

```bash
.venv/bin/python3 -m pytest tests/ -q                # full suite, ~90 s, no network, no spend
.venv/bin/python3 -m pytest tests/test_graph.py -q   # one file
pip install -e ".[dev]"                              # pyproject.toml is the only dependency manifest
uvicorn autornd.main:app --port 8100                 # run the API
```

- **`pytest` is not on PATH** — always the interpreter path.
- **The suite blocks the network.** A conftest plugin logs every non-loopback connection and the run
  ends with `network guard: 0 non-loopback attempt(s)`; any other number is a defect to fix.
- **No linter, formatter or type-checker is configured** (no ruff, black, mypy, flake8 in
  `pyproject.toml` or `ci.yml`). Do not invent a gate; match surrounding style by hand.
- **CI** (`.github/workflows/ci.yml`) runs four things and all must pass: pytest on 3.11/3.12/3.13, an
  editable install with an import smoke, a built wheel carrying its package data, and a Docker build
  that boots and asserts `/api/health` reports `degraded` honestly.
- **Counts are re-derived from `pytest tests/ --collect-only -q`** whenever tests are added, removed or
  rebased — HANDOVER.md, README.md and AGENTS.md state them and guards check every figure. Two branches
  each right at their own tip can merge into a wrong total; re-run the suite on main after sequential
  merges.

## Evals and measurement code

- **Answer keys are frozen.** `evals/tier2/questions.json` and `keys.json` are signed off by the owner
  and stay byte-identical through any scorer change; a key change is a new key version the owner
  ratifies (D44), reported side by side with the old one.
- **A scorer change is a new `evals/tier2/versions.json` entry** that restates its rules. It must hold
  `scorer.self_test()`, `verify_keys.py`, `notation_sweep.py` and `regression_12.py` — real recorded
  answers two readers judged correct. Hand-written fixtures are not enough: the frozen scorer held all
  its fixtures and passed 5 of 12 recorded answers.
- **The scorer is a screen; two hand readings are primary** (D50). A scorer verdict is never reported
  as the result.
- **Traces are evidence:** a run's results file is copied byte-identical into `docs/traces/` and cited
  by sha256. Tier-3 serving pins live in `.env.tier3` (git-ignored, the owner's under G-2/G-3).

## Hard rules

1. **Run the suite before starting and again before finishing** — green both times, CI green before
   a PR.
2. **Never parse English for control flow.** Gates test booleans; a `skipped` flag is a typed field.
   Bought back: `ScenarioRun.skipped` was decided by substring-matching an error message, and fixing
   the message silently turned skipped units into units that had run.
3. **No `eval`, and no new condition syntax.** `graph/conditions.py` implements one grammar —
   `<dotted.path> <op> <literal>`, truthiness, or `not <path>` — and a missing path **raises**. A test
   asserts `__import__('os').system(...)` is rejected.
4. **No hardcoded model names or prices** in code, config defaults, profiles, workflows or user-facing
   docs. Rates come from the provider catalogue at startup; tiers are named by job (triage,
   engineering, architecture, escalation, research, search, ranker, premium) and ship empty
   (`autornd/config.py`). `tests/test_docs.py` fails the PR.
5. **Free checks before paid calls.** Decide anything deterministic in `graph/checks.py`.
6. **Read the comment beside a constant before changing it.** Changing the number without
   addressing the comment discards the measurement (`autornd/config.py`).
7. **When a change invalidates a test, ask which of the two is wrong first.** Two tests here enshrined
   a wrong error message and were corrected, not appeased.
8. **Every instrument test is proven by breaking the line it guards** (a break-proof), and simulates
   its condition end to end — a guard nobody has seen fail is a guard nobody knows works.
9. **Never commit secrets or put a key in a transcript.** `.env.example` carries placeholders; a key
   that appears in a transcript is rotated, not reused.
10. **Private corpora never enter this repo** — `profiles/milkhouse.yaml` stays untracked.
11. **Commit messages are prose naming what was measured or changed**, not bullet lists; `git log` is
    the reference. Single-quote dollar figures.
12. **Schema changes to the DB are destructive — there is no Alembic.** Say so when you propose one
    (`autornd/database.py` creates tables from metadata at startup).

## Gotchas

- **`config.py` validates the six required model tiers at import time and exits** if any is unset.
  Anything importing `autornd.*` outside the suite needs `MODEL_TRIAGE`/`ENGINEERING`/`ARCHITECTURE`/
  `ESCALATION`/`RESEARCH`/`SEARCH` set; `tests/conftest.py` injects placeholders before the first
  import, which is why the CI matrix job deliberately sets none. pydantic also reads `.env` from the
  CWD — force placeholders through the environment in probes.
- **A probe in a worktree must put that worktree first on `sys.path`** — `python -I` from elsewhere
  imports main's `autornd` and reports on the wrong code.
- **`pyproject.toml` needs `[tool.setuptools.packages.find] include = ["autornd*"]`** — without it,
  flat-layout discovery sees `evals/ profiles/ workflows/` and fails the build. Don't tidy it away.
- **`dashboard.html` is read off disk per request** and must stay in `[tool.setuptools.package-data]`.
  `workflows/` and `profiles/` are deliberately not package data — they resolve relative to the
  package directory, which is why the Dockerfile installs editable.
- **A loop owns the nodes in its `body`**, taking them off the top-level schedule (`graph/spec.py`).
  Adding an existing node to a loop body silently shortens the pipeline; a phase needed in both places
  needs **two node ids**.
- **The API entry point is `engine/workflow.py`, not just `graph/executor.py`.** It owns the DB row,
  the status column and episodic memory; it looks like dead legacy and is not
  (`tests/test_live_wiring.py` pins it).
- **Cost figures predating commit `b4cd89f` are understated 2.6×–295×.** Never cite one; re-measure.
- **`api_host` defaults to `127.0.0.1` on purpose** — calls cost real money; the Dockerfile passes
  `--host 0.0.0.0` on its own command line.
- **`evals/results/` is git-ignored; `docs/traces/` is tracked. No git operation against a tree while
  a paid run writes into it** — a `git stash -u` once took the directory entry of a results file the
  writer still held, and every unit record went to a deleted file.

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
