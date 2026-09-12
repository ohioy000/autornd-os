# AutoRnD

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](#testing)

**An open-source multi-model agentic engineering harness.**

AutoRnD replaces single-model AI assistants with a coordinated engineering team that plans, implements, validates, and iterates on engineering objectives — routing each phase to the right model at the right price point.

Instead of asking one expensive model to do everything, AutoRnD assigns cheap models to triage, mid-tier models to implementation, heavyweight models to architecture, and reasoning models to failure analysis. Every token goes where it counts.

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Architecture](#architecture)
- [What Does AutoRnD Output?](#what-does-autornd-output)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Profiles](#project-profiles)
- [Model Configuration](#model-configuration)
- [API](#api)
- [Project Structure](#project-structure)
- [How It's Different](#how-its-different)
- [Cost Example](#cost-example)
- [Testing](#testing)
- [Deployment](#deployment)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License](#license)

---

## Why This Exists

Most agentic frameworks today either use one model for everything (expensive) or give you a blank canvas to wire your own workflow (slow). AutoRnD is an opinionated, ready-to-run engineering team with:

- **Multi-model cost routing** — 5 model tiers, each matched to its task
- **Typed verdicts at every gate** — Pydantic schemas, not English parsing
- **Risk-based review composition** — critical work gets 7 reviewers, low-risk gets 1
- **Plan feasibility gating** — specialists review the plan before you spend implementation tokens
- **Escalation autopsy** — when cheap models fail, a reasoning model diagnoses why and issues a recovery directive
- **Project-specific grounding** — load your docs, define your domain, and every specialist speaks your stack

To our knowledge, no other open-source framework combines all of these in one package. MetaGPT and CrewAI are the closest comparisons — but they use a single model, target software only, and don't optimize cost across model tiers.

## Architecture

```mermaid
flowchart TD
    A[Request] --> B[Triage]
    B -->|"Flash model · $0.07/M"| C[Plan]
    C -->|"Architecture model · $1.40/M"| D[Feasibility Review]
    D --> E{Plan Approved?}
    E -->|No| F[BLOCKED]
    E -->|Yes| G[Implement]
    G -->|"Engineering model · $0.60/M"| H[Validate]
    H -->|Pass| I[Review]
    H -->|Fail · attempts left| G
    H -->|"Fail · exhausted 5 attempts"| J[Escalation Autopsy]
    J -->|"Reasoning model · $3.00/M"| K{Fixable?}
    K -->|"requires_human = true"| F
    K -->|"requires_human = false"| L["Recovery: 3 fresh attempts"]
    L -->|Pass| I
    L -->|Fail| M[ESCALATED]
    I --> N[COMPLETED]
```

### Model Routing

| Function | Role | Cost Tier | Example Models |
|---|---|---|---|
| Triage | Classification, sorting | Cheapest | DeepSeek V4 Flash, GPT-4o Mini |
| Engineering | Implementation, validation, review | Mid-tier | MiniMax M3, Claude Sonnet, GPT-4o |
| Architecture | Planning, critical review | Heavyweight | GLM 5.3, Claude Opus, GPT-4 |
| Research | Knowledge retrieval | Efficient | Gemini Flash, GPT-4o Mini |
| Escalation | Failure autopsy, recovery | Reasoning | Kimi K3, o1, DeepSeek R1 |

You pick the models. AutoRnD routes them.

### Engineering Specialists

AutoRnD ships with 7 specialists. Each has a domain focus, a system prompt, and a model routing function:

| Specialist | Domain | Router |
|---|---|---|
| Systems Architect | Architecture, integration, trade-off analysis | Architecture |
| Firmware Engineer | Embedded systems, microcontrollers, RTOS, power management | Engineering |
| Hardware Engineer | PCB design, BOM, schematic, thermal | Engineering |
| Backend Engineer | Backend services, APIs, databases, data pipelines | Engineering |
| Frontend Engineer | UI frameworks, data visualization, responsive design | Engineering |
| Test Engineer | Validation plans, test protocols, quality assurance | Engineering |
| Supply Chain | BOM costing, sourcing, compliance | Engineering |

Triage assigns specialists per-workflow based on the request's domain. The Systems Architect always plans; the rest review, implement, and validate according to risk level.

You can override any specialist's grounding context in your [project profile](#project-profiles) — for example, telling the Firmware Engineer your specific MCU and toolchain.

### Review Team Composition

The review phase doesn't throw every specialist at every problem. Team size scales with risk:

| Risk Level | Team | Mode |
|---|---|---|
| Critical | All specialists | Adversarial |
| High | Domain specialists + test + architect | Adversarial |
| Medium | Domain specialist + test or architect | Standard |
| Low | Single relevant specialist | Standard |

### Escalation Autopsy

Named the **K3 pattern** after the Kimi K3 reasoning model it was designed around (though any reasoning model works), this is AutoRnD's recovery mechanism when the implement/validate loop exhausts all attempts.

Most systems just give up at this point. AutoRnD routes a structured autopsy to a reasoning model:

1. **Static context** (system prompt, cached) — the architect's plan, project docs, success criteria
2. **Dynamic context** (user message, uncached) — the failure log from all failed attempts
3. **Constrained output** — strict Pydantic schema, hard token cap to prevent runaway reasoning costs
4. **Recovery or block** — if fixable, scrubs failed context and retries with the directive. If it needs human intervention, stops cleanly.

The reasoning model never touches implementation. It diagnoses and directs — the engineering model executes.

## What Does AutoRnD Output?

AutoRnD produces **structured JSON verdicts**, not executable code or deployed artifacts. Each workflow phase returns a typed Pydantic object:

- **Triage** → domains, risk level, assigned specialists
- **Plan** → implementation steps, success criteria, resource estimates
- **Feasibility** → specialist go/no-go verdicts on the plan
- **Implement** → implementation summary, code suggestions, green/red status
- **Validate** → pass/fail with evidence against the plan's success criteria
- **Review** → ship/block verdict with findings from the review team
- **Escalation** (if triggered) → root cause analysis, recovery directive or human-intervention flag

Gate logic checks typed fields directly — `green == true` controls the implement/validate loop, while `ship` and `findings` in the review verdict are informational (recorded in episodic memory but don't block completion). No English parsing anywhere. You take the output and apply it through your own CI/CD pipeline, code review process, or engineering workflow.

## Prerequisites

- **Python 3.11+**
- **An OpenRouter API key** (or any OpenAI-compatible endpoint) — get one at [openrouter.ai](https://openrouter.ai)
- **Docker** (optional, for containerized deployment)

## Quick Start

```bash
# Clone
git clone https://github.com/ohioy000/autornd-os.git
cd autornd-os

# Configure
cp .env.example .env
# Add your OpenRouter API key to .env

# Install
pip install -r requirements.txt

# Run
uvicorn autornd.main:app --port 8100
```

Open `http://localhost:8100` — chat interface and workflow dashboard ready.

### Docker

```bash
docker build -t autornd .
docker run -p 8100:8100 --env-file .env autornd
```

To mount your own project docs and profiles into the container:

```bash
docker run -p 8100:8100 --env-file .env \
  -v ./profiles:/app/profiles \
  -v ./docs:/app/docs \
  -e AUTORND_PROFILE=my-project \
  autornd
```

## Project Profiles

AutoRnD ships with no domain assumptions. You bring the context:

### 1. Drop your docs

```
docs/
  your-project/
    architecture.md
    api-spec.md
    hardware-constraints.md
    whatever-matters.md
```

### 2. Configure your profile

```yaml
# profiles/my-project.yaml
name: "MyProject"
description: "Edge computing platform for industrial IoT"
site_url: "https://myproject.example.com"
stack:
  - "ESP32-S3 + LoRa sensor nodes"
  - "Python/FastAPI backend"
  - "React/Vite frontend"
  - "SQLite (offline-first)"
constraints:
  - "4GB RAM ceiling on hub device"
  - "No cloud dependency"
  - "Must work in -30C to +50C"
specialists:
  firmware_engineer:
    context: "Targets Heltec ESP32-S3 + SX1262, PlatformIO, FreeRTOS"
  hardware_engineer:
    context: "IP65+ enclosures, LiFePO4 batteries, agricultural environment"
  # ... customize any specialist's grounding
```

### 3. Select on launch

```bash
# Set via environment variable
AUTORND_PROFILE=my-project uvicorn autornd.main:app --port 8100

# Or add to your .env file
# AUTORND_PROFILE=my-project
```

### 4. Ingest docs into the knowledge store

```bash
# Ingest all docs for a profile
python -m autornd.cli init-knowledge --profile my-project

# Ingest a specific file or directory
python -m autornd.cli ingest path/to/doc.md

# Check knowledge store stats
python -m autornd.cli stats

# Query the knowledge store
python -m autornd.cli query "MQTT reconnection" -n 5
```

## Model Configuration

Defaults are set in `autornd/config.py` and can be overridden via `.env` or environment variables.

Prices shown are per million input tokens via [OpenRouter](https://openrouter.ai/models) as of September 2026 — check current rates before budgeting:

```bash
MODEL_TRIAGE=deepseek/deepseek-v4-flash          # $0.07/M in
MODEL_ENGINEERING=minimax/minimax-m3              # $0.60/M in
MODEL_ARCHITECTURE=z-ai/glm-5.3                  # $1.40/M in
MODEL_RESEARCH=google/gemini-2.5-flash            # $0.15/M in
MODEL_ESCALATION=moonshotai/kimi-k3               # $3.00/M in
```

Swap in any model you want:

```bash
MODEL_ENGINEERING=anthropic/claude-sonnet-4
MODEL_ARCHITECTURE=anthropic/claude-opus-4
MODEL_ESCALATION=openai/o1
```

Works with any OpenRouter-compatible model. The client is a standard OpenAI-compatible HTTP client, so you can point it at any provider.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard with chat interface |
| POST | `/api/workflows/sync` | Submit workflow (blocks until complete) |
| POST | `/api/workflows` | Submit workflow (async, returns ID) |
| GET | `/api/workflows` | List all workflows |
| GET | `/api/workflows/{id}` | Workflow detail with phase verdicts |
| GET | `/api/profiles` | Active profile and available profiles |
| POST | `/api/profiles/{name}` | Switch profile and reload specialists |
| GET | `/api/episodes` | Recent workflow outcome history |
| GET | `/api/health` | Health check |
| GET | `/api/knowledge/stats` | Knowledge store stats |

### Example: Submit a workflow

**Request:**

```bash
curl -X POST http://localhost:8100/api/workflows/sync \
  -H "Content-Type: application/json" \
  -d '{"request": "Add a retry mechanism to the MQTT reconnection handler"}'
```

**Response:**

```json
{
  "data": {
    "id": 1,
    "request": "Add a retry mechanism to the MQTT reconnection handler",
    "status": "completed",
    "risk_level": "medium",
    "iteration": 1,
    "total_cost": 0.043,
    "created_at": "2026-09-12T14:30:00",
    "updated_at": "2026-09-12T14:30:12",
    "phases": [
      {
        "phase": "triage",
        "iteration": 0,
        "model_used": "deepseek/deepseek-v4-flash",
        "cost": 0.0001,
        "verdict": {
          "domains": ["backend"],
          "risk": "medium",
          "specialists": ["backend_engineer", "test_engineer"],
          "summary": "MQTT reconnection handler — backend networking task"
        }
      },
      {
        "phase": "plan",
        "iteration": 0,
        "model_used": "z-ai/glm-5.3",
        "cost": 0.017,
        "verdict": {
          "ready": true,
          "plan": "1. Add exponential backoff with jitter to reconnect loop...",
          "blockers": [],
          "success_criteria": ["Reconnects within 30s after broker restart"]
        }
      },
      {
        "phase": "implement",
        "iteration": 1,
        "model_used": "minimax/minimax-m3",
        "cost": 0.006,
        "verdict": {
          "done": true,
          "green": true,
          "summary": "Added exponential backoff with jitter...",
          "iteration": 1
        }
      },
      {
        "phase": "validate",
        "iteration": 1,
        "model_used": "minimax/minimax-m3",
        "cost": 0.005,
        "verdict": {
          "green": true,
          "evidence": ["All reconnection scenarios pass within 30s window"]
        }
      },
      {
        "phase": "review",
        "iteration": 1,
        "model_used": "minimax/minimax-m3",
        "cost": 0.009,
        "verdict": {
          "ship": true,
          "findings": [],
          "verdict": "Implementation meets all success criteria. Ship."
        }
      }
    ]
  }
}
```

## Project Structure

```
autornd/
  main.py                 # FastAPI entry
  config.py               # Model routing + settings
  profiles.py             # Project profile loader
  database.py             # SQLAlchemy async engine
  cli.py                  # CLI commands (init-knowledge, ingest, stats, query)
  models/
    verdicts.py            # Pydantic verdict schemas (every phase)
    workflow.py            # ORM models
  specialists/
    base.py                # Specialist base class
    registry.py            # 7 specialists + profile-driven prompts
  engine/
    workflow.py            # 5-phase sequencer + iteration loop + escalation
    phases.py              # Phase implementations + escalation autopsy
    review_composition.py  # Risk-based review team selection
  routing/
    openrouter.py          # Multi-model client + retry + cost tracking
  knowledge/
    store.py               # ChromaDB ingestion + retrieval
    context.py             # Context builder (profile-aware docs + retrieval)
    episodic.py            # Workflow outcome memory
  api/
    auth.py                # API key authentication middleware
    routes.py              # REST endpoints
    dashboard.py           # Dashboard loader
    templates/
      dashboard.html       # Chat + workflow UI
profiles/                  # Project profile configs (YAML)
docs/                      # Your project documentation
tests/                     # Full test suite
```

## How It's Different

*BYO = Build Your Own — the framework gives you primitives but you wire the behavior yourself.*

This comparison is based on our reading of each project's public documentation and source code as of September 2026. These frameworks evolve quickly — verify against their current releases before deciding:

| Feature | AutoRnD | MetaGPT | CrewAI | LangGraph |
|---|---|---|---|---|
| Multi-model routing | 5 tiers, cost-optimized | Single model | Single model | BYO |
| Typed verdicts | Pydantic at every gate | Partial | No | BYO |
| Risk-based review | Dynamic team composition | Fixed roles | Fixed roles | BYO |
| Plan feasibility gate | Specialists pre-review | No | No | BYO |
| Escalation autopsy | Reasoning model recovery | No | No | No |
| Hardware/firmware | Full specialist support | Software only | Software only | BYO |
| Cost tracking | Per-workflow, per-model | No | No | BYO |
| Domain grounding | Project profiles + docs | Code-focused | Generic | BYO |

## Cost Example

A typical medium-risk engineering workflow. These are estimates based on default model pricing as of September 2026 — actual costs vary with prompt length, output verbosity, and provider rates:

| Phase | Model Tier | Est. Tokens | Est. Cost |
|---|---|---|---|
| Triage | Flash | ~500 | $0.0001 |
| Plan | Architecture | ~3,000 | $0.017 |
| Feasibility (2 specialists) | Engineering | ~2,000 | $0.006 |
| Implement | Engineering | ~2,000 | $0.006 |
| Validate | Engineering | ~1,500 | $0.005 |
| Review (2 specialists) | Engineering | ~3,000 | $0.009 |
| **Total** | | | **~$0.04** |

Escalation (if triggered) adds ~$0.02 for the reasoning model. A full workflow with recovery: ~$0.08.

For comparison, running the same work through a single frontier model typically costs $0.30-0.50+ depending on the provider.

## Testing

```bash
# Run the full test suite
pytest tests/ -v

# Run a specific test file
pytest tests/test_engine.py -v
```

The test suite covers verdict schemas, model routing, review composition, workflow sequencing, escalation recovery, API endpoints, knowledge store, and the profile system.

## Deployment

AutoRnD is designed for **single-user, private-network use**.

### API Key Authentication

Set `API_KEY` in your `.env` to enable bearer token auth on all API endpoints (the dashboard and health check remain public):

```bash
API_KEY=your-secret-key-here
```

When set, every API request must include the key:

```bash
curl -H "Authorization: Bearer your-secret-key-here" http://localhost:8100/api/workflows
```

The dashboard stores the key in `localStorage` — click **API Key** in the top bar to set it.

### Network Security

Even with an API key, avoid exposing AutoRnD to the public internet. For remote access:

- Put it behind a reverse proxy (nginx, Caddy, Traefik) with TLS
- Use a VPN or private network (Tailscale, WireGuard)
- Without auth, anyone who can reach the API can run workflows and spend your API credits

```bash
# Bind to localhost only, proxy externally
uvicorn autornd.main:app --host 127.0.0.1 --port 8100
```

## Limitations

- **No code execution.** AutoRnD generates plans, implementations, and reviews as structured text. It does not compile, run, or deploy code — that's your CI/CD pipeline.
- **Quality depends on the models.** Cheaper models produce cheaper results. The default model selections are a tested balance of cost and quality, but your mileage will vary with different providers.
- **Single-user.** Optional API key auth is included, but there's no multi-tenancy or role-based access. See [Deployment](#deployment) for guidance.
- **OpenRouter dependency.** The default routing client targets OpenRouter. You can point it at any OpenAI-compatible endpoint, but you'll need to manage model availability yourself.
- **No streaming.** The `/api/workflows/sync` endpoint blocks until the full workflow completes. For long-running workflows, use the async endpoint and poll.
- **Costs are real.** Every workflow calls external LLM APIs. A stuck escalation loop burns tokens. Set `MAX_ITERATIONS` conservatively and monitor your OpenRouter spend.

## Contributing

PRs welcome. The architecture is modular — add new specialist types, new model providers, new workflow phases, or new review composition rules without touching the core sequencer.

## License

MIT
