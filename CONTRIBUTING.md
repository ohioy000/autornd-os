# Contributing to AutoRnD

Thanks for your interest in contributing. This guide covers the basics.

## Getting Started

```bash
git clone https://github.com/ohioy000/autornd-os.git
cd autornd-os
pip install -e ".[dev]"
cp .env.example .env
# Add your OpenRouter API key to .env
```

## Running Tests

```bash
.venv/bin/python3 -m pytest tests/ -q
```

Use the interpreter path explicitly — `pytest` is not necessarily on your PATH.
The suite is around nine seconds and costs nothing, which is deliberate rather
than incidental: the shape of a workflow, its gates and loops, the deterministic
checks, the condition language and the eval scoring are all decidable without a
provider. Run it before you start and again before you push.

All tests must pass before submitting a PR.

## Evals

Unit tests prove the harness does what it says. **Evals measure whether the
models do**, and they are the cheapest quality signal in the project.

```bash
python -m autornd.evals.cli --scenarios evals/scenarios --workflow triage-classify \
  --repeat 3 --max-spend 0.10
```

Scenarios are YAML in `evals/scenarios/`; `evals/grounding/` grades factual
recall against published figures. Four conventions matter more than the
mechanics:

- **Write the expectation before the run.** Then report the mismatch honestly,
  including "my expectation was wrong". An expectation written afterwards
  measures nothing.
- **Always pass `--max-spend`.** It bounds one scenario-run — a single
  repetition, not the whole invocation. The aggregate ceiling is
  `--max-spend-sweep`, which is **on by default at $1.00**; pass `none` to
  disable it. Setting both makes the sweep cap exact, because a unit that
  might not fit is never started. Anything touching the search tier is by a
  wide margin the most expensive thing here.
- **Repeat.** Models are stochastic; the same triage request has passed on one
  run and failed on the next. A single result is an anecdote.
- **Test doubles must bill like the real client** — call `client._account(...)`.
  A double that answered for free once hid a real accounting bug, and it hid it
  from the very tests meant to show one workflow was cheaper than another.

Every unit is appended to `evals/results/*.jsonl` as it finishes, carrying the
typed verdicts and which provider served each tier alongside the numbers. Two
things follow: an interrupted sweep keeps what it bought, and a failing sector
can be diagnosed — and priced against its serving — without paying to reproduce
it. Both were bought the hard way; see `docs/handover-review.md` §13.

Assertions are free and make no model call. See the README's Evals section for
the full assertion vocabulary.

## What to Work On

Good first contributions:

- **Deterministic checks** — the most welcome contribution there is. Anything
  with a right answer belongs in a free check rather than a paid prompt. Add one
  to `autornd/graph/checks.py` with the `@check("name")` decorator, then name it
  from a workflow node.
- **New workflow shapes** — copy a file in `workflows/`, change it, measure it
  against an existing one with the eval suite. No code required.
- **New specialist types** — add a template in `autornd/specialists/registry.py`,
  or just declare the role in your profile (see below — no code required either).
- **Model providers** — the routing client in `autornd/routing/openrouter.py`
  targets any OpenAI-compatible endpoint; adapters for other providers are
  welcome.
- **New phases** — see "Adding a phase" below.
- **Profile examples** — add example profiles in `profiles/` for different
  domains.

Check the issue tracker for open issues tagged `good first issue`.

## Adding a Phase

The pipeline is **data, not code**. A workflow is a YAML graph in `workflows/`,
so adding a phase is three small steps:

1. **Prompt** — add the prompt text to `autornd/engine/phases.py`.
2. **Dispatch** — add a `_phase_<name>` method to `PhaseRunner` in
   `autornd/graph/adapter.py`. Nodes are dispatched by name onto that method.
3. **Wire it** — add a node to a workflow file in `workflows/`. Node kinds are
   `ai` (one or more model calls), `check` (a free deterministic function) and
   `gate` (a boolean over prior outputs).

> **`autornd/engine/workflow.py` is the API entry point, not a place to add
> phases.** It loads the graph, runs it and persists the results. The hardcoded
> sequencer it once carried as the graph's equivalence reference has been
> deleted: the graph now routes on gate failure, which a linear sequencer cannot
> represent, so the reference modelled less than the product did.

Every phase returns a **typed Pydantic verdict** from
`autornd/models/verdicts.py`, never prose. Gates test booleans
(`plan.ready`, `validate.green`, `review.ship`); nothing parses English to
decide control flow.

## Adding Roles and Domains

**`SpecialistRole` and `Domain` are open vocabularies — defaults, not limits.
Do not edit the enums.** A project declares what it actually uses in its
profile:

```yaml
# profiles/yours.yaml
domains:
  records_management:
    lead: paralegal
    checks:
      - "Does the retention period cite the statute that sets it?"
roles:
  paralegal:
    name: "Paralegal"
    domain: records_management
    tier: engineering
    expertise: "Statutory retention schedules, disclosure, chain of custody."
```

An undeclared role resolves to a **synthesized generalist** rather than failing,
and an unmapped domain falls back to the systems architect.
[`profiles/studio.yaml`](profiles/studio.yaml) is a full worked example on a
non-engineering team, commented as a teaching file.

This is not a style preference; it is a measured correction. With `Domain`
enforced as a closed enum, nine of twelve subjects had no fitting value and
eight of those came back `hardware` — civil engineering as "hardware", buffer
chemistry as "documentation". A closed list does not produce an honest refusal,
it produces a least-wrong label. The same defect put seven engineers on the
review of a records retention schedule.

## Pull Requests

- Keep PRs focused — one feature or fix per PR
- Add tests for new functionality
- Update the README if you're adding user-facing features
- All phase outputs must be Pydantic models with typed fields — no prose parsing
- No model ids in code, configuration defaults, profiles or workflow files. Tiers
  are named by job; the operator chooses what fills them.

## Code Style

- Python 3.11+
- `from __future__ import annotations`, type hints throughout, 4-space indent
- Gate logic checks typed fields (`green == true`, `ship == true`), never parses
  English
- **Comments carry the measurement.** Nearly every non-obvious constant in this
  codebase has a comment beside it naming the live run that set it, and often a
  previous value that failed. Read that comment before you change the constant —
  it usually explains an attempt someone already made. When you set a value from
  a measurement, write the measurement down next to it. Do not strip these in a
  refactor; they are the most valuable thing in the tree.

## Building on AutoRnD

- **Fork the repo** — the simplest path. Clone, modify, ship your own version.
- **Import as a library** — `pip install -e .` and import `autornd` into your own
  project. The profile system, specialists, and workflow engine are all
  importable. Note: the public API surface is not yet frozen — pin to a commit or
  tag.
- **Extend without forking** — declare your roles and domains in a profile, copy
  a workflow file and change it, and add checks. Specialists resolve from the
  shipped defaults plus whatever your profile declares, with a generalist
  fallback for anything named by neither, so new roles need no enum edit and no
  core change. A genuinely new *phase* needs the three steps above.

## Architecture Notes

Entries tagged **[seam]** are stable extension points safe to depend on. Entries
tagged **[internal]** are implementation details that may change between
releases.

- **[seam]** Workflow files (`workflows/*.yaml`) — the pipeline is data. Node
  kinds, gates, loops and conditions are documented in the README. Copying one
  and changing it is the intended way to change the pipeline.
- **[seam]** Verdict schemas (`autornd/models/verdicts.py`) — every phase
  input/output is a Pydantic model. Add new verdict types here.
- **[seam]** Deterministic checks (`autornd/graph/checks.py`) — register with
  `@check("name")`. A check must be decidable without a model.
- **[seam]** Profile YAML format (`profiles/*.yaml`) — the contract between your
  project config and the specialist prompt builder, including your `domains:` and
  `roles:` vocabularies. Fields are documented in the example profile.
- **[seam]** REST API endpoints (`autornd/api/routes.py`) — the public HTTP
  interface. New endpoints go here.
- **[seam]** Specialist registry (`autornd/specialists/registry.py`) — add a
  template entry for a shipped role. Profile-declared roles arrive here
  automatically.
- **[seam]** Evals (`autornd/evals/`) — scenario schema, assertions, and the
  bounded runner. New assertion types are a good contribution.
- **[internal]** Graph engine (`autornd/graph/spec.py`, `executor.py`,
  `adapter.py`) — parsing and validating the workflow file, sequencing, gates,
  loops, roster resolution. The workflow file format is the seam; how it is
  executed is not.
- **[internal]** Condition language (`autornd/graph/conditions.py`) — one
  deliberately tiny grammar, `<dotted.path> <op> <literal>`. Not `eval`, and it
  will not become `eval`: a workflow file is configuration and configuration must
  not execute code.
- **[internal]** Review composition
  (`autornd/engine/review_composition.py`) — `get_review_team(risk, domains,
  specialists)` derives the review roster from the specialists triage actually
  assigned, scaled by risk. It is not a static risk-to-team table; it stopped
  being one when the table put seven engineers on a retention schedule.
- **[internal]** Engine phases (`autornd/engine/phases.py`) — prompt text and
  output contracts. May be refactored; the risk guide especially has been
  rewritten several times against live data.
- **[internal]** Routing client internals (`autornd/routing/openrouter.py`) —
  retry logic, accounting, budgets, provider pinning, JSON extraction. The
  interface is stable; the implementation is not.
- **[internal]** Knowledge store schema (`autornd/knowledge/store.py`) — ChromaDB
  collection structure. May change as retrieval improves.
- **[internal]** Workflow entry point (`autornd/engine/workflow.py`) — loads the
  graph, runs it, persists phases and episodic memory. Phases go in the graph,
  not here.
- **[internal]** Dashboard HTML/JS (`autornd/api/templates/dashboard.html`) — the
  UI. Expect frequent changes.

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.
