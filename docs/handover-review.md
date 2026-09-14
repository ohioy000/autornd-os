# Handover Review — corrections, drift punch list, and chat-only findings

Companion to [`HANDOVER.md`](../HANDOVER.md). That document is the project state;
this one records **what in it was wrong**, **which docs still disagree with the
code**, and **what existed only in a chat transcript** and would otherwise be
lost.

Written 2026-09-13, at `641da5a`+. The intent is that a fresh session executes
from the repo rather than from pasted conversation.

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

**Status: not executed at the time of recording.** Execution record: §11.2.

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
