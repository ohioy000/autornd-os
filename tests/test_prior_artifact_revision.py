"""Ruling D33: the implement node revises its own prior artifact.

On iteration 1 there is no prior artifact and the instruction is to PRODUCE.
On every iteration after the first, the previous implementation's summary is
carried into the prompt VERBATIM and the instruction changes to REVISE —
preserve what passed, change only what the diagnosis requires. A model told to
produce regenerates regardless of what it is shown, so the instruction change is
the ruling, not merely the extra input.

These are provider-free: chat_json is mocked to capture the prompt the phase
built. The last test proves the guard has teeth (convention 22) — withhold the
artifact and the iteration-2 assertion no longer holds.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from autornd.engine.phases import run_implement
from autornd.models.verdicts import PlanVerdict, SpecialistRole
from autornd.routing.openrouter import OpenRouterClient
from autornd.specialists.base import Specialist
from tests.conftest import make_mock_response

ARTIFACT = (
    "SECTION 1\nThe redesign holds condition number kappa = 17.99 at the worst "
    "midpoint, with a slowdown trigger set at 17. UNIQUE-ARTIFACT-MARKER-42."
)


def _specialist() -> Specialist:
    return Specialist(
        role=SpecialistRole.SYSTEMS_ARCHITECT,
        name="Systems Architect",
        domain="architecture",
        system_prompt="You are a test specialist.",
        router_function="engineering",
    )


def _plan() -> PlanVerdict:
    return PlanVerdict(
        ready=True,
        plan="Step 1: keep kappa consistent with the stated slowdown trigger.",
        blockers=[],
        success_criteria=["kappa stays below the stated slowdown trigger"],
    )


def _client_capturing(prompts: list[str]) -> OpenRouterClient:
    client = OpenRouterClient(api_key="test")
    impl = {"done": True, "green": True, "red_cause": None,
            "iteration": 1, "summary": "revised output"}

    async def _capture(function, system_prompt, user_message, **kw):
        prompts.append(user_message)
        return impl, make_mock_response(impl)

    client.chat_json = AsyncMock(side_effect=_capture)
    return client


@pytest.mark.asyncio
class TestPriorArtifactRevision:
    async def test_iteration_one_produces_and_carries_no_prior_artifact(self):
        prompts: list[str] = []
        await run_implement(
            _client_capturing(prompts), "Build it", _plan(), [_specialist()],
            iteration=1, prior_summary=None,
        )
        prompt = prompts[0]
        assert "Produce the implementation for the following plan." in prompt
        assert "REVISION TASK" not in prompt
        assert "YOUR PREVIOUS IMPLEMENTATION" not in prompt
        assert "UNIQUE-ARTIFACT-MARKER-42" not in prompt

    async def test_iteration_two_revises_and_carries_prior_artifact_verbatim(self):
        prompts: list[str] = []
        await run_implement(
            _client_capturing(prompts), "Build it", _plan(), [_specialist()],
            iteration=2, prior_summary=ARTIFACT,
            red_cause="kappa=17.99 exceeds the stated slowdown trigger of 17",
        )
        prompt = prompts[0]
        # instruction changed from produce to revise
        assert "Revise your previous implementation for the following plan" in prompt
        assert "Produce the implementation for the following plan." not in prompt
        # explicit about preserving what passed, not only fixing what failed
        assert "Preserve every part that the success criteria judged correct" in prompt
        assert "Do not regenerate the work from the plan" in prompt
        # the artifact itself is present verbatim
        assert ARTIFACT in prompt
        assert "UNIQUE-ARTIFACT-MARKER-42" in prompt

    async def test_guard_fails_when_artifact_withheld(self):
        """Convention 22: prove the test can fail. Withhold the artifact on what
        is otherwise an iteration-2 call — the verbatim-artifact assertion that
        passes above must NOT hold, or the test above proves nothing."""
        prompts: list[str] = []
        await run_implement(
            _client_capturing(prompts), "Build it", _plan(), [_specialist()],
            iteration=2, prior_summary=None,
            red_cause="kappa=17.99 exceeds the stated slowdown trigger of 17",
        )
        prompt = prompts[0]
        assert ARTIFACT not in prompt
        assert "Revise your previous implementation for the following plan" not in prompt
