# Evals — the paid measurement path

Load when running or changing anything under `evals/` or `autornd/evals/`.
Unit tests prove the harness does what it says. **Evals measure whether the models
do**, and they cost real money.

## Running one

```bash
python -m autornd.evals.cli --scenarios evals/scenarios --workflow triage-classify \
  --repeat 3 --max-spend 0.10
```

Scenarios are YAML in `evals/scenarios/` (triage, wide, convergence,
generalization, materiality, planprobe, probe). `evals/grounding/` grades factual
recall against published figures. Assertions are free and make no model call
(`autornd/evals/assertions.py`).

## Four conventions that matter more than the mechanics

1. **Write the expectation before the run, and commit it first.** The commit is
   the evidence that the prediction preceded the result. See
   `docs/preregistration-*.md` for the shape. **A wrong prediction is reported as
   wrong, never quietly adjusted to match.**
2. **Always pass `--max-spend`.** It bounds **one scenario-run** — a single
   repetition, not the whole invocation. The aggregate ceiling is
   `--max-spend-sweep`, **on by default at $1.00**; pass `none` to disable.
   Anything touching the search tier is by a wide margin the most expensive thing here.
3. **Repeat.** Models are stochastic; the same triage request has passed on one run
   and failed on the next. A single result is an anecdote. Buying extra repetitions
   beyond a registration is a **logged departure carrying its cost and what it
   de-risked** — the exemplar: $0.09 turned a coin-flip pin into a measured one.
4. **Test doubles must bill** — `client._account(...)`.

## The fit rule, and the arithmetic trap

With both caps set the sweep cap is **exact**, because a unit that might not fit is
never started. That conservatism is the fit rule on `SweepBudget`, and it is not a
bug — but it means **`--max-spend 0.50 --max-spend-sweep 0.50 --repeat 2` is
arithmetically impossible**: it needs $1.00 of a $0.50 sweep, so exactly one unit
could ever start. A free pre-spend check now warns before the first call. Check
your registration's arithmetic before you commit it.

A skipped unit carries a **typed `ScenarioRun.skipped` flag**. It was once decided
by substring-matching the error message, and correcting the message silently turned
skipped units into units that had run — which would have inflated the denominator
of every pass rate in any sweep that hit its cap.

## The trace is the deliverable

Every unit is appended to `evals/results/*.jsonl` as it finishes, flushed
immediately, with a header naming models, servings and caps
(`ResultsLog`). Two things follow: an interrupted sweep keeps what it bought, and a
failing sector can be diagnosed — and priced against its serving — without paying
to reproduce it.

The JSONL record carries, and each entry exists because something was once
unanswerable:

| field | what it answers |
|---|---|
| `rejections_by_tier` / `rejections_by_provider` | how often a reply is refused, and **by which serving** |
| `normalised_by_kind` | which coercion fired: green derived, green overruled, evidence folded |
| `seconds_by_phase` | where an expired run's clock went, without buying it again |
| `iterations[]` | per build-loop round: both verdicts, red causes, evidence, concerns, **which judge dissented**, spend delta |
| `tokens_by_tier` | cost alone cannot separate "dearer" from "handed more to read" |
| `refused_lookups` | a zero score with refusals is a poisoned reading, not a bad model |
| `providers_by_function` | who served each tier |

**Protect the trace from git.** A `git stash -u` during a live run took the
directory entry of an untracked results file under the *tracked* `docs/traces/`
while the writer held the inode, and every completed unit record went to a deleted
file — $0.1547 spent, unrecoverable. `evals/results/` is git-ignored and was never
exposed; a mirror outside the working tree is now written alongside the primary,
chosen by hazard. It does **not** protect against `git stash -a`, deletion of the
state directory, filesystem loss, or a `kill -9` between records.

Committed traces cited anywhere live in `docs/traces/`.

## A serving sweep measures three axes, and latency is the least

**Compliance first** — a serving whose replies the schema refuses is disqualified
regardless of speed. Then **iterations to termination**. Then speed. **Never at
n=1.** `crossref_integrity` produced three different outcomes in three runs and is
the standing reason to distrust a single observation.

And: **a repetition of a plan-dependent contrast is a second sample, never a
confirmation** — the plan regenerates between runs, so the second run measures a
different contract.

## Isolate the store

Use `_isolated_store()` (`autornd/evals/runner.py:315`). The eval suite once read a
developer's local Chroma directory and every gap came back pre-answered.
