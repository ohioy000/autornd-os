"""Test OpenRouter client and model routing."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from autornd.routing.openrouter import OpenRouterClient, check_models


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
        assert model == "z-ai/glm-5.3-20260816"

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


@pytest.mark.asyncio
class TestCheckModels:
    @staticmethod
    def _mock_response(data):
        req = httpx.Request("GET", "https://openrouter.ai/api/v1/models")
        return httpx.Response(200, json=data, request=req)

    async def test_marks_available_models(self, monkeypatch):
        resp = self._mock_response({"data": [
            {"id": "deepseek/deepseek-v4-flash"},
            {"id": "minimax/minimax-m3"},
            {"id": "z-ai/glm-5.3-20260816"},
            {"id": "google/gemini-2.5-flash"},
            {"id": "moonshotai/kimi-k3"},
        ]})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=resp)

        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            status = await check_models()

        assert status["triage"]["available"] is True
        assert status["engineering"]["available"] is True

    async def test_marks_missing_model_unavailable(self, monkeypatch):
        resp = self._mock_response({"data": [
            {"id": "deepseek/deepseek-v4-flash"},
        ]})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=resp)

        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            status = await check_models()

        assert status["triage"]["available"] is True
        assert status["engineering"]["available"] is False
        assert status["architecture"]["available"] is False
