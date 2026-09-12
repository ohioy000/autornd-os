# AutoRnD — Multi-Model Agentic Engineering Harness

## Overview

AutoRnD is an agentic engineering team that replaces advisory-style AI with phase-based engineering workflows. You describe an engineering objective and AutoRnD plans, implements, validates, and iterates until done — or escalates what's blocking it.

Domain grounding is configurable via project profiles (YAML files in `profiles/`).

## Tech Stack

- **Python 3.11+**
- **FastAPI** — REST API + chat dashboard
- **SQLAlchemy 2.0 + aiosqlite** — Async SQLite for workflow state
- **Pydantic v2** — Structured verdict schemas
- **httpx** — Async HTTP client for OpenRouter
- **OpenRouter** — Multi-model routing (any OpenAI-compatible endpoint)
- **ChromaDB** — Semantic knowledge retrieval
- **PyYAML** — Project profile configuration
- **pytest** — Testing

## Project Structure

```
AutoRnD-OS/
├── autornd/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings (pydantic-settings)
│   ├── profiles.py          # Project profile loader
│   ├── database.py          # SQLAlchemy async engine
│   ├── cli.py               # CLI commands (init-knowledge, ingest, stats, query)
│   ├── models/
│   │   ├── workflow.py      # ORM models (Workflow, PhaseResult)
│   │   └── verdicts.py      # Pydantic verdict schemas (all phases)
│   ├── specialists/
│   │   ├── base.py          # Specialist base class
│   │   └── registry.py      # 7 specialists + profile-driven system prompts
│   ├── engine/
│   │   ├── phases.py        # Phase implementations (triage, plan, feasibility, implement, validate, review, escalation)
│   │   ├── workflow.py      # Workflow sequencer + iteration loop + escalation recovery
│   │   └── review_composition.py  # Risk-based review team composition
│   ├── routing/
│   │   └── openrouter.py    # OpenRouter client + model routing + retry logic
│   ├── knowledge/
│   │   ├── store.py         # ChromaDB ingestion + retrieval
│   │   ├── context.py       # Context loader (profile-aware docs + retrieval)
│   │   └── episodic.py      # Workflow outcome memory
│   └── api/
│       ├── auth.py          # API key authentication middleware
│       ├── routes.py        # REST endpoints
│       ├── dashboard.py     # Dashboard loader
│       └── templates/
│           └── dashboard.html  # Chat + workflow UI
├── profiles/                # Project profile YAML files
├── docs/                    # Project documentation (per-profile subdirectories)
├── tests/
├── Dockerfile
├── .env.example
├── pyproject.toml
└── requirements.txt
```

## Workflow Phases

Triage → Plan (+ Feasibility Review) → Implement ↔ Validate → Review

- **Triage**: Classifies domain, risk, and specialist assignment
- **Plan**: Systems Architect produces implementation plan
- **Plan Feasibility**: Domain specialists review the plan in parallel
- **Implement ↔ Validate**: Iteration loop, max 5 attempts. If exhausted → escalation autopsy
- **Escalation Autopsy**: Reasoning model analyzes failure pattern, issues recovery directive or flags for human intervention
- **Review**: Risk-based team composition — team size scales with risk level

## Model Routing

| Function | Default Model | Phases |
|---|---|---|
| Triage | `deepseek/deepseek-v4-flash` | Triage |
| Engineering | `minimax/minimax-m3` | Implement, Validate, Review, Feasibility |
| Architecture | `z-ai/glm-5.3` | Plan, critical Review |
| Research | `google/gemini-2.5-flash` | Knowledge retrieval |
| Escalation | `moonshotai/kimi-k3` | Escalation autopsy |

All models configurable via environment variables.

## Key Commands

```bash
uvicorn autornd.main:app --reload --port 8100
pytest tests/ -v
python -m autornd.cli init-knowledge --profile example
```

## Conventions

- All phase outputs are Pydantic models, not prose
- Gate logic checks `green == true` / `ship == true` without parsing English
- Risk levels: critical, high, medium, low — set by triage, controls review depth
- Max 5 iterations on implement↔validate loop, then escalation autopsy
- K3 escalation uses static/dynamic payload split for context cache optimization
- Triage composition is enforced in code, not just prompt guidance
