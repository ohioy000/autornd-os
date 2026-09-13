"""The graph must do what the hardcoded engine did.

`WorkflowEngine.execute()` now runs the graph. `execute_hardcoded()` is the
original sequencer, kept as the reference these tests measure against — delete
it and this file stops proving anything.

This is the load-bearing test of the whole graph effort. `engineering-rnd.yaml`
is only a useful baseline if running it produces the same calls, in the same
order, at the same cost as the pipeline it describes. Once that holds, a variant
workflow is a file you can measure against a known quantity — and without it,
the graph is just a second implementation with its own bugs.

Both sides run against the same mocked client, so any difference is a
difference in sequencing rather than in what the models happened to say.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from autornd.database import Base
from autornd.engine.workflow import WorkflowEngine
from autornd.graph.adapter import PhaseRunner
from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import load
from autornd.routing.openrouter import ModelResponse, OpenRouterClient

import autornd.knowledge.episodic  # noqa: F401 — register Episode
import autornd.models.user  # noqa: F401 — register User


TRIAGE = {
    "domains": ["backend"], "risk": "medium",
    "specialists": ["backend_engineer", "test_engineer"],
    "summary": "reconnection retry work",
}
PLAN = {
    "ready": True, "plan": "Cap backoff at 60s with jitter.", "blockers": [],
    "cost_estimate": None,
    "success_criteria": [
        "Reconnect loop applies exponential backoff capped at 60s",
        "Jitter is applied to every retry attempt",
    ],
}
IMPL = {
    "done": True, "green": True, "red_cause": None, "iteration": 1,
    "summary": ("Applied exponential backoff to the reconnect loop capped at 60s "
                "with jitter on every retry attempt."),
}
SETTINGS = {"max_iterations": 5, "escalation_recovery_attempts": 3}


class Script:
    """One scripted set of model replies, shared by both runners."""

    def __init__(self, plan=None, validate=None, escalation=None):
        self.plan = plan or PLAN
        self.validate = validate or {"green": True, "red_cause": None, "evidence": ["ok"]}
        self.escalation = escalation or {
            "root_cause_analysis": "criteria drift",
            "architectural_correction": None,
            "resolution_directive": "re-read the criteria",
            "requires_human": False,
        }
        self.validate_calls = 0

    def reply(self, message: str) -> dict:
        m = message.lower()
        if "classify this engineering request" in m:
            return TRIAGE
        if "create an implementation plan" in m:
            return self.plan
        if "review this implementation plan" in m or "plan produced by" in m:
            return {"feasible": True, "concerns": [], "blockers": []}
        if "attempts all failed validation" in m:
            return self.escalation
        if "produce the implementation for the following plan" in m:
            return IMPL
        if "review this implementation from your domain perspective" in m:
            return {"concerns": [], "critical": False}
        if "validate this implementation" in m:
            self.validate_calls += 1
            return self.validate(self.validate_calls) if callable(self.validate) \
                else self.validate
        return {"ship": True, "findings": [], "verdict": "Ship."}


def make_client(script: Script, log: list[str]) -> OpenRouterClient:
    client = OpenRouterClient(api_key="test")

    async def chat_json(function, system_prompt, user_message, **kw):
        data = script.reply(user_message)
        log.append(function)
        return data, ModelResponse(
            content=json.dumps(data), model=f"mock-{function}",
            prompt_tokens=10, completion_tokens=5, cost=0.001,
        )

    client.chat_json = AsyncMock(side_effect=chat_json)
    client.close = AsyncMock()
    return client


async def run_graph(script_factory, request="Add retry"):
    log: list[str] = []
    runner = PhaseRunner(make_client(script_factory(), log))
    state = await GraphExecutor(
        load("workflows/engineering-rnd.yaml"), runner, SETTINGS
    ).run(request)
    return state.status, log, round(runner.total_cost, 6)


async def run_engine(script_factory, request="Add retry"):
    log: list[str] = []
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        # execute() now drives the graph, so the reference has to be the
        # original hardcoded sequencer — otherwise this compares the graph
        # against itself and proves nothing.
        workflow = await WorkflowEngine(
            make_client(script_factory(), log), session
        ).execute_hardcoded(request)
        result = workflow.status.value, log, round(workflow.total_cost, 6)
    await engine.dispose()
    return result


@pytest.mark.asyncio
class TestGraphMatchesEngine:
    async def test_happy_path(self):
        graph = await run_graph(Script)
        engine = await run_engine(Script)
        assert graph == engine, f"\ngraph : {graph}\nengine: {engine}"

    async def test_blocked_plan(self):
        def script():
            return Script(plan={
                "ready": False, "plan": "cannot proceed",
                "blockers": ["missing datasheet"], "cost_estimate": None,
                "success_criteria": []})

        graph_status, graph_log, _ = await run_graph(script)
        engine_status, engine_log, _ = await run_engine(script)
        assert graph_status == engine_status == "blocked"
        assert graph_log == engine_log

    async def test_loop_converging_late(self):
        def script():
            return Script(validate=lambda n: {
                "green": n >= 3, "red_cause": None if n >= 3 else "not yet",
                "evidence": ["x"]})

        graph = await run_graph(script)
        engine = await run_engine(script)
        assert graph == engine, f"\ngraph : {graph}\nengine: {engine}"

    async def test_exhausted_loop_escalates_and_recovers(self):
        """The expensive path has to match too — it is where the cost is."""
        def script():
            return Script(validate=lambda n: {
                "green": n > 5, "red_cause": None if n > 5 else "still red",
                "evidence": ["x"]})

        graph = await run_graph(script)
        engine = await run_engine(script)
        assert graph == engine, f"\ngraph : {graph}\nengine: {engine}"

    async def test_escalation_requiring_a_human(self):
        def script():
            return Script(
                validate=lambda n: {"green": False, "red_cause": "red", "evidence": []},
                escalation={"root_cause_analysis": "needs a bench",
                            "architectural_correction": None,
                            "resolution_directive": "get hardware",
                            "requires_human": True})

        graph_status, graph_log, _ = await run_graph(script)
        engine_status, engine_log, _ = await run_engine(script)
        assert graph_status == engine_status
        assert graph_log == engine_log


@pytest.mark.asyncio
class TestAdapterWiring:
    async def test_the_validator_never_builds_or_reviews_the_build(self):
        """A rule that used to be an unexplained line in the engine, and is now
        visible in the workflow file as the `builders` and `peers` rosters."""
        from autornd.graph.executor import ExecutionState
        from autornd.graph.spec import Node, NodeKind
        from autornd.models.verdicts import SpecialistRole, TriageVerdict

        runner = PhaseRunner(make_client(Script(), []))
        state = ExecutionState(request="r", outputs={"triage": TriageVerdict(**TRIAGE)})

        builders = runner._resolve_who(
            Node(id="i", kind=NodeKind.AI, specialist="builders"), state)
        assert SpecialistRole.TEST_ENGINEER not in [s.role for s in builders]

        everyone = runner._resolve_who(
            Node(id="f", kind=NodeKind.AI, specialist="assigned"), state)
        assert SpecialistRole.TEST_ENGINEER in [s.role for s in everyone]

    async def test_a_node_naming_an_unknown_prompt_says_what_exists(self):
        from autornd.graph.executor import ExecutionState
        from autornd.graph.spec import Node, NodeKind
        from autornd.graph.adapter import UnknownPromptError

        runner = PhaseRunner(make_client(Script(), []))
        node = Node(id="x", kind=NodeKind.AI, tier="engineering", prompt="invent")
        with pytest.raises(UnknownPromptError, match="Known:"):
            await runner.run_ai(node, ExecutionState(request="r"))

    async def test_context_is_built_once_and_reused(self):
        log: list[str] = []
        runner = PhaseRunner(make_client(Script(), log))
        state = await GraphExecutor(
            load("workflows/engineering-rnd.yaml"), runner, SETTINGS
        ).run("Add retry")
        assert state.outputs["context"]["passed"] is True
        assert "chars" in state.outputs["context"]


@pytest.mark.asyncio
class TestVariantWorkflows:
    """The payoff: comparing two shapes costs nothing and takes no time.

    Answering "is the full team worth it for this kind of request" used to mean
    running real workflows against real models. It is now a diff between two
    files, measured with mocks.
    """

    async def test_lean_is_cheaper_on_the_happy_path(self):
        full = await run_graph(Script)
        lean_log: list[str] = []
        lean_runner = PhaseRunner(make_client(Script(), lean_log))
        await GraphExecutor(load("workflows/lean.yaml"), lean_runner, SETTINGS).run("Add retry")

        assert len(lean_log) < len(full[1])
        assert lean_runner.total_cost < full[2]

    async def test_lean_is_cheaper_when_nothing_converges(self):
        """The expensive path is the one worth comparing."""
        def script():
            return Script(validate=lambda n: {
                "green": False, "red_cause": "red", "evidence": []})

        _, full_log, full_cost = await run_graph(script)
        lean_log: list[str] = []
        lean_runner = PhaseRunner(make_client(script(), lean_log))
        state = await GraphExecutor(
            load("workflows/lean.yaml"), lean_runner, SETTINGS).run("Add retry")

        assert state.status == "escalated"
        assert len(lean_log) < len(full_log)

    async def test_lean_still_checks_its_work(self):
        """Cheaper must not mean unchecked — the free coverage check stays."""
        spec = load("workflows/lean.yaml")
        body = spec.get("build_loop").body
        assert "coverage" in body
        assert body.index("coverage") < body.index("validate")

    async def test_both_shipped_workflows_load(self):
        for name in ("engineering-rnd", "lean"):
            assert load(f"workflows/{name}.yaml").name == name


@pytest.mark.asyncio
class TestTriageCompositionSurvivesTheGraph:
    """Regression: moving the engine to the graph silently dropped the rule that
    risky work gets a test engineer and multi-domain work gets an architect. The
    equivalence tests missed it because their mock already returned the right
    roster, so enforcement was a no-op — it took five live runs to notice.
    """

    @staticmethod
    def _client(risk, specialists):
        def reply(message: str) -> dict:
            if "classify this engineering request" in message.lower():
                return {"domains": ["hardware", "firmware"], "risk": risk,
                        "specialists": specialists, "summary": "s"}
            return Script().reply(message)
        client = OpenRouterClient(api_key="test")

        async def chat_json(function, system_prompt, user_message, **kw):
            data = reply(user_message)
            return data, ModelResponse(content=json.dumps(data), model="m",
                                       prompt_tokens=1, completion_tokens=1, cost=0.0)

        client.chat_json = AsyncMock(side_effect=chat_json)
        client.close = AsyncMock()
        return client

    async def test_high_risk_gains_a_test_engineer(self):
        from autornd.engine.phases import run_triage
        from autornd.models.verdicts import SpecialistRole

        verdict, _ = await run_triage(
            self._client("high", ["hardware_engineer"]), "wire the sensor")
        assert SpecialistRole.TEST_ENGINEER in verdict.specialists

    async def test_multi_domain_gains_an_architect(self):
        from autornd.engine.phases import run_triage
        from autornd.models.verdicts import SpecialistRole

        verdict, _ = await run_triage(
            self._client("medium", ["hardware_engineer"]), "wire the sensor")
        assert SpecialistRole.SYSTEMS_ARCHITECT in verdict.specialists

    async def test_low_risk_single_domain_is_left_alone(self):
        """Enforcement adds what the rules require and nothing else."""
        from autornd.engine.phases import run_triage
        from autornd.models.verdicts import SpecialistRole

        client = OpenRouterClient(api_key="test")

        async def chat_json(function, system_prompt, user_message, **kw):
            data = {"domains": ["frontend"], "risk": "low",
                    "specialists": ["frontend_engineer"], "summary": "s"}
            return data, ModelResponse(content=json.dumps(data), model="m",
                                       prompt_tokens=1, completion_tokens=1, cost=0.0)

        client.chat_json = AsyncMock(side_effect=chat_json)
        verdict, _ = await run_triage(client, "restyle the cards")
        assert verdict.specialists == [SpecialistRole.FRONTEND_ENGINEER]

    async def test_the_graph_path_enforces_it_too(self):
        """The point of the regression: both paths, not just the old one."""
        from autornd.graph.adapter import PhaseRunner
        from autornd.graph.executor import GraphExecutor
        from autornd.models.verdicts import SpecialistRole

        runner = PhaseRunner(self._client("high", ["hardware_engineer"]))
        state = await GraphExecutor(
            load("workflows/triage-only.yaml"), runner, SETTINGS).run("wire it")
        assert SpecialistRole.TEST_ENGINEER in state.outputs["triage"].specialists
