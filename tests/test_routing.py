"""Test OpenRouter client and model routing."""

import json

import pytest

from autornd.routing.openrouter import OpenRouterClient


class TestModelRouting:
    def test_triage_routes_to_deepseek(self):
        client = OpenRouterClient(api_key="test")
        model = client.get_model("triage")
        assert model == "deepseek/deepseek-v4-flash"

    def test_engineering_routes_to_minimax(self):
        client = OpenRouterClient(api_key="test")
        model = client.get_model("engineering")
        assert model == "minimax/minimax-m3"

    def test_architecture_routes_to_glm(self):
        client = OpenRouterClient(api_key="test")
        model = client.get_model("architecture")
        assert model == "z-ai/glm-5.3"

    def test_research_routes_to_gemini(self):
        client = OpenRouterClient(api_key="test")
        model = client.get_model("research")
        assert model == "google/gemini-2.5-flash"

    def test_escalation_routes_to_k3(self):
        client = OpenRouterClient(api_key="test")
        model = client.get_model("escalation")
        assert model == "moonshotai/kimi-k3"

    def test_unknown_function_defaults_to_engineering(self):
        client = OpenRouterClient(api_key="test")
        model = client.get_model("unknown_function")
        assert model == client.get_model("engineering")


class TestJsonExtraction:
    def test_plain_json(self):
        result = OpenRouterClient._extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = OpenRouterClient._extract_json(text)
        assert result == {"key": "value"}

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = OpenRouterClient._extract_json(text)
        assert result["outer"]["inner"] == [1, 2, 3]

    def test_think_tags_stripped(self):
        text = '<think>some reasoning</think>\n{"key": "value"}'
        result = OpenRouterClient._extract_json(text)
        assert result == {"key": "value"}

    def test_rejects_non_dict(self):
        with pytest.raises(ValueError, match="Expected JSON object"):
            OpenRouterClient._extract_json("42")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Empty response"):
            OpenRouterClient._extract_json("")


class TestCostEstimation:
    def test_known_model(self):
        cost = OpenRouterClient._estimate_cost(
            "deepseek/deepseek-v4-flash", 1000, 500
        )
        expected = (1000 * 0.07 + 500 * 0.14) / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_k3_cost_estimation(self):
        cost = OpenRouterClient._estimate_cost(
            "moonshotai/kimi-k3", 1000, 500
        )
        expected = (1000 * 3.00 + 500 * 12.00) / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_unknown_model_uses_default(self):
        cost = OpenRouterClient._estimate_cost("unknown/model", 1000, 500)
        expected = (1000 * 1.0 + 500 * 3.0) / 1_000_000
        assert abs(cost - expected) < 1e-10
