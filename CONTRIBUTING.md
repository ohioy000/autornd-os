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
pytest tests/ -v
```

All tests must pass before submitting a PR.

## What to Work On

Good first contributions:

- **New specialist types** — add a specialist in `autornd/specialists/registry.py` and register its `SpecialistRole` in `autornd/models/verdicts.py`
- **Model providers** — the routing client in `autornd/routing/openrouter.py` targets any OpenAI-compatible endpoint; adapters for other providers are welcome
- **Workflow phases** — add new phases in `autornd/engine/phases.py` and wire them into the sequencer
- **Review composition rules** — extend `autornd/engine/review_composition.py` with new team selection strategies
- **Profile examples** — add example profiles in `profiles/` for different domains

Check the issue tracker for open issues tagged `good first issue`.

## Pull Requests

- Keep PRs focused — one feature or fix per PR
- Add tests for new functionality
- Update the README if you're adding user-facing features
- All phase outputs must be Pydantic models with typed fields — no prose parsing

## Code Style

- Python 3.11+
- Type hints on public functions
- No comments unless the "why" is non-obvious
- Gate logic checks typed fields (`green == true`, `ship == true`), never parses English

## Building on AutoRnD

- **Fork the repo** — the simplest path. Clone, modify, ship your own version.
- **Import as a library** — `pip install -e .` and import `autornd` into your own project. The profile system, specialists, and workflow engine are all importable. Note: the public API surface is not yet frozen — pin to a commit or tag.
- **Register custom specialists/phases without forking** — add new `SpecialistRole` entries to `autornd/models/verdicts.py`, add matching templates to `autornd/specialists/registry.py`, and wire new phases into `autornd/engine/workflow.py`. No core changes required — the sequencer, review composition, and routing layers all read from the registry dynamically.

## Architecture Notes

Entries tagged **[seam]** are stable extension points safe to depend on. Entries tagged **[internal]** are implementation details that may change between releases.

- **[seam]** Verdict schemas (`autornd/models/verdicts.py`) — every phase input/output is a Pydantic model. Add new verdict types here.
- **[seam]** Profile YAML format (`profiles/*.yaml`) — the contract between your project config and the specialist prompt builder. Fields are documented in the example profile.
- **[seam]** REST API endpoints (`autornd/api/routes.py`) — the public HTTP interface. New endpoints go here.
- **[seam]** Specialist registry (`autornd/specialists/registry.py`) — add specialists by adding a template entry and a `SpecialistRole` enum value.
- **[seam]** Review composition (`autornd/engine/review_composition.py`) — risk-to-team mapping. Add new composition strategies here.
- **[internal]** Engine phases (`autornd/engine/phases.py`) — how each phase calls the model and parses the response. May be refactored.
- **[internal]** Routing client internals (`autornd/routing/openrouter.py`) — retry logic, cost estimation, JSON extraction. The interface is stable; the implementation is not.
- **[internal]** Knowledge store schema (`autornd/knowledge/store.py`) — ChromaDB collection structure. May change as retrieval improves.
- **[internal]** Dashboard HTML/JS (`autornd/api/templates/dashboard.html`) — the UI. Expect frequent changes.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
