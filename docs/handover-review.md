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
| D1 | `CONTRIBUTING.md` | **misdirects** | Tells contributors to "wire new phases into `autornd/engine/workflow.py`" — the **legacy** sequencer kept only as the graph's equivalence reference. Correct path: add a `_phase_<name>` method to `graph/adapter.py` and a node to a `workflows/*.yaml`. Also says to "add new `SpecialistRole` entries to `autornd/models/verdicts.py`" — roles are an **open vocabulary** now; you declare them under `roles:` in a profile and an undeclared one resolves to a generalist. A contributor following this file today builds on the deprecated path. |
| D2 | `CHANGELOG.md` | **frozen** | Last entry `[0.1.0] — 2026-09-12`: "5-phase sequencer", "Full test suite (85 tests)", and a model nickname ("K3 escalation autopsy pattern"). Sixteen commits of substantial change are unrecorded — the workflow graph, the eval harness, outward research, open domain/role vocabularies, client-side accounting, provider pinning, the review gate, and the `unrecallable` axis. |
| D3 | `README.md` | **stale + one model name** | Says **"339 tests"** in two places (`:728`, `:771`); actual count is **501**. Line `:103` names a specific model ("Sonar-pro bills $15.00 per million…"), which breaks the zero-model-names rule. The measurement should stay; the vendor name should become "a sonar-class search model" or similar. |
| D4 | `CLAUDE.md` | ✅ **done** | Rewritten — §3.1. |
| D5 | `HANDOVER.md` | ✅ **done** | §1.1 and §1.2 corrections applied. |

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

| missing | status |
|---|---|
| **Blueprint 001** — full text | absent. §3.2 reworks its *CI step* from first principles (the substance is unambiguous), but the surrounding document is unknown. |
| **Blueprint 002** — full text | absent entirely. |
| The owner's **verification response** from the prior turn | absent. The executing session's prior turn was a model-selection question. |
| **"This turn's audit"** | absent as a supplied artifact. §1 and §2 are this session's own verification, done from the repo. |
| The **B6 plan** ("builds a minimal workflow instead") | absent. Noted as the intended approach; the plan text is unknown. |

Everything in §1–§4 is independently verified against the repo or measured live,
and is safe to rely on. Paste the five items above and they can be appended
verbatim under a new §6.

---

## 6. Session handling

**Archive, do not resume.** The prior transcript is a read-only reference for
"what did we already try" — most usefully the four successive rewrites of the
triage risk guide, each of which failed for a reason now recorded in
`HANDOVER.md` §6.6 and recoverable in full from `git log -p autornd/engine/phases.py`.

Session history lives outside the repository, so nothing in this pass changes
it; the recommendation is unaffected either way.
