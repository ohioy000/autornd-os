"""Test workflow engine execution with mocked OpenRouter."""

import json
from unittest.mock import AsyncMock

import pytest

from autornd.engine.workflow import WorkflowEngine
from autornd.models.workflow import WorkflowStatus
from autornd.routing.openrouter import OpenRouterClient
from tests.conftest import make_mock_response


TRIAGE_RESP = {
    "domains": ["firmware"],
    "risk": "high",
    "specialists": ["firmware_engineer", "test_engineer", "systems_architect"],
    "summary": "Firmware deep sleep redesign",
}

PLAN_RESP = {
    "ready": True,
    "plan": "Step 1: Refactor sleep state machine. Step 2: Add wake sources.",
    "blockers": [],
    "bom_estimate": None,
    "success_criteria": ["Sleep current < 10uA", "Wake latency < 500ms"],
}

IMPLEMENT_RESP = {
    "done": True,
    "green": True,
    "red_cause": None,
    "iteration": 1,
    "summary": "Refactored deep sleep FSM with configurable wake sources.",
}

VALIDATE_RESP = {
    "green": True,
    "red_cause": None,
    "evidence": ["Sleep current 8.2uA < 10uA target", "Wake latency 320ms < 500ms"],
}

REVIEW_RESP = {
    "ship": True,
    "findings": [],
    "verdict": "Ship — sleep performance meets all targets.",
}


FEASIBILITY_RESP = {
    "feasible": True,
    "concerns": [],
    "blockers": [],
}


ESCALATION_RESP = {
    "root_cause_analysis": "N/A — happy path.",
    "architectural_correction": None,
    "resolution_directive": "N/A",
    "requires_human": False,
}


def _route_by_content(user_message: str) -> dict:
    """Route mock responses by detecting which phase the prompt belongs to."""
    msg = user_message.lower()
    if "classify this engineering request" in msg:
        return TRIAGE_RESP
    if "create an implementation plan" in msg:
        return PLAN_RESP
    if "review this implementation plan" in msg or "plan produced by systems architect" in msg:
        return FEASIBILITY_RESP
    if "attempts all failed validation" in msg:
        return ESCALATION_RESP
    if "implement the following plan" in msg:
        return IMPLEMENT_RESP
    if "validate this implementation" in msg:
        return VALIDATE_RESP
    if "review this engineering work" in msg:
        return REVIEW_RESP
    return REVIEW_RESP


def _make_mock_client():
    client = OpenRouterClient(api_key="test")

    async def _mock_chat_json(function, system_prompt, user_message, **kwargs):
        data = _route_by_content(user_message)
        return data, make_mock_response(data, f"mock-{function}")

    client.chat_json = AsyncMock(side_effect=_mock_chat_json)
    client.close = AsyncMock()
    return client


def _make_failing_client(fail_iterations: int = 2, k3_requires_human: bool = False):
    """Validate fails N times then passes. Implement always succeeds.
    When the loop exhausts, K3 autopsy returns the configured requires_human flag."""
    client = OpenRouterClient(api_key="test")
    validate_count = {"n": 0}

    triage_resp = {
        "domains": ["backend"],
        "risk": "medium",
        "specialists": ["backend_engineer", "test_engineer"],
        "summary": "MQTT topic refactor",
    }
    plan_resp = {
        "ready": True,
        "plan": "Refactor MQTT topic structure.",
        "blockers": [],
        "bom_estimate": None,
        "success_criteria": ["All topics parse correctly"],
    }
    k3_resp = {
        "root_cause_analysis": "Systematic parsing failure in topic structure.",
        "architectural_correction": None,
        "resolution_directive": "Use strict schema validation before topic registration.",
        "requires_human": k3_requires_human,
    }

    async def _mock_chat_json(function, system_prompt, user_message, **kwargs):
        msg = user_message.lower()

        if "classify this engineering request" in msg:
            data = triage_resp
        elif "create an implementation plan" in msg:
            data = plan_resp
        elif "plan produced by systems architect" in msg or "review this implementation plan" in msg:
            data = {"feasible": True, "concerns": [], "blockers": []}
        elif "attempts all failed validation" in msg:
            data = k3_resp
        elif "validate this implementation" in msg:
            validate_count["n"] += 1
            if validate_count["n"] <= fail_iterations:
                data = {
                    "green": False,
                    "red_cause": "topic_parse_error",
                    "evidence": [f"Iteration {validate_count['n']}: topic fails"],
                }
            else:
                data = {
                    "green": True,
                    "red_cause": None,
                    "evidence": ["All topics parse correctly"],
                }
        elif "implement the following plan" in msg:
            data = {
                "done": True,
                "green": True,
                "red_cause": None,
                "iteration": 1,
                "summary": "Implemented topic refactor.",
            }
        else:
            data = {"ship": True, "findings": [], "verdict": "Ship."}

        return data, make_mock_response(data, f"mock-{function}")

    client.chat_json = AsyncMock(side_effect=_mock_chat_json)
    client.close = AsyncMock()
    return client


@pytest.mark.asyncio
class TestWorkflowEngine:
    async def test_happy_path(self, db_session):
        client = _make_mock_client()
        engine = WorkflowEngine(client, db_session)
        workflow = await engine.execute("Redesign deep sleep state machine for sensor nodes")

        assert workflow.status == WorkflowStatus.COMPLETED
        assert workflow.total_cost > 0

    async def test_blocked_plan(self, db_session):
        client = OpenRouterClient(api_key="test")

        triage_resp = {
            "domains": ["hardware"],
            "risk": "high",
            "specialists": ["hardware_engineer", "test_engineer", "systems_architect"],
            "summary": "New PCB revision",
        }
        blocked_plan = {
            "ready": False,
            "plan": "Cannot proceed without datasheet",
            "blockers": ["Missing XYZ sensor datasheet"],
            "bom_estimate": None,
            "success_criteria": [],
        }

        async def _mock(function, system_prompt, user_message, **kwargs):
            msg = user_message.lower()
            if "classify" in msg:
                data = triage_resp
            else:
                data = blocked_plan
            return data, make_mock_response(data)

        client.chat_json = AsyncMock(side_effect=_mock)
        client.close = AsyncMock()

        engine = WorkflowEngine(client, db_session)
        workflow = await engine.execute("Design new PCB revision")

        assert workflow.status == WorkflowStatus.BLOCKED

    async def test_iteration_loop_retries_then_passes(self, db_session):
        client = _make_failing_client(fail_iterations=2)
        engine = WorkflowEngine(client, db_session)
        workflow = await engine.execute("Refactor MQTT topic structure")

        assert workflow.status == WorkflowStatus.COMPLETED
        assert workflow.iteration >= 2

    async def test_escalation_recovery_also_fails(self, db_session):
        """K3 says fixable, but recovery loop also fails → ESCALATED."""
        client = _make_failing_client(fail_iterations=99, k3_requires_human=False)
        engine = WorkflowEngine(client, db_session)
        workflow = await engine.execute("Impossible task that always fails validation")

        assert workflow.status == WorkflowStatus.ESCALATED

    async def test_escalation_requires_human_blocks(self, db_session):
        """K3 says requires_human → BLOCKED."""
        client = _make_failing_client(fail_iterations=99, k3_requires_human=True)
        engine = WorkflowEngine(client, db_session)
        workflow = await engine.execute("Task needing manual hardware intervention")

        assert workflow.status == WorkflowStatus.BLOCKED

    async def test_escalation_recovery_succeeds(self, db_session):
        """K3 directive fixes the issue — recovery loop passes → COMPLETED."""
        client = _make_failing_client(fail_iterations=5, k3_requires_human=False)
        engine = WorkflowEngine(client, db_session)
        workflow = await engine.execute("Task that K3 can fix")

        assert workflow.status == WorkflowStatus.COMPLETED
