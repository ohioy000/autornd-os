"""Ruling D35: a heterogeneous judge tier.

domain_review, validate, review and rework_review route to a `judge` tier so a
different pretraining lineage judges the work. Optional with engineering
fallback: unset MODEL_JUDGE drops `judge` from the routing map, and those nodes
resolve to the engineering model — the prior homogeneous behaviour, nothing
breaks. Capped by JUDGE_MAX_TOKENS.
"""

from __future__ import annotations

from autornd.config import settings
from autornd.graph.spec import load
from autornd.routing.openrouter import OpenRouterClient


class TestJudgeRouting:
    def test_the_judging_nodes_route_to_the_judge_tier(self):
        spec = load("workflows/engineering-rnd.yaml")
        tier = {n.id: n.tier for n in spec.nodes if n.kind.value == "ai"}
        for node in ("domain_review", "validate", "review", "rework_review"):
            assert tier[node] == "judge", f"{node} should judge on the judge tier"

    def test_production_nodes_stay_on_engineering(self):
        spec = load("workflows/engineering-rnd.yaml")
        tier = {n.id: n.tier for n in spec.nodes if n.kind.value == "ai"}
        # The producer and the plan-pressure-test are not the judge.
        assert tier["implement"] == "engineering"
        assert tier["feasibility"] == "engineering"

    def test_the_judge_nodes_are_capped_by_judge_max_tokens(self):
        spec = load("workflows/engineering-rnd.yaml")
        mt = {n.id: n.max_tokens for n in spec.nodes if n.kind.value == "ai"}
        for node in ("domain_review", "validate", "review", "rework_review"):
            assert mt[node] == "judge_max_tokens", f"{node} must use the judge cap"


class TestJudgeFallback:
    def test_judge_falls_back_to_engineering_when_unset(self):
        """The optional-tier contract: no judge model → judging runs on the
        engineering model, exactly as it did before D35."""
        client = OpenRouterClient(api_key="test")
        if "judge" in client.FUNCTION_MODELS:
            # test env normally leaves MODEL_JUDGE empty; if a real one is set,
            # this case is not the one under test.
            return
        assert client.get_model("judge") == settings.model_engineering

    def test_judge_resolves_to_the_judge_model_when_set(self):
        client = OpenRouterClient(api_key="test")
        original = dict(client.FUNCTION_MODELS)
        try:
            client.FUNCTION_MODELS = {**original, "judge": "vendor/judge-x"}
            assert client.get_model("judge") == "vendor/judge-x"
        finally:
            client.FUNCTION_MODELS = original


class TestJudgeConfig:
    def test_judge_is_optional_not_required(self):
        from autornd.config import _OPTIONAL_TIERS, _TIER_HELP
        assert "model_judge" in _OPTIONAL_TIERS
        assert "model_judge" not in _TIER_HELP  # _TIER_HELP holds the required tiers

    def test_judge_max_tokens_defaults_tight_and_is_mutable(self):
        assert settings.judge_max_tokens == 8000
        assert "judge_max_tokens" in settings.RUNTIME_MUTABLE


class TestJudgeWiring:
    """The tier a node names must be the tier that serves it.

    D35's first cut moved the YAML to `tier: judge` but every judging phase
    called spec.run() with no function override, so Specialist.router_function
    (engineering) served the call and the judge tier billed nothing — the
    robotics live run proved it: judge configured and preflight-green, zero
    judge calls. These tests pin the override end to end.
    """

    def test_specialist_run_defaults_to_its_router_function(self):
        from autornd.specialists.registry import get_specialist
        from autornd.models.verdicts import SpecialistRole
        spec = get_specialist(SpecialistRole.TEST_ENGINEER)
        assert spec.router_function == "engineering"

    def test_specialist_run_accepts_a_function_override(self):
        import asyncio
        import inspect
        from autornd.specialists.base import Specialist
        sig = inspect.signature(Specialist.run)
        assert "function" in sig.parameters

        from autornd.models.verdicts import SpecialistRole
        from autornd.specialists.registry import get_specialist
        from tests.conftest import make_mock_client

        spec = get_specialist(SpecialistRole.TEST_ENGINEER)
        client = make_mock_client({"judge": {"concerns": [], "critical": False}})

        async def go():
            return await spec.run(client, "hi", function="judge")

        data, resp = asyncio.run(go())
        assert data == {"concerns": [], "critical": False}
        assert client.calls_by_function.get("judge", 0) == 1
        assert client.calls_by_function.get("engineering", 0) == 0

    def test_judge_phases_accept_a_function_override(self):
        import inspect
        from autornd.engine import phases
        for fn in (phases.run_domain_review, phases.run_validate, phases.run_review):
            assert "function" in inspect.signature(fn).parameters, (
                f"{fn.__name__} must accept function= so the adapter can route "
                "the node's tier through the specialist"
            )

    def test_adapter_routes_node_tier_to_judge_phases(self):
        import inspect
        from autornd.graph import adapter
        src = inspect.getsource(adapter.PhaseRunner._phase_domain_review)
        assert "self._tier(node, state)" in src
        src = inspect.getsource(adapter.PhaseRunner._phase_validate)
        assert "self._tier(node, state)" in src
        src = inspect.getsource(adapter.PhaseRunner._phase_review)
        assert "self._tier(node, state)" in src
