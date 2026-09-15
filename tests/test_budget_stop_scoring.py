"""A budget guard is not a crash, and its run still answers questions.

**Why this exists.** `run_scenario` sets the call ceiling one above the
scenario's `max_calls` with the comment: *"One call of headroom, so exceeding
the expectation is reported by the max_calls assertion rather than as an opaque
abort."* That could not happen. `score` returned a single failed `run`
assertion the moment any error was set, so the `max_calls` assertion the
headroom existed to produce was never evaluated.

**What it cost.** `requires_execution` stopped at 42 calls against an
expectation of 40, and reported one failed assertion carrying the raw guard
text. The question being asked of that run — did the workflow terminate
honestly — was silently answered by a cost expectation written three blueprints
earlier, before the workflow grew two of its three loops.

A crash still scores nothing but `run`: a broken state answers no question
honestly. A guarded stop scores everything, with the failed `run` assertion
kept at the front so the stop itself is never lost.
"""

from __future__ import annotations

from autornd.evals.assertions import RunOutcome, score
from autornd.evals.scenario import Scenario
from autornd.graph.executor import ExecutionState


def _state(status: str = "completed") -> ExecutionState:
    state = ExecutionState(request="r")
    state.status = status
    return state


GUARD = "stopped at 42 model calls (ceiling 41)"


def test_a_guarded_stop_scores_the_expectation_it_broke():
    scenario = Scenario(id="s", request="r", expect={"max_calls": 40})
    results = score(scenario, RunOutcome(state=_state(), calls=42,
                                         error=GUARD, stopped_by_budget=True))
    names = [r.name for r in results]
    assert "max_calls" in names, names
    calls = next(r for r in results if r.name == "max_calls")
    assert calls.passed is False
    assert calls.got == 42


def test_the_stop_itself_is_still_reported_and_comes_first():
    scenario = Scenario(id="s", request="r", expect={"max_calls": 40})
    results = score(scenario, RunOutcome(state=_state(), calls=42,
                                         error=GUARD, stopped_by_budget=True))
    assert results[0].name == "run"
    assert results[0].passed is False
    assert GUARD in results[0].detail


def test_a_crash_still_scores_nothing_but_run():
    """A broken state answers no question honestly."""
    scenario = Scenario(id="s", request="r", expect={"max_calls": 40})
    results = score(scenario, RunOutcome(state=_state(""), calls=3,
                                         error="KeyError: 'plan'"))
    assert [r.name for r in results] == ["run"]


def test_a_clean_run_is_unchanged_and_carries_no_run_assertion():
    scenario = Scenario(id="s", request="r", expect={"max_calls": 40})
    results = score(scenario, RunOutcome(state=_state(), calls=12))
    assert "run" not in [r.name for r in results]
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_a_guarded_stop_reports_the_status_it_actually_reached():
    """The termination question and the cost question are different questions."""
    scenario = Scenario(id="s", request="r",
                        expect={"max_calls": 40, "status": "escalated"})
    results = score(scenario, RunOutcome(state=_state("escalated"), calls=42,
                                         error=GUARD, stopped_by_budget=True))
    status = next(r for r in results if r.name == "status")
    assert status.passed is True
    assert next(r for r in results if r.name == "max_calls").passed is False
