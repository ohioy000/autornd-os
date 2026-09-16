# AutoRnD-OS — Project State & Handover Document

**Repo:** `github.com/ohioy000/autornd-os` (public) · **HEAD:** `641da5a` · **Branch:** `main`
**Tests:** 711 as of `cafebabe` · **Date of this snapshot:** 2026-09-13, test counts refreshed 2026-09-14

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
further faults in the same file that no test could see — see §4.2 B1