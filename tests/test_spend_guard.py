"""F3 (ARCH-20261001-104): no call starts that could take a run past its cap.

Exhibit: 102's IA run ended at $0.1570 against an $0.08 cap, because one
escalation call cost $0.1142 and the ceiling was checked only after the call.
These tests drive the real OpenRouterClient.chat over an httpx MockTransport,
so the request counter proves whether a call was made.
"""

from __future__ import annotations

import json

import httpx
import pytest

from autornd.evals.runner import ResultsLog, _isolated_store, run_repeated
from autornd.evals.scenario import parse
from autornd.graph.spec import load
from autornd.routing import openrouter
from autornd.routing.openrouter import (
    CHARS_PER_TOKEN, OpenRouterClient, SpendGuardRefused,
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
        prompt = "x" * 4000                       # ~1000 prompt tokens
        await client.chat("escalation", "", prompt, max_tokens=1000)
        assert requests == [model]
        worst = (4000 / CHARS_PER_TOKEN) * 1e-6 + 1000 * 1e-6
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
