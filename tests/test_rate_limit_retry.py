"""A 429 from OpenRouter is upstream capacity, and it is retryable.

**The measurement this exists for.** On 2026-09-20 a six-serving sweep of the
`engineering` tier read as six failing providers. It was one condition:
OpenRouter's upstream capacity for a single (model, provider) pair, whose body
says *"<model> is temporarily rate-limited upstream. Please retry shortly"*.
Controls taken the same hour: the same model on another provider answered, the
same model unpinned answered, a different model answered — same key, same
minute. The same pin that 429'd completed 90 s later.

Two instrument faults turned that into ten dead runs:

1. `_raise_for_status` kept `error.message` — *"Provider returned error"* — and
   dropped `error.metadata.raw`, which is the half that names the model and says
   the condition is transient.
2. Nothing retried it, while pinned tiers run `allow_fallbacks: False` by design
   (§6.1), so the request had nowhere to go.

Both are repaired. These tests simulate the condition end to end rather than
asserting the shape of the fix (convention 22).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from autornd.routing import openrouter as orm
from autornd.routing.openrouter import OpenRouterClient

RAW = ("deepseek/deepseek-v4-flash is temporarily rate-limited upstream. "
       "Please retry shortly, or add your own key")


class _Resp:
    """Enough of an httpx response for the client's error path."""

    def __init__(self, status_code, payload, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)
        self.request = httpx.Request("POST", "https://example.invalid/x")

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def _ok():
    return _Resp(200, {"choices": [{"message": {"content": "{}"},
                                    "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                                 "cost": 0.001}})


def _rate_limited():
    return _Resp(429, {"error": {"message": "Provider returned error",
                                 "code": 429,
                                 "metadata": {"raw": RAW}}})


class _Http:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def post(self, path, json):
        self.calls += 1
        return self._responses.pop(0) if self._responses else _ok()


@pytest.fixture
def no_sleep(monkeypatch):
    """The backoff is real seconds in production and none here."""
    slept = []

    async def fake_sleep(d):
        slept.append(d)

    monkeypatch.setattr(orm.asyncio, "sleep", fake_sleep)
    return slept


class TestTheDiagnosisSurvives:
    def test_the_upstream_sentence_reaches_the_exception(self):
        with pytest.raises(httpx.HTTPStatusError) as exc:
            orm._raise_for_status(_rate_limited(), "chat/completions")
        assert "temporarily rate-limited upstream" in str(exc.value), (
            "the half of the body that names the condition was dropped again")

    def test_the_category_is_kept_too(self):
        with pytest.raises(httpx.HTTPStatusError) as exc:
            orm._raise_for_status(_rate_limited(), "chat/completions")
        assert "Provider returned error" in str(exc.value)

    def test_a_body_without_metadata_still_raises_its_message(self):
        resp = _Resp(402, {"error": {"message": "Workspace budget exceeded"}})
        with pytest.raises(httpx.HTTPStatusError) as exc:
            orm._raise_for_status(resp, "chat/completions")
        assert "Workspace budget exceeded" in str(exc.value)


@pytest.mark.asyncio
class TestARateLimitIsRetried:
    async def test_a_429_that_clears_completes_the_call(self, monkeypatch, no_sleep):
        http = _Http([_rate_limited(), _ok()])
        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
        out = await client.chat(function="engineering", system_prompt="s",
                                user_message="u")
        assert out.content == "{}"
        assert http.calls == 2, "the retry did not happen"
        assert no_sleep == [orm._RATE_LIMIT_BACKOFF_S], "backoff not applied once"

    async def test_backoff_grows_and_the_attempts_are_bounded(self, monkeypatch, no_sleep):
        http = _Http([_rate_limited()] * 10)
        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
        with pytest.raises(httpx.HTTPStatusError):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u")
        assert http.calls == orm._RATE_LIMIT_ATTEMPTS, (
            "a pinned tier cannot fall back, so this must not retry forever")
        assert no_sleep == [orm._RATE_LIMIT_BACKOFF_S,
                            orm._RATE_LIMIT_BACKOFF_S * 2]

    async def test_a_persistent_429_still_reports_the_upstream_reason(
            self, monkeypatch, no_sleep):
        """Giving up is fine. Giving up without saying why is what cost the sweep."""
        http = _Http([_rate_limited()] * 10)
        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u")
        assert "temporarily rate-limited upstream" in str(exc.value)

    async def test_a_clean_call_is_not_retried_or_delayed(self, monkeypatch, no_sleep):
        http = _Http([_ok()])
        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
        await client.chat(function="engineering", system_prompt="s", user_message="u")
        assert http.calls == 1 and no_sleep == []

    async def test_every_attempt_bills(self, monkeypatch, no_sleep):
        """Test doubles must bill (non-negotiable 7). A retry storm that costs
        real money must show up in the meter, or a budget cannot stop it."""
        http = _Http([_rate_limited(), _ok()])
        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
        await client.chat(function="engineering", system_prompt="s", user_message="u")
        assert client.spend > 0, "the successful attempt after a retry billed nothing"
