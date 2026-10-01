"""Ruling D42: a reviewer that fails is not a finding (ARCH-20261001-104, F1).

A review specialist that fails is retried once; a second failure is recorded
as not reviewed with its failure class, never as a finding and never as a
block. The review ships only if no completed reviewer blocks AND at least
half the assigned reviewers (rounded up) completed. A spend stop is not a
reviewer failure: it is the run's terminal and propagates.

Exhibit: 102's Q2, where a reviewer's failure became a 'high' finding
("Specialist Test Engineer failed to complete review — manual review
required") and refused a correct answer. Its class, read from that run's
stderr, was BudgetExceeded: the run crossed its cap mid-review.

Driven through run_repeated with the billing double; every field is read
back from the written JSONL.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from autornd.engine import phases
from autornd.evals.runner import ResultsLog, _isolated_store, run_repeated
from autornd.evals.scenario import parse
from autornd.graph.spec import load
from autornd.routing.openrouter import BudgetExceeded
from autornd.specialists.registry import get_specialists
from tests.conftest import make_mock_client

SPEC = load("workflows/engineering-rnd.yaml")
SETTINGS = {"max_iterations": 2, "escalation_recovery_attempts": 1,
            "review_rework_attempts": 1}
REVIEW_PROMPT = "ship: true if safe to ship"
# The watchdog suite's request and texts, which pass the build judges
# (tests/test_watchdog.py TODAY_PATH reaches review), at high risk so the
# review team is three: the two staffed roles plus the architect.
REQUEST = "Add retry with exponential backoff to the MQTT client"
_WORK = {"feasible": True, "concerns": [], "blockers": [], "critical": False,
         "done": True, "green": True, "red_cause": None, "evidence": [],
         "summary": "Backoff is capped at 60s with jitter applied.",
         "ship": True, "findings": [], "verdict": "Ship."}
RESPONSES = {
    "triage": {"domains": ["backend"], "risk": "high",
               "specialists": ["backend_engineer", "test_engineer"],
               "summary": "MQTT client retry", "unrecallable": False},
    "architecture": {"ready": True, "plan": "Cap backoff at 60s.", "blockers": [],
                     "success_criteria": ["Backoff is capped at 60s with jitter"]},
    "engineering": _WORK, "judge": _WORK,
    "escalation": {"root_cause_analysis": "x", "resolution_directive": "y",
                   "requires_human": True},
}


def _failing_reviewers(names: set[str], exc: type[Exception] = ValueError):
    """The billing double, with the named review specialists raising on every
    review call. Their system prompts identify them."""
    prompts = {s.system_prompt: s.name for s in get_specialists(sorted(names))}
    client = make_mock_client(RESPONSES)
    original = client.chat_json.side_effect
    calls: dict[str, int] = {}

    async def chat_json(function, system_prompt, user_message, **kwargs):
        if REVIEW_PROMPT in user_message.lower() and system_prompt in prompts:
            calls[prompts[system_prompt]] = calls.get(prompts[system_prompt], 0) + 1
            raise exc("schema rejected the reply")
        return await original(function, system_prompt, user_message, **kwargs)

    client.chat_json = AsyncMock(side_effect=chat_json)
    client.review_failures = calls
    return client


async def _unit(tmp_path, client):
    path = tmp_path / "units.jsonl"
    scenario = parse({"id": "quorum", "request": REQUEST, "timeout": 60})
    with _isolated_store(), ResultsLog(path, {"suite": "quorum"}) as log:
        await run_repeated([scenario], SPEC, lambda: client, SETTINGS,
                           repeat=1, timeout=60, results_log=log)
    (unit,) = [json.loads(l) for l in path.read_text().splitlines()
               if json.loads(l)["record"] == "unit"]
    return unit


class TestOneFailedReviewerOfThree:
    async def test_the_review_ships_on_the_two_that_completed(self, tmp_path):
        client = _failing_reviewers({"test_engineer"})
        unit = await _unit(tmp_path, client)
        review = unit["verdicts"]["review"]
        # Never a finding, and it ships: the two assertions the old
        # behaviour (a failure counted as a 'high' finding) fails.
        assert not any(f.get("lens") == "workflow_engine" for f in review["findings"])
        assert review["ship"] is True
        assert review["reviewers_assigned"] == 3
        assert review["reviewers_completed"] == 2
        assert review["ship"] is True
        assert [n["failure_class"] for n in review["not_reviewed"]] == ["ValueError"]
        # Retried once: two attempts, then recorded.
        assert list(client.review_failures.values()) == [2]
        # Never a finding.
        assert not any(f.get("lens") == "workflow_engine" for f in review["findings"])
        assert unit["status"] == "completed"


class TestTwoFailedReviewersOfThree:
    async def test_below_quorum_the_review_does_not_ship_and_says_why(self, tmp_path):
        client = _failing_reviewers({"test_engineer", "systems_architect"})
        unit = await _unit(tmp_path, client)
        review = unit["verdicts"]["review"]
        assert review["reviewers_completed"] == 1 and review["ship"] is False
        assert "The review did not complete: 1 of 3 reviewers completed" in review["verdict"]
        assert "below the quorum of 2" in review["verdict"]
        assert not any(f.get("lens") == "workflow_engine" for f in review["findings"])


class TestASpendStopIsNotAReviewerFailure:
    async def test_budget_exceeded_propagates_and_is_not_retried(self):
        client = _failing_reviewers({"test_engineer"}, exc=BudgetExceeded)
        triage = phases.TriageVerdict(**RESPONSES["triage"])
        plan = phases.PlanVerdict(**RESPONSES["architecture"])
        implement = phases.ImplementVerdict(**{k: _WORK[k] for k in
                                               ("done", "green", "red_cause", "summary")})
        with pytest.raises(BudgetExceeded):
            await phases.run_review(
                client, REQUEST, triage, plan, implement,
                get_specialists(["backend_engineer", "test_engineer",
                                 "systems_architect"]))
        assert list(client.review_failures.values()) == [1]
