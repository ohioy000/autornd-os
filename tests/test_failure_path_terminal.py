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

    async def test_exhausted_terminal_names_unmet_criteria(self):
        """ARCH-20260923-053: case (c)'s terminal quotes the unmet criteria
        from coverage.missed — MEASURED, the presence test's own output."""
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

        assert state.status == "escalated"
        assert "'Caching layer stores computed results in Redis'" in state.reason
        assert "'Cache invalidation runs on every write'" in state.reason

    async def test_exhausted_terminal_labels_the_assessment(self):
        """ARCH-20260923-053: the escalation diagnosis appears in the terminal
        explicitly labelled as a model claim — never merged with the measured
        part (convention 26: a reading mistakable for a stronger claim is a
        defect in the instrument)."""
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

        assert "— assessment: Implementation does not address caching requirements" in state.reason
        # The label sits between the measured part and the diagnosis, so the
        # two can never read as one unlabelled sentence.
        assert state.reason.index("unmet:") < state.reason.index("— assessment:")

    async def test_exhausted_terminal_bounds_a_long_criteria_list(self):
        """ARCH-20260923-053: the terminal names the first few criteria and
        counts the rest — it cannot grow without limit. Bound: three shown."""
        from autornd.graph.executor import CRITERIA_SUFFIX_SHOWN, _criteria_suffix
        from autornd.graph.executor import ExecutionState as ES

        many = [f"criterion {i} about caching" for i in range(6)]
        state = ES(request="r")
        state.outputs["coverage"] = {"missed": many}
        suffix = _criteria_suffix(state)

        assert "'criterion 0 about caching'" in suffix
        assert "'criterion 2 about caching'" in suffix
        assert "criterion 3" not in suffix
        assert "and 3 more" in suffix
        assert CRITERIA_SUFFIX_SHOWN == 3

    async def test_exhausted_terminal_omits_empty_assessment(self):
        """ARCH-20260923-053: no empty label — an empty or placeholder
        diagnosis leaves no 'assessment' text in the terminal."""
        from autornd.graph.executor import _assessment_suffix
        from autornd.graph.executor import ExecutionState as ES

        for blank in ("", "   ", "n/a", "N/A", "none", "tbd", "unknown", None):
            state = ES(request="r")
            state.outputs["escalation"] = {"root_cause_analysis": blank}
            assert _assessment_suffix(state) == "", f"blank {blank!r} printed"

        state = ES(request="r")
        state.outputs["escalation"] = {"root_cause_analysis": "real finding"}
        assert _assessment_suffix(state) == " — assessment: real finding"

    async def test_satisfied_and_abstained_terminals_unchanged(self):
        """ARCH-20260923-053: cases (a) and (b) carry no unmet list and no
        assessment label — the exhausted path only."""
        satisfied, _ = await _run({**BASE, "validate": {"green": True}})
        assert satisfied.status == "completed"
        assert "unmet:" not in (satisfied.reason or "")
        assert "assessment:" not in (satisfied.reason or "")

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
        abstained, _ = await _run(verdicts)
        assert abstained.status == "completed"
        assert "unmet:" not in (abstained.reason or "")
        assert "assessment:" not in (abstained.reason or "")

    async def test_breaking_coverage_missed_breaks_the_terminal(self):
        """ARCH-20260923-053, prove it by breaking it: with coverage.missed
        removed, the terminal loses the criteria — the suffix reads the field
        it claims to read (convention 28)."""
        from autornd.graph.executor import _criteria_suffix
        from autornd.graph.executor import ExecutionState as ES

        state = ES(request="r")
        state.outputs["coverage"] = {
            "missed": ["Caching layer stores computed results in Redis"]}
        assert "Caching layer" in _criteria_suffix(state)

        del state.outputs["coverage"]["missed"]
        assert _criteria_suffix(state) == ""

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

        # ARCH-20260923-053 resolved the -052 finding: the criteria ARE now
        # surfaced in the terminal itself (see
        # test_exhausted_terminal_names_unmet_criteria above). This keeps the
        # record-level assertion: they live quoted in coverage.missed.
        assert "'Caching layer stores computed results in Redis'" in (state.reason or ""), (
            "-053 resolved the -052 finding: the criteria are now in the terminal")

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

        # ARCH-20260923-053 resolved the -052 finding: the diagnosis IS now
        # in the terminal, labelled as a model claim (see
        # test_exhausted_terminal_labels_the_assessment above).
        assert "caching" in (state.reason or "").lower(), (
            "-053 resolved the -052 finding: the diagnosis is in the terminal, labelled")

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
