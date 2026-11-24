"""A 504 from the gateway on the answer call is retried, bounded, counted and accounted.

**The measurement this exists for.** The first hold-out asked again of the harness (2026-11-24,
docs/reviews/2026-11-24-first-holdout-same-set.md) lost 13 of its 126 units to ``504: The operation was
aborted`` on the answer call, 11 of them in its third draw. The call had no retry for a 504 (a 429 had one),
so each of those units ended blocked with no answer. Whether a retry within 6 seconds is served is not
measured; these tests pin that the retry is made, bounded, counted by class, and accounted like the
transport retries (a dispatched attempt that fails keeps its own worst case, by identity, and the retry is
refused when it does not fit).

These tests simulate the condition end to end rather than asserting the shape of the fix (convention 22).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from autornd.routing import openrouter as orm
from autornd.routing.openrouter import OpenRouterClient


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


def _status(code):
    """The measured failure: the gateway's body said the operation was aborted."""
    return _Resp(code, {"error": {"message": "The operation was aborted"}},
                 text="The operation was aborted")


class _Http:
    def __init__(self, posts):
        self._posts = list(posts)
        self.calls = 0

    async def post(self, path, json):
        self.calls += 1
        outcome = self._posts.pop(0) if self._posts else _ok()
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []

    async def fake_sleep(d):
        slept.append(d)

    monkeypatch.setattr(orm.asyncio, "sleep", fake_sleep)
    return slept


@pytest.fixture
def rates(monkeypatch):
    table: dict[str, tuple[float, float]] = {}
    monkeypatch.setattr(orm, "_model_pricing", table)
    return table


def _client_with(http, monkeypatch):
    client = OpenRouterClient(api_key="test")
    monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=http))
    return client


async def _chat(client, **kw):
    return await client.chat(function="engineering", system_prompt="s",
                             user_message="u", **kw)


@pytest.mark.asyncio
class TestAGatewayTimeoutIsRetried:
    async def test_a_504_that_clears_completes_the_call(self, monkeypatch, no_sleep):
        http = _Http([_status(504), _ok()])
        client = _client_with(http, monkeypatch)
        out = await _chat(client)
        assert out.content == "{}"
        assert http.calls == 2, "the retry did not happen"
        assert no_sleep == [orm._GATEWAY_TIMEOUT_BACKOFF_S]
        assert client.retries_by_kind.get("gateway_timeout") == 1, (
            "the retry was not counted by its class")
        assert "gateway_timeout" in client.retry_reconciliation()[
            "excluded_from_rejection_counters"]

    async def test_a_retried_504_books_the_failed_attempt_s_liability(
            self, monkeypatch, no_sleep, rates):
        """The aborted attempt was dispatched and may have been billed: it keeps its own worst case."""
        http = _Http([_status(504), _ok()])
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)      # 5,000 tokens -> $0.05
        client.spend_ceiling = 0.20
        out = await _chat(client, model=model, max_tokens=5_000)
        assert out.content == "{}"
        assert client.unreconciled_liability == pytest.approx(0.05, abs=1e-6)
        assert [f["kind"] for f in client.failed_after_dispatch] == ["error_status"]
        assert client.spend == pytest.approx(0.001, abs=1e-6)

    async def test_a_retry_that_does_not_fit_is_refused(
            self, monkeypatch, no_sleep, rates):
        http = _Http([_status(504), _ok()])
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)
        client.spend_ceiling = 0.08     # 0.05 booked, 0.03 left
        with pytest.raises(orm.SpendGuardRefused):
            await _chat(client, model=model, max_tokens=5_000)
        assert http.calls == 1, "the retry was made despite the ceiling"
        assert not no_sleep

    async def test_the_attempts_are_bounded_and_the_backoff_doubles(
            self, monkeypatch, no_sleep, rates):
        http = _Http([_status(504)] * 10)
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)
        client.spend_ceiling = 1.0
        with pytest.raises(httpx.HTTPStatusError):
            await _chat(client, model=model, max_tokens=5_000)
        assert http.calls == orm._GATEWAY_TIMEOUT_ATTEMPTS, (
            "a pinned tier cannot fall back, so this must not retry forever")
        assert no_sleep == [orm._GATEWAY_TIMEOUT_BACKOFF_S,
                            orm._GATEWAY_TIMEOUT_BACKOFF_S * 2]
        # every dispatched attempt keeps its own worst case: two booked before a retry, the last by the call site
        assert client.unreconciled_liability == pytest.approx(0.15, abs=1e-6)
        assert len(client.failed_after_dispatch) == orm._GATEWAY_TIMEOUT_ATTEMPTS

    async def test_other_server_errors_are_not_retried(self, monkeypatch, no_sleep):
        """Typed on the status: only the 504 measured is retried; a 500 is a verdict about the serving."""
        for code in (500, 502, 503):
            http = _Http([_status(code), _ok()])
            client = _client_with(http, monkeypatch)
            with pytest.raises(httpx.HTTPStatusError):
                await _chat(client)
            assert http.calls == 1, f"a {code} was retried"
        assert not no_sleep

    async def test_an_interrupted_backoff_releases_the_retry_s_reservation(
            self, monkeypatch, rates):
        """A cancellation in the backoff must not leave the retry's worst case reserved."""
        async def cancelled_sleep(d):
            raise asyncio.CancelledError()

        monkeypatch.setattr(orm.asyncio, "sleep", cancelled_sleep)
        http = _Http([_status(504), _ok()])
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)
        client.spend_ceiling = 0.20
        with pytest.raises(asyncio.CancelledError):
            await _chat(client, model=model, max_tokens=5_000)
        assert http.calls == 1, "the retry left before the backoff ended"
        assert client.reserved == pytest.approx(0.0, abs=1e-9), (
            "the retry's reservation was left held")
        assert client._in_flight == 0
