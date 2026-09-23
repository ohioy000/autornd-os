# AutoRnD-OS — Project State & Handover Document

**Repo:** `github.com/ohioy000/autornd-os` (public) · **HEAD:** `27e3e8f` · **Branch:** `main`
**Tests:** 959 as of `27e3e8f` · **Date of this snapshot:** 2026-09-22, counts and stamps re-derived against the tree at the sha above

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
WorkflowEngine.execute(request)                            engine/workflow.py
      │   resolves workflow_path(), owns the DB row and the status column,
      │   persists PhaseResult rows and writes episodic memory afterwards.
      │   THIS STEP WAS MISSING FROM THIS DIAGRAM until 2026-09-14, and a
      │   blueprint consequently ruled the module legacy and ordered it
      │   deleted. It is on the request path. tests/test_live_wiring.py pins it.
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
    phases.py            ★★ Every prompt lives here. Triage risk guide. ~900 lines
    review_composition.py ★ get_review_team(risk, domains, specialists)
    workflow.py          ★★ WorkflowEngine — the API's entry point, ON the request
                            path. It loads the graph, runs it, owns the DB row and
                            the status column, and writes episodic memory. The
                            hardcoded sequencer it used to carry as the graph's
                            equivalence reference is gone (251 lines): the graph
                            outgrew what a linear engine can represent. A blueprint
                            once ruled this module legacy and ordered it deleted —
                            see convention 19. tests/test_live_wiring.py pins it.
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
    routes.py               16 endpoints (§3.5); `/` dashboard is on main.py
    auth.py                 JWT + API key middleware
    templates/dashboard.html  single-file chat + workflows + settings UI

workflows/
  engineering-rnd.yaml   ★★ the flagship pipeline, 25 nodes, 3 loops (§3.1)
  lean.yaml                 10 nodes — cheaper variant, one loop
  triage-only.yaml          2 nodes — triage + grounding (research measurement)
  triage-classify.yaml   ★  1 node — triage alone. Exists so calibration costs
                            ~$0.00002/call instead of a full workflow.

evals/
  scenarios/*.yaml          17 core scenarios (default suite)
  scenarios/wide/*.yaml  ★  36 sector scenarios — OPT-IN (non-recursive glob)
  scenarios/convergence/ ★  4 B7 traces — the hardest shapes, all now terminating
  scenarios/materiality/    5 · scenarios/planprobe/ 3 · scenarios/probe/ 1
  grounding/*.yaml       ★  8 sectors graded against published figures

profiles/example.yaml       one of two tracked profiles (studio.yaml, §5)
tests/                      51 files, 959 tests (as of `27e3e8f`)
```

### 2.3 Key design patterns

**Workflow-as-data.** `graph/spec.py` defines three node kinds:

| kind | behaviour |
|---|---|
| `ai` | one or more model calls via `PhaseRunner._phase_<prompt>` |
| `check` | free deterministic function from `checks.registry` (five of them: `criteria_addressed`, `numbers_consistent`, `totals_reconcile`, `judges_agree`, `blocked_on_unmet`) |
| `gate` | boolean over prior outputs; `on_fail` names **either** a terminal status **or a node to route to** |

Node fields: `id, kind, depends_on, when, tier, tier_when, specialist, prompt,
schema, max_tokens, check, args, condition, on_fail, on_fail_reason, body,
until, max_iterations, on_exhausted, on_exhausted_status`.

A node with `body` is a **loop** over that sub-sequence until `until` holds or
`max_iterations` (which may *name a setting*, resolved at run time). **Every
loop must declare a bound at load time** — review and implement can disagree
indefinitely, and the graph can no longer express that.

**A gate may route instead of ending.** Before this, a blocking review was the
end of the run and its findings had nowhere to go: three traces in four
terminated there with the work unfixed and the diagnosis unread. `on_fail:
review_rework_loop` sends the work back through implement, validate and a fresh
review, and it ships only when every judge agrees. Routing reuses the loop
handoff path, so a closed gate and an exhausted loop reach a recovery sub-graph
the same way.

**Loop ownership, which is easy to trip over.** A loop **owns** the nodes in its
`body`, and ownership takes them off the top-level schedule — they run because
the loop runs them, never because their dependencies happened to be satisfied.
The same holds for a loop's `on_exhausted` target and for a gate's `on_fail`
target when it names a node. **This cost a real mistake:** adding `review` to a
rework loop's body *deleted the first review from the pipeline*, and took the
gate depending on it and the independent pass beyond that with it. The failure
mode is a silently shorter pipeline, not an error. A phase that must run both in
the main flow and inside a loop needs **two nodes** — same prompt, same tier,
two ids — because the scheduler distinguishes nodes, not phases. That is why
`review` and `rework_review` both exist.

**All judges must agree, not just the validator.** `judges_agree` folds every
judge a loop body produced — `implement.green`, `validate.green`,
`coverage.passed`, `consistency.passed` — into one boolean, and the build loop
exits on the fold rather than on validate alone. Measured once, and it only
takes one: the old exit let a run stop satisfied while the domain reviewer had
already flagged a critical concern and flipped the implementation red, and
validate turned out to be the judge that was wrong. `review_fold` folds the
build judges with the re-review the same way, so reworked work ships only when
both agree. The fold also records **which judge dissented**, per iteration.

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

**Verdict truth tables — derived fields are normalized, not demanded.** Two
schema rules, both bought by traces that died (conventions 20 and 21):

| field | rule |
|---|---|
| `green` (implement, validate) | `Optional[bool] = None`, resolved after construction: absent + a `red_cause` → `False`; absent + none → `True`; `True` *with* a cause → coerced `False` (a false red costs an iteration, a false green ships unchecked work); `False` with no cause → **raise**, because that is the one case losing information. `done` stays required — nothing in the verdict implies it. |
| `evidence` (validate) | a `{criterion: finding}` object folds to `"key: value"` lines, **natural-sorted** so `criterion_2` precedes `criterion_10` and a retry cannot change the answer. Non-text keys or values, or a part-string list, are refused with the accepted shapes named. |

`ReviewFinding` is the older instance of the same idea: a bare string becomes a
`detail`, and eight aliases are accepted for it, after a reviewer writing `issue`
lost three entire reviews at the last phase with the findings in hand.

**The instruments.** A run's JSONL unit record is the measurement surface, and
almost every entry in it exists because something was once unanswerable:

| instrument | what it answers |
|---|---|
| `rejections_by_tier` / `rejections_by_provider` | how often a reply is refused, and **by which serving** — a tier is served by up to a dozen |
| `normalised_by_kind` | which normalization fired: green derived, green overruled, or evidence folded |
| `seconds_by_phase` | where an expired run's clock went, without buying it again |
| `iterations[]` | every build-loop round: both verdicts, red causes, evidence, concerns, **which judge dissented**, and the spend delta |
| `tokens_by_tier` | prompt and completion tokens per tier — cost alone cannot separate "dearer" from "handed more to read" |
| `refused_lookups` | a zero score with refusals is a poisoned reading, not a bad model |
| `providers_by_function` | who served each tier; a suite that drops six sectors looks like a regression until you can see this |
| `ResultsLog` | append-per-unit JSONL, flushed immediately, with a header naming models, servings and caps |

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

### 3.1 `workflows/engineering-rnd.yaml` — the flagship pipeline (25 nodes)

**The file is the source of truth; this table is generated from it.** A
hand-copied YAML lived here for twelve blueprints and drifted — it still
showed a five-node build loop exiting on `validate.green` alone, two exits and
one loop after that stopped being true.

| node | kind | what it does |
|---|---|---|
| `triage` | ai | tier `triage`, → `TriageVerdict` |
| `context` | check | `build_context` (free) |
| `plan` | ai | tier `architecture`, as `systems_architect`, → `PlanVerdict` |
| `feasibility` | ai | tier `engineering`, as `assigned`, when `plan.ready == true` |
| `plan_ready` | gate | `plan.ready == true`; on_fail → `blocked` |
| `verify_grounding` | check | B13 override: one bundled lookup when the plan's criteria demand verifiability (free) |
| `implement` | ai | tier `engineering`, as `lead`, → `ImplementVerdict` |
| `blocked_check` | check | `blocked_on_unmet` over `implement.blocked_on` against `plan.success_criteria` (free) |
| `blocked_gate` | gate | `blocked_check.passed == true`; on_fail → `escalation`, reasoned "Implementation blocked on a criterion it cannot satisfy" |
| `blocked_terminal` | gate | the same condition inside the rework and recovery loops; on_fail → terminal `blocked`. A routing gate cannot go there; a terminal one can |
| `domain_review` | ai | tier `engineering`, as `peers`, when `implement.green == true` |
| `coverage` | check | `criteria_addressed` (free) |
| `consistency` | check | `numbers_consistent` (free) |
| `validate` | ai | tier `engineering`, as `test_engineer`, → `ValidateVerdict` |
| `judges` | check | `judges_agree` (free) |
| `build_loop` | loop | eight-node body, until `judges.passed == true`, max `max_iterations`, exhausted → `escalation` |
| `escalation` | ai | tier `escalation`, → `EscalationVerdict` |
| `recoverable` | gate | `not escalation.requires_human`; on_fail → `blocked` |
| `recovery_loop` | loop | until `review_fold.passed == true`, max `escalation_recovery_attempts`, exhausted ⇒ `escalated` |
| `review` | ai | tier `engineering`, as `reviewers`, → `ReviewVerdict` |
| `review_clean` | gate | `review.ship == true`; on_fail → `review_rework_loop` |
| `rework_review` | ai | tier `engineering`, as `reviewers`, → `ReviewVerdict` |
| `review_fold` | check | `judges_agree` (free) |
| `review_rework_loop` | loop | until `review_fold.passed == true`, max `review_rework_attempts`, exhausted → `escalation` |
| `independent_check` | ai | tier `independent`, → `DoubleCheckVerdict`, when `triage.unrecallable` |

**Three loops, and two of them share a body.** `recovery_loop` and
`review_rework_loop` run the identical eight-node body — `implement`,
`domain_review`, `coverage`, `consistency`, `validate`, `judges`,
`rework_review`, `review_fold` — because work sent back by a blocked review and
work resumed after a recoverable escalation need the same treatment. They are
separate nodes because a loop owns its body (§2.3), and `review` must still run
once on the main schedule.

**`build_loop`'s body is eight nodes and not the same eight.** It carries
`blocked_check` and `blocked_gate` after `implement`: `implement`,
`blocked_check`, `blocked_gate`, `domain_review`, `coverage`, `consistency`,
`validate`, `judges`.

**The two gates differ in what they do, and that is the ruling.** The *routing*
gate is build-only and stays that way — inside the rework and recovery loops it
would re-enter the escalation sub-graph with a fresh iteration budget each time,
which is unbounded, and the workflow file has recorded that rationale since the
gate landed. What those two loops now carry instead is `blocked_terminal`: the
same free check, a gate that **ends** the run `blocked`. A terminal gate has no
re-entry to bound, so the objection does not reach it.

**Why it was added, found by reading rather than from a trace.** `blocked_check`
is the only thing in the graph that reads `blocked_on` independently of `green`,
and validate's failure-log write is guarded on the iteration being red. So an
implementation that came back **green while naming a criterion it could not
satisfy** recorded nothing and met no gate in rework or recovery: the fold saw
four green judges, the loop converged, and the work **shipped carrying the
refusal**. There is no trace of this, because the run it produces reports
`completed` — which is why it is stated here as a reading, with
`tests/test_blocked_on.py::TestTheGreenButBlockedGap` simulating it end to end
(convention 22).

**The loop asymmetry ended 2026-09-20.** The owner overruled the advisor's
2026-09-19 ruling directly; both loops carry `blocked_terminal` now, ending the
run `blocked` rather than shipping a green-but-blocked conclusion. The design is
advisor-ratified on the merits, and the full record — including two claims of
the original ruling recorded as wrong — is §27.3 of the notebook.

**Reading the shape in one line:** triage → ground → plan → *gate* → verify
grounding on demand → build until every judge agrees → escalate if it never
does → *gate* on recoverable → review → *gate* on clean → rework until review
and build both pass → independent pass on unrecallable work.


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
ImplementVerdict  done (REQUIRED) · green: bool|None · red_cause: str|None
                  iteration: Field(ge=1) · summary · domain_concerns: list[str]
                  # green is resolved from red_cause after construction — the
                  # truth table in §2.3. `done` stays required: nothing in the
                  # verdict implies it (convention 20).
ValidateVerdict   green: bool|None · red_cause: str|None · evidence: list[str]
                  # same green truth table; `evidence` accepts a criterion-keyed
                  # object and folds it to "key: value" lines (convention 21)
ReviewFinding     lens="unknown" · severity="medium" · detail=""
                  # model_validator(before) accepts a bare string, or detail under
                  # issue/description/finding/concern/text/problem/note/summary/message
ReviewVerdict     ship: bool · findings: list[ReviewFinding] · verdict: str
                  # field_validator(before) drops entirely-empty findings
DoubleCheckVerdict ship · confidence · critical_issues[] · recommendations[] · verdict
EscalationVerdict root_cause_analysis · resolution_directive · requires_human
                  architectural_correction: str|None
                  # requires_human=False routes to recovery_loop, not to blocked
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
MODEL_PREMIUM=                       # optional. Two consumers, two behaviours:
                                     #   graph `independent_check` falls back to
                                     #   architecture (never to engineering — a
                                     #   review by the model under review is not a
                                     #   second opinion, `independent_model()`);
                                     #   the dashboard Double Check button 404s and
                                     #   does not appear (`api/routes.py:287,313`).

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

### 3.7 Test distribution (959 total, as of `27e3e8f`)

| file | n | file | n |
|---|---|---|---|
| test_graph.py | 83 | test_structural_roles.py | 13 |
| test_evals.py | 73 | test_budget_transparency.py | 11 |
| test_routing.py | 62 | test_citation_demand.py | 11 |
| test_verdicts.py | 42 | test_guards_can_fail.py | 11 |
| test_knowledge.py | 41 | test_handover_truth.py | 11 |
| test_research.py | 37 | test_specialists.py | 11 |
| test_review_composition.py | 28 | test_results_log.py | 10 |
| test_blocked_on.py | 26 | test_triage.py | 10 |
| test_profiles.py | 23 | test_docs.py | 9 |
| test_settings.py | 22 | test_lead_review.py | 9 |
| test_api.py | 21 | test_rate_limit_retry.py | 8 |
| test_sweep_budget.py | 21 | test_doc_corpora.py | 7 |
| test_preflight.py | 20 | test_live_wiring.py | 7 |
| test_protocol_file.py | 20 | test_rejection_counter.py | 7 |
| test_rework_loop.py | 17 | test_serving_ledger.py | 7 |
| test_auth.py | 16 | test_trace_durability.py | 7 |
| test_coverage_shapes.py | 16 | test_engine.py | 6 |
| test_green_resolution.py | 16 | test_preregistration_precedence.py | 6 |
| test_all_judges_exit.py | 15 | test_budget_stop_scoring.py | 5 |
| test_repeat_and_fit_rule.py | 15 | test_iteration_dissent.py | 5 |
| test_schema_wiring.py | 15 | test_handoff_scheduler.py | 4 |
| test_shipped_examples.py | 15 | test_workflow.py | 4 |
| test_terminal_on_bound.py | 15 | test_phase_timing.py | 3 |
| test_evidence_shape.py | 14 | — |  |

Regenerate with `pytest tests/ --collect-only -q`; the total is the part that
matters and `tests/test_docs.py` fails if the README badge disagrees with it.

---

## 4. ACTIVE CONTEXT & WORKING MEMORY

### 4.1 Where the project stands

**The flagship loop is finished.** B7 — *"the build loop does not converge on
complex requests"*, the oldest open problem here — closed on 2026-09-15. All
four convergence traces terminate in ship or escalated-with-diagnosis. What
closed it was not a loop change but pinning the last unpinned tier; §6.9 has the
ledger of the six names it carried on the way, and why five of them pointed at
the wrong layer.

**Thirteen blueprints have run through `docs/handover-review.md` §7–§22**, 92
commits from `641da5a`. An advisor writes each blueprint; this repo executes it,
pastes it verbatim before doing anything, and appends an execution record
afterwards naming departures, what was deliberately left undone, and what
execution found that the blueprint missed. **That last section is where most of
the value landed** — six blueprints found the instrument broken rather than the
hypothesis wrong.

The arc, in one line each:

| # | what it bought |
|---|---|
| 001–003 | packaging (three faults, not one), a documentation truth pass, a sweep-level spend cap |
| 004–005 | three free closures; the triage tier pinned; B4 reframed — *the serving, not the guide* |
| 006–007 | the instrument repaired: schemas wired into the retry, a provider message carried out of a 403 |
| 008–009 | the all-judges exit; review's findings given a consumer via gate routing |
| 010–011 | the clock instrumented; `green` resolved from `red_cause`; three broken instruments found |
| 012 | the `engineering` serving pinned; **B7 closed**; convergence-rate discovered |
| 013 | this consolidation |

**The frontier has moved.** Calibration, cost and convergence are maintenance
now. What is open is product: generalization beyond engineering, the human
surface, and the tiers nobody has measured. §5.

### 4.2 Known bugs, blockers and failing tests

**No failing unit tests — 959/959 pass.** Everything below is a live-behaviour
or design issue. **Closed items stay in the table with their resolution**: the
ledger is most of this section's value, and three of the entries below were
closed by discovering the premise was wrong rather than by fixing what was
named.

| # | Issue | Severity | Notes |
|---|---|---|---|
| B1 | Packaging metadata was unusable | **RESOLVED** | Not one fault but three, and the trivial one was the least of them. `pyjwt` was missing from `pyproject.toml`; flat-layout discovery saw `evals/ profiles/ workflows/` beside `autornd/` and **failed the build**, so `pip install -e .` never reached the ImportError; and no wheel carried `dashboard.html`, so a built install served FileNotFoundError from the dashboard route. One manifest now, plus a CI job that installs from it. |
| B2 | ~~Materiality gate is ineffective~~ | **RESOLVED — it is not a cost lever, and does not need to be** | The finding stands: it never returns empty. But work whose gaps are immaterial reads `low`, and the risk gate already zeroes its lookups — measured 12/12 across six probe designs. The cap of three earns its place as a *question-count* limit protecting per-question tokens (§6.3: truncation, not ignorance). A per-gap reframe was tried and reverted: it zeroed a **material** lookup. §12.5 |
| B3 | ~~`--max-spend` is per scenario, not per sweep~~ | **RESOLVED** | `--max-spend-sweep` bounds the whole invocation — every scenario, repetition and compared workflow against one budget. Defaults to $1.00, `none` disables. With both caps set no unit starts unless it must fit, so the sweep cap is exact; alone, it stops the crossing unit via the existing client ceiling. Fixing it exposed a second bug: six handlers on the research and rerank paths swallowed `BudgetExceeded`, so an abort did not stop the run |
| B4 | ~~`wide_legal_ops` under-classifies on every provider~~ | **RESOLVED — the premise was wrong** | It is the serving, not the guide. Pinned six ways: fails 3/3 on OpenInference, DigitalOcean and unpinned; passes 3/3 on Alibaba and AtlasCloud, 2/3 on StreamLake. Under the adopted `triage:Alibaba` pin it passes ~8/9, and its rare excursions go in **both** directions. No guide edit was made — there was no systematic failure left to target. §12.3, §12.4 |
| B5 | `wide_wind_energy` fails `risk_at_least` ~1/3, **deliberately left red** | low | Two defensible readings; a risk **floor must never be waivable** (§4.4) |
| B6 | ~~`independent_check` has never executed inside a full live workflow~~ | **RESOLVED — observed 2026-09-14** | Ran end to end on `independent-check-probe`: 10 calls, 54s, $0.0212, returning `ship=true, confidence=high, critical_issues=[]`. Trace at `docs/traces/b6-independent-check.json`. Took seven further attempts; every exit was legitimate and the *probe request* was what kept failing — see §13.4 |
| B7 | ~~Build loop convergence~~ | **RESOLVED 2026-09-15 — and the sixth name was the right one** | Closed on 010's criterion: all four convergence traces terminate in ship or escalated-with-diagnosis. `derived_tolerances` and `numeric_consistency` **shipped** in 299 s and 182 s; `crossref_integrity` and `requires_execution` **escalated with a root cause and a directive**. What closed it was not a loop change — it was pinning the last unpinned tier. The win is **iterations, not seconds**: 8 → 2 and 4 → 1, while per-call latency moved only from a 67 s median to 41 s. **A serving does not only run at a speed, it converges at a rate** — B4's finding in the place nobody had looked. Read `§6.9` for the ledger of six names and what each one cost. **Closure means the loop terminates honestly under a compliant pinned serving, on one observation per trace** — not that it is reliable; `crossref_integrity` produced three different outcomes in three runs and is the standing reason to distrust n=1. §20.1 |
| B8 | Shipped-default models fail on hard requests | medium | Documented rather than changed, per owner's instruction. §6.4. **The plan-tier burn is request-driven, not serving-driven** (measured 2026-09-14, n=2 servings × 12 easy plans vs 6 servings × 4 hard ones): the same model burned seven retries on the hard set and none on the easy one. Pinning that tier is not the lever; the candidates are the plan token budget — the burn sits at `Specialist.run`'s default 16,384 while every serving advertises a ceiling above 262,000 — or the model. **The budget is now a setting** — `PLAN_MAX_TOKENS`, default 32,768 (§16) — so that half is tunable without code; the model remains the owner's. |
| B9 | No DB migrations (no Alembic) | low | Schema changes are destructive |
| B13 | ~~The risk gate governs lookups; the success criteria govern what must be verified; nothing reconciles them~~ | **CLOSED (advisor, 2026-09-20)** | Closed on the registered contrast, **n=1 each side**. **Pre-fix:** 43 calls into the cost ceiling with invented citations (§24.1(f), `b14-gen_marketing_claims.jsonl`). **Post-fix:** 22 calls, **$0.0569**, 539.7 s, an honest `blocked` terminal, claims **labelled unsourced**, the engineering pin held to termination (`b16-e1-marketing-claims-registered.jsonl`), and the scenario **scored a pass for the refusal**. **E2:** zero search spend at `low` risk, **n=2** — the risk gate's zero-lookup is *correct behaviour*, not the defect. Mechanism deterministic under test (`tests/test_blocked_on.py`, its `TestTheGreenButBlockedGap` and exhaustion companion). **Wild `blocked_on` frequency: unmeasured, open in §6.** The n resolution: the 2026-09-20 amendment's `n=1` counted scenarios, not repetitions; the registered `--repeat 2` stands. What 016 did **not** fix is B15. |
| B14 | ~~Two literal engineering roles are injected regardless of profile~~ | **CLOSED (owner-ruled, 2026-09-21)** | The two structural slots — *who checks the work* and *who holds the system-level view* — are declared by the profile (`structural_roles.checks_work`, `.holds_system_view`) and resolved at both injection sites. **The rules are unchanged**; only their operands moved. **Undeclared resolves to the shipped engineering roles, so every engineering project behaves byte-identically** — 4 regression guards pin that, and they pass against the pre-B14 code as well as after it, while 9 feature tests fail before and pass after (`tests/test_structural_roles.py`, checked by reverting the source). `profiles/studio.yaml` declares `editor` and `strategist`: a high-risk content brief is now reviewed by copywriter, editor and strategist rather than by a test engineer and a systems architect. **The Pydantic bypass is fixed in the same change** (recorded unfixed since §26 and deferred here): injected roles are normalised `str`, not enum members. **A non-engineering corpus now exists** — `docs/meridian_studio/`, whose three domains (`brand_strategy`, `copywriting`, `seo_analytics`) are **none of them shipped enum members**, guarded by `tests/test_doc_corpora.py`. **Still not validated on a live run**: the corpus is in place and unin­gested, so the demonstration is now a scheduling question rather than a missing artifact. **Demonstrated live, n=1** (2026-09-21, `b14-demo-marketing-claims-grounded.jsonl`, pre-registered before spend): triage staffed `['strategist', 'copywriter', 'fact_checker']` — no shipped engineering structural role anywhere in the run. The boundary claim is **observed, not asserted**. Confounded with grounding by design, as the pre-registration declared. **Two of the run's predictions failed and are recorded as failed:** B14-3 — the run reached **no terminal**, 42 calls against a 41-call ceiling; and C1 — **$0.1783** against a $0.15 budget and $0.0569 for the ungrounded comparator. **Completion pointer:** B14-3 is blocked by **B17** (design: §29, Blueprint 018) and is retried by `ARCH-20260922-006`. See §28 for the arc's record. See B15, which this closure does not touch. |
| B15 | **Draft-level invention persists beyond plan-demanded citations** | medium | Measured 2026-09-20 on E1's registered run. The implementer **labelled all three proof points unsourced** rather than inventing citations — B13's fix working — and in the same draft **invented a product name, 'ExpenseFlow', and presented it as fact rather than flagging it as an assumption** (escalation's autopsy, `b16-e1-marketing-claims-registered.jsonl`). 016's honest-refusal channel governs **what the plan demands citations for**, and nothing else a draft might invent. **Status: OPEN.** **Disposition (advisor, 2026-09-22): the 2026-09-20 fold-into-B14 ruling is SUPERSEDED.** It read *folds into B14's generalization design — the honesty question one level above citations; the fix lives where drafts are composed and reviewed; no standalone arc.* B14 closed without the fold, so the ruling is now false of events, and convention 7 applies to the advisor exactly as it applies to the executor. **B15 stands OPEN as its own row.** **First live evidence (2026-09-21, `b14-demo-marketing-claims-grounded.jsonl`, n=1, confounded):** grounding moves **name-invention** — B15-1 confirmed, the draft carried an Assumptions section where the comparator invented 'ExpenseFlow' and stated it as fact — and does **not** move **citation-invention** — B15-2 failed, the proof points carry firms the escalation autopsy names as invented. **The asymmetry is the finding:** documentation-in-grounding is insufficient for citations, and the fix must reach the **citation/verification channel**, not the composition channel alone. |
| B16 | **Plan success criteria are rewritten from scratch on every run of the same scenario** | **property, not defect** | **RULED (advisor, 2026-09-22) — this is the system working, and no fix is pending.** The row is kept in the ledger because the *consequence* is load-bearing, not because anything is owed. See "The ruling" at the end of this row; everything before it is the measurement as it was taken. **OPEN (advisor, 2026-09-20), superseded by that ruling:** Across **4** committed plan outputs of the identical `gen_marketing_claims` request the criteria were **6, 6, 6 and 5**, each differently worded. B13/016's mechanism keys on *what the plan demands* — `verify_grounding` reads `plan.success_criteria`, and `deferred_gaps` varied **3, 0, 0, 0** across these runs — so the citation-demand pathway's **input is not stable run-to-run**. A reproducibility caveat on 016's registered contrast, which B13's row already states at n=1 each side. **No fix ruled:** the variance is inherent to a generated plan, and the mechanism held across all four (`demanded` true 4/4, zero demand-missed — `ARCH-20260920-004`). Disposition: feeds B14's design — demand-detection must tolerate criteria variance, and any future pre-registered multi-run contrast carries its per-run criteria counts as **run variables**. **Rider (advisor, 2026-09-22):** the zero-deferred-gaps question is an **open sub-question of this row** — why the grounding phase deferred no blocking gap on plans that demanded citations (`deferred_gaps` 3/0/0/0, `ARCH-20260920-010`). Detection fired 4/4; what varied was what it handed downstream, and nothing has explained it. **This rider is NOT closed by the 2026-09-22 ruling** — it is a question about `deferred_gaps`, not about criteria variance, and it stays open. **The sharpest measurement, 2026-09-22 (§34.4, `ARCH-20260922-023`).** The *same* criterion, conceptually, across two runs of the identical request: `ARCH-20260922-010`'s *"a core promise of exactly one sentence with no subordinate clauses, and two to four supporting pillars that are each defensible without reference to another pillar"* scored **0.63 and passed**; 2026-09-22's *"a core promise expressed as a single sentence with no subordinate clauses, and each supporting pillar is independently defensible"* scored **0.43 and failed**. **Nothing about the check changed between them. A rewording moved a criterion across the 0.50 threshold and decided the run.** Recorded as it read, not softened: the first run shipped that criterion, the second died on it. Traces: `docs/traces/b14-rerun-2-marketing-claims.jsonl` (the 0.43 run, which survived); the 0.63 comparator is in `docs/handover-review.md` §34.4, its own trace having been destroyed by executor error (§29.2). **The ruling (advisor, 2026-09-22).** **The regeneration is a property of the system working, not a defect.** The plan adapts to the objective it was given; that adaptation is what grounding buys, and freezing the criteria would defeat it. **The obligation is visibility, not stability.** Nothing is owed here in the form of a fix, and **making criteria deterministic is explicitly rejected** — that would be the defect, not the cure. **The operational consequence, which is the part that binds.** Convention 27 is the governing rule: *a repetition of a plan-dependent contrast is a second sample, never a confirmation.* It follows that **a pass rate across runs with different criteria is not a rate**. Any comparison must state that the criteria differ, and the criteria must be quotable from the run record. **The visibility half is already done** — `ARCH-20260922-008` records the criteria count and the per-criterion shape in every unit record, so the criteria *are* quotable. **The remaining obligation is the reader's: do not aggregate across differing criteria.** **Named downstream consumer (found 2026-09-22 while answering this ruling's own question).** `RepeatedRun.rate` (`autornd/evals/runner.py:757`) is `passes / applicable` over the repetitions of one scenario, and its class docstring states *"the unit of measurement is a pass rate"*. For a plan-dependent scenario, `--repeat N` produces N runs whose criteria were each written fresh, and `rate` presents them as one number with nothing saying the denominators differ. **Reported, not fixed** — this command's scope is documentation, and whether that display is a defect or acceptable with a caveat is a ruling. It is raised in `.orchestration/responses/ARCH-20260922-028.response.json`. **RULED (advisor, 2026-09-22, §37) — the display is acceptable as-is.** The type cannot distinguish plan-dependent from plan-independent scenarios. The obligation is the docstring, not the code: `RepeatedRun`'s docstring must state that for plan-dependent scenarios the criteria may differ across runs. Convention 27 governs the reader. No code change required. |
| B17 | ~~`criteria_addressed` cannot read a criterion whose satisfaction is an absence~~ | **CLOSED (2026-09-22)** | Measured 2026-09-21 on the B14 demonstration (`b14-demo-marketing-claims-grounded.jsonl`). The check is term overlap — at least 50% of a criterion's significant terms must appear in the implementation — and it **failed the same two criteria on all seven iterations** while `implement.green` was true throughout. The run never terminated; it exhausted the 41-call ceiling at 42 calls and $0.1783, **three times the ungrounded comparator's cost for a worse outcome**. Nothing refused and nothing was wrong with the work: **the loop died because a free check could not see that the work was done.** **The mechanism.** Criterion 6 read *"avoids the banned words ('leverage', 'seamless', 'robust', 'in today's fast-paced world')"*. **Six of its seventeen significant terms are words the criterion forbids the draft to contain**, capping a perfectly compliant draft at 65% and scoring it 40%; eight more are meta-vocabulary about the rule (`avoids`, `banned`, `conventions`). **14 of 17 terms are unreachable for a compliant draft — satisfying the criterion is what makes it fail the check.** Criterion 3 fails more mildly (37%) for the second class: `author`, `organization`, `date`, `location` describe what a citation *is*, not words a citation *contains*, and the draft's citations were complete. **Why it surfaced now, and it is not a regression.** The check's docstring is honest — *term overlap, not comprehension* — and it works on engineering criteria, where the compliant artifact contains the words. `docs/meridian_studio/` made the plan's criteria **prohibition-shaped and form-shaped**, because that is what an editorial house style is. **The coverage death is a direct consequence of the corpus working** (B14, B15-1). **VALIDATED IN PART, 2026-09-22 (§34).** Two units, $0.2530, both reaching a typed terminal. **The form branch is demonstrated live**: a citation-fields criterion abstained in both units and did not fail the fold, where its `-010` equivalent scored 0.37 and killed the run. **The prohibition branch is NOT demonstrated** — neither regenerated plan emitted a prohibition criterion, so the inversion had nothing to act on and remains proved by fixtures alone. The loop still exhausted, but now **because a `presence` criterion scored 0.43 against a 0.50 threshold**, which is term overlap behaving as designed rather than being blind. Coverage passed on 2 of 7 and 2 of 5 iterations, where `-010`'s failed all seven. **A fourth shape is exhibited (n=1):** *"a single sentence with no subordinate clauses"* and *"independently defensible"* are satisfied by how prose READS, not by what it contains — prohibition-in-meaning with no quoted token list, so the fail-safe rule sends it to `presence` and it fails there. **Status: OPEN, and it is a ruling** — any fix changes what the harness concludes about whether work is done. Recorded, not designed: two classes need different treatment, and a threshold change alone would trade this failure for the drift the check was built to catch. Interacts with B16: the criteria are regenerated per run, so the check's input is unstable as well as ill-suited. **RULED 2026-09-22 — B17-R1, §29:** shape selects the test. Presence keeps term overlap unchanged; **prohibition inverts** — the criterion's own forbidden tokens become the test, pass iff none appear; **form abstains**, never failing the fold and never silently. The fail-safe direction is presence, because abstention is leniency and convention 21 says exhibits precede leniency. Implementation `ARCH-20260922-008`; paid validation `ARCH-20260922-010`. **`ARCH-20260922-006`'s retry of the B14 demonstration was blocked on this ruling and is superseded by `-010`;** the unexecuted Blueprint 018 design is superseded by §29.2, which names the one place the two contradict. **Implemented by `ARCH-20260922-008`; validation ATTEMPTED and only partly readable** — `ARCH-20260922-010` ran at **$0.1547** and its trace was destroyed by executor error (§29.2). What survives proves the classifier fired on a live plan: *"3 of 5 **measurable** success criteria"* — six criteria, five measured, **one abstained on shape**. The run did **not** converge (0/2), so the pathway is not yet demonstrated end to end and B17 stays OPEN. §29.1(7)'s Phase 2 trigger requires classification misfiring *evidenced in a committed trace*, and there is no committed trace, so it has **not** fired. **THAT TRIGGER HAS NOW FIRED — `ARCH-20260922-027`, 2026-09-22, `docs/traces/b17-prohibition-branch.jsonl`.** On a scenario engineered to produce one, **the planner emitted a prohibition criterion with an explicit quoted token list and the classifier called it `presence`.** The criterion: *"The copy contains no instances of 'leverage', 'seamless', 'robust', or 'in today's fast-paced world'."* **The draft was 401 words and contained none of the four** — verified against the committed trace — and coverage scored it **0.00, "0% of its terms appear"**, because the only significant terms it has are the words it forbids. **This is B17's original mechanism reproduced exactly, with B17-R1's repair merged and not firing.** **The form branch did not fire either.** *"The total word count is between 350 and 450 words"* is satisfied by a property of the text, not by containing words; it was classified `presence` and scored **0.00** against a draft of exactly 401 words. **All 6 of 6 criteria were classified `presence`, `abstained` is empty, and coverage was the dissenting judge on all 6 iterations while `implement.green` was true throughout** — the same signature as `-010`. **Prediction scoring (registered at `0e61119`, unedited): (a) HELD** — a prohibition-shaped criterion was emitted, though worded *"contains no instances of"* rather than the predicted *"avoids the banned words"*, which is **B16 in the act of deciding an outcome**; **(b) REFUTED** — classified `presence`, not `prohibition`; **(c) NOT SCORABLE as a test of the inversion** because the branch never ran, and what was observed instead is that a **compliant draft failed at 0%**; **(d) not reached, as declared at registration.** **The run cost $0.0434 of a $0.25 cap and was bound by TIME, not money** — it timed out at 1200s, with `validate` taking **724s of the 1200**. **Whether this is a check defect or an input-phrasing issue is a ruling and is NOT repaired here** — `ARCH-20260922-027` reports it as its registered question. **RULED B17-R3 (advisor, 2026-09-22, §36) — check defect, not input-phrasing.** The planner describes what work must do; the classifier must recognise what the planner wrote. Bounded by -032: the corpus justifies broadening recall (-033), not a different mechanism. B17 closure requires a live draft containing a banned token, not just fixtures. **RULED B17-R2'(a)/(b)/(c) (advisor, 2026-09-22, §38):** recall is corpus-derived (R2'(a), specification for -033); doubt is a detected state with a four-clause predicate (R2'(b), specification for -034); abstention is agreement in the fold (R2'(c)). **CLOSED by ARCH-20260922-041 replay (2026-09-22).** Replayed the committed -027 criteria (`docs/traces/b17-prohibition-branch.jsonl`) through the repaired classifier: (1) criterion 1 classifies PROHIBITION; (2) all four tokens extracted verbatim: `['leverage', 'seamless', 'robust', "in today's fast-paced world"]`; (3) the committed 401-word compliant draft passes criterion 1. Criterion 3 (`between 350 and 450 words`) classifies FORM under clause (iii), abstaining rather than failing. The fail direction remains fixture-covered per Ruling D6 (`tests/test_prohibition_phrasing.py::TestB17ClosureReplay`, 3 tests, convention 22). **Limitation:** n=1 on phrasing (the -027 draw). This demonstrates the branch is reachable on live planner output; it does not measure recall across phrasings — the corpus in -031 measures that. |
| B18 | ~~A run stopped by a bound produces no terminal status~~ | **CLOSED (2026-09-22)** | Opened 2026-09-22 from the B14 demonstration (`b14-demo-marketing-claims-grounded.jsonl`). The unit's `status` is the **empty string** while `error` carries *"stopped at 42 model calls (ceiling 41); raise max_calls on the scenario if this is expected"* with a per-tier breakdown. **Read precisely, because the instrument is better than the headline suggests** (convention 18): the bound *is* named, and named well. What is missing is the **typed terminal** — nothing in the verdict set says the run ended, so a consumer reading `status` sees a run that neither finished nor stopped. README §1 promises the system *"either finishes or tells you exactly what stopped it"*; on this path it does the second in prose and neither in type. **This is a product defect, not an instrument defect, and it is independent of B17** — B17 explains why the ceiling was reached; B18 is that reaching it produced no status. Unmeasured: whether the stop happened inside the workflow or in the eval runner, and whether a ceiling-stopped run should persist as `blocked` or `escalated` (that second question is a ruling, not an implementation choice). **CLOSED by `ARCH-20260922-009`.** The gap was in the eval runner alone — `engine/workflow.py` already persisted `WorkflowStatus.BLOCKED` for the same exception, so **production never had this defect** and the open ruling question answered itself: `blocked` is what the harness already concludes. Four bounds now name themselves — call ceiling, spend ceiling, deadline, unhandled error — and loop exhaustion appends the dissenting judges. **Not yet observed live:** `ARCH-20260922-010`'s trace was destroyed by executor error before its status field could be read (§29.2), so the repair is proved by `tests/test_terminal_on_bound.py` and by nothing else. |
| B19 | ~~`--repeat N` reports exhaustion before the sample is complete~~ | **CLOSED (2026-09-22) — not the defect it looked like** | Measured 2026-09-22 on the B17-R1 validation. `--repeat 2` produced **one unit** and the sweep reported *"exhausted after 1 of 2 units"* at **$0.1547 against a $0.50 cap — 31%**. That is not exhaustion. Half the registered sample was lost and nothing asked for it. **Unresolved which**: the per-unit ceiling binding where the sweep ceiling did not, or the accounting being wrong. The distinction matters — if the cap is per session a repeat of 2 *can* legitimately stop after one, and then the defect is the message rather than the arithmetic. **RESOLVED by `ARCH-20260922-021`, and the repeat logic was never wrong.** The unit was skipped by the **fit rule**, documented on `SweepBudget` since it was written: with a $0.50 per-unit cap and $0.3453 remaining, no unit could be *guaranteed* to fit, which is the conservative behaviour that rule exists to provide. **Three real defects sat behind the wrong word.** (1) **The message.** `skip()` and the summary line both called a fit-rule decline an *exhaustion*; they now name which of the two happened and report produced-versus-requested separately. (2) **The registration was arithmetically impossible and nothing said so.** `--max-spend 0.50 --max-spend-sweep 0.50 --repeat 2` needs $1.00 of a $0.50 sweep, so **exactly one unit could ever start**; a free pre-spend check now warns before the first call. (3) **`ScenarioRun.skipped` was decided by substring-matching the error message** against `("not applicable", "sweep budget exhausted")` — control flow reading English, against non-negotiable 3. Correcting the message *broke it*: a skipped unit silently began counting as one that **ran**, which would have inflated the denominator of every pass rate in any sweep that hit its cap. Caught by an existing test, inside the change that caused it; it is now a typed flag set where the skip is decided. **Two of this repo's own tests had enshrined the wrong wording** and were corrected under convention 17 — one asserted *"sweep budget exhausted"* for a budget with $0.10 of $0.60 still in it. |
| B20 | ~~A paid run's records do not survive a concurrent git operation~~ | **CLOSED (2026-09-22)** | Measured 2026-09-22 (§32). `git stash -u` during a live run took the directory entry of the untracked results file while the writer held the inode; **every completed unit record was written to a deleted file**. $0.1547 spent, record unrecoverable, only the header surviving. The executor caused it, and the harness made it possible: records are held open for the run's duration rather than flushed per unit, and `docs/traces/` is untracked rather than ignored, so a routine `stash -u` reaches it. **CLOSED by `ARCH-20260922-022`, and two of the three things this row originally said were wrong.** **(1) Flushing was never the problem.** `ResultsLog._write` has flushed per record since it was written; flushing does not help once the directory entry is gone, which is the entire mechanism. **(2) Ignoring `docs/traces/` is not the fix.** It is **tracked** — 60 committed files — and it *is* the evidence model. The default results path `evals/results/` is **already git-ignored and was never exposed**: `stash -u` takes untracked files, not ignored ones. The loss happened because `--results-file` aimed at the one directory that is tracked, where a brand-new file is untracked until committed. **The repair is a mirror outside the working tree**, written and flushed alongside the primary, chosen by hazard rather than by habit — no mirror for an ignored path or one outside any repo. The CLI names it, because a silent protection is an instrument asserting durability it never mentioned (convention 28). Proved by reproducing the loss: unlink the file mid-write, keep writing, and assert the mirror holds every record. **What it does not protect against, stated rather than implied:** `git stash -a`, deletion of the state directory, filesystem loss, and a `kill -9` between two records. |
| B21 | **Guards that never found their subject and reported success** | **high** | Four instances in one day, plus two older ones now recognised as the same class (§33.2). The sharpest: the provenance stamp guard's regex used `\s*` between label and sha where the document has `**HEAD:**`, so `findall` returned `[]` and **all three deliberate break attempts passed**. The older two: the serving ledger's three-tier table with no escalation row, and CI asserting nothing-is-wrong for 87 hours without computing state. **Convention 28 is the ruling**; this row tracks the outstanding repairs. **Status: OPEN.** Repairs: `ARCH-20260922-020` (the four guards — and its executable form found **four more**, two of them the morning's own fix applied to one instance of three); **`ARCH-20260922-024` — DONE:** the serving ledger now enumerates every tier a trace header names and gives each an explicit status, so **`escalation` has rows for the first time** — seven rotated arms over 17 units, and `research`, `search`, `ranker` and `premium` all appear. Pinned numbers are unchanged, guarded by a test. CI was repaired by `-013`. |
| B23 | ~~An empty rejection count could not be told from an uncounted retry class~~ | **CLOSED (2026-09-22)** | Measured on the B17 prohibition run (`ARCH-20260922-027`). Stderr carried **three retry events** — *"JSON parse failed (attempt 1/3) for engineering: Unterminated string starting at: line 7 column 14"*, and twice *"Empty reply for engineering: model returned no text (provider=GMICloud, finish_reason=None | error)"* — while **both `rejections_by_tier` and `rejections_by_provider` were empty** in the unit record. **The counters were RIGHT, and were not widened.** `chat_json` has three retry paths and only the `ValidationError` branch increments them, by design: the counter's own comment defines a rejection as *a reply the truth table could not repair*, which an empty reply is not, and `normalised_verdicts` is read against it as a pair. Widening would have destroyed that distinction. **The defect was the REPORT** — a reader seeing `rejections_by_tier: {}` beside 23 calls cannot tell *"nothing was refused"* from *"the refusals were a class this does not count"*, and **convention 26 makes that the instrument's defect rather than the reader's error**. **Repaired by `ARCH-20260922-030`:** every retry is now counted by class, and the unit record carries a `retries` reconciliation — `total`, `attributed`, `unattributed`, `by_kind`, and the excluded classes **named in the report** so nobody has to open `openrouter.py` to learn what an empty count excludes. Per **convention 28** the total is stated before the breakdown and **`unattributed` is present even when zero**, because an absent field and a measured zero are different claims and only one is evidence. Proved by breaking it: the stderr is committed at `docs/traces/b17-prohibition-branch-STDERR.txt`, and `tests/test_retry_reconciliation.py` simulates each of the three classes end to end (convention 22). Instrument repair, not a behaviour change — no retry logic moved. **The same caveat applies to coverage extractions** (`ARCH-20260922-035`): new traces carry the extracted terms and forbidden tokens per criterion so a reader can verify the score; traces predating `-035` carry the score alone. A reader comparing old to new should not mistake a missing `extractions` field for "nothing was extracted". |
| B24 | ~~A possessive or an unquoted aside became a forbidden token~~ | **CLOSED IN PART (2026-09-22)** | Found by `ARCH-20260922-031` while measuring the criteria corpus, and **more consequential than B17**: B17 fails work that is correct, this **passes work that is wrong**. `_forbidden_tokens` accepted any parenthetical that *contained a quote character*, split the whole group on commas and stripped quotes from each part — so it never verified that a part had actually been quoted. Three exhibits, each demonstrated by invoking the check's own function: *"avoids table locks (CrateDB's default non-blocking behavior)"* → `["CrateDB's default non-blocking behavior"]`; *"avoids jargon (don't use it, it's bad)"* → `["don't use it", "it's bad"]`; *"avoids competitor names without a note (e.g., 'Pending legal review')"* → `['e.g.', 'Pending legal review']`. **Each is a FALSE PROHIBITION** — the inverted test then fails a draft that merely mentions the phrase and passes one that omits what the criterion actually required. **Measured impact on the committed corpus: ZERO.** All **597** criteria extract identically before and after. 40 of them do match a prohibition marker (*"to avoid locking the table"*), but their parentheticals use **backticks**, which are not quote characters — so the corpus was safe by luck rather than by design, and the defect was **latent and reachable, not live**. That is why the repair alters nothing the harness currently concludes, which is what makes it instrument repair rather than a ruling: the extractor now does what its own docstring always claimed. **Repaired:** a token counts only when its opening mark sits at a boundary and its closing mark is followed by one, which is what separates a quotation from a possessive. The single-quote arm deliberately permits an apostrophe *inside* a token, because B17's own exhibit ends in `'in today's fast-paced world'` and a stricter pattern would have traded this bug for a false negative on the one genuine prohibition in 597. Proved by reverting the extraction body and watching the guard name the possessive (`tests/test_coverage_shapes.py::TestOnlyProperlyQuotedTokensAreForbidden`, 7 tests, convention 22). **STILL OPEN, and it is a ruling:** a token that is *correctly quoted* but must be **PRESENT** rather than absent is still inverted the wrong way round — in *"…without a note (e.g., 'Pending legal review')"* the surviving token is a thing the work must contain. Deciding which side of a negation a quoted token falls on is comprehension, not extraction. Pinned by a test so the remaining half cannot be mistaken for fixed. |
| B25 | Term overlap may be the wrong test for most criteria | **high** | Opened by Ruling D4 (§43, ARCH-20260922-036). 98.7% of criteria classify `presence` and are tested by term overlap, which is not concept containment. A plan of 6 criteria has probability 1 − 0.987⁶ = 7.6% that at least one is non-presence — B17 is not a one-in-597 event, it is a one-in-13 plan. B17 is *cannot read a prohibition*; B25 is *may be the wrong test for most criteria*. These are different sizes of claim and both are true. `judges_agree` (`checks.py:139`) treats `coverage.passed` as a bool and does not distinguish pass-by-abstention from pass-by-measurement, so a plan whose criteria all abstained passes identically to one whose criteria were all measured. **Scope:** the architecture is three tiers (D5): Tier 1 computable (word counts, ~4.4%), Tier 2 prohibition (extractable tokens, 0.2%), Tier 3 comprehension (presence + ambiguous polarity, ~95%). Tiers 1 and 2 make the loop terminate; Tier 3 makes it sound. The question is whether Tier 3 is sound enough, and it is a question about what the harness concludes. |
| B22 | ~~The provenance stamp guards asserted resolvability and ancestry, never freshness~~ | **CLOSED (2026-09-22)** | Measured on this tree. The header read ``**HEAD:** `039cabe` `` beside ``**Tests:** 931 as of `8bb0cbc` ``, and **`039cabe` is an ANCESTOR of `8bb0cbc`** — the document claimed to describe a commit older than the commit whose test count it reported. **32 commits had modified `HANDOVER.md` since the HEAD stamp**, 9 since the tests stamp. All three existing guards passed throughout: the shas were not placeholders, both resolved, and both were ancestors of HEAD. **Every one of those properties is true of a stamp that is a day stale**, which is why B21's repair of the regex — correct in itself — did not reach this. **The intended property, established before the value was changed:** HEAD names the commit the document DESCRIBES. Forced by the header's own shape — the snapshot *date* is carried separately, so HEAD would be redundant if it meant *last substantive rewrite*, and the tests stamp carries its own sha, so HEAD is the document-level equivalent of a per-fact stamp. A description cannot predate what it describes. **Repaired by two guards, because the defect has two halves.** *Coherence:* HEAD must be the newest sha the document stamps — this catches `039cabe` beside `8bb0cbc` exactly. *Freshness:* no more than **3** commits may have modified `HANDOVER.md` between the stamp and the commit under test. The bound cannot be zero, since the commit that writes a stamp necessarily edits the document; 3 allows that commit, a merge, and one concurrent edit. It is not finely tuned — the observed staleness was 32, an order of magnitude clear. **What it does NOT catch, stated rather than implied (convention 26):** a set of stamps that are uniformly and consistently stale passes the freshness bound only if the document has not been edited, so the two guards cover different halves and neither establishes that a stamp is *correct*. **Proved by breaking it three ways:** a fabricated sha (`cafebabe` — the lag is uncountable, and an uncountable lag is reported as no evidence rather than no problem), a real non-ancestor, and **a real ancestor that is merely stale — the case that passed before this row existed.** **One self-inflicted exhibit worth keeping:** the coherence guard's first anti-vacuity assertion demanded a *differing* sha, so it failed on a correctly and uniformly stamped document — the exact state it exists to certify. Non-vacuity is a property of the pattern finding stamps, not of the shas differing. |
| B11 | Two tier picks are **interim and unmeasured at their own jobs** | medium | `research` and `engineering` ship on models chosen for price and availability, never scored against the work they do. `engineering` carries five of the flagship's nodes and is the tier whose *serving* closed B7 — the model behind it has had no equivalent test. In service by choice, labelled so nobody mistakes the choice for a finding. |
| B12 | Four tiers have **never been measured by serving** | medium | B4 and B7 both turned on *who serves a tier*, and it has only ever been asked of `triage`, `architecture` and `engineering`. `escalation`, `research`, `search` and the reranker are unpinned and unexamined. `escalation` is 70–78% of spend on hard traces (§6.10), so it is the obvious next place to look. Convention 23 says how. |
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

**B13's override (Blueprint 016 B1) adds one exception:** when the *plan's*
success criteria demand verifiability ("a citable source a reader can use to
verify"), ONE bundled lookup fires regardless of triage risk, at the
medium-risk budget — detected free and deterministically over the criteria
text, after the plan exists. Where no criterion demands citation it costs $0.

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
14. **Check a recorded diagnosis before building on it.** A finding in this
    document is evidence of what happened once, not a standing fact. Where work
    targets one, state its premise as a testable claim and test it before
    spending on the fix — and where a cheap test exists, spend the first dollar
    there. B7 is why: "the build loop does not converge" was carried as
    established through three blueprints, and half its evidence turned out to be
    runs that died before reaching the loop.
15. **A measured claim carries its n.** "Measured" at one observation and
    "measured" at thirty read identically and are not the same evidence. A
    single-repetition reading of the grounding suite was labelled measured at
    5/8 twice over; three repetitions put it at 3.67, and the gap was variance
    that one observation could not show. Write the count beside the number.
16. **Run cheap arms first.** In a multi-arm experiment the expensive arm is
    both the most likely to exhaust a budget and the one most affordable to
    lose and repeat. One arm spent $1.12 of $1.17, hit a weekly ceiling
    mid-experiment and took the two cheap arms with it — they cost a sixth of
    it between them and would have been banked.
17. **When a fix invalidates a test, ask which of the two is wrong first.** A
    test asserting current behaviour is not automatically right — it may be the
    bug, written down. Six tests broke on the all-judges exit: three asserted a
    red implementation completing and a drifted one shipping, which is the
    defect as an expectation; three were doubles whose implementations never
    mentioned their own criteria, and those were fixed rather than the
    assertions relaxed. Five more broke on gate routing, all asserting that a
    blocked review ends the run.
18. **A change that alters per-run work re-derives the harness budgets in the
    same change.** Timeouts and caps are fitted to a pipeline's size, and a
    pipeline that grows invalidates them. Blueprint 009 roughly doubled the work
    per run — a build loop, a rework loop, and escalation now reachable from
    both — and left the 900 s per-scenario timeout alone; all four traces then
    expired, and the expiry was read as evidence about convergence. **An
    instrument reading is a reading, not a diagnosis**: a timeout, a zero score,
    a refused lookup and a 403 are each a fact about the apparatus until
    something rules out the apparatus.
19. **No deletion ruling without a recorded reference check.** Grep for
    importers and callers, and record the result, before anything is removed.
    `engine/workflow.py` was ruled legacy and ordered deleted; `api/routes.py`
    imports `WorkflowEngine` from it on every workflow request. The ruling was
    not careless — it inherited the error from §2.1's own data-flow diagram,
    which draws the request path as routes straight to the executor. A document
    can be wrong indefinitely; `tests/test_live_wiring.py` now pins it.
20. **Required fields are informationally independent fields.** A field the
    verdict's own contract derives from another is normalized, loudly, never
    demanded. `green` is defined in every prompt that asks for it as the
    complement of `red_cause` — the model supplies the cause and omits the
    flag, and that killed two of four convergence traces twice, four
    blueprints apart, the second time *after* the schema retry had asked three
    times. `done` stays required because nothing in the verdict implies it.
    **Loudly** matters: every resolution is counted into the run record,
    because a fix that hides its own trigger stops anyone noticing when it is
    no longer needed — or when it starts firing far more than it did.
21. **Shape variance that preserves information is coerced; shape variance
    that loses it is rejected.** The sibling of convention 20, and the narrower
    rule. A serving returned `ValidateVerdict.evidence` as an object keyed by
    criterion instead of a list of strings — twice in one run, the type error
    fed back between attempts, correct only on the third. The key is part of
    the finding, so nothing is lost and it folds into `"key: value"` lines,
    deterministically ordered so a retry cannot change the answer. An object
    with non-text keys or values, or a list half full of strings, means
    something the code cannot know, so it is refused and the retry asks.
    **Counted, like every normalization.** And **exhibits precede leniency**:
    `ReviewFinding` earned eight aliases by losing three entire reviews first,
    this earned one fold by costing two calls, and the rejection log is what
    produces the next exhibit. No field is made tolerant on speculation.
22. **An instrument's test simulates the condition it watches, end to end.**
    Asserting that a counter exists, or that it increments when you increment
    it, proves nothing about the thing it was built to see. **Five instruments
    in two blueprints were found reporting less than they measured, every one
    of them against a green suite:**

    | instrument | what it reported | for how long |
    |---|---|---|
    | schema-rejection log | correct, to stderr, discarded with the shell redirect | every run; 3 logs of 9 survived |
    | per-iteration dissent | nothing — `getattr(dict, "passed")` is always `None` | 64 iterations, 6 runs |
    | per-phase clock | a gate billed for the sub-graph it routed to — 1,573 s of an 1,800 s run | every routed gate |
    | `max_calls` headroom | an opaque abort, never the assertion it exists to produce | as long as both halves existed |
    | normalisation counter | "2 of something" across three different normalisations | its whole life |

    The pattern is specific: **an instrument written in the same commit as the
    fix it watches gets no run of its own to prove it on.** So its test drives
    the real path — a check whose output really is a dict, a gate that really
    routes, a reply the schema really refuses — and the fix is shown to fail
    against the previous code before it is believed.
23. **A serving sweep measures three axes, and latency is the least of them.**
    Ruled after a five-arm sweep would have pinned the wrong serving twice on
    speed alone. In order: **(i) compliance** — a serving whose replies the
    schema refuses is disqualified regardless of speed; the fastest arm in the
    field returned an empty JSON object three times running and killed its run.
    **(ii) iterations to termination** — the pin that closed B7 cut iterations
    8→2 and 4→1 while per-call latency moved only 67 s → 41 s; *a serving does
    not only run at a speed, it converges at a rate.* **(iii) latency**, last.
    And **never at n=1**: one arm read 18.8 s/call on its single repetition and
    produced a 1,200 s expiry and an escalation on its next two.
24. **A fact about the repo is generated or guarded, never hand-stamped.** Any
    count, node list, schema listing or endpoint tally written by hand will be
    wrong within two blueprints, and a commit stamp beside it does not help —
    it records when someone last believed the number, not that it was right.
    **Twelve drifts in one document, enumerated:** three retired claims
    reasserted, two wrong workflow node counts, a wrong pass count, two
    *differently* stale commit-stamped totals, three wrong verdict-field
    descriptions, and an endpoint tally one too high. Eight of the twelve are
    now caught by `tests/test_handover_truth.py`, which derives them from the
    source; the other four were found by reading and are the argument for
    generating rather than guarding wherever a table can be generated — §3.1
    and §3.7 are, and no longer drift. **Where neither is possible, say what
    the claim was measured on and let it age visibly.**
25. No linter/formatter is configured. Match surrounding style: 4-space indent,
    `from __future__ import annotations`, type hints throughout, ~88-col soft
    wrap, module docstrings that explain rationale.
26. **An instrument's report states what it measured and nothing more.** A
    reading that can be mistaken for a stronger claim is a
    **defect in the instrument, not an error in its reader**. Four instances:
    the 429 handler discarded the upstream sentence that named the cause and
    reported only the status; the `.env` verification compared two filtered
    lists and would have passed whether the key was preserved or absent from
    both; an `n=5` count included a unit that died at `plan` and never reached
    the node being measured; and the `detail` string said *verifiability* on a
    path where no lookup had happened. Each was read as a stronger claim than it
    supported, and in three cases that reading was acted on. The remedy is in
    the instrument's wording, not in the reader's caution
    (`ARCH-20260920-010`).
27. **A repetition of a plan-dependent contrast is a second sample, never a
    confirmation.** The plan regenerates between runs (B16), so the second run
    measures a different contract. A ruling asking for `n=2` on such a contrast
    **states which of the two it wants**, and confirmation is not on offer — a
    second sample can widen the evidence or contradict it, but it cannot repeat
    a measurement whose input has changed.
28. **An instrument asserts that it computed its subject before it asserts
    anything about it.** An empty match set, an unread file, a dropped row and
    an absent tier are all *no evidence*, and **no evidence must never be
    reported as no problem**. Ratified 2026-09-22 after **five instruments
    failed in one day** — four that could not fail and one that could not
    survive (§33.2). The sharpest: a provenance guard whose regex used `\s*`
    where the document reads ``**HEAD:** `sha` ``, so it matched nothing, every
    check below iterated an empty list, and **all three deliberate break
    attempts printed `3 passed`**. Two exhibits predate the ratification — the
    serving ledger, which renders three tiers and no escalation row while
    §6.10 measures that tier at 70–78% of hard-trace spend, and CI, which
    asserted nothing-is-wrong for 87 hours without ever computing the state it
    appeared to report (§30).

---

## 5. THE ROADMAP & NEXT STEPS

**The frontier moved.** Everything the first twelve blueprints were about —
calibration, cost, convergence — is **maintenance** now. Calibration sits at
35/36 and is a serving question rather than a prompt question (§6.6). Cost has
an 8× lever identified and waiting on one `.env` line (§6.3). Convergence
closed with B7 (§6.9). None of these is finished in the sense of perfect; all
are finished in the sense that **the next hour spent on them returns less than
the next hour spent on anything below.**

What is left is product, and it is a different kind of work.

### The chosen arc — generalization, "any team"

**The owner's choice, 2026-09-15 — and it has since been probed rather than
estimated.** §6.13, §6.14 and §6.15 are the measurements; this is what they cost
the plan.

**The original pricing was wrong in the safe direction.** It read:

> Vocabularies, profiles and `studio.yaml` are the 70% prerequisite — the
> prompts are the 30%… the risk is that the triage risk guide was rewritten
> four times against live data, and a generalization pass that touches it
> without re-measuring would throw that away.

Three findings dismantle that, in order of how much they move the estimate:

1. **The dialect does not reach the output.** 24 line-items of engineering
   prose in `phases.py`, and **2 dialect occurrences in 18,500 characters** of
   non-engineering deliverable — both of one word that is a schema field name.
   The prompt rewrite is a **tidying exercise, and it is not on the critical
   path.** (§6.13, n=3)
2. **The calibrated text was never the problem.** What four rounds of live data
   bought is the risk guide's *structure*, and it is already domain-neutral —
   it reasons about consequence, not subject. Only its example lists name
   engineering, and they already contain `style guides`, `broadcast loudness`,
   `presentation` and `copy`. (§24.1(a))
3. **The 70% works, measured.** Domains, roles, the checks mechanism and risk
   invariance all hold live. **0 of 23** stably-read sectors moved risk under a
   profile. (§6.14, n=216 units)

**What is actually on the critical path is code, not prose:**

| | |
|---|---|
| **B13 — the verification gap** | **high.** The risk gate zeroes lookups on `low`-risk work and the plan then demands citable sources; the agent fabricates them. The guide's `low` bucket *is* "presentation, copy, documentation", so a content team meets this on its first brief and an engineering team almost never does. **This, not vocabulary, is what stopped the one trace that failed.** |
| **B14 — two literal role injections** | medium. A content studio's high-risk work is staffed and reviewed by an engineer, in 77 of 108 measured units. Cheap to fix, invisible to a prompt map. |
| the prompt tidy-up | low, and now optional. 24 line-items, none a judgement rule. |

**Honest remaining unknown:** all of this is **n=1 per full trace**. Two of
three non-engineering traces shipped inside or at the engineering envelope
(135 s/10 calls and 339 s/15 against 299 s/13), which is encouraging and is not
the same as reliable — `crossref_integrity` is the standing reminder that one
observation of a trace predicts little.

### The arc continues under a new executor

**2026-09-15.** The executor that ran Blueprints 001–015 is being replaced
mid-arc. The protocol those blueprints ran on had lived in session transcripts;
it is now a repo artifact.

- **[`AGENTS.md`](AGENTS.md) is the protocol file** — who decides what, the
  permission boundary, the convention digest, the G-gates, and where the state
  and the evidence live. `CLAUDE.md` is a symlink to it, so there is one copy
  and it cannot drift. `tests/test_protocol_file.py` pins both.
- **[`docs/successor-prompt.md`](../docs/successor-prompt.md) opens a session** —
  the block the owner pastes into a new agent, with the orientation order, the
  division of labour, and what not to touch.
- **`docs/handover-review.md` §26 stages B13 and B14** as design inputs. Neither
  is designed; both need a ruling before anything is built.

Nothing about the harness changed. The next executor should read §25.2 first.

### The other open arcs, priced

| arc | what it is | honest price |
|---|---|---|
| **The human surface** | Escalation produces a root cause and a directive that no human ever sees in a usable form; `dashboard.html` is one file that has had little attention relative to the engine. | Unknown and probably underestimated. The engine's output is good; nothing downstream presents it. |
| **Cascade search** | §6.3 measured two search models tying at the same mean on **different sectors** — complementary, not equivalent. A cascade would take both. | Design is cheap, evidence is not: the tie is n=3 and a cascade needs its own suite. Blocked behind the `.env` swap, which is the owner's. |
| **Per-serving measurement of the remaining tiers** | B12. `escalation`, `research`, `search` and the reranker have never been measured this way, and the axis decided both B4 and B7. | Cheapest high-value item on this list. Convention 23 says how; escalation first, since it is 70–78% of spend on hard traces (§6.10). |
| **Alembic** | B9. No migrations; schema changes are destructive. | Small, dull, and blocking the moment anyone stores real data. |
| **Cross-workflow finding reuse** | Recall exists per gap; a warm shared store across a team's workflows is where search cost goes to near zero. | Speculative — no measurement yet that team workflows overlap enough to pay. |

### Done, and kept here because the ledger is the point

| # | item | outcome |
|---|---|---|
| 1 | B1 — packaging | Three faults, not one. *The fault a suite structurally cannot see is the one that ships.* |
| 2 | B3 — sweep-level spend cap | `--max-spend-sweep`, default $1.00. Production keeps no cap, deliberately. |
| 3 | B2 — materiality | Resolved: not a cost lever, and does not need to be. The per-gap reframe was tried and reverted — it zeroed a *material* lookup. |
| 4 | B4 — `legal_ops` calibration | Done by **pinning rather than tuning**. Nothing in `phases.py` changed. |
| 5 | Provider pin for the real workload | `triage`, then `architecture`, then `engineering` — the last of which closed B7. |
| 6 | B6 — reach `independent_check` live | Done via a purpose-built minimal workflow, kept as the regression shape. Lands ~1 run in 3. |
| 7 | B7 — build-loop convergence | **Closed 2026-09-15.** §6.9, §6.11. |
| 10 | CI — extend, do not create | Complete: matrix, editable install, wheel, container, dashboard template. |
| 11 | Retire the hardcoded sequencer | Done — 251 lines. The file stays; it is the API's entry point. A reference that models less than the product is not confidence. |
| 12 | Review→rework loop | Landed 2026-09-14. Three of four traces had been dying at review with the findings unread. |

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

**Boundary, measured 2026-09-14 — this curve does not transfer between models,
even within one family.** The table above is **n=1 on the expensive model**. On
its cheap sibling at **n=3**, raising both search budgets to 4000 cost
essentially nothing ($0.0061 vs $0.0062 a lookup, the fee inversion confirmed)
and **recovered fewer** figures: 3.00 of 8 against 3.67 with the budgets
unchanged. The swap recommended to the owner is therefore **model only, caps
unchanged**, and this curve must be re-measured on whatever model runs the tier.
At n=3 both models sit near 3.67, not the 5/8 recorded above at n=1.

**The swap itself, measured (n=3 per arm):** the cheap sibling **ties the
expensive model exactly** — same mean 3.67/8, same per-repetition sequence
4, 3, 4 — at **8.2× less per lookup** ($0.0062 against $0.0510) and half the
wall clock. Search is 61–98% of all spend, so this is the largest single cost
lever in the project. The two arms are **complementary, not equivalent**: same
mean, different sectors — arm 1 owns `architectural_acoustics` and `hydraulics`,
arm 2 owns `ev_charging` and `water_treatment` — which is the evidence for a
cascade, and the reason the swap was recommended rather than a merge. The `.env`
edit is the owner's (G-3).

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
     Without this, a return-to-play progression and a statutory retention schedule
     both read `low`.
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

**Validate and review answer different questions, and both are needed.**
Measured 2026-09-14 (n=1): with the assessment contract hardened so criteria
cannot be amended, `requires_execution` came back with all six criteria assessed
as written and none altered — and review still blocked it, on a load test that
sends 101 requests over 1.01 s against a bucket refilling at 100/s and would
therefore pass spuriously. **Criterion 4 asks that sustained rate be covered;
Test 4 covers it; the test is wrong.** Formal satisfaction of a criterion is not
correctness of the work, and no wording fixes that — it is why the per-criterion
structured verdict was not pursued. Validate checks the contract; review checks
the thing.

**The fold caught work the old exit would have shipped.** Measured 2026-09-14:
`derived_tolerances` ran two iterations with `implement` and `validate` green on
both, which can only happen if a free check dissented — so its first attempt
would have shipped under an exit that read validate alone.

**Escalation is the largest single cost line once it is actually reachable.**
Measured 2026-09-14 (n=1, four traces): $0.2684 of $0.4431 — more than the
architecture and engineering tiers combined. It is a reasoning tier reading the
whole failure log, and the log got richer in the same pass that made escalation
reachable from two loops: every failing criterion validate found, and every
finding review blocked on, now travel in it. **The enrichment that fixed the
feedback channel is the same enrichment escalation pays for by the token.**
Capping the excerpt handed to the autopsy is the obvious lever and is
deliberately untouched — it trades the autopsy's evidence for its price, and
that is a judgement, not a repair.

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

**The repaired meter has since been checked against the provider's own books**
(measured 2026-09-14, §12.2): across $0.32 of live spend, OpenRouter's
`total_usage` moved $0.3165 where the meter accounted for $0.3173 — agreement
within **0.3%**, reading marginally *high*, which is the conservative direction
for a ceiling. The first external validation since the fix.
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

- **Two phases never opted into the schema retry at all** (found 2026-09-14).
  `chat_json` validates against a schema and retries three times with a note
  saying what was rejected; `implement` and `escalation` passed no schema and
  constructed their verdicts afterwards, so one malformed reply raised and ended
  the run. Implement killed **two of four live traces**, and those deaths were
  read as convergence failures — which is how B7's premise came to rest on
  evidence that never reached the loop. Escalation had it worse: the longest
  input in the system, read only after the loop has burned every iteration.
- **A status code read as a diagnosis** (same date). A live 403 stopped every
  paid run; it was read as rate limiting and blamed on two sweeps running
  concurrently. The response body said `Workspace weekly budget of $10.00
  exceeded` — a different problem, a different fix, and nothing to do with
  concurrency. `raise_for_status` renders only the status line, so the half of
  the error that explained it was discarded at the point of raising, at all
  three call sites. Purchased credit was never the constraint and stayed
  healthy, which is exactly why the balance looked fine while nothing worked:
  **credit and the workspace's weekly ceiling are independent limits.** The
  body travels with the exception now.
- **Leniency at the verdict layer, defeated three lines upstream** (same date).
  `ReviewFinding` accepts a bare string or a detail under eight aliases, added
  after a reviewer using `issue` lost three whole reviews. The aggregation still
  called `f.get("severity")` on the raw item, so the exact shape the leniency
  existed for raised `AttributeError` **after every reviewer had been paid**.

Both were invisible to the suite, which was green before and after, because test
doubles return well-formed verdicts. Pinning the call sites is the only thing
that catches this class — `tests/test_schema_wiring.py` now does.

- **A guard whose result depends on test ordering is not a guard** (found
  2026-09-14). The equivalence suite passed in a full run and failed in
  isolation, on unmodified code, because the rerank strategy latches in a
  module-level global and whichever side of the comparison ran first did the
  probing. The latch is right in production — each strategy is probed once, so a
  dead end stops costing a call forever — and poison in a comparison.

- **A wrong diagram outlived every reader of it** (found 2026-09-14). §2.1
  draws the request path as routes → executor, omitting the `WorkflowEngine`
  the routes actually call. Nine blueprints read that section; the error
  surfaced only when a ruling acted on it and ordered the live module deleted.
  Prose is not checkable and a test is: the dependency is pinned now.

- **A gate billed for the sub-graph it routed to** (found 2026-09-15). B3 named
  the per-phase timing table as what B7 gets from an expiry instead of closure.
  The first expiry that needed it reported a *gate*, `review_clean`, as the
  largest consumer of the run at 1,573 s, with the table summing to **3,374
  seconds inside an 1,800-second run**. `_run_gate` awaited `_run_from` from
  inside the node's timing block, so every node a closed gate routed to was
  counted twice. The correction is exact: drop the one gate and the table reads
  1,801 s. A measurement that is 187% of its own ceiling is not a rounding
  error, and nothing in the suite could see it because no test timed anything.

- **A record that read attributes off a dict** (found 2026-09-15).
  `derived_tolerances` ran two build-loop rounds with implement green and
  validate green and did not exit, so a free check dissented. The iteration
  record was built to name which. It named nothing for **64 iterations across
  six runs**: a check's entry in `state.outputs` is a plain dict, and the
  retention called `getattr(coverage, "passed", None)` on it. The same code also
  read the `judges` fold, which at that point in the loop body belongs to the
  *previous* iteration.

- **A working instrument whose output nobody kept** (found 2026-09-15). The
  schema retry has logged every rejection at `WARNING` since the clause
  ordering above was fixed. The eval CLI configures no logging, so those lines
  went to Python's lastResort stderr handler and lived as long as the shell
  redirect that caught them. Asked for the malformed-verdict rate across all
  retained history, 011 found **three run logs of nine**, and neither of the two
  runs the question turned on was among them. This is not the meter-epoch bug —
  nothing was mismeasured — it is the subtler one: the measurement was correct,
  free, and thrown away every time. **A number that only exists in a temp file
  has not been recorded.** The count lands in the JSONL unit record now, per
  tier and per serving.

**Therefore: live-test multi-request sequences. The unit suite is necessary and
nowhere near sufficient.**

### 6.9 B7's six names — what "the build loop does not converge" decomposed into

B7 was open for seven blueprints and carried **six** different names. The list
is recovered from the row itself, by reading `HANDOVER.md` at each commit that
changed it, because two separate summaries written from memory both got it
wrong — one invented a name ("budget") the row never had.

| # | the row said | after | the diagnosis | what it cost to find out |
|---|---|---|---|---|
| 1 | *does not converge on complex requests* | — | specialists have no filesystem; the validator asks for evidence that cannot exist | `SPECIALIST_OUTPUT_CONTRACT`, which mitigates and does not solve |
| 2 | *premise **untested*** | 006 | the claim rested on runs that never reached the loop — 2 of 4 died on a schema violation first | the schema was never wired into the retry; two phases fixed |
| 3 | *premise tested; **failure mode moved*** | 008 | the all-judges exit landed; three of four converge, **one runs out the wall clock** | the exit condition, the fold, and four judges |
| 4 | *failure mode moved twice; **now clock-bound*** | 009 | review→rework landed; both feedback channels opened | a rework loop and two channels |
| 5 | *the loop works; **a required field does not arrive*** | 010 | two of four traces die on `ImplementVerdict` missing `green` | the green truth table; convention 20 |
| 6 | *the loop is not the constraint; **the clock is*** | 011 | 23 units, six expiries, **none ever stopped by money** | the gate-timing fix, the rejection counter, the dissent record |

**Read the shape, not the list.** The wall clock appears as an aside in name 3,
becomes the name in name 4, is **displaced** in name 5 by a verdict field, and
returns in name 6 with twenty-three units behind it. B7 was diagnosed
clock-bound two blueprints before it was settled clock-bound. The thing that
displaced it — four traces dying on a missing field — was real, was fixed, and
**was never the constraint**.

**What actually closed it was none of the six.** Every name pointed at the
workflow; the fix was the `engineering` tier's *serving*. Pinning it turned two
traces that had never completed into ships in 299 s and 182 s. And the mechanism
was not the one the sweep measured: per-call latency moved from a 67 s median to
41 s, while **iterations went 8 → 2 and 4 → 1**. A serving does not only run at
a speed, it converges at a rate. That is §6.1's thesis — *a model id is not a
system* — reaching the one tier that had never been pinned, six names later.

**The transferable lesson is about the naming, not the answer.** Each of the six
names was correct about what the evidence then showed, and five of them were
about the wrong layer. The one question never asked until 012 was *who is
serving this tier* — and it had been answerable, for free, from
`providers_by_function`, since B4.

---

### 6.10 Escalation is where the money goes, and not where the time goes

Measured on the three traces that ran a full 1,800 s clock (n=3, gate rows
excluded — see §6.8 on the gate that billed itself for its own sub-graph):

| trace | escalation spend | escalation clock | escalation calls |
|---|---|---|---|
| `derived_tolerances` | **71%** | 5% | 1 |
| `numeric_consistency` | **70%** | 10% | 3 |
| `requires_execution` | **78%** | 34% | 3 |

A fixed prompt reading a log that grows with iteration count: per-call cost crept
$0.0673 → $0.0895 → $0.0917 across three runs. **What is in that log**, by
character count across four traces: **77–89% implementation summaries**, 9–17%
the evidence and findings channels, 2–10% red causes. An earlier suspicion that
the channels were the expense is **wrong by measurement** — cutting them would
remove a tenth of the tokens and all of the diagnostic value the autopsy exists
to use.

**The consequence is a decision, not a design.** Compressing the failure log is
a *cost* measure: it would take 70–78% of a bill that has **never once been the
binding constraint** and return 5–10% of a clock that always was. Worth a
blueprint on its own terms; not a fix for anything currently broken.

### 6.11 A serving does not only run at a speed — it converges at a rate

> **PROVISIONAL (2026-09-22, §31).** Every serving reading below is
> provisional by the resweep-2 pre-registration's own registered rule: its
> control was refuted — SiliconFlow, predicted to fail all six units, went 6/6
> at mean 1.0 iterations. 43 units across four generations license **no
> ranking** (convention 23). **T1 — peak-hour serving — has never been run.**

**The finding that closed B7, and the one most likely to be reused.** Pinning the
`engineering` tier to a compliant serving changed the loop far more than it
changed the clock:

| trace | iterations before → after | loop s/call before → after |
|---|---|---|
| `derived_tolerances` | **8 → 2** | 67.1 → 26.0 |
| `numeric_consistency` | **4 → 1** | 135.9 → 42.6 |
| `requires_execution` | 8 → 8 | 41.5 → 41.1 |

**n = 1 per trace.** Two traces that had never completed under an unpinned tier
shipped on the first attempt in 299 s and 182 s; `derived_tolerances` had been
run seven times before without completing once. Per-call latency moved from a
67 s median to 41 s — a third — while iterations fell by 4× and 4×.

**Two pre-registered predictions, both about seconds per call, both wrong in the
same direction**, which is why this is recorded as the finding rather than the
latency table that was expected. It is §6.1's thesis — *a model id is not a
system* — reaching the tier that had never been pinned. Convention 23 encodes
it: sweep on compliance, then iterations, then speed.

**Also measured in the same sweep (n=1–4 per arm):** the fastest serving of five
returned an **empty JSON object** three times running and killed its run, and a
serving reading 18.8 s/call at one repetition produced a 1,200 s expiry and an
escalation at its next two. A latency-only sweep would have pinned either.

### 6.12 Formal satisfaction is not substantive correctness — and that is by design

Measured on `requires_execution`: the validator returned green on a criterion
asking that sustained rate be covered, because a test did cover it — while that
test was **arithmetically wrong in a way that would produce false passes**. The
verdict was correct as written.

This is not a defect in the validator. **Validate asks whether the criteria are
satisfied; review asks whether the work is right.** The division is deliberate,
and this is the measurement that confirms both halves are needed: a criterion
can be met by work that is wrong, and only a second reader with a different
question catches it. It is the same structural axis as *specialists have no
filesystem* (§6.9, name 1) — the validator asks for evidence that cannot be
produced, so it grades the description of the evidence instead.

**Validated in service:** the escalation autopsy for this trace named a real
arithmetic contradiction in the plan itself — *a token bucket of depth 20
refilling at 100/s admits at most 20 in an instantaneous burst, yet the burst
tests expected 120*. The machinery that catches substance is working; it simply
is not the validator, and must not be asked to be.

---

### 6.13 The engineering dialect is in the prompts and does not reach the output

> **Post-fix reading, 2026-09-20 (B13).** On the build path the fix replaces
> fabrication with **refusal plus labelling**: *"All three proof points are
> labeled as unsourced because I cannot independently verify the cited
> reports."* The contrast is 43 calls into a cost ceiling against **22 calls to
> an honest `blocked` terminal**, n=1 each side. And the premise this section's
> B13 row was built on is narrowed: **zero lookups at `low` risk is correct
> behaviour, not the defect** — E2 measured it at **n=2**, with `low` returned
> at both bounds and no search tier billed in either repetition. The defect was
> never the zero; it was the plan writing a criterion the run could not satisfy.
> What remains unfixed is **B15**.

**The generalization arc's central assumption, tested.** §5 priced the prompt
rewrite as the risky 30%. Two free measurements and three paid traces say it is
neither risky nor, on this evidence, necessary.

**What the prompts contain** (`engine/phases.py`, 1,019 lines, read line by
line): **24 line-items bind the dialect** — 4 artifact-noun lists, 8 examples,
6 uses of "engineering" as a modifier, 2 role names in prose, 2 literal role
injections in code, 2 eng-worded statements of a neutral intent. **None is a
judgement rule.** The risk guide's calibrated structure — the two questions in
order, the standards clause, the protective-systems and governing-documents
rules — is already domain-neutral, and so is `ASSESSMENT_CONTRACT`'s
criteria-are-fixed clause, the most load-bearing block in the file.

**What the output contains** (n=3 traces, 18,500 characters of model output
searched for 13 dialect markers):

| | dialect occurrences |
|---|---|
| three implement deliverables (16,514 ch) | **1** |
| validate causes, review findings, autopsies (~2,000 ch) | **1** |

Both are the word `implementation`, which is the harness's own schema field
name. **No "test case", no "code", no "schema", no "engineer".**
`OUTPUT_CONTRACT` instructs implement to produce *"the design, the code, the
schema, the procedure, the calculation"*; implement produced contract clauses, a
house style guide and a positioning brief. **The dialect reads as context the
model discards, not as instruction it obeys.**

Two pre-registrations predicted where binding would concentrate — implement and
validate, or escalation. **Neither bound.** A prompt map says what *could* bind;
only a probe says what *did*.

### 6.14 A profile does not move risk, and the suite's own noise is larger

Measured 2026-09-15, 36 sectors × 3 repetitions × 2 arms = **216 units, $0.0597**,
same day, same pins, differing only in `AUTORND_PROFILE`:

| | |
|---|---|
| sectors whose modal risk is unchanged | 32/36 |
| sectors read **unanimously in both arms** | 23/36 |
| of those 23, sectors whose risk differs | **0** |
| sectors not unanimous **with themselves** across 3 reps | studio 9, control 8 |

**Not one stably-read sector changed its risk under a profile.** All four
apparent movers are unstable in at least one arm; one produced three different
answers in the control alone. The profile's effect is smaller than the suite's
own repetition spread, and that is the honest form of "risk is
profile-invariant". The mechanism is narrow by construction: `run_triage`'s
system prompt is a fixed literal and its user prompt carries no profile context,
so a profile changes **only the two vocabulary lists** triage is offered.

**The vocabulary earns its place on exactly the work it should.** Of 36 sectors
one is content work; the control invented `copywriting` for it **once in three**
unaided, and the profile made it **three of three** with `copywriter` attached.
The other 35 were untouched.

**And the open vocabulary is doing more work than any profile.** In the studio
arm triage invented **67 role assignments across 38 distinct names** —
`process_engineer` ×14, then `prosthodontist`, `veterinary_anesthesiologist`,
`brewer`, `agronomist` — against **4** assignments of the profile's own declared
roles. On work a profile does not cover, the freedom to name a role matters far
more than the roles it declares. §6.5 from the other direction.

### 6.15 The crossref failure is a property of the agent, not of the subject

§18.1 diagnosed `crossref_integrity` as *"the implementation agent writes each
section as an independent narrative unit and never performs a global
dependency-ordering or cross-reference pass"*. That was measured on engineering
work over eight iterations.

Re-asked 2026-09-15 on a **house style guide** (n=1): iteration 1 came back red
with `dissenting = [consistency, implement, validate]` and the cause *"Worked
examples in Sections 2, 3, and 5 violate stated rules"* — **the same failure, in
a subject with no engineering in it.** The loop caught and fixed it in **one**
rework round rather than eight.

This is also the first live reading from the per-iteration dissent record
repaired in 012, and it names `consistency` — a free deterministic numeric check
— as a judge that caught a style-guide defect nobody would have pointed it at.

---

### 6.16 A 429 is a property of the (model, provider) pair

**Belongs with §6.1 and §6.11** — the same thesis, one layer down: a model id is
not a system, and neither is a provider name.

**A 429 is a property of the (model, provider) pair, not of the model alone or
the provider alone.** All twelve 429s in the committed record are
`deepseek/deepseek-v4-flash`, spread across five providers inside one two-hour
window, while the same model via Alibaba ran 309 units without one. The pair
plus `allow_fallbacks: False` is what converts a transient upstream shortage
into a dead run; an unpinned rotation answered on demand throughout. Cost of the
twelve: **$0.2163, all of it buying nothing.**

**One episode, one window, no denominator — sufficient to name the mechanism,
not to rank servings.**

> **PROVISIONAL (2026-09-22, §31).** The ledger this cites carries three
> tiers and **no row for escalation**, which §6.10 measures at 70–78% of
> hard-trace spend: `tests/serving_ledger.py`'s skip-unpinned rule drops every
> unpinned arm, so a complete-looking table reports less than it measured
> (convention 26). Repair proposed in `ARCH-20260922-011`, not yet ruled.

Two things this fact does **not** license. The $0.2163 is a **pre-fix** number
and is not what the retry saves: there have been **zero post-fix 429 events**, so
the repair has never fired in production and is proved by
`tests/test_rate_limit_retry.py` alone. And the distribution cannot rank
providers — GMICloud carries 3 of the 12 events *and* 227 completed units of 236
(`docs/serving-ledger.md`). Derivation and the four questions the record cannot
answer: `.orchestration/responses/ARCH-20260920-005.response.json`.

---

## 7. FAST ORIENTATION FOR THE NEW ARCHITECT

```bash
cd ~/projects/autornd-os
.venv/bin/python3 -m pytest tests/ -q                    # 959 tests as of `27e3e8f`, ~52 s, free

# cheap live calibration — 108 calls, ~5-18 min, under 2 cents
.venv/bin/python3 -m autornd.evals.cli \
  --scenarios evals/scenarios/wide --workflow triage-classify \
  --repeat 3 --timeout 45 --max-spend 0.10

# factual accuracy vs published standards — 8 sectors, ~$0.17-0.72
.venv/bin/python3 -m autornd.evals.cli \
  --scenarios evals/grounding --workflow triage-only \
  --repeat 1 --timeout 240 --max-spend 0.30

# the flagship, on the four hardest shapes — all four now terminate.
# ~$0.15-0.45 and 3-20 min per trace. PIN THE TIERS or the reading is noise.
OPENROUTER_PROVIDER_ORDER="triage:Alibaba,architecture:StreamLake,engineering:GMICloud" \
.venv/bin/python3 -m autornd.evals.cli \
  --scenarios evals/scenarios/convergence --workflow engineering-rnd \
  --repeat 1 --timeout 3600 --max-spend 0.75 --max-spend-sweep 3.00 \
  --results-file docs/traces/my-run.jsonl

uvicorn autornd.main:app --reload --port 8100            # API + dashboard
```

**Read these four files, in this order, to understand the system:**
`workflows/engineering-rnd.yaml` → `autornd/graph/spec.py` →
`autornd/engine/phases.py` (the risk guide especially) →
`autornd/routing/openrouter.py` (accounting, budgets, provider pinning).

**Three habits, in order of how much they will save you:**

1. **Before changing a prompt or a constant, read the comment beside it.** It
   names the live run that set it, and probably a previous attempt that failed.
2. **Pin the servings before believing any live reading.** An unpinned tier
   draws a dozen providers inside one run, and *which* one served it has decided
   two of this project's largest findings (§6.1, §6.11). An unpinned measurement
   is not a measurement of your change.
3. **An instrument reading is a reading, not a diagnosis.** A timeout, a zero
   score, a refused lookup and a 403 are each a fact about the apparatus until
   something rules the apparatus out. Five instruments in this repo were found
   reporting less than they measured, every one against a green suite
   (convention 22).

**Where the record lives.** `docs/handover-review.md` is the lab notebook:
thirteen blueprints, each pasted verbatim before execution with an execution
record after it naming departures and what execution found that the blueprint
missed. `docs/traces/` holds the committed JSONL of every live run cited here.
**This document is the state; that one is the evidence.**
