"""Workflow sequencer — drives requests through all 5 phases with iteration loop."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from autornd.config import settings
from autornd.engine.phases import (
    run_escalation_autopsy, run_implement, run_plan,
    run_plan_feasibility, run_review, run_triage, run_validate,
)
from autornd.engine.review_composition import get_review_team
from autornd.knowledge.context import build_phase_context
from autornd.models.verdicts import (
    domain_key,
    Domain, EscalationVerdict, ImplementVerdict, PlanVerdict,
    ReviewVerdict, RiskLevel, SpecialistRole, TriageVerdict, ValidateVerdict,
)
from autornd.models.workflow import PhaseResult, Workflow, WorkflowStatus
from autornd.routing.openrouter import ModelResponse, OpenRouterClient
from autornd.specialists.registry import get_specialists

logger = logging.getLogger(__name__)


def workflow_path() -> str:
    """The graph to run. A name resolves inside workflows/; a path is used as-is."""
    from pathlib import Path

    configured = settings.autornd_workflow or "engineering-rnd"
    candidate = Path(configured)
    if candidate.suffix and candidate.exists():
        return str(candidate)
    root = Path(__file__).resolve().parent.parent.parent / "workflows"
    return str(root / f"{candidate.stem}.yaml")


class WorkflowEngine:
    def __init__(self, client: OpenRouterClient, session: AsyncSession):
        self.client = client
        self.session = session

    # Which node maps to which visible status while a run is in flight. The
    # dashboard and the API poll this, so it has to keep moving.
    _NODE_STATUS = {
        "triage": WorkflowStatus.TRIAGE,
        "plan": WorkflowStatus.PLAN,
        "feasibility": WorkflowStatus.PLAN,
        "implement": WorkflowStatus.IMPLEMENT,
        "domain_review": WorkflowStatus.IMPLEMENT,
        "validate": WorkflowStatus.VALIDATE,
        "review": WorkflowStatus.REVIEW,
    }

    async def execute(self, request: str) -> Workflow:
        """Run the configured workflow graph.

        The sequence used to live in a hardcoded method here. It now lives in a
        YAML file, which is what makes the shape of a workflow something you can
        change and measure rather than something only the code knows. That file
        is proven to reproduce the old behaviour call-for-call — see
        tests/test_graph_equivalence.py — and the old sequencer is kept beside
        it as the reference those tests compare against.
        """
        from autornd.graph.adapter import PhaseRunner
        from autornd.graph.executor import GraphExecutor
        from autornd.graph.spec import load as load_spec

        workflow = Workflow(request=request, status=WorkflowStatus.PENDING)
        self.session.add(workflow)
        await self.session.flush()
        logger.info("Workflow %d created for: %s", workflow.id, request[:80])

        pending_saves: list[tuple] = []

        def on_phase(node_id, verdict, responses, iteration):
            # Collected synchronously, written after the run — the executor is
            # not async-aware about our session and should not be.
            pending_saves.append((node_id, verdict, responses, iteration))

        runner = PhaseRunner(self.client, on_phase=on_phase)
        spec = load_spec(workflow_path())
        executor = GraphExecutor(spec, runner, settings_lookup={
            "max_iterations": settings.max_iterations,
            "escalation_recovery_attempts": settings.escalation_recovery_attempts,
            "escalation_max_tokens": settings.escalation_max_tokens,
        })

        try:
            state = await executor.run(request)
        except Exception as exc:
            logger.exception("Workflow %d failed", workflow.id)
            await self._flush_phases(workflow, pending_saves)
            workflow.status = WorkflowStatus.BLOCKED
            workflow.error = f"{type(exc).__name__}: {exc}"[:2000]
            workflow.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            return workflow

        await self._flush_phases(workflow, pending_saves)

        triage = state.outputs.get("triage")
        if triage is not None:
            workflow.risk_level = triage.risk.value
        loop = state.outputs.get("build_loop") or {}
        workflow.iteration = loop.get("iterations", 0)
        workflow.status = WorkflowStatus(state.status)
        workflow.error = state.reason if state.status != "completed" else None
        workflow.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

        if workflow.status is WorkflowStatus.COMPLETED:
            review = state.outputs.get("review")
            implement = state.outputs.get("implement")
            plan = state.outputs.get("plan")
            if triage and plan and implement and review:
                await self._save_episodic_memory(
                    workflow, triage, plan, implement, review)

        return workflow

    async def _flush_phases(self, workflow: Workflow, saves: list[tuple]) -> None:
        for node_id, verdict, responses, iteration in saves:
            data = verdict.model_dump() if hasattr(verdict, "model_dump") else dict(verdict)
            for response in responses:
                await self._save_phase(
                    workflow, node_id, data, response, max(iteration, 1))
    @staticmethod
    def _enforce_triage_composition(verdict: TriageVerdict) -> None:
        """Enforce doc-specified rules the LLM might omit."""
        if verdict.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            if SpecialistRole.TEST_ENGINEER not in verdict.specialists:
                verdict.specialists.append(SpecialistRole.TEST_ENGINEER)
        if len(verdict.domains) > 1:
            if SpecialistRole.SYSTEMS_ARCHITECT not in verdict.specialists:
                verdict.specialists.append(SpecialistRole.SYSTEMS_ARCHITECT)

    async def _run_plan(
        self, workflow: Workflow, triage: TriageVerdict, context: str = ""
    ) -> PlanVerdict:
        workflow.status = WorkflowStatus.PLAN
        await self.session.flush()

        specialists = get_specialists(triage.specialists)
        verdict, response = await run_plan(
            self.client, workflow.request, triage, specialists, context=context
        )
        await self._save_phase(workflow, "plan", verdict.model_dump(), response)

        if verdict.ready:
            feasibility_responses = await run_plan_feasibility(
                self.client, workflow.request, triage, verdict, specialists,
                context=context,
            )
            for resp in feasibility_responses:
                await self._save_phase(workflow, "plan_feasibility", verdict.model_dump(), resp)

        return verdict
    async def _save_phase(
        self,
        workflow: Workflow,
        phase: str,
        verdict_data: dict,
        response: ModelResponse,
        iteration: int = 1,
    ):
        phase_result = PhaseResult(
            workflow_id=workflow.id,
            phase=phase,
            iteration=iteration,
            verdict_json=json.dumps(verdict_data),
            model_used=response.model,
            cost=response.cost,
        )
        self.session.add(phase_result)
        # Read the client's own total rather than summing phase responses: the
        # engine shares its client with the phase runner and with context
        # building, so research lookups and reranking are in that figure and
        # were missing from this one. Assigning is idempotent — it converges on
        # the true total however many phases are recorded.
        workflow.total_cost = self.client.spend
        workflow.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def _save_episodic_memory(
        self,
        workflow: Workflow,
        triage: TriageVerdict,
        plan: PlanVerdict,
        implement: ImplementVerdict,
        review: ReviewVerdict,
    ):
        """Save workflow outcome to episodic memory for future reference."""
        from autornd.knowledge.episodic import save_episode

        try:
            await save_episode(
                self.session,
                workflow_id=workflow.id,
                request=workflow.request,
                domains=[domain_key(d) for d in triage.domains],
                risk=triage.risk.value,
                iterations=workflow.iteration,
                shipped=review.ship,
                verdict=review.verdict,
                findings_count=len(review.findings),
                total_cost=workflow.total_cost,
            )
        except Exception:
            logger.warning("Failed to save episodic memory for workflow %d", workflow.id)
