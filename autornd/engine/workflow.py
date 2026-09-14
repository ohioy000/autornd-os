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

        The sequence used to live in execute_hardcoded below. It now lives in a
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

    async def execute_hardcoded(self, request: str) -> Workflow:
        workflow = Workflow(request=request, status=WorkflowStatus.PENDING)
        self.session.add(workflow)
        await self.session.flush()
        logger.info("Workflow %d created for: %s", workflow.id, request[:80])

        try:
            triage = await self._run_triage(workflow)

            context = await build_phase_context(
                request, triage.domains, triage.specialists, client=self.client
            )

            plan = await self._run_plan(workflow, triage, context)

            if not plan.ready:
                workflow.status = WorkflowStatus.BLOCKED
                workflow.error = (
                    "Plan not ready: " + "; ".join(plan.blockers)
                    if plan.blockers
                    else "Plan not ready (no blockers given)"
                )[:2000]
                await self.session.commit()
                return workflow

            primary_domain = triage.domains[0] if triage.domains else None
            implement, validate, failure_log = await self._run_implement_validate_loop(
                workflow, triage, plan, context,
                primary_domain=primary_domain,
            )

            if implement is None:
                try:
                    escalation = await self._run_escalation(
                        workflow, triage, plan, failure_log, context
                    )
                except Exception as exc:
                    logger.exception("Workflow %d escalation failed", workflow.id)
                    workflow.status = WorkflowStatus.ESCALATED
                    workflow.error = f"Escalation failed — {type(exc).__name__}: {exc}"[:2000]
                    workflow.updated_at = datetime.now(timezone.utc)
                    await self.session.commit()
                    return workflow

                if escalation.requires_human:
                    workflow.status = WorkflowStatus.BLOCKED
                    workflow.error = (
                        "Escalation requires human intervention: "
                        + escalation.root_cause_analysis
                    )[:2000]
                    await self.session.commit()
                    return workflow

                implement, validate, _ = await self._run_implement_validate_loop(
                    workflow, triage, plan, context,
                    max_attempts=settings.escalation_recovery_attempts,
                    resolution_directive=escalation.resolution_directive,
                    primary_domain=primary_domain,
                )

                if implement is None:
                    workflow.status = WorkflowStatus.ESCALATED
                    await self.session.commit()
                    return workflow

            review = await self._run_review(workflow, triage, plan, implement, context)

            workflow.status = WorkflowStatus.COMPLETED
            workflow.updated_at = datetime.now(timezone.utc)
            await self.session.commit()

            await self._save_episodic_memory(workflow, triage, plan, implement, review)

            return workflow

        except Exception as exc:
            logger.exception("Workflow %d failed", workflow.id)
            workflow.status = WorkflowStatus.BLOCKED
            workflow.error = f"{type(exc).__name__}: {exc}"[:2000]
            workflow.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            return workflow

    async def _run_triage(self, workflow: Workflow) -> TriageVerdict:
        workflow.status = WorkflowStatus.TRIAGE
        await self.session.flush()

        verdict, response = await run_triage(self.client, workflow.request)
        self._enforce_triage_composition(verdict)

        workflow.risk_level = verdict.risk.value
        await self._save_phase(workflow, "triage", verdict.model_dump(), response)
        return verdict

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

    async def _run_implement_validate_loop(
        self,
        workflow: Workflow,
        triage: TriageVerdict,
        plan: PlanVerdict,
        context: str = "",
        max_attempts: int | None = None,
        resolution_directive: str | None = None,
        primary_domain: "Domain | None" = None,
    ) -> tuple[ImplementVerdict | None, ValidateVerdict | None, list[dict]]:
        if max_attempts is None:
            max_attempts = settings.max_iterations

        specialists = get_specialists(
            [s for s in triage.specialists if s != "test_engineer"]
        )
        if not specialists:
            specialists = get_specialists(triage.specialists)

        red_cause: str | None = None
        implement_verdict: ImplementVerdict | None = None
        validate_verdict: ValidateVerdict | None = None
        failure_log: list[dict] = []

        for iteration in range(1, max_attempts + 1):
            workflow.status = WorkflowStatus.IMPLEMENT
            workflow.iteration = iteration
            await self.session.flush()

            implement_verdict, impl_responses = await run_implement(
                self.client,
                workflow.request,
                plan,
                specialists,
                iteration,
                red_cause,
                resolution_directive=resolution_directive,
                context=context,
                primary_domain=primary_domain,
            )
            for resp in impl_responses:
                await self._save_phase(
                    workflow, "implement", implement_verdict.model_dump(), resp, iteration
                )

            workflow.status = WorkflowStatus.VALIDATE
            await self.session.flush()

            validate_verdict, val_response = await run_validate(
                self.client, workflow.request, plan, implement_verdict,
                context=context, domains=triage.domains,
            )
            await self._save_phase(
                workflow, "validate", validate_verdict.model_dump(), val_response, iteration
            )

            if validate_verdict.green:
                logger.info(
                    "Workflow %d passed validation on iteration %d",
                    workflow.id,
                    iteration,
                )
                return implement_verdict, validate_verdict, failure_log

            red_cause = validate_verdict.red_cause
            failure_log.append({
                "iteration": iteration,
                "implement_summary": implement_verdict.summary,
                "validate_red_cause": validate_verdict.red_cause,
                "validate_evidence": validate_verdict.evidence,
            })
            logger.warning(
                "Workflow %d failed validation iteration %d: %s",
                workflow.id,
                iteration,
                red_cause,
            )

        logger.error(
            "Workflow %d exhausted %d iterations — escalating",
            workflow.id,
            max_attempts,
        )
        return None, None, failure_log

    async def _run_escalation(
        self,
        workflow: Workflow,
        triage: TriageVerdict,
        plan: PlanVerdict,
        failure_log: list[dict],
        context: str = "",
    ) -> EscalationVerdict:
        logger.info("Workflow %d — routing escalation autopsy to K3", workflow.id)
        verdict, response = await run_escalation_autopsy(
            self.client, workflow.request, plan, triage, failure_log, context=context,
        )
        await self._save_phase(workflow, "escalation", verdict.model_dump(), response)

        if verdict.requires_human:
            logger.warning(
                "Workflow %d — K3 says requires_human, blocking", workflow.id,
            )
        else:
            logger.info(
                "Workflow %d — K3 recovery directive issued, retrying with %d attempts",
                workflow.id, settings.escalation_recovery_attempts,
            )
        return verdict

    async def _run_review(
        self,
        workflow: Workflow,
        triage: TriageVerdict,
        plan: PlanVerdict,
        implement: ImplementVerdict,
        context: str = "",
    ) -> ReviewVerdict:
        workflow.status = WorkflowStatus.REVIEW
        await self.session.flush()

        review_roles = get_review_team(
            triage.risk, triage.domains, triage.specialists)
        specialists = get_specialists(review_roles)
        verdict, responses = await run_review(
            self.client, workflow.request, triage, plan, implement, specialists,
            context=context,
        )
        total_cost = sum(r.cost for r in responses)
        models_used = ", ".join(dict.fromkeys(r.model for r in responses))
        combined = ModelResponse(
            content="", model=models_used,
            prompt_tokens=sum(r.prompt_tokens for r in responses),
            completion_tokens=sum(r.completion_tokens for r in responses),
            cost=total_cost,
        )
        await self._save_phase(workflow, "review", verdict.model_dump(), combined)

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
