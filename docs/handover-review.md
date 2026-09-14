# Handover Review — corrections, drift punch list, and chat-only findings

Companion to [`HANDOVER.md`](../HANDOVER.md). That document is the project state;
this one records **what in it was wrong**, **which docs still disagree with the
code**, and **what existed only in a chat transcript** and would otherwise be
lost.

Written 2026-09-13, at `641da5a`+. The intent is that a fresh session executes
from the repo rather than from pasted conversation.

---

## 0. The blueprint protocol

Four blueprints have run through this document (§7, §9, §10, §11). The working
shape is stable enough to state once:

1. **The blueprint lands in the repo verbatim and unexecuted, before any of it
   is carried out.** The session then works from the repo rather than from a
   chat transcript, and the record shows what was asked for separately from what
   was done.
2. **An execution record follows as §N.2**: departures with their reasons, what
   was left undone deliberately, and anything execution found that the blueprint
   missed. Every value touched gets a line, "while here" edits included.
3. **The provenance rule** (binding from Blueprint 004): every number in a
   blueprint carries `[measured: §ref]`, `[derived: method]`, or
   `[estimate → derive before use]`. **Estimates set expectations; they never
   gate anything.** This exists because the estimates have been the wrong part
   on every pass so far while the mechanisms were right — 001 assumed one
   packaging fault and found three, 002 flagged an accurate test count as stale,
   003 was ten times high on a unit cost whose true value was already in
   `HANDOVER` §6. Source a number from §6 before asserting it.
4. **Expectations are pre-registered**, and a wrong one is reported as wrong
   rather than quietly adjusted to match the result (convention 7).

---

## 1. Corrections to HANDOVER.md

### 1.1 CI exists — and that is the *point* of B1 ❗

> **Resolved.** Kept below as the record of the reasoning, which was
> correct. The two-manifest split is gone: `requirements.txt` is deleted
> and CI installs from `pyproject.toml`. The analysis *understated* the
> problem — see §7.2.

**HANDOVER.md claimed (§1 Infrastructure and §5 item 10): "no CI pipeline",
"No pipeline exists."** That was wrong. Verified:

```
.github/workflows/ci.yml    pytest on Python 3.11 / 3.12 / 3.13
                            triggers: push + pull_request to main
                            install step: pip install -r requirements.txt
```

Both claims are now fixed in `HANDOVER.md`.

The correction matters more than the fact, because it explains **how green CI
and a broken install coexist**:

| source | contains `pyjwt`? | used by |
|---|---|---|
| `requirements.txt` | **yes** | CI install step, Docker |
| `pyproject.toml` `[project].dependencies` | **no** | `pip install -e .`, any wheel build |

`autornd/api/auth.py:10` does `import jwt`. CI installs from the file that has
it, so the suite passes on three Python versions while an editable or packaged
install has no JWT library at all. **CI was never going to catch B1** — not
because CI is missing, but because it exercises only one of two dependency
manifests.

### 1.2 The doc set was under-reported

`HANDOVER.md` §2.2 lists only `.py`/`.yaml`/`.html`. The repo root also carries
`CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, `README.md` and now
`HANDOVER.md` + this file. Three of those have drifted — §2.

### 1.3 Numbering note

`HANDOVER.md` §4.2 numbers known issues **B1–B10**. Any item referred to as
**B11 or higher originates outside that document** (i.e. from the advisor
session). The CLAUDE.md rewrite was handed to this session as "B11"; it is done
(§3.1) and is recorded here rather than renumbered into HANDOVER, so the two
numbering schemes do not silently merge.

---

## 2. Doc-drift punch list

Ordered by how much damage the drift does.

| # | file | status | drift |
|---|---|---|---|
| D1 | `CONTRIBUTING.md` | ✅ **done** (§9.2) | Tells contributors to "wire new phases into `autornd/engine/workflow.py`" — the **legacy** sequencer kept only as the graph's equivalence reference. Correct path: add a `_phase_<name>` method to `graph/adapter.py` and a node to a `workflows/*.yaml`. Also says to "add new `SpecialistRole` entries to `autornd/models/verdicts.py`" — roles are an **open vocabulary** now; you declare them under `roles:` in a profile and an undeclared one resolves to a generalist. A contributor following this file today builds on the deprecated path. |
| D2 | `CHANGELOG.md` | ✅ **done** (§9.2) | Last entry `[0.1.0] — 2026-09-12`: "5-phase sequencer", "Full test suite (85 tests)", and a model nickname ("K3 escalation autopsy pattern"). Sixteen commits of substantial change are unrecorded — the workflow graph, the eval harness, outward research, open domain/role vocabularies, client-side accounting, provider pinning, the review gate, and the `unrecallable` axis. |
| D3 | `README.md` | ✅ **done** (§9.2) | Says **"339 tests"** in two places (`:728`, `:771`); actual count is **501**. Line `:103` names a specific model ("Sonar-pro bills $15.00 per million…"), which breaks the zero-model-names rule. The measurement should stay; the vendor name should become "a sonar-class search model" or similar. |
| D4 | `CLAUDE.md` | ✅ **done** | Rewritten — §3.1. |
| D5 | `HANDOVER.md` | ✅ **done** | §1.1 and §1.2 corrections applied. §0's naming sentence rewritten to the selection-vs-record policy in Blueprint 002. |
| D6 | `.env.example` | ✅ **done** (§9.2) | Never on this list, because this pass only audited the four docs above. Five defects, one of them a retracted measurement: a stale tier count, a figure produced by the pre-`b4cd89f` meter, a clause missing its negation, a pinning claim contradicted by §4.6, and a named model. Two more found while executing — a workflow list missing half the shipped workflows, and `AUTORND_PROFILE` orphaned thirty lines from its own documentation. |

---

## 3. Work completed in this pass

### 3.1 CLAUDE.md rewritten

Short, current, **zero model names** (verified by grep: 0 hits across
deepseek/minimax/glm/kimi/gemini/sonar/qwen/gpt/mistral/llama/claude/openai/
anthropic). Replaces a version that:

- named five specific models in a "Model Routing" table,
- claimed "133 tests (9 test files)" against the real 501 / 17,
- omitted `graph/` and `evals/` entirely,
- described the pipeline as a hardcoded sequence rather than a YAML graph,
- said nothing about the research and search tiers, open vocabularies,
  client-side accounting, the review gate, `unrecallable`, or provider pinning,
- referred to a model by nickname ("K3 escalation uses static/dynamic payload
  split").

The rewrite is organised as: what it is → stack → layout → pipeline → tiers →
**twelve invariants** → commands → style. The invariants are the load-bearing
part; they encode the rules that were each learned by breaking something.

### 3.2 Reworked CI step — extend, do not create

> **Shipped**, with three departures from the draft below, each forced by
> something the live install revealed — §7.2.

The brief's step 3 changes from "add CI" to **"add an editable-install job"**,
because CI exists and is green. Below is the substance, ready to drop in when B1
is opened. It fails today (which is the point) and passes once `pyjwt` is added
to `pyproject.toml`:

```yaml
  # append to .github/workflows/ci.yml
  editable-install:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      # Installs from pyproject.toml, NOT requirements.txt. The existing `test`
      # job installs from requirements.txt, which is why a missing pyproject
      # dependency (pyjwt / B1) passed CI on three Python versions while
      # `pip install -e .` produced an unusable install.
      - name: Editable install from project metadata
        run: |
          python -m pip install --upgrade pip
          pip install -e .

      # Import the modules a real process touches at startup. The gap was a
      # transitive import (api/auth.py -> jwt), so importing the package alone
      # would not have caught it.
      - name: Import smoke test
        run: |
          python -c "
          import autornd.main, autornd.api.auth, autornd.api.routes
          import autornd.graph.executor, autornd.routing.openrouter
          import autornd.evals.runner
          print('editable install imports clean')
          "
```

Two deliberate choices: a **single** Python version (this job tests packaging
metadata, not version compatibility — the matrix already covers that), and an
**import** smoke test rather than `pytest`, because the tests run against the
source tree and would pass regardless of install metadata.

---

## 4. Chat-only findings — the skim

The brief predicted a small yield, expecting only B6 failure traces (not needed),
failed prompt wordings (recoverable from git diffs) and provider tables (already
in `HANDOVER.md` §6.1). **That prediction was wrong in one direction:** the
model-selection research is substantial, was never committed, and is the highest
cost-leverage material produced. It is recorded here in full.

### 4.1 ❗ The search tier is on the most expensive option in its family

From the live OpenRouter catalogue (445 models, fetched 2026-09-13):

| model | in $/M | out $/M | ctx |
|---|---|---|---|
| `perplexity/sonar` | 1.00 | **1.00** | 127k |
| `perplexity/sonar-reasoning-pro` | 2.00 | 8.00 | 128k |
| `perplexity/sonar-deep-research` | 2.00 | 8.00 | 128k |
| `perplexity/sonar-pro` ← **current** | 3.00 | **15.00** | 200k (max out 8000) |

Search is **61–98% of all spend** (`HANDOVER.md` §6.3). The non-pro model is
**15× cheaper in the same family**. This is the single largest untested cost
lever in the project, and the grounding eval grades it directly.

**Second-order effect if `sonar` wins:** the per-request fee is ~$0.00698 and
fixed. At $15/M output it is 13% of a 3000-token lookup; at $1/M it becomes
**~64%**. The token economics invert — a *generous* token budget becomes nearly
free, and the owner's original instinct ("it's per call, so give it max tokens")
becomes correct for the first time.

### 4.2 Real prices of the currently-configured tiers

Three of six are mispriced for their job:

| tier | configured model | out $/M | note |
|---|---|---|---|
| search | `perplexity/sonar-pro` | **15.00** | §4.1 — 15× alternative exists |
| escalation | `moonshotai/kimi-k3` | **13.28** | rare enough to defend |
| architecture | `z-ai/glm-5.3` | **4.40** | expensive **and** reasoning **and** stubs on planning |
| research | `google/gemini-2.5-flash` | **2.50** | a summarisation tier at 2× the engineering tier; max out only 65,535 |
| engineering | `minimax/minimax-m3` | 1.20 | fair price, silent-failure mode |
| triage | `deepseek/deepseek-v4-flash` | 0.18 | good value; provider-sensitive (§6.1) |

`glm-5.3` is **not** a mid-tier model at $4.40/M — a working assumption that had
gone unchecked.

### 4.3 The selection criterion that matters here

Catalogue field `supported_parameters` is the discriminator, and the filter is:

> **`structured_outputs` present AND `reasoning` absent**

Every phase fills a typed schema. A reasoning-capable model can spend its whole
output budget thinking and emit nothing — the measured failure mode of both the
engineering and architecture tiers (`HANDOVER.md` §6.4). **54 models** pass that
filter under $3/M with ≥100k context.

Best value per tier, selected on catalogue signals (price, non-reasoning,
context, max-output, model class) — **not** on reputation, since several of
these postdate the assistant's knowledge cutoff:

| tier | candidate | out $/M | rationale |
|---|---|---|---|
| search | `perplexity/sonar` | 1.00 | §4.1 |
| architecture | `mistralai/mistral-large-2512` | 1.50 | large-class, non-reasoning, 209k max out |
| | `openai/gpt-4.1-mini` | 1.60 | 1M ctx, reliable at JSON |
| | `moonshotai/kimi-k2-0905` | 2.50 | non-reasoning sibling of the escalation model |
| engineering | `qwen/qwen3-235b-a22b-2507` | 0.35 | 235B MoE, non-reasoning, 235k max out — 3.4× cheaper than current |
| | `deepseek/deepseek-chat-v3-0324` | 1.00 | strong generalist |
| research | `qwen/qwen3-235b-a22b-2507` | 0.35 | 7× cheaper than current for summarisation |
| | `mistralai/mistral-small-3.2-24b-instruct` | 0.20 | leaner option |
| triage | keep current **+ pin provider** | 0.18 | the 28/36 → 33/36 gap was the provider, not the model |
| | `qwen/qwen3-235b-a22b-2507` | 0.35 | far larger non-reasoning model for 2× the price |
| premium | `z-ai/glm-5.3` | 4.40 | **reassign here** — §4.4 |

### 4.4 The glm reassignment: right model, wrong tier

Measured (`HANDOVER.md` §6.4): `z-ai/glm-5.3` returns schema-shaped stubs when
asked to **plan**, across Together, Modal and the AkashML/Wafer rotation — so it
is the model, not the serving. The *same* model, as the independent reviewer,
caught a flaw nothing upstream had found (that a table rename and drop in one
migration script make the observation window between them impossible).

**Action:** move it from `MODEL_ARCHITECTURE` to `MODEL_PREMIUM`, and put a
non-reasoning model on architecture. Judge a tier by its job, not the model's
reputation.

### 4.5 Ruled out, so nobody re-investigates

- **`inference-net/schematron-v2-turbo` / `-small`** ($0.15 / $0.23). Tempting on
  price and name, but they are **HTML-to-JSON extraction** models that require
  extraction instructions through a specific mechanism. Wrong shape for a chat
  tier. Do not put them on triage.
- **`qwen/qwen3-reranker-8b`** is correctly **absent from the chat catalogue** —
  it is served via `/rerank`. This is why model validation needed the
  non-chat confirmation path, and it is not a missing-model bug.
- **22 zero-priced models** exist in the catalogue (free/promo). Not evaluated;
  treat with suspicion for anything whose classification decides review depth.

### 4.6 Provider allowlists fail over within themselves — verified live

Pinned the triage tier to `[Perplexity, StreamLake]`, where Perplexity does not
serve that model. **Result: succeeded via StreamLake.**

So `OPENROUTER_PROVIDER_ORDER` with several providers gives a measured quality
floor *and* availability, even with `allow_fallbacks: false`. That makes pinning
safe in deployment, not just in measurement:

| purpose | shape | why |
|---|---|---|
| measuring (evals) | **one** provider per tier | maximum reproducibility |
| deployment | a measured **allowlist**, 2–3 per tier | quality floor + failover |

```bash
OPENROUTER_PROVIDER_ORDER=triage:StreamLake,triage:DigitalOcean,architecture:Together,search:
```

A tier named with an empty value (`search:`) opts out of a general default.

### 4.7 Catalogue metadata worth keeping

- `perplexity/sonar-pro` **does not** advertise `structured_outputs` — fine,
  because `research.py` uses plain `chat`, not `chat_json`. Do not "fix" this.
- `google/gemini-2.5-flash` max completion tokens is **65,535**, well below
  other tiers — relevant if it is ever put on a long-output phase.
- A catalogue snapshot was saved to a scratchpad during this work and **is not
  persisted**. Re-fetch with `GET https://openrouter.ai/api/v1/models` (no auth
  required).

### 4.8 Ranked beta test plan

| # | test | command target | cost | upside |
|---|---|---|---|---|
| 1 | `sonar` vs `sonar-pro` | `evals/grounding` | ~$0.05 + $0.35 | up to **90% off the dominant cost line** |
| 2 | architecture swap | `evals/scenarios/backend_index.yaml` | ~$0.15 each | removes the planning stub; ~65% off that tier |
| 3 | research swap | `evals/grounding` | ~$0.05 | 7× off a tier called 2–3× per workflow |
| 4 | triage candidate, pinned | `evals/scenarios/wide` | ~$0.03 | the remaining calibration gap |

---

## 5. ⚠️ Not included — must be pasted by the advisor session

The brief asked this file to contain four things that **were not in the
executing session's context**, and they have deliberately **not** been
reconstructed, because inventing them would put fabricated architectural
documents into a public repo under someone else's authorship:

| item | status |
|---|---|
| **Blueprint 001** — full text | ✅ **received — §7.** Its CI section already incorporates the rework from §3.2, so §3.2 is now background rather than a live instruction. |
| **Blueprint 002** — full text | ❌ still absent. |
| The owner's **verification response** from the prior turn | ❌ still absent. The executing session's prior turn was a model-selection question. |
| **"This turn's audit"** | ❌ absent as a supplied artifact. §1 and §2 are this session's own verification, done from the repo. |
| The **B6 plan** ("builds a minimal workflow instead") | ❌ still absent. Noted as the intended approach; the plan text is unknown. |

Everything in §1–§4 is independently verified against the repo or measured live,
and is safe to rely on. Paste the four remaining items and they can be appended
verbatim alongside §7.

---

## 6. Session handling

**Archive, do not resume.** The prior transcript is a read-only reference for
"what did we already try" — most usefully the four successive rewrites of the
triage risk guide, each of which failed for a reason now recorded in
`HANDOVER.md` §6.6 and recoverable in full from `git log -p autornd/engine/phases.py`.

Session history lives outside the repository, so nothing in this pass changes
it; the recommendation is unaffected either way.

---

## 7. Blueprint 001 — B1 (verbatim, as received)

**Status: executed 2026-09-14 — see §7.2 for what it actually took.**
Recorded here so the fresh session executes from the
repo rather than from pasted chat. Its CI section already folds in the rework
described in §3.2 (extend rather than create), which supersedes that section as
an instruction.

Note for the executor: the two prerequisites are stated inside the blueprint and
are not optional — diff the manifests for strays and confirm nothing else
references `requirements.txt`; and verify whether importing `autornd.main`
requires environment variables before writing the import smoke. Neither has been
done in this pass.

```text
B1 Goal: fix the install-breaker, the manifest class, and add the drift-catcher. One commit.

Instance: add "pyjwt>=2.8.0" to pyproject.toml dependencies.
Class — pick one (my recommendation: A):
A (single source): pyproject.toml becomes canonical. Dockerfile switches from pip install -r requirements.txt to COPY . . + RUN pip install --no-cache-dir .; delete requirements.txt; update README Quick Start; dev installs use .[dev].
B (conservative): keep both files; add a free test that parses both manifests and asserts their runtime-dependency sets agree, so drift fails CI.
Either way, Claude first diffs the two manifests for strays and confirms nothing else references requirements.txt.
CI: .github/workflows/ci.yml — push/PR, Python 3.12, pip install -e ".[dev]", import smoke (Claude must verify first whether importing autornd.main requires env vars — if Settings validates at import time, set the six MODEL_* tiers plus OPENROUTER_API_KEY to dummies in CI env), then pytest -q. Public repo → free Actions minutes, ~9 s.
Hygiene re-verify (the checks my sandbox couldn't run): git ls-files profiles/ → example.yaml only; git ls-files | grep .env → .env.example only; vendor-name grep across the tree → clean.
Test-first (convention 7): manifest-parity test (if B) or the CI import smoke (if A) written before touching the manifests.
Commit message: prose per convention 12 — a fresh editable install failed on import jwt, the root cause is two dependency manifests drifting in both directions, and CI now catches this class.
```

### 7.1 Standing observations relevant to executing it

Recorded now so they are not re-derived, but note these are **observations, not
the prerequisite work** — the diff and the import check still have to be run:

- The existing `test` job installs from `requirements.txt` across a
  3.11/3.12/3.13 matrix. **Under option A that job must also change**, or CI
  breaks the moment `requirements.txt` is deleted. Option A therefore touches
  both jobs, not just the new one.
- Under option A the drift-catcher is partly structural: with one manifest there
  is nothing to drift *between*, and installing from it in CI means a missing
  runtime dependency fails the suite directly (`tests/test_auth.py` imports the
  module that needs `jwt`). The import smoke still earns its place for anything
  the tests do not import — the startup path in `autornd/main.py` in particular.
- `requirements.txt` currently mixes runtime and dev dependencies (`pytest`,
  `pytest-asyncio`), which means the Docker image installs a test framework into
  production. Option A resolves that as a side effect; option B should decide
  whether the parity test compares runtime sets only.

---

### 7.2 Execution record — 2026-09-14, option A

The owner chose **option A** (single manifest). The blueprint's two stated
prerequisites were run first, and both changed the work.

**Prerequisite 1 — diff the manifests for strays.** Clean: `requirements.txt`
was `pyproject.toml`'s runtime block verbatim, same order and same pins, plus
`pyjwt>=2.8.0` and the two dev packages `pyproject` already carried under
`[dev]`. Live consumers of the file were four — `ci.yml:27`, `Dockerfile:5-6`,
`CONTRIBUTING.md:10`, `README.md:499`. All four now point at `pyproject.toml`.

**Prerequisite 2 — does importing `autornd.main` need env vars?** Yes, six.
`config.py:192` calls `_build_settings()` at module scope, which raises
`SystemExit` when any required tier is empty. `OPENROUTER_API_KEY` is *not*
required at import — it defaults to `""` — so the blueprint's instinct to set it
was right about the shape and wrong about the key. `tests/conftest.py` already
solves this with `os.environ.setdefault`, which is why the matrix job needs no
env block. The new job's env block is scoped to that job alone and deliberately
not made workflow-wide: putting it at the top level would mask a future
regression in conftest's injection.

**What the install actually found.** B1 was recorded as one line. Running
`pip install -e .` in a clean venv found **three faults, and the documented one
could not even be reached**:

| | fault | how it presented |
|---|---|---|
| 1 | flat-layout package discovery | `error: Multiple top-level packages discovered in a flat-layout: ['evals', 'autornd', 'profiles', 'workflows']` — the build aborts, so `pip install -e .` never got as far as importing anything |
| 2 | `pyjwt` absent from `pyproject.toml` | the documented B1; only observable once fault 1 was fixed |
| 3 | no package data in the wheel | `autornd/api/templates/dashboard.html` was in **no** built wheel, so every non-editable install served `FileNotFoundError` from the dashboard route |

Fault 3 is the interesting one: it was never going to surface from an editable
install either, and `CONTRIBUTING.md:52` had been telling people to
`pip install -e .` — which had been failing at build the whole time.

**Three departures from the §3.2 draft**, each forced by the above:

1. the `env:` block, per prerequisite 2;
2. a third step asserting a built wheel carries `dashboard.html`, because an
   import smoke passes happily on an install whose data files are missing;
3. the **matrix** job changed too (`pip install -e ".[dev]"`). The draft touched
   only the new job; deleting `requirements.txt` forces both, exactly as §7.1
   predicted.

**One departure from the blueprint's option A text.** It specified
`RUN pip install --no-cache-dir .` for the Dockerfile; the file uses `-e .`.
`workflow_path()` (`engine/workflow.py:38`) and `PROFILES_DIR` (`profiles.py:16`)
both resolve their data directory as `Path(__file__).parent.parent.parent`, and
neither `workflows/` nor `profiles/` ships inside the package — verified by
inspecting the built wheel, whose only top-level entry is `autornd/`. A
relocating install therefore puts both at paths that do not exist. It would have
happened to work in the image, because `WORKDIR /app` shadows site-packages on
`sys.path` — which is luck, not design. Editable keeps one copy at `/app` and
both resolve by construction. The cost is the lost layer-caching of the old
`COPY requirements.txt` first step; there is no production deployment and the
image is not built in CI, so nothing is measurably worse.

**Verification.** Every claim above was produced by running it, in a throwaway
venv built from `get-pip.py` (this box has no `ensurepip`), against a copy of
the tree — never the repo, so no build artifacts reached the working directory:

- before: `pip install -e .` → build error, as quoted;
- after: install succeeds, `pyjwt-2.14.0` resolved, import smoke clean;
- both CI jobs replayed against the final tree — `-e ".[dev]"` + `pytest` →
  **501 passed**; `-e .` + import smoke → clean; `python -m build --wheel` →
  wheel carries the template.

**Left undone, deliberately.** Nothing exercises the **Docker build** — it is
now the only install shape no job covers, and it is recorded in `HANDOVER.md` §5
item 10 rather than fixed here. `CONTRIBUTING.md` got its install line only;
C1–C7 and C9–C10 remain Blueprint 002's.

**The generalisable lesson**, in the register of §6.8: 501 tests could not see
any of these three, because a test suite runs against the source tree and a
packaging fault lives in the metadata. One live install found all three in under
a minute. It is §6.8's lesson again in a new place — *the fault a suite is
structurally incapable of seeing is the one that ships.*

---

## 8. Inventory: CHANGELOG.md and CONTRIBUTING.md stale claims

Inventory only — **no fixes in this pass**; they land in Blueprint 002. Ordered
within each file by how much damage the claim does if believed.

### 8.1 CONTRIBUTING.md

> ✅ **All of C1–C10 closed by Blueprint 002.** The inventory below was
> re-read at HEAD before executing and was accurate in every particular.
> Kept as written — it is the record of what the file used to teach.

| # | claim | why it is wrong |
|---|---|---|
| C1 | *"No comments unless the 'why' is non-obvious"* (Code Style) | Directly contradicts this project's strongest convention. Measurement comments are the codebase's most valuable property — nearly every constant carries the live run that set it. A contributor following this line would **strip** exactly that. |
| C2 | *"Workflow phases — add new phases in `autornd/engine/phases.py` and wire them into the sequencer"* | "The sequencer" is `engine/workflow.py`, the **legacy** path kept only as the graph's equivalence reference. Correct path: add `_phase_<name>` to `graph/adapter.py` and a node to a `workflows/*.yaml`. |
| C3 | *"wire new phases into `autornd/engine/workflow.py`"* (Building on AutoRnD) | Same error, stated more explicitly, in the section aimed at people extending without forking. |
| C4 | *"register its `SpecialistRole` in `autornd/models/verdicts.py`"* — appears **three times** (What to Work On, Building on AutoRnD, `[seam]` Specialist registry) | Roles are an **open vocabulary**. You declare them under `roles:` in a profile; an undeclared role resolves to a synthesized generalist. No enum edit is needed, and editing the enum is not how a project adds its own roles. |
| C5 | The `[seam]`/`[internal]` architecture list omits **`graph/`** entirely | `spec.py`, `executor.py`, `adapter.py`, `conditions.py`, `checks.py` — the actual engine — appear nowhere. A contributor reading the seam list would not learn the graph exists. `evals/` is likewise absent. |
| C6 | *"`[seam]` Review composition — risk-to-team mapping. Add new composition strategies here."* | The risk-to-team **table** was replaced by derivation from the specialists triage assigned; the signature is now `get_review_team(risk, domains, specialists)`. "Risk-to-team mapping" no longer describes it. |
| C7 | *"the sequencer, review composition, and routing layers all read from the registry dynamically"* | Outdated framing for the same reason as C6. |
| C8 | ~~`pip install -r requirements.txt` (Getting Started)~~ | **Fixed in Blueprint 001** — now `pip install -e ".[dev]"`. The rest of this file is untouched and remains Blueprint 002's. |
| C9 | `pytest tests/ -v` (Running Tests) | Repo convention is `-q`, and in the owner's environment `.venv/bin/python3 -m pytest` (pytest is not on PATH). |
| C10 | No mention of the eval suites, `--max-spend`, or the test-first convention | A contributor has no route to the cheapest quality signal in the project. |

### 8.2 CHANGELOG.md

> ✅ **Closed by Blueprint 002, with one correction to this inventory.**
> **G1 was wrong**: "85 tests" was *true* at 0.1.0. Counting test functions
> at `7fa5b11` gives exactly 85, so the claim stands and the current count
> belongs to `[Unreleased]`, where it is stamped with the commit that
> produced it. G4 and G5 are also left standing: both describe behaviour
> that was real at 0.1.0 and changed afterwards, which is what a historical
> entry is for. G3 (the model nickname) is the only edit made to the 0.1.0
> record, and G7 is now an `[Unreleased]` section.

Frozen at a single entry, `[0.1.0] — 2026-09-12`. Every claim below is in that
entry.

| # | claim | why it is wrong |
|---|---|---|
| G1 | *"Full test suite (85 tests)"* | Actual: **501**. |
| G2 | *"5-phase sequencer (triage, plan, implement, validate, review)"* | Now a 16-node YAML graph with gates, loops, escalation recovery, a review gate and a conditional independent pass. |
| G3 | *"K3 escalation autopsy pattern"* | Model nickname in a user-facing document; breaks the zero-model-names rule. |
| G4 | *"Risk-based review team composition (critical → all specialists, low → single specialist)"* | `critical` no longer returns all specialists — that behaviour was the measured defect that put seven engineers on a records-retention review. |
| G5 | *"OpenRouter multi-model routing client with cost tracking"* | Present but misleading: cost tracking missed research, context and rerank calls until `b4cd89f`, understating by 2.6×–295×. |
| G6 | *"7 engineering specialists"* | True as defaults, but the roster is open now — profiles declare their own. |
| G7 | **Unrecorded since 0.1.0** | The workflow graph as data; the eval harness (scenarios, assertions, bounded runner, per-tier spend); outward research with recall-before-search; open domain **and** role vocabularies; client-side accounting and budgets; provider recording and per-tier pinning; the review gate; the `unrecallable` axis; risk-scaled search budgets. |

**Note for Blueprint 002:** C1 and C4 are the two worth fixing first — C1 because
it invites the removal of the project's most valuable property, C4 because it is
repeated three times and sends every would-be extender to the wrong mechanism.

---

## 9. Blueprint 002 — the documentation truth pass (verbatim, as received)

**Status: not executed at the time of recording.** Same protocol as 001: the
blueprint is committed to the repo before any of it is carried out, so the
executing session works from the repo rather than from pasted chat, and the
record shows what was asked for separately from what was done. The execution
record is §9.2.

```text
BLUEPRINT 002 — Documentation truth pass: README, .env.example, CONTRIBUTING,
CHANGELOG, CI action pins.

Goal: every user-facing document asserts only what the code does at HEAD.
Closes D1, D2, D3 of docs/handover-review.md §2, the C1–C7/C9–C10 and G1–G7
inventories in §8, and the README/.env.example items that never reached that
punch list (the advisor's original list was a §5 artifact that arrived late;
every item below was re-verified against the tree on 2026-09-14).

Protocol (same as 001): paste this blueprint verbatim into
docs/handover-review.md as §9 BEFORE executing. When done, append the
execution record as §9.2 — departures with reasons, things left undone
deliberately, and what a live check found that the blueprint missed.

Prerequisites: run the suite first (.venv/bin/python3 -m pytest tests/ -q).
Do not trust any test count in this blueprint — re-derive it with
--collect-only -q; A1 exists precisely because counts drift.

PART A — README.md

A1. Test count, three places: the shields badge URL (tests-339%20passing),
the Testing section ("339 tests"), and the Project Structure comment
(tests/ # 339 tests). Update all three to the count at commit time.

A2. Workflows: "Three workflows ship" table and the workflows/ line in
Project Structure both omit triage-classify (1 node — triage alone; exists
so calibration costs ~$0.00002/call instead of a full workflow; see
workflows/triage-classify.yaml and HANDOVER §2.2). Add the row and comment.

A3. Configuration block shows VALIDATE_MAX_TOKENS=3000 and
SEARCH_MAX_TOKENS=1200. Actual defaults: 8000 / 1500, and
SEARCH_MAX_TOKENS_CONSEQUENTIAL=4000 is missing. Update to match
.env.example and say the README block is illustrative — .env.example
documents every setting.

A4. Limitations — two claims false since b4cd89f, remove or rewrite:
  - "The review verdict does not block" — the graph has a review_clean
    gate (on_fail: blocked). Review blocks.
  - "Retrieval and research cost is not attributed" — research, context
    and rerank all flow through the client meter since the cost-meter
    fix; total_cost is assigned from client.spend.
Re-verify the remaining Limitations lines while there (checked
2026-09-14: no code execution, negation gap, research-can-be-wrong,
quality-follows-models, no RBAC, no streaming, costs-are-real all still
true).

A5. Cost section: "one lookup per gap it finds, bounded at four"
contradicts the shipped policy (EXACTLY ONE bundled request carrying
every gap, MAX_LOOKUPS = 1; HANDOVER §4.3) and the README's own Research
section. Rewrite the research-overhead paragraph to the bundled shape.
Do NOT invent replacement numbers: re-derive them the same way the
workflow-comparison table was derived — BoundedRunner with billing
doubles, free, under a second — and say so in the text. If a number
can't be derived that way, state the shape without the number.

A6. Research intro editing artifact: "…so two things bound it:"
immediately followed by "Three things bound it, in the order they take
effect:" over FOUR bullets. One sentence, four bullets. (.env.example
already says "Four things bound it" — match it.)

A7. "Sonar-pro bills $15.00 per million output tokens…" — apply the
naming ruling (Part E): keep the number, anonymize the subject, e.g.
"One measured search model billed $15.00 per million output tokens plus
about $0.007 a request, and filled whatever cap it was given (2907 of
3000)…". The named subject stays in HANDOVER §6.3, which is the record.

PART B — .env.example

B1. Header: "until all four required model tiers name a model" → six.
(The tier list below it is already correct.)

B2. Retracted figure: "one pairing listed at 15x on completion measured
1.98x in practice" was measured with the pre-b4cd89f meter that did not
count search spend at all (HANDOVER §6.7 retracts it). Remove the figure.
The honest guidance is already stated beside it: the fee/token split
(13% fee / 87% tokens at a 3000-token cap, on the measured model) plus
"measure rather than assume".

B3. Garbled clause: "Only gaps are searched — facts the briefing already
established are missing —" → "Only gaps are searched — facts the briefing
did not already establish —".

B4. NEW, caught by cross-reading review §4.6 against this file: the
pinning block says "A pin disables fallbacks, so a run either uses the
provider you named or fails loudly." Measured (§4.6): a multi-name
allowlist fails over WITHIN itself — pinned [Perplexity, StreamLake],
Perplexity does not serve the model, the run succeeded via StreamLake.
Correct the line: fallbacks are disabled outside the named list; within
a list, serving fails over between the named providers. Keep the
pin-when-measuring advice. Optionally add the two shapes: one provider
for measuring (reproducibility), a measured 2–3 provider allowlist for
deployment (quality floor + failover).

B5. "Measured: sonar-pro bills $15.00/M output tokens…" in the
SEARCH_MAX_TOKENS comment — same ruling as A7: keep the number,
anonymize the subject.

PART C — CONTRIBUTING.md (C1–C7, C9–C10; the §8.1 inventory is accurate
— it was re-read at HEAD)

C1. Code Style "No comments unless the 'why' is non-obvious" invites
contributors to strip the codebase's most valuable property. Replace
with the real rule: comments record the measurement that set a constant.
Read the comment beside a constant before changing it; add one when you
set one (HANDOVER §4.4 convention 1).

C2/C3. "wire new phases into autornd/engine/workflow.py" (twice) — that
is the legacy sequencer, kept only as the graph's equivalence reference.
Correct path: _phase_<name> dispatch in graph/adapter.py with prompt text
in engine/phases.py, then a node in a workflows/*.yaml. The workflow
file is the product; the code is the engine.

C4 (three occurrences). "register its SpecialistRole in
autornd/models/verdicts.py" — roles are an OPEN vocabulary. A project
declares its roles under roles: in a profile; an undeclared role
resolves to a synthesized generalist. The shipped enum is defaults, not
limits, and editing it is not how anyone adds a role (HANDOVER §6.5 is
the measured reason — closed lists produced least-wrong labels, and
critical risk once staffed seven engineers on a retention schedule).

C5. The [seam]/[internal] list omits graph/ and evals/ entirely — the
actual engine and the quality harness. Add graph/spec.py (workflow files
are data), graph/executor.py, graph/adapter.py, graph/checks.py (new
deterministic checks are the welcome contribution — the README already
says so), graph/conditions.py, and evals/. Reclassify review
composition's [seam] entry per C6.

C6. "[seam] Review composition — risk-to-team mapping" no longer
describes the mechanism: the team is DERIVED from the specialists triage
assigned, scaled by risk — signature get_review_team(risk, domains,
specialists). Say that.

C7. "the sequencer, review composition, and routing layers all read from
the registry dynamically" — reword to the open-vocabulary reality:
shipped defaults + profile-declared, generalist fallback.

C9. "Running Tests": pytest tests/ -v → .venv/bin/python3 -m pytest
tests/ -q (pytest is not on the owner's PATH; the suite is ~9 s and
free — say so, it is a feature).

C10. Add a short Evals section: scenarios live in evals/scenarios/;
expectations are written BEFORE the run (convention 7); assertions are
free; --max-spend bounds a scenario; runs repeat because models are
stochastic; test doubles must bill like the real client
(client._account(...)) — a free double hides accounting bugs, and it
did. Point at README §Evals and HANDOVER §4.4 for depth.

PART D — CHANGELOG.md (G1–G7; §8.2 inventory)

The file is Keep-a-Changelog, frozen at [0.1.0] — 2026-09-12. Do NOT
turn 0.1.0 into a description of HEAD; it is a historical record. Two
exceptions, one addition:

D1. G3: "K3 escalation autopsy pattern" names a model by nickname in a
living document. Reword to the mechanism ("reasoning-model escalation
autopsy") without changing meaning. 0.1.0 was never a published release
and the nickname breaks the naming rule now in force.

D2. G1: "Full test suite (85 tests)" — verify before touching: find the
first commit (git log --reverse --oneline), count its test functions.
True at 0.1.0 → leave it. False at release → correct it. The current
count belongs to [Unreleased], not to 0.1.0.

D3. G7: add an [Unreleased] section recording the arc since 0.1.0, in
prose, with the measurements. Must include at least: the workflow graph
as data (three node kinds, gates, loops, exhaustion semantics; the
legacy sequencer kept as the equivalence reference under
tests/test_graph_equivalence.py); the eval harness (scenarios, free
assertions, BoundedRunner, per-tier spend, repetitions); outward
research with recall-before-search and the single bundled lookup; open
domain AND role vocabularies; client-side accounting and the meter fix
(b4cd89f — earlier figures understated, §6.7); per-tier provider pinning
and the measured serving-quality table; the review gate; the
unrecallable axis and the independent pass; risk-scaled search budgets;
and Blueprint 001's packaging fixes (flat-layout discovery, pyjwt in
project metadata, wheel package data). NO model ids anywhere in the
changelog.

PART E — the naming policy (the vendor-name ruling — record it, then
apply it)

The rule: zero model ids in code, configuration defaults, profiles,
workflow files, and any doc passage that recommends or defaults to a
model. Measured results may name their subjects and live in the
development records (HANDOVER §6, docs/handover-review.md). User-facing
docs carry the lesson with the subject anonymized where the id isn't
load-bearing. The closer a document is to configuration, the stricter
the rule.

Where to record it:
  - CLAUDE.md: if the invariants already state the zero-model-names
    rule, sharpen it in place with the selection-vs-record distinction
    (one clause). Do not add a duplicate numbered invariant.
  - HANDOVER §0: its sentence "zero model names outside .env.example
    illustrations" is now wrong on both ends — .env.example has none
    (and will stay anonymized), and HANDOVER §6.3/§6.4 deliberately
    names measured models. Verify the current text first; if unamended,
    fix the one sentence to the policy form. This is the ONLY HANDOVER
    edit in this blueprint.

PART F — CI action pins

Both jobs (test, editable-install): actions/checkout@v4 → @v6,
actions/setup-python@v5 → @v6. Both v6 lines are Node-24-native, which
clears the deprecation annotations (setup-python v6.0.0, 2025-09-04,
"Upgrade to node 24"; checkout v6.1.0 line). Do NOT jump checkout to v7
— fresh breaking change (allow-unsafe-pr-checkout) this repo doesn't
need. Verify both tags resolve and CI is green before finishing. Two
lines, nothing else in the workflow file.

PART G — optional but recommended; both FREE. Decide either way and
record the decision with a reason.

G1. A doc-names test (tests/test_docs.py or similar): scan the
user-facing doc set — README.md, .env.example, CLAUDE.md,
CONTRIBUTING.md, CHANGELOG.md — for vendor-model names (the regex family
the CLAUDE.md rewrite was verified with: glm, deepseek, minimax, sonar,
perplexity, gemini, kimi, qwen, gpt-, mistral, llama, and
claude-as-model) with an explicit allowlist for non-selections: the
protocol descriptors "OpenAI-compatible" and "OpenAI chat-completions"
(the wire protocol's industry name), "Claude Code" / the CLAUDE.md
self-reference. HANDOVER.md and docs/ are exempt BY POLICY — say so in
the docstring. Rationale: this failure class already happened three
times (the old CLAUDE.md model table, the K3 nickname, the sonar-pro
mentions); a free check is cheaper than a fourth.

G2. A badge-count test: parse the number out of the README tests badge
and assert it equals the collected count. The 339/501 drift happened.
If you judge the badge too brittle to maintain, the alternative is
dropping the count from the badge — record which you chose and why.

COMMIT GUIDANCE: prose, per convention 12. Name what was stale and what
made it stale: the docs predate the graph/b4cd89f changes and were never
revisited; the changelog froze at 0.1.0; CONTRIBUTING was teaching the
two mechanisms the project itself has since measured as wrong — closed
vocabularies and the legacy sequencer. One commit per document is
acceptable and probably clearer; the CI pin bump may ride along or
stand alone.

OUT OF SCOPE, deliberately: the Docker build job (HANDOVER §5 item 10
records it as the one uncovered install shape); any HANDOVER edit
beyond the single §0 sentence in Part E; any prompt, constant, or code
in autornd/; any live model call — this blueprint is free to execute
and verify (suite + CI only).
```

### 9.2 Execution record — 2026-09-14

Executed at `be8fd08`, one commit per document. The suite was 501 before and is
**504 after** — the three added tests are Part G's guards, and the count moving
is itself the first thing one of them caught.

**Prerequisite.** The count was re-derived with `--collect-only -q` rather than
trusted, as instructed: 501. Worth knowing that `grep -c 'def test_'` gives
**477** — parametrisation accounts for the other 24 — so the badge tracks
*collection*, and the Part G guard had to run collection in a subprocess rather
than count functions or read the current session.

#### What the blueprint asked for and did not get

**A5 — the number was derived, and the derivation changed a second row.** The
research overhead was re-derived the way the workflow-comparison table was: the
graph driven against billing doubles with an isolated store, free, in about a
second. It is **two research-tier calls plus at most one lookup** — one call to
write the retrieval queries, one to brief from what came back or to scope the
request when nothing matched. Both grounding shapes cost the same two calls,
which was worth establishing rather than assuming: with documentation ingested
the second call is a briefing, with an empty store it is a scoping analysis.
Low-risk work makes no lookup at all, so **its row was 9 and is now 8** — a
correction the blueprint did not ask for and the derivation produced.

Two things about that derivation are worth recording so nobody repeats them.
`run_scenario` re-isolates the knowledge store per scenario (`runner.py:253`),
so ingesting into an outer `_isolated_store()` and then calling it silently
discards the fixture — the with-documentation path has to be driven through
`GraphExecutor` directly. And a scripted double must return *plausible* query
expansions: nonsense queries retrieve nothing, the run falls through to the
empty-store branch, and the harness reports the shape you were trying to avoid
measuring.

**D2 — the inventory was wrong, and checking cost thirty seconds.** "85 tests"
was flagged as suspect. Counting test functions at `7fa5b11` gives exactly 85.
Left alone. §8.2 is corrected accordingly.

**Part G — both taken, and G1 failed on this pass's own work.** The doc-names
guard flagged exactly one line, written about an hour earlier in this same
session: the corrected pinning example in `.env.example` named a provider whose
name is also a model family. The two providers beside it are unambiguous and
stay; that one is described rather than named, and the identity lives in §4.6
where the measurement is. This is the argument for the guard in miniature — the
rule was being actively applied by someone who had just written the policy, and
it still leaked within the hour.

G2 was taken rather than dropping the count from the badge. The badge is a claim
about the repo and should be checked like one; the maintenance cost the
blueprint worried about is real but small, and the failure message names all
three sites that have to move together.

#### Departures

1. **`.env.example` got two fixes nobody listed** (recorded above as D6). Its
   workflow selector documented two of the four shipped workflows — omitting
   both triage shapes, including the one that makes a calibration sweep
   affordable, which is precisely what an operator reading that file wants. And
   `AUTORND_PROFILE` had been orphaned: its sixteen-line comment block sat above
   the provider-pinning section while the setting itself had drifted to the last
   line of the file, under documentation for something else. Both are the same
   class of defect as the rest of the pass — a document asserting less than the
   code does — so they were fixed rather than filed.
2. **A4 replaced a limitation instead of deleting it.** "The review verdict does
   not block" is false, but deleting it would overstate the position. Review
   blocks and does not *rework*: feeding findings back into implement and
   validate needs exhaustion semantics that are not settled, and the two phases
   can disagree indefinitely. That is the honest remaining limitation and it now
   says so.
3. **Part F stopped at v6 for `setup-python` as instructed**, though v7.0.0 also
   exists and the blueprint's v7 warning was about `checkout` only. Both v6 tags
   were verified against the registry; `setup-python` v6.0.0 is indeed the
   2025-09-04 Node-24 release.

#### Verified rather than asserted

- Every field on `Settings` appears in `.env.example` (`RUNTIME_MUTABLE` is a
  class constant, not a setting), which is what lets the README call that file
  the single source of truth for settings.
- The Limitations entries left in place were re-checked in the tree, not
  assumed: no role or admin field on the user model, no streaming path anywhere
  in `api/` or `routing/`, and `criteria_addressed` documenting its own term-
  overlap blindness at `checks.py:139`.
- `profiles.py:144-145` really does read `domains:` and `roles:`, and
  `registry.py:203` really does synthesize a generalist — CONTRIBUTING's new
  profile example was written against the code, not from memory.

#### Left undone, deliberately

- **The Docker build is still uncovered by CI.** Recorded in `HANDOVER.md` §5
  item 10 and explicitly out of scope here. It is the only install shape no job
  exercises, and the Dockerfile changed in Blueprint 001.
- **`profiles/example.yaml` declares no `domains:` or `roles:`.** It is the only
  tracked profile and the only worked example a new user gets, and it does not
  demonstrate the two vocabularies this pass spent a section explaining. Adding
  them touches a shipped profile rather than a document, so it is left for a
  blueprint that scopes it.
- **CI's matrix job still runs `pytest tests/ -v`** while every document now
  says `-q`. Verbose output is more useful in a CI log than in a terminal, so
  this is a deliberate inconsistency rather than an oversight.

---

## 10. Blueprint 003 — B3, the sweep-level spend cap (verbatim, as received)

**Status: executed 2026-09-14 — see §10.2.** Recorded here unexecuted first. Same protocol as 001 and 002.
The execution record is §10.2.

```text
BLUEPRINT 003 — B3: a sweep-level spend cap, plus truth fixes the last pass left.

Origin: HANDOVER §4.2 B3. --max-spend bounds ONE scenario-run (a fresh client
per attempt carries spend_ceiling=max_spend), so a 108-unit sweep at $0.25 is
a $27 ceiling. Its earlier sibling B10 was a budget counting the wrong unit.
This blueprint is FREE to build and verify: unit tests with billing doubles
(convention 9). The optional live proof costs at most one cent. No calibration
happens here — B4/B2 come after the owner's pin sweep, per HANDOVER §6.1.

Protocol (as 001/002): paste this verbatim into docs/handover-review.md as
§10 BEFORE executing. Append the execution record as §10.2: departures with
reasons, everything left undone deliberately, and anything live execution
found that this blueprint missed. Every value you touch gets a line in the
record — including "while here" items; the last pass changed a documented
default under that phrase without recording it, and that is how F1 happened.

Prerequisites: suite green (504) before and after; CI green before finishing.
Read first: autornd/evals/cli.py and autornd/evals/runner.py in full, plus
tests/test_evals.py's scripted doubles. Two §9.2 traps are load-bearing here:
run_scenario swaps in an isolated empty store per unit (outer store fixtures
are invisible — do not build tests on them), and a double must return
plausible query expansions or the run falls through to a branch you were not
measuring. Reuse the existing grounding-navigating doubles for the
full-workflow test; do not hand-roll new ones.

PART A — SEMANTICS (decided; relitigate only with a measurement)

A1. New flag --max-spend-sweep USD, aggregate across the ENTIRE invocation:
    every scenario × every repetition × every compared workflow, including
    the pinned per-scenario run_repeated calls in --compare mode. One budget
    object, created in main(), passed into every run_repeated call.

A2. Default $1.00, disable with --max-spend-sweep none. The default is a
    measurement, and its comment must say so: wide triage sweeps cost
    $0.01–0.03, grounding $0.17–0.72, the planned search-swap test ~$0.40 —
    all fit. The runaway shape this exists for — a full-workflow wide sweep,
    108 × ~$0.1454 (post-b4cd89f meter) ≈ $15.7 — is stopped at ~$1.00 and
    requires a conscious override. That is the control working.

A3. Enforcement, BEFORE any paid call, in two tiers:
    - FIT RULE (both caps set): do not start a unit unless
      spent + per_unit_cap <= sweep_cap. This makes the sweep cap a hard
      guarantee — total spend cannot exceed it, and no unit is ever aborted
      mid-flight by the sweep budget. Deliberately conservative: a unit is
      skipped even if it would have cost less than its cap. The guarantee is
      worth the occasional early stop. Record that as a decision, not a bug.
    - BACKSTOP (no per-unit cap): start a unit only while spent < cap, and
      set that unit's client spend_ceiling to the REMAINING budget, so the
      existing BudgetExceeded mechanism stops the unit the moment the total
      crosses. Overshoot is then bounded by a single model call. Compose, do
      not duplicate: the unit's ceiling is min(max_spend, remaining).

A4. Abort semantics. A unit stopped by the backstop carries its
    BudgetExceeded error exactly as a --max-spend abort does today (existing
    precedent, do not invent new behavior). Every unit that never starts
    gets ONE skip marker: a ScenarioRun with results=[] and an error
    "skipped: sweep budget exhausted ($X.XXXX of $Y.YY spent)". Extend the
    skipped predicate to recognize that reason alongside "not applicable",
    so skipped units are excluded from pass rates and the applicable count,
    exactly like not-applicable ones. The CLI exit rule "passed or skipped"
    then yields exit 0 on exhaustion — a truncated sweep with honest partial
    results is a successful bounded measurement, not a failure. Recorded
    decision; one line to change later if a failure signal is ever wanted.

A5. --max-spend semantics UNCHANGED. But fix its --help: state precisely
    that it bounds one scenario-run (one repetition), and replace the
    pre-epoch "$1.28" anecdote — the true figure is ~$3.30 and the $1.28 was
    the broken meter's reading (HANDOVER §6.7). Either cite the true number
    with that note or drop the number; never a pre-b4cd89f figure unlabelled.

A6. Reporting. After all reports, print one line when a budget was in
    effect: "sweep budget: $X.XXXX of $Y.YY · exhausted after N of M units"
    (omit "exhausted after" when it ran to completion). The skip markers
    carry their reasons in the per-scenario lines already.

PART B — IMPLEMENTATION SHAPE

B1. SweepBudget dataclass in autornd/evals/runner.py:
    cap, spent; remaining; can_start(per_unit_cap) implementing A3;
    record(cost) called after EVERY unit, including failed and aborted ones
    (ScenarioRun.cost is client.spend for that unit). Float comparison with
    a small epsilon; comment it.
B2. Thread an optional budget through run_suite AND run_repeated (symmetry;
    tests may use either) and into run_scenario, which composes the client
    ceiling per A3. The CLI creates one budget and passes it to every
    run_repeated invocation — including the pinned-scenario loop; that is
    the multi-call trap in compare mode.

PART C — TESTS FIRST (pre-registered, convention 7; every double bills)

C1. Fit rule: three scripted units billing $0.50 each, --max-spend 0.50,
    sweep $1.20 → units 1–2 run ($1.00), unit 3 never starts, one skip
    marker, no mid-unit abort, summary spent $1.00.
C2. Backstop: no per-unit cap, sweep $1.20, double bills $0.15/call →
    third unit starts at $1.00, dies crossing the cap via BudgetExceeded,
    overshoot ≤ one call's price, later units skipped.
C3. One budget spans compare mode: two run_repeated calls against one
    budget object; exhaustion in the first starves the second.
C4. Flag behavior: absent → $1.00 effective and printed; "none" → uncapped.
C5. Regression: --max-spend alone behaves exactly as before (the existing
    eval tests are the regression suite — they must pass unmodified).
C6. One full-workflow test where the budget lands on the RESEARCH/SEARCH
    path — the expensive tiers — using the existing grounding-navigating
    doubles. The abort must land on the expensive path, not before it.

Badge: the G2 guard will fail the moment these tests land. Update the
README badge AND the Testing count AND the Project Structure comment in the
SAME commit — that is what the guard is for.

PART D — TRUTH FIXES FROM THE ADVISOR'S 002 AUDIT (all small, all in this pass)

D1. API_HOST (F1 — the lie the last pass planted). config.py defaults
    api_host to "0.0.0.0" while .env.example and README now say "defaults
    to loopback". Resolution — CODE side, owner-vetoed: change config.py to
    api_host: str = "127.0.0.1", with a comment naming why (no rate
    limiting, spends real money, Docker passes --host 0.0.0.0 on its own
    command line, README says do not expose directly). Add a settings test
    asserting the default. The docs are then true as written. If the owner
    vetoes before you execute, flip to the docs-side fix instead:
    document 0.0.0.0 honestly and keep the security warning. Do NOT leave
    the two disagreeing.
D2. Research-call count (F2): .env.example's RESEARCH block says the
    no-docs shape is "one small call"; README's derived cost section (and
    commit 2214b05) say both grounding shapes cost the same TWO calls.
    Re-derive the empty-store path with billing doubles (free, seconds),
    fix whichever document loses, and name the derivation in the comment.
D3. CLAUDE.md: "17 test files" → 18 (this pass's own test_docs.py).
D4. README Testing command: pytest tests/ -v → .venv/bin/python3 -m pytest
    tests/ -q, matching CONTRIBUTING and CLAUDE.md.
D5. HANDOVER §4.2 B3 row and §5 item 2 → closed, with the semantics in one
    sentence each.

PART E — DOCS

README Evals: "Runs are bounded" gains the sweep cap (default, disable
token, hard-guarantee-when-both-caps-set). CONTRIBUTING Evals: the
"Always pass --max-spend" bullet mentions the sweep cap and that it is on
by default. CLAUDE.md working rules: mention the sweep cap in the
--max-spend line. Nothing else.

OPTIONAL LIVE PROOF (≤ $0.01; do it if convenient, skip honestly if not):
  .venv/bin/python3 -m autornd.evals.cli \
    --scenarios evals/scenarios/wide --workflow triage-classify \
    --repeat 1 --timeout 45 --max-spend-sweep 0.001
Pre-registered expectation: aborts after roughly 4–6 of 36 units (per-unit
≈ $0.0002, varies by provider), spent ≈ the cap, skip markers present,
exit 0, partial results rendered. Any deviation — including "my
expectation was wrong" — is reported and recorded in §10.2.

OUT OF SCOPE, deliberately: the production/API path (no cap there —
aborting live work destroys it, and search is structurally bounded);
changing --max-spend behavior; B4/B2 calibration (pin first — §6.1);
the Docker CI job and profiles/example.yaml (queued as their own small
blueprints).

COMMIT GUIDANCE: prose, convention 12. Name the history — the runaway
this prevents, the $27 arithmetic, B10's sibling (a budget counting the
wrong unit), and that every figure cited is post-b4cd89f. If D1 lands
code-side, its commit (or its paragraph) must say it is a behavior change
and what a LAN user must now set.
```

### 10.2 Execution record — 2026-09-14

Executed at `2214b05`, one commit. Suite 504 → **527**; 23 tests added, every
double billing. CI green. Live cost: **$0.0009** total, against a $0.01
authorisation.

#### Every value touched

| value | from | to | why |
|---|---|---|---|
| `--max-spend-sweep` | — | new, default `$1.00` | A1/A2 |
| `config.py` `api_host` | `0.0.0.0` | `127.0.0.1` | D1 — **behaviour change**, below |
| `.env.example` no-docs grounding | "One small call" | two calls | D2, re-derived |
| `CLAUDE.md` test files | 17 | 19 | D3 |
| `README.md` test command | `pytest tests/ -v` | `.venv/bin/python3 -m pytest tests/ -q` | D4 |
| README badge / Testing / tree | 504 | 527 | forced by the G2 guard |
| `sweep_summary` cap format | `:.2f` | `:.4f` | found by the live run, below |
| `research.py` ×1, `context.py` ×5 | swallow `BudgetExceeded` | re-raise | found while building, below |

Nothing else was touched. No "while here" edits.

#### What building it found — the bug worth more than the feature

C6 asked that the abort land on the search tier. It did not: the run continued
past the crossing and died on the *next* phase. Six handlers catch `Exception`
around a paid call — `research.py:151` and `context.py` at query expansion,
briefing synthesis, both rerank strategies, and scoping — and every one of them
swallowed `BudgetExceeded`. Each exists for a good reason (a failed lookup must
not sink a workflow) and each was also eating the signal that says *stop
spending*.

Two of them are worse than the rest: the rerank sites **latch their strategy**
off any exception, so a budget abort would have permanently marked a working
rerank API as unsupported for the life of the process. That is §6.8's "the
rerank fallback latched on any exception" happening again, to a new exception
type, in the same lines that were fixed the first time. A budget stop is a
decision, not a failure. All six now re-raise.

Without this the sweep cap does not work — it would have shipped looking
correct, since every unit test that does not cross a budget inside a research
call passes either way.

#### The pre-registered overshoot bound was wrong

A3 states overshoot under the backstop is "bounded by a single model call". It
is not. Feasibility, domain review and final review each run their rosters
through `asyncio.gather` (`phases.py:310`, `512`, `725`), so a whole roster can
bill between the crossing and the raise — **measured at two calls** with a
two-specialist roster, giving $1.30 against a $1.20 cap where the blueprint
predicted $1.25. The true bound is the widest parallel fan-out.

The test is named for what it measures rather than adjusted quietly, the
docstring says the same, and a companion test asserts the contrast that makes
the looser bound acceptable: **with both caps set there is no overshoot at
all**, because no unit that might not fit is ever started. The fit rule is the
strong guarantee; the backstop is the weak one.

#### The live proof — expectation wrong, mechanism right

Pre-registered: "aborts after roughly 4–6 of 36 units (per-unit ≈ $0.0002),
spent ≈ the cap, skip markers present, exit 0".

**First run, as specified (`--max-spend-sweep 0.001`): all 36 units ran, total
$0.0007, nothing skipped.** The cost estimate was 10× high. A `triage-classify`
unit costs about **$0.00002**, not $0.0002 — which is exactly the figure
`HANDOVER` §2.2 already claims for this workflow, so the blueprint's estimate
was the outlier, not the measurement. The whole 36-sector sweep fits inside a
tenth of a cent.

So the cap was re-run at `0.0002`, tight enough to actually bite:

```
12/16 scenarios passed every repetition · 16 calls · 45.8s · $0.0002
sweep budget: $0.0002 of $0.0002 · exhausted after 16 of 36 units
```

Sixteen units ran, twenty carried the skip marker with its reason, spend landed
**exactly on the cap with no overshoot**, and the pass rate reads `12/16` rather
than `12/36` — the skipped units are correctly out of the applicable count.

One claim in A4 is *not* demonstrated by this run: **exit 0 on exhaustion.**
Both runs exited 1, because genuine assertion failures were present among the
units that did run. Exhaustion alone does not fail a run — the exit rule is
"every result passed or skipped" and skipped now includes budget skips — but
this live run cannot be the evidence for it; the unit tests are.

The first run also printed `sweep budget: $0.0000 of $0.00`, because the cap was
formatted to two decimals and a $0.001 cap rounds to nothing precisely when the
budget is tightest. Fixed to four decimals, with a regression test. A defect
that only a live run with an unusual value would have surfaced.

**Incidental, not this blueprint's business but worth recording:** unpinned, the
sweep scored **31/36** served by a mix of OpenInference and StreamLake, which
sits exactly where §6.1 predicts an unpinned mix. Four of the five failures are
already-known: `legal_ops`, `building_services` and `geotechnical`
under-classifying (B4 and the §6.1 cheap-serving pattern), with `appsec` and
`textiles` over-classifying on `risk_at_most`. No calibration was attempted and
none should be until the pin sweep — §6.1.

#### Credentials

The key in the local `.env` was dead: the first attempt returned 401 on all 36
units and billed nothing. A replacement was supplied in conversation and written
only to the untracked, gitignored `.env`. **It should be rotated** — it has been
pasted into a chat transcript, which is the same exposure `HANDOVER` §3.6
already flags for the earlier keys. `git ls-files` still shows `.env.example` as
the only env file tracked.

#### Departures

1. **`api_host` is a behaviour change, taken code-side as instructed.** The
   default has been `0.0.0.0` since the initial commit while both `.env.example`
   and the README said loopback; the documents were right about what it should
   be. Verified before changing: the value is read only by
   `python -m autornd.main`, and the Dockerfile passes `--host 0.0.0.0` on its
   own command line, so containers are unaffected. **Anyone serving a LAN from
   the module entry point must now set `API_HOST=0.0.0.0` deliberately.**
2. **One commit rather than two.** The G2 badge guard couples the test count to
   the README, and D1 adds tests, so splitting would have left the first commit
   failing its own guard. D1 gets its own paragraph in the message, which the
   blueprint allows.
3. **C6 uses a billing double built here, not the existing grounding doubles.**
   The ones in `test_knowledge.py` are `AsyncMock`s that never call `_account`,
   so they cannot exercise a spend ceiling at all — convention 9 is the reason
   the blueprint's instruction could not be followed literally. The new double
   reuses `test_evals`'s `scripted()` for phase replies and adds only the
   grounding shapes, plus a mocked `chat`: `test_evals`'s double leaves `chat`
   live, which is safe there only because its replies never produce unknowns and
   so never reach the search path.

#### Left undone, deliberately

- **No calibration.** B4 and B2 wait for the owner's pin sweep (§6.1). The 31/36
  above is an observation, not a tuning input.
- **No cap on the production path.** Unchanged and deliberate: aborting a live
  workflow destroys work, and search is structurally bounded at ≈$0.07.
- **`--max-spend` semantics unchanged**, per A5. Only its help text moved, and
  the pre-epoch "$1.28" is now "$3.30" with a note that the smaller figure came
  from the meter that did not count search.
- Still queued from earlier passes: the **Docker build** CI job, and
  **`profiles/example.yaml`** declaring no `domains:`/`roles:`.

---

## 11. Blueprint 004 — Docker CI, the example profile, budget transparency, and the B6 probe (verbatim, as received)

**Status: executed 2026-09-14 — see §11.2.** Recorded here unexecuted first.

```text
BLUEPRINT 004 — three free closures and one guard: Docker CI, the example
profile, budget-transparency tests, and the B6 probe workflow.

Protocol (as 001–003): paste verbatim into docs/handover-review.md as §11
BEFORE executing; append §11.2 (departures, left undone, what live execution
found). PROVENANCE RULE, new and binding: every number below carries
[measured: §ref], [derived: method], or [estimate → derive before use].
Estimates set expectations only — never gates. Read HANDOVER §6 before
trusting any figure, including mine.

Prerequisites: suite green (527) before and after; CI green before finishing.

PART A — Docker CI job (closes HANDOVER §5 item 10, the last uncovered
install shape)

A1. New `docker` job in ci.yml: `docker build -t autornd:ci .`, run the
image detached on 8100 with the same dummy env block the existing jobs
use (six MODEL_* tiers; the key defaults to empty), then smoke:
  - GET /api/health → 200. Assert what the code actually does: degraded
    with tier names is an acceptable — and expected — result with dummy
    models. READ main.py's startup first: if startup crashes on an
    invalid/empty key, that is a finding to record, and the smoke asserts
    the truth, not a vacuous pass.
  - GET / → 200: proves dashboard.html resolves inside the container —
    the wheel-data fault class in its real deployment shape.
  - Retry loop, not a bare sleep (startup is seconds [estimate → the
    job's own timeout is the derivation]; ~10 tries × 2s is fine).
  - On failure, dump `docker logs` before the job fails.
A2. Do not push images. No registry, no tags beyond the local build.

PART B — profiles/example.yaml (closes the §10.2 carry-forward)

B1. Content decision [taste, grounded in §0 "any team" + §6.5]: the only
worked example a new user gets must demonstrate the OPEN VOCABULARY with
a NON-engineering team — the shipped defaults already teach engineering;
the example's job is to prove the "works for any team" claim. Use a small
content/marketing studio: three domains (e.g. brand_strategy, copywriting,
seo_analytics) and three or four roles (e.g. copywriter, editor,
fact_checker — fact_checker is deliberate: it echoes the
anti-confabulation theme). Derive the EXACT yaml schema from
autornd/profiles.py and tests/test_profiles.py — do not invent fields.
Heavily commented: the file is a teaching artifact, and the comments carry
the §6.5 rationale (closed lists produced least-wrong labels; measured).
~20 lines of yaml plus comments.
B2. Tests: the example loads through the profile loader; it declares at
least one domain and one role NOT in the shipped enums; a declared role
resolves to itself, not the synthesized generalist.
B3. Extend the G1 naming guard's scan set with profiles/*.yaml and
workflows/*.yaml (shipped config is user-facing; model ids are banned
there by the Part-E policy of Blueprint 002). The example must pass it.
B4. One README line in the profiles section pointing at the example;
check CONTRIBUTING's profile example (from the 002 pass) agrees with the
shipped file — one of them will need to match the other.

PART C — budget-transparency pin tests (the class guard for the bug 003
found)

C1. tests/test_budget_transparency.py: for each paid-call handler that
has a broad except — expand_queries, synthesize_briefing, analyze_request,
research_gaps, and rerank_chunks in BOTH native and listwise modes
(monkeypatch the mode/settings as needed) — inject a client double whose
paid methods raise BudgetExceeded, and assert it ESCAPES the function
(pytest.raises). These are propagation tests, not accounting tests: the
double raises before billing, and convention 9 does not apply — say so
in the docstring so nobody "fixes" it.
C2. File docstring names the pattern for future sites: when adding a paid
call with a broad handler, the same commit adds its transparency test.
Rationale comment cites BOTH occurrences — §6.8's original latch and
003's rediscovery in the same lines: the class has bitten twice, and a
pinned test set is the cheapest insurance against a third.

PART D — workflows/independent-check-probe.yaml (pre-builds the B6
artifact so the owner's afternoon can observe it live)

D1. Build the probe exactly per the B6 plan already delivered: 7 nodes
(triage, context, plan, implement, validate, review + review_clean gate,
independent_check with `when: "triage.unrecallable"`), single pass by
design — no build_loop, no feasibility, no escalation path.
D2. Spec test: loads; node order as above; the when clause present on the
last node; no loop or escalation nodes. Free.
D3. The live run is OUT OF SCOPE here — it needs MODEL_PREMIUM configured
owner-side and runs in the measurement afternoon under the default $1.00
sweep cap, which bounds the [estimate → measure] ~$0.05–0.15 run cost.

PART E — records

E1. HANDOVER §5 item 10 → closed (Docker shape now exercised). §10.2's
carry-forward list → both remaining items closed by this blueprint.
E2. Record the provenance rule in the review doc's blueprint-protocol
preamble (it is now binding on future blueprints), and add one line to
HANDOVER §4.4 pointing at it — convention 7's family: expectations are
written before runs, and numbers are sourced before they are asserted.

COMMIT GUIDANCE: prose. Name the lineage: the Docker job closes the last
install shape after 001's lesson (the fault a suite structurally cannot
see is the one that ships); the example profile teaches the vocabulary
§6.5 paid to open; the transparency tests pin the class that §6.8 and
B3 each caught a different instance of; the probe exists because nine
full-workflow attempts never legitimately reached the independent pass
(B6). The G2 badge guard will fire when tests land — update badge, Testing
count, and tree comment in the SAME commit.

OUT OF SCOPE, deliberately: calibration of anything (B4/B2 wait on the
owner's pin sweep — §6.1); any prompt or constant inside autornd/engine;
the production API path (no cap there, unchanged).
```

### 11.2 Execution record — 2026-09-14

Executed at `3502baf`, one commit (`2eae652`). Suite 527 → **553**, 26 tests
added. CI green on all five jobs, the new `docker` job included, first run.

#### Every value touched

| value | change | why |
|---|---|---|
| `.github/workflows/ci.yml` | new `docker` job | A1/A2 |
| `profiles/studio.yaml` | new file | B1 |
| `profiles/example.yaml` | gains `domains:`/`roles:` | §10.2 carry-forward |
| `workflows/independent-check-probe.yaml` | new file | D1 |
| `tests/test_budget_transparency.py` | new, 11 tests | C1/C2 |
| `tests/test_shipped_examples.py` | new, 15 tests | B2/D2 |
| `tests/test_docs.py` | scan set gains `profiles/*.yaml`, `workflows/*.yaml` | B3 |
| README profiles section, CONTRIBUTING | pointer to the new profile | B4 |
| README badge / Testing / tree | 527 → 553 | forced by the G2 guard |
| `CLAUDE.md` test files | 19 → 21 | follows the new files |
| `HANDOVER` §4.4 | new convention 13 (provenance) | E2 |
| `HANDOVER` §5 item 10 | closed | E1 |
| this document, §0 | new — the blueprint protocol | E2 |

No "while here" edits.

#### The Docker job could not be verified locally, so it was derived instead

This box has no Docker (`HANDOVER` §1: no sudo, no system pip, no Docker), so
the job's first real execution was in CI. Rather than guess at the assertions,
the server was run locally under `uvicorn` with the same placeholder tiers and
an empty key, and the smoke was written against what it actually returned.

That mattered. The obvious assertion — health returns `ok` — is wrong: with
placeholder ids every tier comes back `available: false`, so **`degraded` naming
all six tiers is the correct answer**, and a smoke accepting `ok` would have
proved only that the check never ran. The catalogue endpoint needs no auth
(§4.7), so the container reaches it even with no key and gets real negatives
rather than the `available: None` path.

CI confirmed the local derivation exactly:

```
answered after 2 attempt(s)
{"status":"degraded","unverified_models":["triage","engineering","architecture",
 "escalation","research","search"],...}
dashboard served, 34902 bytes
```

34,902 bytes in the container, byte-identical to the local run — the template
resolves in the image, which is B1's wheel-data fault in its deployment shape.

**Provenance check on the blueprint's one estimate.** A1 gave `~10 tries × 2s`
as `[estimate → the job's own timeout is the derivation]`. Derived: **2
attempts**, in CI and locally. The loop has roughly five times the headroom it
needs, which is the right direction for a retry loop and is now a measured
number rather than a guess.

#### Departures

1. **The probe has 8 nodes, not 7.** D1 says "7 nodes" and then lists eight:
   triage, context, plan, implement, validate, review, `review_clean`,
   `independent_check`. The list was taken as authoritative over the count.
2. **The non-engineering example is a new file, not a rewrite of
   `example.yaml`.** B1 wants the worked example to be a team that is not a team
   of engineers; `example.yaml` cannot become one, because
   `tests/test_profiles.py` pins its name to `SmartFactory` in three places and
   `docs/smartfactory/` is keyed to that name — rewriting it would have broken
   passing tests to satisfy a taste decision. So `profiles/studio.yaml` carries
   the non-engineering demonstration in full, and `example.yaml` gains a small
   declaration of its own so that the file §10.2 actually named stops being the
   one that teaches nothing. Both halves of the intent are met; neither test is
   broken.
3. **C1 gained a class the blueprint did not ask for.** Every propagation test
   would also pass if the handlers simply stopped catching anything — which
   would undo the reason each handler exists. Four companion tests assert
   ordinary failures *still* degrade: a broken expansion falls back to the raw
   request, a failed lookup returns no findings rather than failing the run, and
   ranking falls back to retrieval order. Without them the guard is buyable by
   deleting the thing it guards.
4. **The "B6 plan already delivered" is still not in the repo.** §5 lists it as
   absent and it remains so; D1's node list was complete enough to execute from,
   so nothing was reconstructed. If a fuller plan exists, it lives outside this
   repo.

#### Left undone, deliberately

- **The probe has never been run.** It needs `MODEL_PREMIUM` configured, and the
  live run is the owner's — B6 is only closed when the independent pass is
  observed executing, not when the shape that should reach it exists. The
  default $1.00 sweep cap bounds it; the per-run cost is still
  `[estimate → measure]`.
- **No calibration.** B4 and B2 wait on the pin sweep (§6.1), unchanged.
- **The API key supplied during Blueprint 003 is still unrotated.** It was
  pasted into a transcript; §10.2 says the same thing and it stays true.

---

## 12. Blueprint 005 — Calibrate: pin the triage tier, close B4, settle B2 (verbatim, as received)

**Status: recorded, NOT executed — blocked at owner gate G-1.** The exposed API
key has not been rotated: the key in the local `.env` is byte-identical to the
one pasted into the working conversation (verified by fingerprint, 2026-09-14).
G-1 is blocking and non-delegable, so no part of A, B or C has run. The two free
prerequisites were completed and are recorded in §12.1.

```text
BLUEPRINT 005 — Calibrate: pin the triage tier, close B4, settle B2.

Origin: HANDOVER §4.2 B4 and B2; §6.1 makes a pin a precondition for both.
All parts are live measurement under the sweep cap Blueprint 003 shipped.

Protocol (as 001–004): paste verbatim into docs/handover-review.md as §12
BEFORE executing; append §12.2 after. Provenance rule binding, including the
extension: a count is a number; a count beside its list equals the list; the
list is authoritative on disagreement. Prerequisites: suite green (re-derive
the count, do not trust 553), CI green before finishing.

PART 0 — owner gates, blocking and non-delegable
G-1: the exposed key is rotated and the new one written to local .env at the
     terminal. Nothing below runs before this. If it has not happened, stop
     and say so.
G-2: Part A ends in a STOP; the owner's one-line reply confirms the pin.
G-3: no .env edits in this blueprint. Experiments use env-var prefixes.
Pre-flight (free): before relying on prefixes, verify env-var-over-.env
precedence with a one-line settings assertion and record the result.

PART A — pin sweep  [measured basis: §6.1]
A1. Six invocations, one per §6.1 provider pinned to the triage tier, plus
    one unpinned baseline:
    OPENROUTER_PROVIDER_ORDER=triage:<Name> \
      .venv/bin/python3 -m autornd.evals.cli \
      --scenarios evals/scenarios/wide --workflow triage-classify \
      --repeat 3 --timeout 45 --max-spend 0.05 --max-spend-sweep 0.10
    Wall clock 5–25 min each [measured: §6.1]; run as a background loop.
    Total ≈ $0.02–0.15 [measured: §6.1 per-sweep costs].
A2. Pre-register BEFORE running, per invocation: predicted sectors passing
    and predicted under-classified sectors. Known priors [measured]: the
    StreamLake pin 33/36 under-classifying water_treatment, building_services,
    legal_ops; the OpenInference pin 28/36 in the same shape; unpinned
    ~30–31/36 (§10.2's incidental run scored 31/36). The other three
    providers have no individual prior — that is why they are swept; write
    "no prior" rather than inventing one.
A3. Record into §12.1, one row per invocation: pin, sectors passing, cost,
    wall clock, under-classified sectors, over-classified sectors. Also
    record providers_by_function from the unpinned baseline — who actually
    served, as data.
A4. Proposal rule: any pin under-classifying ≥2 sectors on ≥2/3 repetitions
    is DISQUALIFIED for triage regardless of price — under-classification is
    the dangerous direction [§6.1]. Among the rest: most sectors passing;
    within one sector, the cheaper. Propose exactly one pin, with the row
    that justifies it. Then STOP. The owner's reply is G-2.

PART B — B4, under the confirmed pin
B1. FREE FIRST: Part A already paid for 18 legal_ops triage verdicts (six
    invocations × 3 repetitions — count follows the sweep list). Read their
    summary fields and diagnose why the governing-documents clause does not
    land: not recognized as governing? stage judged before consequence?
    Quote the verdicts. Do not spend a cent until this is exhausted.
B2. Reproduce under the pin only if B1 leaves the failure shape ambiguous.
B3. Minimal guide edit in phases.py targeting the diagnosed shape.
    Constraints, all measured and all load-bearing: the two-question ORDER
    stands (consequence before stage — reordering is what demoted the lintel
    and the sterilisation protocol, §6.6); the not-every-published-standard
    distinction stands (broadcast went high 3/3 without it); the
    protective-systems wording stands (the first version sent 200 t of
    livestock to critical). Add the measurement comment naming this run.
B4. Verify: legal_ops ×3 under the pin — pre-register 3/3 at its asserted
    floor (the scenario file is the authority on what it asserts; read it).
    Then the full wide ×3 as the regression net [measured cost ≈ $0.02–0.03
    pinned; caps 0.05/0.10]. Pre-register: no sector that passed 3/3 under
    this pin in Part A drops below 2/3 after the edit.
B5. Close B4 in HANDOVER §4.2; add the measured fact to §6.6.

PART C — B2, materiality
C1. Author five probe scenarios [count follows the list] into
    evals/scenarios/materiality/ — first verify how the suite globs behave
    so these stay out of default runs, and read scenario.py for the exact
    assertion vocabulary:
    three IMMATERIAL (medium-risk, externally visible work whose unknowns
    are cosmetic: FAQ copy before an announcement; tone and wording on a
    published page; internal changelog phrasing) and two MATERIAL
    (medium-risk work with a genuinely answer-changing unknown: a
    compliance threshold that varies by jurisdiction; a load figure that
    decides a code requirement). Each probe asserts its own risk class so a
    mis-classified probe is caught, not absorbed. A risk floor is never
    waivable — these probes must not be engineered to read low.
C2. Pre-register under the CURRENT gate: each immaterial probe marks 2–3
    blocking gaps and fires a lookup [measured: §6.2 — 0/33 empty, means
    2.7–2.9]; each material probe marks ≥1. Run all five, triage-only,
    repeat 2, --max-spend 0.05 --max-spend-sweep 0.50.
C3. Reframe synthesize_briefing from subset-selection to per-gap judgment:
    for each gap ask "would a wrong assumption here change the answer?" and
    DERIVE blocking from the yes-answers instead of requesting a subset.
    [prediction, labelled: self-restraint failed 0/33; question reframing
    worked for the risk guide and the schema retry — the codebase's own
    record favours reframing over restraint.]
C4. Re-run the five probes identically. Decision rule: keep the reframed
    gate ONLY if it zeroes blocking on all three immaterial probes AND
    keeps ≥1 blocking on both material probes. Any other outcome → drop
    the gate entirely and record the honest rationale [§6.2: with one
    bundled request only zero gaps saves money; the token budget is the
    only dial that costs anything].
C5. Close B2 either way. Add one line on the interaction: if 006-A later
    swaps the search model, a lookup becomes fee-dominated and the gate's
    maximum value shrinks to a fraction of a cent [derived: §6.3 fee/token
    split].

PART D — records
§12.1 tables, §12.2 execution record, HANDOVER B4/B2 rows closed, §6
additions. Commits in prose, per convention 12. The badge guard will fire
if tests are added — badge, Testing count, and tree comment move in the
SAME commit.

OUT OF SCOPE, deliberately: the production API path; any workflow yaml; the
search-tier swap (006-A); B6 and B7 (006); any change to the wide or
grounding scenario files beyond the new materiality/ directory.
```

### 12.1 Prerequisites and pre-flight — completed, free

Both were run before the gate stopped things, because neither spends anything
and both are inputs Part A needs regardless.

| check | result |
|---|---|
| Suite green, count **re-derived** rather than trusted | `553 passed`; `553 tests collected`. The blueprint's figure was right. |
| Env-var-over-`.env` precedence (G-3's premise) | **Confirmed.** With no prefix, `settings.openrouter_provider_order` is `''`; with `OPENROUTER_PROVIDER_ORDER=triage:PreflightProbe` prefixed, it reads `triage:PreflightProbe`. Prefixes override cleanly, so the sweep needs no `.env` edits. |

Nothing else has run. Parts A, B and C are untouched.

### 12.2 Part A — pre-registered predictions, written before any sweep ran

G-1 cleared 2026-09-14: the key in `.env` no longer matches the exposed one
(fingerprint `d38e9ff…` → `d70e4c6…`). Committed before the first invocation so
the predictions cannot be tidied afterwards.

All five §6.1 provider names were confirmed live to still serve the triage
model — it currently has 17 endpoints, so the five swept here are a deliberate
subset carried over from §6.1, not the whole field.

The headline measure is **sectors passing every repetition** (3/3), which is
what `RepeatedRun.passed` counts; a sector at 2/3 reads as a failure in that
column and is recorded separately as flaky.

| invocation | predicted 3/3 sectors | predicted under-classified | basis |
|---|---|---|---|
| unpinned baseline | 30–31 / 36 | `legal_ops`, `building_services`, and at least one other that varies by serving | [measured: §6.1 = 30/36; §10.2 = 31/36] |
| `triage:StreamLake` | 33 / 36 | `water_treatment`, `building_services`, `legal_ops` | [measured: §6.1] |
| `triage:OpenInference` | 28 / 36 | `water_treatment`, `building_services`, `legal_ops` | [measured: §6.1] |
| `triage:Alibaba` | **no prior** | **no prior** | never swept individually |
| `triage:AtlasCloud` | **no prior** | **no prior** | never swept individually |
| `triage:DigitalOcean` | **no prior** | **no prior** | never swept individually |

Two further predictions, stated so they can be wrong:

- **Over-classification:** `appsec` and `textiles` fail `risk_at_most` on at
  least one invocation [measured: §10.2's incidental unpinned run failed exactly
  those two in that direction].
- **The §6.1 under-classified triple is not stable across servings.** §6.1
  names `water_treatment`, `building_services`, `legal_ops` failing on every
  repetition; §10.2's unpinned run instead failed `geotechnical` and *passed*
  `water_treatment`. So the predicted sector *sets* above are weaker claims than
  the predicted counts, and a mismatch in set membership is expected rather than
  surprising.

**A correction to the blueprint's own basis, recorded before it misleads
anyone:** §6.1's "12× the price bought five sectors of accuracy" compares
*observed sweep spend*, not list price. At list, the five providers swept here
span $0.120–$0.280 per million output tokens — a 2.3× spread, not 12×. The 12×
came from cheap servings also returning much shorter replies, so it is a
statement about total tokens billed, not about rate. Cost per sweep is still the
number to compare; the rate is not.

### 12.3 Part A — results

Six invocations, `evals/scenarios/wide` × `triage-classify`, `--repeat 3`,
`--max-spend 0.05 --max-spend-sweep 0.10`. Headline measure is sectors passing
**every** repetition. No invocation was truncated by the sweep cap.

| pin | 3/3 | cost | wall | under-classified (≥2/3 reps) | over-classified |
|---|---|---|---|---|---|
| unpinned → OpenInference | 27/36 | $0.0014 | 304s | building_services, geotechnical, legal_ops, water_treatment | appsec, textiles |
| `triage:OpenInference` | 27/36 | $0.0014 | 323s | + conservation, water_treatment 3/3 | appsec, textiles |
| `triage:DigitalOcean` | **22/36** | $0.0041 | 766s | geotechnical, legal_ops, water_treatment, dentistry | appsec |
| `triage:Alibaba` | 31/36 | $0.0317 | 886s | wind_energy | brewing, broadcast |
| `triage:AtlasCloud` | 32/36 | $0.0355 | 1274s | wind_energy | brewing |
| `triage:StreamLake` | **33/36** | $0.0184 | 2254s | **none** | — |

StreamLake's three non-clean sectors are not all classification failures:
`legal_ops` under-classified 1/3, `appsec` failed `unrecallable` 1/3, and
`dentistry` had one run **time out at 45s** — which is the missing 108th call.

**Predictions, scored honestly (§12.2):**

| prediction | outcome |
|---|---|
| unpinned 30–31/36 | **wrong** — 27/36. §10.2's 31 was `--repeat 1`; strict 3/3 scoring over three reps is harsher. The two numbers measure different things. |
| StreamLake 33/36 | **right**, exactly. Cost $0.0184 against §6.1's $0.0185. |
| OpenInference 28/36 | **near** — 27/36. |
| `legal_ops`/`building_services` under-classify somewhere | **right** |
| `appsec` + `textiles` over-classify | **right** |
| §6.1's under-classified triple is not stable across servings | **right**, and more so than expected — see below |
| Alibaba / AtlasCloud / DigitalOcean | no prior offered; DigitalOcean is the surprise at 22/36 |

#### ❗ B4 is a serving artifact, not a guide defect

`HANDOVER` §4.2 records B4 as `wide_legal_ops` under-classifying "on **every**
provider", and §5 item 4 as "guide's fault, not the serving's". Both are
**false**:

```
OpenInference 0/3    DigitalOcean 0/3    unpinned 0/3
StreamLake    2/3    Alibaba      3/3    AtlasCloud 3/3
```

The governing-documents clause lands. It does not land on a cheap serving. The
same holds for every sector §6.1 named as dangerous — `building_services`,
`geotechnical` and `water_treatment` are all clean on Alibaba and AtlasCloud.

#### Two corrections to §6.1's framing

1. **"Unpinned" is no longer a mix.** Unpinned and `OpenInference` returned
   identical scores, identical cost and the same failure set: today the tier
   routes to one provider. §6.1's "an unpinned score is partly a record of who
   answered" was written when five shared it. It currently answers "OpenInference"
   — the least accurate serving measured.
2. **Price buys accuracy, but the multiple is bigger than recorded.** 23× the
   cost (Alibaba vs OpenInference) bought 4 sectors; §6.1 recorded 12× for 5.
   The direction of the failures matters more than the count: cheap servings
   fail by **under**-classifying (7–10 sectors, the dangerous direction), the
   dear ones by **over**-classifying (1–2 sectors, the safe one).

#### Operational findings

- **StreamLake has roughly doubled in latency.** §6.1 clocked this sweep at
  1102s; it now takes 2254s and lost one unit to the 45s per-scenario timeout.
  A first attempt was killed at a 2400s ceiling.
- **A killed sweep loses everything it paid for.** That first attempt spent
  **≈$0.018** and wrote nothing: the CLI renders its report only after the last
  unit. Quantified by provider-side accounting, below.
- **The meter cross-checks against the provider.** OpenRouter's own
  `total_usage` moved $0.0937 across a window in which our meter recorded
  $0.0594 of *completed* runs; the difference is an in-flight run plus the
  killed sweep. This is the first external validation of the meter since
  `b4cd89f`, and it is consistent.

Part A total: **$0.0925 recorded + ≈$0.018 lost = ≈$0.11**, inside the
blueprint's $0.02–0.15 estimate.

### 12.4 Part B — B4, closed without touching the guide

G-2 answered: **`triage:Alibaba`**. A qualified pin under A4 — its only
under-classification on ≥2/3 repetitions is `wind_energy`, which `HANDOVER` B5
already records as deliberately left red — and the fastest of the three
qualifiers at 886s.

**B1 could not run as written, and did not need to.** It asks for the 18
`legal_ops` verdicts Part A already paid for, to diagnose why the
governing-documents clause does not land. Two obstacles, one fatal to the step
and one fatal to its premise:

- **The harness discards the verdicts it pays for.** `ScenarioRun` keeps
  results, calls, seconds, cost, error, path and per-tier accounting — but not
  the `ExecutionState` outputs, so the `TriageVerdict.summary` text is gone by
  the time a report exists. Diagnosing from a past sweep is not possible today;
  it would need a re-run capturing verdicts directly, or a field on
  `ScenarioRun`. Recorded as a finding, not fixed here — it is `evals/` code and
  outside this blueprint.
- **There is no failure to diagnose under this pin.** `legal_ops` passed 3/3
  under Alibaba in Part A. A diagnosis of why a clause fails cannot be written
  about a clause that works.

**B3 — the guide edit — was deliberately not made.** Characterising the sector
under the adopted pin, four runs, 24 repetitions in total:

| run | reps | result |
|---|---|---|
| Part A sweep | 3 | 3/3 clean |
| dedicated verification | 3 | 2/3 — one **ceiling** breach (read `critical`, ceiling `high`) |
| repeat 9 | 9 | at least one excursion (per-assertion breakdown not captured) |
| repeat 9 | 9 | 8/9 — one **floor** breach (read below `medium`) |

Roughly 87% clean, with rare excursions **in both directions**. That is not the
failure B4 describes — a deterministic under-classification on every provider,
measured at 3/3 failures on the cheap servings. Under a qualified pin there is
no systematic defect left to target, and editing the risk guide to chase a
one-in-nine excursion that goes both ways would be tuning against noise, which
is precisely what §6.1 warns against. The three load-bearing constraints B3
listed — question order, the not-every-standard distinction, the
protective-systems wording — are therefore untouched, as is everything else in
`phases.py`.

**B4's verification target, read from the scenario file as B4 instructed:**
`wide_legal_ops` asserts `risk_at_least: medium` and `risk_at_most: high`. The
floor is `medium`, not `high` — a softer bar than "under-classifies" suggests,
and the one the governing-documents clause exists to clear.

**The regression net was not run.** B4 specifies a full wide ×3 sweep to prove
no sector regressed "after the edit". There was no edit, so there is nothing to
regress; re-running it would re-measure Part A at $0.03 and fifteen minutes.
Part A's Alibaba row **is** the baseline.

Part B spend: **$0.0068**. No code, prompt or constant changed.

#### Still owner-side

G-3 forbids `.env` edits in this blueprint, so the pin is **not** written
anywhere. To adopt it:

```
OPENROUTER_PROVIDER_ORDER=triage:Alibaba
```

Until that line exists, the tier routes unpinned — which today means
OpenInference at 27/36, the least accurate serving measured.

### 12.5 Part C — B2, materiality

Five probes in `evals/scenarios/materiality/`, kept out of default runs by the
same non-recursive glob that excludes `wide/` (`scenario.py:187`, verified:
the default suite still loads 17 scenarios and none of them is a probe).

All five sit at the **deciding** stage rather than the acting one, so they read
`medium`. That is deliberate and load-bearing: low-risk work looks nothing up at
all (§4.3), so a probe that read `low` would measure the risk gate instead of
the materiality gate and prove nothing. A risk floor is never waivable, so they
are written to be genuinely medium rather than engineered to read low.

**Departure from C1's suggested content, recorded before running.** The
blueprint proposes "a load figure that decides a code requirement" as the second
material probe. §6.6 makes structural loading a harm rule and therefore
`critical` **at every stage**, so that probe would have failed its own risk
assertion and measured the risk guide rather than materiality. Replaced with an
accessibility conformance level — a published standard that §6.6 explicitly
classes as *not* a harm rule (quality and interoperability standards are not),
while still carrying an unknown that genuinely changes what gets built.

**Pre-registered, before the baseline ran, under the CURRENT gate:**

| probe | predicted blocking gaps | predicted lookup |
|---|---|---|
| `mat_immaterial_faq` | 2–3 | fires |
| `mat_immaterial_page_copy` | 2–3 | fires |
| `mat_immaterial_changelog` | 2–3 | fires |
| `mat_material_threshold` | ≥1 | fires |
| `mat_material_contrast` | ≥1 | fires |

Basis [measured: §6.2] — across 33 workflows the gate never returned an empty
blocking list, averaging 2.7–2.9 of a permitted 3. The prediction is therefore
that the current gate cannot tell these two classes apart at all, and that all
five fire a lookup.

**Which function is actually under test.** The blueprint names
`synthesize_briefing`. With an empty store — which `run_scenario` guarantees per
unit — the exercised path is `analyze_request` and its `blocking_unknowns`, not
`synthesize_briefing` and its `blocking_gaps`. Both carry the identical
subset-selection framing ("the subset of those where a wrong assumption changes
the answer. Often empty. Never more than three."), and §6.2's measurement was of
the scoping path, so the reframe targets both and the probes exercise the
scoping one.

#### Part C results — the gate stays, and the reason it exists changes

**The baseline killed the experiment's premise.** All three immaterial probes
read `low`, 2/2, and so never reached the materiality gate at all: the risk gate
zeroes lookups below medium (§4.3), and they made 3 calls each where the two
material probes made 4.

They were rewritten once to commit to something costly to undo — a print run, a
send to every user — since §6.6 puts copy on a page under "trivially
reversible". **They still read `low`, 2/2, all three.** Six probe designs,
twelve repetitions, and not one lookup fired.

| run | immaterial | material | cost |
|---|---|---|---|
| baseline, original gate | 3 calls each, no lookup | 4 calls each, lookup | $0.1317 |
| rewritten immaterial probes | 3 calls each, no lookup | — | $0.0105 |
| after the reframe | 3 calls each, no lookup | contrast **3**, threshold 4 | $0.0738 |

**C3's reframe was tried and is reverted.** Rewriting both gates from
subset-selection to per-gap judgment, with an explicitly named empty case, did
not zero anything immaterial — it zeroed a **material** lookup.
`mat_material_contrast` fired a lookup 2/2 before and 0/2 after. The prediction
that reframing beats self-restraint was reasonable from this codebase's own
record, and it is wrong here: the reframe suppressed research on a figure that
decides what gets built, which is the same dangerous direction as
under-classifying risk. `context.py` is unchanged.

**C4's rule, applied honestly, points at "drop the gate" — and the measurement
says do not.** The rule keeps the reframe only if it zeroes the immaterial and
preserves the material; it did the opposite, so the rule says drop the gate
entirely. Two measured reasons not to:

1. **The job the gate was built for is already done by the risk gate.** §6.2
   showed materiality only saves money by producing zero gaps. Zero gaps is
   exactly what work with cosmetic unknowns produces — because that work reads
   `low`, and low-risk work looks nothing up. Measured here, twelve times out of
   twelve. The two gates are not redundant by accident: **risk and materiality
   are correlated**, and the cheaper, deterministic gate already catches the
   class.
2. **The cap is doing a different and useful job.** Dropping the gate makes
   every gap blocking, so a medium-risk workflow would carry ~12 questions into
   one bundled request instead of ~3, against a fixed `SEARCH_MAX_TOKENS`. §6.3
   measured that the failure mode at a lean budget is **truncation of the tails
   of bundled questions** — tokens buy figures. Twelve questions on a 1500-token
   budget would answer each of them worse.

**B2's disposition: the gate stays, and its description changes.** It is not the
cost lever it was built to be — §6.2 was right about that and the finding
stands. It is a *question-count cap* that protects the per-question token
budget, and it should be understood and documented as one. Nothing about the
prompt changes; what changes is that nobody need keep trying to make it produce
empty lists, because the case where it should is already handled one gate
earlier and more cheaply.

Part C spend: **$0.2160**.

### 12.6 Execution record

*(Numbering departure: the protocol asks for the execution record at §N.2, but
§12.2 was spent on Part A's pre-registration — which had to be committed before
the first invocation ran. The record is here instead; §12.1–§12.5 are the
working sections, in order.)*

Executed at `4189518`→`c738271`. Suite **553 before and after** — no tests
added, no test file touched, so the badge guard did not fire. Every part of A, B
and C ran.

**Spend, reconciled against the provider.** OpenRouter's own `total_usage` moved
**$0.3165** across the window; our meter accounts for **$0.3173** of it once the
~$0.016 billed before the snapshot is excluded. Agreement within **0.3%**. The
cost meter, broken before `b4cd89f` and never externally checked since, is now
verified against the provider's books.

| part | spend |
|---|---|
| A — six pin sweeps | $0.0925 recorded + ~$0.018 lost to a killed run |
| B — B4 verification | $0.0068 |
| C — materiality probes, three runs | $0.2160 |
| **total** | **≈$0.333** |

#### Departures

1. **No guide edit (B3).** Under the adopted pin there was no systematic failure
   to target; §12.4 has the characterisation. Editing the risk guide to chase a
   one-in-nine excursion that goes in both directions is tuning against noise.
2. **No regression sweep (B4).** It exists to prove nothing broke after the
   edit; there was no edit. Part A's Alibaba row is the baseline.
3. **C1's load-figure probe replaced.** §6.6 makes structural loading `critical`
   at every stage, so it would have failed its own risk assertion.
4. **The immaterial probes were rewritten once** after reading `low`, then kept
   despite still reading `low` — the second result is the finding, not a defect
   to design around.
5. **C4's rule was applied and then argued with.** It points at dropping the
   gate; two measured reasons not to are in §12.5, and the gate stays with its
   purpose redescribed rather than its wording changed.
6. **The reframe (C3) is reverted**, not kept — it zeroed a material lookup.

#### What execution found that the blueprint did not anticipate

- **B4's premise was false.** Recorded as the guide's fault on every provider;
  it is the serving's, and pinning was the entire fix.
- **B1 is not possible today.** The harness discards the verdicts it pays for —
  `ScenarioRun` keeps cost, calls and assertions but not the execution state, so
  a past sweep cannot be diagnosed. Not fixed here: it is `evals/` code.
- **The blueprint named the wrong function for C3.** With an empty store the
  live path is `analyze_request`/`blocking_unknowns`, not
  `synthesize_briefing`/`blocking_gaps`. Both were reframed; both reverted.
- **A killed sweep loses everything it paid for** — ~$0.018 here — because the
  CLI renders its report only after the last unit.
- **StreamLake has roughly doubled in latency** since §6.1 and now loses units
  to a 45s per-scenario timeout.
- **Unpinned is no longer a mix**, so §6.1's framing of an unpinned score needs
  reading with today's routing in mind.

#### Left undone, deliberately

- **The pin is not adopted.** G-3 forbids `.env` edits here.
  `OPENROUTER_PROVIDER_ORDER=triage:Alibaba` is the owner's line to add; until
  then the tier routes to the least accurate serving measured.
- **C5's interaction note, recorded rather than acted on:** if 006-A swaps the
  search tier to a model at ~$1/M output, a bundled lookup becomes
  **fee-dominated** — §6.3 measured the fee at 13% of a 3000-token lookup at
  $15/M, and at $1/M the same fee is roughly 64%. The materiality gate's
  maximum possible value then shrinks to a fraction of a cent per workflow,
  which is a second, independent reason not to spend more effort on it.
- **B6 and B7** remain, and `wind_energy` (B5) is still deliberately red.

---

## 13. Blueprint 006 — Harden the instrument, then observe (verbatim, as received)

**Status: not executed at the time of recording.** Execution record: §13.2.

Pre-flight at recording time, all three clear: the owner's pin line
`OPENROUTER_PROVIDER_ORDER=triage:Alibaba` is present in `.env`, `MODEL_PREMIUM`
is set, and the search tier's cheap sibling is available from the catalogue.

```text
BLUEPRINT 006 — Harden the instrument, then observe: results retention, the
search-tier swap, the B6 probe run, and the B7 convergence traces.

Origin: two defects 005 paid to discover — the harness discards the verdicts
it buys (005's Part B1 was structurally impossible: no past sweep can be
diagnosed after the fact), and a killed sweep loses everything it paid for
(~$0.018 measured) because the CLI renders only at the end — plus review
§4.8 test #1, HANDOVER B6, and B7 phase 1 of 3: capture the evidence; the
advisor rules the design from the traces; the executor implements the
ruling. An executor design proposal is invited and will be adjudicated like
any departure.

Protocol (as 001–005): paste verbatim into docs/handover-review.md as §13
BEFORE executing; append §13.2 after — departures with reasons, left undone
deliberately, and anything execution found that the blueprint missed.
Provenance rule binding, counts included: a count beside its list equals
the list; the list is authoritative; estimates set expectations and never
gate. Prerequisites: suite green before and after (re-derive the count —
do not trust any number in this blueprint), CI green before finishing.
Paid parts pre-flight their env: Part D requires the owner's triage pin
line in .env; Part C requires MODEL_PREMIUM; Part B pins the search
serving per-run.

PART A — the instrument keeps its readings (FREE; run before any paid part
— B, C and D all run under its protection)

A1. ScenarioRun retains what it pays for: the per-attempt verdicts (every
    node's typed verdict, node_id → dict) and the client's
    providers_by_function — who actually served each function. Additive
    field with a default so no existing constructor call breaks.
    Rationale: §6.1's lesson is that an unpinned score is a record of who
    answered; retention that omits WHO answered leaves B4-class diagnoses
    impossible — which is exactly what made 005's Part B1 impossible.
A2. The CLI persists incrementally: after each unit (scenario × repetition
    × workflow) completes, append one JSON record to a results file —
    default evals/results/<utc-timestamp>-<suite>.jsonl, overridable with
    --results-file. An appended line is durable the moment it is written,
    so a killed sweep keeps everything it paid for; no signal-handler
    gymnastics. Record contents: scenario id, workflow, repetition, cost,
    calls, cost_by_tier, assertion results (name → outcome and detail),
    status, verdicts (from A1), providers_by_function. Write ONE header
    record at file open carrying the run configuration — tier → model
    map, pins, caps — so a results file is fully self-describing and a
    future failing sector can be priced against its serving without
    re-running anything.
A3. Add evals/results/ to .gitignore. Results files are local by
    default; measurement records reach the repo only by deliberate commit
    (the §12 tables, and in Part D the committed traces).
A4. README Evals and CONTRIBUTING Evals: one short paragraph each —
    results persist as JSONL, where they land, what a record carries, and
    that a killed sweep's data survives.
A5. Tests (billing doubles; the §9.2 traps apply — the store re-isolates
    per scenario, and doubles must return plausible query expansions):
      - a two-unit run writes a header record and two unit records that
        replay to the same pass/fail as the in-memory ScenarioRun;
      - a run aborted after unit 1 (simulate the abort — do not kill a
        real process in CI) leaves unit 1's record on disk;
      - a record contains verdicts and providers.
    The G2 badge guard fires when the count moves — badge, Testing count
    and tree comment move in the SAME commit.

PART B — search-tier swap (review §4.8 test #1)
B1. Pin the search tier's SERVING for BOTH runs — same provider for both
    models; that is what makes this a model comparison rather than a
    second §6.1 lottery. Verify both models are served by the named
    provider via the catalogue before running. Record the serving in
    §13.1.
B2. Two invocations on evals/grounding, triage-only, repeat 1, caps
    --max-spend 0.30 --max-spend-sweep 0.75 [derived: §6.3 grounding
    costs $0.17–0.72 across budget shapes]: the current MODEL_SEARCH from
    .env vs the cheap sibling from review §4.3's search-tier row (record
    the id in §13.1). Env prefix for the sibling; pre-flight assert
    settings picked it up (free).
B3. Pre-register BEFORE running: the current model recovers 5/8 at the
    1500-token cap [measured: §6.3]; the sibling has no prior — that is
    the question. Also record token-fill behaviour and per-run cost from
    the meter [measured: §12.2 — provider-verified to 0.3%].
B4. Output is a DECISION INPUT, not a decision: the table lands in
    §13.1; any .env change is the owner's (G-3). If the sibling matches
    figures at a fraction of the cost, the recommendation carries the
    numbers; if figures drop, the current model stands and §4.1's
    fee-inversion arithmetic stays a labelled projection. Record the
    interaction already noted in HANDOVER B2: if the swap lands, a
    lookup becomes fee-dominated and the materiality cap's value shrinks
    further.

PART C — B6: run the probe
C1. First close the records gap 004 reported: the B6 plan text is
    appended at the end of this blueprint — paste it into §13 with this
    blueprint so the repo finally holds the plan it executed. The built
    probe (workflows/independent-check-probe.yaml, 8 nodes) is
    authoritative on node shape; the plan text is the record.
C2. Mechanism: env-prefix the server — MODEL_PREMIUM=<the §4.4
    reassignment id> AUTORND_WORKFLOW=independent-check-probe — then
    POST /api/workflows/sync with the plan's request, then pull the
    workflow row and phase_results. If scenario.py admits a probe
    scenario, prefer the eval harness for its spend caps — read it and
    pick; record which and why. Cost [estimate → derive]: a handful of
    cheap calls plus one premium call.
C3. Pre-registered expectations (from the plan): triage marks
    unrecallable=true on the deliberately-irreversible, deliberately-safe
    request; every phase ships on trivial work; independent_check EXECUTES
    and returns a DoubleCheckVerdict with no critical issues. If triage
    will not mark unrecallable, that is itself a calibration finding — do
    NOT remove the when clause to force the pass. Every deviation
    reported honestly, including "my expectation was wrong."
C4. Close B6 with the trace as evidence (HANDOVER §4.2 and §5 item 6);
    the probe workflow remains the regression shape.

PART D — B7 phase 1: convergence traces (run AFTER Part A)
D1. FREE FIRST — record three facts from source, read not recalled (they
    are the design-relevant structure; no document states them):
      a. the build loop's entire feedback channel is
         failure_log[-1].red_cause — ONE string — plus
         resolution_directive after escalation; validate's findings and
         evidence are logged but never reach the next implement;
      b. domain_review concerns mutate the implement verdict but reach
         the next iteration only as the generic "Domain reviewer flagged
         critical concern" when critical;
      c. the loop's until tests validate.green ONLY — a critical domain
         review can flip implement red while validate stays green, and
         the loop EXITS CONVERGED-ON-RED. Whether that path occurs is an
         empirical question the traces answer.
D2. Author four hard scenarios [count follows the list], each
    pre-registered before running with expected iterations, expected
    red_cause shape, and predicted outcome: (1) multi-artifact numeric
    consistency — figures that must agree across sections of a written
    deliverable; (2) derived tolerances — values that must be recomputed,
    not copied; (3) cross-reference integrity — definitions used before
    they are defined; (4) verification-requires-execution — work whose
    honest validation needs running something: the structural axis §6.8
    diagnosed and the SPECIALIST_OUTPUT_CONTRACT only mitigates.
D3. Run engineering-rnd, repeat 1, --max-spend 0.75 --max-spend-sweep
    3.00 — a conscious override of the $1.00 default, the Part A
    rationale in person: this run buys the design input for the
    highest-value open problem, and Part A is what makes the spend
    survivable. [estimate → the caps are the bound.]
D4. Extract per-iteration records from phase_results (rows carry
    iteration; the persistence hook writes them) AND from Part A's JSONL
    (verdicts, providers). Classify each:
      red_cause → fixable-in-text | structural | token-starved;
      loop      → converged | stalled (same red_cause ≥2 consecutive) |
                  oscillating | converged-on-red | exhausted.
    Measure whether implement's summary substantively changes between
    iterations despite the one-string channel (free: length delta and a
    rough similarity).
D5. Deliverables: the taxonomy table with counts; all four traces
    committed as measurement records (deliberate commits, per A3);
    providers_by_function per trace — the B4 lesson in force: a failing
    trace is first priced against its serving, and who served is recorded
    before any prompt edit is proposed. An attached design proposal is
    invited; it will be adjudicated. Phase 2 (the advisor's): the design,
    ruled from this data, against the lever menu — stall detection and
    early escalation; widening the feedback channel past one string;
    aligning validate's prompt to the written-output contract; routing
    structural red_causes straight to escalation; an echo-the-findings
    forcing function on implement. Phase 3: implement the ruled design.
D6. Pre-registered, the advisor's, labelled [prediction] — they gate
    nothing, and 005 falsified one such prediction, which is the system
    working: stalls in ≥1/3 of non-converging runs; structural causes in
    ≥1/4 of red iterations; at least one converged-on-red. Wrong is
    recorded either way.

PART E — records and one stale row
E1. HANDOVER §4.2: close B6 per Part C. HANDOVER §5: strike item 3 — B2
    is resolved (§4.2 and §6.2 already say so; item 3 still presents the
    original three options as open) — and close item 5 once the owner's
    pin line is confirmed present in .env, recording the line and date.
E2. HANDOVER §6.7: add one line — the post-b4cd89f meter agrees with the
    provider's books to 0.3% across $0.32 of live spend (measured
    2026-09-14, §12.2), reading marginally high, the conservative
    direction for ceilings.
E3. HANDOVER header, §2.2 and §3.7: the test count and file count have
    drifted with every test-adding pass (header says 501). Update with
    the commit-stamped form the CHANGELOG uses: "N tests as of
    <commit>". The per-file table regenerates from a collection listing
    if convenient; the total is the mandatory part.
E4. CHANGELOG [Unreleased]: one short paragraph — the sweep cap and the
    budget-abort propagation fix; B4 resolved by pinning; B2 resolved as
    a question-count cap; the meter verified against the provider's
    books; the triage pin adopted. No model ids.
E5. §13.2 as ever: departures, left undone, and what execution found
    that the blueprint missed.

OUT OF SCOPE, deliberately: implementing ANY B7 mechanism before the
traces are read (the free stall check included — measure first, §0's own
rule); the production API path; any .env edit (G-3); the review→rework
loop (§5 item 12 — it needs exhaustion semantics and will be designed
with B7's data); per-tier pins beyond triage (roadmap item 8 — measure
each tier before pinning it).

COMMIT GUIDANCE: prose, convention 12. Name the lineage: the harness now
keeps what it pays for because 005 had to re-buy its own verdicts; the
search decision gets its table; the independent pass finally executes
inside a complete run; B7 gets designed from traces rather than taste.
```

### 13.0 The B6 plan — verbatim, recorded at last

`docs/handover-review.md` §5 listed this as missing from the repo through four
blueprints; §11.2 noted 004 executed from its node list without it. It is
recorded here so the repo holds the plan it executed.

```text
B6 — the goal is not to fix the flagship; it is to observe independent_check
execute inside a complete live run, which has never happened (nine attempts
each exited earlier for a legitimate reason). Apply the triage-classify
trick: a minimal workflow that reaches review_clean by construction.

Build workflows/independent-check-probe.yaml (BUILT — Blueprint 004):
triage, context, plan, implement, validate, review + review_clean gate,
independent_check with `when: "triage.unrecallable"`. No build_loop, no
feasibility, no escalation path — single pass by design.

The request must genuinely set unrecallable=true, or the last node
legitimately skips. Use a trivially-safe but irreversible framing, e.g.
"finalize the customer confirmation notice for a one-way production
database migration that has already been run" — decides nothing, harms
nobody, cannot be recalled. Per HANDOVER §6.6 that is exactly what sets
unrecallable without inflating risk. Do NOT work around the when clause
by removing it — if triage won't mark it, that is itself a calibration
finding; record it.

Pre-registered expectations (convention 7): ship=true on trivial work at
every phase; independent_check executes and returns a DoubleCheckVerdict
with no critical issues. Any deviation is reported honestly, including
"my expectation was wrong."

Deliverables: one clean full-path trace including independent_check
executing (phase_results from the DB); B6 closed in HANDOVER as observed
live, the probe workflow kept as the regression shape; the trace doubles
as live-path evidence toward eventually retiring engine/workflow.py.
```

### 13.1 Part B — the search-tier swap

**The serving is fixed by construction.** B1 asks that both models be pinned to
one provider so this is a model comparison rather than a second §6.1 lottery.
Checked against the catalogue: **both are served by exactly one provider,
Perplexity**, so no pin is needed and no lottery is possible. Recorded rather
than assumed.

| model | in $/M | out $/M | max out |
|---|---|---|---|
| `perplexity/sonar-pro` (current) | 3.00 | **15.00** | 8,000 |
| `perplexity/sonar` (the sibling) | 1.00 | **1.00** | 114,364 |

**Correction to the blueprint's stated prior, per the provenance rule.** B3 cites
"5/8 at the 1500-token cap [measured: §6.3]". §6.3 does not say that: its rows
are ~4800 tokens → 7/8, ~2900 → 5/8, and ~1400 → **3/8**. The 5/8 figure belongs
to the ~2900-token row, not to a 1500 cap. Which cap actually applies here
depends on how these sectors classify: `SEARCH_MAX_TOKENS` is 1500 for medium
and `SEARCH_MAX_TOKENS_CONSEQUENTIAL` is 4000 for high and critical, and the
grounding sectors — hotel acoustics, water treatment, rail signalling, robot
safety — are consequential work.

**Pre-registered, before either run:**

| | prediction | basis |
|---|---|---|
| `sonar-pro` sectors recovered | **5/8** | [measured: §6.3, ~2900-token row] — these sectors should take the 4000 cap and the model fills what it is given |
| `sonar` sectors recovered | **no prior** | that is the question |
| `sonar-pro` cost | ~$0.32 | [measured: §6.3] |
| `sonar` cost | **~$0.08**, fee-dominated | [derived: §6.3's fee of ~$0.00698/request against $1/M output — at 2900 tokens the fee becomes ~70% of the lookup, the inversion §4.1 projected] |

My own added prediction, stated so it can be wrong: **`sonar` matches within one
sector.** §6.3's finding is that tokens buy figures and the misses at lean
budgets were truncation rather than ignorance; both models face the same cap and
the cheaper one can emit far more before hitting its ceiling. If that holds, the
decision is straightforward. If figures drop materially, the current model
stands and §4.1's fee-inversion arithmetic remains a projection.

### 13.3 Part D — B7 phase 1

#### D1: the three structural facts, read from source

All three hold, and (a) is narrower than stated.

**(a) The feedback channel into the next implement is one string.**
`adapter.py:223-233` builds every subsequent `implement` call from exactly
`red_cause=last.get("red_cause")` plus `self.resolution_directive`. The failure
log records more than that — `adapter.py:261-266` appends `iteration`,
`implement_summary`, `red_cause` **and** `evidence` — so validate's evidence is
captured and then not passed on. It reaches the escalation autopsy, which is
handed the whole log as JSON (`phases.py:851`), but never the next
implementation. **The data exists; the pipe is one field wide.**

**(b) A critical domain review arrives as a fixed sentence.** `adapter.py:245-248`
sets `implement.domain_concerns = concerns` and then, if critical,
`implement.red_cause = "Domain reviewer flagged critical concern"`. The concerns
themselves are on the verdict; what the next iteration receives is that
sentence, identical whatever the reviewer said.

**(c) The loop tests `validate.green` alone.** `engineering-rnd.yaml:102`:
`until: validate.green == true`. So a critical domain review can flip
`implement` red while `validate` stays green and the loop exits satisfied —
**converged on red**. Whether that path is ever taken is an empirical question,
which is what the traces are for.

#### D2: four scenarios, pre-registered before running

In `evals/scenarios/convergence/`, kept out of default runs by the same
non-recursive glob as `wide/` and `materiality/`. These are **observation
instruments, not pass/fail gates** — their assertions are deliberately loose,
because a run that fails to converge is the data, not a defect in the scenario.

| # | scenario | expected iterations | expected `red_cause` shape | predicted outcome |
|---|---|---|---|---|
| 1 | `conv_numeric_consistency` — figures that must agree across sections | 2–3 | names a mismatched figure; **fixable-in-text** | converges |
| 2 | `conv_derived_tolerances` — values that must be recomputed, not copied | 3–5 | names a value as unverified or inconsistent; fixable-in-text, but repeating | stalls — the one-string channel cannot carry which value or why |
| 3 | `conv_crossref_integrity` — terms used before they are defined | 2–3 | names an undefined reference; fixable-in-text | converges |
| 4 | `conv_requires_execution` — validation that honestly needs running something | exhausts (5) | asks for test output or a run result; **structural** | exhausts, then escalates |

My own predictions, labelled and gating nothing: **at least one stall on #2 or
#4**, and **#4 is where a structural cause should appear** — it is the axis §6.8
diagnosed, where the validator asks for evidence a specialist with no filesystem
cannot produce. I do **not** predict a converged-on-red, because it needs a
critical domain review alongside a green validate, and these scenarios are
engineering work where the two should mostly agree.

#### Part B results

One repetition each, identical suite, identical serving (Perplexity is the only
provider for both), `--repeat 1`, 4000-token consequential budget.

| | `sonar-pro` (current) | `sonar` (sibling) |
|---|---|---|
| sectors recovered | **5/8** | **4/8** |
| total cost | $0.4005 | **$0.0664** |
| search-tier cost | $0.3845 over 7 lookups | $0.0500 over 8 lookups |
| **cost per lookup** | **$0.0549** | **$0.0063** — 8.7× cheaper |
| wall clock | 530s | 192s — 2.8× faster |

**Predictions scored.** `sonar-pro` at 5/8: **right, exactly** [measured: §6.3].
My own added prediction, that the sibling matches within one sector: **right** —
4/8.

**The headline is not the score, it is that the misses are complementary rather
than nested.**

| sector | `sonar-pro` | `sonar` |
|---|---|---|
| food_processing, water_treatment | pass | pass |
| architectural_acoustics, broadcast, rail_signalling | pass | **fail** |
| ev_charging, hydraulics | **fail** | pass |
| robot_safety | fail | fail |

Only two sectors pass on both and only one fails on both; the **union is 7/8**.
These are not a better and a worse model, they are two models that miss
different things. A 5-versus-4 gap built from that pattern, on one repetition,
is not a quality ranking — it is close to noise.

One of `sonar-pro`'s three failures is not a search failure at all:
**`hydraulics` fired no lookup** (0 search calls) and failed for want of one,
while `sonar` looked it up and passed. That is the materiality gate declining to
mark a blocking gap, not the model failing to find a figure — so `sonar-pro`'s
"5/8" contains one sector it lost to a gate decision rather than to its own
answer.

**The fee inversion §4.1 projected has happened, measured.** At $0.0063 a lookup
against a per-request fee of roughly half a cent, the fee is now the *majority*
of a lookup's cost rather than 13% of it. Two consequences, both already
anticipated: a generous token budget becomes nearly free, so the owner's
original instinct — "it is priced per call, give it the maximum" — becomes
correct for the first time; and the materiality cap's maximum possible value
shrinks to a fraction of a cent per workflow, which is the interaction
`HANDOVER` B2 predicted.

**Recommendation — a decision input, not a decision (B4; `.env` is the owner's).**
`sonar` is a strong candidate: 8.7× cheaper per lookup and 2.8× faster, one
sector behind on a single repetition, with a complementary miss pattern that
suggests the gap is not a quality ordering. Search is 61–98% of all spend
(§6.3), so the saving is the largest single cost lever in the project. **What
this does not yet support is a confident swap**: one repetition each, and the
repeat convention exists precisely because a single result is an anecdote. The
cheap, obvious next step is three repetitions of both — about $1.40 for
`sonar-pro` and $0.20 for `sonar` — which would settle whether 5-versus-4 is a
ranking or a coin toss.

### 13.4 Part C — B6, observed

**`independent_check` executed inside a complete live workflow.** The full path,
every node, one pass:

```
triage → context → plan → implement → validate → review → review_clean → independent_check
10 calls · 54s · $0.0212
tiers: triage 1, research 2, search 1, architecture 1, engineering 4, independent 1
served: triage=Alibaba, research=Google, search=Perplexity,
        architecture=NextBit, engineering=AtlasCloud/DeepInfra/GMICloud/Venice,
        independent=Morph
```

The `DoubleCheckVerdict`: `ship=True`, `confidence=high`, `critical_issues=[]`,
with one optional recommendation about structuring the entry for
machine-parseability. **All three pre-registered expectations met**: triage set
`unrecallable=true`, every phase shipped on trivial work, and the independent
pass executed and returned a clean verdict. Trace committed at
`docs/traces/b6-independent-check.json`.

#### It took seven attempts, and the probe was what kept failing

Attempts 10 through 16, counting from the nine `HANDOVER` already records. Every
exit was legitimate; none was a harness defect.

| attempt | request framing | outcome |
|---|---|---|
| 1 | the plan's own example — finalize a notice about a migration already run | `unrecallable=false`, review blocked on placeholders |
| 2 | irreversibility moved to the work product | transport `ReadError` |
| 3 | same | **reached `independent_check`**, timed out inside it at 300s |
| 4–6 | same | review blocked 3/3, correctly |
| 7 (rep 1) | simplified to pure prose | review shipped, `unrecallable=false` |
| 7 (rep 2) | same | **all gates passed; the node ran** |

**The plan's example request does not set `unrecallable`, and triage is right
about that.** "Finalize the customer confirmation notice for a one-way migration
that has already been run" puts the irreversibility on the *migration*; the work
requested is a draft, and a draft is recallable. §6.6's axis attaches to what the
work commits you to. Recorded as the calibration finding the plan asked for —
and it is a finding about the plan, not about triage.

**The probe sits in a narrow window, and both walls are real.** Make the request
consequential enough to read irreversible and it acquires genuine engineering
surface: calling the ledger "cryptographically chained" drew three correct
review blocks on unspecified hash construction, append API and canonicalization.
Simplify it to pure prose and review ships but triage stops marking it
unrecallable. The passing run threads that window; at roughly one in three, the
probe is a repetition-and-patience instrument rather than a deterministic one.

**Recorded for whoever runs it next:** the scenario's own `timeout` wins over
`--timeout` (`runner.py`), and 300s is not enough — the independent tier is a
reasoning model and attempt 3 died inside it with every gate already passed. The
scenario now carries 900.

#### Part D results — the loop could not be studied, because half the runs never reached it

Four scenarios, `engineering-rnd`, one repetition, $0.3329 of a $3.00 cap.
Traces committed at `docs/traces/b7-convergence-traces.jsonl`.

| trace | iterations | outcome | classification |
|---|---|---|---|
| `conv_crossref_integrity` | 1 | converged green, then **review blocked** | converged |
| `conv_numeric_consistency` | **3** | converged and shipped | converged |
| `conv_derived_tolerances` | 1 | **died — `ImplementVerdict` missing `green`** | schema failure |
| `conv_requires_execution` | 2 | validate went red on iter 1, then **died — `ImplementVerdict` missing `done`** | schema failure |

**Two of four runs were killed by a schema violation on the implement phase.**
Not a stall, not an oscillation, not exhaustion — the run raised and ended.

#### ❗ The root cause, isolated from source

`implement` is the **only** phase that does not pass its schema into the retry
loop.

| phase | how it validates |
|---|---|
| triage | `chat_json(..., schema=TriageVerdict)` — 3 attempts, each carrying a rejection note |
| plan | `chat_json(..., schema=PlanVerdict)` — same |
| doublecheck | `chat_json(..., schema=DoubleCheckVerdict)` — same |
| **implement** | `chat_json(...)` with **no schema**, then `ImplementVerdict(**lead_data)` at `phases.py:602` |

Because the construction happens *after* the retry loop, a verdict missing one
field is fatal on the first attempt. Every other phase gets three tries and is
told what was wrong; implement gets none. §6.8 records the fix that made schema
retries useful — "the schema retry re-asked the identical prompt with no hint of
what was wrong" — and that fix landed inside `chat_json`, which implement never
opted into.

This reframes B7. The loop was not observed failing to converge because **half
the runs died before the loop could express any behaviour at all**, and the
deaths look like convergence failures from outside. The two runs that did loop
both converged — one in a single iteration, one in three.

#### Predictions scored

| prediction | outcome |
|---|---|
| D6: stalls in ≥1/3 of non-converging runs | **not observable** — both non-converging runs died on schema |
| D6: structural causes in ≥1/4 of red iterations | **1/1** — the only red validate was `conv_requires_execution`, and it was structural: validate wanted execution evidence a specialist cannot produce |
| D6: at least one converged-on-red | **no** — `crossref_integrity` converged *green* and was blocked at review, which is a different thing |
| mine: a stall on #2 or #4 | **wrong** — both died on schema instead |
| mine: #4 is where a structural cause appears | **right** |
| mine: no converged-on-red | **right** |

#### Design proposal, offered for adjudication (Part D invites one; phase 2 rules it)

**Pass `schema=ImplementVerdict` into `chat_json` for the implement phase, and
re-run these four traces before touching anything on the lever menu.** It is the
smallest possible change, it brings implement in line with every other phase,
and the evidence is that it is responsible for 50% of observed run deaths. Every
lever D5 lists — stall detection, widening the feedback channel, aligning
validate's prompt, routing structural causes to escalation — is a change to how
the loop *behaves*, and none can be evaluated while half the runs never reach
the loop. Measure again after the cheap fix; the taxonomy above is not yet a
measurement of convergence.

#### A limitation in the instrument, found by using it

D4 asks whether implement's summary changes substantively between iterations.
**It cannot be answered from this data.** The results log captures the *final*
`ExecutionState`, so a three-iteration run yields one implement verdict, not
three. The per-iteration history exists at run time in `PhaseRunner.failure_log`
(iteration, summary, red_cause, evidence) and is discarded with the runner.
Capturing it is the obvious next increment to Part A, and would have made this
blueprint's own question answerable.

#### The serving, recorded before any prompt is blamed

Per the B4 lesson. The architecture tier drew **six different providers** across
four runs (Alibaba, Baidu, DigitalOcean, Novita, SiliconFlow, StreamLake), and
the configured architecture model is a reasoning model that repeatedly returned
nothing at all — `finish_reason=length, completion_tokens=16384 of 16384`, the
exact §6.4 failure, live. Architecture was also the largest spend line at
$0.2339 of $0.3329. **No prompt should be edited on this evidence until the tier
is pinned**, which is roadmap item 8 and explicitly out of scope here.

### 13.2 Execution record

Executed at `7800dae`→. Suite 553 → **561**, CI green. Spend **≈$1.20**:
Part B $0.4669, Part C $0.5252 across seven attempts, Part D $0.3329, Part A
free.

#### Departures

1. **Part C used the eval harness, not the API.** C2 offered the choice and
   asked for the reason: the harness carries the spend caps *and*, after Part A,
   retains every verdict — which is strictly more evidence than
   `phase_results` would have given, and bounded. The DB route would have needed
   a server, a manual pull, and no cap.
2. **The B6 probe request was rewritten twice.** The plan's own example does not
   set `unrecallable` and triage is right about that; the first rewrite
   overshot into genuine engineering surface. Both are recorded in §13.4 as
   findings rather than smoothed away. The `when` clause was never touched.
3. **The probe scenario's `timeout` was raised 300 → 900.** Not a workaround: at
   300s a run died *inside* `independent_check` with every gate passed.
4. **No B7 mechanism was implemented.** Out of scope by instruction, and the
   traces say the lever menu is not yet the right question — a design proposal
   is attached instead, as Part D invites.
5. **Part D ran concurrently with Part C.** Part A is what made that safe, and
   D3 says so in as many words. One probe attempt died of a transport error
   during the overlap, and the retained verdicts survived it — which is the
   protection working rather than an argument against the overlap.

#### What execution found that the blueprint did not anticipate

- **Part A had the same hole it was written to close.** A transport error
  mid-run produced a record with no verdicts, because `run_scenario` replaced
  the executor's state with a blank one in its exception handlers. Four billed
  calls, all outputs discarded. Fixed with a test; the runs worth diagnosing are
  exactly the ones that broke.
- **`implement` is the only phase that validates outside the retry loop**, and
  it killed half the B7 traces. See the Part D results.
- **The two search models are complementary, not ranked** — union 7/8 against 5
  and 4 individually — so the comparison does not support the ranking its
  headline numbers imply.
- **One `sonar-pro` sector failed for want of a lookup that never fired**, which
  is a materiality-gate decision showing up inside a search-quality measurement.
- **The B6 plan's example request is miscalibrated**, and triage's refusal to
  mark it unrecallable is correct behaviour.
- **The results log cannot answer D4's per-iteration question**, because it
  keeps final state rather than iteration history.

#### Left undone, deliberately

- **B7 remains open** and is now better posed: fix the implement schema path,
  re-measure, *then* consider the lever menu.
- **Only triage is pinned.** Six architecture providers appeared across four
  runs, on a reasoning model that returned nothing at all more than once. That
  is roadmap item 8, and Part D is now the evidence for prioritising it.
- **The search swap is not adopted** — a decision input, one repetition, and
  `.env` is the owner's (G-3).
- **Per-iteration capture** in the results log, which this blueprint's own
  Part D wanted and could not have.

---

## 14. Blueprint 007 — Repair the instrument, pin the second tier, settle the search swap, re-ask B7 (verbatim, as received)

**Status: not executed at the time of recording.** Execution record: §14.2.

Pre-flight at recording, all clear: key live, `triage:Alibaba` present in `.env`,
and A2's two conditions confirmed — `EscalationVerdict` **does** carry
`resolution_directive` (§3.3 is abbreviated), and no verdict sets
`extra="forbid"` (all default to `ignore`), so schema validation tolerates model
extras.

```text
BLUEPRINT 007 — Repair the instrument, pin the second tier, settle the search
swap, and re-ask B7's question with a working instrument.

Origin: 006's Part D — two of four traces died on ImplementVerdict schema
violations before the loop was ever reached, so B7's recorded premise ("the
loop does not converge") is UNTESTED, not falsified. The advisor's source read
found the bypass is not implement alone: escalation has the identical defect,
and review's aggregation crashes on shapes ReviewFinding was built to accept.
Repair the class, then re-run.

Protocol (as 001–006): paste verbatim into docs/handover-review.md as §14
BEFORE executing; append §14.2 after. Provenance rule binding, counts
included. NEW — the premise rule, binding from here: where a part targets a
recorded diagnosis, state its premise as a testable claim and pre-register
the check; the first paid dollar tests the claim where a cheap test exists.
Permission boundary, now codified: instrument repair (crash-proofing phases
against well-formed-enough model output, retry wiring, retention, accounting)
needs no ruling; changes to what a phase MEANS (verdict semantics, loop
behavior, judgment-steering prompt text) do.

Prerequisites: suite green before and after (re-derive the count); CI green
before finishing. Part 0 pre-flight: key live per the 005 adjudication;
the triage pin (triage:Alibaba) present in .env — every paid part below
env-prefixes it alongside any new pins.

PART A — instrument repair (FREE; before any paid part)

A1. implement passes its schema. run_implement currently calls
    lead.run(client, implement_prompt) with no schema and constructs
    ImplementVerdict(**lead_data) afterwards, so a reply missing one field
    is fatal on attempt one — measured twice in 006's traces. Fix: pass
    schema=ImplementVerdict (mirror run_validate's existing call shape).
    Do NOT restructure the post-reply mutations (iteration overwrite, green
    flip on critical domain review, domain_concerns) — they operate on the
    validated dict exactly as now; chat_json returns the parsed dict after
    validating it, so validation-in-retry and construction-after are
    compatible. [measured: 006 §13 — derived_tolerances missing green,
    requires_execution missing done]
A2. escalation passes its schema — the same defect, found by the advisor's
    read. run_escalation_autopsy calls chat_json without schema and
    constructs EscalationVerdict(**data) after, on the longest messiest
    input in the system, at the most expensive moment a run can fail (after
    the loop has burned max_iterations). Pass schema=EscalationVerdict.
    Pre-flight: confirm EscalationVerdict carries resolution_directive (the
    prompt demands it and the recovery loop consumes it; §3.3 may be
    abbreviated) and that no verdict sets extra="forbid" — schema validation
    must tolerate model extras, since escalation's prompt asks for fields
    the verdict may summarize differently.
A3. review aggregation tolerates every shape ReviewFinding accepts. The
    findings loop calls f.get("severity") on raw items, so a specialist
    returning findings as bare strings — the exact shape the lenient
    model_validator(before) exists for — raises AttributeError after every
    review call is paid. Normalize each finding through ReviewFinding (or
    guard with isinstance, mirroring run_domain_review's concerns loop)
    BEFORE the severity check. The leniency must be reachable, and a test
    must pin it: findings as bare strings, as dicts with aliased detail
    keys, as dicts missing severity.
A4. ImplementVerdict.iteration: relax to Field(default=1, ge=1). The phase
    overwrites iteration unconditionally [read: phases.py run_implement],
    so requiring the model to echo it buys nothing and costs a retry when
    echoed wrong. Comment carries that reasoning.
A5. Class audit + guard: for EVERY phase whose workflow node declares a
    schema (triage, plan, implement, validate, review, escalation,
    doublecheck), a capture-double test pins that the phase passes that
    schema into its client call. Phases that deliberately do not
    (feasibility, domain_review — free-form mutators) get a test each
    documenting the exception with the reason. File docstring states the
    pattern in force: a declared schema and an unpinned call site is how
    006's traces died and how §6.8's latch shipped — the class has bitten
    three times; the test set is the insurance against a fourth.
    Also pin A3's shapes here.
A6. Per-iteration retention — 006's own flagged gap: the results log keeps
    final state, so D4's drift question was unanswerable and the history
    died with PhaseRunner.failure_log. Unit records gain an "iterations"
    list: per build-loop iteration, the implement summary (full text is
    fine — the file is local and gitignored), red_cause, green, validate
    green, and that iteration's cost. Source it from the run's
    ExecutionState/trace after completion; find the seam, the requirement
    is the requirement. D4's drift measure (length delta, rough similarity)
    becomes computable next run.

PART B — architecture tier: probe and pin (≈ $0.10–0.40, caps bound)

B1. Pre-flight (free): from §13.1's retained model_used/providers, name what
    actually served and burned on the architecture tier across 006's four
    traces, and record it in §14.1. The pin below targets whatever
    MODEL_ARCHITECTURE is in .env at run time; record that id too. The
    model-swap decision is the owner's (G-3) and stays separate.
B2. Build workflows/plan-probe.yaml — the triage-classify trick applied to
    architecture: triage → context → plan, nothing else. A probe request
    must reliably yield plan.ready=true (three short feasible scenarios
    authored for the probe; read evals/scenario.py and reuse its assertion
    vocabulary rather than inventing one).
B3. Sweep the servings: one invocation per provider that serves the
    architecture model (six served it in 006), env-prefixed
    OPENROUTER_PROVIDER_ORDER="triage:Alibaba,architecture:<Name>", 2
    repetitions, caps --max-spend 0.10 --max-spend-sweep 0.50 each.
    Assertions per unit: PlanVerdict parses, ready=true, criteria pass the
    placeholder validators; the JSONL's retained token data shows burns
    (16k tokens, no text) and stubs where they occur.
B4. Pre-registered expectations [prediction, the advisor's, labelled]:
    at least one serving reproduces the §6.4 signature (burn or stub) if
    the current model is the §6.4 model; servings differ measurably in
    completion_tokens per plan; the spread across servings is smaller than
    triage's §6.1 spread (plans are longer, more constrained outputs).
    Wrong is recorded either way.
B5. Proposal rule (as 005-A4): propose exactly one serving — most units
    passing, then cheapest, with the row that justifies it. Record the
    table in §14.1. The proposal env-prefixes Parts C and D; the owner
    ratifies it into .env alongside the existing pin (one line, G-2 form).

PART C — search swap, settled (≈ $1.40, caps bound)

C1. Three arms, each pinned to the SAME search serving for all models
    (a model comparison, not a §6.1 lottery):
      arm 1 — current MODEL_SEARCH, caps as configured;
      arm 2 — the cheap sibling, caps as configured;
      arm 3 — the cheap sibling, SEARCH_MAX_TOKENS=4000 and
              SEARCH_MAX_TOKENS_CONSEQUENTIAL=4000 via env prefix.
    evals/grounding, triage-only, repeat 3, caps --max-spend 0.40 per
    scenario; sweep caps: arm 1 --max-spend-sweep 1.50, arms 2–3 0.50.
    [derived from §6.3 and 006 §13.1: ~8.7x per-lookup spread]
C2. Pre-register before running: arm 1 mean figures-recovered ≈ 5/8
    [measured: §6.3]; arms 2 and 3 — no prior, that is the question; the
    fee-inversion arithmetic says arm 3's extra tokens cost ~nothing
    [labelled projection — the measurement decides].
C3. Decision rule, pre-registered: swap iff the best sibling arm's mean
    figures ≥ arm 1's mean; if arm 3 beats arm 2 materially, the swap is
    model AND cap together. If the sibling loses, the current model stands
    and §4.1's projection stays a projection. The .env edit is the owner's
    (G-3). Record the complementary-miss structure at 3 reps as the input
    to a possible cascade design (sibling first, expensive fallback on
    missed figures) — a future blueprint, since it changes MAX_LOOKUPS.
C4. Interaction on record [derived: §6.3 fee/token split]: if the swap
    lands, lookups become fee-dominated and the materiality cap's value
    shrinks further — one line in HANDOVER B2's row if it happens.

PART D — B7 re-asked with a working instrument (≈ $0.30–0.60, caps bound)

D1. The premise, pre-registered per the new rule: "the build loop does not
    converge on complex requests" is UNTESTED — 2/4 of its evidence died
    pre-loop. This part tests the premise, not a fix.
D2. Re-run 006's four scenarios verbatim under the Part B pin (env-prefixed
    triage:Alibaba,architecture:<proposed>), engineering-rnd, repeat 1,
    --max-spend 0.75 --max-spend-sweep 3.00.
D3. Per-scenario expectations [prediction, labelled]:
      numeric_consistency — converges ≤3, ships [measured: 006];
      derived_tolerances — now reaches the loop; converges ≤3;
      crossref_integrity — converges ≤2; review MAY block again, and if it
        does that is §5 item 12 measured, not a failed trace;
      requires_execution — validate red persists on structural grounds and
        the honest outcome is exhaustion → escalation → recovery attempts
        fail or requires_human. CONVERGENCE GREEN HERE WOULD BE A FINDING:
        it would mean validate attested to work it could not verify, and
        the per-criterion evidence lines get read line by line.
D4. Deliverables: the taxonomy table v2 with per-iteration drift (A6 makes
    it computable); all four traces committed as measurement records;
    providers_by_function per trace (the B4 lesson in force). B7's phase-2
    ruling — the advisor's, from this data — evaluates the old lever menu
    against the discrimination objective: converge fast on convergent
    work, escalate fast on structural work. NO mechanism is implemented in
    this blueprint.

PART E — records

E1. HANDOVER §4.2: B7 row reframed (premise untested; instrument fault
    isolated and repaired; re-run evidence at §14). §6.8 gains two
    entries: the implement/escalation schema bypass (the retry machinery
    landed in chat_json and the two phases that needed it most never opted
    in — 561 tests green throughout, because doubles return well-formed
    verdicts) and the review-aggregation crash (leniency at the verdict
    layer defeated three lines upstream).
E2. §4.4 convention 15 — the premise rule — plus the permission boundary
    (instrument repair vs behavior change) in the blueprint-protocol
    preamble of the review doc.
E3. Housekeeping: §7's stale "501 tests" comment; test-count and file
    counts refreshed commit-stamped; badge, Testing count and tree comment
    move in the SAME commit as A5's tests (the G2 guard fires).
E4. CHANGELOG [Unreleased]: one prose paragraph — B6 observed; the search
    sibling measured complementary; the instrument repairs; the premise
    rule. No model ids.

COMMIT GUIDANCE: prose, convention 12. Name the lineage: the loop was
never the thing that failed; the phases that could not retry were; the
class guard exists because the same class bit three times; B7's question
was re-asked rather than answered.

OUT OF SCOPE, deliberately: ANY B7 mechanism (stall detection, channel
widening, prompt alignment, escalation routing — phase 2 rules on Part D's
traces); the cascade search design; per-tier pins beyond architecture
(roadmap item 8 continues after); the review→rework loop (item 12 — its
evidence base is being built by D3's crossref expectation); any .env edit
(G-3); prompts that steer judgment.
```

### 14.1 Part B — the architecture tier

#### B1 pre-flight, from 006's retained traces (free)

| trace | servings drawn | architecture calls | architecture cost |
|---|---|---|---|
| `conv_crossref_integrity` | DigitalOcean, Novita, SiliconFlow | 4 | $0.0898 |
| `conv_derived_tolerances` | Baidu | 1 | $0.0113 |
| `conv_numeric_consistency` | Baidu, DigitalOcean, Novita, SiliconFlow, StreamLake | 5 | $0.1176 |
| `conv_requires_execution` | Alibaba | 1 | $0.0152 |

Model at run time: **`deepseek/deepseek-v4-pro`**. Six servings across four
traces; **eleven calls to produce four plans**, so seven were retries or burns;
**$0.2339, which is 70% of all trace spend** at $0.0213 a call. The catalogue
currently lists **16** servings for that model, spanning $1.89–$4.00 per million
output tokens; the six that actually appeared are the ones swept.

The burn signature observed in 006 — `finish_reason=length,
completion_tokens=16384 of 16384` — is at `Specialist.run`'s **default**
`max_tokens=16384`, not a provider ceiling: every serving but two advertises a
maximum above 262,000 tokens. The model spends the default budget reasoning and
emits nothing.

#### Pre-registered before the sweep

**The advisor's [predictions], labelled:**

1. *At least one serving reproduces the §6.4 signature if the current model is
   the §6.4 model.* The antecedent is **false** — §6.4's stub-on-planning model
   was the one since reassigned to premium, and the current architecture model
   is a different id. The signature was nevertheless already reproduced by this
   model in 006, so the prediction's conclusion holds for a reason its premise
   did not anticipate. Recorded rather than scored.
2. *Servings differ measurably in completion tokens per plan.*
3. *The spread across servings is smaller than triage's §6.1 spread.*

**Mine, labelled and falsifiable:** *the burn is model-intrinsic, not
serving-specific* — it is a reasoning model spending a fixed default budget
before emitting, so it should appear across most or all servings at a similar
rate, unlike triage's §6.1 quality spread which was strongly serving-dependent.
**If that holds, pinning this tier does not fix it and the real lever is a model
swap or a larger plan budget** — which is the owner's call under G-3, not this
blueprint's.

**Assertions.** The vocabulary has no `plan_ready`, and inventing one is out of
scope, so each unit asserts `status: completed`, `path_includes: [plan]` and
`max_calls: 6`. Readiness, criteria quality and token burn are read from the
**retained verdicts** — which is what Part A's retention is for. `PlanVerdict`'s
own validators already reject a stub inside the retry loop: a plan is required
when ready, blockers when not, and `"..."`/`"TBD"` criteria are refused.
