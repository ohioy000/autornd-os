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
import logging
import tempfile
import time
from dataclasses import dataclass, field
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
    "RepeatedReport",
    "RepeatedRun",
    "ScenarioRun",
    "run_repeated",
    "run_scenario",
    "run_suite",
]

DEFAULT_CALL_CEILING = 40
DEFAULT_TIMEOUT_SECONDS = 600.0


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

    @property
    def skipped(self) -> bool:
        return not self.results and bool(self.error) and "not applicable" in self.error

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
        provider_line = _provider_line(self.runs)
        if provider_line:
            lines.append(provider_line)
        return "\n".join(lines)


async def run_scenario(
    scenario: Scenario,
    spec: WorkflowSpec,
    client_factory: Callable[[], OpenRouterClient],
    settings_lookup: dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_spend: float | None = None,
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

    ceiling = scenario.max_calls or DEFAULT_CALL_CEILING
    # One call of headroom, so exceeding the expectation is reported by the
    # max_calls assertion rather than as an opaque abort.
    runner = BoundedRunner(client_factory(), ceiling + 1, spend_ceiling=max_spend)
    executor = GraphExecutor(spec, runner, settings_lookup)

    # A scenario's own timeout wins: it knows what it is measuring.
    deadline = scenario.timeout or timeout

    started = time.perf_counter()
    error: str | None = None
    try:
        with _isolated_store():
            state = await asyncio.wait_for(executor.run(scenario.request), deadline)
    except asyncio.TimeoutError:
        from autornd.graph.executor import ExecutionState

        state = ExecutionState(request=scenario.request)
        error = f"timed out after {deadline:.0f}s"
    except CallCeilingExceeded as exc:
        from autornd.graph.executor import ExecutionState

        state = ExecutionState(request=scenario.request)
        error = str(exc)
    except Exception as exc:  # a broken run is a result, not a crash
        from autornd.graph.executor import ExecutionState

        state = ExecutionState(request=scenario.request)
        error = f"{type(exc).__name__}: {exc}"
    seconds = time.perf_counter() - started

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
        provider_line = _provider_line(
            [run for result in self.results for run in result.runs])
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
) -> EvalReport:
    runs = []
    for scenario in scenarios:
        logger.info("eval: %s", scenario.id)
        runs.append(await run_scenario(
            scenario, spec, client_factory, settings_lookup, timeout, max_spend))
    return EvalReport(runs=runs, workflow=spec.name)


async def run_repeated(
    scenarios: list[Scenario],
    spec: WorkflowSpec,
    client_factory: Callable[[], OpenRouterClient],
    settings_lookup: dict[str, Any],
    repeat: int = 3,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_spend: float | None = None,
) -> RepeatedReport:
    results = []
    for scenario in scenarios:
        runs = []
        for attempt in range(repeat):
            logger.info("eval: %s (%d/%d)", scenario.id, attempt + 1, repeat)
            run = await run_scenario(
                scenario, spec, client_factory, settings_lookup, timeout, max_spend)
            runs.append(run)
            if run.skipped:
                break      # the shape will not change between repetitions
        results.append(RepeatedRun(scenario=scenario, runs=runs))
    return RepeatedReport(results=results, workflow=spec.name, repeat=repeat)
