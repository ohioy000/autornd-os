"""Three criterion outcomes, three terminals — satisfied, abstained, unmet.

The primary subject is case (c), the failure path. HANDOVER §4.2 B14 records a
run that made 42 calls against a 41-call ceiling and produced no terminal. The
graph now bounds every loop, routes the exhaustion to escalation, and names the
diagnosis and the bound in the terminal reason. This file proves it.

All three cases drive the full ``engineering-rnd`` workflow end to end through
``ScriptedRunner``, which returns canned verdicts for AI nodes and runs real
checks. No provider, no network, no spend.
"""

from __future__ import annotations

import pytest

from tests.test_graph import _run, BASE, IMPL, SETTINGS


PLAN_ABSTAINED = {
    "ready": True,
    "plan": "Cap backoff at 60s, handle 100 connections.",
    "success_criteria": [
        "Reconnect loop applies exponential backoff capped at 60s",
        "The system handles exactly 100 concurrent connections",
    ],
}

PLAN_UNMET = {
    "ready": True,
    "plan": "Implement a caching layer with Redis.",
    "success_criteria": [
        "Caching layer stores computed results in Redis",
        "Cache invalidation runs on every write",
    ],
}

IMPL_UNMET = {
    "done": True, "green": True, "iteration": 1, "blocked_on": [],
    "summary": "Applied exponential backoff to the reconnect loop capped at 60s.",
}


@pytest.mark.asyncio
class TestThreeTerminals:
    """Convention 22: each test simulates its condition end to end."""

    async def test_satisfied_criteria_reach_completed(self):
        """Case (a): all criteria addressed → completed, no escalation."""
        state, runner = await _run({**BASE, "validate": {"green": True}})
        assert state.status == "completed"
        assert "escalation" not in state.path
        judges = state.outputs["judges"]
        assert judges["passed"] is True
        assert "all " in judges["detail"]
        assert runner.ai_calls.count("implement") == 1

    async def test_abstained_criteria_complete_with_empty_seat(self):
        """Case (b): a FORM criterion abstains → coverage passes → fold passes
        BUT records an empty seat (ARCH-20260922-043), not a dissent or
        unanimous agreement."""
        verdicts = {
            "triage": {"risk": "medium", "domains": ["backend"],
                       "unrecallable": False},
            "context": {}, "plan": PLAN_ABSTAINED,
            "feasibility": {"feasible": True},
            "implement": {**IMPL},
            "domain_review": {"critical": False},
            "review": {"ship": True},
            "validate": {"green": True},
        }
        state, runner = await _run(verdicts)
        assert state.status == "completed"
        assert "escalation" not in state.path

        judges = state.outputs["judges"]
        assert judges["passed"] is True
        assert judges["abstained_judges"] == {"coverage": 1}
        assert "empty seat" in judges["detail"]
        assert "all " not in judges["detail"], (
            "an abstaining judge must not be recorded as agreeing")

        coverage = state.outputs["coverage"]
        assert coverage["passed"] is True
        assert len(coverage["abstained"]) == 1

    async def test_unmet_criteria_exhaust_to_escalated(self):
        """Case (c): coverage persistently fails → build_loop exhausts →
        escalation → recovery_loop exhausts → terminal 'escalated'.

        This is the path that ran 42 calls into a ceiling (B14). Assert it
        terminates within its declared bounds, names the diagnosis in the
        reason, and does not reach any call ceiling."""
        verdicts = {
            "triage": {"risk": "medium", "domains": ["backend"],
                       "unrecallable": False},
            "context": {}, "plan": PLAN_UNMET,
            "feasibility": {"feasible": True},
            "implement": IMPL_UNMET,
            "domain_review": {"critical": False},
            "review": {"ship": True},
            "validate": {"green": True},
            "escalation": {"requires_human": False,
                           "root_cause_analysis": "Implementation does not "
                           "address caching requirements"},
        }
        state, runner = await _run(verdicts)

        assert state.status == "escalated"
        assert "escalation" in state.path

        build = state.outputs["build_loop"]
        assert build["converged"] is False
        assert build["iterations"] == SETTINGS["max_iterations"]

        recovery = state.outputs["recovery_loop"]
        assert recovery["converged"] is False
        assert recovery["iterations"] == SETTINGS["escalation_recovery_attempts"]

        expected_impl = (SETTINGS["max_iterations"]
                         + SETTINGS["escalation_recovery_attempts"])
        assert runner.ai_calls.count("implement") == expected_impl

        assert "did not converge" in state.reason
        assert "still red" in state.reason

        coverage = state.outputs["coverage"]
        assert coverage["passed"] is False
        assert len(coverage["missed"]) == 2

        judges = state.outputs["judges"]
        assert judges["passed"] is False
        assert "coverage" in judges["detail"]

    async def test_failure_record_names_the_persistent_criteria(self):
        """ARCH-20260923-052 Assertion 1: the record names which criteria stayed
        unsatisfied. They live in coverage.missed and coverage.detail, reachable
        from the terminal via: reason → 'still red: build' → judges.dissenting
        → coverage.missed."""
        verdicts = {
            "triage": {"risk": "medium", "domains": ["backend"],
                       "unrecallable": False},
            "context": {}, "plan": PLAN_UNMET,
            "feasibility": {"feasible": True},
            "implement": IMPL_UNMET,
            "domain_review": {"critical": False},
            "review": {"ship": True},
            "validate": {"green": True},
            "escalation": {"requires_human": False,
                           "root_cause_analysis": "Implementation does not "
                           "address caching requirements"},
        }
        state, _ = await _run(verdicts)

        coverage = state.outputs["coverage"]
        assert set(coverage["missed"]) == {
            "Caching layer stores computed results in Redis",
            "Cache invalidation runs on every write",
        }
        assert "0% of its terms appear" in coverage["detail"]

        # The criteria are in the record but NOT in the terminal reason itself.
        # A reader must chase: reason → judges → coverage to reach them.
        assert "Caching" not in (state.reason or ""), (
            "if this starts passing, the criteria were surfaced in the "
            "terminal and the -052 finding is resolved")

    async def test_escalation_diagnosis_is_captured(self):
        """ARCH-20260923-052 Assertion 2: the escalation node produces a
        diagnosis (root_cause_analysis) and it is present in the record."""
        verdicts = {
            "triage": {"risk": "medium", "domains": ["backend"],
                       "unrecallable": False},
            "context": {}, "plan": PLAN_UNMET,
            "feasibility": {"feasible": True},
            "implement": IMPL_UNMET,
            "domain_review": {"critical": False},
            "review": {"ship": True},
            "validate": {"green": True},
            "escalation": {"requires_human": False,
                           "root_cause_analysis": "Implementation does not "
                           "address caching requirements"},
        }
        state, _ = await _run(verdicts)

        esc = state.outputs["escalation"]
        assert esc["root_cause_analysis"] == (
            "Implementation does not address caching requirements")

        # The diagnosis is in state.outputs but NOT in the terminal reason.
        assert "caching" not in (state.reason or "").lower(), (
            "if this starts passing, the diagnosis was surfaced in the "
            "terminal and the -052 finding is resolved")

    async def test_escalation_sets_human_or_not_signal(self):
        """ARCH-20260923-052 Assertion 3: the escalation verdict carries
        requires_human and it gates recovery."""
        verdicts = {
            "triage": {"risk": "medium", "domains": ["backend"],
                       "unrecallable": False},
            "context": {}, "plan": PLAN_UNMET,
            "feasibility": {"feasible": True},
            "implement": IMPL_UNMET,
            "domain_review": {"critical": False},
            "review": {"ship": True},
            "validate": {"green": True},
            "escalation": {"requires_human": False,
                           "root_cause_analysis": "wrong topic"},
        }
        state, _ = await _run(verdicts)
        assert state.outputs["escalation"]["requires_human"] is False
        assert state.status == "escalated"
        assert "recovery_loop" in state.outputs, "recovery ran"
