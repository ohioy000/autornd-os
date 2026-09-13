"""Tests for outward research.

The behaviour under test is a discipline, not a capability: a looked-up fact
carries its sources, an unsourced answer is marked and never stored as project
knowledge, and no single failed lookup takes a workflow down with it.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from autornd.knowledge.research import (
    MAX_LOOKUPS, Finding, render_findings, research_gaps,
)
from autornd.routing.openrouter import ModelResponse

GAPS = [
    "The per-cell charge cutoff voltage for LiFePO4",
    "The maximum EIRP in the EU 868 MHz band",
]


def reply(content, citations=(), model="search/model"):
    return ModelResponse(content=content, model=model, prompt_tokens=10,
                         completion_tokens=20, cost=0.005,
                         citations=list(citations))


def client_returning(*responses):
    client = AsyncMock()
    client.chat = AsyncMock(side_effect=list(responses))
    return client


class TestFinding:
    def test_a_cited_finding_is_grounded(self):
        assert Finding("q", "a", ["https://example.com/ds.pdf"]).grounded

    def test_an_uncited_finding_is_not(self):
        """The failure mode this module exists to prevent: a confident
        assertion with nothing behind it."""
        assert not Finding("q", "a", []).grounded

    def test_render_says_when_nothing_backed_it_up(self):
        assert "treat as unverified" in Finding("q", "a", []).render()

    def test_render_lists_sources(self):
        out = Finding("q", "a", ["https://example.com/ds.pdf"]).render()
        assert "example.com/ds.pdf" in out


@pytest.mark.asyncio
class TestResearchGaps:
    async def test_no_search_model_means_no_lookups(self, monkeypatch):
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "")
        client = client_returning(reply("should not be called"))
        assert await research_gaps(client, "req", GAPS) == []
        client.chat.assert_not_called()

    async def test_no_gaps_means_no_lookups(self, monkeypatch):
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = client_returning(reply("x"))
        assert await research_gaps(client, "req", []) == []
        client.chat.assert_not_called()

    async def test_each_gap_becomes_one_lookup(self, monkeypatch):
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = client_returning(
            reply("3.65 V per cell", ["https://eve.com/lf280k.pdf"]),
            reply("+16 dBm", ["https://lora-alliance.org/rp.pdf"]),
        )
        findings = await research_gaps(client, "req", GAPS)
        assert [f.question for f in findings] == GAPS
        assert all(f.grounded for f in findings)
        assert client.chat.await_count == 2

    async def test_lookups_route_to_the_search_tier(self, monkeypatch):
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = client_returning(reply("a", ["https://x/y.pdf"]))
        await research_gaps(client, "req", GAPS[:1])
        assert client.chat.await_args.kwargs["function"] == "search"

    async def test_one_failed_lookup_does_not_sink_the_rest(self, monkeypatch):
        """Three facts out of four beats aborting; the missing one stays a gap."""
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = AsyncMock()
        client.chat = AsyncMock(side_effect=[
            RuntimeError("provider down"),
            reply("+16 dBm", ["https://lora-alliance.org/rp.pdf"]),
        ])
        findings = await research_gaps(client, "req", GAPS)
        assert len(findings) == 1
        assert findings[0].question == GAPS[1]

    async def test_lookups_are_bounded(self, monkeypatch):
        """A runaway sweep cost forty minutes once. Nothing unbounded ships."""
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        many = [f"gap {i}" for i in range(12)]
        client = AsyncMock()
        client.chat = AsyncMock(return_value=reply("a", ["https://x/y.pdf"]))
        findings = await research_gaps(client, "req", many)
        assert len(findings) == MAX_LOOKUPS
        assert client.chat.await_count == MAX_LOOKUPS

    async def test_an_empty_answer_is_discarded(self, monkeypatch):
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = client_returning(reply("   ", ["https://x/y.pdf"]))
        assert await research_gaps(client, "req", GAPS[:1]) == []


@pytest.mark.asyncio
class TestOnlyCitedFactsBecomeKnowledge:
    async def test_a_cited_finding_is_stored(self, monkeypatch):
        from autornd import config
        import autornd.knowledge.research as research

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        stored: list[tuple] = []
        monkeypatch.setattr(research, "ingest_text",
                            lambda text, tag, source="": stored.append((tag, source)))
        client = client_returning(reply("3.65 V", ["https://eve.com/ds.pdf"]))
        await research_gaps(client, "req", GAPS[:1])
        assert stored and stored[0][0] == "research"

    async def test_an_uncited_finding_is_shown_but_not_stored(self, monkeypatch):
        """Worth telling the operator; not worth becoming permanent context
        that later workflows treat as established project knowledge."""
        from autornd import config
        import autornd.knowledge.research as research

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        stored: list[tuple] = []
        monkeypatch.setattr(research, "ingest_text",
                            lambda text, tag, source="": stored.append((tag, source)))
        client = client_returning(reply("I could not find this.", []))
        findings = await research_gaps(client, "req", GAPS[:1])
        assert len(findings) == 1 and not findings[0].grounded
        assert stored == []

    async def test_a_storage_failure_is_not_fatal(self, monkeypatch):
        from autornd import config
        import autornd.knowledge.research as research

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")

        def explode(*a, **kw):
            raise RuntimeError("chroma unavailable")

        monkeypatch.setattr(research, "ingest_text", explode)
        client = client_returning(reply("3.65 V", ["https://eve.com/ds.pdf"]))
        findings = await research_gaps(client, "req", GAPS[:1])
        assert len(findings) == 1


class TestRenderFindings:
    def test_nothing_renders_as_nothing(self):
        assert render_findings([]) == ""

    def test_unverified_findings_are_called_out_in_the_header(self):
        out = render_findings([
            Finding("q1", "a1", ["https://x/y.pdf"]),
            Finding("q2", "a2", []),
        ])
        assert "1 of 2 could not be sourced" in out
        assert "do not treat those as specifications" in out

    def test_the_header_says_why_these_were_looked_up(self):
        out = render_findings([Finding("q", "a", ["https://x/y.pdf"])])
        assert "project documentation did not cover" in out
