"""A workflow node's token ceiling must reach the model call, on every phase.

**Why this exists.** The 072 live retest died at `plan`: three architecture
calls each filled 16384 completion tokens and truncated mid-JSON, while the
owner's `.env` granted `PLAN_MAX_TOKENS=112768` and the workflow declared
`max_tokens: plan_max_tokens` on the plan node. `_phase_plan` never called
`_max_tokens(node)` — unlike `_phase_validate`, which did — so `run_plan`
fell through to `chat_json`'s 16384 default. The ceiling was configured,
declared, resolved nowhere, and silently ignored: $0.44 for three truncated
plans and zero verdicts. A configured ceiling that never reaches its call is
convention 28 — an instrument that reports less than it measured, here the
measurement being what the run was allowed to spend.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from autornd.graph.adapter import PhaseRunner
from autornd.graph.executor import ExecutionState
from autornd.graph.spec import Node, NodeKind
from autornd.models.verdicts import (
    ImplementVerdict,
    PlanVerdict,
    TriageVerdict,
    ValidateVerdict,
)
from autornd.routing.openrouter import ModelResponse, OpenRouterClient


def _plan_state() -> ExecutionState:
    state = ExecutionState(request="size the queue")
    state.outputs["triage"] = TriageVerdict(
        domains=["backend"], risk="medium",
        specialists=["backend_engineer"], summary="s")
    return state


def _plan_node(**kw) -> Node:
    return Node(id="plan", kind=NodeKind.AI, tier="architecture",
                prompt="plan", **kw)


def _validate_state() -> ExecutionState:
    state = _plan_state()
    state.outputs["plan"] = PlanVerdict(
        ready=True, plan="p", success_criteria=["Backoff capped at 60s"])
    state.outputs["implement"] = ImplementVerdict(
        done=True, green=True, summary="s", iteration=1)
    return state


def _ok_response() -> ModelResponse:
    return ModelResponse(content="{}", model="m", prompt_tokens=1,
                         completion_tokens=1, cost=0.0)


@pytest.mark.asyncio
class TestNodeCeilingsReachTheirCalls:
    async def test_the_plan_node_ceiling_reaches_run_plan(self, monkeypatch):
        """072's defect: the node's 112768 never left the workflow file."""
        from autornd import config

        monkeypatch.setattr(config.settings, "plan_max_tokens", 112768)
        runner = PhaseRunner(client=OpenRouterClient(api_key="test"))
        verdict = PlanVerdict(ready=True, plan="p",
                              success_criteria=["Backoff capped at 60s"])
        with patch("autornd.engine.phases.run_plan",
                   new=AsyncMock(return_value=(verdict, _ok_response()))) as run:
            await runner._phase_plan(
                _plan_node(max_tokens="plan_max_tokens"), _plan_state())
        assert run.await_args.kwargs["max_tokens"] == 112768

    async def test_a_literal_plan_ceiling_passes_through(self):
        runner = PhaseRunner(client=OpenRouterClient(api_key="test"))
        verdict = PlanVerdict(ready=True, plan="p",
                              success_criteria=["Backoff capped at 60s"])
        with patch("autornd.engine.phases.run_plan",
                   new=AsyncMock(return_value=(verdict, _ok_response()))) as run:
            await runner._phase_plan(_plan_node(max_tokens=4096), _plan_state())
        assert run.await_args.kwargs["max_tokens"] == 4096

    async def test_no_ceiling_falls_back_to_the_setting(self, monkeypatch):
        """A node without max_tokens still gets the phase default, not the
        client default — the setting is the floor, never silent."""
        from autornd import config

        monkeypatch.setattr(config.settings, "plan_max_tokens", 32768)
        runner = PhaseRunner(client=OpenRouterClient(api_key="test"))
        verdict = PlanVerdict(ready=True, plan="p",
                              success_criteria=["Backoff capped at 60s"])
        with patch("autornd.engine.phases.run_plan",
                   new=AsyncMock(return_value=(verdict, _ok_response()))) as run:
            await runner._phase_plan(_plan_node(), _plan_state())
        assert run.await_args.kwargs["max_tokens"] is None
        # ...which run_plan resolves to the setting, asserted at its level:
        import json

        from autornd.engine import phases
        from autornd.specialists.registry import get_specialist

        client = OpenRouterClient(api_key="test")
        seen: dict = {}

        async def chat_json(function, system_prompt, user_message, **kw):
            seen.update(kw)
            client._account(function, 0.001)
            reply = {"ready": True, "plan": "p", "blockers": [],
                     "cost_estimate": None,
                     "success_criteria": ["Backoff capped at 60s"]}
            return dict(reply), ModelResponse(
                content=json.dumps(reply), model="mock",
                prompt_tokens=1, completion_tokens=1, cost=0.001)

        client.chat_json = AsyncMock(side_effect=chat_json)
        triage = TriageVerdict(domains=["backend"], risk="medium",
                               specialists=["backend_engineer"], summary="s")
        await phases.run_plan(client, "add retry", triage,
                              [get_specialist("backend_engineer")])
        assert seen["max_tokens"] == 32768

    async def test_the_validate_node_ceiling_still_reaches_run_validate(
            self, monkeypatch):
        """The pre-existing wiring this fix mirrors — pinned so the mirror
        cannot drift from the model."""
        from autornd import config

        monkeypatch.setattr(config.settings, "validate_max_tokens", 28000)
        runner = PhaseRunner(client=OpenRouterClient(api_key="test"))
        verdict = ValidateVerdict(green=True, red_cause=None, evidence=[])
        with patch("autornd.engine.phases.run_validate",
                   new=AsyncMock(return_value=(verdict, _ok_response()))) as run:
            await runner._phase_validate(
                Node(id="validate", kind=NodeKind.AI,
                     max_tokens="validate_max_tokens"),
                _validate_state())
        assert run.await_args.kwargs["max_tokens"] == 28000
