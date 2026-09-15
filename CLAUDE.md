# AutoRnD-OS

A multi-model agentic harness for team work that aims to be frugal and accurate,
starting with engineering R&D. You give it an objective in prose; it classifies
the work, assembles grounding, plans, implements, validates in a loop, reviews
with a risk-scaled team, and either produces a written deliverable or escalates
with a diagnosis. Tiers are named by *job* — triage, engineering, architecture,
escalation, research, search — never by vendor: the harness is what ships, and
the model choice is the operator's. **[`HANDOVER.md`](HANDOVER.md) is the
authoritative state of record; its §6 (measured facts) is load-bearing — nearly
every constant here came from a live run recorded there.**

## ⚠️ Meter epoch

Cost accounting was broken before commit `b4cd89f`: research, context and rerank
calls bypassed it entirely. **Any cost figure predating `b4cd89f` is understated
by 2.6×–295×. Never cite one.** Re-measure instead.

## Current shape

- `graph/` is the engine. Workflows are **YAML data** in `workflows/`, not a
  sequence compiled into code.
- `evals/` is in-package (`autornd/evals/`); scenarios and suites live in
  `evals/` at the root.
- 26 test files.
- `engine/workflow.py` is the API entry point: it loads the graph, runs it, and
  persists phases. The hardcoded sequencer it used to carry as the graph's
  equivalence reference is gone — the graph outgrew what a linear engine can
  represent.

## Non-negotiables

Condensed from `HANDOVER.md` §4.4, which holds the full list.

1. **Measurement comments are sacred.** Read the comment beside a constant
   before touching it — it usually names the live run that set it, and often a
   previous attempt that failed.
2. **Free checks before paid calls.** Always.
3. **Typed verdicts; gates test booleans.** Never parse English for control flow.
4. **No `eval` in workflow files.** Conditions are one deliberate grammar.
5. **Enums are default vocabularies, not limits.** `Domain` and `SpecialistRole`
   are starting sets; profiles declare their own.
6. **No hardcoded model names or prices.** Rates come from the provider
   catalogue. Selection is anonymous, the record is not: no model id in code,
   config defaults, profiles, workflows or user-facing docs — but `HANDOVER.md`
   §6 and `docs/handover-review.md` are the lab notebook and name what they
   measured.
7. **Test doubles must bill** (`client._account`). A free double hid a real
   accounting bug.

## Working rules

```bash
.venv/bin/python3 -m pytest tests/ -q     # ~9 s, free — run before AND after
```

- Commit messages are **prose that names the measurement**, not bullet lists.
- **Private corpora never enter this repo.** `profiles/milkhouse.yaml` stays
  untracked; see `.gitignore`.
- Pass `--max-spend` on anything touching the search tier — it is by a wide
  margin the most expensive one. It caps **one scenario-run**, not the
  invocation; `--max-spend-sweep` does that and is on by default at $1.00
  (`none` disables). With both set the sweep cap is exact.

Corrections, doc drift and open blueprints:
[`docs/handover-review.md`](docs/handover-review.md).
