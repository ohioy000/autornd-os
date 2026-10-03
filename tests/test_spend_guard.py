"""F3 (ARCH-20261001-104): no call starts that could take a run past its cap.

Exhibit: 102's IA run ended at $0.1570 against an $0.08 cap, because one
escalation call cost $0.1142 and the ceiling was checked only after the call.
These tests drive the real OpenRouterClient.chat over an httpx MockTransport,
so the request counter proves whether a call was made.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from autornd.evals.runner import ResultsLog, _isolated_store, run_repeated
from autornd.evals.scenario import parse
from autornd.graph.spec import load
from autornd.routing import openrouter
from autornd.routing.openrouter import (
    CHAT_TEMPLATE_ALLOWANCE_BYTES, BudgetExceeded, OpenRouterClient,
    SpendGuardRefused,
)

# One reply that satisfies every phase's schema; keys a verdict does not
# declare are ignored.
UNION = {"domains": ["backend"], "risk": "medium",
         "specialists": ["backend_engineer", "test_engineer"],
         "summary": "Backoff is capped at 60s with jitter applied.",
         "unrecallable": False, "queries": [], "blocking_unknowns": [],
         "ready": True, "plan": "Cap backoff at 60s.", "blockers": [],
         "success_criteria": ["Backoff is capped at 60s with jitter"],
         "feasible": True, "concerns": [], "critical": False, "done": True,
         "green": True, "red_cause": None, "evidence": [], "ship": True,
         "findings": [], "verdict": "Ship."}


def _client(requests: list) -> OpenRouterClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body["model"])
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(UNION)},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 100,
                      "cost": 0.001},
            "provider": "Test", "model": body["model"]})
    client = OpenRouterClient(api_key="test-key", base_url="https://router.test/api/v1")
    client._client = httpx.AsyncClient(base_url=client.base_url,
                                       transport=httpx.MockTransport(handler))
    return client


@pytest.fixture
def rates(monkeypatch):
    table: dict[str, tuple[float, float]] = {}
    monkeypatch.setattr(openrouter, "_model_pricing", table)
    return table


class TestTheGuardDecidesBeforeTheCall:
    async def test_a_call_whose_worst_case_exceeds_what_remains_is_never_made(self, rates):
        requests: list = []
        client = _client(requests)
        model = client.get_model("escalation")
        rates[model] = (0.0, 1e-5)               # 10,000 tokens -> $0.10
        client.spend_ceiling = 0.08
        with pytest.raises(SpendGuardRefused) as refused:
            await client.chat("escalation", "sys", "user", max_tokens=10_000)
        assert requests == []                     # nothing was sent
        assert refused.value.worst_case == pytest.approx(0.10, abs=1e-6)
        assert refused.value.remaining == pytest.approx(0.08)
        assert str(refused.value).startswith("stopped at $0.0000 before a call")

    async def test_a_call_that_fits_is_made(self, rates):
        requests: list = []
        client = _client(requests)
        model = client.get_model("escalation")
        rates[model] = (1e-6, 1e-6)
        client.spend_ceiling = 0.08
        prompt = "x" * 4000                       # 4,000 bytes: the bound is bytes
        await client.chat("escalation", "", prompt, max_tokens=1000)
        assert requests == [model]
        worst = (4000 + CHAT_TEMPLATE_ALLOWANCE_BYTES) * 1e-6 + 1000 * 1e-6
        assert worst < 0.08
        assert client.spend_guard_blind == []

    async def test_with_no_rate_the_call_is_made_and_the_guard_says_it_was_blind(self, rates):
        requests: list = []
        client = _client(requests)
        client.spend_ceiling = 0.08
        await client.chat("escalation", "sys", "user", max_tokens=10_000)
        assert len(requests) == 1
        assert client.spend_guard_blind == [
            {"function": "escalation", "model": client.get_model("escalation")}]


class TestTheGuardOnARealRun:
    async def test_the_refusal_and_the_blindness_are_in_the_written_record(
            self, rates, tmp_path):
        """The engineering tier is priced so that its implement call cannot
        fit a $0.05 run; every other tier has no rate. The run ends on the
        spend ceiling before the call, and the written record shows both."""
        requests: list = []
        clients: list = []

        def factory():
            c = _client(requests)
            clients.append(c)
            return c

        engineering = OpenRouterClient(api_key="x").get_model("engineering")
        rates[engineering] = (0.0, 1e-5)          # 16384 tokens -> $0.16
        path = tmp_path / "units.jsonl"
        scenario = parse({"id": "guard", "request": "MQTT backoff", "timeout": 60})
        with _isolated_store(), ResultsLog(path, {"suite": "guard"}) as log:
            await run_repeated([scenario], load("workflows/engineering-rnd.yaml"),
                               factory, {"max_iterations": 1,
                                         "escalation_recovery_attempts": 1,
                                         "review_rework_attempts": 1},
                               repeat=1, timeout=60, max_spend=0.05, results_log=log)
        (unit,) = [json.loads(l) for l in path.read_text().splitlines()
                   if json.loads(l)["record"] == "unit"]
        assert unit["status"] == "blocked"
        assert "before a call" in unit["reason"]
        assert f"call to {engineering}" in unit["reason"]
        assert engineering not in requests       # the refused call was never sent
        assert unit["spend_guard_blind"], "unrated tiers must be recorded as blind"
        assert all(b["model"] != engineering for b in unit["spend_guard_blind"])


# ── Ruling D45 (ARCH-20261002-110): the guard holds ─────────────────────────
#
# (e) concurrent calls, (f) failed calls, (g) reranking — the three ways the
# F3 guard could be walked past. Each drives the real client over
# httpx.MockTransport, so the request list proves whether a call was made.


class TestTheReservationHoldsAcrossConcurrentCalls:
    """(e) The guard read completed spend, which _account updates only after a
    response — so reviewer fan-out ran calls that each passed against the same
    remaining balance. The worst case is now reserved before dispatch."""

    async def test_the_second_concurrent_call_is_refused_before_dispatch(self, rates):
        requests: list = []
        mid_flight = asyncio.Event()

        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            requests.append(body["model"])
            mid_flight.set()
            await asyncio.sleep(0.2)
            return httpx.Response(200, json={
                "choices": [{"message": {"content": json.dumps(UNION)},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                          "cost": 0.001}})

        client = OpenRouterClient(api_key="k",
                                  base_url="https://router.test/api/v1")
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler))
        model = client.get_model("escalation")
        rates[model] = (0.0, 1e-5)          # 5,000 completion tokens -> $0.05
        client.spend_ceiling = 0.08

        first = asyncio.create_task(
            client.chat("escalation", "sys", "user", max_tokens=5_000))
        await mid_flight.wait()             # the first call is in flight
        with pytest.raises(SpendGuardRefused) as refused:
            await client.chat("escalation", "sys", "user", max_tokens=5_000)
        # $0.05 reserved leaves $0.03, and the second call could cost $0.05.
        assert refused.value.worst_case == pytest.approx(0.05, abs=1e-6)
        assert refused.value.remaining == pytest.approx(0.03, abs=1e-6)
        assert len(requests) == 1           # the refused call was never sent
        await first
        assert len(requests) == 1


class TestAFailedCallKeepsItsWorstCase:
    """(f) A call can fail after dispatch — error status, transport error,
    timeout, cancellation. No actual cost will ever arrive to replace the
    estimate, so the worst case stays as unreconciled liability and is
    recorded with its kind."""

    def _client_failing(self, requests: list, response) -> OpenRouterClient:
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(json.loads(request.content)["model"])
            return response
        client = OpenRouterClient(api_key="k",
                                  base_url="https://router.test/api/v1")
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler))
        return client

    async def test_an_error_status_keeps_the_worst_case_counted_and_recorded(
            self, rates):
        requests: list = []
        client = self._client_failing(
            requests, httpx.Response(500, json={"error": {"message": "boom"}}))
        model = client.get_model("escalation")
        rates[model] = (0.0, 1e-5)          # 5,000 completion tokens -> $0.05
        client.spend_ceiling = 0.08

        with pytest.raises(httpx.HTTPStatusError):
            await client.chat("escalation", "sys", "user", max_tokens=5_000)

        assert client.spend == 0.0          # nothing was booked
        assert client.reserved == 0.0
        assert client.unreconciled_liability == pytest.approx(0.05, abs=1e-6)
        assert client.failed_after_dispatch == [{
            "function": "escalation", "model": model, "kind": "error_status",
            "worst_case": 0.05}]
        # Counted for the rest of the run: a call that would fit the raw
        # budget no longer fits once the liability is kept.
        with pytest.raises(SpendGuardRefused):
            await client.chat("escalation", "sys", "user", max_tokens=5_000)
        assert len(requests) == 1           # only the failed call was sent

    async def test_a_timeout_is_kept_under_its_own_kind(self, rates):
        requests: list = []

        def timed_out(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow")

        client = OpenRouterClient(api_key="k",
                                  base_url="https://router.test/api/v1")
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(timed_out))
        model = client.get_model("escalation")
        rates[model] = (0.0, 1e-5)
        client.spend_ceiling = 0.08

        with pytest.raises(httpx.ReadTimeout):
            await client.chat("escalation", "sys", "user", max_tokens=5_000)

        assert client.failed_after_dispatch[0]["kind"] == "timeout"
        assert client.unreconciled_liability == pytest.approx(0.05, abs=1e-6)


class TestRerankPassesTheGuard:
    """(g) rerank was the one dispatch in the client with no pre-call check at
    all — it posted and spent whatever the documents cost."""

    async def test_rerank_is_refused_when_its_worst_case_does_not_fit(self, rates):
        requests: list = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request.url.path)
            return httpx.Response(200, json={"results": [],
                                             "usage": {"cost": 0.0}})
        client = OpenRouterClient(api_key="k",
                                  base_url="https://router.test/api/v1")
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler))
        rates["test/reranker"] = (1e-4, 0.0)
        client.spend_ceiling = 0.0001

        with pytest.raises(SpendGuardRefused) as refused:
            await client.rerank("test/reranker", "q", ["x" * 10_000], top_n=3)
        assert requests == []               # never posted
        assert refused.value.worst_case > 0.0001


class TestThePromptEstimateIsABoundNotAMean:
    """D45 amendment (b): prompt tokens are bounded by the prompt's UTF-8
    bytes plus the template allowance. The mean (chars / 4) under-counts any
    prompt a tokenizer finds expensive, so it was never a worst case."""

    async def test_the_worst_case_counts_utf8_bytes_plus_the_allowance(self, rates):
        requests: list = []
        client = _client(requests)
        model = client.get_model("escalation")
        rates[model] = (1e-3, 0.0)
        prompt = "é" * 1_000                # 1,000 characters, 2,000 bytes
        bound = (2_000 + CHAT_TEMPLATE_ALLOWANCE_BYTES) * 1e-3   # $2.512
        mean = (1_000 / 4) * 1e-3                              # $0.25
        client.spend_ceiling = (mean + bound) / 2   # the mean fits, the bound does not

        with pytest.raises(SpendGuardRefused) as refused:
            await client.chat("escalation", "", prompt, max_tokens=0)
        assert requests == []
        assert refused.value.worst_case == pytest.approx(bound, abs=1e-6)


class TestTheCallCeilingIsCheckedBeforeDispatch:
    """D45 amendment (c): a call past the ceiling must not be sent, and
    in-flight calls count against it."""

    async def test_the_call_past_the_ceiling_is_refused_before_it_is_sent(
            self, rates):
        requests: list = []
        client = _client(requests)
        client.call_ceiling = 2
        for _ in range(2):
            await client.chat("escalation", "sys", "user", max_tokens=10)
        assert len(requests) == 2

        with pytest.raises(BudgetExceeded) as exceeded:
            await client.chat("escalation", "sys", "user", max_tokens=10)
        assert len(requests) == 2           # the third was never sent
        assert "ceiling 2" in str(exceeded.value)


class TestUnratedIsNotFree:
    """Ruling D49, properties 1 and 2 (ARCH-20261002-116): a model the
    catalogue does not fully price is unknown, not free, and a
    published zero is a price. What the parse produces for each case
    is asserted at the parse (test_routing.py, TestCostEstimation);
    here is what each means to the guard.

    The defect this pins: the old parse entered a model with an absent
    pricing component at (prompt, 0.0), so the guard bounded a call on
    it at the prompt rate alone — a call that could cost $0.04 passed
    as $0.0004, bounded and silent, with no blindness recorded."""

    async def test_an_unrated_model_dispatches_blind_and_says_so(self, rates):
        """No table entry — what the parse leaves for a model with an
        absent component, or an unboundable charge — means the guard
        cannot bound the call. It is made (F3: refusing every unrated
        model would break runs against models the catalogue has not
        been read for) and the blindness is recorded, never guessed."""
        requests: list = []
        client = _client(requests)
        client.spend_ceiling = 0.08
        await client.chat("escalation", "sys", "user", max_tokens=10_000)
        assert len(requests) == 1
        assert client.spend_guard_blind == [
            {"function": "escalation",
             "model": client.get_model("escalation")}]

    async def test_an_explicit_zero_price_is_bounded_not_blind(self, rates):
        """A published zero is a price: the guard bounds the call at
        $0.00 — the same answer as the provider's own accounting for a
        free model — and says nothing was blind. Distinguishable from
        the unrated case above, which is the property."""
        requests: list = []
        client = _client(requests)
        model = client.get_model("escalation")
        rates[model] = (0.0, 0.0)          # what the parse keeps
        client.spend_ceiling = 0.08
        await client.chat("escalation", "sys", "user", max_tokens=10_000)
        assert len(requests) == 1
        assert client.spend_guard_blind == []
        assert client.reserved == 0.0      # a $0.00 worst case, reserved


# ── Ruling D47 (ARCH-20261002-113): a reservation is identified ─────────────
#
# (b) the advisor's out-of-order case, (c) a blind call releases nothing,
# (d) a failed call keeps its OWN worst case. The old guard held reservations
# in a FIFO deque and released whatever was oldest when a call accounted.


def _sequenced_client(handler) -> OpenRouterClient:
    client = OpenRouterClient(api_key="k",
                              base_url="https://router.test/api/v1")
    client._client = httpx.AsyncClient(
        base_url=client.base_url, transport=httpx.MockTransport(handler))
    return client


class TestReservationsAreIdentifiedNotCounted:
    """(b) With A ($0.06) in flight, B ($0.01) completing released A's
    reservation under the FIFO guard, and C ($0.05) then dispatched — the
    advisor's $0.111 booked against a $0.10 ceiling."""

    async def test_the_advisors_out_of_order_case(self, rates):
        costs = {"A": 0.06, "B": 0.01, "C": 0.041}
        sent: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            tag = body["messages"][1]["content"]
            sent.append(tag)
            if tag == "A":
                await asyncio.sleep(0.3)        # A stays in flight
            return httpx.Response(200, json={
                "choices": [{"message": {"content": json.dumps(UNION)},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                          "cost": costs[tag]}})

        client = _sequenced_client(handler)
        model = client.get_model("escalation")
        rates[model] = (0.0, 1e-5)              # worst = max_tokens / 100000
        client.spend_ceiling = 0.10

        a = asyncio.create_task(
            client.chat("escalation", "sys", "A", max_tokens=6_000))  # worst 0.06
        await asyncio.sleep(0.05)               # A is in flight
        await client.chat("escalation", "sys", "B", max_tokens=1_000)  # 0.01
        assert client.reserved == pytest.approx(0.06, abs=1e-6), (
            "B's completion must not release A's reservation")

        with pytest.raises(SpendGuardRefused) as refused:
            await client.chat("escalation", "sys", "C", max_tokens=5_000)
        assert refused.value.remaining == pytest.approx(0.03, abs=1e-6)
        await a
        # Booked is A + B and can never exceed the ceiling. Under the FIFO
        # guard this is $0.111 against $0.10 — the advisor's number.
        assert client.spend == pytest.approx(0.07, abs=1e-6)
        assert client.spend <= 0.10


class TestABlindCallReleasesNothing:
    """(c) A blind call reserved nothing, so it releases nothing — the old
    FIFO release let a blind booking consume a priced call's reservation."""

    async def test_a_completing_blind_call_leaves_the_priced_reservation(self, rates):
        mid_flight = asyncio.Event()

        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            tag = body["messages"][1]["content"]
            if tag == "priced":
                mid_flight.set()
                await asyncio.sleep(0.3)
            return httpx.Response(200, json={
                "choices": [{"message": {"content": json.dumps(UNION)},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                          "cost": 0.05 if tag == "priced" else 0.001}})

        client = _sequenced_client(handler)
        priced_model = client.get_model("escalation")
        rates[priced_model] = (0.0, 1e-5)       # worst 0.05
        blind_model = client.get_model("engineering")   # no rate: blind
        client.spend_ceiling = 0.10

        priced = asyncio.create_task(
            client.chat("escalation", "sys", "priced", max_tokens=5_000))
        await mid_flight.wait()
        await client.chat("engineering", "sys", "blind", max_tokens=5_000)
        assert client.reserved == pytest.approx(0.05, abs=1e-6), (
            "the blind call must not release the priced reservation")
        await priced
        assert client.reserved == 0.0


class TestAFailedCallBooksItsOwnWorstCase:
    """(d) Two calls in flight, the SMALL one fails: the liability is its own
    worst case, not the other call's."""

    async def test_the_failed_call_keeps_its_own_not_the_others(self, rates):
        mid_flight = asyncio.Event()

        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            tag = body["messages"][1]["content"]
            if tag == "big":
                mid_flight.set()
                await asyncio.sleep(0.3)
                return httpx.Response(200, json={
                    "choices": [{"message": {"content": json.dumps(UNION)},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                              "cost": 0.06}})
            return httpx.Response(500, json={"error": {"message": "boom"}})

        client = _sequenced_client(handler)
        model = client.get_model("escalation")
        rates[model] = (0.0, 1e-5)
        client.spend_ceiling = 0.10

        big = asyncio.create_task(
            client.chat("escalation", "sys", "big", max_tokens=6_000))
        await mid_flight.wait()
        with pytest.raises(httpx.HTTPStatusError):
            await client.chat("escalation", "sys", "small", max_tokens=1_000)
        assert client.unreconciled_liability == pytest.approx(0.01, abs=1e-6), (
            "the failure booked its own worst case, not the in-flight call's")
        assert client.reserved == pytest.approx(0.06, abs=1e-6)
        await big
        assert client.spend == pytest.approx(0.06, abs=1e-6)
