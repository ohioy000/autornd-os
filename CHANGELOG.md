# Changelog

All notable changes to AutoRnD will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

Everything below happened after 0.1.0 and none of it was recorded until now.
The entry is written as prose rather than a bullet list because most of these
changes are only meaningful with the measurement that forced them.

**The workflow became a file.** The five-phase sequencer is gone from the
critical path. A pipeline is now a YAML graph in `workflows/`, built from three
node kinds — `ai` (model calls), `check` (free deterministic functions) and
`gate` (booleans over prior outputs) — with loops that carry an `until`
condition, a bounded iteration count and explicit exhaustion semantics, so a
build loop that gives up hands off to an escalation autopsy rather than simply
stopping. Conditions are one deliberately tiny grammar, not `eval`;
configuration must not execute code. Four workflows ship, and comparing two of
them is a measurement anyone can run. The original hardcoded sequencer is kept
as the equivalence reference and `tests/test_graph_equivalence.py` asserts the
graph reproduces it call for call — it has caught real drift, so it stays until
it stops paying.

**An eval harness, so rules come from data.** Scenarios are YAML with
expectations written *before* the run; assertions are free and make no model
call; a bounded runner enforces per-scenario spend and call ceilings and reports
cost and calls per tier; suites repeat, because the same request has passed on
one run and failed on the next. Each scenario gets an isolated knowledge store,
after the discovery that research ingests what it finds and so grounded every
scenario after the first.

**Outward research, as a default rather than an option.** The harness writes its
own queries, ranks what it retrieves, briefs the phases that follow, and looks
outward for what the documentation does not cover. It asks the local store
before it pays for anything, and it ingests what it finds, so a fact is looked
up once and free thereafter. The reason it exists is a measurement: asked which
charger IC a board used, a capable model named the wrong part confidently and
without hedging; asked an RF limit it conflated two units 2.15 dB apart, the
difference between a compliant transmitter and a failed certification. Both
wrong answers sounded exactly as certain as the right ones, so there is no
confidence signal to gate a lookup on.

**Search cost was cut 44% by changing its shape, not its budget.** Low-risk work
looks nothing up; only gaps that would change the answer are looked up; and
every remaining gap rides in exactly one request, because the fee is charged per
request rather than per question. Token budgets scale with risk — a wrong figure
in medium-risk work is recoverable and in critical work it is not. Measured
across 36 sectors, $0.0999 to $0.0562 per workflow, almost entirely from four
requests becoming one.

**Domains and roles became open vocabularies.** Both were closed enums. With
`Domain` enforced, nine of twelve subjects had no fitting value and eight came
back `hardware` — civil engineering as "hardware", buffer chemistry as
"documentation". A closed list does not produce an honest refusal; it produces a
least-wrong label. Projects now declare `domains:` and `roles:` in a profile, an
undeclared role resolves to a synthesized generalist, and the shipped enums are
defaults rather than limits.

**Review composition is derived, not tabulated.** The review team is built from
the specialists triage actually assigned, scaled by risk. The old static table
returned every shipped role at critical risk, which meant seven engineers
reviewing a records retention schedule.

**Review gates the run.** `ship: false` now blocks rather than being recorded and
surfaced while the workflow completes anyway.

**`unrecallable` is a separate axis from risk.** A signed rollout to forty
thousand devices harms nobody and breaches no rule, so it is not critical — but
it cannot be taken back. It earns one extra independent review pass instead of
inflating its risk level.

**Cost accounting moved onto the client, and the old numbers were wrong.**
Spend, call counts and serving provider are recorded per tier inside the client,
so no call path can avoid being priced, with optional call and spend ceilings
enforced at the same place. This fixed a meter that had been counting only one
of four paths: research, grounding and reranking were all free as far as the
totals were concerned, and rerank cost was read into a debug log and discarded.
An eight-sector grounding run metered at $0.0025 actually cost $0.7366.
**Every cost figure in this project's history before that fix is understated by
between 2.6x and 295x and should not be cited.**

**Providers can be pinned per tier, and it turns out to matter.** One sweep saw a
single tier served by five different providers. Pinning each and re-running the
identical suite scored 35/36 at one end and 28/36 at the other, for twelve times
the price — and the cheap serving did not fail randomly, it under-classified risk
on the same three consequential sectors every repetition. An unpinned score is
partly a record of who answered, so pinning is a precondition for calibrating
anything. Pins are per tier because tiers run different models and no provider
serves them all.

**Packaging was unusable and is now fixed.** `pip install -e .` failed at build
on flat-layout package discovery, so it never reached the missing runtime
dependency behind it, and no built wheel contained the dashboard template.
`pyproject.toml` is the single dependency manifest, `requirements.txt` is gone,
and CI grew a job that installs from project metadata, imports the startup path
and checks a built wheel carries its package data — because the test suite runs
against the source tree and is structurally incapable of seeing a packaging
fault.

The suite stands at **501 tests** as of `be8fd08`, up from 85 at 0.1.0.

## [0.1.0] — 2026-09-12

### Added

- Multi-model agentic workflow engine with 5-phase sequencer (triage, plan, implement, validate, review)
- 7 engineering specialists with profile-driven system prompts
- Reasoning-model escalation autopsy — recovery when the implement/validate loop exhausts
- Risk-based review team composition (critical → all specialists, low → single specialist)
- Plan feasibility gating — specialists review the plan before implementation tokens are spent
- Project profile system — YAML-based domain grounding with per-specialist context overrides
- Profile-aware knowledge store with ChromaDB semantic retrieval
- Episodic memory — workflow outcomes stored for future context
- REST API with sync and async workflow submission
- Dashboard with chat interface, workflow table, and profile selector
- API key authentication middleware (optional, bearer token)
- OpenRouter multi-model routing client with cost tracking and retry logic
- CLI for doc ingestion (`init-knowledge`)
- Docker support with volume mounts for profiles and docs
- Example profile (SmartFactory) with sample docs
- Full test suite (85 tests)
