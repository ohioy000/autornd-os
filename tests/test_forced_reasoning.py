"""Ruling D34: the implement node reasons before it produces.

run_implement's JSON contract requires a `reasoning` field emitted FIRST, so a
non-reasoning model generates its delta/consistency analysis before the
deliverable — synthetic reasoning, json_object-safe. The verdict ignores the
field, so the process changes, not the verdict's meaning.

Provider-free: chat_json is mocked to capture the prompt. The field-order check
is the guard with teeth (convention 22) — reasoning must precede summary, or the
autoregressive CoT runway the ruling depends on does not exist.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from autornd.engine.phases import run_implement
from autornd.models.verdicts import ImplementVerdict, PlanVerdict, SpecialistRole
from autornd.routing.openrouter import OpenRouterClient
from autornd.specialists.base import Specialist
from tests.conftest import make_mock_response


def _specialist() -> Specialist:
    return Specialist(
        role=SpecialistRole.SYSTEMS_ARCHITECT, name="Systems Architect",
        domain="architecture", system_prompt="You are a test specialist.",
        router_function="engineering",
    )


def _plan() -> PlanVerdict:
    return PlanVerdict(ready=True, plan="Keep every value consistent.",
                       blockers=[], success_criteria=["numbers agree"])


def _client(prompts: list[str]) -> OpenRouterClient:
    client = OpenRouterClient(api_key="test")
    impl = {"reasoning": "delta analysis", "done": True, "green": True,
            "red_cause": None, "iteration": 1, "summary": "the work"}

    async def _cap(function, system_prompt, user_message, **kw):
        prompts.append(user_message)
        return impl, make_mock_response(impl)

    client.chat_json = AsyncMock(side_effect=_cap)
    return client


@pytest.mark.asyncio
class TestForcedReasoning:
    async def test_prompt_requires_a_reasoning_field(self):
        prompts: list[str] = []
        await run_implement(_client(prompts), "Build it", _plan(), [_specialist()],
                            iteration=1)
        p = prompts[0]
        assert "- reasoning:" in p
        assert "fill this FIRST" in p
        assert "numeric" in p.lower()  # the consistency failure it guards

    async def test_reasoning_is_emitted_before_the_deliverable(self):
        """Convention 22 — the guard that can fail. Field order IS the mechanism:
        reasoning must precede summary so the model generates its analysis before
        the answer. If they were reversed, there is no CoT runway."""
        prompts: list[str] = []
        await run_implement(_client(prompts), "Build it", _plan(), [_specialist()],
                            iteration=1)
        p = prompts[0]
        assert p.index("- reasoning:") < p.index("- summary:")

    async def test_the_reasoning_field_is_ignored_by_the_verdict(self):
        """It is a scratchpad, not verdict data: extra field, dropped on validate."""
        v = ImplementVerdict(reasoning="scratch", done=True, green=True,
                             red_cause=None, iteration=2, summary="work")
        assert v.summary == "work" and v.green is True
        assert not hasattr(v, "reasoning")
