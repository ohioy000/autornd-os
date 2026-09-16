"""B13's override: the criteria demand verifiability, so the lookup fires.

The measured failure (§24/§26): a low-risk brief whose plan demanded "a
citable source a reader can use to verify the claim" — after the risk gate
had already zeroed its lookups. The implementer did not refuse honestly; it
fabricated sources for six iterations and died on the cost ceiling. The
controlled contrast shipped in one iteration with one lookup at medium risk.

The override (Blueprint 016 B1): the demand is detected free and
deterministically over the criteria text, and the one bundled lookup the risk
gate declined fires anyway, at the medium-risk budget. Where no criterion
demands citation the override costs nothing — that is Part E2's regression
case, pre-figured here at unit level.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from autornd.knowledge.context import (
    build_phase_context,
    criteria_demand_verification,
)


DEMANDING = [
    "Every factual claim carries a citable source a reader can use to verify it",
    "The tone matches the house style guide",
]
ORDINARY = [
    "Reconnect loop applies exponential backoff capped at 60s with jitter",
    "Jitter is applied to every retry attempt",
]


class TestTheDemandTrigger:
    def test_the_blueprint_example_demands(self):
        assert criteria_demand_verification(
            ["a citable source (author, title, publication, date, and URL) "
             "that a reader can use to verify the claim"])

    def test_a_citation_demand_in_any_wording_demands(self):
        for criterion in ("each claim carries a citation",
                          "claims are verifiable against published figures",
                          "a bibliography accompanies the deliverable"):
            assert criteria_demand_verification([criterion]), criterion

    def test_ordinary_engineering_criteria_do_not_demand(self):
        assert not criteria_demand_verification(ORDINARY)

    def test_no_criteria_do_not_demand(self):
        assert not criteria_demand_verification([])
        assert not criteria_demand_verification(None)


@pytest.fixture
def _no_docs(monkeypatch):
    """The empty-store shape the measured failure ran under."""
    from autornd import config
    import autornd.knowledge.context as ctx
    import autornd.knowledge.research as research

    monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
    monkeypatch.setattr(config.settings, "model_search", "vendor/search")
    monkeypatch.setattr(ctx, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(ctx, "load_docs_context", lambda *a, **k: "")
    monkeypatch.setattr(research, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(research, "ingest_text", lambda *a, **k: 0)


def _scoping_client(blocking):
    from autornd.routing.openrouter import ModelResponse

    client = AsyncMock()
    client.chat_json = AsyncMock(return_value=({
        "objective": "write the brief", "unknowns": ["the claim's figure"],
        "blocking_unknowns": blocking,
        "assumptions": [], "considerations": []}, None))
    client.chat = AsyncMock(return_value=ModelResponse(
        content="A: the figure", model="m", prompt_tokens=1,
        completion_tokens=1, cost=0.03,
        citations=["https://example.org/ds.pdf"]))
    return client


class TestTheRiskGateDefersInsteadOfDiscarding:
    async def test_low_risk_defers_the_lookup_and_keeps_the_gaps(
            self, _no_docs):
        from autornd.models.verdicts import Domain, RiskLevel

        client = _scoping_client(["the claim's figure"])
        deferred: list[str] = []
        out = await build_phase_context(
            "write the positioning brief", [Domain.FRONTEND],
            client=client, risk=RiskLevel.LOW, deferred_gaps=deferred)

        assert client.chat.await_count == 0, "the risk gate still declines"
        assert deferred == ["the claim's figure"], "the gap is kept, not dropped"
        assert "REQUEST ANALYSIS" in out

    async def test_consequential_work_looks_up_and_defers_nothing(self, _no_docs):
        from autornd.models.verdicts import Domain, RiskLevel

        client = _scoping_client(["the claim's figure"])
        deferred: list[str] = []
        await build_phase_context(
            "size a bracket", [Domain.HARDWARE],
            client=client, risk=RiskLevel.HIGH, deferred_gaps=deferred)

        assert client.chat.await_count == 1
        assert deferred == []


class TestTheDocsPathDefersToo:
    async def test_a_declined_blocking_gap_is_kept(self, monkeypatch):
        from autornd import config
        import autornd.knowledge.context as ctx
        from autornd.models.verdicts import RiskLevel

        monkeypatch.setattr(config.settings, "model_research", "vendor/researcher")
        monkeypatch.setattr(config.settings, "model_search", "vendor/search")
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=(
            {"briefing": "Supply is 24V nominal.",
             "gaps": ["cable length limits"],
             "blocking_gaps": ["the connector's ingress rating"]}, None))
        client.chat = AsyncMock()

        deferred: list[str] = []
        await ctx.synthesize_briefing(
            client, "wire it",
            [{"text": "24V nominal", "tag": "power", "distance": 0.1}],
            risk=RiskLevel.LOW, deferred_gaps=deferred)

        assert client.chat.await_count == 0
        assert deferred == ["the connector's ingress rating"]


class TestTheOverrideNode:
    """The adapter's verify_grounding node, driven directly — the same shape
    test_routing.py uses for _phase_doublecheck. The plan in state is a real
    PlanVerdict, because that is the only shape production ever puts there:
    a dict fixture would simulate a condition nothing produces."""

    @staticmethod
    def _runner(deferred):
        from autornd.graph.adapter import PhaseRunner
        from autornd.routing.openrouter import OpenRouterClient

        runner = PhaseRunner(OpenRouterClient(api_key="test"))
        runner.deferred_gaps = list(deferred)
        return runner

    @staticmethod
    def _state(criteria):
        from autornd.graph.executor import ExecutionState
        from autornd.models.verdicts import PlanVerdict

        return ExecutionState(request="write the brief", outputs={
            "plan": PlanVerdict(ready=True, plan="p", success_criteria=criteria)})

    async def test_no_demand_costs_nothing(self, monkeypatch):
        import autornd.knowledge.research as research

        lookup = AsyncMock()
        monkeypatch.setattr(research, "research_gaps", lookup)
        runner = self._runner(["a gap"])

        result = await runner._verify_grounding(self._state(ORDINARY))

        lookup.assert_not_called()
        assert result.data["demanded"] is False

    async def test_a_demand_fires_the_declined_lookup_at_the_medium_budget(
            self, monkeypatch):
        import autornd.knowledge.research as research
        from autornd import config
        from autornd.knowledge.research import Finding

        captured = {}

        async def fake_gaps(client, request, gaps, max_tokens=None, **kw):
            captured["gaps"] = list(gaps)
            captured["max_tokens"] = max_tokens
            # Real research echoes each gap back as its Finding's question, and
            # the rendered findings are what the override appends to the
            # context. The double must return that shape or the context
            # assertion below tests nothing: this one used to answer "q" and
            # the failure it produced was the double's, not the code's.
            return [Finding(gap, "18-30 V per the datasheet",
                            ["https://example.org/ds.pdf"])
                    for gap in gaps]

        monkeypatch.setattr(research, "research_gaps", fake_gaps)
        runner = self._runner(["the claim's figure"])
        result = await runner._verify_grounding(self._state(DEMANDING))

        assert captured["gaps"] == ["the claim's figure"]
        assert captured["max_tokens"] == config.settings.search_max_tokens, (
            "the standard medium-risk budget, whatever the triage risk")
        assert result.data["looked_up"] == 1
        assert "the claim's figure" in runner.context, (
            "the findings reach the implement prompt's context")
        assert "18-30 V" in runner.context, "and the answer travels with them"

    async def test_the_override_fires_once_per_run(self, monkeypatch):
        import autornd.knowledge.research as research
        from autornd.knowledge.research import Finding

        calls = {"n": 0}

        async def fake_gaps(*a, **kw):
            calls["n"] += 1
            return [Finding("q", "a", ["https://example.org/s.pdf"])]

        monkeypatch.setattr(research, "research_gaps", fake_gaps)
        runner = self._runner(["the claim's figure"])
        state = self._state(DEMANDING)

        await runner._verify_grounding(state)
        await runner._verify_grounding(state)

        assert calls["n"] == 1, "one bundled lookup per run, not per call"

    async def test_a_demand_with_no_deferred_gaps_looks_up_nothing(
            self, monkeypatch):
        import autornd.knowledge.research as research

        lookup = AsyncMock()
        monkeypatch.setattr(research, "research_gaps", lookup)
        runner = self._runner([])

        result = await runner._verify_grounding(self._state(DEMANDING))

        lookup.assert_not_called()
        assert result.data["demanded"] is True
        assert result.data["looked_up"] == 0
