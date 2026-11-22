"""Any catalogue price shape is bounded, so any model can serve any tier with the spend guard sighted.

Owner's ruling, 2026-11-22: "make sure any model can be used for any tier in future plug and play no
issues". The exhibit was the model line-up smoke (docs/reviews/2026-11-22-model-lineup-smoke.md): two of
its five answer models ran with the guard blind, the global one because its catalogue entry carries a
time-of-day `overrides` list, a newly listed one because its cache-write rate is above its prompt rate.
Both ran unbounded on every call, and nothing but the run record said so. The bound now takes the
highest rate each side can be charged at across the entry and its overrides; only a charge it cannot
read (a component it does not know, a price that does not parse) leaves a model blind, and the blind
model's log line names the charge.

The shapes below are the shapes of real catalogue entries read on 2026-11-22, under vendor ids.
"""

from __future__ import annotations

import json

import httpx
import pytest

from autornd.routing import openrouter
from autornd.routing.openrouter import (
    OpenRouterClient, SpendGuardRefused, _unreadable_charges, _worst_case_rates,
)

PLAIN = {"prompt": "0.00000037", "completion": "0.00000125", "input_cache_read": "0.000000075"}
CACHE_WRITE_ABOVE_PROMPT = {"prompt": "0.000001425", "completion": "0.000004275",
                            "input_cache_read": "0.00000007125",
                            "input_cache_write": "0.00000178125"}
BY_THE_HOUR = {"prompt": "0.00000015", "completion": "0.0000006", "input_cache_read": "0.000000003",
               "overrides": [
                   {"utc_days": ["saturday", "sunday"], "prompt": "0.00000015",
                    "completion": "0.0000006", "input_cache_read": "0.000000003"},
                   {"utc_days": ["monday"], "utc_start": 100, "utc_end": 400,
                    "prompt": "0.0000003", "completion": "0.0000012",
                    "input_cache_read": "0.000000006"}]}
STEPS_BY_PROMPT_SIZE = {"prompt": "0.0000001", "completion": "0.0000005", "web_search": "0.01",
                        "input_cache_read": "0.00000001", "input_cache_write": "0.000000125",
                        "input_cache_write_1h": "0.0000002",
                        "overrides": [{"min_prompt_tokens": 100000, "prompt": "0.0000005",
                                       "completion": "0.0000025", "input_cache_read": "0.00000005",
                                       "input_cache_write": "0.000000625",
                                       "input_cache_write_1h": "0.000001"}]}
MULTIMODAL = {"prompt": "0.0000015", "completion": "0.0000075", "image": "0.0000015",
              "audio": "0.0000015", "input_audio_cache": "0.000000075", "web_search": "0.014",
              "internal_reasoning": "0.0000075", "input_cache_read": "0.000000075",
              "input_cache_write": "0.0000000833333333333333"}


class TestTheBoundIsTheHighestRate:
    def test_a_plain_entry_is_bounded_at_its_own_rates(self):
        assert _worst_case_rates(PLAIN) == (0.00000037, 0.00000125, 0.0)

    def test_a_cache_write_above_the_prompt_rate_is_a_prompt_token_billed_higher(self):
        assert _worst_case_rates(CACHE_WRITE_ABOVE_PROMPT) == (0.00000178125, 0.000004275, 0.0)

    def test_a_time_of_day_override_raises_the_bound_to_its_highest_layer(self):
        assert _worst_case_rates(BY_THE_HOUR) == (0.0000003, 0.0000012, 0.0)

    def test_a_step_up_by_prompt_size_and_the_hour_cache_write_both_count(self):
        assert _worst_case_rates(STEPS_BY_PROMPT_SIZE) == (0.000001, 0.0000025, 0.01)

    def test_modality_components_never_charge_a_text_call_and_reasoning_stays_in_the_cap(self):
        assert _worst_case_rates(MULTIMODAL) == (0.0000015, 0.0000075, 0.014)

    def test_the_flat_per_request_charges_are_added_together_once(self):
        pricing = {"prompt": "0.000001", "completion": "0.000004",
                   "web_search": "0.01", "request": "0.002"}
        assert _worst_case_rates(pricing) == (0.000001, 0.000004, pytest.approx(0.012))

    def test_the_output_modalities_of_a_generator_never_charge_a_text_call(self):
        pricing = {"prompt": "0.000001", "completion": "0.000004",
                   "image_output": "0.00004", "audio_output": "0.00006"}
        assert _worst_case_rates(pricing) == (0.000001, 0.000004, 0.0)

    def test_a_layer_inherits_what_it_does_not_set(self):
        pricing = {"prompt": "0.000001", "completion": "0.000004", "web_search": "0.01",
                   "overrides": [{"utc_days": ["monday"], "completion": "0.000008"}]}
        assert _worst_case_rates(pricing) == (0.000001, 0.000008, 0.01)

    def test_an_explicit_zero_is_a_published_price_and_an_absent_side_is_unknown(self):
        assert _worst_case_rates({"prompt": "0", "completion": "0"}) == (0.0, 0.0, 0.0)
        assert _worst_case_rates({"prompt": "0.000001"}) is None
        assert _worst_case_rates({}) is None

    def test_the_bound_is_never_below_any_rate_the_entry_can_charge(self):
        for pricing in (PLAIN, CACHE_WRITE_ABOVE_PROMPT, BY_THE_HOUR, STEPS_BY_PROMPT_SIZE, MULTIMODAL):
            prompt_rate, completion_rate, _flat = _worst_case_rates(pricing)
            layers = [{k: v for k, v in pricing.items() if k != "overrides"}]
            layers += [{**layers[0], **layer} for layer in pricing.get("overrides", [])]
            for layer in layers:
                for key, value in layer.items():
                    if key in ("prompt", "input_cache_read", "input_cache_write", "input_cache_write_1h"):
                        assert float(value) <= prompt_rate, (key, pricing)
                    if key in ("completion", "internal_reasoning"):
                        assert float(value) <= completion_rate, (key, pricing)


class TestWhatTheBoundStillCannotRead:
    def test_a_component_it_does_not_know_leaves_the_model_blind_and_is_named(self):
        pricing = {"prompt": "0.000001", "completion": "0.000004", "fine_tuning": "0.01"}
        assert _worst_case_rates(pricing) is None
        assert _unreadable_charges(pricing) == ["fine_tuning"]

    def test_a_price_that_does_not_parse_leaves_the_model_blind(self):
        pricing = {"prompt": "0.000001", "completion": "0.000004", "web_search": "a lot"}
        assert _worst_case_rates(pricing) is None
        assert _unreadable_charges(pricing) == ["web_search"]

    def test_an_overrides_field_it_cannot_read_leaves_the_model_blind_and_is_named(self):
        for overrides in ("weekdays cost more", ["a", "b"], [{"prompt": "a lot"}]):
            pricing = {"prompt": "0.000001", "completion": "0.000004", "overrides": overrides}
            assert _worst_case_rates(pricing) is None, overrides
        assert _unreadable_charges({"prompt": "1", "completion": "1", "overrides": "x"}) == ["overrides"]

    def test_a_readable_entry_names_nothing(self):
        for pricing in (PLAIN, CACHE_WRITE_ABOVE_PROMPT, BY_THE_HOUR, STEPS_BY_PROMPT_SIZE, MULTIMODAL):
            assert _unreadable_charges(pricing) == []


def _client(requests: list) -> OpenRouterClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body["model"])
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "cost": 0.0001},
            "provider": "Test", "model": body["model"]})
    client = OpenRouterClient(api_key="test-key", base_url="https://router.test/api/v1")
    client._client = httpx.AsyncClient(base_url=client.base_url,
                                       transport=httpx.MockTransport(handler))
    return client


class TestTheGuardSeesTheModelsThatWereBlind:
    """The end of the chain: a rated model is bounded by the guard before the call is made."""

    async def test_a_call_that_cannot_fit_is_refused_and_one_that_can_is_made_and_not_blind(self, monkeypatch):
        requests: list = []
        client = _client(requests)
        model = client.get_model("engineering")
        prompt_rate, completion_rate, _flat = _worst_case_rates(CACHE_WRITE_ABOVE_PROMPT)
        monkeypatch.setattr(openrouter, "_model_pricing", {model: (prompt_rate, completion_rate)})
        monkeypatch.setattr(openrouter, "_model_per_request", {})
        # 10,000 output tokens at the bound is about $0.043: over a $0.02 ceiling, refused before dispatch.
        client.spend_ceiling = 0.02
        with pytest.raises(SpendGuardRefused):
            await client.chat("engineering", "sys", "user", max_tokens=10_000)
        assert requests == [] and client.spend_guard_blind == []
        # 1,000 output tokens is about $0.0043 + the prompt: fits, is made, and was not blind.
        await client.chat("engineering", "sys", "user", max_tokens=1_000)
        assert len(requests) == 1 and client.spend_guard_blind == []

    async def test_the_loader_rates_a_model_the_old_rule_left_blind(self, monkeypatch):
        """check_models, end to end, over a mocked catalogue holding each shape above."""
        from unittest.mock import AsyncMock, patch
        from autornd.config import settings
        monkeypatch.setattr(settings, "model_engineering", "vendor/by-the-hour")
        monkeypatch.setattr(openrouter, "_model_pricing", {})
        monkeypatch.setattr(openrouter, "_model_per_request", {})
        catalogue = {"data": [
            {"id": "vendor/by-the-hour", "pricing": BY_THE_HOUR},
            {"id": "vendor/cache-write", "pricing": CACHE_WRITE_ABOVE_PROMPT},
            {"id": "vendor/unknown", "pricing": {"prompt": "0.000001", "completion": "0.000004",
                                                 "fine_tuning": "0.01"}},
        ]}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=httpx.Response(
            200, json=catalogue, request=httpx.Request("GET", "https://openrouter.ai/api/v1/models")))
        with patch("autornd.routing.openrouter.httpx.AsyncClient", return_value=mock_client):
            await openrouter.check_models()
        assert openrouter._model_pricing["vendor/by-the-hour"] == (0.0000003, 0.0000012)
        assert openrouter._model_pricing["vendor/cache-write"] == (0.00000178125, 0.000004275)
        assert "vendor/unknown" not in openrouter._model_pricing
