"""The optional decision tier: a decision model's narrow notes on a finished
answer (owner, 2026-11-13). Recorded, never routed on."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from autornd.engine import phases
from autornd.graph.adapter import PhaseRunner
from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import load
from autornd.preflight import check, sent_parameters
from autornd.routing import openrouter
from autornd.routing.openrouter import ModelResponse, OpenRouterClient
from tests.test_recompute_vote import (REQUEST, SETTINGS, SUMMARY, _double,
                                       _workflow_router)

WORKFLOW = "workflows/answer-and-recompute.yaml"
ASKS = [{"number": 1, "quote": "Give the cap in seconds", "kind": "value"},
        {"number": 2, "quote": "state whether jitter applies", "kind": "verdict"}]
SOURCES = [{"lookup": "grounding", "findings": [{
    "question": "What is the cap?",
    "quotes": [
        {"status": "found", "text": "The cap is 60 s.", "url": "https://a.example/p"},
        {"status": "not_found", "text": "Something else.", "url": "https://b.example/p"},
    ]}]}]


class _Transport:
    """A local stand-in for the HTTP client: records the post, answers it."""

    is_closed = False

    def __init__(self, body: dict, status: int = 200):
        self.posts: list[tuple[str, dict]] = []
        self._body, self._status = body, status

    async def post(self, path, json=None):
        self.posts.append((path, json))
        body, status = self._body, self._status

        class Response:
            status_code = status
            text = "refused"
            headers: dict = {}

            @staticmethod
            def json():
                return body

            @staticmethod
            def raise_for_status():
                if status >= 400:
                    import httpx
                    raise httpx.HTTPStatusError(
                        "refused", request=httpx.Request("POST", "https://x.example"),
                        response=httpx.Response(status))
        return Response()


@pytest.fixture
def decision_tier(monkeypatch):
    monkeypatch.setattr(openrouter.settings, "model_decision", "vendor/decider")
    monkeypatch.setitem(OpenRouterClient.FUNCTION_MODELS, "decision", "vendor/decider")


def _reply(**answers) -> dict:
    return {"id": "d", "model": "vendor/decider-20261101", "provider": "Vendor",
            "answers": answers,
            "usage": {"input_tokens": 400, "output_tokens": 9, "cost": 0.00002}}


class TestTheClientCall:
    async def test_the_request_goes_to_the_decisions_route_with_its_cost_booked(
            self, decision_tier):
        client = OpenRouterClient(api_key="test",
                                  base_url="https://router.example/api/v1")
        client._client = _Transport(_reply(q={"type": "noul", "noul": 0.9}))
        answers, response = await client.decide(
            {"request": "r"}, {"q": {"type": "noul", "instructions": "i"}})
        (path, body), = client._client.posts
        assert path == "https://router.example/api/alpha/decisions"
        assert body == {"model": "vendor/decider", "state": {"request": "r"},
                        "questions": {"q": {"type": "noul", "instructions": "i"}}}
        assert answers == {"q": {"type": "noul", "noul": 0.9}}
        assert response.model == "vendor/decider-20261101"
        assert response.cost == 0.00002 and response.content == ""
        assert client.calls_by_function == {"decision": 1}
        assert client.spend == pytest.approx(0.00002)
        assert client._in_flight == 0

    async def test_a_pin_is_sent_as_every_other_call_sends_it(
            self, decision_tier, monkeypatch):
        monkeypatch.setattr(openrouter.settings, "openrouter_provider_order",
                            "decision:Vendor")
        client = OpenRouterClient(api_key="test")
        client._client = _Transport(_reply())
        await client.decide({}, {})
        assert client._client.posts[0][1]["provider"]["order"] == ["Vendor"]

    @pytest.mark.parametrize("transport", [
        _Transport({"error": {"code": 502, "message": "upstream"}}, status=502),
        _Transport({"id": "d", "usage": {}}),          # 200 with no answers
    ])
    async def test_a_failed_call_raises_and_leaves_nothing_in_flight(
            self, decision_tier, transport):
        client = OpenRouterClient(api_key="test")
        client._client = transport
        with pytest.raises(Exception):
            await client.decide({}, {"q": {"type": "noul"}})
        assert client._in_flight == 0
        assert client.spend == 0.0

    async def test_a_busy_model_is_asked_again_and_booked_once(
            self, decision_tier, monkeypatch):
        """Live 2026-11-13: "Model busy, retry later" lost one call's notes."""
        waits: list[float] = []

        async def sleep(seconds):
            waits.append(seconds)

        monkeypatch.setattr(openrouter.asyncio, "sleep", sleep)
        busy = _Transport({"detail": "Model busy, retry later"}, status=429)
        good = _Transport(_reply(q={"type": "noul", "noul": 0.5}))

        class Flaky:
            is_closed = False
            posts = 0

            async def post(self, path, json=None):
                Flaky.posts += 1
                return await (busy if Flaky.posts == 1 else good).post(path, json)

        client = OpenRouterClient(api_key="test")
        client._client = Flaky()
        answers, _ = await client.decide({}, {"q": {"type": "noul"}})
        assert answers["q"]["noul"] == 0.5 and Flaky.posts == 2
        assert waits == [openrouter._RATE_LIMIT_BACKOFF_S]
        assert client.calls_by_function == {"decision": 1}
        assert client._in_flight == 0

    async def test_a_model_that_stays_busy_fails_after_the_bound(
            self, decision_tier, monkeypatch):
        async def sleep(seconds):
            return None

        monkeypatch.setattr(openrouter.asyncio, "sleep", sleep)
        client = OpenRouterClient(api_key="test")
        client._client = _Transport({"detail": "busy"}, status=429)
        with pytest.raises(Exception):
            await client.decide({}, {"q": {"type": "noul"}})
        assert len(client._client.posts) == openrouter._RATE_LIMIT_ATTEMPTS
        assert client._in_flight == 0

    def test_there_is_no_fallback_model(self, monkeypatch):
        monkeypatch.delitem(OpenRouterClient.FUNCTION_MODELS, "decision",
                            raising=False)
        assert OpenRouterClient(api_key="test").decision_model() is None


class TestTheNotes:
    async def _notes(self, answers: dict, asks=ASKS, sources=SOURCES):
        client = OpenRouterClient(api_key="test")
        asked: list[tuple[dict, dict]] = []

        async def decide(state, questions):
            asked.append((state, questions))
            return answers, ModelResponse(content="", model="m", prompt_tokens=1,
                                          completion_tokens=0, cost=0.0)

        client.decide = AsyncMock(side_effect=decide)
        notes, responses = await phases.run_decision_notes(
            client, REQUEST, SUMMARY, asks, sources)
        return notes, asked[0], responses

    async def test_one_request_asks_each_narrow_question(self):
        notes, (state, questions), responses = await self._notes({})
        assert len(responses) == 1
        assert sorted(questions) == ["ask_1", "ask_2", "needs_sources", "quote_0"]
        assert all(q["type"] == "noul" for q in questions.values())
        assert state["request"] == REQUEST and state["answer"] == SUMMARY
        assert state["asks"] == {"1": ASKS[0]["quote"], "2": ASKS[1]["quote"]}
        # Only a quote the check found on its page is asked about.
        assert state["quotes"] == {"0": {"question": "What is the cap?",
                                         "passage": "The cap is 60 s."}}
        assert notes["questions_asked"] == 4

    async def test_a_quote_is_read_against_its_own_question(self):
        sources = [{"lookup": "grounding", "findings": [{
            "question": "The first question",
            "quotes": [{"status": "found", "text": "A passage.", "url": "u",
                        "question_text": "The second question"}]}]}]
        _, (state, _), _ = await self._notes({}, sources=sources)
        assert state["quotes"]["0"]["question"] == "The second question"

    async def test_each_answer_is_recorded_as_its_probability(self):
        notes, _, _ = await self._notes({
            "needs_sources": {"type": "noul", "noul": 0.12},
            "ask_1": {"type": "noul", "noul": 0.97},
            "ask_2": {"type": "noul", "noul": 0.4},
            "quote_0": {"type": "noul", "noul": 1},
        })
        assert notes == {
            "skipped": False, "reason": "", "needs_sources": 0.12,
            "asks": [{"ask": 1, "addressed": 0.97}, {"ask": 2, "addressed": 0.4}],
            "quotes": [{"quote": 0, "url": "https://a.example/p",
                        "bears_on_question": 1.0}],
            "questions_asked": 4,
        }

    @pytest.mark.parametrize("answer", [
        None, {"type": "refusal"}, {"type": "noul", "noul": "high"},
        {"type": "noul", "noul": 1.4}, {"type": "noul", "noul": True}, "yes"])
    async def test_an_answer_that_states_no_probability_is_recorded_as_none(
            self, answer):
        notes, _, _ = await self._notes({"ask_1": answer} if answer else {})
        assert notes["asks"][0] == {"ask": 1, "addressed": None}
        assert notes["needs_sources"] is None

    async def test_with_no_asks_and_no_sources_one_question_is_still_asked(self):
        notes, (state, questions), _ = await self._notes({}, asks=None, sources=[])
        assert list(questions) == ["needs_sources"]
        assert "asks" not in state and "quotes" not in state
        assert notes["asks"] == [] and notes["quotes"] == []

    async def test_the_questions_are_bounded(self):
        many = [{"number": n, "quote": f"ask {n}", "kind": "value"}
                for n in range(1, 40)]
        _, (_, questions), _ = await self._notes({}, asks=many, sources=[])
        assert len(questions) == phases.DECISION_MAX_ASKS + 1


def _with_decisions(router, answers=None, error=None):
    client, calls = _double(router)
    asked: list[tuple[dict, dict]] = []

    async def decide(state, questions):
        asked.append((state, questions))
        if error:
            raise error
        client._account("decision", 0.00002)
        return (answers if answers is not None else
                {name: {"type": "noul", "noul": 0.9} for name in questions}), \
            ModelResponse(content="", model="vendor/decider", prompt_tokens=400,
                          completion_tokens=0, cost=0.00002)

    client.decide = AsyncMock(side_effect=decide)
    return client, asked


async def _run(client, recorded=None):
    runner = PhaseRunner(client)
    if recorded is not None:
        runner.on_phase = lambda node, verdict, responses, iteration: (
            recorded.append((node, verdict)))
    return await GraphExecutor(load(WORKFLOW), runner, SETTINGS).run(REQUEST)


class TestTheNodeInTheWorkflow:
    async def test_unset_the_node_skips_and_makes_no_call(self):
        client, asked = _with_decisions(_workflow_router(200.0, [200.0] * 3))
        state = await _run(client)
        assert state.status == "completed"
        notes = state.outputs["decision_notes"]
        assert notes["skipped"] is True and "decision tier" in notes["reason"]
        assert notes["asks"] == [] and notes["needs_sources"] is None
        assert asked == []

    async def test_set_the_notes_are_recorded_and_the_status_is_the_same(
            self, decision_tier):
        recorded: list = []
        client, asked = _with_decisions(_workflow_router(200.0, [200.0] * 3))
        state = await _run(client, recorded)
        assert state.status == "completed"
        notes = state.outputs["decision_notes"]
        assert notes["skipped"] is False
        assert notes["asks"] == [{"ask": 1, "addressed": 0.9},
                                 {"ask": 2, "addressed": 0.9}]
        assert notes["needs_sources"] == 0.9
        (state_sent, _), = asked
        assert state_sent["answer"] == SUMMARY
        assert ("decision_notes", notes) in recorded

    @pytest.mark.parametrize("answers", [
        {},                                               # every note absent
        {"ask_1": {"type": "noul", "noul": 0.0},          # every note "no"
         "ask_2": {"type": "noul", "noul": 0.0},
         "needs_sources": {"type": "noul", "noul": 1.0}},
    ])
    async def test_no_note_changes_the_run(self, decision_tier, answers):
        """Break-proof for "notes only": the worst notes a model can give
        leave the status and the answer exactly as they were."""
        client, _ = _with_decisions(_workflow_router(200.0, [200.0] * 3), answers)
        state = await _run(client)
        assert state.status == "completed"
        assert state.outputs["implement"].summary == SUMMARY

    async def test_a_failed_call_is_a_recorded_skip_and_the_run_completes(
            self, decision_tier):
        client, _ = _with_decisions(_workflow_router(200.0, [200.0] * 3),
                                    error=RuntimeError("route gone"))
        state = await _run(client)
        assert state.status == "completed"
        notes = state.outputs["decision_notes"]
        assert notes["skipped"] is True and notes["asks"] == []


class TestPreflightKnowsTheTier:
    GOOD = {t: f"vendor/{t}" for t in ("triage", "engineering", "architecture",
                                       "escalation", "research", "search")}
    KNOWN = set(GOOD.values())

    def test_a_decision_pin_is_checked_against_who_serves_the_model(self):
        models = {**self.GOOD, "decision": "vendor/decider"}
        endpoints = {"vendor/decider": {"Vendor"}}
        ok, = [f for f in check(models, {"decision": "Vendor"}, self.KNOWN, endpoints)
               if f.subject == "pin decision"]
        assert ok.ok
        bad, = [f for f in check(models, {"decision": "Other"}, self.KNOWN, endpoints)
                if f.subject == "pin decision"]
        assert not bad.ok

    def test_an_unset_tier_makes_its_pin_unused(self):
        finding, = [f for f in check({**self.GOOD, "decision": ""},
                                     {"decision": "Vendor"}, self.KNOWN, {})
                    if f.subject == "pin decision"]
        assert finding.ok and "MODEL_DECISION is unset" in finding.detail

    def test_the_decisions_route_takes_no_chat_parameter(self):
        assert sent_parameters("decision") == ()
