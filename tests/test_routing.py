"""Test OpenRouter client and model routing."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from autornd.config import settings
from autornd.routing.openrouter import (
    OpenRouterClient,
    check_models,
    rebuild_function_models,
)


class TestModelRouting:
    """Tiers are a contract; which model fills a tier is the operator's choice."""

    TIERS = ("triage", "engineering", "architecture", "research", "escalation")

    def test_each_tier_resolves_to_its_configured_model(self):
        client = OpenRouterClient(api_key="test")
        for tier in self.TIERS:
            assert client.get_model(tier) == getattr(settings, f"model_{tier}")

    def test_every_tier_is_routable(self):
        client = OpenRouterClient(api_key="test")
        for tier in self.TIERS:
            assert client.get_model(tier), f"{tier} resolved to nothing"

    def test_tiers_are_independently_configurable(self, monkeypatch):
        monkeypatch.setattr(settings, "model_triage", "vendor-a/cheap")
        monkeypatch.setattr(settings, "model_architecture", "vendor-b/heavy")
        rebuild_function_models()
        client = OpenRouterClient(api_key="test")
        assert client.get_model("triage") == "vendor-a/cheap"
        assert client.get_model("architecture") == "vendor-b/heavy"

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


@pytest.mark.asyncio
class TestCostEstimation:
    """Rates come from the provider catalogue, never from a table in this repo —
    AutoRnD hardcodes no models, so it cannot hardcode their prices either."""

    def test_uses_catalogue_rates(self, monkeypatch):
        import autornd.routing.openrouter as orr

        monkeypatch.setitem(orr._model_pricing, "vendor/some-model", (2e-6, 8e-6))
        cost = OpenRouterClient._estimate_cost("vendor/some-model", 1000, 500)
        assert abs(cost - (1000 * 2e-6 + 500 * 8e-6)) < 1e-12

    def test_unknown_model_is_zero_not_invented(self, monkeypatch):
        import autornd.routing.openrouter as orr

        monkeypatch.setattr(orr, "_model_pricing", {})
        assert OpenRouterClient._estimate_cost("vendor/never-seen", 1000, 500) == 0.0

    async def test_catalogue_check_records_pricing(self):
        import autornd.routing.openrouter as orr

        resp = self._cat({"data": [
            {"id": settings.model_triage,
             "pricing": {"prompt": "0.000001", "completion": "0.000004"}},
        ]})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def _get(url, **kw):
            if url.endswith("/endpoints"):
                return httpx.Response(404, json={}, request=httpx.Request("GET", url))
            return resp

        mock_client.get = AsyncMock(side_effect=_get)
        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            await check_models()
        assert orr._model_pricing[settings.model_triage] == (0.000001, 0.000004)

    @staticmethod
    def _cat(data):
        return httpx.Response(
            200, json=data,
            request=httpx.Request("GET", "https://openrouter.ai/api/v1/models"),
        )


@pytest.mark.asyncio
class TestCheckModels:
    @staticmethod
    def _mock_response(data):
        req = httpx.Request("GET", "https://openrouter.ai/api/v1/models")
        return httpx.Response(200, json=data, request=req)

    @staticmethod
    def _mock_client(resp, endpoints_ok=()):
        """Dispatches by URL like the real API: the bulk catalogue on /models,
        per-model confirmation on /models/<id>/endpoints."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def _get(url, **kw):
            if url.endswith("/endpoints"):
                model_id = url.rsplit("/models/", 1)[-1].rsplit("/endpoints", 1)[0]
                code = 200 if model_id in endpoints_ok else 404
                return httpx.Response(code, json={"data": {}},
                                      request=httpx.Request("GET", url))
            return resp

        mock_client.get = AsyncMock(side_effect=_get)
        return mock_client

    async def test_requests_the_providers_catalogue_url(self):
        """Regression: the URL was built by stripping /v1 and re-appending /api/v1,
        which produced .../api/api/v1/models and 404'd on every startup."""
        mock_client = self._mock_client(self._mock_response({"data": []}))
        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            await check_models()

        requested = mock_client.get.call_args_list[0][0][0]
        expected = settings.openrouter_base_url.rstrip("/") + "/models"
        assert requested == expected, f"requested {requested!r}, expected {expected!r}"
        assert "/api/api/" not in requested

    async def test_marks_available_models(self):
        configured = [
            settings.model_triage, settings.model_engineering,
            settings.model_architecture, settings.model_research,
            settings.model_escalation,
        ]
        resp = self._mock_response({"data": [{"id": m} for m in configured]})
        mock_client = self._mock_client(resp)

        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            status = await check_models()

        assert status["triage"]["available"] is True
        assert status["engineering"]["available"] is True

    async def test_marks_missing_model_unavailable(self):
        resp = self._mock_response({"data": [{"id": settings.model_triage}]})
        mock_client = self._mock_client(resp)

        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            status = await check_models()

        assert status["triage"]["available"] is True
        assert status["engineering"]["available"] is False
        assert status["architecture"]["available"] is False

    async def test_unreachable_catalogue_leaves_availability_unknown(self):
        """Unknown must stay None so /api/health can report degraded, not ok."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("no route"))

        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            status = await check_models()

        assert all(s["available"] is None for s in status.values())

    async def test_catalogue_check_works_without_an_api_key(self, monkeypatch):
        """Regression: a blank key produced `Bearer `, which httpx rejects outright —
        so tier ids could not be validated until a key was pasted, which is exactly
        when validating them is most useful."""
        monkeypatch.setattr(settings, "openrouter_api_key", "")
        mock_client = self._mock_client(self._mock_response({"data": []}))

        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            await check_models()

        headers = mock_client.get.call_args_list[0].kwargs.get("headers", {})
        assert "Authorization" not in headers, "must not send an empty bearer token"

    async def test_catalogue_check_authenticates_when_a_key_is_set(self, monkeypatch):
        monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-123")
        mock_client = self._mock_client(self._mock_response({"data": []}))

        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            await check_models()

        headers = mock_client.get.call_args_list[0].kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer sk-test-123"

    async def test_non_chat_models_are_confirmed_individually(self, monkeypatch):
        """Regression: /models lists chat models only. A reranker or embedding
        model a provider genuinely serves is absent from it, and must not be
        reported missing on that basis alone."""
        monkeypatch.setattr(settings, "model_research", "qwen/qwen3-reranker-8b")
        rebuild_function_models()
        catalogue = self._mock_response({"data": [
            {"id": settings.model_triage}, {"id": settings.model_engineering},
            {"id": settings.model_architecture}, {"id": settings.model_escalation},
        ]})
        mock_client = self._mock_client(catalogue, endpoints_ok={"qwen/qwen3-reranker-8b"})

        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            status = await check_models()

        assert status["research"]["available"] is True, "reranker wrongly marked missing"
        assert status["triage"]["available"] is True

    async def test_genuinely_absent_model_still_reported(self, monkeypatch):
        monkeypatch.setattr(settings, "model_research", "vendor/not-real")
        rebuild_function_models()
        catalogue = self._mock_response({"data": [{"id": settings.model_triage}]})
        mock_client = self._mock_client(catalogue, endpoints_ok=())

        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            status = await check_models()

        assert status["research"]["available"] is False


@pytest.mark.asyncio
class TestSchemaRetry:
    """Regression: a response that parsed as JSON but did not match the verdict
    schema was raised straight to the caller with no retry, failing a whole
    workflow on one malformed reply."""

    @staticmethod
    def _client(contents):
        from autornd.routing.openrouter import ModelResponse

        client = OpenRouterClient(api_key="test")
        seq = iter(contents)

        async def _chat(**kw):
            return ModelResponse(content=next(seq), model="m",
                                 prompt_tokens=1, completion_tokens=1, cost=0.0)

        client.chat = AsyncMock(side_effect=_chat)
        return client

    async def test_retries_until_the_shape_is_right(self):
        from autornd.models.verdicts import TriageVerdict

        good = json.dumps({"domains": ["backend"], "risk": "low",
                           "specialists": ["backend_engineer"], "summary": "ok"})
        client = self._client(['{": ": "domains"}', good])
        data, _ = await client.chat_json(
            function="triage", system_prompt="s", user_message="u",
            schema=TriageVerdict,
        )
        assert data["domains"] == ["backend"]
        assert client.chat.call_count == 2

    async def test_gives_up_after_max_retries(self):
        from pydantic import ValidationError
        from autornd.models.verdicts import TriageVerdict

        client = self._client(['{"wrong": 1}'] * 3)
        # don't actually sit through the exponential backoff
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        with pytest.raises(ValidationError):
            await client.chat_json(
                function="triage", system_prompt="s", user_message="u",
                schema=TriageVerdict, max_retries=3,
            )
        monkeypatch.undo()

    async def test_no_schema_means_no_shape_check(self):
        client = self._client(['{"anything": true}'])
        data, _ = await client.chat_json(
            function="triage", system_prompt="s", user_message="u",
        )
        assert data == {"anything": True}


@pytest.mark.asyncio
class TestEmptyReplyDiagnostics:
    """An empty reply used to read only as "model returned no text", which hides
    the common cause: a reasoning model spending its whole token budget on
    reasoning and returning finish_reason=length with nothing to show."""

    @staticmethod
    def _client(finish_reason, provider="SomeProvider", completion_tokens=50):
        from autornd.routing.openrouter import ModelResponse

        client = OpenRouterClient(api_key="test")
        client.chat = AsyncMock(return_value=ModelResponse(
            content="", model="vendor/reasoner", prompt_tokens=10,
            completion_tokens=completion_tokens, cost=0.0,
            finish_reason=finish_reason, provider=provider))
        return client

    async def test_length_explains_the_reasoning_budget(self, monkeypatch):
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        client = self._client("length")
        with pytest.raises(ValueError) as exc:
            await client.chat_json(function="architecture", system_prompt="s",
                                   user_message="u", max_retries=2)
        msg = str(exc.value)
        assert "finish_reason=length" in msg
        assert "reasoning model" in msg
        assert "max_tokens" in msg

    async def test_other_empties_name_the_provider(self, monkeypatch):
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        client = self._client("stop", provider="Flaky")
        with pytest.raises(ValueError) as exc:
            await client.chat_json(function="architecture", system_prompt="s",
                                   user_message="u", max_retries=2)
        assert "provider=Flaky" in str(exc.value)
        assert "reasoning model" not in str(exc.value)
