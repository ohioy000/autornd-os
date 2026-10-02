"""Which judge blocked the exit must survive the run that asked.

**Why this exists.** `derived_tolerances` ran two build-loop rounds with
`implement` green and `validate` green and did *not* exit, so one of the two
free checks must have dissented. The record was supposed to say which. It said
nothing, and had said nothing for 64 recorded iterations across six runs,
because the retention had two independent defects and the suite could see
neither:

1. A check's entry in `state.outputs` is a **plain dict** (`_run_check` builds
   `{**data, "passed": ..., "detail": ...}`), so `getattr(coverage, "passed",
   None)` was `None` every single time.
2. The fold could not be read there at all. `judges` is the node *after*
   `validate` in the loop body, so the only `judges` output in scope when the
   iteration is recorded belongs to the **previous** iteration — empty on the
   first, stale on the rest.

Dissent is therefore derived from the four judges themselves, all of which have
run by the time validate closes the iteration. That is what `judges_agree` does
with the same four values, and it cannot go stale.

This is the second instrument in one blueprint found recording nothing while
looking wired — see HANDOVER §6.8. Both are pinned now.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from autornd.graph.adapter import PhaseRunner
from autornd.graph.spec import Node
from autornd.graph.executor import ExecutionState
from autornd.models.verdicts import ImplementVerdict, TriageVerdict, ValidateVerdict
from autornd.routing.openrouter import ModelResponse, OpenRouterClient


def _state(*, coverage_passed, consistency_passed, implement_green) -> ExecutionState:
    state = ExecutionState(request="spec a bore fit")
    state.outputs["triage"] = TriageVerdict(
        domains=["mechanical"], risk="low", complexity="medium",
        unrecallable=False, rationale="r", specialists=[], summary="s")
    state.outputs["plan"] = "the plan"
    state.outputs["implement"] = ImplementVerdict(
        done=True, green=implement_green, summary="s",
        red_cause=None if implement_green else "implementation is red")
    # Exactly as the executor writes them: plain dicts, never objects.
    state.outputs["coverage"] = {"missed": [], "passed": coverage_passed,
                                 "detail": ""}
    state.outputs["consistency"] = {"conflicts": [], "passed": consistency_passed,
                                    "detail": ""}
    return state


async def _run_validate(state, *, validate_green):
    runner = PhaseRunner(client=OpenRouterClient(api_key="test"))
    verdict = ValidateVerdict(
        green=validate_green,
        red_cause=None if validate_green else "criterion 4 fails",
        # Ruling D46 (1): a green with nothing behind it is the bug the
        # ruling names, so the fixture carries the assessment it claims.
        evidence=(["criterion 1: PASS — the check ran"] if validate_green
                  else ["criterion 4: FAIL — the totals disagree"]))
    response = ModelResponse(content="{}", model="m", prompt_tokens=1,
                             completion_tokens=1, cost=0.0)
    with patch("autornd.engine.phases.run_validate",
               new=AsyncMock(return_value=(verdict, response))):
        await runner._phase_validate(Node(id="validate", kind="ai"), state)
    return runner.iterations[-1]


@pytest.mark.asyncio
async def test_the_free_check_that_dissented_is_named():
    """The exact case `derived_tolerances` produced and could not report."""
    state = _state(coverage_passed=False, consistency_passed=True,
                   implement_green=True)
    record = await _run_validate(state, validate_green=True)

    assert record["coverage_passed"] is False
    assert record["consistency_passed"] is True
    assert record["dissenting"] == ["coverage"]


@pytest.mark.asyncio
async def test_a_unanimous_iteration_names_no_dissenter():
    state = _state(coverage_passed=True, consistency_passed=True,
                   implement_green=True)
    record = await _run_validate(state, validate_green=True)
    assert record["dissenting"] == []
    assert record["coverage_passed"] is True


@pytest.mark.asyncio
async def test_every_red_judge_is_named_not_just_the_first():
    state = _state(coverage_passed=False, consistency_passed=False,
                   implement_green=False)
    record = await _run_validate(state, validate_green=False)
    assert record["dissenting"] == ["consistency", "coverage", "implement",
                                    "validate"]


@pytest.mark.asyncio
async def test_a_check_that_never_ran_is_not_a_dissenter():
    """Absent is not red. A workflow without `coverage` must not be told it
    failed one — the loop's exit condition never asked it anything."""
    state = _state(coverage_passed=True, consistency_passed=True,
                   implement_green=True)
    del state.outputs["coverage"]
    record = await _run_validate(state, validate_green=True)
    assert record["coverage_passed"] is None
    assert record["dissenting"] == []


@pytest.mark.asyncio
async def test_the_stale_fold_is_not_consulted():
    """A `judges` output in scope belongs to the previous iteration."""
    state = _state(coverage_passed=True, consistency_passed=True,
                   implement_green=True)
    state.outputs["judges"] = {"passed": False,
                               "dissenting": ["validate"], "detail": "stale"}
    record = await _run_validate(state, validate_green=True)
    assert record["dissenting"] == []


# ── Ruling D46 (ARCH-20261002-111) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_check_that_compared_nothing_is_listed_in_the_record():
    """(d) Ruling D46 (3): the run's record lists every check that did not
    check — a reader sees the comparison that never happened."""
    state = _state(coverage_passed=True, consistency_passed=True,
                   implement_green=True)
    state.outputs["consistency"] = {"conflicts": [], "passed": True,
                                    "detail": "", "checked": False}
    record = await _run_validate(state, validate_green=True)
    assert record["unchecked"] == ["consistency"]
    assert record["dissenting"] == []


@pytest.mark.asyncio
async def test_a_consistency_only_failure_is_logged_naming_the_judge():
    """(e) Ruling D46 (4): the fold refuses convergence on a coverage miss or
    a consistency conflict too, and the next attempt is told why — whether or
    not validate and implement are red (review B finding 9)."""
    state = _state(coverage_passed=True, consistency_passed=False,
                   implement_green=True)
    runner = PhaseRunner(client=OpenRouterClient(api_key="test"))
    verdict = ValidateVerdict(
        green=True, red_cause=None,
        evidence=["criterion 1: PASS — the check ran"])
    response = ModelResponse(content="{}", model="m", prompt_tokens=1,
                             completion_tokens=1, cost=0.0)
    with patch("autornd.engine.phases.run_validate",
               new=AsyncMock(return_value=(verdict, response))):
        await runner._phase_validate(Node(id="validate", kind="ai"), state)
    assert len(runner.failure_log) == 1
    entry = runner.failure_log[0]
    assert "consistency" in entry["red_cause"], entry["red_cause"]
    assert "validate" not in entry["red_cause"]
    assert "implement" not in entry["red_cause"]


@pytest.mark.asyncio
async def test_one_entry_per_iteration_not_two():
    """(e) A failed attempt is one failure: a second write in the same
    iteration folds its cause in rather than appending the dissent twice."""
    state = _state(coverage_passed=False, consistency_passed=False,
                   implement_green=False)
    runner = PhaseRunner(client=OpenRouterClient(api_key="test"))
    verdict = ValidateVerdict(
        green=True, red_cause=None,
        evidence=["criterion 1: PASS — the check ran"])
    response = ModelResponse(content="{}", model="m", prompt_tokens=1,
                             completion_tokens=1, cost=0.0)
    node = Node(id="validate", kind="ai")
    with patch("autornd.engine.phases.run_validate",
               new=AsyncMock(return_value=(verdict, response))):
        await runner._phase_validate(node, state)
        await runner._phase_validate(node, state)
    assert len(runner.failure_log) == 1
    entry = runner.failure_log[0]
    assert "coverage" in entry["red_cause"]
    assert "consistency" in entry["red_cause"]
    assert "implement" in entry["red_cause"]
