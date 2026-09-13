"""Scoring a finished run against a scenario's expectations.

Every assertion here is a set comparison or an integer comparison. None of them
asks a model anything, so a full regression sweep costs nothing and finishes in
milliseconds — which is the difference between a suite you run on every change
and one you run when you can afford it.

Each assertion reports what it wanted and what it got, because a red line that
does not tell you the actual value is a red line you have to re-run to
understand.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from autornd.evals.scenario import RISK_ORDER, Scenario
from autornd.graph.executor import ExecutionState

__all__ = ["Assertion", "AssertionResult", "RunOutcome", "score"]


@dataclass
class RunOutcome:
    """What a run produced, in the terms assertions care about."""

    state: ExecutionState
    calls: int
    cost: float = 0.0
    error: str | None = None


@dataclass
class AssertionResult:
    name: str
    passed: bool
    wanted: Any = None
    got: Any = None
    detail: str = ""

    def __str__(self) -> str:
        mark = "pass" if self.passed else "FAIL"
        if self.passed:
            return f"{mark}  {self.name}"
        return f"{mark}  {self.name}: wanted {self.wanted!r}, got {self.got!r}"


Assertion = Callable[[Scenario, RunOutcome], AssertionResult | None]

_ASSERTIONS: list[Assertion] = []


def assertion(fn: Assertion) -> Assertion:
    _ASSERTIONS.append(fn)
    return fn


def _triage(outcome: RunOutcome):
    return outcome.state.outputs.get("triage")


def _values(items) -> set[str]:
    """Enum members and plain strings compare the same way."""
    return {getattr(i, "value", i) for i in (items or [])}


# ── triage: did it understand the request ────────────────────────────────

@assertion
def domains_exact(scenario: Scenario, outcome: RunOutcome):
    wanted = scenario.expect.get("domains")
    if wanted is None:
        return None
    triage = _triage(outcome)
    got = _values(getattr(triage, "domains", None))
    return AssertionResult("domains", got == set(wanted), sorted(wanted), sorted(got))


@assertion
def domains_include(scenario: Scenario, outcome: RunOutcome):
    wanted = scenario.expect.get("domains_include")
    if wanted is None:
        return None
    got = _values(getattr(_triage(outcome), "domains", None))
    missing = set(wanted) - got
    return AssertionResult(
        "domains_include", not missing, sorted(wanted), sorted(got),
        detail=f"missing {sorted(missing)}" if missing else "",
    )


@assertion
def risk_exact(scenario: Scenario, outcome: RunOutcome):
    wanted = scenario.expect.get("risk")
    if wanted is None:
        return None
    risk = getattr(_triage(outcome), "risk", None)
    got = getattr(risk, "value", risk)
    return AssertionResult("risk", got == wanted, wanted, got)


@assertion
def risk_at_least(scenario: Scenario, outcome: RunOutcome):
    """Under-classifying risk is the dangerous direction — it buys one reviewer
    where the change needed seven. Over-classifying only costs money."""
    wanted = scenario.expect.get("risk_at_least")
    if wanted is None:
        return None
    risk = getattr(_triage(outcome), "risk", None)
    got = getattr(risk, "value", risk)
    passed = got in RISK_ORDER and RISK_ORDER.index(got) >= RISK_ORDER.index(wanted)
    return AssertionResult("risk_at_least", passed, f">= {wanted}", got)


@assertion
def specialists_include(scenario: Scenario, outcome: RunOutcome):
    wanted = scenario.expect.get("specialists_include")
    if wanted is None:
        return None
    got = _values(getattr(_triage(outcome), "specialists", None))
    missing = set(wanted) - got
    return AssertionResult(
        "specialists_include", not missing, sorted(wanted), sorted(got),
        detail=f"missing {sorted(missing)}" if missing else "",
    )


@assertion
def specialists_exclude(scenario: Scenario, outcome: RunOutcome):
    unwanted = scenario.expect.get("specialists_exclude")
    if unwanted is None:
        return None
    got = _values(getattr(_triage(outcome), "specialists", None))
    present = set(unwanted) & got
    return AssertionResult(
        "specialists_exclude", not present, f"none of {sorted(unwanted)}", sorted(got),
        detail=f"unexpectedly assigned {sorted(present)}" if present else "",
    )


# ── the run itself ───────────────────────────────────────────────────────

@assertion
def status(scenario: Scenario, outcome: RunOutcome):
    wanted = scenario.expect.get("status")
    if wanted is None:
        return None
    return AssertionResult(
        "status", outcome.state.status == wanted, wanted, outcome.state.status,
        detail=outcome.state.reason or "",
    )


@assertion
def converge_within(scenario: Scenario, outcome: RunOutcome):
    """Iterations are the expensive axis: each one is a full build and verify."""
    wanted = scenario.expect.get("converge_within")
    if wanted is None:
        return None
    loop = outcome.state.outputs.get("build_loop") or {}
    got = loop.get("iterations")
    passed = bool(loop.get("converged")) and got is not None and got <= wanted
    return AssertionResult(
        "converge_within", passed, f"<= {wanted}", got,
        detail="" if loop.get("converged") else "did not converge",
    )


@assertion
def max_calls(scenario: Scenario, outcome: RunOutcome):
    """A cost regression guard. A change that quietly doubles call count is the
    kind of thing nobody notices until the bill arrives."""
    wanted = scenario.expect.get("max_calls")
    if wanted is None:
        return None
    return AssertionResult("max_calls", outcome.calls <= wanted,
                           f"<= {wanted}", outcome.calls)


@assertion
def criteria_addressed(scenario: Scenario, outcome: RunOutcome):
    wanted = scenario.expect.get("criteria_addressed")
    if wanted is None:
        return None
    coverage = outcome.state.outputs.get("coverage") or {}
    got = coverage.get("passed")
    return AssertionResult(
        "criteria_addressed", got == wanted, wanted, got,
        detail=coverage.get("detail", ""),
    )


def score(scenario: Scenario, outcome: RunOutcome) -> list[AssertionResult]:
    """Every assertion the scenario actually asked for."""
    if outcome.error:
        return [AssertionResult("run", False, "a completed run", "error",
                                detail=outcome.error)]
    results = [a(scenario, outcome) for a in _ASSERTIONS]
    return [r for r in results if r is not None]
