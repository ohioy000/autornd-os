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

**The second condition these tests cover (R4, the stage-1 report's
repair list, 2026-10-06).** A serving can fail a call at a *success*
status: the reply is JSON, it carries an `error`, and there is no
`choices` array to read. `chat` used to read `data["choices"][0]`
and crash with a bare `KeyError` — which the runners' generic
`except Exception` handlers class with broken runs, so the unit went
`incomplete` and the serving that produced the reply went unnamed.
That is a provider failure, not a bug in our own parsing: it is
retried like a 429 (the same bound and backoff, for the same reason —
a pinned tier cannot fall back and the caller is holding a scenario
clock), and when the retries exhaust it raises the typed
`ProviderFailure`, carrying the tier, the model and the body. The
tests below drive it end to end over the same fake transport the 429
tests use, including a `{"error": ...}` reply at status 200.
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


def _failed_call():
    """A serving that failed the call at a success status (R4):
    JSON, an error, and no choices array to read."""
    return _Resp(200, {"error": {"message": "model unavailable",
                                 "code": "upstream_error"}})


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


@pytest.fixture
def rates(monkeypatch):
    """The pricing table, empty by default — a priced entry
    makes the spend guard reserve a real worst case (the same
    fixture test_spend_guard carries)."""
    table: dict[str, tuple[float, float]] = {}
    monkeypatch.setattr(orm, "_model_pricing", table)
    return table


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


@pytest.mark.asyncio
class TestAReplyWithoutChoicesIsARetryableProviderFailure:
    """R4: a 200 reply without a choices array is the serving
    failing the call, not a missing key in our own code. It is
    retried like a 429 (same bound, same backoff) and raises a
    typed ProviderFailure when the retries exhaust — never a
    KeyError, which the runners' generic handlers would class
    with broken runs and leave the serving unnamed."""

    async def test_a_failed_call_that_clears_completes(
            self, monkeypatch, no_sleep):
        http = _Http([_failed_call(), _ok()])
        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
        out = await client.chat(function="engineering", system_prompt="s",
                                user_message="u")
        assert out.content == "{}"
        assert http.calls == 2, "the retry did not happen"
        assert no_sleep == [orm._RATE_LIMIT_BACKOFF_S], "backoff not applied once"

    async def test_backoff_grows_and_the_attempts_are_bounded(
            self, monkeypatch, no_sleep):
        http = _Http([_failed_call()] * 10)
        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
        with pytest.raises(orm.ProviderFailure):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u")
        assert http.calls == orm._RATE_LIMIT_ATTEMPTS, (
            "a pinned tier cannot fall back, so this must not retry forever")
        assert no_sleep == [orm._RATE_LIMIT_BACKOFF_S,
                            orm._RATE_LIMIT_BACKOFF_S * 2]

    async def test_the_exhausted_failure_is_typed_and_names_the_body(
            self, monkeypatch, no_sleep):
        """Giving up is fine. Giving up as a KeyError — an
        unattributed crash the runner classes with broken runs —
        is the defect."""
        http = _Http([_failed_call()] * 10)
        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
        with pytest.raises(orm.ProviderFailure) as exc:
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u")
        assert exc.value.function == "engineering"
        assert "no choices array" in str(exc.value)
        assert "model unavailable" in str(exc.value), (
            "the body's own sentence was dropped")

    async def test_the_failed_attempts_keep_their_worst_case(
            self, monkeypatch, no_sleep, rates):
        """Test doubles must bill (non-negotiable 7): a call that
        fails after dispatch keeps its own worst case as
        unreconciled liability — the same accounting a
        persistent 429 gets — so the ceiling still sees it."""
        http = _Http([_failed_call()] * 10)
        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)               # 10,000 tokens -> $0.10
        client.spend_ceiling = 1.0
        with pytest.raises(orm.ProviderFailure):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u", max_tokens=10_000)
        recorded = client.failed_after_dispatch
        assert recorded, "the failed call was not recorded after dispatch"
        assert recorded[-1]["kind"] == "ProviderFailure"
        assert recorded[-1]["worst_case"] > 0, (
            "the reservation became nothing: the ceiling is now blind "
            "to the money this call may have spent")
        assert client.unreconciled_liability > 0

    async def test_a_clean_call_is_not_retried_or_delayed(
            self, monkeypatch, no_sleep):
        http = _Http([_ok()])
        client = OpenRouterClient(api_key="test")
        monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
        await client.chat(function="engineering", system_prompt="s", user_message="u")
        assert http.calls == 1 and no_sleep == []
