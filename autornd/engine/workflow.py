"""Workflow sequencer — drives requests through all 5 phases with iteration loop."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from autornd.config import RENAMED_WORKFLOWS, settings, settings_lookup
from autornd.engine.phases import (
    run_escalation_autopsy, run_implement, run_plan,
    run_plan_feasibility, run_review, run_triage, run_validate,
)
from autornd.engine.review_composition import get_review_team
from autornd.graph.spec import WorkflowSpec
from autornd.knowledge.context import build_phase_context
from autornd.models.verdicts import (
    domain_key,
    Domain, EscalationVerdict, ImplementVerdict, PlanVerdict,
    ReviewVerdict, TriageVerdict, ValidateVerdict,
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


# The shipped workflow files, found from the package and not from the working
# directory. That is why the Dockerfile installs editable (CLAUDE.md).
WORKFLOWS_DIR = Path(__file__).resolve().parent.parent.parent / "workflows"


class WorkflowNotOffered(ValueError):
    """A request named a workflow it may not name (Ruling D55 (3))."""


def workflow_path() -> str:
    """The configured graph. A name resolves inside workflows/; a path is used as-is."""
    configured = settings.autornd_workflow or "full-team"
    candidate = Path(configured)
    if candidate.suffix and candidate.exists():
        return str(candidate)
    return str(WORKFLOWS_DIR / f"{candidate.stem}.yaml")


def offered_workflows() -> dict[str, WorkflowSpec]:
    """The workflows a request may name (Ruling D55 (2)), by file stem.

    Every file in workflows/ that loads and declares `offered: true`. A file
    that does not load is not offered, and the reason is logged.
    """
    from autornd.graph.spec import load as load_spec

    offered: dict[str, WorkflowSpec] = {}
    for path in sorted(WORKFLOWS_DIR.glob("*.yaml")):
        try:
            spec = load_spec(path)
        except ValueError as exc:
            logger.warning("workflow %s does not load, so it is not offered: %s",
                           path.name, exc)
            continue
        if spec.offered:
            offered[path.stem] = spec
    return offered


def requested_workflow(name: str) -> str:
    """The file of the offered workflow a request names.

    A name, never a path (Ruling D55 (3)). `name` is looked up as a key, so
    a path, an instrument, an unknown name and a file that does not load are
    all refused alike: WorkflowNotOffered, with a sentence that lists the
    offered names. An old name is refused with its new one; there is no alias.
    """
    offered = offered_workflows()
    if name in offered:
        return str(WORKFLOWS_DIR / f"{name}.yaml")
    choices = ", ".join(offered)
    renamed = RENAMED_WORKFLOWS.get(name)
    if renamed:
        raise WorkflowNotOffered(
            f"The workflow '{name}' is now named '{renamed}'. A request can "
            f"name one of: {choices}.")
    raise WorkflowNotOffered(
        f"No workflow a request can name is called '{name}'. A request can "
        f"name one of: {choices}.")


class WorkflowEngine:
    def __init__(self, client: OpenRouterClient, session: AsyncSession):
        self.client = client
        self.session = session
        # Ruling D48: progress writes lost at the database, named in the run's
        # record rather than left silent. Per-run, never shared.
        self._lost_progress: list[str] = []

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
        workflow_file: str | None = None,
    ) -> Workflow:
        """Run the configured workflow graph, or the one a request named.

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

        `workflow_file` is the file of an offered workflow the request named,
        which the API has already checked (Ruling D55). None runs the
        configured default.
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
        path = workflow_file or workflow_path()
        spec = load_spec(path)
        # Ruling D55 (5): which workflow ran, recorded before anything else,
        # through the phase channel on a zero-cost response, as the recompute
        # vote's record is. No DB schema change.
        on_phase("workflow",
                 {"name": spec.name,
                  "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()},
                 [ModelResponse(content="", model="", prompt_tokens=0,
                                completion_tokens=0, cost=0.0)],
                 0)
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
            # Ruling D57 (3): the unendorsed candidate reaches the caller.
            # The executor keeps it at every terminal that is not completed
            # once an implementation exists (D51 (7)); this path dropped
            # it, so an API caller saw the status and never the answer.
            # It goes through the phase channel on a zero-cost response,
            # as the workflow record does, with D38's pointer to the last
            # answer the build judges agreed on, and that answer when it
            # is not the last one. No DB schema change.
            if state.candidate is not None:
                approved = (state.watchdog.approved
                            if state.watchdog is not None else None)
                record = {**state.candidate, "approved": approved}
                if approved and approved.get("latest_differs"):
                    record["approved_answer"] = (
                        runner.iterations[approved["index"]]
                        ["implement_summary"])
                on_phase("candidate", record,
                         [ModelResponse(content="", model="", prompt_tokens=0,
                                        completion_tokens=0, cost=0.0)],
                         0)
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
            # The lost-progress note rides on the error even when the run
            # completed: a record that silently misses what it lost is the
            # defect D48 names (convention 28).
            _base = state.reason if state.status != "completed" else None
            workflow.error = "; ".join(
                p for p in (_base, self._lost_note()) if p) or None
        except Exception as exc:
            logger.exception("Workflow %d failed", workflow.id)
            await self._flush_phases(workflow, pending_saves, chain)
            # The failed terminal reconciles the same figures. A
            # call can be accounted and its phase write never
            # happen — a handler that raised after its request
            # was made, a retry sequence that exhausted — and
            # without this the row committed BLOCKED with the
            # spend already made erased from it.
            workflow.total_cost = self.client.spend
            workflow.unreconciled_liability = (
                self.client.unreconciled_liability)
            workflow.status = WorkflowStatus.BLOCKED
            workflow.error = "; ".join(
                p for p in (f"{type(exc).__name__}: {exc}",
                            self._lost_note()) if p)[:2000]
            workflow.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            return workflow

        await self._flush_phases(workflow, pending_saves, chain)
        # The terminal reconciles the client's own accounting
        # into the record, deliberately: a phase write sets
        # total_cost as a side effect, but only for calls whose
        # phase got written, and the figures at the terminal are
        # the run's final ones. Booked spend and the outstanding
        # liability of failed-after-dispatch calls are recorded
        # apart — one is what the run was charged, the other is
        # what it may still owe.
        workflow.total_cost = self.client.spend
        workflow.unreconciled_liability = self.client.unreconciled_liability
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
        # Read while the instance is live: after a rollback it is expired, and
        # the handler below must read nothing from it (Ruling D48).
        workflow_id = workflow.id
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
            # Ruling D48: one failed progress write loses that node's record
            # and nothing else. The session is rolled back — a failed commit
            # leaves it unusable and the terminal at the end of the run would
            # fail with it — the row is re-read so the run keeps everything it
            # still needs, and the loss is NAMED in the run's record rather
            # than left silent (convention 28). The item is consumed: the
            # drain never retries a write that failed at the database and
            # never re-raises it.
            logger.exception(
                "Progress write failed for node %s on workflow %s — the "
                "node's record is lost, the run continues",
                item["node_id"], workflow_id,
            )
            self._lost_progress.append(str(item["node_id"]))
            item["written"] = True
            try:
                await self.session.rollback()
                await self.session.refresh(workflow)
            except Exception:
                logger.exception(
                    "Rollback after a failed progress write also failed "
                    "for workflow %s", workflow_id)

    def _lost_note(self) -> str:
        if not self._lost_progress:
            return ""
        return ("progress write lost for: "
                + ", ".join(self._lost_progress)
                + " (that node's phase record was not saved)")

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
