"""Test workflow engine execution with mocked OpenRouter."""

import json
from unittest.mock import AsyncMock

import pytest

from autornd.engine.workflow import WorkflowEngine
from autornd.models.workflow import WorkflowStatus
from autornd.routing.openrouter import OpenRouterClient
from tests.conftest import make_mock_response, seal_double


TRIAGE_RESP = {
    "domains": ["firmware"],
    "risk": "high",
    "specialists": ["firmware_engineer", "test_engineer", "systems_architect"],
    "summary": "Firmware deep sleep redesign",
}

PLAN_RESP = {
    "ready": True,
                     "blockers": [],
    "plan": "Step 1: Refactor sleep state machine. Step 2: Add wake sources.",
    "blockers": [],
    "cost_estimate": None,
    "success_criteria": ["Sleep current < 10uA", "Wake latency < 500ms"],
}

IMPLEMENT_RESP = {
    "done": True,
    "green": True,
    "red_cause": None,
    "iteration": 1,
    # Mentions both success criteria by name. It did not before, and the run
    # still completed, because the exit read the validator alone — a drifted
    # implementation shipping on one judge is exactly what the fold stops.
    "summary": ("Refactored deep sleep FSM with configurable wake sources. "
                "Measured sleep current 8.2uA against the < 10uA target and "
                "wake latency 320ms against the < 500ms target."),
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


DOMAIN_REVIEW_RESP = {
    "concerns": [],
    "critical": False,
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
    if "implementation for the following plan" in msg:  # produce (iter 1) or revise (D33, iter>1)
        return IMPLEMENT_RESP
    if "review this implementation from your domain perspective" in msg:
        return DOMAIN_REVIEW_RESP
    if "validate this implementation" in msg:
        return VALIDATE_RESP
    if "review this engineering work" in msg:
        return REVIEW_RESP
    return REVIEW_RESP


def _make_mock_client():
    client = OpenRouterClient(api_key="test")

    async def _mock_chat_json(function, system_prompt, user_message, **kwargs):
        data = _route_by_content(user_message)
        response = make_mock_response(data, f"mock-{function}")
        # Bill like the real client: spend lives there so nothing can dodge it,
        # and a double that answered free would hide exactly that.
        client._account(function, response.cost)
        return data, response

    client.chat_json = AsyncMock(side_effect=_mock_chat_json)
    seal_double(client)
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
                     "blockers": [],
        "plan": "Refactor MQTT topic structure.",
        "blockers": [],
        "cost_estimate": None,
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
        elif "implementation for the following plan" in msg:  # produce or revise (D33)
            data = {
                "done": True,
                "green": True,
                "red_cause": None,
                "iteration": 1,
                # Addresses the criteria this scenario declares; see the note
                # on IMPLEMENT_RESP above.
                "summary": ("Implemented topic refactor: all topics parse "
                            "correctly, validated on subscribe."),
            }
        elif "review this implementation from your domain perspective" in msg:
            data = {"concerns": [], "critical": False}
        else:
            data = {"ship": True, "findings": [], "verdict": "Ship."}

        response = make_mock_response(data, f"mock-{function}")
        client._account(function, response.cost)
        return data, response

    client.chat_json = AsyncMock(side_effect=_mock_chat_json)
    seal_double(client)
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

    async def test_a_failed_run_reconciles_spend_and_liability(
            self, db_session, monkeypatch):
        """ARCH-20261002-116 (property 9): every terminal path
        reconciles the client's booked spend into the workflow
        record. A run that dies after dispatch — a call
        accounted, a worst case reserved, the request then
        failed — committed BLOCKED with total_cost still at
        its default: the money already spent was erased from
        the record, and the liability the guard held had no
        column to land in at all."""
        from autornd.routing import openrouter as orr

        client = OpenRouterClient(api_key="test")
        client.spend_ceiling = 0.08
        model = client.get_model("engineering")
        # A rate the guard can bound: 5,000 tokens at $0.00001
        # is a $0.05 worst case.
        monkeypatch.setattr(orr, "_model_pricing", {model: (0.0, 1e-5)})

        async def _run_and_die(self, request):
            # Booked: a call that completed and was accounted.
            client._account("triage", 0.002)
            # In flight: a call whose worst case was reserved
            # before dispatch, then failed after it.
            reservation = client._guard_spend(
                "engineering", model, 100, max_tokens=5_000)
            client._fail_call("engineering", model, "error_status",
                              reservation=reservation)
            raise RuntimeError("the run died after dispatch")

        monkeypatch.setattr(
            "autornd.graph.executor.GraphExecutor.run", _run_and_die)

        engine = WorkflowEngine(client, db_session)
        workflow = await engine.execute(
            "Redesign deep sleep state machine for sensor nodes")

        assert workflow.status == WorkflowStatus.BLOCKED
        assert "died after dispatch" in workflow.error
        # The call that completed is booked spend, kept on the
        # record — it was $0.002 the run already paid.
        assert workflow.total_cost == pytest.approx(0.002)
        # The failed call's worst case is liability, not spend:
        # the two are kept apart, and neither is lost.
        assert workflow.unreconciled_liability == pytest.approx(0.05)

    async def test_blocked_plan(self, db_session, monkeypatch):
        client = OpenRouterClient(api_key="test")

        async def _no_lookup(lookup_client, request, question,
                             **kwargs):
            # The one network boundary this test's blocked plan would
            # reach: the gap the blockers name is looked up, and the
            # suite may not reach the provider (ARCH-20261002-112).
            # No answer is the same outcome a failed lookup produces.
            return "", [], "mock"

        monkeypatch.setattr(
            "autornd.knowledge.research._lookup", _no_lookup)

        # The context build also probes the rerank API with this
        # client's own method — another boundary the suite may not
        # reach (ARCH-20261002-112). The refusal is the same
        # capability answer a model without the API gives.
        client.rerank = AsyncMock(
            side_effect=RuntimeError(
                "rerank is not part of the test double"))

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
            "cost_estimate": None,
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
        seal_double(client)
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


@pytest.mark.asyncio
class TestASkippedIndependentCheckRecordsNoShip:
    """(c) Ruling D48 (3): a check that did not run carries no approval-shaped
    value. The skip output records that it was skipped and why, and records NO
    ship; the gate reads the typed veto — false on a skip, true only when the
    check ran and said do not ship — and passes. With the check run and ship
    false, the gate still ends the run blocked with the findings in the reason.

    Driven through GraphExecutor and the real PhaseRunner, and the skip output
    read off `state.outputs` — the skip makes no model call and returns no
    responses, so the output is the record it leaves (convention 28: an empty
    response list writes no phase row, which is why the row cannot be where
    this is asserted)."""

    @staticmethod
    def _probe_client(doublecheck: dict) -> OpenRouterClient:
        client = OpenRouterClient(api_key="test")

        async def _mock(function, system_prompt, user_message, **kwargs):
            msg = user_message.lower()
            if "classify" in msg:
                data = {"domains": ["firmware"], "risk": "high",
                        "specialists": ["firmware_engineer", "test_engineer"],
                        "unrecallable": True, "summary": "Signed rollout"}
            elif function == "independent":
                data = doublecheck
            elif "create an implementation plan" in msg:
                data = PLAN_RESP
            elif "review this implementation plan" in msg:
                data = FEASIBILITY_RESP
            elif "implementation for the following plan" in msg:
                data = IMPLEMENT_RESP
            elif "domain perspective" in msg:
                data = DOMAIN_REVIEW_RESP
            elif "validate this implementation" in msg:
                data = VALIDATE_RESP
            else:
                data = REVIEW_RESP
            response = make_mock_response(data, f"mock-{function}")
            client._account(function, response.cost)
            return data, response

        client.chat_json = AsyncMock(side_effect=_mock)
        seal_double(client)
        client.close = AsyncMock()
        return client

    async def _drive_probe(self, monkeypatch, doublecheck):
        from autornd.evals.runner import _isolated_store
        from autornd.graph.adapter import PhaseRunner
        from autornd.graph.executor import GraphExecutor
        from autornd.graph.spec import load

        client = self._probe_client(doublecheck)
        runner = PhaseRunner(client)
        spec = load("workflows/independent-check-probe.yaml")
        with _isolated_store():
            return await GraphExecutor(
                spec, runner,
                {"max_iterations": 5, "escalation_recovery_attempts": 1,
                 "review_rework_attempts": 1},
            ).run("Roll signed firmware to 40,000 devices")

    async def test_a_skipped_check_records_no_ship_and_the_gate_passes(
            self, monkeypatch):
        from autornd.config import settings

        # The honest condition for a skip: no model distinct from the one
        # under review. premium unset falls back to the architecture tier, so
        # that must land on engineering too — then independent_model() is None
        # and the pass refuses to fake independence.
        monkeypatch.setattr(settings, "model_premium", "")
        monkeypatch.setattr(settings, "model_architecture",
                            "test-provider/test-engineering")
        state = await self._drive_probe(monkeypatch, {})

        assert state.status == "completed", state.reason
        skip = state.outputs["independent_check"]
        assert "ship" not in skip, (
            "a check that did not run recorded a ship value")
        assert skip["skipped"] is True
        assert skip["vetoed"] is False
        assert "no model available" in skip["reason"]
        assert "independent_verdict" in state.path, "the gate ran and passed"

    async def test_a_run_that_vetoes_blocks_with_its_findings(self, monkeypatch):
        from autornd.config import settings

        monkeypatch.setattr(settings, "model_premium", "test/premium-model")
        state = await self._drive_probe(monkeypatch, {
            "ship": False, "confidence": "high",
            "critical_issues": ["R7 value contradicts the schematic"],
            "recommendations": [], "verdict": "Do not ship."})

        assert state.status == "blocked"
        assert "Independent check: do not ship" in state.reason
        assert "R7 value contradicts the schematic" in state.reason
