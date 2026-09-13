"""Tests for lead+review implement pattern."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from autornd.engine.phases import DOMAIN_LEAD_MAP, run_implement
from autornd.models.verdicts import (
    Domain,
    ImplementVerdict,
    PlanVerdict,
    SpecialistRole,
)
from autornd.routing.openrouter import OpenRouterClient
from autornd.specialists.base import Specialist
from tests.conftest import make_mock_response


def _make_specialist(role: SpecialistRole) -> Specialist:
    return Specialist(
        role=role,
        name=role.value,
        domain=role.value,
        system_prompt="You are a test specialist.",
        router_function="engineering",
    )


def _make_plan() -> PlanVerdict:
    return PlanVerdict(
        ready=True,
        plan="Step 1: Do the thing.",
        blockers=[],
        success_criteria=["Thing is done"],
    )


class TestDomainLeadMap:
    def test_all_domains_mapped(self):
        for domain in Domain:
            assert domain in DOMAIN_LEAD_MAP

    def test_firmware_maps_to_firmware_engineer(self):
        assert DOMAIN_LEAD_MAP[Domain.FIRMWARE] == SpecialistRole.FIRMWARE_ENGINEER

    def test_hardware_maps_to_hardware_engineer(self):
        assert DOMAIN_LEAD_MAP[Domain.HARDWARE] == SpecialistRole.HARDWARE_ENGINEER

    def test_infrastructure_maps_to_architect(self):
        assert DOMAIN_LEAD_MAP[Domain.INFRASTRUCTURE] == SpecialistRole.SYSTEMS_ARCHITECT


@pytest.mark.asyncio
class TestLeadSelection:
    async def test_single_specialist_unchanged(self):
        """Single specialist path should work identically to before."""
        client = OpenRouterClient(api_key="test")
        impl_data = {
            "done": True, "green": True, "red_cause": None,
            "iteration": 1, "summary": "Built it.",
        }

        async def _mock(function, system_prompt, user_message, **kw):
            return impl_data, make_mock_response(impl_data)

        client.chat_json = AsyncMock(side_effect=_mock)
        specialist = _make_specialist(SpecialistRole.FIRMWARE_ENGINEER)

        verdict, responses = await run_implement(
            client, "test request", _make_plan(),
            [specialist], iteration=1,
        )

        assert verdict.green is True
        assert verdict.summary == "Built it."
        assert len(responses) == 1

    async def test_lead_selected_by_domain(self):
        """With primary_domain=hardware, hardware_engineer should be lead."""
        client = OpenRouterClient(api_key="test")
        call_order = []

        async def _mock(function, system_prompt, user_message, **kw):
            msg = user_message.lower()
            if "produce the implementation for the following plan" in msg:
                call_order.append("implement")
                data = {
                    "done": True, "green": True, "red_cause": None,
                    "iteration": 1, "summary": "Hardware lead built it.",
                }
            else:
                call_order.append("review")
                data = {"concerns": [], "critical": False}
            return data, make_mock_response(data)

        client.chat_json = AsyncMock(side_effect=_mock)

        hw = _make_specialist(SpecialistRole.HARDWARE_ENGINEER)
        fw = _make_specialist(SpecialistRole.FIRMWARE_ENGINEER)

        verdict, responses = await run_implement(
            client, "test request", _make_plan(),
            [fw, hw], iteration=1,
            primary_domain=Domain.HARDWARE,
        )

        assert verdict.green is True
        assert call_order[0] == "implement"
        assert "review" in call_order

    async def test_domain_review_skipped_when_lead_fails(self):
        """If lead returns green=False, reviewers should NOT run."""
        client = OpenRouterClient(api_key="test")
        call_count = {"n": 0}

        async def _mock(function, system_prompt, user_message, **kw):
            call_count["n"] += 1
            data = {
                "done": False, "green": False,
                "red_cause": "Can't solve it",
                "iteration": 1, "summary": "Failed attempt.",
            }
            return data, make_mock_response(data)

        client.chat_json = AsyncMock(side_effect=_mock)
        hw = _make_specialist(SpecialistRole.HARDWARE_ENGINEER)
        fw = _make_specialist(SpecialistRole.FIRMWARE_ENGINEER)

        verdict, responses = await run_implement(
            client, "test request", _make_plan(),
            [hw, fw], iteration=1,
            primary_domain=Domain.HARDWARE,
        )

        assert verdict.green is False
        assert call_count["n"] == 1  # only the lead was called

    async def test_domain_concerns_propagated(self):
        """Domain reviewer concerns should appear in verdict."""
        client = OpenRouterClient(api_key="test")

        async def _mock(function, system_prompt, user_message, **kw):
            msg = user_message.lower()
            if "produce the implementation for the following plan" in msg:
                data = {
                    "done": True, "green": True, "red_cause": None,
                    "iteration": 1, "summary": "Built voltage regulator.",
                }
            else:
                data = {
                    "concerns": ["TVS voltage exceeds regulator max"],
                    "critical": False,
                }
            return data, make_mock_response(data)

        client.chat_json = AsyncMock(side_effect=_mock)
        hw = _make_specialist(SpecialistRole.HARDWARE_ENGINEER)
        fw = _make_specialist(SpecialistRole.FIRMWARE_ENGINEER)

        verdict, _ = await run_implement(
            client, "test request", _make_plan(),
            [hw, fw], iteration=1,
            primary_domain=Domain.HARDWARE,
        )

        assert verdict.green is True
        assert "TVS voltage exceeds regulator max" in verdict.domain_concerns

    async def test_critical_concern_flips_green(self):
        """A critical domain concern should set green=False."""
        client = OpenRouterClient(api_key="test")

        async def _mock(function, system_prompt, user_message, **kw):
            msg = user_message.lower()
            if "produce the implementation for the following plan" in msg:
                data = {
                    "done": True, "green": True, "red_cause": None,
                    "iteration": 1, "summary": "Built it.",
                }
            else:
                data = {
                    "concerns": ["Fatal voltage domain crossing"],
                    "critical": True,
                }
            return data, make_mock_response(data)

        client.chat_json = AsyncMock(side_effect=_mock)
        hw = _make_specialist(SpecialistRole.HARDWARE_ENGINEER)
        fw = _make_specialist(SpecialistRole.FIRMWARE_ENGINEER)

        verdict, _ = await run_implement(
            client, "test request", _make_plan(),
            [hw, fw], iteration=1,
            primary_domain=Domain.HARDWARE,
        )

        assert verdict.green is False
        assert verdict.red_cause is not None
