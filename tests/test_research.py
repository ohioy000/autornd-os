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


@pytest.fixture(autouse=True)
def _empty_store(monkeypatch):
    """No stored findings unless a test puts one there.

    Research consults the store before paying for a lookup, so without this the
    suite reads whatever a developer's local Chroma directory happens to hold —
    which it did: every gap came back already answered by findings that earlier
    live runs had ingested, and no test made a single lookup.
    """
    monkeypatch.setattr("autornd.knowledge.research.retrieve",
                        lambda *a, **kw: [])


def stored(text, source="https://example.org/standard.pdf", distance=0.05):
    """A hit as the store would return it."""
    return [{"text": text, "source": source, "tag": "research",
             "distance": distance}]


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

    async def test_every_gap_rides_in_one_request(self, monkeypatch):
        """The fee is charged per request, not per question, so asking two gaps
        separately costs twice as much as asking them together. Measured at
        roughly $0.024 a lookup, that is the difference between search being a
        line item and search being the bill."""
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = client_returning(
            reply("1. 3.65 V per cell\n2. +16 dBm ERP",
                  ["https://eve.com/lf280k.pdf",
                   "https://lora-alliance.org/rp.pdf"]),
        )
        findings = await research_gaps(client, "req", GAPS)

        assert client.chat.await_count == 1, "paid a second search fee"
        assert len(findings) == 1
        # both gaps are in the question that was asked
        asked = client.chat.await_args.kwargs["user_message"]
        for gap in GAPS:
            assert gap in asked
        assert findings[0].grounded

    async def test_a_single_gap_is_not_numbered(self, monkeypatch):
        """One question should read as a question, not as a list of one."""
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = client_returning(reply("3.65 V", ["https://eve.com/x.pdf"]))
        findings = await research_gaps(client, "req", [GAPS[0]])
        assert findings[0].question == GAPS[0]
        assert not findings[0].question.startswith("1.")

    async def test_lookups_route_to_the_search_tier(self, monkeypatch):
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = client_returning(reply("a", ["https://x/y.pdf"]))
        await research_gaps(client, "req", GAPS[:1])
        assert client.chat.await_args.kwargs["function"] == "search"

    async def test_a_failed_lookup_does_not_sink_the_workflow(self, monkeypatch):
        """The gaps ride in one request now, so a failure loses the findings
        rather than some of them — and the workflow still proceeds, with the
        gaps still named in the briefing above."""
        from autornd import config

        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = AsyncMock()
        client.chat = AsyncMock(side_effect=RuntimeError("provider down"))
        findings = await research_gaps(client, "req", GAPS)
        assert findings == []

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


class TestRecallBeforeSearch:
    """Search is the most expensive thing this harness does — measured at 61% of
    a full workflow and 98% of a grounding run. Findings are ingested, so a fact
    looked up once is local afterwards, and the cheapest lookup is the one
    already answered.
    """

    @pytest.mark.asyncio
    async def test_a_close_stored_finding_replaces_the_lookup(self, monkeypatch):
        monkeypatch.setattr(
            "autornd.knowledge.research.retrieve",
            lambda *a, **kw: stored("Q: burst ratio\nA: 4:1 per ISO 1436"))
        client = client_returning(reply("should not be called"))

        findings = await research_gaps(client, "a crane circuit",
                                       ["What burst ratio applies?"])

        assert client.chat.await_count == 0, "paid for something already known"
        assert len(findings) == 1
        assert "4:1" in findings[0].answer
        assert findings[0].model == "recalled"
        assert findings[0].grounded, "a recalled finding keeps its source"

    @pytest.mark.asyncio
    async def test_a_distant_hit_does_not_count(self, monkeypatch):
        """Reusing the wrong finding is a wrong figure in a design; a needless
        lookup only costs money. The threshold leans that way on purpose."""
        monkeypatch.setattr(
            "autornd.knowledge.research.retrieve",
            lambda *a, **kw: stored("Q: something else\nA: unrelated",
                                    distance=0.9))
        client = client_returning(reply("A: 4:1", ["https://example.org/x.pdf"]))

        findings = await research_gaps(client, "r", ["What burst ratio applies?"])

        assert client.chat.await_count == 1
        assert findings[0].model != "recalled"

    @pytest.mark.asyncio
    async def test_only_researched_material_is_recalled(self, monkeypatch):
        """Project documentation is already in the briefing that produced the
        gap, so treating a doc chunk as the answer would mean it was never a
        gap."""
        seen = {}

        def fake_retrieve(query, n_results=1, where=None):
            seen["where"] = where
            return []

        monkeypatch.setattr("autornd.knowledge.research.retrieve", fake_retrieve)
        client = client_returning(reply("A: x", ["https://example.org/x.pdf"]))
        await research_gaps(client, "r", ["a gap"])
        assert seen["where"] == {"tag": "research"}

    @pytest.mark.asyncio
    async def test_a_recalled_finding_is_not_stored_again(self, monkeypatch):
        stores = []
        monkeypatch.setattr(
            "autornd.knowledge.research.retrieve",
            lambda *a, **kw: stored("Q: q\nA: a"))
        monkeypatch.setattr("autornd.knowledge.research._remember",
                            lambda f: stores.append(f))
        await research_gaps(client_returning(), "r", ["a gap"])
        assert stores == []

    @pytest.mark.asyncio
    async def test_a_store_failure_falls_back_to_searching(self, monkeypatch):
        """An unavailable store must not stop the work — it should cost a
        lookup, not the finding."""
        def boom(*a, **kw):
            raise RuntimeError("chroma is down")

        monkeypatch.setattr("autornd.knowledge.research.retrieve", boom)
        client = client_returning(reply("A: 4:1", ["https://example.org/x.pdf"]))
        findings = await research_gaps(client, "r", ["a gap"])
        assert client.chat.await_count == 1 and len(findings) == 1

    def test_one_request_per_workflow(self):
        """Search was 61% of a full workflow and 98% of a grounding run. One
        request, carrying every blocking gap."""
        assert MAX_LOOKUPS == 1


class TestWhenNothingIsWorthLookingUp:
    """The cost fix. Research used to fire on every workflow because the only
    gate was "did a model name any unknowns" — and a model asked what is
    unknown always names something. Measured, that was 61% of a full workflow
    and 98% of a grounding run on the most expensive tier in the system.
    """

    @pytest.mark.asyncio
    async def test_no_gaps_means_no_call(self):
        client = client_returning(reply("should not be called"))
        assert await research_gaps(client, "r", []) == []
        assert client.chat.await_count == 0

    @pytest.mark.asyncio
    async def test_blank_gaps_mean_no_call(self):
        """A model that returns ["", " "] has named nothing."""
        client = client_returning(reply("should not be called"))
        assert await research_gaps(client, "r", ["", "   "]) == []
        assert client.chat.await_count == 0

    @pytest.mark.asyncio
    async def test_no_search_tier_means_no_call(self, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "model_search", "")
        client = client_returning(reply("should not be called"))
        assert await research_gaps(client, "r", ["a real gap"]) == []
        assert client.chat.await_count == 0


class TestRiskGate:
    """Low risk means a wrong answer is trivially reversible and cannot hurt
    anyone. That does not justify the most expensive call this harness makes.

    The floor sits below medium on purpose: both measured confabulations that
    justify research at all — a charger IC named confidently and wrongly, and
    ERP quoted as EIRP — were selection work at medium risk.
    """

    def test_low_risk_does_not_pay(self):
        from autornd.knowledge.context import worth_a_lookup
        from autornd.models.verdicts import RiskLevel
        assert worth_a_lookup(RiskLevel.LOW) is False

    def test_everything_above_low_pays(self):
        from autornd.knowledge.context import worth_a_lookup
        from autornd.models.verdicts import RiskLevel
        for risk in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
            assert worth_a_lookup(risk) is True, risk

    def test_a_plain_string_works_too(self):
        from autornd.knowledge.context import worth_a_lookup
        assert worth_a_lookup("low") is False
        assert worth_a_lookup(" LOW ") is False
        assert worth_a_lookup("critical") is True

    def test_unknown_risk_still_grounds(self):
        """An absent risk is not a licence to skip grounding — it is a caller
        that did not pass one, and guessing cheap would be the wrong default."""
        from autornd.knowledge.context import worth_a_lookup
        assert worth_a_lookup(None) is True


class TestBudgetScalesWithConsequence:
    """Accuracy tracks the token budget almost linearly — graded against
    published figures, ~4800 tokens recovered 7 of 8 sectors, ~2900 recovered 5,
    ~1400 recovered 3. Tokens buy figures, so the budget is a dial rather than
    waste to cut, and it belongs where being wrong is expensive.
    """

    def test_consequential_work_gets_the_larger_budget(self):
        from autornd.knowledge.context import search_budget
        from autornd.config import settings
        from autornd.models.verdicts import RiskLevel

        for risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            assert search_budget(risk) == settings.search_max_tokens_consequential

    def test_medium_work_gets_the_lean_budget(self):
        from autornd.knowledge.context import search_budget
        from autornd.config import settings
        from autornd.models.verdicts import RiskLevel

        assert search_budget(RiskLevel.MEDIUM) == settings.search_max_tokens

    def test_the_larger_budget_is_actually_larger(self):
        from autornd.config import settings
        assert (settings.search_max_tokens_consequential
                > settings.search_max_tokens)

    def test_an_unknown_risk_takes_the_lean_budget(self):
        """Cheap is the right default when nobody said what this costs to get
        wrong — unlike the lookup gate, where the safe default is to ground."""
        from autornd.knowledge.context import search_budget
        from autornd.config import settings

        assert search_budget(None) == settings.search_max_tokens

    @pytest.mark.asyncio
    async def test_the_budget_reaches_the_request(self, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = client_returning(reply("A: 4:1", ["https://example.org/x.pdf"]))
        await research_gaps(client, "r", ["a blocking gap"], max_tokens=4000)
        assert client.chat.await_args.kwargs["max_tokens"] == 4000

    @pytest.mark.asyncio
    async def test_it_falls_back_to_the_setting(self, monkeypatch):
        from autornd import config
        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        monkeypatch.setattr(config.settings, "search_max_tokens", 1500)
        client = client_returning(reply("A: 4:1", ["https://example.org/x.pdf"]))
        await research_gaps(client, "r", ["a blocking gap"])
        assert client.chat.await_args.kwargs["max_tokens"] == 1500
