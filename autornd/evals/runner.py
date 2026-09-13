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
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from autornd.evals.assertions import AssertionResult, RunOutcome, score
from autornd.evals.scenario import Scenario
from autornd.graph.adapter import PhaseRunner
from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import WorkflowSpec
from autornd.routing.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

__all__ = ["EvalReport", "ScenarioRun", "run_scenario", "run_suite"]

DEFAULT_CALL_CEILING = 40
DEFAULT_TIMEOUT_SECONDS = 600.0


class CallCeilingExceeded(RuntimeError):
    """A run asked for more model calls than the scenario allows."""


class BoundedRunner(PhaseRunner):
    """A PhaseRunner that refuses to exceed its call budget.

    MAX_ITERATIONS bounds loops but not total spend: a workflow with a wide
    fan-out can make many calls per iteration. This bounds the thing that
    actually costs money.
    """

    def __init__(self, client: OpenRouterClient, ceiling: int) -> None:
        super().__init__(client)
        self.ceiling = ceiling
        self.calls = 0

    async def run_ai(self, node, state):
        self.calls += 1
        if self.calls > self.ceiling:
            raise CallCeilingExceeded(
                f"stopped at {self.calls} model calls (ceiling {self.ceiling}); "
                f"raise max_calls on the scenario if this is expected"
            )
        return await super().run_ai(node, state)


@dataclass
class ScenarioRun:
    scenario: Scenario
    results: list[AssertionResult]
    calls: int
    seconds: float
    cost: float = 0.0
    error: str | None = None
    path: list[str] = field(default_factory=list)

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

    def render(self) -> str:
        lines = [
            f"workflow: {self.workflow}",
            f"{'scenario':<28}{'result':<8}{'calls':>6}{'secs':>8}   failures",
            "-" * 92,
        ]
        for run in self.runs:
            mark = "pass" if run.passed else "FAIL"
            detail = ", ".join(
                f"{f.name}(wanted {f.wanted}, got {f.got})" for f in run.failures
            ) or (run.error or "")
            lines.append(
                f"{run.scenario.id:<28}{mark:<8}{run.calls:>6}{run.seconds:>8.1f}   "
                f"{detail[:44]}"
            )
        lines.append("-" * 92)
        summary = f"{self.passed}/{self.total} scenarios passed"
        summary += f"  ·  {self.calls} model calls  ·  {self.seconds:.1f}s"
        if self.cost:
            summary += f"  ·  ${self.cost:.4f}"
        lines.append(summary)
        return "\n".join(lines)


async def run_scenario(
    scenario: Scenario,
    spec: WorkflowSpec,
    client_factory: Callable[[], OpenRouterClient],
    settings_lookup: dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ScenarioRun:
    ceiling = scenario.max_calls or DEFAULT_CALL_CEILING
    # One call of headroom, so exceeding the expectation is reported by the
    # max_calls assertion rather than as an opaque abort.
    runner = BoundedRunner(client_factory(), ceiling + 1)
    executor = GraphExecutor(spec, runner, settings_lookup)

    started = time.perf_counter()
    error: str | None = None
    try:
        state = await asyncio.wait_for(executor.run(scenario.request), timeout)
    except asyncio.TimeoutError:
        from autornd.graph.executor import ExecutionState

        state = ExecutionState(request=scenario.request)
        error = f"timed out after {timeout:.0f}s"
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
                         cost=runner.total_cost, error=error)
    return ScenarioRun(
        scenario=scenario,
        results=score(scenario, outcome),
        calls=runner.calls,
        seconds=seconds,
        cost=runner.total_cost,
        error=error,
        path=list(state.path),
    )


async def run_suite(
    scenarios: list[Scenario],
    spec: WorkflowSpec,
    client_factory: Callable[[], OpenRouterClient],
    settings_lookup: dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> EvalReport:
    runs = []
    for scenario in scenarios:
        logger.info("eval: %s", scenario.id)
        runs.append(await run_scenario(
            scenario, spec, client_factory, settings_lookup, timeout))
    return EvalReport(runs=runs, workflow=spec.name)
