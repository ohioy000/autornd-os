"""Test workflow state machine and ORM models."""

import pytest
import pytest_asyncio

from autornd.models.workflow import PhaseResult, Workflow, WorkflowStatus


@pytest.mark.asyncio
class TestWorkflowModel:
    async def test_create_workflow(self, db_session):
        w = Workflow(request="Add temperature sensor node type")
        db_session.add(w)
        await db_session.flush()

        assert w.id is not None
        assert w.status == WorkflowStatus.PENDING
        assert w.iteration == 0
        assert w.total_cost == 0.0

    async def test_status_transitions(self, db_session):
        w = Workflow(request="Test request")
        db_session.add(w)
        await db_session.flush()

        for status in [
            WorkflowStatus.TRIAGE,
            WorkflowStatus.PLAN,
            WorkflowStatus.IMPLEMENT,
            WorkflowStatus.VALIDATE,
            WorkflowStatus.REVIEW,
            WorkflowStatus.COMPLETED,
        ]:
            w.status = status
            await db_session.flush()
            assert w.status == status

    async def test_phase_result_relationship(self, db_session):
        w = Workflow(request="Test request")
        db_session.add(w)
        await db_session.flush()

        phase = PhaseResult(
            workflow_id=w.id,
            phase="triage",
            verdict_json='{"domains": ["firmware"], "risk": "high"}',
            model_used="test-model",
            cost=0.01,
        )
        db_session.add(phase)
        await db_session.flush()

        assert phase.id is not None
        assert phase.workflow_id == w.id

    async def test_cost_accumulation(self, db_session):
        w = Workflow(request="Test cost tracking")
        db_session.add(w)
        await db_session.flush()

        w.total_cost += 0.15
        w.total_cost += 0.40
        w.total_cost += 0.10
        await db_session.flush()

        assert abs(w.total_cost - 0.65) < 0.001
