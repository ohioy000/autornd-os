# AutoRnD

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-2506%20passing-brightgreen.svg)](#testing)

**A harness that lets low-cost models answer precise expert questions, shows what each answer rested on, and says honestly what it checked.**

You send a request in prose. A workflow defined in a YAML file triages it, grounds it in sources, writes one answer and checks that answer with free deterministic code. The answer comes back with what was checked against a source and what was not.

It is built for precise professional questions that name their rule or standard. It talks to any OpenAI-compatible endpoint.

**Who it is for.** People who ask many precise questions and need to see what each answer rested on: a team checking regulations, standards and datasheets, for example. It is built to cost far less an answer than asking a frontier model directly. The trade, as measured: it is slower, and on questions written after it was fixed it was less often right than a frontier model asked directly with web search. For a handful of questions, asking a frontier model with search is the simpler way. The figures are in [`docs/MODELS.md`](docs/MODELS.md) and the [release notes](docs/release-notes.md); this README does not restate them. **You choose every model:** AutoRnD ships no defaults and recommends none.

## What It Does

A request that names no workflow runs the default, [`workflows/answer-and-recompute.yaml`](workflows/answer-and-recompute.yaml):

1. **Triage.** One call on the triage tier classifies the request: its domains, its risk and its specialists.
2. **Asks.** One call on the triage tier quotes what the request asks for. A free check keeps only the quotes that really occur in the request. When none do, the whole request is the one ask.
3. **Grounding.** The harness retrieves from the documents you ingested and, when a lookup is wanted, reads outside sources itself. See [Research](#research).
4. **One answer.** One call on the engineering tier, from the request, the asks and the grounding. It states its results as typed values, one for each ask that wants a value or a verdict.
5. **Two gates.** The run ends `blocked` if the answer says it cannot meet an ask, or if the answer is still cut off mid-sentence after it has been written again three times.
6. **Free checks.** Does the answer address each ask? Does it contradict a figure the request states? These are notes. They never block.
7. **Recompute vote, optional.** For a request judged to need a calculation, three blind samples recompute the typed results and a free check votes. A disagreement is a note, never a block. It is off unless two optional tiers are set, see [Model Tiers](#model-tiers).
8. **Decision switches, optional.** Small yes/no questions on the decision tier, asked before and after the answer.

This workflow has no plan, no judge and no loop. Those belong to the other workflows, see [Workflows Are Files](#workflows-are-files).

What comes back is the answer, the lines that were confirmed against a source, the cautions, and the sources read. See [Ask a Question and Read the Answer](#ask-a-question-and-read-the-answer).

AutoRnD produces text. It does not run code, edit files or deploy anything.

## Status

AutoRnD is a research harness as much as a product. It measures itself, and the records say what it does and what it does not do. Read them before you rely on a workflow:

- [`docs/HOW-WE-GOT-HERE.md`](docs/HOW-WE-GOT-HERE.md) tells how the harness came to its present shape, why it has so many tests, and why its rules describe an architect and a coder.
- [`docs/MODELS.md`](docs/MODELS.md) names the models we ran for each tier and argues why inexpensive ones are the right choice for this work.
- [`docs/README.md`](docs/README.md) is a map of the record.
- [`docs/reviews/`](docs/reviews/) holds one dated report for each measurement.
- [`docs/traces/`](docs/traces/) holds the run records those reports cite.
- [`docs/carryover-2026-11-16.md`](docs/carryover-2026-11-16.md) says where the harness stands and what is planned.
- `HANDOVER.md` section 6 keeps the older measured facts.

What the records say, in short:

- **The lookup that reads the documents is the default.** It was compared with the older lookup on the professional question sets: [`2026-11-15-lookup-reads-documents.md`](docs/reviews/2026-11-15-lookup-reads-documents.md), [`2026-11-15-professional-baseline.md`](docs/reviews/2026-11-15-professional-baseline.md), [`2026-11-15-professional-hard-run.md`](docs/reviews/2026-11-15-professional-hard-run.md).
- **The cautions were rebuilt around the text the harness hands on:** [`2026-11-15-cautions-on-handed-on-text.md`](docs/reviews/2026-11-15-cautions-on-handed-on-text.md).
- **The recompute vote is off by default and kept for calculations.** It was proven on calculations ([`2026-10-18-d53-the-recompute-vote.md`](docs/reviews/2026-10-18-d53-the-recompute-vote.md)). On questions a document answers it was measured not to help ([`2026-11-16-recompute-samplers.md`](docs/reviews/2026-11-16-recompute-samplers.md), and the comment on `needs_calculation` in `switches/default.yaml`).
- **The default workflow runs no judges.** The reason is in the comment on `autornd_workflow` in `autornd/config.py`.
- **What is not caught** is under [Limitations](#limitations).

This README describes mechanisms and points to the records. It does not restate their figures, so it cannot fall behind them.

## Quick Start

You need Python 3.11 or later and an API key for an OpenAI-compatible provider. Docker is optional.

```bash
git clone https://github.com/ohioy000/autornd-os.git
cd autornd-os
python3 -m venv .venv && . .venv/bin/activate
cp .env.example .env          # then edit .env, see below
pip install -e .
python -m autornd.preflight   # checks the configuration, bills nothing
uvicorn autornd.main:app --port 8100
```

`python3 --version` must print 3.11 or later. If it prints an older version, make the virtual environment with `python3.11` or `python3.12` instead; `pip` refuses an older Python and says so. AutoRnD keeps its database (`autornd.db`) and its knowledge store (`chromadb_data/`) in the directory you start it from, so start it from the same place each time.

In `.env`:

- Set `OPENROUTER_API_KEY`. Set `OPENROUTER_BASE_URL` to use another OpenAI-compatible endpoint.
- Set a model for each of the six required tiers: `MODEL_TRIAGE`, `MODEL_ENGINEERING`, `MODEL_ARCHITECTURE`, `MODEL_ESCALATION`, `MODEL_RESEARCH`, `MODEL_SEARCH`. All six must be set to start, although the default workflow calls only four of them. See [Model Tiers](#model-tiers).
- Set `API_KEY` or `JWT_SECRET` if anything other than this machine will call the server. See [Auth, Limits and Deployment](#auth-limits-and-deployment).

[`.env.example`](.env.example) documents every setting and its default. It is the single source of truth for settings.

If a required tier is unset, AutoRnD refuses to start and names the tiers that are missing. `python -m autornd.preflight` asks the provider's catalogue whether each configured model and provider pin is real. It makes no model call, and it needs the network but not your key, because the catalogue is public. It prints one `[ok]` or `[FAIL]` line for each check and exits with status 1 if any failed. A `[FAIL] ... not in the provider catalogue` line means that model id is not one your provider serves; correct it in `.env`. At startup the server makes the same kind of check, and `GET /api/health` reports `ok` or `degraded` and names the tiers it could not verify.

The dashboard is at `http://localhost:8100/`. The server binds to loopback by default.

**What you should see on the first start.** With the key left empty or the tier ids not yet checked, the server still starts, and `GET /api/health` answers 200 with `"status": "degraded"`, `"provider_key_configured": false`, and each tier it could not verify under `unverified_models` with `"available": false`. That is the honest report, not a crash. A run submitted in that state ends `blocked` at once, bills nothing, and says why in `error`: `MissingProviderKey: No provider key is set. Put OPENROUTER_API_KEY in .env and restart the server.` Set the key, restart, and `/api/health` reports `ok`.

### Docker

```bash
docker build -t autornd .
docker run -p 8100:8100 --env-file .env \
  -v autornd-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/autornd.db \
  -e CHROMADB_PATH=/data/chromadb \
  autornd
```

- **The image does not carry your `.env`.** [`.dockerignore`](.dockerignore) keeps every `.env*` file except `.env.example` out of the build, so a key never lands in an image you might push or share. The key reaches the container only through `--env-file` when it runs. If you build an image of your own from this tree, keep that file.
- **Keep the volume.** By default the image writes its SQLite file and its ChromaDB store inside the container, and both are lost when the container is removed. The `-v` and `-e` lines above put them on a named volume.
- **Set `API_KEY` or `JWT_SECRET` first.** A request that reaches the container through the published port is not a loopback caller, your own host included. With neither set it is refused with 403 and a sentence naming the fix. Only `/api/health` answers.

## Ask a Question and Read the Answer

Submit and wait for the result:

```bash
curl -X POST http://localhost:8100/api/workflows/sync \
  -H "Content-Type: application/json" \
  -d '{"request": "Under 14 CFR § 91.151, how much fuel beyond the first point of intended landing must an airplane carry to begin a flight under VFR conditions, by day and by night? Give each as a time at normal cruising speed."}'
```

Or submit, get an id back at once, and poll:

```bash
curl -X POST http://localhost:8100/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"request": "..."}'            # 202, the id is in data.id
curl http://localhost:8100/api/workflows/<id>
```

Poll until `status` is `completed`, `blocked` or `escalated`. With authentication on, add `-H "Authorization: Bearer <your API key or token>"`. A request may name its workflow: `{"request": "...", "workflow": "verify-first"}`.

Both paths return the same record under `data`:

| Field | What it holds |
|---|---|
| `status` | `completed`, `blocked` or `escalated` when the run has ended |
| `answer` | the answer, only when the run completed |
| `candidate` | the last answer written, when the run did not complete. Nothing endorsed it |
| `confirmations` | what was checked against a source, in plain sentences |
| `cautions` | what a reader should know before relying on the answer, in plain sentences |
| `sources` | for each lookup: the documents named, each passage handed on, its page, whether it was `found` there, and the time and sha256 of the version read |
| `recompute_vote` | the vote's record. `skipped` is true when the samples did not run |
| `decisions` | every decision switch asked: its probability, choice, mode and route. Empty with no decision tier |
| `total_cost` | what the run spent. `unreconciled_liability` is the worst case of calls that failed after they were sent |
| `error` | `null` on a healthy run, otherwise why it stopped |
| `phases` | every step's typed record, the workflow file's name and sha256 first |

`confirmations` and `cautions` are written only for a completed run. Nothing routes on them. They are for the reader.

**A confirmation** names the asks whose figures stand in a passage that was found on its page. Found on its page means the words are there. It does not mean the answer is right, or that the page is the right rule.

**The cautions**, and what to do about each:

| The caution says | What it means | What to do |
|---|---|---|
| A figure is in none of the passages found on their pages | the answer states a number that no text the harness read contains | check that figure against the source yourself |
| Two pages give different figures for the same thing | the pages read disagree, for example an old edition beside the current one | open both pages in `sources` and see which one governs |
| A lookup ran, but nothing was checked against a source | it quoted no passage, or no page it named could be read, or no passage was found on its page | treat the answer as the model's memory. Ingest the document, or ask again naming a page that can be read |
| No lookup ran | figures and citations come from the model's memory. Not said beside a request judged to need a calculation | ask for sources in the request ("cite the source"), which always runs a lookup |
| The recompute vote disagrees with this answer | a majority of the blind samples computed another value for the ask named | recompute that ask by hand. `recompute_vote.disagreements` has both values |
| The recompute vote compared nothing, or did not run | said only when nothing else checked the answer either | as for the first rows: the answer is unchecked |
| The vote worded an ask differently, reached no majority, or could not compare an ask | that part of the answer was not compared, or differs only in wording | read that ask with more care |

## Model Tiers

Each step is routed to a tier named by its job. You set one model per tier.

**Required** at startup, all six, whichever workflow you run:

| Tier | Job | Which workflows call it |
|---|---|---|
| **Triage** | triage and the asks | every workflow |
| **Engineering** | the answer. In `lean` also validate and review, in `full-team` also feasibility | every workflow that writes an answer |
| **Architecture** | the plan | `full-team`, `lean` and two probes. Not the default |
| **Escalation** | the autopsy after a build loop gives up | `full-team` only |
| **Research** | grounding: the retrieval queries and the briefing | every workflow but `triage-classify` |
| **Search** | outward lookups | every workflow but `triage-classify`, when a lookup is wanted |

**Optional**, each one turns its feature off when empty:

| Tier | Job |
|---|---|
| **Ranker** | orders retrieved documentation by usefulness. Empty, the research model ranks |
| **Premium** | the Double Check review a user can ask for after a run, and `full-team`'s independent pass on work that cannot be recalled. Empty, the Double Check endpoints answer 404 and the pass uses the architecture tier |
| **Judge** | validate, domain review and review in `full-team`, and validate in `verify-first`, on a different model from the one that wrote the answer. Empty, they run on the engineering tier. The default workflow does not use it |
| **Recompute** | the three blind samples of the recompute vote. They run only when the decision tier is set as well and the `needs_calculation` switch routes yes. Otherwise the step records a skip, and the vote reads a skip as skipped, never as passed |
| **Reader** | small, fast models that read the long pages a lookup fetched, many stretches at once, and copy back the words that bear on the question. Each copied passage is checked against the page and dropped if it is not there; nothing is summarised. Empty, a lookup hands on the stretches chosen by shared words alone |
| **Decision** | a decision model, which returns typed answers with probabilities and no text. It answers the decision switches. Empty, no switch is asked and the recompute step never runs |

So `MODEL_DECISION` alone turns on the switches, and `MODEL_DECISION` with `MODEL_RECOMPUTE` turns on the recompute vote for calculations. The decision tier needs a model served on the provider's decisions route, not a chat model.

To pin which provider serves a tier, set `OPENROUTER_PROVIDER_ORDER`. `.env.example` explains the form and why a measurement should be pinned.

### Decision switches

The switches are declared in [`switches/default.yaml`](switches/default.yaml), each with two thresholds, a safe answer and a mode. All four are `live`: the harness acts on a confident answer and takes the safe, more careful side otherwise. A new switch starts in `shadow`, where its answer is recorded and nothing acts on it.

| Switch | Mode | What it does |
|---|---|---|
| `needs_sources` | live | a yes runs the grounding lookup whatever risk triage gave. A confident no skips a lookup that only the risk rating asked for |
| `needs_calculation` | live | the recompute step runs unless the answer is a confident no |
| `quote_answers` | live | a found passage that does not answer its question is labelled `answers_question: false` in `sources`. It is kept, and it backs no confirmation |
| `same_meaning` | live | asked when the vote flags an ask stated in words. A confident yes clears the flag as a difference of wording, and a caution says so |

## Workflows Are Files

The sequence of steps is data, not code. A workflow is a graph of nodes in YAML, of three kinds:

| Kind | What it is | Cost |
|---|---|---|
| `ai` | one model call, routed to a tier, validated against a typed verdict | paid |
| `check` | a deterministic function over earlier outputs | free |
| `gate` | a condition that lets the run continue, routes it, or ends it with a status | free |

An excerpt from `workflows/full-team.yaml` (`tests/test_docs.py` compares it with the file):

```yaml
- id: validate
  kind: ai
  tier: judge
  specialist: test_engineer
  prompt: validate
  schema: ValidateVerdict
  max_tokens: judge_max_tokens
  depends_on: [coverage, consistency, domain_review]

- id: build_loop
  kind: ai
  body: [implement, blocked_check, blocked_gate,
         domain_review, coverage, consistency, validate, judges]
  until: judges.passed == true
  max_iterations: max_iterations
  on_exhausted: escalation
  depends_on: [verify_grounding]
```

A condition is one comparison over a dotted path. There is no `eval`: a workflow file is configuration and must not execute code.

The workflows that ship, one file each in `workflows/` (`tests/test_docs.py` checks this table against the directory):

| Workflow | Shape |
|---|---|
| `answer-and-recompute` | the default, described under [What It Does](#what-it-does). Offered |
| `verify-first` | no plan: the asks, one answer, the free checks and one judge. One revision if the judge names a failed ask, escalated if the dissent survives. Offered |
| `lean` | a plan, a build loop with validate, the cut-off gate, then one review. No feasibility review, no domain review and no escalation autopsy: a loop that does not converge ends `escalated`. Offered |
| `full-team` | the full team: plan, feasibility, a build loop with domain review and judges, review with rework, an escalation autopsy, and an independent pass on work that cannot be recalled. Offered |
| `triage-only` | triage and grounding only, for measuring them cheaply. A probe |
| `triage-classify` | one node, triage alone. A probe |
| `plan-probe` | triage, grounding and the plan alone. A probe |
| `independent-check-probe` | one pass that reaches the independent check and nothing else. A probe |

**Choosing one.** `AUTORND_WORKFLOW` sets the server's default. Unset, it is `answer-and-recompute`. A request may name one of the four offered workflows in its `workflow` field, and `GET /api/workflows/offered` lists them. Any other name, or a path, is refused with 422 before anything runs. The probes cannot be named by a request. To make your own, copy a file and change it.

**Plan, judges, review and escalation belong to `full-team`, `lean` and `verify-first`,** not to the default. So do the specialists' review teams and the settings `MAX_ITERATIONS`, `VALIDATE_MAX_TOKENS`, `JUDGE_MAX_TOKENS` and the escalation settings. How those workflows work is described in [`docs/readme-archive.md`](docs/readme-archive.md) and in the workflow files' own comments.

Two shapes against the scripted test client, measured in model calls (`tests/test_docs.py` re-derives both rows):

| | happy path | never converges |
|---|---|---|
| `full-team` | 11 calls | 18 calls |
| `lean` | **8 calls** | **15 calls** |

## Deterministic Checks

A `check` node runs a function, not a model call. It is free and exact about what it measures. Checks register by name in `autornd/graph/checks.py`, and a workflow file names the ones it runs. Some of them (`tests/test_docs.py` checks that each one named here is registered):

| Check | What it does |
|---|---|
| `asks_anchored` | keeps only the asks a model quoted that really occur in the request. When none do, the whole request is the one ask |
| `blocked_on_unmet` | ends the run blocked when the answer refuses an ask it cannot meet, or says "none stated" for an ask the lookup holds no proof of absence for |
| `answer_ends_whole` | finds an answer that is cut off mid-sentence |
| `criteria_addressed` | does the answer visibly address each ask? |
| `numbers_consistent` | does the answer contradict a figure the request states? |
| `recompute_vote` | does a majority of blind recomputes agree with the answer's typed results? |
| `judges_agree` | folds every judge's verdict, so a loop cannot exit while one of them is still red. Not in the default |
| `totals_reconcile` | do the parts sum to a stated total? Registered, but no shipped workflow runs it |

A check decides only when a gate reads its result. Otherwise it is a note: recorded, and never blocking. The checks that compare words are notes in the shipped workflows, because word matching cannot see negation or paraphrase.

## Research

Grounding has two parts: your own documents, then outside sources.

**Your documents.** The research tier writes retrieval queries, the knowledge store returns excerpts, and the research tier writes a briefing from them and lists what they do not cover. With nothing ingested, it scopes the request, and that text is labelled as analysis, not fact.

**When a lookup runs.** One of these must hold, and a search model must be set:

- the request asks for its sources in words, such as "cite" or "with sources". This always runs a lookup;
- the live `needs_sources` switch says yes;
- triage rated the risk above low, grounding found something missing, and `needs_sources` did not say a confident no.

With no decision tier, the risk rating and the request's own words decide. Everything that is missing goes into one request.

**How a lookup works.** There is one lookup:

1. The search model is asked where the answer is written, not what it is. It names documents and a few words that stand near the answer.
2. The harness fetches those pages itself. It reads HTML, plain text, the text layer of a PDF and some office formats.
3. It hands on stretches of each page's own text. A short page is handed on whole. No model's summary is handed on.
4. Every stretch is recorded as a quote with whether it was found on its page, the time it was fetched and the sha256 of the bytes read. That record is `sources`.
5. Passages found on their pages are stored in the knowledge store, so a later run can reuse them without a new search.
6. In the default workflow and `verify-first`, when a page was read in full, the harness also searches its whole text for the words an answer would be printed with. A cheap model lists the words for each figure or verdict the request asks for, and code does the search. Where none of the words is on a page, the grounding says so, naming the page, its size and its hash. Only then may the answer say "none stated" for that ask. A page that was not read in full proves nothing, and a document that names the thing without giving a figure has the words on it, so such an ask still blocks the run.

**A fetch reads public web pages only:** `http` and `https`, public addresses, redirects included. A page that answers with a prove-you-are-a-person challenge is recorded as not read.

Settings, in `autornd/config.py`, each settable in `.env` in upper case:

- `lookup_avoid_unreadable`, on. A site that refuses twice is named to later lookups, which are told to give a copy that can be read. The list of such sites is kept for the whole server process, so one caller's refused fetches shape what the next caller's lookup is told.
- `SEARCH_MAX_TOKENS` and `SEARCH_MAX_TOKENS_CONSEQUENTIAL` cap one search call. The second applies at high and critical risk.

## Profiles and the Knowledge Store

A profile supplies the team and the project context: the roles, the subjects, your stack and constraints. `AUTORND_PROFILE` selects `profiles/<name>.yaml`. Six are tracked:

| Profile | What it is |
|---|---|
| `general` | the default when `AUTORND_PROFILE` is unset: a lead, a reviewer and a planner, with no subject list |
| `engineering` | the engineering team, see [Specialists](#specialists) |
| `example` | a worked example built on `engineering`: an IoT monitoring project |
| `studio` | a worked example that is not an engineering team: a content studio |
| `cupline`, `tier4` | fictional test corpora used by the measurements |

A profile can set `base: engineering` to build on that team and add its own `domains:` and `roles:`. The comments in `example.yaml` and `studio.yaml` show how.

The knowledge store is a local ChromaDB store. It ships empty.

```bash
python -m autornd.cli init-knowledge --profile example   # ingest that profile's documents
python -m autornd.cli ingest path/to/doc.md
python -m autornd.cli stats
python -m autornd.cli query "laser sensor wiring" -n 5
```

A profile's documents are read from `docs/<name>/`, where `<name>` is the profile's `name:` field in lower case with spaces as underscores, not its filename.

## Specialists

The engineering profile's roster (`profiles/engineering.yaml`), each with a domain, a system prompt and a tier (`tests/test_docs.py` checks this table against that profile):

| Specialist | Domain |
|---|---|
| Systems Architect | architecture, integration, trade-off analysis |
| Firmware Engineer | embedded systems, microcontrollers, RTOS, power management |
| Hardware Engineer | board design, bill of materials, schematic, thermal |
| Backend Engineer | services, APIs, databases, data pipelines |
| Frontend Engineer | UI frameworks, data visualisation, responsive design |
| Test Engineer | validation plans, test protocols, quality assurance |
| Supply Chain | cost, sourcing, compliance |

Triage assigns specialists for each run. In the default workflow one lead writes the answer. Review teams are used by `full-team` only.

## Auth, Limits and Deployment

**Authentication.** Send a credential as `Authorization: Bearer <token>`.

- **Neither `API_KEY` nor `JWT_SECRET` set:** the server serves loopback callers only, with no credential. A remote caller gets 403 and a sentence naming the fix.
- **`API_KEY` set:** a caller sending that key is served. Its runs belong to no user.
- **`JWT_SECRET` set:** `POST /api/auth/login` returns a token, and a caller sees only its own runs. Accounts are created with `POST /api/auth/register` from this machine only. `REGISTRATION_ENABLED=false` turns registration off.
- **With either one set, every caller needs a credential,** loopback callers too. Without one the answer is 401.
- `ALLOW_UNAUTHENTICATED_REMOTE=1` serves everyone with no authentication. Anyone who can reach the port can then spend your credits. It is logged at startup and reported by `/api/health`.
- `/api/health` answers everyone.

**Limits on the API path.** The defaults are in `.env.example`.

- `MAX_CONCURRENT_RUNS` caps the runs in flight in one process. One more is refused with 429. The same request through the same workflow from the same caller, while the first is still running, is refused with 409.
- `RUN_SPEND_CEILING_USD` bounds one run's spend. A call that would pass it is refused and the run stops with the reason in `error`.
- `RUN_TIME_BUDGET_SECONDS` bounds one run's time. A run that is running out ends `blocked`.

**Settings at runtime.** `PUT /api/settings` is for loopback callers only and accepts five settings: `max_iterations` (1 to 20), `escalation_max_tokens`, `escalation_recovery_attempts`, `autornd_profile` and `log_level`. A numeric setting can be lowered below the value the server started with and never raised above it. `POST /api/profiles/{name}` switches the profile, also from loopback only. Everything else is changed in `.env` and needs a restart.

**Deployment.** Run one server process on its database. A run lives in the process that started it: when the server starts, any run a stopped server left in flight is ended as `blocked` with the reason, and a second process on the same database would end the first one's live runs. Run it on a private network, or behind a reverse proxy with TLS. Behind a reverse proxy on the same host, set `API_KEY` or `JWT_SECRET` anyway: the no-key rule trusts the caller's address, and a proxy that does not pass `X-Forwarded-For` makes every caller look like this machine (measured: with the header the request is refused, without it the request is accepted). There is no rate limiting, and every run spends real money. The database is SQLite by default. It carries a schema version: at startup, numbered migrations bring an older database forward in place, and a database written by a newer AutoRnD is refused with a plain sentence instead of being opened. A release that must change a table adds a numbered step; it never edits one that has shipped.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/` | the dashboard |
| POST | `/api/workflows/sync` | submit and wait for the full record |
| POST | `/api/workflows` | submit, returns 202 and the id |
| GET | `/api/workflows` | list runs, the caller's own (`limit`, `offset`) |
| GET | `/api/workflows/offered` | the workflows a request may name |
| GET | `/api/workflows/{id}` | one run's full record |
| GET | `/api/workflows/{id}/doublecheck/estimate` | projected cost of a Double Check. Needs the premium tier |
| POST | `/api/workflows/{id}/doublecheck` | run the Double Check. Needs the premium tier |
| POST | `/api/auth/register` | create an account, from this machine only |
| POST | `/api/auth/login` | log in, returns a token |
| GET | `/api/auth/me` | the current user |
| GET · PUT | `/api/settings` | read settings, secrets redacted. Change the five runtime settings |
| GET | `/api/profiles` | the active and the available profiles |
| POST | `/api/profiles/{name}` | switch profile, from this machine only |
| GET | `/api/health` | health and per-tier model verification |
| GET | `/api/knowledge/stats` | knowledge store statistics |

A successful response wraps its payload in `{"data": ...}`. An error is `{"detail": "<a plain sentence>"}`.

## Evals

**The scenario runner costs money.** `python -m autornd.evals.cli` runs YAML scenarios against live models.

```bash
python -m autornd.evals.cli --repeat 5 --max-spend-sweep <USD>
python -m autornd.evals.cli --compare full-team lean
```

- A scenario is a request plus what a good run of it looks like (`evals/scenarios/`). The assertions are free comparisons.
- It runs the free preflight first and refuses to start if that fails.
- `--max-spend` caps one scenario run. `--max-spend-sweep` caps the whole invocation, and it has a default.
- Each run appends one JSON line to `evals/results/`, which is git-ignored.

**The professional question sets** are in [`evals/professional/`](evals/professional/): `questions.json`, `hard-questions.json` and `misleading-questions.json`. Each question names its rule and carries its source page, the key passage and the key answer. The keys are signed by the owner and frozen. `verify_keys.py` fetches each source and checks each passage with the harness's own quote check. It makes no model call, but it does use the network.

Answers to these sets are read by hand against the keys. A scorer is a screen, not the result. The reports are in [`docs/reviews/`](docs/reviews/).

## Testing

```bash
pip install -e ".[dev]"
.venv/bin/python3 -m pytest tests/ -q
```

The suite takes about 90 seconds to 3 minutes. It makes no network call and spends nothing: its settings are forced to placeholders, it does not read your `.env`, and a guard counts every non-loopback connection and reports the count at the end of the run. CI runs it on Python 3.11, 3.12 and 3.13, with an editable-install check and a Docker build.

## Limitations

- **A source that is wrong, with nothing in its text to show it, is not caught.** A stale official page or a sister rule, found word for word, is confirmed like any other.
- **A confirmation is about words on a page.** It means the answer's figures stand in a passage that was found. It does not mean the passage is the right rule.
- **A right figure can come with a wrong claim beside it.** The answers are long, and the checks read the figures a question asks for, not the rest. A misdefined term next to a right number was confirmed like any other.
- **A caution can be a false alarm.** When an older edition of a rule sits among the pages found, the delivery says the pages differ, including on an answer that is right.
- **Answers written in words are not checked the way figures are.** The confirmations and most cautions read numbers. A wrong condition in prose can pass unseen.
- **The answer-step prompt can trip a safety filter on some frontier models.** It was written for inexpensive models. If you put a frontier model in the answer seat, try one request first; a reply stopped by a content filter ends the run as blocked.
- **With no key set, a same-host proxy that does not pass `X-Forwarded-For` serves everyone.** The loopback rule reads the caller's address. Set `API_KEY` or `JWT_SECRET` whenever anything other than this machine can reach the server.
- **Some sites refuse to be read.** A page behind a login or a challenge, or a scanned PDF, stays unread, and the delivery says so. A page that does not answer within its time limit is unread too, and an answer built on few pages was wrong more often in our measurements.
- **On new questions it is less often right than a frontier model asked directly,** and its misses scatter: the same question can be right on one run and wrong on the next. See `docs/MODELS.md`.
- **The recompute vote cannot see an omission,** nor an error every sample shares. It is off unless a request is judged to need a calculation.
- **Word-matching checks cannot see negation or paraphrase.** That is why they are notes.
- **No code execution.** AutoRnD produces text.
- **No streaming.** The sync endpoint blocks. Use the async endpoint and poll for long runs.
- **No roles.** Runs are kept apart for each user. There are no admin or team permissions.
- **Quality follows the models you choose,** and every run calls a paid API.

## Contributing

Pull requests are welcome, through `https://github.com/ohioy000/autornd-os`, against `main`. See `CONTRIBUTING.md`. Anything with a right answer belongs in a check, not in a prompt.

**Keeping this README true.** It describes mechanisms. It does not restate prices, result figures or ruling numbers. Where it lists something the repository defines (workflows, tiers, checks, specialists), `tests/test_docs.py` checks the list against its source, and the badge's test count is checked against the suite. Add a figure to this file only if a test derives it.

Sections of the earlier README that tell the history and describe the `full-team` workflow are kept in [`docs/readme-archive.md`](docs/readme-archive.md).

## License

MIT
