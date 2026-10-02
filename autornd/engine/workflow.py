"""Workflow sequencer — drives requests through all 5 phases with iteration loop."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from autornd.config import settings, settings_lookup
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

# Statuses that end a run. A progress write advances the row's visible status
# as nodes complete; it must never move a row that has already ended.
_TERMINAL = (
    WorkflowStatus.COMPLETED,
    WorkflowStatus.BLOCKED,
    WorkflowStatus.ESCALATED,
)


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

    async def execute(
        self,
        request: str,
        workflow: Workflow | None = None,
        user_id: int | None = None,
    ) -> Workflow:
        """Run the configured workflow graph.

        The sequence used to live in a hardcoded method here. It now lives in a
        YAML file, which is what makes the shape of a workflow something you can
        change and measure rather than something only the code knows. That file
        is proven to reproduce the old behaviour call-for-call — see
        tests/test_graph_equivalence.py — and the old sequencer is kept beside
        it as the reference those tests compare against.

        One row per submission: the API paths create the caller's row and pass
        it in, so the id the caller polls is the id the run writes. Passing no
        row keeps working — the row is created here, with `user_id` when one is
        known (ARCH-20261002-109).
        """
        import asyncio

        from autornd.graph.adapter import PhaseRunner
        from autornd.graph.executor import GraphExecutor
        from autornd.graph.spec import load as load_spec

        if workflow is None:
            workflow = Workflow(
                request=request, status=WorkflowStatus.PENDING, user_id=user_id
            )
            self.session.add(workflow)
        # Committed before the run starts: a poll sees the submission at once,
        # and a crash mid-run keeps every node completed before it.
        await self.session.commit()
        logger.info("Workflow %d running: %s", workflow.id, request[:80])

        # Each completed node is written in a transaction of its own, from a
        # chain of tasks the synchronous on_phase callback schedules. The
        # executor is not async-aware about our session and should not be; the
        # chain keeps one writer at a time, in node order, so a poll sees
        # progress and a crash keeps what was paid for. The `written` flag is
        # what stops the end-of-run flush writing any phase twice.
        pending_saves: list[dict] = []
        chain: list = [None]

        def on_phase(node_id, verdict, responses, iteration):
            item = {
                "node_id": node_id,
                "verdict": verdict,
                "responses": responses,
                "iteration": iteration,
                "written": False,
            }
            pending_saves.append(item)
            previous = chain[0]

            async def _write_in_order():
                if previous is not None:
                    await previous
                await self._write_progress(workflow, item)

            chain[0] = asyncio.create_task(_write_in_order())

        runner = PhaseRunner(self.client, on_phase=on_phase)
        spec = load_spec(workflow_path())
        # Ruling D38: the API path gets the watchdog through the same executor
        # the eval runner uses. Unset (the default) means no budget, and the
        # run behaves as it did before. A watchdog end is the workflow's own
        # terminal: it lands below as status blocked with the reason in
        # `error`, the existing fields. No DB schema change (hard rule 11).
        # Ruling D39: loop bounds come from the one shared map. This path kept
        # its own copy, which lacked the rework bound, so any blocking review
        # here crashed with a ConditionError instead of reaching rework.
        executor = GraphExecutor(spec, runner, settings_lookup=settings_lookup(),
                                 time_budget=settings.run_time_budget_seconds)

        try:
            state = await executor.run(request)
            # Drain the progress writers first: the node writes are what
            # advance the row's status while the run is in flight, and none of
            # them may land after the terminal below.
            await self._flush_phases(workflow, pending_saves, chain)
            triage = state.outputs.get("triage")
            if triage is not None:
                workflow.risk_level = triage.risk.value
            loop = state.outputs.get("build_loop") or {}
            workflow.iteration = loop.get("iterations", 0)
            # Inside the guarded region: a terminal string that is not a
            # member raises here, and lands as the row's BLOCKED with the raw
            # terminal in `error`, committed — the result is kept
            # (ARCH-20261002-109).
            workflow.status = WorkflowStatus(state.status)
            workflow.error = state.reason if state.status != "completed" else None
        except Exception as exc:
            logger.exception("Workflow %d failed", workflow.id)
            await self._flush_phases(workflow, pending_saves, chain)
            workflow.status = WorkflowStatus.BLOCKED
            workflow.error = f"{type(exc).__name__}: {exc}"[:2000]
            workflow.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            return workflow

        await self._flush_phases(workflow, pending_saves, chain)
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

    async def _flush_phases(
        self, workflow: Workflow, saves: list[dict], chain: list | None = None
    ) -> None:
        """Wait for the progress writers, then write whatever they did not.

        The `written` flag is what keeps a phase from being recorded twice:
        a node's record is written once, by the writer that got there first.
        """
        if chain and chain[0] is not None:
            await chain[0]
        for item in saves:
            await self._write_progress(workflow, item)

    async def _write_progress(self, workflow: Workflow, item: dict) -> None:
        if item["written"]:
            return
        try:
            data = (
                item["verdict"].model_dump()
                if hasattr(item["verdict"], "model_dump")
                else dict(item["verdict"])
            )
            for response in item["responses"]:
                await self._save_phase(
                    workflow, item["node_id"], data, response,
                    max(item["iteration"], 1),
                )
            # The row's visible status moves with the node that just finished —
            # but never over a terminal: a retried write landing after the run
            # ended must not repaint `completed` with `review`.
            status = self._NODE_STATUS.get(item["node_id"])
            if status is not None and workflow.status not in _TERMINAL:
                workflow.status = status
            # One transaction of its own: a poll sees this node before the
            # next one starts, and a crash keeps it.
            await self.session.commit()
            item["written"] = True
        except Exception:
            # Kept out of the run's way and out of silence both: the run's
            # result survives, and the record says which node was lost.
            logger.exception(
                "Progress write failed for node %s on workflow %d",
                item["node_id"], workflow.id,
            )

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
