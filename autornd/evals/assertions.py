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
    # Whether a budget guard stopped the run, rather than a crash or a timeout.
    # A guarded stop is different in kind: the run was making progress and the
    # partial state is real, so everything the scenario asked about is still
    # answerable. See `score`.
    stopped_by_budget: bool = False
    # The grounding the run assembled — briefing, retrieved documents and
    # researched findings. Kept because factual accuracy is graded against it,
    # and it does not live in node outputs.
    context: str = ""


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
def risk_at_most(scenario: Scenario, outcome: RunOutcome):
    """The cost ceiling. Risk drives review team size, so a request classified
    two levels above its consequence silently buys reviewers nobody needed."""
    wanted = scenario.expect.get("risk_at_most")
    if wanted is None:
        return None
    risk = getattr(_triage(outcome), "risk", None)
    got = getattr(risk, "value", risk)
    passed = got in RISK_ORDER and RISK_ORDER.index(got) <= RISK_ORDER.index(wanted)
    return AssertionResult("risk_at_most", passed, f"<= {wanted}", got)


@assertion
def unrecallable(scenario: Scenario, outcome: RunOutcome):
    """Separate from risk on purpose.

    A signed rollout to 40,000 devices harms nobody and cannot be taken back.
    Measured, it classifies `high` 3/3 — correct by the risk guide — so the
    recall question is asked on its own axis and buys one extra independent
    reviewer rather than inflating `critical`.
    """
    wanted = scenario.expect.get("unrecallable")
    if wanted is None:
        return None
    got = getattr(_triage(outcome), "unrecallable", None)
    return AssertionResult("unrecallable", got == wanted, wanted, got)


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
def path_includes(scenario: Scenario, outcome: RunOutcome):
    """Did the run actually take the nodes it was supposed to?

    A conditional node is invisible to every other assertion: a workflow whose
    `when` never fires produces the same verdicts as one without the node at
    all. The independent pass sat in the graph unexercised for exactly this
    reason — its spec loaded, its condition parsed, and nothing proved it ran.
    """
    wanted = scenario.expect.get("path_includes")
    if wanted is None:
        return None
    got = list(outcome.state.path)
    missing = [n for n in wanted if n not in got]
    return AssertionResult(
        "path_includes", not missing, wanted, got,
        detail=f"never ran {missing}" if missing else "",
    )


@assertion
def path_excludes(scenario: Scenario, outcome: RunOutcome):
    wanted = scenario.expect.get("path_excludes")
    if wanted is None:
        return None
    got = list(outcome.state.path)
    present = [n for n in wanted if n in got]
    return AssertionResult(
        "path_excludes", not present, f"none of {wanted}", got,
        detail=f"unexpectedly ran {present}" if present else "",
    )


def _normalise(text: str) -> str:
    """One spelling for comparison.

    Models write a minus sign three different ways. Grading `-23 LUFS` with a
    pattern that only matched the ASCII hyphen scored a correct answer wrong and
    reported 78% where the real figure was 91% — the grader was broken, not the
    system it was grading. Dashes, case and whitespace are normalised once,
    here, so no scenario file can get this wrong again.
    """
    for dash in ("\u2212", "\u2013", "\u2014", "\u2011"):
        text = text.replace(dash, "-")
    return " ".join(text.lower().split())


@assertion
def figures_present(scenario: Scenario, outcome: RunOutcome):
    """Are the published figures a correct answer must contain actually there?

    Counting citations measures whether a lookup happened, not whether the
    answer is right. These are checkable numbers from published standards, so
    the miss is named rather than reduced to a fraction: which figure is absent
    is the whole finding.
    """
    wanted = scenario.expect.get("figures_present")
    if wanted is None:
        return None

    context = _normalise(_researched_text(outcome))
    missing: list[str] = []
    for entry in wanted:
        alternates = entry if isinstance(entry, list) else [entry]
        if not any(_normalise(a) in context for a in alternates):
            missing.append(alternates[0])

    found = len(wanted) - len(missing)
    return AssertionResult(
        "figures_present", not missing,
        f"all {len(wanted)}", f"{found}/{len(wanted)}",
        detail=f"missing {missing}" if missing else "",
    )


def _researched_text(outcome: RunOutcome) -> str:
    """Everything the run assembled as grounding, however it is carried."""
    parts: list[str] = []
    for value in outcome.state.outputs.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            for inner in value.values():
                if isinstance(inner, str):
                    parts.append(inner)
    context = getattr(outcome, "context", "") or ""
    return "\n".join([*parts, context])


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
    """Every assertion the scenario actually asked for.

    A crash scores nothing but `run`, because a broken state answers no
    question honestly. **A budget guard is not a crash.** The runner sets the
    call ceiling one above the scenario's `max_calls` precisely "so exceeding
    the expectation is reported by the max_calls assertion rather than as an
    opaque abort" — and that could not happen, because this function discarded
    every assertion the moment an error was set.

    Measured: `requires_execution` stopped at 42 calls against an expectation
    of 40 and reported one failed `run` assertion carrying the raw guard text.
    The `max_calls` assertion it was supposed to fail was never evaluated, and
    the question actually being asked of that run — did the workflow terminate
    honestly — was answered by a cost expectation three blueprints old.

    So a guarded stop scores everything, and keeps the failed `run` assertion
    at the front so the stop itself is never lost.
    """
    run_failed = AssertionResult("run", False, "a completed run", "error",
                                 detail=outcome.error)
    if outcome.error and not outcome.stopped_by_budget:
        return [run_failed]
    results = [a(scenario, outcome) for a in _ASSERTIONS]
    scored = [r for r in results if r is not None]
    return [run_failed, *scored] if outcome.error else scored
