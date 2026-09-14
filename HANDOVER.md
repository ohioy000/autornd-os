# AutoRnD-OS — Project State & Handover Document

**Repo:** `github.com/ohioy000/autornd-os` (public) · **HEAD:** `641da5a` · **Branch:** `main`
**Tests:** 501 passing · **Date of this snapshot:** 2026-09-13

> **Read this first.** Almost every rule, prompt and default in this codebase was
> derived from a *measurement*, and the measurement is recorded in the comment
> next to it. If you are tempted to "clean up" a strange-looking constant, read
> the comment first — it probably names the live run that produced it. Section 6
> lists the measured facts so you do not have to re-derive them at your own
> expense.

---

## 0. VISION & PROVENANCE

### The owner's vision, in their own framing

> *"A harness for team work that can be frugal and accurate, starting with
> engineering R&D, but generally working for any team."*

Four commitments follow from that, and they have shaped every design decision:

1. **Model-agnostic by principle.** *"I'm not picking the model for the public,
   I'm giving them the harness."* **Selection is anonymous; the record is not.**
   Zero model ids in code, configuration defaults, profiles, workflow files and
   any user-facing passage that recommends or defaults to a model — including
   `.env.example`, which names none. Measured results may name their subjects
   and live in the development records: §6 here and `docs/handover-review.md`
   are the lab notebook, and §6.3/§6.4 name models on purpose. The closer a
   document sits to configuration, the stricter the rule. **Zero** hardcoded
   prices anywhere. Tiers are named by *job* (triage, engineering, architecture,
   escalation, research, search), never by vendor. Prices are learned from the provider catalogue at startup; an
   unknown model estimates as `0.0` rather than inventing a number.
2. **Frugal and accurate are the same lever.** Every question moved *out* of a
   model is both cheaper and more reliable. Deterministic checks run before paid
   calls; a free check that can pre-empt a model call always runs first. **This
   holds with exactly one measured exception — see §6.1.**
3. **Outward research is a core default feature, not an option.** The owner was
   emphatic and repeatedly so: *"this is a default main feature, stop asking if
   it's optional."* Its role: *"act as a ranker-esque research bot that searches
   outward for technical docs, ingests them, and adds context where necessary."*
   It is the **anti-confabulation mechanism** (§6.3).
4. **Empiricism over taste.** *"Let's live test before we start making rules and
   use the real tests to guide the direction we make these rules."* Prompts are
   tuned against eval suites, not intuition. Several rules in `phases.py` were
   rewritten 3–4 times because live data contradicted the previous wording.

### Lineage

| Project | Relationship |
|---|---|
| **Archon** — `github.com/coleam00/Archon` | One of the two conceptual parents. Contributed the agentic-orchestration and knowledge-base ideas (retrieval-grounded agents, task decomposition). |
| **AutoExec** — `github.com/ohioy000/AutoExec` | The owner's own fork/earlier generation (referred to in conversation as "openexec"/AutoExec). Shows the evolution of the owner's thinking toward this project — it is the direct predecessor lineage, not an external dependency. |
| **AutoRnD** (private, `ohioy000/AutoRnD`) | The owner's private, domain-loaded implementation. AutoRnD-OS is the **generalised, public, domain-free** descendant. The private version carried ~161 KB of domain grounding; the public one ships with an **empty** knowledge store on purpose. |

AutoRnD-OS is best described as: **Archon's grounded-agent idea + AutoExec's
execution lineage, generalised into a domain-free, model-agnostic, measurable
harness.**

### Hard constraint: private corpora must never enter this repo

`.gitignore` enforces separation. Verified at this snapshot: `git ls-files
profiles/` returns **only** `example.yaml`; no `.env` is tracked.

```
.env
docs/milkhouse/
docs/private*/
evals/private*/
profiles/milkhouse.yaml
profiles/private*.yaml
```

A `profiles/milkhouse.yaml` exists on the owner's working machine and is
correctly untracked. **Do not commit it, and do not add domain-specific content
to the public repo** — the domain-free default is a product decision, not an
oversight.

---

## 1. EXECUTIVE SUMMARY & CORE TECH STACK

### What it is

AutoRnD-OS is a **multi-model agentic engineering harness**. You give it an
objective in prose; it classifies the work, assembles grounding, plans,
implements, validates in a loop, reviews with a risk-scaled team, and either
ships a written deliverable or escalates with a diagnosis. Every phase returns a
**typed Pydantic verdict**, never prose — gates test booleans (`plan.ready`,
`validate.green`, `review.ship`), never parsed English.

The **workflow itself is data**: a YAML graph of nodes (`workflows/*.yaml`). The
pipeline is not compiled into the engine; it is a file you copy and change.

Everything the harness produces is **written output**. Specialists have no
filesystem, shell or repository, and every specialist prompt says so explicitly
(`SPECIALIST_OUTPUT_CONTRACT`) — because without it, models replied that they
could not complete the work, and the validate phase read that as a failed
implementation.

### Stack — installed versions at this snapshot

| Component | Declared | Installed |
|---|---|---|
| Python | `>=3.11` | **3.12.3** (Dockerfile pins `python:3.11-slim`) |
| FastAPI | `>=0.115.0` | 0.141.1 |
| Uvicorn | `>=0.32.0` (`[standard]`) | 0.52.4 |
| Pydantic | `>=2.10.0` | **2.13.5** (v2 validators throughout) |
| pydantic-settings | `>=2.6.0` | 2.15.0 |
| SQLAlchemy | `>=2.0.36` | 2.0.52 (async, `Mapped[]` style) |
| aiosqlite | `>=0.20.0` | 0.22.1 |
| httpx | `>=0.28.0` | 0.28.1 |
| ChromaDB | `>=0.6.0` | **1.5.9** |
| PyYAML | `>=6.0` | 6.0.3 |
| PyJWT | `>=2.8.0` | 2.14.0 |
| pytest | `>=8.3.0` | 9.1.1 |
| pytest-asyncio | `>=0.24.0` | 1.4.0 (`asyncio_mode = "auto"`) |

**Resolved (B1).** `pyjwt` was in `requirements.txt` and missing from
`pyproject.toml` while auth imported it. `requirements.txt` is gone;
`pyproject.toml` is the single manifest. Attempting the install turned up two
further faults in the same file that no test could see — see §4.2 B1.

### Infrastructure

- **Runtime:** single FastAPI process. `uvicorn autornd.main:app --port 8100`.
- **Database:** SQLite via `sqlite+aiosqlite:///./autornd.db`. No migration tool
  (no Alembic) — tables are created from metadata at startup. Schema changes are
  currently destructive.
- **Vector store:** ChromaDB, local persistent directory `./chromadb_data`.
- **Model access:** OpenRouter (`https://openrouter.ai/api/v1`), OpenAI
  chat-completions protocol. Any compatible endpoint works.
- **CI:** `.github/workflows/ci.yml` — two jobs, on push and PR to `main`.
  `test` runs pytest on Python 3.11/3.12/3.13, now installing with
  `pip install -e ".[dev]"`. `editable-install` installs from project metadata
  on 3.12 alone, runs an import smoke over the startup path, and asserts a built
  wheel carries its package data. The second job exists because the first runs
  against the source tree and so cannot see a packaging fault at all — which is
  how B1 shipped.
- **Container:** `Dockerfile` is minimal (see §3.4). No compose file and no
  deployment automation. **There is no production deployment.** The
  owner runs it locally; this snapshot's development box has no sudo, no system
  pip and no Docker (venv bootstrapped via `get-pip.py`).
- **Dev environment quirk:** use `.venv/bin/python3` explicitly. `pytest` is not
  on PATH.

---

## 2. ARCHITECTURAL BLUEPRINT

### 2.1 Data flow

```
HTTP request (api/routes.py)
      │
      ▼
GraphExecutor(spec, runner, settings_lookup).run(request)      graph/executor.py
      │   loads workflows/<name>.yaml                          graph/spec.py
      │   evaluates node.when / gate.condition / loop.until    graph/conditions.py
      ▼
PhaseRunner  ── dispatch: getattr(self, f"_phase_{node.prompt}")   graph/adapter.py
      │
      ├── kind: ai     → engine/phases.py  → specialists/registry.py
      │                                    → routing/openrouter.py  → provider
      ├── kind: check  → graph/checks.py   (FREE — no model call)
      └── kind: gate   → boolean over node outputs; may end the run
      │
      ▼
ExecutionState{ outputs{node_id: verdict}, trace[StepRecord], status, reason }
      │
      ├── persisted → models/workflow.py (Workflow, PhaseResult)
      └── summarised → knowledge/episodic.py (Episode)
```

**Grounding assembly** (`knowledge/context.py`, run once per workflow as the
`context` node):

```
request + triage.domains + triage.specialists + triage.risk
      │
      ├── load_docs_context()      deterministic profile docs (free)
      ├── expand_queries()         research tier → targeted doc queries
      ├── retrieve()               ChromaDB (free)
      ├── rerank_chunks()          ranker tier → native /rerank, else listwise,
      │                            else embedding distance (probe-once, 3-state)
      ├── synthesize_briefing()    research tier → briefing + gaps + blocking_gaps
      │     └── OR analyze_request()  when the store is empty (the ship default):
      │            scoping + unknowns + blocking_unknowns
      └── research_gaps()          search tier → ONE bundled lookup, gated (§4.3)
                                   findings are ingested → local next time
```

### 2.2 Directory structure — critical files marked ★

```
autornd/
  main.py                    FastAPI entry; startup model validation
  config.py              ★  Settings (pydantic-settings), RUNTIME_MUTABLE set
  profiles.py            ★  Project profiles: domains{}, roles{}, specialists{}
  database.py               async engine + Base
  cli.py                    ingest / init-knowledge / stats / query
  models/
    verdicts.py          ★★ ALL phase schemas + RiskLevel/Domain/SpecialistRole
    workflow.py             ORM: Workflow, PhaseResult, WorkflowStatus
    user.py                 ORM: User (JWT auth)
  graph/
    spec.py              ★★ Node, NodeKind, WorkflowSpec, parse/load, validation
    executor.py          ★★ GraphExecutor, ExecutionState, gates, loops, _gate_detail
    adapter.py           ★★ PhaseRunner: node → phase dispatch, specialist rosters
    conditions.py        ★  Deliberately tiny expression language (NOT eval)
    checks.py            ★  Free deterministic checks + registry
  engine/
    phases.py            ★★ Every prompt lives here. Triage risk guide. ~750 lines
    review_composition.py ★ get_review_team(risk, domains, specialists)
    workflow.py             Legacy WorkflowEngine (hardcoded sequence; kept as
                            the equivalence reference for the graph)
  knowledge/
    context.py           ★★ Grounding assembly, rerank, scoping, research gating
    research.py          ★★ Outward lookup, recall-before-search, findings
    store.py             ★  ChromaDB ingest / retrieve
    episodic.py             Workflow outcome memory
  routing/
    openrouter.py        ★★ Client, tier resolution, accounting, budgets,
                            provider pinning, JSON extraction, schema retry
  specialists/
    registry.py          ★  7 built-in roles + profile roles + generalist fallback
    base.py                 Specialist dataclass
  evals/
    scenario.py          ★  Scenario schema + expectation validation
    assertions.py        ★  All assertions (free, no model calls)
    runner.py            ★  BoundedRunner, per-tier reporting, repetitions
    cli.py                  `python -m autornd.evals.cli`
  api/
    routes.py               17 endpoints (§3.5)
    auth.py                 JWT + API key middleware
    templates/dashboard.html  single-file chat + workflows + settings UI

workflows/
  engineering-rnd.yaml   ★★ the flagship pipeline, 16 nodes (full text in §3.1)
  lean.yaml                 9 nodes — cheaper variant
  triage-only.yaml          2 nodes — triage + grounding (research measurement)
  triage-classify.yaml   ★  1 node — triage alone. Exists so calibration costs
                            ~$0.00002/call instead of a full workflow.

evals/
  scenarios/*.yaml          17 core scenarios (default suite)
  scenarios/wide/*.yaml  ★  36 sector scenarios — OPT-IN (non-recursive glob)
  grounding/*.yaml       ★  8 sectors graded against published figures

profiles/example.yaml       the only tracked profile
tests/                      17 files, 501 tests
```

### 2.3 Key design patterns

**Workflow-as-data.** `graph/spec.py` defines three node kinds:

| kind | behaviour |
|---|---|
| `ai` | one or more model calls via `PhaseRunner._phase_<prompt>` |
| `check` | free deterministic function from `checks.registry` |
| `gate` | boolean over prior outputs; `on_fail` sets a terminal status |

Node fields: `id, kind, depends_on, when, tier, tier_when, specialist, prompt,
schema, max_tokens, check, args, condition, on_fail, on_fail_reason, body,
until, max_iterations, on_exhausted, on_exhausted_status`.

A node with `body` is a **loop** over that sub-sequence until `until` holds or
`max_iterations` (which may *name a setting*, resolved at run time).

**Specialist rosters** — `specialist:` accepts a concrete role name or a roster:

| token | meaning |
|---|---|
| `assigned` | every specialist triage assigned, in parallel |
| `builders` | assigned, minus whoever validates |
| `peers` | builders other than the lead |
| `lead` | the domain lead among the builders |
| `reviewers` | the risk-scaled review team |

**Conditions are not `eval`.** `graph/conditions.py` implements one grammar:
`<dotted.path> <op> <literal>`, `<path>` (truthiness), or `not <path>`. Ops:
`== != < <= > >= in`. A test asserts `__import__('os').system(...)` is rejected.
Missing paths **raise** rather than silently evaluating false — a typo'd `when`
that silently skipped a node would be worse than a loud failure.

**Open vocabularies.** `Domain` and `SpecialistRole` are **defaults, not
limits**. Both normalise through `normalise_key()` / `domain_key()` /
`role_key()` in `verdicts.py`; both enums subclass `str`, so every legacy
comparison still works. Profiles declare their own `domains:` and `roles:`; an
undeclared role resolves to a **synthesized generalist** rather than raising.
*(Rationale in §6.5.)*

**Accounting lives on the client.** `OpenRouterClient` holds `spend`, `calls`,
`spend_by_function`, `calls_by_function`, `providers_by_function`, plus optional
`call_ceiling` / `spend_ceiling` enforced inside `_account()`. Nothing can make
a call without being priced. `PhaseRunner.total_cost` is a *property* reading
`client.spend`.

**Three-state rerank probe.** `_rerank_mode: None → "native" | "listwise" |
"distance"`. Each strategy is probed **at most once**; a dead end stops costing
calls forever after.

### 2.4 Database schemas

```python
# models/workflow.py
class WorkflowStatus(str, Enum):
    PENDING, TRIAGE, PLAN, IMPLEMENT, VALIDATE, REVIEW,
    COMPLETED, BLOCKED, ESCALATED

workflows        id PK · request TEXT · status ENUM · risk_level STR(20)
                 iteration INT · created_at · updated_at
                 total_cost FLOAT · error TEXT · user_id FK→users.id
phase_results    id PK · workflow_id FK→workflows.id · phase STR(20)
                 iteration INT · verdict_json TEXT · model_used STR(100)
                 cost FLOAT · created_at
                 (Workflow.phases cascade="all, delete-orphan")
users            id PK · username STR(50) UNIQUE IDX · email STR(255) UNIQUE
                 password_hash STR(255) · created_at
episodes         id PK · workflow_id INT · request TEXT · domains TEXT
                 risk STR(20) · iterations INT · shipped BOOL · verdict TEXT
                 findings_count INT · total_cost FLOAT · created_at
```

`workflow.total_cost` is **assigned** from `self.client.spend` (not accumulated
per response) so research and rerank spend are included; assignment is
idempotent across phases.

---

## 3. CURRENT STATE & SOURCE OF TRUTH

### 3.1 `workflows/engineering-rnd.yaml` — the flagship pipeline (16 nodes)

Execution order: `triage → context → plan → feasibility → plan_ready →
build_loop → review → review_clean → independent_check`
(`build_loop` body: `implement → domain_review → coverage → consistency →
validate`; exhaustion hands off to `escalation → recoverable → recovery_loop`.)

```yaml
name: engineering-rnd
nodes:
  - {id: triage,  kind: ai, tier: triage, prompt: triage, schema: TriageVerdict}
  - {id: context, kind: check, check: build_context, depends_on: [triage]}

  - id: plan
    kind: ai
    tier: architecture
    tier_when: {"triage.risk == 'low'": engineering}   # a restyle needn't wake a reasoner
    specialist: systems_architect
    prompt: plan
    schema: PlanVerdict
    depends_on: [context]

  - {id: feasibility, kind: ai, tier: engineering, specialist: assigned,
     prompt: feasibility, depends_on: [plan], when: "plan.ready == true"}
  - {id: plan_ready, kind: gate, condition: "plan.ready == true",
     depends_on: [feasibility], on_fail: blocked, on_fail_reason: "Plan not ready"}

  - {id: implement, kind: ai, tier: engineering, specialist: lead,
     prompt: implement, schema: ImplementVerdict}
  - {id: domain_review, kind: ai, tier: engineering, specialist: peers,
     prompt: domain_review, depends_on: [implement], when: "implement.green == true"}
  - {id: coverage, kind: check, check: criteria_addressed,
     args: {criteria: plan.success_criteria, text: implement.summary}, depends_on: [implement]}
  - {id: consistency, kind: check, check: numbers_consistent,
     args: {plan: plan.plan, implementation: implement.summary}, depends_on: [implement]}
  - {id: validate, kind: ai, tier: engineering, specialist: test_engineer,
     prompt: validate, schema: ValidateVerdict, max_tokens: validate_max_tokens,
     depends_on: [coverage, consistency, domain_review]}

  - {id: build_loop, kind: ai, body: [implement, domain_review, coverage, consistency, validate],
     until: "validate.green == true", max_iterations: max_iterations,
     on_exhausted: escalation, depends_on: [plan_ready]}

  - {id: escalation, kind: ai, tier: escalation, prompt: escalation,
     schema: EscalationVerdict, max_tokens: escalation_max_tokens}
  - {id: recoverable, kind: gate, condition: "not escalation.requires_human",
     depends_on: [escalation], on_fail: blocked,
     on_fail_reason: "Escalation requires human intervention"}
  - {id: recovery_loop, kind: ai, body: [implement, domain_review, coverage, consistency, validate],
     until: "validate.green == true", max_iterations: escalation_recovery_attempts,
     on_exhausted_status: escalated, depends_on: [recoverable]}

  - {id: review, kind: ai, tier: engineering, specialist: reviewers,
     prompt: review, schema: ReviewVerdict, depends_on: [build_loop]}
  - {id: review_clean, kind: gate, condition: "review.ship == true",
     depends_on: [review], on_fail: blocked,
     on_fail_reason: "Review found blocking issues"}
  - {id: independent_check, kind: ai, when: "triage.unrecallable",
     tier: independent, prompt: doublecheck, schema: DoubleCheckVerdict,
     depends_on: [review_clean]}
```

### 3.2 `pyproject.toml` (verbatim)

```toml
[project]
name = "autornd"
version = "0.1.0"
description = "AutoRnD — Multi-model agentic engineering harness"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0", "uvicorn[standard]>=0.32.0", "pydantic>=2.10.0",
    "email-validator>=2.2.0", "pydantic-settings>=2.6.0", "sqlalchemy>=2.0.36",
    "aiosqlite>=0.20.0", "httpx>=0.28.0", "python-dotenv>=1.0.1",
    "chromadb>=0.6.0", "pyyaml>=6.0", "pyjwt>=2.8.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.3.0", "pytest-asyncio>=0.24.0"]

[project.scripts]
autornd = "autornd.cli:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

# Both added by B1; without them the build fails outright and the wheel ships
# no dashboard template. Comments trimmed here — the file carries the full ones.
[tool.setuptools.packages.find]
include = ["autornd*"]

[tool.setuptools.package-data]
autornd = ["api/templates/*.html"]

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.build_meta"
```

### 3.3 Verdict schemas — `models/verdicts.py`

```python
RiskLevel(str, Enum):      CRITICAL, HIGH, MEDIUM, LOW
Domain(str, Enum):         firmware, hardware, backend, frontend,
                           supply_chain, infrastructure, documentation   # DEFAULTS
SpecialistRole(str, Enum): systems_architect, firmware_engineer, hardware_engineer,
                           backend_engineer, frontend_engineer, test_engineer,
                           supply_chain                                  # DEFAULTS

TriageVerdict     domains: list[str]          # open vocabulary, normalised+deduped
                  risk: RiskLevel
                  specialists: list[str]      # open vocabulary, normalised+deduped
                  unrecallable: bool = False  # SEPARATE AXIS from risk (§6.6)
                  summary: str
PlanVerdict       ready: bool · plan: str="" · blockers: list[str]
                  cost_estimate: float|None · success_criteria: list[str]
                  # validators: plan required when ready; blockers required when
                  # not ready; _is_placeholder() rejects "...", "TBD" criteria
ImplementVerdict  done · green · red_cause|None · iteration: Field(ge=1)
                  summary · domain_concerns: list[str]
ValidateVerdict   green · (findings)
ReviewFinding     lens="unknown" · severity="medium" · detail=""
                  # model_validator(before) accepts a bare string, or detail under
                  # issue/description/finding/concern/text/problem/note/summary/message
ReviewVerdict     ship: bool · findings: list[ReviewFinding] · verdict: str
                  # field_validator(before) drops entirely-empty findings
DoubleCheckVerdict ship · confidence · critical_issues[] · recommendations[] · verdict
EscalationVerdict root_cause_analysis · architectural_correction|None · requires_human
```

### 3.4 `Dockerfile` (verbatim)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
# Editable: workflows/ and profiles/ resolve relative to the package directory
# and ship in neither the wheel nor the package, so a relocating install points
# both at paths that do not exist. Comments trimmed — see the file.
RUN pip install --no-cache-dir -e .
EXPOSE 8100
CMD ["uvicorn", "autornd.main:app", "--host", "0.0.0.0", "--port", "8100"]
```

### 3.5 API surface — `api/routes.py`

```
POST   /api/auth/register            201
POST   /api/auth/login
GET    /api/auth/me
POST   /api/workflows                202  (async, background)
POST   /api/workflows/sync                (blocking)
GET    /api/workflows
GET    /api/workflows/{id}
GET    /api/workflows/{id}/doublecheck/estimate
POST   /api/workflows/{id}/doublecheck
GET    /api/settings
PUT    /api/settings                      (only keys in Settings.RUNTIME_MUTABLE)
GET    /api/health                        degraded + names tiers if models unverified
GET    /api/profiles
POST   /api/profiles/{name}               switch active profile
GET    /api/knowledge/stats
GET    /api/episodes
```

CLI: `python -m autornd.cli {ingest|init-knowledge|stats|query}`
Evals: `python -m autornd.evals.cli --scenarios DIR --workflow NAME --repeat N
[--timeout S] [--max-spend USD] [--compare W1 W2]`

### 3.6 Environment variables (placeholders only — never commit real values)

```bash
# ── provider ─────────────────────────────────────────────────────────────
OPENROUTER_API_KEY=<YOUR_OPENROUTER_KEY>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# Per-tier provider pin, comma separated, highest first. Fallbacks DISABLED.
#   StreamLake                  every tier prefers StreamLake
#   triage:StreamLake,search:   triage pinned, search left free
#   triage:StreamLake,Together  triage pinned, everything else Together
# A tier named with an empty value is explicitly unpinned. SEE §6.1 — this is
# a QUALITY control, not just availability.
OPENROUTER_PROVIDER_ORDER=

# ── model tiers: 6 required, 2 optional. NO defaults ship. ───────────────
MODEL_TRIAGE=<vendor/model>          # cheap, reliably valid JSON
MODEL_ENGINEERING=<vendor/model>     # implement, validate, review, feasibility
MODEL_ARCHITECTURE=<vendor/model>    # plan, critical review
MODEL_ESCALATION=<vendor/model>      # failure autopsy; the one tier that wants a reasoner
MODEL_RESEARCH=<vendor/model>        # briefing/scoping; must not invent facts
MODEL_SEARCH=<vendor/model>          # outward lookups WITH citations
MODEL_RANKER=                        # optional: native /rerank model
MODEL_PREMIUM=                       # optional: independent pass; falls back to architecture

# ── budgets (every value below was set from a measurement — see §6) ──────
MAX_ITERATIONS=5
SEARCH_MAX_TOKENS=1500               # medium-risk lookup budget
SEARCH_MAX_TOKENS_CONSEQUENTIAL=4000 # high/critical lookup budget
VALIDATE_MAX_TOKENS=8000             # do NOT set near 3000 (§6.4)
ESCALATION_MAX_TOKENS=16384          # do NOT set low: reasoners need headroom
ESCALATION_RECOVERY_ATTEMPTS=3

# ── runtime ──────────────────────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8100
LOG_LEVEL=INFO
DATABASE_URL=sqlite+aiosqlite:///./autornd.db
CHROMADB_PATH=./chromadb_data
API_KEY=<SERVICE_API_KEY_PLACEHOLDER>
JWT_SECRET=<JWT_SECRET_PLACEHOLDER>
REGISTRATION_ENABLED=true
AUTORND_WORKFLOW=engineering-rnd
AUTORND_PROFILE=                     # loads profiles/<name>.yaml
```

⚠️ **SECURITY — ACTION REQUIRED.** Three credentials were pasted into the
working conversation during development and **must be rotated**: two GitHub PATs
(one read-only, one write) and **three** OpenRouter API keys (two expired, one
live and currently in the untracked local `.env`). None are in git history.

### 3.7 Test distribution (501 total)

| file | n | file | n |
|---|---|---|---|
| test_graph.py | 82 | test_review_composition.py | 28 |
| test_evals.py | 73 | test_profiles.py | 23 |
| test_routing.py | 62 | test_api.py | 21 |
| test_verdicts.py | 42 | test_settings.py | 20 |
| test_knowledge.py | 41 | test_auth.py | 16 |
| test_research.py | 37 | test_graph_equivalence.py | 16 |
| test_specialists.py | 11 | test_lead_review.py | 9 |
| test_triage.py | 10 | test_engine.py | 6 |
| test_workflow.py | 4 | | |

---

## 4. ACTIVE CONTEXT & WORKING MEMORY

### 4.1 What we were doing immediately before this handover

Executing a 4-item list, in this order, all four now complete:

1. **Measure how often research actually fires** → 33/36 (92%). §6.2.
2. **Resolve the wide-sweep calibration drop** (35/36 → 29/36) → root cause was
   **provider rotation**, not code. §6.1.
3. **Provider-pin experiment** → conclusive; produced the price/quality table.
4. **Independent pass** → verified by decomposition after 9 failed live attempts.

Immediately prior to that, a larger arc: fixing a broken cost meter, opening the
roles vocabulary, gating review, and cutting search spend. 14 commits this
session, `3fdf3b3` → `641da5a`.

### 4.2 Known bugs, blockers and failing tests

**No failing unit tests — 501/501 pass.** Everything below is a live-behaviour
or design issue.

| # | Issue | Severity | Notes |
|---|---|---|---|
| B1 | Packaging metadata was unusable | **RESOLVED** | Not one fault but three, and the trivial one was the least of them. `pyjwt` was missing from `pyproject.toml`; flat-layout discovery saw `evals/ profiles/ workflows/` beside `autornd/` and **failed the build**, so `pip install -e .` never reached the ImportError; and no wheel carried `dashboard.html`, so a built install served FileNotFoundError from the dashboard route. One manifest now, plus a CI job that installs from it. |
| B2 | ~~Materiality gate is ineffective~~ | **RESOLVED — it is not a cost lever, and does not need to be** | The finding stands: it never returns empty. But work whose gaps are immaterial reads `low`, and the risk gate already zeroes its lookups — measured 12/12 across six probe designs. The cap of three earns its place as a *question-count* limit protecting per-question tokens (§6.3: truncation, not ignorance). A per-gap reframe was tried and reverted: it zeroed a **material** lookup. §12.5 |
| B3 | ~~`--max-spend` is per scenario, not per sweep~~ | **RESOLVED** | `--max-spend-sweep` bounds the whole invocation — every scenario, repetition and compared workflow against one budget. Defaults to $1.00, `none` disables. With both caps set no unit starts unless it must fit, so the sweep cap is exact; alone, it stops the crossing unit via the existing client ceiling. Fixing it exposed a second bug: six handlers on the research and rerank paths swallowed `BudgetExceeded`, so an abort did not stop the run |
| B4 | ~~`wide_legal_ops` under-classifies on every provider~~ | **RESOLVED — the premise was wrong** | It is the serving, not the guide. Pinned six ways: fails 3/3 on OpenInference, DigitalOcean and unpinned; passes 3/3 on Alibaba and AtlasCloud, 2/3 on StreamLake. Under the adopted `triage:Alibaba` pin it passes ~8/9, and its rare excursions go in **both** directions. No guide edit was made — there was no systematic failure left to target. §12.3, §12.4 |
| B5 | `wide_wind_energy` fails `risk_at_least` ~1/3, **deliberately left red** | low | Two defensible readings; a risk **floor must never be waivable** (§4.4) |
| B6 | `independent_check` has **never executed inside a full live workflow** | medium | Wiring proven by test; the tier proven by a direct live call. 9 attempts each hit a *different, mostly legitimate* earlier exit |
| B7 | Build loop does not converge on complex requests | medium | Earlier root cause diagnosed: implementer has no filesystem, validator rejected nonexistent work. `SPECIALIST_OUTPUT_CONTRACT` mitigates; not fully solved |
| B8 | Shipped-default models fail on hard requests | medium | Documented rather than changed, per owner's instruction. §6.4 |
| B9 | No DB migrations (no Alembic) | low | Schema changes are destructive |
| B10 | `ambiguous_request` — historical "mystery failure" | **RESOLVED** | It was B3's sibling: a `max_calls: 4` baseline set when the budget counted *nodes*. Measured 6. Now 8 |

### 4.3 Search-cost policy as it stands (the most-iterated subsystem)

```
risk == low                  → 0 lookups, $0
no blocking gap marked       → 0 lookups, $0
otherwise                    → EXACTLY 1 bundled request carrying every gap
  medium                     → SEARCH_MAX_TOKENS (1500)          ≈ $0.030
  high / critical            → SEARCH_MAX_TOKENS_CONSEQUENTIAL   ≈ $0.067
store already answers a gap  → free (recall before search, distance ≤ 0.35,
                               research-tagged material only)
MAX_LOOKUPS = 1
```

Result: **$0.0999 → $0.0562 per workflow (−44%)**, measured across 36 sectors.

### 4.4 Established conventions — please preserve these

1. **Every non-obvious constant carries the measurement that set it.** Comments
   explain *why*, with the number. This is the codebase's most valuable
   property; do not strip it in refactors.
2. **Derive rules from live measurement, never from taste.** The triage risk
   guide was rewritten four times because data contradicted each version.
3. **Free checks before paid calls.** Always.
4. **Enums are default vocabularies, not limits.** New closed enums for anything
   a user's domain might extend are an anti-pattern here.
5. **Typed verdicts; gates test booleans.** Never parse English for control flow.
6. **No `eval` in workflow files.** Configuration must not execute code.
7. **Write eval expectations *before* running.** Then report mismatches
   honestly, including "my expectation was wrong."
8. **A risk *floor* is never waivable.** Ceilings may be waived with a recorded
   reason in the scenario's `risk_ceiling_waived` field — a schema field, so a
   test can check it. `risk_at_most: critical` is a *vacuous* assertion and must
   not be written.
9. **Test doubles must bill like the real client** (`client._account(...)`).
   A free double hides accounting bugs — it did.
10. **Never hardcode a model name or a price.** Rates come from the catalogue.
11. **Isolate the knowledge store in experiments** (`_isolated_store()`).
    Research ingests, so scenario 1 otherwise grounds scenarios 2–12.
12. **Commit messages are prose that explains the measurement**, not bullet
    lists. Match the existing style.
13. **Source a number before asserting it.** Convention 7's sibling: a figure
    in a plan carries where it came from — measured (with the §6 reference),
    derived (with the method), or an estimate to be derived before it is used.
    Estimates set expectations and never gate anything. Four blueprints in, the
    estimates have been the wrong part every time while the mechanisms held.
    The protocol is in `docs/handover-review.md` §0.
14. No linter/formatter is configured. Match surrounding style: 4-space indent,
    `from __future__ import annotations`, type hints throughout, ~88-col soft
    wrap, module docstrings that explain rationale.

---

## 5. THE ROADMAP & NEXT STEPS

### Immediate (prioritised)

1. ~~**B1 — add `pyjwt` to `pyproject.toml`.**~~ **Done**, and it was three
   faults rather than one — see §4.2. `requirements.txt` is deleted,
   `pyproject.toml` is canonical, and CI has an `editable-install` job that
   installs from it. The lesson generalises: *the fault that a test suite
   structurally cannot see is the one that ships.* Running the install once
   found two defects that had been invisible to 501 tests.
2. ~~**B3 — sweep-level spend cap.**~~ **Done.** `--max-spend-sweep`, default
   $1.00, `none` to disable; `--max-spend` is unchanged and still per scenario-
   run. Production still keeps *no* cap, for the reason originally given —
   aborting a live workflow mid-flight destroys work, and search is
   structurally bounded at ≈$0.07/workflow. Two things worth carrying forward:
   overshoot under the backstop is bounded by the widest **parallel fan-out**,
   not by one call, because feasibility and both reviews run their rosters
   through `asyncio.gather`; and a budget abort now propagates rather than
   being swallowed by the research and rerank error handlers.
3. **B2 — make materiality actually discriminate.** A model asked to self-limit
   does not. Options: require a blocking gap to name a quantity/limit/standard
   (checkable, but phrasing-fragile); ask *per gap* "would a wrong assumption
   change the answer?" instead of requesting a subset; or drop the gate and
   treat the token budget as the only dial (honest, and §6.2 shows gap *count*
   doesn't affect cost anyway).
4. ~~**B4 — `legal_ops` calibration.**~~ **Done, by pinning rather than
   tuning.** The instruction to pin before tuning turned out to be the whole
   fix: the governance-document clause was landing all along, on a serving
   capable of reading it. Nothing in `phases.py` changed.
5. **Choose and document a provider pin for the owner's real workload.**
   `--scenarios evals/scenarios/wide` scores a provider in ~10 min for <2¢.

### Medium term

6. **B6 — reach `independent_check` in a live full workflow.** Needs a model
   combination that reliably completes one; consider a purpose-built minimal
   workflow (the `triage-classify` trick applied to review).
7. **B7 — build-loop convergence.** The highest-value unsolved *product*
   problem: the implement↔validate loop is where iterations and money go.
8. **Per-tier provider quality measurement.** The eval suite can now score
   providers; only triage has been measured.
9. **Alembic migrations** before anyone stores real data.
10. ~~**CI — extend, do not create.**~~ **Done, and now complete.**
    `.github/workflows/ci.yml` carries the matrix, an `editable-install` job,
    and a `docker` job that builds the image, runs it, and smokes `/api/health`
    and `/`. Every install shape is now exercised: source tree, project
    metadata, built wheel, and container. The dashboard template check is the
    one that matters — it is the wheel-data fault of B1 in its deployment
    shape.

### Longer term / technical debt

11. **Retire `engine/workflow.py`** (legacy hardcoded sequence). It is kept as
    the graph's equivalence reference (`test_graph_equivalence.py`, 16 tests).
    Once the graph is trusted, deleting it removes a whole duplicated pipeline —
    but it *has* caught real drift, so keep it until it stops paying.
12. **Review→rework loop.** The review gate currently blocks. Feeding findings
    back into implement/validate is more useful but needs exhaustion semantics,
    and review/validate can disagree indefinitely.
13. **Generalise beyond engineering.** The vision is "any team." Roles, domains
    and validation lenses are now open; the *prompts* in `phases.py` still speak
    engineering. That is the next frontier for the "works for any team" claim.
14. **Cross-workflow finding reuse.** Recall exists per gap; a warm shared store
    across a team's workflows is where search cost goes to near zero.
15. **Dashboard.** `dashboard.html` is a single file and has had little
    attention relative to the engine.

---

## 6. MEASURED FACTS — DO NOT RE-DERIVE THESE

Each cost real money and wall-clock to establish.

### 6.1 ⚠️ A model id is not a system — the one place the thesis inverts

One 108-call sweep saw the triage tier served by **five** providers (Alibaba,
AtlasCloud, DigitalOcean, OpenInference, StreamLake). Pinning each and re-running
the *identical* 36-sector suite and prompt:

| provider | sectors passing | cost | wall clock |
|---|---|---|---|
| (unrecorded, likely StreamLake) | **35/36** | $0.0329 | 1465 s |
| StreamLake pinned | **33/36** | $0.0185 | 1102 s |
| unpinned, 5 mixed | 30/36 | $0.0135 | 853 s |
| OpenInference pinned | **28/36** | **$0.0015** | 303 s |

**12× the price bought 5 sectors of accuracy and 3.6× the latency.** The cheap
serving did not fail randomly: it under-classified risk on `water_treatment`,
`building_services` and `legal_ops` on **every repetition** — the dangerous
direction.

*Implications:* an unpinned eval score is partly a record of who answered. A
"35/36 → 29/36 regression" chased as a code bug was this. And the risk guide
rewritten three times that day was being tuned against a lottery. **Pinning is a
precondition for calibrating anything.**

"Frugal and accurate are the same lever" holds when you remove a question from a
model. It is **false** when you buy a cheaper serving of one.

### 6.2 Research fires on 92% of workflows

| risk | looked up | mean unknowns | mean marked blocking |
|---|---|---|---|
| low | **0/3** | 11.3 | 2.7 |
| medium | 5/5 | 10.8 | 2.8 |
| high | 9/9 | 11.9 | 2.9 |
| critical | 19/19 | 12.1 | 2.9 |

The materiality gate never produced an empty list (0/33). Only the risk gate
fires, and `low` is 8% of this (deliberately consequence-heavy) suite. Net
saving **44%**, almost entirely from 4 requests → 1.

**Key structural insight:** with one bundled request, the *number* of gaps does
not affect cost. Cost = fee + tokens. Materiality only saves money by producing
**zero** gaps.

**Resolved 2026-09-14 (B2).** Zero gaps is what work with cosmetic unknowns
produces — but the risk gate gets there first and more cheaply, because that
work reads `low`. Six probe designs at the deciding stage, twelve repetitions,
not one lookup fired: requests whose unknowns are preferences classify `low`
even when committed to a print run or a send to every user. **Risk and
materiality are correlated**, so the materiality gate was never going to add a
saving on top of the risk gate. What the cap of three actually buys is
per-question tokens: drop it and roughly a dozen questions ride one bundled
request against a fixed budget, which §6.3 measured as truncation of the tails.
A per-gap reframe with an explicit empty case was tried and reverted — it
changed nothing immaterial and zeroed a *material* lookup.

### 6.3 Search pricing and the accuracy/token curve

Measured on `perplexity/sonar-pro`: **$15.00 per 1M output tokens + ≈$0.00698
per request.** The model fills whatever cap it is given (2907/3000, 1407/1500,
217/300). At a 3000-token cap the fee is **13%** and tokens **87%** — so *"it's
priced per call, give it the maximum"* is the opposite of what the billing does.

Graded against published figures across the 8 `evals/grounding` sectors:

| total output tokens | figures recovered | search cost (8 sectors) |
|---|---|---|
| ~4800 (4 separate lookups) | **7/8** | $0.72 |
| ~2900 (1 bundled) | **5/8** | $0.32 |
| ~1400 (1 bundled) | **3/8** | $0.17 |

≈ one recovered sector per 800 tokens. Misses at the lean budget were precisely
the *tails* of bundled questions (`-1 dBTP`, `type B`, `8(d-14)`) — truncation,
not ignorance. **Tokens buy figures; bundling saves only the fee (13%).**

*Why research exists at all:* asked which charger IC a specific board used, a
capable model answered "IP5306" in bold with no hedge; a search-backed model
answered "MCP73831" with 18 citations. Asked the EU 868 MHz limit, the same model
gave "25 mW (+14 dBm EIRP)" — conflating ERP with EIRP, 2.15 dB apart, the
difference between a compliant transmitter and a failed certification. Both
answers were confident. **Apparent certainty does not correlate with
correctness, so there is no confidence signal to gate a lookup on.**

### 6.4 Model behaviour on the shipped default tiers

- `z-ai/glm-5.3` (architecture) returns a **schema-shaped stub** —
  `{"plan": "...", "success_criteria": ["...", "..."]}` — at
  `finish_reason=stop`, with *and without* a worked example in the prompt, and
  across Together/AkashML/Wafer. **It is the model, not the provider.**
- `minimax/minimax-m3` (engineering) spent **all 16,384 tokens** reasoning and
  returned no text on the same request.
- **But the same glm-5.3 is an incisive reviewer.** As the independent pass it
  caught a real flaw nothing upstream had: that putting a table rename and drop
  in one migration script makes the observation window between them impossible.
  **Judge a tier by its job, not the model's reputation.**
- `validate_max_tokens` was 3000 and too tight: a reasoning model spent the whole
  budget thinking and emitted nothing **three times**, failing the run having
  paid for 9000 tokens of nothing. Now 8000. **A ceiling is billed only when
  used, so headroom is free on runs that were already fine.**

### 6.5 Closed vocabularies produce least-wrong labels, not honest refusals

With `Domain` enforced as an enum, **9 of 12** subjects had no fitting value and
**8 of those 9** came back `hardware` — civil engineering as "hardware", a 5 ms
latency budget as "firmware, hardware", buffer chemistry as "documentation".
Triage was not guessing badly; it was picking from a list without the answer.

Same defect for roles: asked to staff a firmware signing-key rotation, triage
returned `infrastructure_engineer` (not a shipped role) and put the *domain*
value `documentation` in the specialists field.

Review composition had the same shape: `critical` returned `list(SpecialistRole)`
— **seven engineers reviewing a records retention schedule.**

### 6.6 Risk calibration — current state and the rules that earned their place

Best measured: **35/36** (provider-dependent, see §6.1). The guide asks two
questions **in order**, and the ordering is load-bearing — judging *stage* before
*consequence* demoted a concrete lintel and a sterilisation protocol.

1. Can a person be harmed, or is a **harm-preventing** rule breached (structural
   loading, food contact, sterility, pressure, electrical code, emissions)?
   → `critical`, at every stage.
   - **Not every published standard is a harm rule.** Quality/interoperability
     standards (broadcast loudness, file formats, style guides) are not. Treating
     them alike pushed `broadcast` to `high` 3/3.
2. If not: has anything been committed to yet? Acting (`high`) vs deciding
   (`medium`) vs trivially reversible (`low`).
   - **Governing documents** — a protocol, schedule, policy or setpoint band
     followed repeatedly — are judged by *what happens when they are followed*.
     Without this, a return-to-play progression and a statutory retention
     schedule both read `low`.
   - **Protective systems** (a backup, interlock, alarm, containment,
     life-support) are judged by *what they protect*: **at least high**, and
     critical only if a person can be harmed. Naming the level mattered — the
     first wording sent 200 t of livestock to `critical`.

**A calibration gap can be a serving gap.** Measured 2026-09-14, the same
36-sector suite pinned six ways at three repetitions:

| pin | sectors 3/3 | cost | `legal_ops` |
|---|---|---|---|
| unpinned → OpenInference | 27/36 | $0.0014 | 0/3 |
| OpenInference | 27/36 | $0.0014 | 0/3 |
| DigitalOcean | 22/36 | $0.0041 | 0/3 |
| Alibaba | 31/36 | $0.0317 | **3/3** |
| AtlasCloud | 32/36 | $0.0355 | **3/3** |
| StreamLake | 33/36 | $0.0184 | 2/3 |

B4 was recorded for a year as the one genuine calibration gap, and as the
guide's fault rather than the serving's. It was the serving's. The rule §6.1
already stated — pin before you tune — was not merely a precondition for
calibrating; **it was the fix**. Before rewriting a prompt to chase a failing
sector, price the same sector on a better serving.

Note also the *direction* of failure tracks quality. Cheap servings fail by
under-classifying (seven to ten sectors here, the dangerous direction); capable
ones fail by over-classifying one or two, which is the safe direction and, per
convention 8, the waivable one.

**`unrecallable` is a separate axis from risk.** A signed rollout to 40,000
devices harms nobody and breaches nothing (so: `high`) and cannot be taken back
— so it sets `unrecallable: true` and earns one extra independent pass rather
than inflating `critical`.

### 6.7 The cost meter was broken, and every earlier figure was understated

`total_cost` accumulated only inside `PhaseRunner.run_ai`. Three paths bypassed
it: research (`research.py`), four `chat_json` sites in `context.py`, and
`rerank()` — whose cost was read into a **debug log and discarded**.

| run | old meter | true |
|---|---|---|
| 8-sector grounding | **$0.0025** | **$0.7366** (≈295×) |
| one full workflow | ~$0.057 | $0.1454 (2.6×) |

Search was **61%** of a full workflow and **98%** of a grounding run.
**Consequence for the new architect:** any cost figure in the git history before
commit `b4cd89f` is understated by 2.6×–295×. That includes a "$1.28 runaway"
(true ≈ $3.30) and a claim that sonar-pro cost "only 1.98× more" — which was
measured with a meter that did not count search at all and **should be
discarded**.

### 6.8 Bugs that only appeared in live multi-request sequences

Hundreds of passing unit tests missed all of these. It is the single most
important lesson about this codebase:

- Context was built **twice** per workflow (found by auditing README call counts).
- The rerank fallback latched on *any* exception, then made a doomed call every
  workflow forever.
- `except ValidationError` sat **below** `except ValueError`, which it subclasses
  — unreachable dead code, so every schema violation was logged as a parse
  failure.
- The schema retry **re-asked the identical prompt** with no hint of what was
  wrong. The rejection text already names the offending value and every
  permitted one.
- `_extract_json` stripped code fences by dropping the first line *positionally*;
  three real model shapes each cost a full retry and one parsed into a valid-but-
  meaningless `{':': ...}` dict.
- `lead_for_domain` validated a profile-declared lead against the shipped enum,
  so `legal_ops → paralegal` silently reviewed with the architect **and blamed
  the profile in the log**.
- `ReviewFinding.detail` was required, so a review using `issue` instead lost the
  **entire review** three times over, at the last phase, with the findings in hand.
- The eval suite was reading a developer's **local Chroma directory**: every gap
  came back pre-answered and not one test made a lookup.

**Therefore: live-test multi-request sequences. The unit suite is necessary and
nowhere near sufficient.**

---

## 7. FAST ORIENTATION FOR THE NEW ARCHITECT

```bash
cd ~/projects/autornd-os
.venv/bin/python3 -m pytest tests/ -q                    # 501 tests, ~9 s, free

# cheap live calibration — 108 calls, ~5-18 min, under 2 cents
.venv/bin/python3 -m autornd.evals.cli \
  --scenarios evals/scenarios/wide --workflow triage-classify \
  --repeat 3 --timeout 45 --max-spend 0.10

# factual accuracy vs published standards — 8 sectors, ~$0.17-0.72
.venv/bin/python3 -m autornd.evals.cli \
  --scenarios evals/grounding --workflow triage-only \
  --repeat 1 --timeout 240 --max-spend 0.30

uvicorn autornd.main:app --reload --port 8100            # API + dashboard
```

**Read these four files, in this order, to understand the system:**
`workflows/engineering-rnd.yaml` → `autornd/graph/spec.py` →
`autornd/engine/phases.py` (the risk guide especially) →
`autornd/routing/openrouter.py` (accounting, budgets, provider pinning).

**The single most important habit:** before changing a prompt or a constant,
read the comment beside it. It names the live run that set it, and probably a
previous attempt that failed.
