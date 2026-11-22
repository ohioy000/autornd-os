"""A pin reaches every place a tier is resolved, and an empty setting reaches none of them.

tests/test_profile_pins.py holds the grammar and the overlay (autornd/routing/pins.py). This file
holds the sites that read it: the client's model for a function (`get_model`), the derived
independent model, the recompute and decision tiers, the provider order a call sends, the gates
that ask whether a tier is configured at all (knowledge/context.py, knowledge/research.py) and the
one request that went to the wire. Three things are held apart.

1. With PROFILE_MODELS empty every accessor answers what it answered before the setting existed,
   on every shipped profile and on every shape of global configuration. The reference is a copy of
   the old expressions written out in this file, not a call into the code under test.
2. A pin is the model the profile it names reads for the tier it names, and no other profile and no
   other tier reads it. A tier the global map leaves unset and the pin sets is turned on for that
   profile only, and a tier nothing sets falls back to the *pinned* engineering model.
3. A pin carries its own serving: `@provider` sends that provider and no other, no `@provider`
   sends none and the global order is not applied, because it was written for another model.

Each guarded line was proven by breaking it (docs/reviews/2026-11-21-per-profile-pins-and-tuned-prompts.md).
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import autornd
from autornd import profiles
from autornd.config import PINNABLE_TIERS, settings
from autornd.routing.openrouter import (
    OpenRouterClient, provider_order_for, rebuild_function_models,
)

LINE = ("legal:engineering=vendor/legal-model@vendor,"
        "legal:judge=vendor/legal-judge,"
        "legal:recompute=vendor/legal-recompute,"
        "finance:triage=vendor/fin-triage@other")

OPTIONAL = ("ranker", "premium", "judge", "recompute", "decision", "reader")

# Shapes of global configuration. Each one reaches a different branch of the old expressions:
# optional tiers all unset, all set, the architecture tier equal to the engineering one (no honest
# independent model), and the premium tier equal to it.
CONFIGS = {
    "bare": {"model_ranker": "", "model_premium": "", "model_judge": "", "model_recompute": "",
             "model_decision": "", "model_reader": ""},
    "full": {"model_ranker": "g/ranker", "model_premium": "g/premium", "model_judge": "g/judge",
             "model_recompute": "g/recompute", "model_decision": "g/decision",
             "model_reader": "g/reader"},
    "architecture_is_engineering": {"model_architecture": "g/eng", "model_premium": ""},
    "premium_is_engineering": {"model_premium": "g/eng"},
}


@pytest.fixture
def globals_(monkeypatch):
    """Distinct global models for every required tier, so a wrong read is a wrong answer."""
    for name, value in {
        "model_triage": "g/triage", "model_engineering": "g/eng", "model_architecture": "g/arch",
        "model_escalation": "g/esc", "model_research": "g/research", "model_search": "g/search",
        "model_ranker": "", "model_premium": "", "model_judge": "", "model_recompute": "",
        "model_decision": "", "model_reader": "",
        "openrouter_provider_order": "", "profile_models": "",
    }.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(OpenRouterClient, "FUNCTION_MODELS", OpenRouterClient.FUNCTION_MODELS)
    monkeypatch.setattr(profiles, "_active_profile", profiles._active_profile)
    rebuild_function_models()
    return monkeypatch


def _configure(monkeypatch, shape: str) -> None:
    for name, value in CONFIGS[shape].items():
        monkeypatch.setattr(settings, name, value)
    rebuild_function_models()


def _active(stem: str) -> None:
    profiles.set_profile(profiles.ProjectProfile(stem=stem))


# ── the old expressions, copied out, as the reference ──────────────────────────────────────────

def _old_independent(client) -> str | None:
    candidate = settings.model_premium or settings.model_architecture
    if not candidate or candidate == settings.model_engineering:
        return None
    return candidate


def _old_get_model(client, function: str) -> str:
    if function == "independent":
        return _old_independent(client) or settings.model_engineering
    return client.FUNCTION_MODELS.get(function, settings.model_engineering)


class TestAnEmptySettingResolvesEveryTierAsBefore:
    @pytest.mark.parametrize("stem", profiles.list_profiles())
    @pytest.mark.parametrize("shape", list(CONFIGS))
    def test_every_accessor_equals_the_old_expression(self, globals_, stem, shape):
        _configure(globals_, shape)
        profiles.set_profile(profiles.load_profile(stem))
        client = OpenRouterClient(api_key="test")
        for tier in (*PINNABLE_TIERS, "independent", "not_a_tier"):
            assert client.get_model(tier) == _old_get_model(client, tier), (stem, shape, tier)
        assert client.independent_model() == _old_independent(client)
        assert client.recompute_model() == client.FUNCTION_MODELS.get("recompute")
        assert client.decision_model() == client.FUNCTION_MODELS.get("decision")

    @pytest.mark.parametrize("stem", profiles.list_profiles())
    @pytest.mark.parametrize("order, expect", [
        ("", {"triage": [], "search": [], "independent": []}),
        ("StreamLake", {"triage": ["StreamLake"], "search": ["StreamLake"],
                        "independent": ["StreamLake"]}),
        ("triage:StreamLake,Together", {"triage": ["StreamLake"], "search": ["Together"],
                                         "independent": ["Together"]}),
        ("Together,search:", {"triage": ["Together"], "search": [], "independent": ["Together"]}),
    ])
    def test_the_provider_order_is_the_global_one(self, globals_, stem, order, expect):
        globals_.setattr(settings, "openrouter_provider_order", order)
        profiles.set_profile(profiles.load_profile(stem))
        for function, providers in expect.items():
            assert provider_order_for(function) == providers, (stem, order, function)

    def test_the_profile_is_not_even_asked_when_no_pin_is_set(self, globals_):
        """The empty setting must cost one dict read and cannot fail on an odd profile."""
        calls = []
        globals_.setattr(profiles, "get_profile", lambda: calls.append(1) or profiles.ProjectProfile())
        client = OpenRouterClient(api_key="test")
        client.get_model("engineering")
        client.independent_model()
        provider_order_for("triage")
        assert calls == []


class TestAPinIsTheModelItsProfileReads:
    def test_the_named_tier_reads_the_pin_and_the_others_stay_global(self, globals_):
        globals_.setattr(settings, "profile_models", LINE)
        _active("legal")
        client = OpenRouterClient(api_key="test")
        assert client.get_model("engineering") == "vendor/legal-model"
        assert client.get_model("triage") == "g/triage"
        assert client.get_model("architecture") == "g/arch"

    def test_another_profile_reads_the_global_model(self, globals_):
        globals_.setattr(settings, "profile_models", LINE)
        client = OpenRouterClient(api_key="test")
        _active("general")
        assert client.get_model("engineering") == "g/eng"
        _active("finance")
        assert client.get_model("engineering") == "g/eng"
        assert client.get_model("triage") == "vendor/fin-triage"

    def test_the_next_call_follows_a_profile_switch(self, globals_):
        globals_.setattr(settings, "profile_models", LINE)
        client = OpenRouterClient(api_key="test")
        _active("legal")
        assert client.get_model("engineering") == "vendor/legal-model"
        _active("general")
        assert client.get_model("engineering") == "g/eng"

    def test_a_pin_turns_an_unset_optional_tier_on_for_its_profile_only(self, globals_):
        globals_.setattr(settings, "profile_models", LINE)
        client = OpenRouterClient(api_key="test")
        _active("legal")
        assert client.get_model("judge") == "vendor/legal-judge"
        assert client.recompute_model() == "vendor/legal-recompute"
        _active("general")
        assert client.get_model("judge") == "g/eng", "an unset judge falls back to engineering"
        assert client.recompute_model() is None, "an unset recompute still skips"

    def test_a_pin_replaces_a_tier_the_global_map_sets(self, globals_):
        _configure(globals_, "full")
        globals_.setattr(settings, "profile_models", LINE)
        client = OpenRouterClient(api_key="test")
        _active("legal")
        assert client.get_model("judge") == "vendor/legal-judge"
        assert client.recompute_model() == "vendor/legal-recompute"
        assert client.decision_model() == "g/decision"
        _active("general")
        assert client.get_model("judge") == "g/judge"
        assert client.recompute_model() == "g/recompute"

    def test_the_decision_tier_is_pinnable_and_has_no_fallback(self, globals_):
        globals_.setattr(settings, "profile_models", "legal:decision=vendor/legal-decider")
        client = OpenRouterClient(api_key="test")
        _active("legal")
        assert client.decision_model() == "vendor/legal-decider"
        _active("general")
        assert client.decision_model() is None

    def test_a_tier_nothing_sets_falls_back_to_the_profiles_own_engineering_model(self, globals_):
        globals_.setattr(settings, "profile_models", LINE)
        client = OpenRouterClient(api_key="test")
        _active("legal")
        assert client.get_model("ranker") == "vendor/legal-model"
        assert client.get_model("not_a_tier") == "vendor/legal-model"
        _active("general")
        assert client.get_model("ranker") == "g/eng"


class TestTheIndependentModelIsDerivedFromTheModelsTheProfileReads:
    def test_a_pinned_engineering_model_equal_to_architecture_leaves_no_honest_second_opinion(
            self, globals_):
        globals_.setattr(settings, "profile_models", "legal:engineering=g/arch")
        client = OpenRouterClient(api_key="test")
        _active("general")
        assert client.independent_model() == "g/arch"
        _active("legal")
        assert client.independent_model() is None
        assert client.get_model("independent") == "g/arch", "falls back to the pinned engineering model"

    def test_a_pinned_architecture_model_equal_to_engineering_leaves_none_either(self, globals_):
        globals_.setattr(settings, "profile_models", "legal:architecture=g/eng")
        client = OpenRouterClient(api_key="test")
        _active("legal")
        assert client.independent_model() is None

    def test_a_pinned_premium_model_is_the_independent_one(self, globals_):
        globals_.setattr(settings, "profile_models", "legal:premium=vendor/legal-premium")
        client = OpenRouterClient(api_key="test")
        _active("legal")
        assert client.independent_model() == "vendor/legal-premium"
        assert client.get_model("independent") == "vendor/legal-premium"
        _active("general")
        assert client.independent_model() == "g/arch"

    def test_a_pinned_premium_model_equal_to_the_pinned_engineering_one_is_refused(self, globals_):
        globals_.setattr(settings, "profile_models",
                         "legal:engineering=vendor/same,legal:premium=vendor/same")
        client = OpenRouterClient(api_key="test")
        _active("legal")
        assert client.independent_model() is None


class TestAPinCarriesItsOwnServing:
    def test_a_pin_with_a_provider_sends_that_provider_alone(self, globals_):
        globals_.setattr(settings, "openrouter_provider_order", "triage:StreamLake,Together")
        globals_.setattr(settings, "profile_models", LINE)
        _active("legal")
        assert provider_order_for("engineering") == ["vendor"]
        assert provider_order_for("triage") == ["StreamLake"], "a tier it did not pin is as before"
        assert provider_order_for("search") == ["Together"]

    def test_a_pin_without_a_provider_sends_none_even_when_a_global_order_exists(self, globals_):
        """The order was written for another model; a provider that does not host this one
        answers 404 under hard pins."""
        globals_.setattr(settings, "openrouter_provider_order", "Together")
        globals_.setattr(settings, "profile_models", LINE)
        _active("legal")
        assert provider_order_for("judge") == []
        assert provider_order_for("search") == ["Together"]

    def test_the_other_profiles_keep_the_global_order(self, globals_):
        globals_.setattr(settings, "openrouter_provider_order", "Together")
        globals_.setattr(settings, "profile_models", LINE)
        _active("general")
        assert provider_order_for("engineering") == ["Together"]
        _active("finance")
        assert provider_order_for("engineering") == ["Together"]
        assert provider_order_for("triage") == ["other"]

    def test_the_independent_call_follows_the_tier_that_supplies_it(self, globals_):
        globals_.setattr(settings, "openrouter_provider_order", "Together")
        globals_.setattr(settings, "profile_models",
                         "legal:premium=vendor/legal-premium@vendor-p,legal:architecture=vendor/a@vendor-a")
        _active("legal")
        assert provider_order_for("independent") == ["vendor-p"], "premium supplies it"
        globals_.setattr(settings, "profile_models", "legal:architecture=vendor/a@vendor-a")
        assert provider_order_for("independent") == ["vendor-a"], "no premium: architecture does"
        globals_.setattr(settings, "profile_models", "legal:triage=vendor/t@vendor-t")
        assert provider_order_for("independent") == ["Together"], "no pin on it: as before"

    def test_function_names_fold_to_lower_case_as_the_global_order_does(self, globals_):
        globals_.setattr(settings, "profile_models", LINE)
        _active("legal")
        assert provider_order_for("ENGINEERING") == ["vendor"]


class TestTheRequestThatLeavesCarriesThePin:
    async def _sent(self, monkeypatch, function):
        captured: dict = {}

        class FakeResponse:
            status_code = 200
            text = ""

            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}}

        class FakeHttp:
            async def post(self, path, json):
                captured.update(json)
                return FakeResponse()

        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=FakeHttp()))
        monkeypatch.setattr(settings, "openrouter_provider_fallbacks", "")
        await client.chat(function=function, system_prompt="s", user_message="u")
        return captured

    async def test_the_pinned_profile_sends_the_pinned_model_and_its_provider(self, globals_):
        globals_.setattr(settings, "profile_models", LINE)
        _active("legal")
        sent = await self._sent(globals_, "engineering")
        assert sent["model"] == "vendor/legal-model"
        assert sent["provider"] == {"order": ["vendor"], "allow_fallbacks": False}

    async def test_the_same_request_under_another_profile_sends_the_global_model(self, globals_):
        globals_.setattr(settings, "profile_models", LINE)
        _active("general")
        sent = await self._sent(globals_, "engineering")
        assert sent["model"] == "g/eng"
        assert "provider" not in sent

    async def test_a_pin_without_a_provider_sends_no_provider_block(self, globals_):
        globals_.setattr(settings, "openrouter_provider_order", "Together")
        globals_.setattr(settings, "profile_models", LINE)
        _active("legal")
        sent = await self._sent(globals_, "judge")
        assert sent["model"] == "vendor/legal-judge"
        assert "provider" not in sent

    async def test_a_call_that_names_its_own_serving_is_not_reached_by_a_pin(self, globals_):
        """The tier-3 arms name a model on the call and a function of their own ('tier3_arm_a'),
        and take their provider from 'tier3_arm_a:Provider'. A pin keys on a tier, so it cannot
        reach them, even under the profile that pins every tier it can."""
        globals_.setattr(settings, "openrouter_provider_order", "tier3_arm_a:Provider")
        globals_.setattr(settings, "profile_models", LINE)
        _active("legal")
        captured: dict = {}

        class FakeResponse:
            status_code = 200
            text = ""

            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}}

        class FakeHttp:
            async def post(self, path, json):
                captured.update(json)
                return FakeResponse()

        client = OpenRouterClient(api_key="test")
        globals_.setattr(client, "_get_client", AsyncMock(return_value=FakeHttp()))
        globals_.setattr(settings, "openrouter_provider_fallbacks", "")
        await client.chat(function="tier3_arm_a", system_prompt="s", user_message="u",
                          model="arm/own-model")
        assert captured["model"] == "arm/own-model"
        assert captured["provider"]["order"] == ["Provider"]


class TestTheGatesThatAskWhetherATierIsConfigured:
    """A pin on a tier the global map leaves unset turns the capability on for that profile."""

    def test_the_ranker_tier_ranks_for_the_profile_that_pins_it(self, globals_):
        import autornd.knowledge.context as ctx

        globals_.setattr(settings, "model_research", "")
        globals_.setattr(settings, "profile_models", "legal:ranker=vendor/legal-ranker")
        _active("general")
        assert ctx._rank_tier() is None
        _active("legal")
        assert ctx._rank_tier() == "ranker"

    def test_a_pinned_research_model_ranks_when_there_is_no_ranker(self, globals_):
        import autornd.knowledge.context as ctx

        globals_.setattr(settings, "model_research", "")
        globals_.setattr(settings, "profile_models", "legal:research=vendor/legal-research")
        _active("general")
        assert ctx._rank_tier() is None
        _active("legal")
        assert ctx._rank_tier() == "research"

    async def test_the_reranker_is_asked_with_the_pinned_ranker_model(self, globals_):
        import autornd.knowledge.context as ctx

        globals_.setattr(settings, "model_ranker", "g/ranker")
        globals_.setattr(settings, "profile_models", "legal:ranker=vendor/legal-ranker")
        globals_.setattr(ctx, "_rerank_mode", None)
        _active("legal")
        client = AsyncMock()
        client.rerank = AsyncMock(return_value=[(0, 0.9), (1, 0.8)])
        cands = [{"text": f"c{i}", "tag": f"t{i}", "distance": i / 10} for i in range(6)]
        await ctx.rerank_chunks(client, "q", cands, keep=2)
        assert client.rerank.call_args.kwargs["model"] == "vendor/legal-ranker"

    async def test_expansion_runs_for_the_profile_that_pins_a_research_model(self, globals_):
        import autornd.knowledge.context as ctx

        globals_.setattr(settings, "model_research", "")
        globals_.setattr(settings, "profile_models", "legal:research=vendor/legal-research")
        client = AsyncMock()
        client.chat_json = AsyncMock(return_value=({"queries": ["a statute"]}, None))
        _active("general")
        assert await ctx.expand_queries(client, "a request") == ["a request"]
        client.chat_json.assert_not_called()
        _active("legal")
        assert await ctx.expand_queries(client, "a request") == ["a statute"]
        assert client.chat_json.call_args.kwargs["function"] == "research"

    async def test_the_lookup_runs_for_the_profile_that_pins_a_search_model(self, globals_):
        """The gate sits first in research_gaps: unpinned it returns at once, pinned it goes on
        to the call, which this client refuses, so the refusal reaching us is the proof."""
        from autornd.knowledge import research
        from autornd.routing.openrouter import BudgetExceeded

        globals_.setattr(settings, "model_search", "")
        globals_.setattr(settings, "profile_models", "legal:search=vendor/legal-search")
        client = AsyncMock()
        client.chat = AsyncMock(side_effect=BudgetExceeded("stopped"))
        client.chat_json = AsyncMock(side_effect=BudgetExceeded("stopped"))
        globals_.setattr(research, "retrieve", lambda *a, **k: [])
        _active("general")
        assert await research.research_gaps(client, "a request", ["a gap"], max_tokens=100) == []
        _active("legal")
        with pytest.raises(BudgetExceeded):
            await research.research_gaps(client, "a request", ["a gap"], max_tokens=100)

    async def test_the_reader_reads_for_the_profile_that_pins_it(self, globals_):
        from autornd.knowledge import research

        calls: list[str] = []

        async def fake_readers(client, question, pages, terms):
            calls.append(question)
            return {}

        globals_.setattr(research, "_read_with_readers", fake_readers)
        globals_.setattr(research, "fetch_source", _no_page)
        globals_.setattr(research, "_note_fetch", lambda *a, **k: None)
        globals_.setattr(settings, "model_reader", "")
        globals_.setattr(settings, "profile_models", "legal:reader=vendor/legal-reader")
        near = {"https://example.org/a": "a statute"}
        _active("general")
        await research._read_documents(near, set(), client=AsyncMock(), question="q")
        assert calls == []
        _active("legal")
        await research._read_documents(near, set(), client=AsyncMock(), question="q")
        assert calls == ["q"]


async def _no_page(url):
    from autornd.knowledge.fetch import Source

    return Source(url=url, status="failed", reason="not fetched in this test")


class TestThePremiumRoutes:
    """The double-check estimate asks whether a premium model is configured, and which one."""

    async def _workflow(self, db_session):
        import json

        from autornd.models.workflow import PhaseResult, Workflow, WorkflowStatus

        w = Workflow(request="a request", status=WorkflowStatus.COMPLETED)
        db_session.add(w)
        await db_session.flush()
        db_session.add(PhaseResult(
            workflow_id=w.id, phase="plan", iteration=1,
            verdict_json=json.dumps({"ready": True, "plan": "p", "blockers": [],
                                     "success_criteria": []}),
            model_used="test", cost=0.001))
        await db_session.commit()
        return w.id

    async def test_the_estimate_is_open_to_the_profile_that_pins_a_premium_model(
            self, globals_, api_client, db_session):
        globals_.setattr(settings, "model_premium", "")
        globals_.setattr(settings, "profile_models", "legal:premium=vendor/legal-premium")
        workflow_id = await self._workflow(db_session)
        _active("general")
        refused = await api_client.get(f"/api/workflows/{workflow_id}/doublecheck/estimate")
        assert refused.status_code == 404
        assert refused.json()["detail"] == "Premium model not configured"
        _active("legal")
        answered = await api_client.get(f"/api/workflows/{workflow_id}/doublecheck/estimate")
        assert answered.status_code == 200
        assert answered.json()["data"]["model"] == "vendor/legal-premium"

    async def test_the_run_route_is_open_to_it_too(self, globals_, api_client):
        globals_.setattr(settings, "model_premium", "")
        globals_.setattr(settings, "profile_models", "legal:premium=vendor/legal-premium")
        _active("general")
        refused = await api_client.post("/api/workflows/999/doublecheck")
        assert refused.json()["detail"] == "Premium model not configured"
        _active("legal")
        past_the_gate = await api_client.post("/api/workflows/999/doublecheck")
        assert past_the_gate.json()["detail"] != "Premium model not configured"

    async def test_health_names_the_premium_model_the_active_profile_would_use(
            self, globals_, api_client):
        globals_.setattr(settings, "model_premium", "")
        globals_.setattr(settings, "profile_models", "legal:premium=vendor/legal-premium")
        _active("general")
        assert (await api_client.get("/api/health")).json()["premium_model"] is None
        _active("legal")
        assert (await api_client.get("/api/health")).json()["premium_model"] == "vendor/legal-premium"


class TestTheOtherGatesInTheKnowledgeLayer:
    """The remaining places that ask whether a tier is configured at all."""

    async def test_the_needs_sources_switch_is_asked_for_the_profile_that_pins_a_search_model(
            self, globals_):
        import autornd.knowledge.context as ctx

        asked: list[str] = []

        async def fake_route(name, evidence):
            asked.append(name)
            return "default"

        globals_.setattr(ctx, "route_for", fake_route)
        globals_.setattr(settings, "model_search", "")
        globals_.setattr(settings, "profile_models", "legal:search=vendor/legal-search")
        _active("general")
        assert await ctx._lookup_wanted("Size the heater.", "high") == (False, True)
        assert asked == [], "no search model, so no switch is asked"
        _active("legal")
        assert await ctx._lookup_wanted("Size the heater.", "high") == (False, True)
        assert asked == ["needs_sources"]

    async def test_scoping_runs_for_the_profile_that_pins_a_research_model(self, globals_):
        import autornd.knowledge.context as ctx
        from autornd.routing.openrouter import BudgetExceeded

        globals_.setattr(settings, "model_research", "")
        globals_.setattr(settings, "profile_models", "legal:research=vendor/legal-research")
        client = AsyncMock()
        client.chat_json = AsyncMock(side_effect=BudgetExceeded("stopped"))
        _active("general")
        assert await ctx.analyze_request(client, "a request") == ("", [])
        client.chat_json.assert_not_called()
        _active("legal")
        with pytest.raises(BudgetExceeded):
            await ctx.analyze_request(client, "a request")

    async def test_the_briefing_is_written_for_the_profile_that_pins_a_research_model(
            self, globals_):
        import autornd.knowledge.context as ctx
        from autornd.routing.openrouter import BudgetExceeded

        globals_.setattr(settings, "model_research", "")
        globals_.setattr(settings, "profile_models", "legal:research=vendor/legal-research")
        chunks = [{"text": f"excerpt {i}", "tag": "docs", "distance": 0.1 * i, "source": "d.md"}
                  for i in range(3)]
        client = AsyncMock()
        client.chat_json = AsyncMock(side_effect=BudgetExceeded("stopped"))
        _active("general")
        await ctx.synthesize_briefing(client, "a request", chunks)
        client.chat_json.assert_not_called()
        _active("legal")
        with pytest.raises(BudgetExceeded):
            await ctx.synthesize_briefing(client, "a request", chunks)


# Where a tier setting is read directly on purpose: these build or rebuild the GLOBAL map, which is
# what every profile reads for a tier it has not pinned. Every other reader asks tier_model(), whose
# second argument is the setting it read before pins existed.
GLOBAL_READERS = {
    ("routing/openrouter.py", "OpenRouterClient"),         # the FUNCTION_MODELS table, built at import
    ("routing/openrouter.py", "check_models"),             # confirms the global map
    ("routing/openrouter.py", "rebuild_function_models"),  # rebuilds that table
}
TIER_SETTINGS = {f"model_{tier}" for tier in PINNABLE_TIERS}


class _TierSettingReads(ast.NodeVisitor):
    """Every `settings.model_<tier>` that is not an argument of a tier_model() call."""

    def __init__(self):
        self.scope: list[str] = []
        self.inside_tier_model = 0
        self.hits: list[tuple[str, int]] = []

    def _scoped(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scoped

    def visit_Call(self, node):
        is_pin_read = isinstance(node.func, ast.Name) and node.func.id == "tier_model"
        self.inside_tier_model += is_pin_read
        self.generic_visit(node)
        self.inside_tier_model -= is_pin_read

    def visit_Attribute(self, node):
        if (isinstance(node.value, ast.Name) and node.value.id == "settings"
                and node.attr in TIER_SETTINGS and not self.inside_tier_model):
            self.hits.append((self.scope[-1] if self.scope else "<module>", node.lineno))
        self.generic_visit(node)


def _direct_readers() -> list[tuple[str, str, int]]:
    package = Path(autornd.__file__).resolve().parent
    found = []
    for path in sorted(package.rglob("*.py")):
        scan = _TierSettingReads()
        scan.visit(ast.parse(path.read_text(encoding="utf-8")))
        found += [(path.relative_to(package).as_posix(), scope, line) for scope, line in scan.hits]
    return found


class TestNoTierIsReadAroundThePins:
    """A reader added later that asks `settings.model_<tier>` directly would run a profile on the
    global model while its pin says otherwise, and no behaviour test would notice until that path
    ran. This reads the source for it. The twelve gates in knowledge/context.py and
    knowledge/research.py, and the premium routes, sit inside long flows; this is what holds each
    of them."""

    def test_every_reader_but_the_global_map_asks_the_overlay(self):
        stray = [(path, scope, line) for path, scope, line in _direct_readers()
                 if (path, scope) not in GLOBAL_READERS]
        assert stray == [], (
            "these read a tier setting without tier_model(); a pin would not reach them: "
            f"{stray}")

    def test_the_allowed_readers_still_read_and_the_scan_sees_them(self):
        """A scan that found nothing would pass on any tree."""
        seen = {(path, scope) for path, scope, _ in _direct_readers()}
        assert seen == GLOBAL_READERS

    def test_the_scan_catches_a_direct_read_and_lets_the_overlay_pass(self):
        direct = _TierSettingReads()
        direct.visit(ast.parse("def f():\n    return settings.model_search\n"))
        assert direct.hits == [("f", 2)]
        through = _TierSettingReads()
        through.visit(ast.parse('def f():\n    return tier_model("search", settings.model_search)\n'))
        assert through.hits == []
