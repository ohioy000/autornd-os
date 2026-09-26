"""Test OpenRouter client and model routing.

No `@pytest.mark.asyncio` anywhere in this file. pyproject sets
`asyncio_mode = "auto"`, so async tests are collected without a mark — and a
class-level mark over a mixed sync/async class (TestCostEstimation) made
pytest warn once per sync test it held.
"""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from autornd.config import settings
from autornd.routing.openrouter import (
    BudgetExceeded,
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
        text = 'some reasoning\n{"key": "value"}'
        result = OpenRouterClient._extract_json(text)
        assert result == {"key": "value"}

    def test_rejects_non_dict(self):
        with pytest.raises(ValueError, match="Expected JSON object"):
            OpenRouterClient._extract_json("42")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Empty response"):
            OpenRouterClient._extract_json("")


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

    async def test_marks_missing_model_unavailable(self, monkeypatch):
        """A configured model absent from the catalogue reads unavailable.

        This used to build its catalogue from `settings.model_triage` alone and
        assert every other tier False — which silently assumed the tier ids are
        pairwise distinct. Nothing requires that: config permits one model to
        serve several tiers, and where two do, a catalogue "holding only triage"
        also holds the second tier's id, and the code correctly reports it
        available. The assertion failed live against correct code, so the test's
        premise was the bug, written down (convention 17). The tiers are pinned
        to distinct dummies now, so the test simulates the condition it watches
        — some configured ids present, the rest absent — whatever the local
        `.env` names.
        """
        for tier in ("triage", "engineering", "architecture",
                     "escalation", "research", "search"):
            monkeypatch.setattr(settings, f"model_{tier}", f"vendor/{tier}")
        resp = self._mock_response({"data": [{"id": "vendor/triage"}]})
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

    async def test_the_retry_is_told_what_was_wrong(self, monkeypatch):
        """Measured live: a triage reply used a value outside a closed enum and
        the retry re-asked the identical question, so nothing made the second
        answer more likely to be valid. The rejection text already lists every
        permitted value — send it.

        (The role that prompted this, `infrastructure_engineer`, is legal now:
        the roster is open. `risk` is still closed, and closed fields are where
        this matters.)"""
        from autornd.models.verdicts import TriageVerdict

        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        invented = json.dumps({"domains": ["appsec"], "risk": "catastrophic",
                               "specialists": ["test_engineer"],
                               "summary": "rotate signing keys"})
        good = json.dumps({"domains": ["appsec"], "risk": "critical",
                           "specialists": ["test_engineer"], "summary": "ok"})
        client = self._client([invented, good])
        data, _ = await client.chat_json(
            function="triage", system_prompt="s", user_message="ORIGINAL ASK",
            schema=TriageVerdict,
        )
        assert data["risk"] == "critical"

        first, second = [c.kwargs["user_message"] for c in client.chat.call_args_list]
        assert first == "ORIGINAL ASK"
        assert second.startswith("ORIGINAL ASK")
        assert "rejected" in second
        # the offending value and the permitted ones both reach the model
        assert "catastrophic" in second
        assert "critical" in second

    async def test_a_schema_violation_is_not_logged_as_a_parse_failure(self, caplog):
        """ValidationError subclasses ValueError, so the combined
        `except (JSONDecodeError, ValueError)` clause caught every schema
        violation first and the specific handler below it never ran — every
        wrong-shape reply was reported as bad JSON."""
        import logging
        from autornd.models.verdicts import TriageVerdict

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        good = json.dumps({"domains": ["backend"], "risk": "low",
                          "specialists": ["backend_engineer"], "summary": "ok"})
        bad = json.dumps({"domains": ["backend"], "risk": "nope",
                          "specialists": ["backend_engineer"], "summary": "x"})
        client = self._client([bad, good])
        with caplog.at_level(logging.WARNING):
            await client.chat_json(function="triage", system_prompt="s",
                                   user_message="u", schema=TriageVerdict)
        monkeypatch.undo()
        text = caplog.text
        assert "did not match TriageVerdict" in text
        assert "JSON parse failed" not in text


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
        from autornd.routing.openrouter import ProviderFailure

        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        client = self._client("length")
        with pytest.raises(ProviderFailure) as exc:
            await client.chat_json(function="architecture", system_prompt="s",
                                   user_message="u", max_retries=2)
        msg = str(exc.value)
        assert "finish_reason=length" in msg
        assert "reasoning model" in msg
        assert "max_tokens" in msg

    async def test_other_empties_name_the_provider(self, monkeypatch):
        from autornd.routing.openrouter import ProviderFailure

        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        client = self._client("stop", provider="Flaky")
        with pytest.raises(ProviderFailure) as exc:
            await client.chat_json(function="architecture", system_prompt="s",
                                   user_message="u", max_retries=2)
        assert "provider=Flaky" in str(exc.value)
        assert "reasoning model" not in str(exc.value)


class TestJsonExtraction:
    """Three of these shapes were seen live and each cost a full retry. One of
    them parsed into a valid-but-meaningless dict instead of failing, because
    the fence was stripped by dropping the first line positionally."""

    @staticmethod
    def _extract(text):
        return OpenRouterClient._extract_json(text)

    def test_a_fence_with_the_object_on_the_same_line(self):
        assert self._extract('```json {"risk": "low"}\n```') == {"risk": "low"}

    def test_no_newline_before_the_closing_fence(self):
        assert self._extract('```json\n{"risk": "low"}```') == {"risk": "low"}

    def test_preamble_before_the_object(self):
        assert self._extract('Here is the JSON:\n{"risk": "low"}') == {"risk": "low"}

    def test_prose_after_the_object(self):
        assert self._extract('{"risk": "low"}\nHope that helps!') == {"risk": "low"}

    def test_a_plain_object_is_untouched(self):
        assert self._extract('{"risk": "low"}') == {"risk": "low"}

    def test_braces_inside_strings_do_not_end_the_span(self):
        assert self._extract('{"summary": "use {this} pattern"}') == {
            "summary": "use {this} pattern"}

    def test_escaped_quotes_inside_strings(self):
        assert self._extract(r'{"summary": "a \"quoted\" word"}') == {
            "summary": 'a "quoted" word'}

    def test_a_reasoning_block_is_stripped(self):
        assert self._extract('weighing it up\n{"risk": "low"}') == {
            "risk": "low"}

    def test_genuinely_broken_json_still_raises(self):
        """Recovering harder must not become guessing."""
        with pytest.raises(json.JSONDecodeError):
            self._extract('{"risk": ')

    def test_a_non_object_is_rejected(self):
        with pytest.raises(ValueError):
            self._extract('[1, 2, 3]')

    def test_empty_content_is_rejected(self):
        with pytest.raises(ValueError):
            self._extract('')


class TestAccounting:
    """Spend and call counts live on the client because that is the one object
    every request must pass through.

    They used to be tallied by the phase runner inside `run_ai`, so the three
    most expensive paths were free as far as any report was concerned: research
    lookups (`research.py`), context expansion and synthesis (four sites in
    `context.py`), and reranking, whose cost was read into a debug log and
    discarded. Eight sectors making roughly thirty-two search calls
    self-reported $0.0025.
    """

    def test_a_fresh_client_has_spent_nothing(self):
        c = OpenRouterClient(api_key="test")
        assert c.spend == 0.0 and c.calls == 0
        assert c.spend_by_function == {} and c.calls_by_function == {}

    def test_accounting_is_per_tier(self):
        c = OpenRouterClient(api_key="test")
        c._account("search", 0.012)
        c._account("search", 0.008)
        c._account("triage", 0.0001)
        assert c.calls == 3
        assert c.calls_by_function == {"search": 2, "triage": 1}
        assert round(c.spend, 5) == 0.0201
        assert round(c.spend_by_function["search"], 4) == 0.02

    def test_a_free_call_still_counts_as_a_call(self):
        """A zero-cost reply is still a request that took time and could fail."""
        c = OpenRouterClient(api_key="test")
        c._account("triage", 0.0)
        assert c.calls == 1 and c.spend == 0.0

    def test_reset_clears_everything(self):
        c = OpenRouterClient(api_key="test")
        c._account("search", 0.01)
        c.reset_accounting()
        assert c.spend == 0.0 and c.calls == 0 and c.spend_by_function == {}

    def test_a_call_ceiling_stops_the_next_call(self):
        c = OpenRouterClient(api_key="test")
        c.call_ceiling = 2
        c._account("search", 0.01)
        c._account("search", 0.01)
        with pytest.raises(BudgetExceeded, match="ceiling 2"):
            c._account("search", 0.01)

    def test_a_spend_ceiling_stops_the_next_call(self):
        c = OpenRouterClient(api_key="test")
        c.spend_ceiling = 0.015
        c._account("search", 0.01)
        with pytest.raises(BudgetExceeded, match=r"\$0.0200"):
            c._account("search", 0.01)

    def test_the_budget_message_names_the_tiers(self):
        """A budget abort should say where the money went, or the next thing
        anyone does is re-run it to find out."""
        c = OpenRouterClient(api_key="test")
        c.call_ceiling = 1
        c._account("search", 0.5)
        with pytest.raises(BudgetExceeded, match="search"):
            c._account("triage", 0.0001)

    def test_no_ceiling_means_no_limit(self):
        c = OpenRouterClient(api_key="test")
        for _ in range(50):
            c._account("triage", 0.001)
        assert c.calls == 50


class TestResearchIsBilled:
    """The regression that started this: a run whose only model call is a
    research lookup reported $0.0000, because research calls `client.chat`
    directly and never touch the phase runner that was doing the counting."""

    async def test_a_research_lookup_moves_the_clients_totals(self, monkeypatch):
        from autornd.knowledge import research

        client = OpenRouterClient(api_key="test")

        async def fake_chat(function, system_prompt, user_message, **kw):
            from autornd.routing.openrouter import ModelResponse
            response = ModelResponse(
                content="A: 4:1 burst ratio", model="mock-search",
                prompt_tokens=10, completion_tokens=20, cost=0.017,
                citations=["https://example.org/standard.pdf"])
            client._account(function, response.cost)
            return response

        monkeypatch.setattr(client, "chat", fake_chat)
        monkeypatch.setattr(research, "_remember", lambda finding: None)
        # Research checks the store before paying for a lookup; an empty store
        # is what makes this a test of the lookup path.
        monkeypatch.setattr(research, "retrieve", lambda *a, **kw: [])

        findings = await research.research_gaps(
            client, "a crane boom circuit", ["What burst ratio applies?"])

        assert len(findings) == 1 and findings[0].grounded
        assert client.calls == 1, "the lookup was not counted"
        assert round(client.spend, 4) == 0.017, "the lookup was not priced"
        assert "search" in client.spend_by_function


class TestRunnerReadsTheClient:
    async def test_total_cost_comes_from_the_client(self):
        from autornd.graph.adapter import PhaseRunner

        client = OpenRouterClient(api_key="test")
        runner = PhaseRunner(client)
        assert runner.total_cost == 0.0
        # a call made anywhere, by anything, reaches the runner's total
        client._account("search", 0.031)
        assert round(runner.total_cost, 4) == 0.031
        assert runner.total_calls == 1


class TestIndependentTier:
    """The independent pass must not be the model it is reviewing.

    `premium` is omitted from FUNCTION_MODELS when unset, and `get_model` falls
    back to the engineering model — so before this resolver existed, an
    "independent" review would have run on the same model that produced the
    work and every review of it.
    """

    def _settings(self, monkeypatch, premium="", architecture="vendor/arch",
                  engineering="vendor/eng"):
        from autornd.config import settings
        monkeypatch.setattr(settings, "model_premium", premium)
        monkeypatch.setattr(settings, "model_architecture", architecture)
        monkeypatch.setattr(settings, "model_engineering", engineering)
        return OpenRouterClient(api_key="test")

    def test_premium_wins_when_configured(self, monkeypatch):
        c = self._settings(monkeypatch, premium="vendor/premium")
        assert c.independent_model() == "vendor/premium"
        assert c.get_model("independent") == "vendor/premium"

    def test_it_falls_back_to_architecture(self, monkeypatch):
        """So the feature works without a second paid tier, on a family that did
        not produce the work."""
        c = self._settings(monkeypatch)
        assert c.independent_model() == "vendor/arch"

    def test_it_refuses_to_be_the_engineering_model(self, monkeypatch):
        c = self._settings(monkeypatch, architecture="vendor/eng")
        assert c.independent_model() is None

    def test_it_refuses_even_when_premium_names_the_engineering_model(self, monkeypatch):
        c = self._settings(monkeypatch, premium="vendor/eng")
        assert c.independent_model() is None

    def test_it_refuses_when_nothing_is_configured(self, monkeypatch):
        c = self._settings(monkeypatch, architecture="")
        assert c.independent_model() is None


class TestIndependentPassSkips:
    async def test_the_phase_skips_rather_than_faking_independence(self, monkeypatch):
        """When the only available model is the one under review, the pass
        records a skip. Claiming a second opinion that is the same model is
        worse than admitting there is none."""
        from autornd.config import settings
        from autornd.graph.adapter import PhaseRunner
        from autornd.graph.executor import ExecutionState

        monkeypatch.setattr(settings, "model_premium", "")
        monkeypatch.setattr(settings, "model_architecture", "vendor/eng")
        monkeypatch.setattr(settings, "model_engineering", "vendor/eng")

        runner = PhaseRunner(OpenRouterClient(api_key="test"))
        verdict, responses = await runner._phase_doublecheck(
            None, ExecutionState(request="r"))

        assert verdict["skipped"] is True
        assert "engineering model" in verdict["reason"]
        assert responses == [], "a skip must not cost a call"


class TestProviderVisibility:
    """A model id is not a system.

    The same id served by a different provider produced 70-token replies at a
    thirtieth of the price and classified four sectors differently between two
    runs of one eval suite. Without the provider recorded, that reads as a code
    regression.
    """

    def test_providers_are_recorded_per_tier(self):
        c = OpenRouterClient(api_key="test")
        c._account("triage", 0.0001, provider="OpenInference")
        c._account("triage", 0.0001, provider="StreamLake")
        c._account("search", 0.02, provider="Perplexity")
        assert c.providers_by_function["triage"] == {"OpenInference", "StreamLake"}
        assert c.providers_by_function["search"] == {"Perplexity"}

    def test_a_missing_provider_is_not_recorded_as_one(self):
        c = OpenRouterClient(api_key="test")
        c._account("triage", 0.0001, provider=None)
        assert c.providers_by_function == {}
        assert c.calls == 1, "the call still counts"

    def test_reset_clears_providers(self):
        c = OpenRouterClient(api_key="test")
        c._account("triage", 0.0001, provider="OpenInference")
        c.reset_accounting()
        assert c.providers_by_function == {}


class TestProviderPinning:
    """Reproducibility and availability are different goals. Unset, the provider
    decides and a run may be served by anyone; set, a run is repeatable."""

    async def _payload(self, monkeypatch, order):
        from autornd.config import settings
        from autornd.routing.openrouter import ModelResponse

        monkeypatch.setattr(settings, "openrouter_provider_order", order)
        captured = {}

        class FakeResponse:
            status_code = 200
            text = ""
            def raise_for_status(self): pass
            def json(self):
                return {"choices": [{"message": {"content": "{}"},
                                     "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                                  "cost": 0.0}}

        class FakeHttp:
            async def post(self, path, json):
                captured.update(json)
                return FakeResponse()

        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=FakeHttp()))
        await client.chat(function="triage", system_prompt="s", user_message="u")
        return captured

    async def test_unset_sends_no_provider_block(self, monkeypatch):
        payload = await self._payload(monkeypatch, "")
        assert "provider" not in payload

    async def test_a_pin_disables_fallbacks_by_default(self, monkeypatch):
        """A pin that silently falls back to someone else is not a pin —
        unless the owner says so. Default keeps the hard pin (reproducibility)."""
        payload = await self._payload(monkeypatch, "OpenInference, StreamLake")
        assert payload["provider"] == {
            "order": ["OpenInference", "StreamLake"], "allow_fallbacks": False}

    async def test_fallbacks_open_when_the_owner_allows(self, monkeypatch):
        """Measured 2026-09-26: the same 112768-token ask 404d pinned and
        served first try with fallbacks allowed — through the pin itself.
        The pin stays preferred-first; the router may serve beyond it."""
        from autornd.config import settings

        monkeypatch.setattr(settings, "openrouter_provider_fallbacks", "1")
        payload = await self._payload(monkeypatch, "OpenInference, StreamLake")
        assert payload["provider"] == {
            "order": ["OpenInference", "StreamLake"], "allow_fallbacks": True}

    async def test_whitespace_and_blanks_are_ignored(self, monkeypatch):
        payload = await self._payload(monkeypatch, " , OpenInference ,, ")
        assert payload["provider"]["order"] == ["OpenInference"]


class TestPerTierProviderOrder:
    """A pin has to be per tier.

    Tiers run different models and no provider serves them all. A global pin of
    the triage provider would have the search tier asking it for sonar-pro,
    which it does not host — and with fallbacks disabled that is a hard failure.
    Shipping a global pin and documenting it as the thing to do was a defect.
    """

    @staticmethod
    def _order(monkeypatch, value, function):
        from autornd.config import settings
        from autornd.routing.openrouter import provider_order_for

        monkeypatch.setattr(settings, "openrouter_provider_order", value)
        return provider_order_for(function)

    def test_unset_pins_nothing(self, monkeypatch):
        assert self._order(monkeypatch, "", "triage") == []

    def test_a_bare_list_applies_to_every_tier(self, monkeypatch):
        for tier in ("triage", "search", "architecture"):
            assert self._order(monkeypatch, "StreamLake", tier) == ["StreamLake"]

    def test_a_tier_can_be_pinned_alone(self, monkeypatch):
        value = "triage:StreamLake"
        assert self._order(monkeypatch, value, "triage") == ["StreamLake"]
        assert self._order(monkeypatch, value, "search") == []

    def test_a_named_tier_overrides_the_general_default(self, monkeypatch):
        value = "triage:StreamLake,Together"
        assert self._order(monkeypatch, value, "triage") == ["StreamLake"]
        assert self._order(monkeypatch, value, "search") == ["Together"]

    def test_an_empty_value_opts_a_tier_out(self, monkeypatch):
        """The case that matters: pin triage for reproducibility while leaving
        search free, because no one provider serves both models."""
        value = "Together,search:"
        assert self._order(monkeypatch, value, "triage") == ["Together"]
        assert self._order(monkeypatch, value, "search") == []

    def test_several_providers_for_one_tier(self, monkeypatch):
        value = "triage:StreamLake,triage:OpenInference"
        assert self._order(monkeypatch, value, "triage") == [
            "StreamLake", "OpenInference"]

    def test_tier_names_are_case_insensitive(self, monkeypatch):
        assert self._order(monkeypatch, "TRIAGE:StreamLake", "triage") == [
            "StreamLake"]
