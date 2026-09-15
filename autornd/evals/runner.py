"""Runs scenarios against a workflow and reports what held.

Bounded on purpose. An eval sweep that can run away is one you stop running,
and a suite you do not run is worth nothing — so every run carries a call
ceiling and a wall-clock deadline, and exceeding either is a recorded failure
rather than a hang.

The same runner drives mocked and live clients. Mocked is free and instant and
catches regressions in shape; live costs money and measures quality. Both score
against the same expectations.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from autornd.evals.assertions import AssertionResult, RunOutcome, score
from autornd.evals.scenario import Scenario
from autornd.graph.adapter import PhaseRunner
from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import WorkflowSpec
from autornd.routing.openrouter import BudgetExceeded, OpenRouterClient

logger = logging.getLogger(__name__)

__all__ = [
    "EvalReport",
    "ResultsLog",
    "SweepBudget",
    "RepeatedReport",
    "RepeatedRun",
    "ScenarioRun",
    "run_repeated",
    "run_scenario",
    "run_suite",
]

DEFAULT_CALL_CEILING = 40
DEFAULT_TIMEOUT_SECONDS = 600.0


# 0.1 + 0.1 + 0.1 is 0.30000000000000004, which is larger than a 0.30 cap. A
# budget that refuses the last unit it was sized for is worse than useless, so
# every comparison carries a tolerance far below a cent.
_BUDGET_EPSILON = 1e-9


@dataclass
class SweepBudget:
    """An aggregate ceiling across a whole invocation.

    `--max-spend` bounds one scenario-run, and every repetition builds a fresh
    client carrying that ceiling — so it says nothing about what an invocation
    costs. Thirty-six scenarios at three repetitions with `--max-spend 0.25` is
    a $27 ceiling. This is the same defect as B10, which was a budget counting
    nodes when the thing worth counting was calls: a limit on the wrong unit
    reads like a limit.

    Two enforcement modes, both decided before any paid call is made:

    **Fit rule** — when a per-unit cap is also set, a unit starts only if it
    could not possibly overrun the sweep cap. That makes the sweep cap a hard
    guarantee and means no unit is ever killed mid-flight by it. It is
    deliberately conservative: a unit is skipped even when it would have cost
    far less than its cap. The guarantee is worth the occasional early stop.

    **Backstop** — with no per-unit cap there is nothing to reason about in
    advance, so the unit starts with its client ceiling set to whatever is left
    and the existing BudgetExceeded machinery stops it at the crossing.

    Overshoot is then bounded by the calls already in flight — NOT by one call,
    which is what this was designed assuming. Feasibility, domain review and
    final review each fan out with asyncio.gather, so a whole roster can be
    billed between the crossing and the raise; measured at two calls with a
    two-specialist roster. The bound is the widest fan-out. That is the price
    of the parallelism, and it is why the fit rule is the stronger guarantee:
    with a per-unit cap set there is no overshoot at all.
    """

    cap: float
    spent: float = 0.0
    # For the summary line: how much of the sweep actually ran.
    started: int = 0
    skipped: int = 0

    @property
    def remaining(self) -> float:
        return max(0.0, self.cap - self.spent)

    def can_start(self, per_unit_cap: float | None) -> bool:
        if per_unit_cap is not None:
            return self.spent + per_unit_cap <= self.cap + _BUDGET_EPSILON
        return self.spent < self.cap - _BUDGET_EPSILON

    def unit_ceiling(self, per_unit_cap: float | None) -> float:
        """Compose the two ceilings rather than duplicating either.

        Under the fit rule the remaining budget is never the binding one, so
        this returns the per-unit cap; under the backstop there is no per-unit
        cap and it returns the remainder. One expression covers both.
        """
        if per_unit_cap is None:
            return self.remaining
        return min(per_unit_cap, self.remaining)

    def record(self, cost: float) -> None:
        """Called after every unit that started, including failed and aborted
        ones — an abort still cost whatever it spent before it stopped."""
        self.spent += cost
        self.started += 1

    def skip(self) -> str:
        """Mark one unit as never started, and say so in its own words."""
        self.skipped += 1
        return (f"skipped: sweep budget exhausted "
                f"(${self.spent:.4f} of ${self.cap:.2f} spent)")


class ResultsLog:
    """Append-only JSONL, one line per unit, flushed as each unit finishes.

    A sweep used to hold every result in memory and render once at the end, so
    killing it threw away everything it had paid for — measured at about $0.018
    on a single interrupted run, and the reason a whole invocation had to be
    repeated. A line appended and flushed is durable the moment it is written,
    which needs no signal handling and survives a kill -9 just as well as a
    clean exit.

    The header line carries the run's configuration, so a results file answers
    "which model, served by whom, under what caps" without anyone re-running
    anything. That is the B4 lesson made durable: a sector that fails is priced
    against its serving before a prompt is blamed.
    """

    def __init__(self, path: str | Path, config: dict[str, Any] | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")
        self._write({"record": "header",
                     "written_at": datetime.now(timezone.utc).isoformat(),
                     **(config or {})})

    def _write(self, payload: dict[str, Any]) -> None:
        json.dump(payload, self._handle, ensure_ascii=False, default=str)
        self._handle.write("\n")
        # Durability is the entire point; buffering it away would restore the
        # bug this class exists to fix.
        self._handle.flush()

    def record(self, run: "ScenarioRun", workflow: str, repetition: int) -> None:
        self._write({
            "record": "unit",
            "scenario": run.scenario.id,
            "workflow": workflow,
            "repetition": repetition,
            "passed": run.passed,
            "skipped": run.skipped,
            "status": run.status,
            "error": run.error,
            "calls": run.calls,
            "seconds": round(run.seconds, 3),
            "cost": run.cost,
            "cost_by_tier": run.cost_by_tier,
            "calls_by_tier": run.calls_by_tier,
            "providers_by_function": run.providers_by_tier,
            "refused_lookups": run.refused_lookups,
            "normalised_verdicts": run.normalised_verdicts,
            "tokens_by_tier": run.tokens_by_tier,
            "rejections_by_tier": run.rejections_by_tier,
            "rejections_by_provider": run.rejections_by_provider,
            "seconds_by_phase": run.seconds_by_phase,
            "assertions": [
                {"name": r.name, "passed": r.passed,
                 "wanted": r.wanted, "got": r.got, "detail": r.detail}
                for r in run.results
            ],
            "path": run.path,
            "iterations": run.iterations,
            "verdicts": run.verdicts,
        })

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()

    def __enter__(self) -> "ResultsLog":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def default_results_path(suite: str) -> Path:
    """evals/results/<utc-timestamp>-<suite>.jsonl"""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = Path(suite).name.replace(".yaml", "") or "suite"
    return Path("evals/results") / f"{stamp}-{slug}.jsonl"


@contextlib.contextmanager
def _isolated_store():
    """Give each scenario its own knowledge store.

    Research ingests what it looks up, which is right for a real workflow and
    wrong for an experiment: in a twelve-scenario sweep the first scenario's
    findings grounded all eleven after it, so only one was a genuine
    empty-store test. Product behaviour is unchanged; the harness just stops
    letting scenarios contaminate each other.
    """
    from autornd.config import settings

    # The store builds a fresh client from settings.chromadb_path on every call,
    # so redirecting the path is all the isolation needed.
    original = settings.chromadb_path
    with tempfile.TemporaryDirectory(prefix="autornd-eval-") as tmp:
        settings.chromadb_path = tmp
        try:
            yield tmp
        finally:
            settings.chromadb_path = original


def _provider_line(runs) -> str:
    """Which upstream served each tier across the whole suite.

    A model id is not a system. The same id served by a different provider gave
    70-token replies at a thirtieth of the price and classified four sectors
    differently between two runs of this suite — so the answer to "did my change
    break this?" often lives on this line.
    """
    seen: dict[str, set[str]] = {}
    for run in runs:
        for tier, providers in (run.providers_by_tier or {}).items():
            seen.setdefault(tier, set()).update(providers)
    if not seen:
        return ""
    return "served by: " + ", ".join(
        f"{tier} via {'/'.join(sorted(p))}" for tier, p in sorted(seen.items()))


def _refusal_line(runs) -> str:
    """Say it loudly when lookups were refused.

    A unit whose lookups were all refused scores zero and reads exactly like a
    model that found nothing. In 007 that difference was recoverable only by
    going and counting lookups per unit by hand, after the scores had already
    been written down.
    """
    refused = sum(getattr(r, "refused_lookups", 0) or 0 for r in runs)
    if not refused:
        return ""
    affected = sum(1 for r in runs if getattr(r, "refused_lookups", 0))
    return (f"!! {refused} lookup(s) refused across {affected} unit(s) — "
            f"their scores are not a measurement of the model")


def _tier_line(by_tier: dict[str, float]) -> str:
    """Where the money went, biggest first.

    A single total hides the thing worth knowing: one search tier can outweigh
    every other call in a workflow combined, and until now it did not appear in
    any total at all.
    """
    if not by_tier:
        return "spend by tier: nothing billed"
    ordered = sorted(by_tier.items(), key=lambda kv: -kv[1])
    return "spend by tier: " + ", ".join(f"{t} ${c:.4f}" for t, c in ordered)


# Kept as an alias: the budget is now enforced by the client, so research
# lookups and reranking count against it too. They never did before — the
# ceiling only saw nodes that passed through run_ai.
CallCeilingExceeded = BudgetExceeded


class BoundedRunner(PhaseRunner):
    """A PhaseRunner whose client refuses to exceed its budget.

    MAX_ITERATIONS bounds loops but not total spend: a workflow with a wide
    fan-out can make many calls per iteration, and research lookups are made
    outside the node machinery entirely. Setting the ceiling on the client
    bounds every path, including the ones that used to be free.
    """

    def __init__(self, client: OpenRouterClient, ceiling: int,
                 spend_ceiling: float | None = None) -> None:
        super().__init__(client)
        self.ceiling = ceiling
        client.reset_accounting()
        client.call_ceiling = ceiling
        client.spend_ceiling = spend_ceiling

    @property
    def calls(self) -> int:
        return self.client.calls


@dataclass
class ScenarioRun:
    scenario: Scenario
    results: list[AssertionResult]
    calls: int
    seconds: float
    cost: float = 0.0
    error: str | None = None
    path: list[str] = field(default_factory=list)
    # Where the money went. A total hides the thing worth seeing: one search
    # tier can outweigh every other call in a workflow.
    cost_by_tier: dict[str, float] = field(default_factory=dict)
    calls_by_tier: dict[str, int] = field(default_factory=dict)
    # Who served each tier. Recorded because a suite that drops six sectors
    # between runs looks like a code regression until you can see that a model
    # id changed hands.
    providers_by_tier: dict[str, list[str]] = field(default_factory=dict)
    # Every node's typed verdict, as plain dicts. The harness used to throw
    # these away the moment it had scored them, which made diagnosing a past
    # sweep impossible: Blueprint 005 set out to read eighteen triage verdicts
    # it had already paid for and found nothing left to read. Scoring tells you
    # *that* a sector failed; only the verdict says why, and re-buying it costs
    # money and cannot reproduce the run that actually failed.
    verdicts: dict[str, Any] = field(default_factory=dict)
    # The terminal status of the run — completed, blocked, escalated. Scored by
    # the `status` assertion already, but a result file needs it in its own
    # right: "blocked" and "failed an assertion" are different outcomes.
    status: str = ""
    # One entry per build-loop iteration; see PhaseRunner.iterations.
    iterations: list[dict[str, Any]] = field(default_factory=list)
    # Lookups the provider refused during this unit. A unit that scored zero
    # with refusals is a poisoned reading, not a bad model.
    refused_lookups: int = 0
    # Where the wall clock went, phase -> seconds, summed across iterations. A
    # run that expires should not need buying again to say what was slow.
    seconds_by_phase: dict[str, float] = field(default_factory=dict)
    # How many verdicts had their `green` resolved from `red_cause`. This is the
    # malformed-verdict rate, and it is recorded rather than swallowed: a fix
    # that hides its own trigger stops anyone noticing when it is no longer
    # needed — or when it starts firing far more than it used to.
    normalised_verdicts: int = 0
    # Prompt and completion tokens per tier. Cost alone cannot separate "this
    # tier got dearer" from "this tier was handed more to read".
    tokens_by_tier: dict[str, dict[str, int]] = field(default_factory=dict)
    # Replies the schema refused, per tier, retries included. Read beside
    # `normalised_verdicts`: a normalisation is a reply the truth table
    # repaired, a rejection is one it could not, and the pair is the whole
    # malformed rate. Both are needed because the resolution converts the
    # second into the first — without the counts, that conversion is invisible.
    rejections_by_tier: dict[str, int] = field(default_factory=dict)
    # The same refusals attributed to the serving that produced them. A tier is
    # not a system: the engineering tier is served by a dozen providers inside a
    # single run, and "the engineering tier refused" names no one.
    rejections_by_provider: dict[str, int] = field(default_factory=dict)

    # A unit the sweep budget never started is skipped in exactly the sense a
    # not-applicable one is: it produced no evidence, so it must not dilute a
    # pass rate or count towards the applicable total.
    _SKIP_REASONS = ("not applicable", "sweep budget exhausted")

    @property
    def skipped(self) -> bool:
        return (not self.results and bool(self.error)
                and any(r in self.error for r in self._SKIP_REASONS))

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(r.passed for r in self.results)

    @property
    def failures(self) -> list[AssertionResult]:
        return [r for r in self.results if not r.passed]


@dataclass
class EvalReport:
    runs: list[ScenarioRun]
    workflow: str

    @property
    def passed(self) -> int:
        return sum(1 for r in self.runs if r.passed)

    @property
    def total(self) -> int:
        return len(self.runs)

    @property
    def calls(self) -> int:
        return sum(r.calls for r in self.runs)

    @property
    def cost(self) -> float:
        return sum(r.cost for r in self.runs)

    @property
    def seconds(self) -> float:
        return sum(r.seconds for r in self.runs)

    @property
    def cost_by_tier(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for run in self.runs:
            for tier, amount in run.cost_by_tier.items():
                totals[tier] = totals.get(tier, 0.0) + amount
        return totals

    def render(self) -> str:
        lines = [
            f"workflow: {self.workflow}",
            f"{'scenario':<28}{'result':<8}{'calls':>6}{'secs':>8}   failures",
            "-" * 92,
        ]
        for run in self.runs:
            mark = "skip" if run.skipped else ("pass" if run.passed else "FAIL")
            detail = ", ".join(
                f"{f.name}(wanted {f.wanted}, got {f.got})" for f in run.failures
            ) or (run.error or "")
            lines.append(
                f"{run.scenario.id:<28}{mark:<8}{run.calls:>6}{run.seconds:>8.1f}   "
                f"{detail[:44]}"
            )
        lines.append("-" * 92)
        applicable = self.total - sum(1 for r in self.runs if r.skipped)
        summary = f"{self.passed}/{applicable} applicable scenarios passed"
        if applicable != self.total:
            summary += f" ({self.total - applicable} not applicable)"
        summary += f"  ·  {self.calls} model calls  ·  {self.seconds:.1f}s"
        if self.cost:
            summary += f"  ·  ${self.cost:.4f}"
        lines.append(summary)
        lines.append(_tier_line(self.cost_by_tier))
        refusal = _refusal_line(self.runs)
        if refusal:
            lines.append(refusal)
        provider_line = _provider_line(self.runs)
        if provider_line:
            lines.append(provider_line)
        return "\n".join(lines)


def _phase_seconds(state) -> dict[str, float]:
    """Wall clock per node, summed over every iteration it ran in."""
    totals: dict[str, float] = {}
    for step in getattr(state, "trace", []) or []:
        if getattr(step, "skipped", False):
            continue
        totals[step.node_id] = round(
            totals.get(step.node_id, 0.0) + (getattr(step, "seconds", 0.0) or 0.0), 3)
    return dict(sorted(totals.items(), key=lambda kv: -kv[1]))


def _partial_state(executor: GraphExecutor, request: str):
    """Whatever the run completed before it broke, rather than a blank slate.

    A run that failed is the one you most want the verdicts from. Replacing its
    state with an empty one threw away every node that had already succeeded —
    and been paid for.
    """
    from autornd.graph.executor import ExecutionState

    return getattr(executor, "state", None) or ExecutionState(request=request)


async def run_scenario(
    scenario: Scenario,
    spec: WorkflowSpec,
    client_factory: Callable[[], OpenRouterClient],
    settings_lookup: dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_spend: float | None = None,
    budget: SweepBudget | None = None,
) -> ScenarioRun:
    unmet = scenario.unmet_requirements(set(spec.ids))
    if unmet:
        detail = "; ".join(
            f"'{key}' needs a '{node}' node" for key, node in unmet.items()
        )
        return ScenarioRun(
            scenario=scenario, results=[], calls=0, seconds=0.0,
            error=f"not applicable to workflow '{spec.name}': {detail}",
        )

    # Decided before a client is built, so an exhausted sweep costs nothing at
    # all — not even the first call of a unit that cannot finish.
    if budget is not None and not budget.can_start(max_spend):
        return ScenarioRun(
            scenario=scenario, results=[], calls=0, seconds=0.0,
            error=budget.skip(),
        )

    from autornd.knowledge import research as _research
    from autornd.models import verdicts as _verdicts
    _research.reset_refused_lookups()
    _verdicts.reset_normalisations()

    ceiling = scenario.max_calls or DEFAULT_CALL_CEILING
    spend_ceiling = budget.unit_ceiling(max_spend) if budget else max_spend
    # One call of headroom, so exceeding the expectation is reported by the
    # max_calls assertion rather than as an opaque abort.
    runner = BoundedRunner(client_factory(), ceiling + 1, spend_ceiling=spend_ceiling)
    executor = GraphExecutor(spec, runner, settings_lookup)

    # A scenario's own timeout wins: it knows what it is measuring.
    deadline = scenario.timeout or timeout

    started = time.perf_counter()
    error: str | None = None
    try:
        with _isolated_store():
            state = await asyncio.wait_for(executor.run(scenario.request), deadline)
    except asyncio.TimeoutError:
        state = _partial_state(executor, scenario.request)
        error = f"timed out after {deadline:.0f}s"
    except CallCeilingExceeded as exc:
        state = _partial_state(executor, scenario.request)
        error = str(exc)
    except Exception as exc:  # a broken run is a result, not a crash
        state = _partial_state(executor, scenario.request)
        error = f"{type(exc).__name__}: {exc}"
    seconds = time.perf_counter() - started

    # Every unit that started is billed to the sweep, including one that failed
    # or was aborted — it spent whatever it spent before it stopped.
    if budget is not None:
        budget.record(runner.total_cost)

    # Verdicts are Pydantic models or plain values; normalise to something
    # JSON can hold without importing the schemas back to read a result file.
    verdicts: dict[str, Any] = {}
    for node_id, value in (state.outputs or {}).items():
        dump = getattr(value, "model_dump", None)
        try:
            verdicts[node_id] = dump(mode="json") if dump else value
        except Exception:      # a verdict that will not serialise is not a
            verdicts[node_id] = repr(value)   # reason to lose the whole run

    outcome = RunOutcome(state=state, calls=runner.calls,
                         cost=runner.total_cost, error=error,
                         context=getattr(runner, "context", "") or "")
    return ScenarioRun(
        scenario=scenario,
        results=score(scenario, outcome),
        calls=runner.calls,
        seconds=seconds,
        cost=runner.total_cost,
        error=error,
        path=list(state.path),
        cost_by_tier=dict(runner.client.spend_by_function),
        calls_by_tier=dict(runner.client.calls_by_function),
        providers_by_tier={k: sorted(v) for k, v
                           in runner.client.providers_by_function.items()},
        verdicts=verdicts,
        status=str(getattr(state, "status", "") or ""),
        iterations=list(getattr(runner, "iterations", []) or []),
        refused_lookups=_research.refused_lookups(),
        normalised_verdicts=_verdicts.normalisations(),
        tokens_by_tier={k: dict(v) for k, v
                        in runner.client.tokens_by_function.items()},
        rejections_by_tier=dict(runner.client.rejections_by_function),
        rejections_by_provider=dict(runner.client.rejections_by_provider),
        seconds_by_phase=_phase_seconds(state),
    )


@dataclass
class RepeatedRun:
    """The same scenario, several times.

    Models are stochastic: the same request produced a passing triage on one
    run and a failing one on the next. A single result is an anecdote, so the
    unit of measurement is a pass rate and the flaky assertions are named.
    """

    scenario: Scenario
    runs: list[ScenarioRun]

    @property
    def skipped(self) -> bool:
        return all(r.skipped for r in self.runs)

    @property
    def passes(self) -> int:
        return sum(1 for r in self.runs if r.passed)

    @property
    def rate(self) -> float:
        applicable = [r for r in self.runs if not r.skipped]
        return self.passes / len(applicable) if applicable else 0.0

    @property
    def passed(self) -> bool:
        """Only a clean sweep counts. A flaky assertion is a finding, not a pass."""
        return not self.skipped and self.passes == len(self.runs)

    @property
    def flaky(self) -> dict[str, int]:
        """How often each assertion failed across the repetitions."""
        counts: dict[str, int] = {}
        for run in self.runs:
            for failure in run.failures:
                counts[failure.name] = counts.get(failure.name, 0) + 1
        return counts

    @property
    def calls(self) -> int:
        return sum(r.calls for r in self.runs)

    @property
    def cost(self) -> float:
        return sum(r.cost for r in self.runs)

    @property
    def seconds(self) -> float:
        return sum(r.seconds for r in self.runs)


@dataclass
class RepeatedReport:
    results: list[RepeatedRun]
    workflow: str
    repeat: int

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def applicable(self) -> int:
        return sum(1 for r in self.results if not r.skipped)

    @property
    def calls(self) -> int:
        return sum(r.calls for r in self.results)

    @property
    def cost(self) -> float:
        return sum(r.cost for r in self.results)

    @property
    def seconds(self) -> float:
        return sum(r.seconds for r in self.results)

    @property
    def cost_by_tier(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for result in self.results:
            for run in result.runs:
                for tier, amount in run.cost_by_tier.items():
                    totals[tier] = totals.get(tier, 0.0) + amount
        return totals

    def render(self) -> str:
        lines = [
            f"workflow: {self.workflow}   repetitions: {self.repeat}",
            f"{'scenario':<24}{'rate':>8}{'calls':>7}{'secs':>8}   flaky assertions",
            "-" * 92,
        ]
        for result in self.results:
            if result.skipped:
                lines.append(f"{result.scenario.id:<24}{'skip':>8}{'':>7}{'':>8}   "
                             f"{(result.runs[0].error or '')[:40]}")
                continue
            rate = f"{result.passes}/{len(result.runs)}"
            flaky = ", ".join(
                f"{name} {count}/{len(result.runs)}"
                for name, count in sorted(result.flaky.items(), key=lambda i: -i[1])
            )
            # The name of a failed assertion is rarely the finding; the detail
            # is. `figures_present` exists to say which figure is missing, and
            # showing only its name sends the reader back to re-run it.
            details = [f.detail for run in result.runs for f in run.failures
                       if f.detail]
            if details:
                flaky = f"{flaky} — {details[0]}"
            lines.append(
                f"{result.scenario.id:<24}{rate:>8}{result.calls:>7}"
                f"{result.seconds:>8.1f}   {flaky[:88]}"
            )
        lines.append("-" * 92)
        lines.append(
            f"{self.passed}/{self.applicable} scenarios passed every repetition"
            f"  ·  {self.calls} calls  ·  {self.seconds:.1f}s  ·  ${self.cost:.4f}"
        )
        lines.append(_tier_line(self.cost_by_tier))
        all_runs = [run for result in self.results for run in result.runs]
        refusal = _refusal_line(all_runs)
        if refusal:
            lines.append(refusal)
        provider_line = _provider_line(all_runs)
        if provider_line:
            lines.append(provider_line)
        return "\n".join(lines)


async def run_suite(
    scenarios: list[Scenario],
    spec: WorkflowSpec,
    client_factory: Callable[[], OpenRouterClient],
    settings_lookup: dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_spend: float | None = None,
    budget: SweepBudget | None = None,
    results_log: "ResultsLog | None" = None,
) -> EvalReport:
    runs = []
    for scenario in scenarios:
        logger.info("eval: %s", scenario.id)
        run = await run_scenario(
            scenario, spec, client_factory, settings_lookup, timeout, max_spend,
            budget)
        runs.append(run)
        if results_log is not None:
            results_log.record(run, spec.name, repetition=1)
    return EvalReport(runs=runs, workflow=spec.name)


async def run_repeated(
    scenarios: list[Scenario],
    spec: WorkflowSpec,
    client_factory: Callable[[], OpenRouterClient],
    settings_lookup: dict[str, Any],
    repeat: int = 3,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_spend: float | None = None,
    budget: SweepBudget | None = None,
    results_log: "ResultsLog | None" = None,
) -> RepeatedReport:
    results = []
    for scenario in scenarios:
        runs = []
        for attempt in range(repeat):
            logger.info("eval: %s (%d/%d)", scenario.id, attempt + 1, repeat)
            run = await run_scenario(
                scenario, spec, client_factory, settings_lookup, timeout, max_spend,
                budget)
            runs.append(run)
            # Written before the next unit starts, so an interrupt anywhere
            # after this point keeps everything bought so far.
            if results_log is not None:
                results_log.record(run, spec.name, repetition=attempt + 1)
            if run.skipped:
                # Neither reason changes between repetitions: a workflow that
                # cannot satisfy a scenario still cannot, and a budget that is
                # exhausted stays exhausted.
                break
        results.append(RepeatedRun(scenario=scenario, runs=runs))
    return RepeatedReport(results=results, workflow=spec.name, repeat=repeat)
