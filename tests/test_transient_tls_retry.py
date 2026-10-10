"""A transient TLS record-MAC alert is a condition of the
connection, and it is retryable.

**The measurement this exists for.** On 2026-10-04 (the golden
probe's fourth sample) the engineering call died on a raw
``ssl.SSLError: [SSL: SSLV3_ALERT_BAD_RECORD_MAC] ssl/tls
alert bad record mac`` — not wrapped in httpx.TransportError —
and the call was killed with its worst case booked as
unreconciled liability. A record-MAC alert is a transient
record-layer condition on the connection: the same pin answered
on retry. The 429 loop already retries the one transient class
the client knew about; this repairs the other one, bounded,
backed off and counted, so the record reconciles every retry by
class.

These tests simulate the condition end to end rather than
asserting the shape of the fix (convention 22).
"""

from __future__ import annotations

import asyncio
import ssl
from unittest.mock import AsyncMock

import httpx
import pytest

from autornd.routing import openrouter as orm
from autornd.routing.openrouter import OpenRouterClient


def _alert():
    """The measured failure, as it surfaced: a raw ssl.SSLError
    with the alert's reason set, as the ssl module sets it on
    the errors it raises."""
    alert = ssl.SSLError(
        "[SSL: SSLV3_ALERT_BAD_RECORD_MAC] ssl/tls alert "
        "bad record mac (_ssl.c:2580)")
    alert.reason = "SSLV3_ALERT_BAD_RECORD_MAC"
    return alert


def _wrapped_alert():
    """The same alert behind an httpx transport error."""
    request = httpx.Request("POST", "https://example.invalid/x")
    wrapped = httpx.ReadError("read", request=request)
    wrapped.__cause__ = _alert()
    return wrapped


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
                           "usage": {"prompt_tokens": 1,
                                     "completion_tokens": 1,
                                     "cost": 0.001}})


class _Http:
    """Posts responses, or raises the failures it was given."""

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
    """The backoff is real seconds in production and none here."""
    slept = []

    async def fake_sleep(d):
        slept.append(d)

    monkeypatch.setattr(orm.asyncio, "sleep", fake_sleep)
    return slept


@pytest.fixture
def rates(monkeypatch):
    """The catalogue's pricing table, filled by the test — the
    guard is blind for an unrated model, and a blind call keeps
    no worst case to book as liability."""
    table: dict[str, tuple[float, float]] = {}
    monkeypatch.setattr(orm, "_model_pricing", table)
    return table


def _client_with(http, monkeypatch):
    client = OpenRouterClient(api_key="test")
    monkeypatch.setattr(client, "_get_client",
                        AsyncMock(return_value=http))
    return client


@pytest.mark.asyncio
class TestATransientTLSAlertIsRetried:
    async def test_an_alert_that_clears_completes_the_call(
            self, monkeypatch, no_sleep):
        http = _Http([_alert(), _ok()])
        client = _client_with(http, monkeypatch)
        out = await client.chat(function="engineering", system_prompt="s",
                                user_message="u")
        assert out.content == "{}"
        assert http.calls == 2, "the retry did not happen"
        assert no_sleep == [orm._TRANSIENT_TLS_BACKOFF_S], (
            "backoff not applied once")
        assert client.retries_by_kind.get("transient_tls") == 1, (
            "the retry was not counted by class")

    async def test_an_alert_behind_a_transport_error_is_retried(
            self, monkeypatch, no_sleep):
        """The alert can ride in an httpx error's chain, not only
        surface raw — both shapes are the same condition."""
        http = _Http([_wrapped_alert(), _ok()])
        client = _client_with(http, monkeypatch)
        out = await client.chat(function="engineering", system_prompt="s",
                                user_message="u")
        assert out.content == "{}"
        assert http.calls == 2, "the chained alert was not retried"

    async def test_a_retried_alert_books_the_failed_attempt_s_liability(
            self, monkeypatch, no_sleep, rates):
        """D45: the alert arrives while the response is being
        read, so the generation was likely complete and billed —
        the failed attempt keeps its worst case as unreconciled
        liability before the retry leaves."""
        http = _Http([_alert(), _ok()])
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)      # 5,000 tokens -> $0.05
        client.spend_ceiling = 0.20     # room for both attempts
        out = await client.chat(function="engineering", system_prompt="s",
                                user_message="u", model=model,
                                max_tokens=5_000)
        assert out.content == "{}"
        assert http.calls == 2, "the retry did not happen"
        assert client.unreconciled_liability == pytest.approx(
            0.05, abs=1e-6), (
            "the failed attempt's worst case was not booked")
        assert client.failed_after_dispatch[-1]["kind"] == "SSLError"
        # The retry reconciled: its actual cost is booked, and
        # the failed attempt's worst case stays on the hook for
        # the rest of the run.
        assert client.spend == pytest.approx(0.001, abs=1e-6)

    async def test_a_retry_that_does_not_fit_is_refused(
            self, monkeypatch, no_sleep, rates):
        """The failed attempt's worst case is on the hook, so the
        retry is re-checked against what remains — refused, not
        retried, when it does not fit."""
        http = _Http([_alert(), _ok()])
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)      # 5,000 tokens -> $0.05
        client.spend_ceiling = 0.08     # 0.05 booked, 0.03 left
        with pytest.raises(orm.SpendGuardRefused):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u", model=model,
                              max_tokens=5_000)
        assert http.calls == 1, "the retry was made despite the ceiling"
        assert not no_sleep, "no backoff without a retry"
        assert client.unreconciled_liability == pytest.approx(
            0.05, abs=1e-6), "the failed attempt's worst case was not booked"

    async def test_backoff_grows_and_the_attempts_are_bounded(
            self, monkeypatch, no_sleep, rates):
        http = _Http([_alert()] * 10)
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)      # 5,000 tokens -> $0.05
        client.spend_ceiling = 0.20     # room for both attempts
        with pytest.raises(ssl.SSLError):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u", model=model,
                              max_tokens=5_000)
        assert http.calls == orm._TRANSIENT_TLS_ATTEMPTS, (
            "a pinned tier cannot fall back, so this must not retry forever")
        assert no_sleep == [orm._TRANSIENT_TLS_BACKOFF_S]
        # Both dispatched attempts keep their worst cases (D45):
        # the first is booked before the retry leaves, the second
        # by the caller's dispatch accounting when the alert
        # exhausts the attempts — the fourth sample's shape,
        # worst case and kind.
        assert client.unreconciled_liability == pytest.approx(
            0.10, abs=1e-6)
        assert [f["kind"] for f in client.failed_after_dispatch] == [
            "SSLError", "SSLError"]

    async def test_an_ssl_error_with_a_different_reason_is_not_retried(
            self, monkeypatch, no_sleep):
        """Typed matching: an SSLError whose reason is not the
        record-MAC alert is a verdict about the serving (or
        another condition), not this transient one — retrying
        it would spend the same worst case twice."""
        cert_error = ssl.SSLError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
        cert_error.reason = "CERTIFICATE_VERIFY_FAILED"
        http = _Http([cert_error, _ok()])
        client = _client_with(http, monkeypatch)
        with pytest.raises(ssl.SSLError):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u")
        assert http.calls == 1, "a different reason must not be retried"
        assert not no_sleep, "no backoff without a retry"

    async def test_bad_record_mac_text_without_the_typed_reason(
            self, monkeypatch, no_sleep):
        """Hard rule 2: text is not a verdict. An error whose
        message names the alert but is not an ssl.SSLError
        carrying the alert's reason is not this condition —
        the text-matching matcher this repair replaces
        retried exactly this shape."""
        impostor = RuntimeError(
            "[SSL: SSLV3_ALERT_BAD_RECORD_MAC] ssl/tls alert "
            "bad record mac")
        http = _Http([impostor, _ok()])
        client = _client_with(http, monkeypatch)
        with pytest.raises(RuntimeError):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u")
        assert http.calls == 1, "text alone must not be retried"
        assert not no_sleep, "no backoff without a retry"

    async def test_a_clean_call_is_not_retried_or_delayed(
            self, monkeypatch, no_sleep):
        http = _Http([_ok()])
        client = _client_with(http, monkeypatch)
        await client.chat(function="engineering", system_prompt="s",
                          user_message="u")
        assert http.calls == 1 and no_sleep == []
        assert client.retry_reconciliation()["total"] == 0

    async def test_a_cancellation_is_not_retried(self, monkeypatch, no_sleep):
        """The watchdog's cut is a BaseException and must reach the
        watchdog untried — a retry would outlive the budget that
        cancelled the run."""
        http = _Http([asyncio.CancelledError(), _ok()])
        client = _client_with(http, monkeypatch)
        with pytest.raises(asyncio.CancelledError):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u")
        assert http.calls == 1, "a cancellation must not be retried"

    async def test_an_alert_on_the_no_choices_re_post_is_retried(
            self, monkeypatch, no_sleep, rates):
        """The fourth post site (R4's no-choices re-post) goes
        through the same helper: a record-MAC alert on it is the
        same condition of the connection, retried and accounted
        like the others — one failed entry, the ledger correct."""
        no_choices = _Resp(200, {"error": "the serving failed the call"})
        http = _Http([no_choices, _alert(), _ok()])
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)      # 5,000 tokens -> $0.05
        client.spend_ceiling = 0.20
        out = await client.chat(function="engineering", system_prompt="s",
                                user_message="u", model=model,
                                max_tokens=5_000)
        assert out.content == "{}"
        assert http.calls == 3, "the no-choices re-post and its retry"
        assert no_sleep == [orm._RATE_LIMIT_BACKOFF_S,
                            orm._TRANSIENT_TLS_BACKOFF_S], (
            "the no-choices backoff, then the retry's")
        assert client.retries_by_kind.get("transient_tls") == 1
        assert [f["kind"] for f in client.failed_after_dispatch] == [
            "SSLError"]
        assert client.unreconciled_liability == pytest.approx(
            0.05, abs=1e-6)


class TestABackoffInterruptedBeforeTheRetryDispatches:
    """The 2026-10-10 review's probe: an interruption landing in
    the retry's backoff. The retry never left this process, so
    nothing is booked for it — the ledger carries the attempt
    that did leave, once, and the in-flight count stays
    balanced (convention 22: the tests simulate the condition
    end to end on the real chat() dispatch)."""

    async def test_a_cancelled_backoff_books_one_failure(
            self, monkeypatch, rates):
        """The probe, end to end: the alert once, the backoff
        cancelled. One post left this process, so the ledger
        carries exactly one failure with one worst case — not
        the retry's, which never left."""
        http = _Http([_alert()])
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1.00519e-5)  # 10,000 tokens -> $0.100519
        client.spend_ceiling = 5.0

        async def cancel_sleep(delay):
            raise asyncio.CancelledError()

        monkeypatch.setattr(orm.asyncio, "sleep", cancel_sleep)
        with pytest.raises(asyncio.CancelledError):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u", model=model,
                              max_tokens=10000)
        assert http.calls == 1, "only the first attempt left"
        assert client.failed_after_dispatch == [
            {"function": "engineering", "model": model,
             "kind": "SSLError", "worst_case": 0.100519}]
        assert client.unreconciled_liability == pytest.approx(
            0.100519, abs=1e-6)
        assert client.reserved == 0.0
        assert client._in_flight == 0

    async def test_an_error_in_the_backoff_books_nothing_for_the_retry(
            self, monkeypatch, rates):
        """Any interruption, not only a cancellation: an error
        raised while the retry backs off leaves the same ledger
        — the attempt that left, booked once."""
        http = _Http([_alert()])
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)      # 5,000 tokens -> $0.05
        client.spend_ceiling = 0.20

        async def broken_sleep(delay):
            raise RuntimeError("the watchdog's cut, as an error")

        monkeypatch.setattr(orm.asyncio, "sleep", broken_sleep)
        with pytest.raises(RuntimeError):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u", model=model,
                              max_tokens=5_000)
        assert http.calls == 1, "only the first attempt left"
        assert [f["kind"] for f in client.failed_after_dispatch] == [
            "SSLError"]
        assert client.unreconciled_liability == pytest.approx(
            0.05, abs=1e-6)
        assert client._in_flight == 0

    async def test_the_in_flight_count_stays_balanced(
            self, monkeypatch, rates):
        """A concurrent call in flight keeps its reservation and
        its count: the cancelled backoff takes back only the
        retry's own in-flight count and releases only the
        retry's own reservation, so the call ceiling still sees
        the other call and admits no extra one."""

        class _TwoCallHttp:
            """The first post blocks in flight (the other call);
            the second raises the alert (the cancelled call's
            dispatched attempt)."""

            def __init__(self):
                self.calls = 0
                self.b_dispatched = asyncio.Event()
                self.b_release = asyncio.Event()

            async def post(self, path, json):
                self.calls += 1
                if self.calls == 1:
                    self.b_dispatched.set()
                    await self.b_release.wait()
                    return _ok()
                raise _alert()

        http = _TwoCallHttp()
        client = _client_with(http, monkeypatch)
        model = client.get_model("engineering")
        rates[model] = (0.0, 1e-5)      # 5,000 tokens -> $0.05
        client.spend_ceiling = 0.20
        client.call_ceiling = 2          # both calls may be in flight

        async def cancel_sleep(delay):
            raise asyncio.CancelledError()

        monkeypatch.setattr(orm.asyncio, "sleep", cancel_sleep)

        task_b = asyncio.create_task(client.chat(
            function="engineering", system_prompt="s",
            user_message="u", model=model, max_tokens=5_000))
        await http.b_dispatched.wait()   # B's post is in flight now
        task_a = asyncio.create_task(client.chat(
            function="engineering", system_prompt="s",
            user_message="u", model=model, max_tokens=5_000))
        with pytest.raises(asyncio.CancelledError):
            await task_a                 # A's backoff is cancelled
        # Only B is in flight: its reservation is untouched and
        # the ledger carries A's dispatched attempt, once.
        assert client._in_flight == 1
        assert len(client._reservations) == 1
        assert client.reserved == pytest.approx(0.05, abs=1e-6)
        assert client.unreconciled_liability == pytest.approx(
            0.05, abs=1e-6)
        assert [f["kind"] for f in client.failed_after_dispatch] == [
            "SSLError"]
        # The count still sees B, so the ceiling admits no
        # extra call: one in-flight slot, held by B.
        client.call_ceiling = 1
        with pytest.raises(orm.BudgetExceeded):
            await client.chat(function="engineering", system_prompt="s",
                              user_message="u", model=model,
                              max_tokens=5_000)
        http.b_release.set()
        out = await task_b
        assert out.content == "{}"
        assert client._in_flight == 0


class TestTheRetryIsReconciled:
    def test_the_transient_tls_class_is_named_as_excluded(self):
        """A reader of an empty rejection count learns what the
        retry total includes without opening this file."""
        report = OpenRouterClient(api_key="test").retry_reconciliation()
        assert "transient_tls" in report["excluded_from_rejection_counters"]
