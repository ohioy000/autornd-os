# AutoRnD

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-854%20passing-brightgreen.svg)](#testing)

**An open-source harness for engineering teamwork, aimed at being frugal and accurate at the same time.**

You describe an engineering objective. AutoRnD grounds it in your documentation, looks up what your documentation does not cover and cites the sources, plans the work, builds it, checks it against criteria written in advance, and either finishes or tells you exactly what stopped it.

It starts from engineering R&D, but nothing in it is specific to engineering. The mechanisms are a workflow you define, a research phase that establishes what is actually known, checks that cost nothing, and evals that tell you whether a change helped.

**You choose every model.** AutoRnD ships no defaults and recommends none.

---

## Table of Contents

- [Frugal and accurate are the same lever](#frugal-and-accurate-are-the-same-lever)
- [What AutoRnD Produces](#what-autornd-produces)
- [Research](#research)
- [Workflows Are Files](#workflows-are-files)
- [Deterministic Checks](#deterministic-checks)
- [Model Tiers](#model-tiers)
- [Engineering Specialists](#engineering-specialists)
- [Review Team Composition](#review-team-composition)
- [Escalation Autopsy](#escalation-autopsy)
- [Evals](#evals)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Project Profiles](#project-profiles)
- [Knowledge Store](#knowledge-store)
- [Lead + Review Implementation](#lead--review-implementation)
- [Double Check](#double-check)
- [Multi-User and Authentication](#multi-user-and-authentication)
- [Settings Dashboard](#settings-dashboard)
- [API](#api)
- [Worked Example](#worked-example)
- [Project Structure](#project-structure)
- [Cost and Performance](#cost-and-performance)
- [Testing](#testing)
- [Deployment](#deployment)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License](#license)

---

## Frugal and accurate are the same lever

These look like opposing goals and are not. Every question moved out of a model is both cheaper *and* more reliable, so the two improve together:

- **Grounding** removes guessing about facts. A model told what your system actually is does not invent one.
- **Research** removes guessing about the world, with sources attached.
- **Deterministic checks** remove guessing about arithmetic and consistency. They cost nothing and cannot be wrong about what they measure.
- **A defined workflow** removes guessing about process. Skip a phase a request does not need and you pay for neither the phase nor its mistakes.

What is left for a model is judgement, which is what models are for. The rest is constraint, and constraint is cheap.

## What AutoRnD Produces

**AutoRnD produces engineering artifacts as text.** It has no repository, shell, or build tools. It does not compile, run, deploy, or edit files. Every phase returns a typed object whose content is written work — a plan, a design, a schema, a procedure, a calculation — which you or your pipeline then apply.

Every prompt states this contract in both directions: producing phases are told their response *is* the deliverable, and assessing phases are told that "it has not been run" is not a defect. Without both halves stated, a capable model asked to "implement" correctly reports that it cannot reach your filesystem, the validator correctly rejects an implementation that does not exist, and the loop burns every iteration before escalating.

The same reasoning shapes the plan: **success criteria must be verifiable by reading the implementation.** `reconnect loop applies exponential backoff capped at 60s with jitter` can be checked. `reconnects within 30s in production` cannot, and will stall the loop forever. A plan that cannot state real criteria must return `ready: false` with the reason.

## Research

### Search is the expensive tier — treat it that way

Once every call was actually priced, search turned out to be **61% of a full
workflow** and **98% of a grounding run** ($0.72 of $0.74 across eight
sectors). Nothing else comes close, so four things bound it, in the order they
take effect:

- **Low-risk work does not look anything up.** A wrong answer in copy,
  configuration or presentation costs a correction, not a board revision. The
  floor sits below medium deliberately: both confabulations that justify
  research at all — a charger IC named confidently and wrongly, ERP quoted as
  EIRP — were selection work at medium risk.
- **Only gaps that change the answer are looked up.** The briefing lists
  everything the documentation does not cover, and separately marks which of
  those a wrong assumption would actually change the answer for — a figure that
  sets a dimension, a limit that decides compliance, a convention that decides
  a unit. Often that list is empty. Every gap is still shown to the engineer;
  only the blocking ones cost money. This is the change that mattered most: the
  old gate was "did a model name any unknowns", and a model asked what is
  unknown always names something, so research fired on every workflow whether
  or not anything needed it.
- **One request, carrying every gap.** The fee is charged per request, not per
  question, so five gaps asked separately cost five fees. They are bundled into
  one question with a larger token budget instead.
- **The store is asked before anyone is paid.** Findings are ingested, so a fact
  looked up once is local for every workflow afterwards. The cheapest lookup is
  the one already answered — and it is the more consistent one, since it returns
  the figure already cited instead of re-asking and hoping for the same answer.

### The token budget is the dial, and it is measured

One measured search model billed **$15.00 per million output tokens plus about
$0.007 a request**, and filled whatever cap it was given (2907 of 3000). At a
3000-token cap the fee is 13% of the cost and tokens are 87% — so "it is priced
per call, give it the maximum" is the opposite of what the billing does. Check
your own model's rates; the shape of the result is what transfers, not the
number.

Accuracy tracks that budget almost linearly. Graded against published figures
across the eight `evals/grounding` sectors:

| total output tokens | figures recovered | search cost, 8 sectors |
|---|---|---|
| ~4800 (4 separate lookups) | 7/8 | $0.72 |
| ~2900 | 5/8 | $0.32 |
| ~1400 | 3/8 | $0.17 |

Roughly one sector per 800 tokens. Tokens buy figures, so the budget is a dial
rather than waste to trim — which is why it scales with consequence:

| risk | lookup | budget | cost |
|---|---|---|---|
| low | none | — | $0 |
| medium | one | `SEARCH_MAX_TOKENS` (1500) | ~$0.03 |
| high, critical | one | `SEARCH_MAX_TOKENS_CONSEQUENTIAL` (4000) | ~$0.07 |

Set both to the same number for a flat budget. Re-measure after changing
either: `--scenarios evals/grounding` grades against the published figures and
reports spend per tier, so the trade is a table rather than an argument.

Run `python -m autornd.evals.cli --max-spend 0.50` on anything that touches this
tier. Reports break spend down per tier, so you can see where it went:

```
spend by tier: search $0.0885, engineering $0.0332, architecture $0.0216,
               research $0.0020, triage $0.0001
```


This is the part that makes AutoRnD more than a model with a checklist, and it exists because of a measurement rather than a theory.

Asked which charger IC a specific board uses, a capable model answered `IP5306` — a power-bank part that does not do that job — in bold, with no hedge. Asked the maximum EIRP in the EU 868 MHz band, the same model answered `25 mW (+14 dBm EIRP)`, conflating ERP with EIRP: two units 2.15 dB apart, and the difference between a compliant transmitter and a failed certification.

Both answers sounded exactly as certain as its correct ones. It was also right about an obscure humidity sensor's accuracy to one decimal place. **There is no confidence signal to gate a lookup on** — and no deterministic check would have caught the RF error either, because `14 dBm` is a perfectly well-formed value. Only a source catches a wrong unit convention.

So research runs on every workflow, and the loop is driven by gaps rather than curiosity:

```
brief from your documentation  ──▶  what it does not cover  (the gaps)
                                              │
                            the gaps become the search queries
                                              │
                          search ──▶ findings, with citations
                                              │
                    ingested, so the next workflow has them locally
```

Nothing is searched that the briefing had not already established was missing, and a fact is looked up once. Two disciplines are enforced rather than hoped for:

- **A finding carries its sources or it is marked unverified.** An uncited answer is exactly the failure mode this exists to prevent.
- **Unverified findings are shown to you and never stored.** A guess must not quietly become permanent context that later runs treat as established.

One failed lookup does not sink a workflow — three facts out of four beats aborting, and the missing one stays visible as a gap. Lookups are bounded.

With no documentation ingested, research scopes the request instead: restating the objective, listing what the request leaves unspecified, and stating the assumptions being made so they can be challenged rather than buried in a plan. That output is labelled as analysis, not fact.

**Choosing a search model.** `.env.example` describes what to look for, from comparing several on real datasheet questions: does it name the document rather than the subject (`RP002-1.0.3`, not "the LoRaWAN spec"), does it say what *kind* of number it found (a programmable regulation value is not an absolute maximum rating), and does it admit when a figure is not universal. Note also that search models bill per request as much as per token, so a headline rate several times higher often lands near parity on the short lookups research actually makes.

## Workflows Are Files

The sequence of phases is data, not code. A workflow is a graph of nodes in YAML, with three kinds:

| kind | what it is | cost |
|---|---|---|
| `ai` | one model call, routed to a tier, validated against a typed verdict | paid |
| `check` | a deterministic function over prior outputs | **free** |
| `gate` | a condition that lets the run continue, routes it to another node, or ends it with a terminal status | **free** |

```yaml
- id: validate
  kind: ai
  tier: engineering
  specialist: test_engineer
  prompt: validate
  schema: ValidateVerdict
  max_tokens: validate_max_tokens
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

Conditions are a deliberately small language — one comparison over a dotted path — rather than `eval`, because a workflow file is configuration and configuration must not execute code.

Four workflows ship:

| workflow | shape |
|---|---|
| `engineering-rnd` | the full team: feasibility, domain review, escalation, risk-scaled review |
| `lean` | plan, build, verify. No review team, no escalation — but it keeps the free checks |
| `triage-only` | classification and grounding, two calls, for measuring triage quality cheaply |
| `triage-classify` | one node — triage alone. A calibration sweep costs a fraction of a cent per call instead of a whole workflow, which is what makes running one over dozens of scenarios affordable |

Select with `AUTORND_WORKFLOW`. Copy one and change it — that is the point of it being a file. Measured against each other with mocks, in under a second, for nothing:

| | happy path | never converges |
|---|---|---|
| `engineering-rnd` | 10 calls | 17 calls |
| `lean` | **7 calls** | **14 calls** |

Writing the sequence down also forced out rules that had been implicit in code: the test engineer validates the work and so does not build it or review the build (the `builders` and `peers` rosters), feasibility only reviews a plan the architect declared ready, and escalation runs because a loop gave up rather than because its dependencies happened to be satisfied.

## Deterministic Checks

A `check` node runs a function instead of a model call. Free, instant, and correct about what it measures — three properties no prompt has. Five ship:

| check | catches |
|---|---|
| `criteria_addressed` | work that does not visibly address a success criterion |
| `numbers_consistent` | the plan saying 60s where the implementation says 600s |
| `totals_reconcile` | parts that do not sum to a stated total |
| `judges_agree` | a loop exiting while any judge it produced is still red |
| `blocked_on_unmet` | an implementer refusing on a criterion the plan itself demands — routed to escalation rather than iterated against |

They run **before** the paid validator, so an implementation that never mentions a criterion costs nothing to reject.

They are calibrated rather than assumed. Measured against realistic implementation text, criteria that are genuinely addressed score 71–100% of their terms and unaddressed ones score 0–33%, so the 50% threshold sits in the gap. The case most worth catching — text that names every topic while committing to nothing — scores under 33% and fails.

Their limits are documented and tested rather than papered over. **Term overlap cannot see negation**: an implementation stating it *removed* the backoff scores highly against a criterion requiring backoff. That gap belongs to `numbers_consistent`, which catches the contradiction. And no check can tell you a plan's own numbers are physically wrong — that is research's job.

## Model Tiers

AutoRnD routes each phase to a named tier and will not start until every required tier names a model.

**Required** — these run on every workflow:

| Tier | Phases | Optimise for |
|---|---|---|
| **Engineering** | implement, validate, review, feasibility | Capability at volume. This tier dominates your bill. |
| **Architecture** | plan, critical review | Reasoning quality. A weak plan wastes every token after it. |
| **Triage** | triage | Price, and reliably valid JSON. |
| **Escalation** | failure autopsy | Depth on long, messy input. Rarely called. |
| **Research** | grounding and briefing | Faithful summarisation. It must not invent facts. |
| **Search** | outward lookups | Sources, and precision about what kind of figure it found. |

**Optional** — each turns a feature off when empty:

| Tier | Job |
|---|---|
| **Ranker** | orders retrieved documentation by usefulness. Without it, retrieval falls back to embedding distance |
| **Premium** | the independent pass on work that cannot be recalled. Falls back to the architecture tier when empty |

### Choose non-reasoning models for the tiers that fill a schema

Every phase returns a typed verdict, and a model that reasons at length before
answering can spend its whole output budget on the reasoning and emit nothing.
That is not a hypothetical: measured on one rollout request, one candidate
architecture model returned `{"plan": "...", "success_criteria": ["...", "..."]}`
— a schema-shaped stub, at `finish_reason=stop`, with and without a worked
example in the prompt — and one candidate engineering model spent all 16,384
tokens reasoning and returned no text at all.

The harness handles both correctly. A stub is caught by the placeholder
validator and a silent model is reported with its cause:

```
model returned no text (finish_reason=length, completion_tokens=16384 of
max_tokens=16384 — a reasoning model can spend its whole budget before
emitting an answer; raise max_tokens or use a non-reasoning model for this tier)
```

So the failure is loud, cheap and correctly attributed rather than silent. But
it is still a failed run, so:

- **Engineering, Architecture, Triage** fill schemas on every workflow. Prefer
  models that answer directly. If you want a reasoning model here, give it
  headroom well above the tokens its answer needs.
- A model can be strong at one of these and weak at another. Measured on the
  same request, one reasoning model returned a schema stub when asked to
  **plan** and, as the independent reviewer, caught a real flaw nobody had
  named — that a rename and a drop in one migration script make the observation
  window between them impossible. Judge a tier by the job, not by the model's
  reputation.
- **Escalation** is the one tier where reasoning earns its keep — it reads a
  long failure log and is rarely called, so it ships with a 16k budget.
- **Validate** is capped separately (`VALIDATE_MAX_TOKENS`, default 8000)
  because it judges work rather than redoing it. An unbounded validator once
  produced 15k output tokens for a green/red verdict. 3000 proved too tight for
  a reasoning model, which is how that default was found.

A ceiling is billed only when it is used, so raising one costs nothing on the
runs that were already fine.

All tiers accept any model your provider serves, in `provider/model` form. The client speaks the OpenAI chat-completions protocol. On startup AutoRnD validates every configured id against your provider's catalogue and reports it:

```
Model check: 7/7 models available
```

Models a provider serves but omits from its chat-model listing — rerankers, embedding models — are confirmed individually rather than reported missing. If anything cannot be verified, `/api/health` reports `degraded` and names the tiers.

### A model id is not a system — pin the provider when it matters

A provider serves a model id on its own hardware, quantization and settings, and
one id is routed across many of them. Measured on a single 108-call sweep, the
triage tier was served by **five** providers: Alibaba, AtlasCloud, DigitalOcean,
OpenInference and StreamLake.

That is not cosmetic. The same 36-sector calibration suite, the same prompt, the
same scenarios:

| provider | sectors passing | cost | wall clock |
|---|---|---|---|
| StreamLake (pinned) | 33/36 | $0.0185 | 1102s |
| unpinned, five mixed | 30/36 | $0.0135 | 853s |
| OpenInference (pinned) | 28/36 | $0.0015 | 303s |

Twelve times the price bought five sectors of accuracy and cost 3.6x the
latency. And the cheap serving did not fail randomly — it under-classified risk
on `water_treatment`, `building_services` and `legal_ops`, every repetition,
which is the dangerous direction.

This is the one place where **frugal and accurate are not the same lever.**
Taking a question away from a model is free accuracy. Buying a cheaper serving
of the same model is not: it is a trade, it is silent, and it lands on exactly
the judgement you least want degraded.

So:

- **Measuring anything?** Pin `OPENROUTER_PROVIDER_ORDER`. An unpinned eval
  score is partly a record of who answered, which is how a 35/36 became a 29/36
  with no code change in between.
- **Running work that matters?** Pin, and choose on measured quality rather than
  price. `--scenarios evals/scenarios/wide` scores a provider in ten minutes for
  under two cents.
- **Leave it unset** only when availability beats reproducibility.

Pins are per tier, because they have to be — tiers run different models and no
provider serves them all:

```
OPENROUTER_PROVIDER_ORDER=triage:StreamLake,search:
```

pins triage and leaves search free to route. A bare name applies to every tier;
a tier named with an empty value opts out of that default.

**Routing can depend on the run.** `tier_when` makes a node's tier conditional, so low-risk work does not wake a reasoning model to plan a layout change:

```yaml
- id: plan
  tier: architecture
  tier_when:
    "triage.risk == 'low'": engineering
```

## Engineering Specialists

Seven specialists, each with a domain, a system prompt, and a tier:

| Specialist | Domain |
|---|---|
| Systems Architect | architecture, integration, trade-off analysis |
| Firmware Engineer | embedded systems, microcontrollers, RTOS, power management |
| Hardware Engineer | board design, bill of materials, schematic, thermal |
| Backend Engineer | services, APIs, databases, data pipelines |
| Frontend Engineer | UI frameworks, data visualisation, responsive design |
| Test Engineer | validation plans, test protocols, quality assurance |
| Supply Chain | cost, sourcing, compliance |

Triage assigns them per workflow. Every specialist's grounding can be overridden in your [project profile](#project-profiles).

### The roster is a default, not a limit

`roles:` in your profile declares the roles your team actually has, and triage
is offered the shipped seven plus yours. A role nobody declared still resolves —
it becomes a generalist carrying that role's name, logged once so you know to
declare it — because failing a whole workflow over a role name is worse than
acting as the role and saying so.

This is not hypothetical. Asked to staff a firmware signing-key rotation, triage
returned `infrastructure_engineer`, which this harness does not ship, and it
returned the domain `documentation` in the roles field. A legal team wants a
paralegal and a marketing team a copywriter, and no shipped list of engineering
roles will ever contain them.

A declared role is built by the same path as a shipped one, so it inherits the
project context and the output contract rather than being a second-class prompt.

Two composition rules are enforced in code rather than left to a model, because they are not judgement calls: **risky work gets a test engineer, and work spanning domains gets an architect.** Measured over five live runs, triage omitted the test engineer on safety-relevant hardware work three times in five.

## Review Team Composition

| Risk | Team | Mode |
|---|---|---|
| Critical | all specialists | Adversarial |
| High | domain specialists + test + architect | Adversarial |
| Medium | domain specialist + test or architect | Standard |
| Low | single relevant specialist | Standard |

The team is derived from whoever triage assigned, and risk decides how much
scrutiny is added on top: a test engineer above `low`, an architect from `high`,
and at `critical` the declared lead of every domain in play. It used to be a
fixed table that returned *every* role at `critical` — which, measured across
thirty-six sectors, meant seven engineers reviewing a records retention
schedule. That is the same failure twice, since a reviewer with nothing to say
costs a call and adds no accuracy.

Because risk sets team size, it sets cost, and it is graded on the consequence
of being wrong rather than on how technical the subject sounds. Triage asks two
questions in order: can a person be harmed or a regulated requirement be
breached — structural loading, food contact, sterility, pressure, electrical
code, emissions — and if not, has anything been committed to yet. Installing or
wiring something is `high`; choosing what to buy is `medium`, reversible until
the order is placed.

Two clauses exist because a sweep across thirty-six sectors found them missing.
A **governing document** — a protocol, schedule, policy or setpoint band that
will be followed repeatedly — is judged by what happens when it is followed, not
by the fact that it is a document; without that, a return-to-play progression
and a statutory retention schedule both read as `low`. And **recall** is asked
on its own axis: a signed rollout to 40,000 devices harms nobody and breaches
nothing, so it is `high`, and it cannot be taken back, so it sets
`unrecallable` and earns one extra independent pass on a model that has seen
none of the reviews above it. Scale alone does not trigger it; the test is
whether the thing can be recalled.

Getting this wrong is expensive in both directions, so it is measured in both.
Fourteen calibration scenarios spanning civil, biotech, aerospace, optics,
acoustics, materials and real-time control assert a floor *and* a ceiling on
each: `risk_at_least` catches under-classification, which buys one reviewer
where the work needed seven, and `risk_at_most` catches the drift that follows
from fixing the first. An earlier build passed every floor while classifying a
VLAN addressing scheme, a lens choice and a bearing tolerance as `high`, and
never once assigned `low` in twelve requests. A ceiling on a case where two
readings are genuinely defensible — occupational noise exposure is both a
health limit and a regulated one — is left off with the reason recorded, rather
than written as `risk_at_most: critical`, which asserts nothing.

Validation adapts too: it injects checks for the domains a request actually touches, as lenses for judging the stated criteria rather than as extra criteria of their own. A copy change is never asked whether its pin assignments conflict.

## Escalation Autopsy

When the implement/validate loop exhausts its budget, a reasoning model performs a structured autopsy: it reads the full failure log, and either issues a recovery directive that drives fresh attempts with the failed context scrubbed, or stops the run and says a human is needed.

The escalation model never implements. It diagnoses and directs; the engineering tier executes.

Give it room. Reasoning models spend their token budget thinking before they emit anything, so too tight a ceiling returns an empty reply with `finish_reason=length` — and the autopsy fails on exactly the runs that needed it.

## Evals

A scenario is a request plus what a good run of it looks like, written before the run:

```yaml
id: triage_hardware
workflow: triage-only
request: "Route the voltage from the PCB to the laser sensor on the cup-style food packaging machine"
expect:
  domains_include: [hardware]
  risk_at_least: high
  specialists_include: [hardware_engineer, test_engineer]
  max_calls: 2
```

Every assertion is a set or integer comparison — no judge, no cost, milliseconds.

```bash
python -m autornd.evals.cli --repeat 5
python -m autornd.evals.cli --compare engineering-rnd lean
```

**Evals repeat by default, because models are stochastic.** The same triage request passed on one run and failed on the next, so a single result is an anecdote. Reports give a pass rate and name the flaky assertion:

```
scenario                    rate  calls    secs   flaky assertions
triage_backend               5/5      5    18.5
triage_frontend              5/5      5    19.8
triage_hardware              5/5      5    27.4
```

**Runs are bounded.** A call ceiling and a wall-clock deadline, both recorded as failures rather than hangs, because `MAX_ITERATIONS` bounds loops and not spend — a wide fan-out makes many calls per iteration. Scenarios may set their own timeout, since a reasoning model taking two minutes to correctly decide it cannot plan is slow rather than broken. A scenario whose expectations a workflow cannot answer is skipped with the reason, not failed.

**Results persist as they are produced.** Every unit appends one JSON line to
`evals/results/<utc-timestamp>-<suite>.jsonl` — overridable with
`--results-file` — flushed the moment it is written, so an interrupted sweep
keeps everything it paid for rather than discarding it at the last hurdle. A
record carries the scenario, repetition, cost and calls by tier, the assertion
outcomes, the terminal status, **every node's typed verdict**, and **which
provider served each tier**. One header line at the top records the run's
configuration — the tier-to-model map, the provider pins and the spend caps — so
a stored result can be priced against its serving months later without
re-running anything. Results are gitignored: they reach the repo only by
deliberate commit.

**Spend is bounded twice.** `--max-spend` caps one scenario-run, which is a repetition rather than an invocation — 36 scenarios at 3 repetitions with `--max-spend 0.25` is a $27 ceiling, not a $0.25 one. `--max-spend-sweep` caps the whole invocation: every scenario, every repetition and every compared workflow against one budget. It defaults to **$1.00** and takes `none` to disable. Set both and the sweep cap is exact — a unit that cannot be guaranteed to fit is never started, so nothing is killed part-way. Set only the sweep cap and the crossing unit is stopped by the client's own ceiling instead, which overshoots by however many calls were already in flight. Units that never start are skipped with their reason and excluded from the pass rate, so a truncated sweep reports honest partial results and exits zero.

Splitting triage into its own workflow is what made triage quality measurable: **30 seconds and a hundredth of a cent**, against sixteen minutes for a full-pipeline sweep. That is what caught safety-relevant hardware being classified below `high` risk three times in five.

## Prerequisites

- **Python 3.11+**
- **An API key** for any OpenAI-compatible provider
- **Docker** (optional)

## Quick Start

```bash
git clone https://github.com/ohioy000/autornd-os.git
cd autornd-os

cp .env.example .env
# Add your API key and choose a model for each required tier

pip install -e .
uvicorn autornd.main:app --port 8100
```

If a required tier is unset, AutoRnD refuses to start and says which:

```
AutoRnD is not configured — no model is set for 4 of 6 tiers.

  MODEL_ARCHITECTURE   planning and critical review — heavyweight tier
  MODEL_ESCALATION     failure autopsy and recovery — reasoning tier
  MODEL_RESEARCH       grounds the request in documentation and briefs every phase
  MODEL_SEARCH         looks up facts the documentation does not cover, with sources
```

### Docker

```bash
docker build -t autornd .
docker run -p 8100:8100 --env-file .env autornd
```

## Configuration

Every setting lives in `.env` — see [`.env.example`](.env.example), which documents all of them and explains what to optimise each tier for.

```bash
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1   # or any compatible endpoint

MODEL_TRIAGE=             # required
MODEL_ENGINEERING=        # required
MODEL_ARCHITECTURE=       # required
MODEL_ESCALATION=         # required
MODEL_RESEARCH=           # required
MODEL_SEARCH=             # required

MODEL_RANKER=             # optional
MODEL_PREMIUM=            # optional, enables Double Check

AUTORND_WORKFLOW=engineering-rnd
MAX_ITERATIONS=5                      # 1-20
VALIDATE_MAX_TOKENS=8000
SEARCH_MAX_TOKENS=1500                # medium-risk lookup budget
SEARCH_MAX_TOKENS_CONSEQUENTIAL=4000  # high and critical

API_HOST=127.0.0.1        # containers need 0.0.0.0
```

The block above is illustrative and not exhaustive. **`.env.example` is the
single source of truth for settings and their defaults** — it documents every
one, and explains what each value was measured against.

The bind address defaults to loopback. AutoRnD has no rate limiting and spends real money, so do not expose it directly.

## Project Profiles

AutoRnD ships with no domain assumptions. You bring the context.

Two worked profiles are tracked. [`profiles/example.yaml`](profiles/example.yaml) is an industrial IoT project; [`profiles/studio.yaml`](profiles/studio.yaml) is a content studio, and exists to show the same machinery running a team that is not a team of engineers — every domain and role in it is one this harness does not ship, and none of it needed a code change. Both are commented as teaching files.

```yaml
# profiles/packaging-line.yaml
name: "PackagingLine"
description: "Control and vision systems for a cup-style food packaging machine"
stack:
  - "Servo-driven indexing conveyor"
  - "Laser presence sensors on the fill station"
  - "PLC control with an industrial PC supervisor"
constraints:
  - "Washdown environment, IP69K on anything in the fill zone"
  - "Food-contact materials must be FDA compliant"
specialists:
  hardware_engineer:
    context: "24V DC distribution, shielded sensor runs, washdown-rated connectors"
domains:
  mechanical:  hardware_engineer
  optics:      hardware_engineer
  food_safety:
    lead: supply_chain
    checks:
      - "Is every food-contact material identified with its compliance basis?"
roles:
  quality_engineer:
    name: "Quality Engineer"
    domain: "Validation protocols, compliance evidence"
    tier: engineering
    expertise: "Your domain: IQ/OQ/PQ protocols and compliance evidence."
```

### Domains are an open vocabulary

The `domains:` mapping names the domains your work actually has, and who leads
each one. It is additive: triage is offered the seven shipped defaults plus
yours, and may name a domain that appears in neither when nothing fits.

This is deliberate. A closed list does not produce an honest "none of these" —
it produces the least-wrong label. Measured across twelve subjects with the
enum enforced, nine had no fitting value and eight of those nine came back as
`hardware`: civil engineering as "hardware", a 5 ms latency budget as
"firmware, hardware", buffer chemistry as "documentation". Triage was not
guessing badly; it was picking from a list without the answer in it.

An unmapped domain still resolves a lead — the assigned specialist, falling
back to the systems architect, whose job is cross-domain work anyway — so
naming a new domain degrades into a sensible default rather than an error.
Names are normalised, so `food safety` and `Food_Safety` are one domain.

The documentation directory is derived from the profile's **`name:` field**, lowercased with spaces replaced by underscores — not from the filename. A profile named `"PackagingLine"` reads from `docs/packagingline/`. A missing directory is skipped silently, so check `python -m autornd.cli stats` if your docs do not seem to load.

Select with `AUTORND_PROFILE`, or switch at runtime in the Settings tab.

## Knowledge Store

Documentation is chunked into a local ChromaDB store and retrieved per workflow.

```bash
python -m autornd.cli init-knowledge --profile packaging-line
python -m autornd.cli ingest path/to/doc.md
python -m autornd.cli stats
python -m autornd.cli query "laser sensor wiring" -n 5
```

Retrieval pulls a wide candidate set and ranks it down, because embedding distance reliably finds material *about* the right subject and is much worse at ordering it. Research findings are ingested alongside your documents, tagged `research`, so a looked-up fact is local afterwards.

The store ships empty. Until you ingest something, research scopes requests rather than grounding them.

## Lead + Review Implementation

**The problem it solves:** parallel specialists produce contradictory designs — one plans a polling architecture while another plans an event-driven one. The validator rejects the merged result and the loop spends every iteration on irreconcilable designs.

One domain lead implements alone, producing something coherent. The other builders then review it in parallel with a scoped prompt: *review from your domain perspective, flag concerns, do not produce an alternative design.* Any critical concern flips the implementation red and is passed to the validator.

## Double Check

An optional independent review by the premium tier, triggered by the user after a workflow reaches a terminal state. Set `MODEL_PREMIUM` to enable it; leave it empty and the button never appears. It estimates cost first, then sends the full workflow to a reviewer prompted as an independent senior engineer who has not seen the previous review.

## Multi-User and Authentication

Optional JWT authentication with per-user workflow isolation on both list and detail endpoints.

Input rules: username 3–64 characters, a valid email address, password at least 8 characters. Raise the floor in your own deployment if you want a stricter policy.

```bash
JWT_SECRET=              # generated at startup if empty, which logs everyone out on restart
REGISTRATION_ENABLED=true
API_KEY=                 # optional static bearer token for programmatic access
```

**Auth priority:** a valid JWT scopes workflows to that user; otherwise an `API_KEY` match grants anonymous access; otherwise everything is open. With no auth configured, any caller can see every workflow and spend your credits.

## Settings Dashboard

The Settings tab explains what each tier is for, shows a live verified / not-found / not-set badge per model from `/api/health`, and lets you change what can safely change at runtime.

| Setting | Validation |
|---|---|
| `max_iterations` | 1–20 |
| `validate_max_tokens`, `search_max_tokens`, `escalation_max_tokens` | integer |
| `escalation_recovery_attempts` | integer |
| `autornd_profile`, `autornd_workflow` | reloads on change |
| `log_level` | DEBUG, INFO, WARNING, ERROR, CRITICAL |

Model ids, database URL, host/port, ChromaDB path and auth secrets are read-only — they need a restart. Secrets are redacted to their last four characters.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard |
| POST | `/api/workflows/sync` | Submit and block until complete |
| POST | `/api/workflows` | Submit asynchronously |
| GET | `/api/workflows` | List (scoped to the caller) |
| GET | `/api/workflows/{id}` | Detail with phase verdicts (scoped to the owner) |
| GET | `/api/workflows/{id}/doublecheck/estimate` | Projected cost |
| POST | `/api/workflows/{id}/doublecheck` | Run the premium review |
| POST | `/api/auth/register` | Create an account |
| POST | `/api/auth/login` | Log in, returns a JWT |
| GET | `/api/auth/me` | Current user |
| GET · PUT | `/api/settings` | Settings, secrets redacted |
| GET | `/api/profiles` | Active and available profiles |
| POST | `/api/profiles/{name}` | Switch profile |
| GET | `/api/episodes` | Workflow outcome history |
| GET | `/api/health` | Health plus per-tier model verification |
| GET | `/api/knowledge/stats` | Knowledge store stats |

Every workflow response carries an `error` field: `null` on a healthy run, and otherwise why the run stopped — an infrastructure fault, a plan the architect judged unready, or an escalation needing a human. A blocked workflow always says why.

## Worked Example

```bash
curl -X POST http://localhost:8100/api/workflows/sync \
  -H "Content-Type: application/json" \
  -d '{"request": "Route the voltage from the PCB to the laser sensor on the cup-style food packaging machine"}'
```

Triage classifies it `hardware`, risk `high`, and assigns a hardware engineer, a test engineer and the architect. Research briefs from your documentation, finds it does not specify the sensor's supply range, looks that up and cites the datasheet. The architect plans against both, with success criteria that can be checked by reading. The lead implements; the other builders review it; the free checks confirm every criterion is addressed and that no value contradicts the plan; the test engineer validates. Review scales to the risk level.

If the request had been too underspecified to plan — as a battery-threshold change with no stated chemistry was in testing — the architect returns `ready: false`, and the workflow blocks in two calls with the reason attached, rather than discovering it five iterations later.

## Project Structure

```
autornd/
  main.py                 # FastAPI entry + startup model check
  config.py               # Settings, tier requirements, startup errors
  profiles.py             # Project profile loader
  cli.py                  # init-knowledge, ingest, stats, query
  graph/
    spec.py               # Workflow graph: nodes, loops, validation
    executor.py           # Sequencing, gates, loops, handoffs
    adapter.py            # Maps nodes onto phases, resolves rosters
    checks.py             # Deterministic checks
    conditions.py         # The small condition language
  evals/
    scenario.py           # Scenarios and expectations
    assertions.py         # Free scoring
    runner.py             # Bounded runs, repetitions, pass rates
    cli.py                # python -m autornd.evals.cli
  engine/
    workflow.py           # Drives the graph; persists phases
    phases.py             # Phase implementations, output contracts
    review_composition.py # Risk-based review team selection
  knowledge/
    research.py           # Outward lookups, citations, persistence
    context.py            # Grounding: retrieve, rank, brief, research
    store.py              # ChromaDB ingestion + retrieval
    episodic.py           # Workflow outcome memory
  models/                 # Verdict schemas, ORM, users
  specialists/            # Specialist registry + profile-driven prompts
  routing/openrouter.py   # Multi-model client, rerank, model validation
  api/                    # REST endpoints, auth, dashboard
workflows/                # engineering-rnd, lean, triage-only, triage-classify
evals/scenarios/          # Scenario definitions
profiles/                 # Profile YAML
docs/                     # Your documentation, per profile
tests/                    # 854 tests
```

## Cost and Performance

AutoRnD publishes no dollar figures. Prices change, and they depend entirely on models you chose — multiply the call counts by your provider's rates and check its usage dashboard for the truth.

Model calls for a single-iteration workflow:

| Risk | Total | Triage | Plan | Feasibility | Implement | Domain review | Validate | Review |
|---|---|---|---|---|---|---|---|---|
| Low | 6 | 1 | 1 | 1 | 1 | — | 1 | 1 |
| Medium | 8 | 1 | 1 | 2 | 1 | — | 1 | 2 |
| High | 14 | 1 | 1 | 3 | 1 | 2 | 1 | 5 |
| Critical | 18 | 1 | 1 | 4 | 1 | 3 | 1 | 7 |

Research adds a small fixed overhead on top of that: **two research-tier calls** — one to write the retrieval queries, one to brief from what came back, or to scope the request instead when nothing matched — plus **at most one outward lookup**. Not one per gap: every blocking gap rides in a single request, because the fee is charged per request rather than per question. Low-risk work makes no lookup at all, so it adds two calls rather than three.

| Risk | Phases | + research | Typical total |
|---|---|---|---|
| Low | 6 | 2 | **8** |
| Medium | 8 | 3 | **11** |
| High | 14 | 3 | **17** |
| Critical | 18 | 3 | **21** |

Those research figures were derived the same way as the workflow comparison above — the graph driven against billing doubles with an isolated knowledge store, free, in under a second — rather than estimated. Both grounding shapes cost the same two calls: with documentation ingested the second call is a briefing, with an empty store it is a scoping analysis. Configuring a ranker tier adds one more call when retrieval returns material; without one, ordering falls back to embedding distance and costs nothing.

Retries and escalation add further: a medium-risk workflow failing validation three times costs 14 phase calls, and one exhausting the loop and recovering through escalation costs 19.

Three things follow, and they are the levers worth pulling:

- **The engineering tier dominates.** At every risk level it runs implement, validate, feasibility and most of review.
- **Review scales hardest with risk.** Critical work runs seven reviewers where low-risk runs one, so risk classification is a cost decision as much as a quality one.
- **Output tokens are the expensive half, and they are also latency.** Measured live, an unbounded validator produced 15,000 output tokens for a green/red verdict, taking three minutes. `VALIDATE_MAX_TOKENS` exists because of that.

**Latency.** Feasibility, domain review and final review run in parallel, so wall-clock tracks the critical path rather than the call count: six to seven sequential round trips for a single-iteration workflow. Harness overhead is negligible — tens of milliseconds — so effectively all wall-clock is provider latency. Measured across live runs, calls averaged roughly a minute each with reasoning models in the architecture and escalation tiers, which puts a full workflow in minutes rather than seconds.

**Variance is large.** The same request has measured 7 calls and 68 seconds on one run and 21 calls and 663 seconds on another. Treat any single run as an anecdote, which is why evals repeat.

## Testing

```bash
.venv/bin/python3 -m pytest tests/ -q
```

854 tests. Most make no model call, which is deliberate: the shape of a workflow, its gates and loops, the deterministic checks, the eval scoring and the condition language are all decidable without a provider, so a full regression sweep is free and finishes in seconds.

The graph tests are the load-bearing ones: node shape, gate routing, loop bounds and the all-judges exit are all decidable without a provider. An earlier hardcoded sequencer was kept alongside the graph as an equivalence reference and has been retired — once gates could route on failure, a linear engine could no longer represent the pipeline it was supposed to be checking.

## Deployment

Designed for **private-network use.**

Even with auth, do not put AutoRnD on the public internet. Use a reverse proxy with TLS, or a private network. Anyone who reaches the API can run workflows and spend your credits.

```bash
uvicorn autornd.main:app --host 127.0.0.1 --port 8100
```

**Database.** SQLite by default. Additive, nullable columns are applied automatically at startup, so routine upgrades need no manual step. There is no full migration tool, so altering or dropping a column would still need handling by hand.

## Limitations

- **No code execution.** AutoRnD produces structured text. It does not compile, run, or deploy anything.
- **Checks cannot see negation.** `criteria_addressed` scores term overlap, so an implementation stating it *removed* something scores highly against a criterion requiring it. `numbers_consistent` covers the numeric case; the general case is a known gap.
- **Research can be wrong.** It cites its sources, which makes it checkable rather than infallible — and that is the point. Verifiability is the product.
- **Quality follows the models you choose.** Cheap tiers give cheap results.
- **No role-based access.** Per-user isolation exists; admin/user roles and team permissions do not.
- **No streaming.** `/api/workflows/sync` blocks. Use the async endpoint and poll for long runs.
- **Review reworks, within bounds.** A `ship: false` verdict routes the work back through implement, validate and a fresh review — up to `review_rework_attempts` (default 2) — and exhausted rework escalates with the findings in the failure log. Review and implement can disagree indefinitely, so every disagreement path is bounded and ends in escalation or a human.
- **Costs are real.** Every workflow calls a paid API. Set `MAX_ITERATIONS` conservatively and watch your provider's spend.

## Contributing

PRs welcome. The architecture is modular — add specialists, providers, phases, checks, workflows or review composition rules without touching the sequencer. New deterministic checks are especially welcome: anything with a right answer belongs in a check rather than a prompt.

## License

MIT
