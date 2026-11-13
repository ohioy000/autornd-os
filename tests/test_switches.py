"""Decision switches: cheap typed questions that guard expensive steps
(owner, 2026-11-13). Declared in switches/default.yaml, asked through the
optional decision tier, in shadow until the owner rules one live."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from autornd.graph.adapter import PhaseRunner
from autornd.graph.executor import GraphExecutor
from autornd.graph.spec import load
from autornd.knowledge import context as ctx
from autornd.knowledge import research
from autornd.preflight import check, sent_parameters
from autornd.routing import openrouter, switches
from autornd.routing.openrouter import ModelResponse, OpenRouterClient
from autornd.routing.switches import (
    DEFAULT, LIVE, NO, SHADOW, UNAVAILABLE, UNSURE, YES, Switch,
    Switchboard, SwitchError, load_switches, parse_switches,
    release_switchboard, use_switchboard)
from tests.test_recompute_vote import (REQUEST, SETTINGS, SUMMARY, _double,
                                       _workflow_router)

WORKFLOW = "workflows/answer-and-recompute.yaml"


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


def _switch(name="s", mode=SHADOW, safe=YES, each="") -> Switch:
    return Switch(name=name, question="Is it so?", yes="It is.", no="It is not.",
                  yes_at=0.8, no_at=0.2, safe=safe, mode=mode, each=each)


class _Decider:
    """A client double with a decision tier: answers each question with the
    probability `answer` gives for its evidence."""

    def __init__(self, answer=lambda evidence: 0.9, error=None, tier=True):
        self.calls: list[tuple[dict, dict]] = []
        self._answer, self._error, self._tier = answer, error, tier

    def decision_model(self):
        return "vendor/decider" if self._tier else None

    async def decide(self, state, questions):
        self.calls.append((state, questions))
        if self._error:
            raise self._error
        answers = {}
        for key in questions:
            p = self._answer(state[key])
            if p is not None:
                answers[key] = {"type": "noul", "noul": p}
        return answers, ModelResponse(content="", model="vendor/decider",
                                      prompt_tokens=10, completion_tokens=0,
                                      cost=0.00001)


@pytest.fixture
def board():
    """Install a switchboard for the knowledge layer; yields a maker."""
    tokens = []

    def make(client, **declared) -> Switchboard:
        made = Switchboard(client, declared)
        tokens.append(use_switchboard(made))
        return made

    yield make
    for token in reversed(tokens):
        try:
            release_switchboard(token)
        except ValueError:
            # Set inside the test's own task, whose context ended with it:
            # nothing is left to release.
            pass


class TestASwitchSettles:
    @pytest.mark.parametrize("probability, choice", [
        (1.0, YES), (0.8, YES), (0.79, UNSURE), (0.21, UNSURE),
        (0.2, NO), (0.0, NO), (None, UNAVAILABLE)])
    def test_the_thresholds_give_the_choice(self, probability, choice):
        assert _switch().settle(probability)["choice"] == choice

    @pytest.mark.parametrize("probability", [1.0, 0.5, 0.0, None])
    def test_in_shadow_the_route_is_always_default(self, probability):
        """Break-proof for "shadow acts on nothing": whatever the model
        says, the guarded step is told to do what it did before."""
        record = _switch(mode=SHADOW).settle(probability)
        assert record["route"] == DEFAULT and record["mode"] == SHADOW

    @pytest.mark.parametrize("safe", [YES, NO])
    def test_live_a_confident_answer_routes_and_anything_else_is_safe(self, safe):
        live = _switch(mode=LIVE, safe=safe)
        assert live.settle(0.95)["route"] == YES
        assert live.settle(0.05)["route"] == NO
        assert live.settle(0.5)["route"] == safe          # unsure
        assert live.settle(None)["route"] == safe         # the call failed


class TestTheDeclarations:
    GOOD = {"question": "q", "yes": "y", "no": "n",
            "yes_at": 0.8, "no_at": 0.2, "safe": "yes"}

    def test_yaml_booleans_are_read_as_yes_and_no(self):
        """YAML reads a bare yes or no as a boolean, as key and as value."""
        import yaml
        raw = yaml.safe_load(
            "s:\n  question: q\n  yes: y\n  no: n\n  yes_at: 0.8\n"
            "  no_at: 0.2\n  safe: no\n")
        assert True in raw["s"]            # the trap this test is about
        parsed = parse_switches(raw)["s"]
        assert (parsed.yes, parsed.no, parsed.safe) == ("y", "n", NO)
        assert parsed.mode == SHADOW       # shadow unless declared live

    @pytest.mark.parametrize("change", [
        {"yes_at": 0.2, "no_at": 0.8}, {"yes_at": 1.2}, {"no_at": -0.1},
        {"yes_at": 0.5, "no_at": 0.5}, {"safe": "maybe"}, {"mode": "on"},
        {"yes_at": "high"}])
    def test_a_switch_declared_wrongly_fails_at_load(self, change):
        with pytest.raises(SwitchError):
            parse_switches({"s": {**self.GOOD, **change}})

    @pytest.mark.parametrize("missing", ["question", "yes", "no", "yes_at",
                                         "no_at", "safe"])
    def test_every_field_that_decides_a_route_is_required(self, missing):
        body = {k: v for k, v in self.GOOD.items() if k != missing}
        with pytest.raises(SwitchError):
            parse_switches({"s": body})

    def test_a_missing_file_is_no_switches(self, tmp_path):
        assert load_switches(tmp_path / "none.yaml") == {}

    def test_only_a_ruled_switch_is_live_and_each_says_what_it_guards(self):
        """Moving a switch to live changes what the harness concludes: it
        is the owner's ruling. One is ruled (2026-11-13): needs_sources."""
        shipped = load_switches(switches.SWITCHES_FILE)
        assert sorted(shipped) == [
            "ask_covered", "chunk_helps", "finding_answers", "hard_request",
            "needs_sources", "quote_answers", "same_meaning"]
        assert sorted(s.name for s in shipped.values() if s.mode == LIVE) == [
            "needs_sources"]
        for switch in shipped.values():
            assert switch.guards and switch.safe in (YES, NO), switch.name
        # The side that does more work is the safe one.
        assert shipped["needs_sources"].safe == YES
        assert shipped["chunk_helps"].safe == YES
        assert shipped["finding_answers"].safe == NO
        # Unsure keeps the vote's flag: the careful side is "they differ".
        assert shipped["same_meaning"].safe == NO
        assert shipped["same_meaning"].each == "disagreements"


class TestTheSwitchboard:
    async def test_with_no_decision_tier_nothing_is_asked(self):
        client = _Decider(tier=False)
        made = Switchboard(client, {"s": _switch()})
        assert await made.ask([("s", "x", "evidence")]) == []
        assert await made.route("s", "evidence") == DEFAULT
        assert client.calls == [] and made.records == []

    async def test_many_questions_go_in_one_request(self):
        client = _Decider(lambda e: 0.9 if e == "a" else 0.1)
        made = Switchboard(client, {"s": _switch(mode=LIVE)})
        records = await made.ask([("s", "first", "a"), ("s", "second", "b"),
                                  ("unknown", "x", "c")])
        (state, questions), = client.calls
        assert state == {"q0": "a", "q1": "b"}
        assert questions["q0"] == {
            "type": "noul",
            "instructions": 'Look only at state["q0"]. Is it so?',
            "criteria": {"true": "It is.", "false": "It is not."}}
        assert [(r["item"], r["choice"], r["route"]) for r in records] == [
            ("first", YES, YES), ("second", NO, NO)]
        assert made.drain() == records and made.drain() == []

    @pytest.mark.parametrize("client", [
        _Decider(error=RuntimeError("route gone")),
        _Decider(lambda e: None),                    # a refusal: no probability
    ])
    async def test_a_failed_or_refused_answer_is_unavailable_and_safe(self, client):
        made = Switchboard(client, {"s": _switch(mode=LIVE, safe=YES)})
        record, = await made.ask([("s", "x", "e")])
        assert record["choice"] == UNAVAILABLE and record["route"] == YES
        assert record["probability"] is None

    async def test_questions_and_evidence_are_bounded(self):
        client = _Decider()
        made = Switchboard(client, {"s": _switch()})
        long = "x" * (switches.MAX_EVIDENCE_CHARS + 50)
        records = await made.ask(
            [("s", str(i), {"text": long}) for i in range(60)])
        assert len(records) == switches.MAX_QUESTIONS
        state, _ = client.calls[0]
        assert len(state["q0"]["text"]) == switches.MAX_EVIDENCE_CHARS


class TestNeedsSources:
    """The lookup trigger: (demanded whatever the gaps, wanted by the risk)."""

    @pytest.fixture(autouse=True)
    def _search(self, monkeypatch):
        monkeypatch.setattr(ctx.settings, "model_search", "vendor/search")

    async def test_with_no_switchboard_it_is_the_old_rule(self):
        assert await ctx._lookup_wanted("Size the heater.", "high") == (False, True)
        assert await ctx._lookup_wanted("Size the heater.", "low") == (False, False)

    async def test_in_shadow_it_is_asked_recorded_and_changes_nothing(self, board):
        client = _Decider(lambda e: 0.99)
        made = board(client, needs_sources=_switch("needs_sources"))
        assert await ctx._lookup_wanted("Size the heater.", "low") == (False, False)
        assert await ctx._lookup_wanted("Size the heater.", "high") == (False, True)
        assert [r["choice"] for r in made.records] == [YES, YES]
        assert client.calls[0][0] == {"q0": {"request": "Size the heater."}}

    async def test_live_a_yes_demands_the_lookup_at_any_risk(self, board):
        board(_Decider(lambda e: 0.99),
              needs_sources=_switch("needs_sources", mode=LIVE))
        assert await ctx._lookup_wanted("Size the heater.", "low") == (True, False)

    async def test_live_a_no_bars_the_lookup_the_risk_alone_asked_for(self, board):
        board(_Decider(lambda e: 0.01),
              needs_sources=_switch("needs_sources", mode=LIVE))
        assert await ctx._lookup_wanted("Size the heater.", "high") == (False, False)

    async def test_live_an_unsure_or_failed_answer_takes_the_safe_side(self, board):
        board(_Decider(lambda e: 0.5),
              needs_sources=_switch("needs_sources", mode=LIVE, safe=YES))
        assert await ctx._lookup_wanted("Size the heater.", "low") == (True, False)

    async def test_a_request_that_asks_for_sources_in_words_is_never_asked(self, board):
        """The free rule comes first, and a model's no cannot override it."""
        client = _Decider(lambda e: 0.0)
        board(client, needs_sources=_switch("needs_sources", mode=LIVE))
        assert await ctx._lookup_wanted(
            "State the limit. Cite the datasheet.", "low") == (True, False)
        assert client.calls == []

    async def test_with_no_search_model_there_is_nothing_to_guard(
            self, board, monkeypatch):
        monkeypatch.setattr(ctx.settings, "model_search", "")
        client = _Decider()
        board(client, needs_sources=_switch("needs_sources", mode=LIVE))
        assert await ctx._lookup_wanted("Size the heater.", "low") == (False, False)
        assert client.calls == []


CHUNKS = [{"text": "on the subject", "tag": "a", "distance": 0.3},
          {"text": "off the subject", "tag": "b", "distance": 0.6}]


class TestChunkHelps:
    answer = staticmethod(lambda e: 0.02 if "off" in e["excerpt"] else 0.97)

    async def test_with_no_switchboard_every_candidate_is_kept(self):
        assert await ctx._helpful_chunks("q", CHUNKS) == CHUNKS

    async def test_in_shadow_it_is_recorded_and_every_candidate_is_kept(self, board):
        made = board(_Decider(self.answer), chunk_helps=_switch("chunk_helps"))
        assert await ctx._helpful_chunks("the question", CHUNKS) == CHUNKS
        assert [(r["item"], r["choice"]) for r in made.records] == [
            ("a", YES), ("b", NO)]

    async def test_live_a_confident_no_drops_the_excerpt(self, board):
        board(_Decider(self.answer), chunk_helps=_switch("chunk_helps", mode=LIVE))
        assert await ctx._helpful_chunks("the question", CHUNKS) == CHUNKS[:1]

    async def test_live_a_failed_call_keeps_every_candidate(self, board):
        board(_Decider(error=RuntimeError("down")),
              chunk_helps=_switch("chunk_helps", mode=LIVE))
        assert await ctx._helpful_chunks("the question", CHUNKS) == CHUNKS


class TestFindingAnswers:
    def _stored(self, monkeypatch, distance):
        monkeypatch.setattr(research, "retrieve", lambda *a, **k: [
            {"text": "The cap is 60 s.", "source": "https://a.example/p",
             "tag": research.RESEARCH_TAG, "distance": distance}])

    async def test_in_shadow_it_is_recorded_and_the_lookup_still_runs(
            self, board, monkeypatch):
        self._stored(monkeypatch, 0.6)
        made = board(_Decider(lambda e: 0.99),
                     finding_answers=_switch("finding_answers", safe=NO))
        assert await research._recall_by_switch("What is the cap?") is None
        assert [r["choice"] for r in made.records] == [YES]

    async def test_live_a_yes_reuses_the_stored_finding(self, board, monkeypatch):
        self._stored(monkeypatch, 0.6)
        board(_Decider(lambda e: 0.99),
              finding_answers=_switch("finding_answers", mode=LIVE, safe=NO))
        finding = await research._recall_by_switch("What is the cap?")
        assert finding.recalled and finding.answer == "The cap is 60 s."
        assert finding.citations == ["https://a.example/p"]

    @pytest.mark.parametrize("probability", [0.5, 0.01, None])
    async def test_live_anything_but_a_confident_yes_looks_it_up(
            self, board, monkeypatch, probability):
        self._stored(monkeypatch, 0.6)
        board(_Decider(lambda e: probability),
              finding_answers=_switch("finding_answers", mode=LIVE, safe=NO))
        assert await research._recall_by_switch("What is the cap?") is None

    @pytest.mark.parametrize("distance", [
        0.05,                                         # the reuse rule's own ground
        research.REUSE_CANDIDATE_DISTANCE + 0.01])    # too far to be a candidate
    async def test_it_is_asked_only_between_the_two_bounds(
            self, board, monkeypatch, distance):
        self._stored(monkeypatch, distance)
        client = _Decider()
        board(client, finding_answers=_switch("finding_answers", mode=LIVE, safe=NO))
        assert await research._recall_by_switch("What is the cap?") is None
        assert client.calls == []


def _with_decisions(router, answer=lambda evidence: 0.9, error=None):
    client, calls = _double(router)
    asked: list[tuple[dict, dict]] = []

    async def decide(state, questions):
        asked.append((state, questions))
        if error:
            raise error
        client._account("decision", 0.00002)
        return ({key: {"type": "noul", "noul": answer(state[key])}
                 for key in questions},
                ModelResponse(content="", model="vendor/decider",
                              prompt_tokens=400, completion_tokens=0,
                              cost=0.00002))

    client.decide = AsyncMock(side_effect=decide)
    return client, asked


async def _run(client, recorded=None, declared=None, spec=None):
    runner = PhaseRunner(client)
    if declared is not None:
        runner.switchboard = Switchboard(client, declared)
    if recorded is not None:
        runner.on_phase = lambda node, verdict, responses, iteration: (
            recorded.append((node, verdict)))
    return await GraphExecutor(spec or load(WORKFLOW), runner, SETTINGS).run(REQUEST)


class TestTheSwitchNodes:
    async def test_with_no_tier_both_nodes_skip_and_every_route_is_default(self):
        recorded: list = []
        client, asked = _with_decisions(_workflow_router(200.0, [200.0] * 3))
        state = await _run(client, recorded)
        assert state.status == "completed" and asked == []
        for node, names in (("request_switches", ["hard_request"]),
                            ("answer_switches", ["same_meaning", "ask_covered",
                                                 "quote_answers"])):
            out = state.outputs[node]
            assert out["skipped"] is True and out["records"] == []
            assert out["route"] == {name: DEFAULT for name in names}
        assert not [n for n, _ in recorded if n == "switches"]

    async def test_with_the_tier_set_each_switch_is_asked_and_recorded(
            self, decision_tier):
        recorded: list = []
        client, asked = _with_decisions(_workflow_router(200.0, [200.0] * 3))
        state = await _run(client, recorded)
        assert state.status == "completed"
        before = state.outputs["request_switches"]
        assert [(r["switch"], r["item"], r["choice"], r["route"])
                for r in before["records"]] == [
            ("hard_request", "request", YES, DEFAULT)]
        assert before["route"] == {"hard_request": DEFAULT}
        after = state.outputs["answer_switches"]
        assert [(r["switch"], r["item"]) for r in after["records"]] == [
            ("ask_covered", "ask 1"), ("ask_covered", "ask 2")]
        assert ("request_switches", before) in recorded
        assert ("answer_switches", after) in recorded
        # The evidence each question saw.
        request_state, _ = asked[0]
        assert request_state == {"q0": {"request": REQUEST}}
        assert asked[-1][0]["q0"]["answer"] == SUMMARY

    @pytest.mark.parametrize("probability", [0.0, 0.5, 1.0])
    async def test_in_shadow_no_answer_changes_the_run(
            self, decision_tier, probability):
        """Break-proof for the shipped file: whatever every switch says,
        the answer and the status are what they are with no tier at all."""
        plain, _ = _with_decisions(_workflow_router(200.0, [200.0] * 3))
        monkey = OpenRouterClient.FUNCTION_MODELS.pop("decision")
        try:
            base = await _run(plain)
        finally:
            OpenRouterClient.FUNCTION_MODELS["decision"] = monkey
        client, _ = _with_decisions(_workflow_router(200.0, [200.0] * 3),
                                    answer=lambda e: probability)
        state = await _run(client)
        assert state.status == base.status == "completed"
        assert state.outputs["implement"].summary == base.outputs["implement"].summary
        assert state.outputs["recompute_vote"] == base.outputs["recompute_vote"]

    async def test_a_live_switch_puts_its_route_where_a_condition_can_read_it(
            self, decision_tier):
        client, _ = _with_decisions(_workflow_router(200.0, [200.0] * 3),
                                    answer=lambda e: 0.03)
        declared = {"hard_request": _switch("hard_request", mode=LIVE,
                                            each="request")}
        state = await _run(client, declared=declared)
        assert state.outputs["request_switches"]["route"] == {"hard_request": NO}
        assert state.status == "completed"

    async def test_a_failed_decision_call_never_fails_the_run(self, decision_tier):
        client, _ = _with_decisions(_workflow_router(200.0, [200.0] * 3),
                                    error=RuntimeError("route gone"))
        state = await _run(client)
        assert state.status == "completed"
        record, = state.outputs["request_switches"]["records"]
        assert record["choice"] == UNAVAILABLE and record["route"] == DEFAULT

    async def test_the_knowledge_layers_questions_are_written_to_the_record(
            self, decision_tier, monkeypatch):
        """The switches asked inside grounding have no node of their own:
        they reach the run's record through the phase channel."""
        monkeypatch.setattr(ctx.settings, "model_search", "vendor/search")
        recorded: list = []
        client, _ = _with_decisions(_workflow_router(200.0, [200.0] * 3))
        await _run(client, recorded)
        written = [v for n, v in recorded if n == "switches"]
        assert written and written[0]["where"] == "grounding"
        assert [r["switch"] for r in written[0]["records"]] == ["needs_sources"]

    async def test_several_requests_in_one_place_are_one_record(self, decision_tier):
        """Live pilot, 2026-11-13: grounding made three decision requests
        and the same records were written three times, a row per response."""
        written: list = []
        client, _ = _with_decisions(_workflow_router(200.0, [200.0] * 3))
        runner = PhaseRunner(client, on_phase=lambda *a: written.append(a))
        runner.switchboard = Switchboard(client, {"s": _switch()})
        state = type("S", (), {"iteration": 1})()
        async with runner._switching("grounding", state):
            for evidence in ("a", "b", "c"):
                await runner.switchboard.ask([("s", evidence, evidence)])
        (name, verdict, responses, _), = written
        assert name == "switches" and len(verdict["records"]) == 3
        assert len(responses) == 1
        assert responses[0].cost == pytest.approx(0.00006)


@pytest.fixture
def recompute_tier(monkeypatch):
    """The recompute tier set, so the vote has samples to compare."""
    monkeypatch.setattr(openrouter.settings, "model_recompute",
                        "vendor/recompute-tier")
    monkeypatch.setitem(OpenRouterClient.FUNCTION_MODELS, "recompute",
                        "vendor/recompute-tier")


def _worded(router, answer_words, sample_words):
    """The workflow double with ask 2, the verdict ask, stated in words:
    the answer's own, and every sample's."""
    def route(user_message, calls):
        data = router(user_message, calls)
        if user_message.startswith("Produce the answer to the following request"):
            data = dict(data, results=[data["results"][0],
                                       {"ask": 2, "value": answer_words, "unit": ""}])
        elif user_message.startswith(REQUEST):
            data = {"results": [data["results"][0],
                                {"ask": 2, "value": sample_words, "unit": ""}]}
        return data
    return route


class TestSameMeaning:
    """The vote's text flags, put to the decision tier in shadow (the owner,
    2026-11-13, on that day's same-meaning replay: yes on 9 of 10 flags on
    right answers, no on all 6 contrary pairs)."""

    async def test_a_text_flag_is_asked_with_a_samples_own_words(
            self, decision_tier, recompute_tier):
        client, asked = _with_decisions(_worded(
            _workflow_router(60.0, [60.0] * 3), "yes, full jitter applies", "Yes."))
        state = await _run(client)
        vote = state.outputs["recompute_vote"]
        assert vote["flagged"] is True
        assert [(d["ask"], d["majority"]) for d in vote["disagreements"]] == [(2, "YES")]
        first = state.outputs["answer_switches"]["records"][0]
        assert (first["switch"], first["item"], first["route"]) == (
            "same_meaning", "ask 2", DEFAULT)
        # The sample's words, not the identifier the vote compared.
        assert asked[-1][0]["q0"] == {"request": REQUEST,
                                      "answer_value": "yes, full jitter applies",
                                      "sample_value": "Yes."}

    @pytest.mark.parametrize("probability", [0.0, 1.0])
    async def test_in_shadow_its_answer_changes_nothing(
            self, decision_tier, recompute_tier, probability):
        runs = []
        for answer in (lambda e: 0.5, lambda e: probability):
            client, _ = _with_decisions(_worded(
                _workflow_router(60.0, [60.0] * 3), "yes, full jitter applies",
                "Yes."), answer=answer)
            runs.append(await _run(client))
        first, second = runs
        assert first.status == second.status == "completed"
        assert first.outputs["recompute_vote"] == second.outputs["recompute_vote"]
        assert first.outputs["recompute_vote"]["flagged"] is True

    @pytest.mark.parametrize("answer_value, samples", [
        (100.0, [200.0] * 3),     # a number flagged: not a question of words
        (60.0, [60.0] * 3)])      # nothing flagged
    async def test_only_a_text_flag_is_asked(
            self, decision_tier, recompute_tier, answer_value, samples):
        client, _ = _with_decisions(_workflow_router(answer_value, samples))
        state = await _run(client)
        assert state.outputs["recompute_vote"]["flagged"] is (answer_value == 100.0)
        switches_asked = [r["switch"] for r in
                          state.outputs["answer_switches"]["records"]]
        assert switches_asked and "same_meaning" not in switches_asked


class TestHeadAndTail:
    def test_a_text_within_the_bound_is_sent_as_it_is(self):
        text = "a" * switches.MAX_EVIDENCE_CHARS
        assert switches.head_and_tail(text) == text

    def test_a_long_text_keeps_its_opening_and_its_end_within_the_bound(self):
        text = "OPENING " + "middle " * 2000 + " THE VERDICT: PASS."
        sent = switches.head_and_tail(text)
        assert len(sent) == switches.MAX_EVIDENCE_CHARS
        assert sent.startswith("OPENING ") and sent.endswith("THE VERDICT: PASS.")
        assert f"{len(text)} characters in all" in sent

    async def test_ask_covered_is_shown_the_end_of_a_long_answer(self, decision_tier):
        """Golden batch 1's Q5 r2: its release step and verdict sat at
        characters 6553 and 8732 of 9265, past the head the switch saw."""
        long = SUMMARY + "\n\n" + "The timer is reviewed. " * 400 + "\nVERDICT: PASS."
        router = _workflow_router(200.0, [200.0] * 3)

        def route(user_message, calls):
            data = router(user_message, calls)
            if user_message.startswith("Produce the answer to the following request"):
                data = dict(data, summary=long)
            return data

        client, asked = _with_decisions(route)
        state = await _run(client)
        assert state.status == "completed"
        evidence = asked[-1][0]["q0"]
        assert evidence["item"] and len(long) > switches.MAX_EVIDENCE_CHARS
        assert evidence["answer"].startswith(SUMMARY[:200])
        assert evidence["answer"].endswith("VERDICT: PASS.")


class TestTheDelivery:
    def test_every_switch_record_is_returned_in_order(self):
        import json
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from autornd.api.routes import _detail

        def phase(n, name, verdict):
            return SimpleNamespace(
                phase=name, verdict_json=json.dumps(verdict), iteration=1,
                model_used="m", cost=0.0, id=n,
                created_at=datetime(2026, 11, 13, 0, 0, n, tzinfo=timezone.utc))

        record = lambda name: {"switch": name, "item": "x", "probability": 0.9,
                               "choice": YES, "mode": SHADOW, "route": DEFAULT}
        workflow = SimpleNamespace(
            id=1, request="r", status=SimpleNamespace(value="completed"),
            risk_level=None, iteration=1, total_cost=0.0,
            unreconciled_liability=0.0, error=None,
            created_at=datetime(2026, 11, 13, tzinfo=timezone.utc),
            updated_at=datetime(2026, 11, 13, tzinfo=timezone.utc),
            phases=[
                phase(1, "switches", {"where": "grounding",
                                      "records": [record("needs_sources")]}),
                phase(2, "request_switches", {"skipped": False, "route": {},
                                              "records": [record("hard_request")]}),
                phase(3, "implement", {"summary": "the answer"}),
            ])
        detail = _detail(workflow)
        assert [(d["switch"], d["where"]) for d in detail.decisions] == [
            ("needs_sources", "grounding"), ("hard_request", "request_switches")]


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
