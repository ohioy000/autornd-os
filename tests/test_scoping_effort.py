"""The scoping call asks for medium reasoning effort and the research tier has
its own output ceiling (owner's ruling, 2026-11-21: correctness first).

Measured: at the provider's default the scoping call spent 4,000 to 30,000
tokens reasoning and twice returned nothing at the 16,384-token cap on X12; at
medium it used 650 to 1,030 and all four hold-out units run through it were
right. What is pinned: the scoping call carries the effort option and only that
call does; all three research-tier calls carry the tier's ceiling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from autornd import config
from autornd.knowledge import context


@pytest.mark.asyncio
class TestTheScopingCallAsksForMediumEffort:
    async def test_analyze_request_sends_medium_effort(self, monkeypatch):
        """Break-proof: remove `reasoning=` from the call in analyze_request
        and this fails."""
        monkeypatch.setattr(config.settings, "model_research", "vendor/research")
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=(
            {"objective": "o", "unknowns": ["u"], "blocking_unknowns": ["b"]}, None))
        scoping, unknowns = await context.analyze_request(client, "a request")
        assert client.chat_json.await_args.kwargs["reasoning"] == {"effort": "medium"}
        assert unknowns == ["b"]

    async def test_query_expansion_is_left_as_it_was(self, monkeypatch):
        monkeypatch.setattr(config.settings, "model_research", "vendor/research")
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=({"queries": ["q"]}, None))
        await context.expand_queries(client, "a request")
        assert "reasoning" not in client.chat_json.await_args.kwargs


@pytest.mark.asyncio
class TestTheResearchTierHasItsOwnCeiling:
    async def test_the_three_research_calls_carry_the_ceiling(self, monkeypatch):
        """Break-proof: take `max_tokens=settings.research_max_tokens` out of any
        one of the three calls and this fails for that call."""
        monkeypatch.setattr(config.settings, "model_research", "vendor/research")
        monkeypatch.setattr(config.settings, "research_max_tokens", 12345)
        seen = []

        async def chat_json(**kw):
            seen.append(kw)
            return ({"queries": ["q"], "briefing": "b", "objective": "o",
                     "unknowns": [], "blocking_unknowns": []}, None)

        client = AsyncMock()
        client.chat_json = AsyncMock(side_effect=chat_json)
        await context.expand_queries(client, "a request")
        await context.analyze_request(client, "a request")
        await context.synthesize_briefing(
            client, "a request", [{"tag": "t", "text": "x", "source": "s", "distance": 0.1}])
        assert len(seen) == 3
        assert all(kw["max_tokens"] == 12345 for kw in seen)

    def test_the_default_is_above_the_old_sixteen_thousand(self):
        assert config.Settings.model_fields["research_max_tokens"].default == 32768
