"""The tier-3 runner, proved through the real machinery with
provider-free doubles (ARCH-20261003-119, tests (a)-(j)).

Every test runs the real runner (evals/tier3/runner.py,
imported by path - evals/ is not an installed package, the
way the tier-2 probes import it) with the model-serving layer
replaced by the runner's own doubles: a scripted client for
arms A-D that bills through the client's REAL guard and
accounting (convention 7: a test double must bill), a fixture
catalogue whose rates are installed in the real pricing table,
and a stand-in at the pipeline boundary for arm E. Nothing
reaches the network: the suite's guard (tests/conftest.py)
refuses every non-loopback socket and fails the offending
test, so the closed-world fetch tool's "opens no socket" is
proved by the guard itself, not asserted here.

Each test is proved by breaking one line of the runner and
quoting the failure - the break-proof is recorded under the
test it proves. A test that cannot fail proves nothing
(convention 22).

The ten tests, as the command orders them:
(a) the order - build_order and order_digest against an
    independent reconstruction, and a different seed must not
    reproduce it;
(b) each arm's treatment and call limits - arm B's
    final call keeps the tools declared with
    tool_choice "none", arm C's stage 3 runs only
    when the check objected;
(c) each gate's refusal - the three ratification gates, each
    naming what the owner must set;
(d) every failure class counted in its arm's 75-unit
    denominator - through the real dry run of all 375 units;
(e) resume - recorded units skipped, the in-flight unit
    charged its ceiling and re-run;
(f) arm E's "approved, not shipped" - scored and reported
    beside the delivered count, never counted as delivered;
(g) each preflight refusal - the five refusal cases,
    including the owner's max_completion_tokens addition;
(h) recompute's rejections - names, attributes and calls
    outside the whitelist, and an oversized exponent;
(i) fetch on each lookup question's citation in its written
    form, and a typed not-available otherwise;
(j) the reading sheet and the five measures computed both
    ways - scorer-only and with the readers' verdicts.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import json
import math
import os
import random
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
TIER2 = ROOT / "evals" / "tier2"
TIER3 = ROOT / "evals" / "tier3"

# The runner, imported by path: evals/ is not an installed
# package (the tier-2 probes do the same). The registration
# in sys.modules precedes exec_module - the runner's
# dataclasses look their module up there.
_SPEC = importlib.util.spec_from_file_location(
    "tier3_runner", TIER3 / "runner.py")
runner = importlib.util.module_from_spec(_SPEC)
sys.modules["tier3_runner"] = runner
_SPEC.loader.exec_module(runner)

# The runner put evals/tier2 on sys.path; the frozen scorer
# and the recorded-answer probe are the two instruments the
# runner scores with (D50 (1): the scorer is the screen).
import scorer                                     # noqa: E402
import regression_12                              # noqa: E402

QUESTIONS = {q["id"]: q for q in runner.load_questions()}
KEYS = {k["id"]: k for k in scorer.KEYS}

# The test lineup: placeholder serving names, never model
# ids (non-negotiable 6). Arm B's pin is arm A's pin, as
# the ratification gate requires.
TEST_SERVINGS = {
    "A": "test/arm-a",
    "B": "test/arm-a",
    "C": ["test/arm-c-1", "test/arm-c-2"],
    "D": "test/arm-d",
    "E": {tier: f"test/arm-e-{tier}"
          for tier in runner.PIPELINE_TIERS},
}
TEST_FINGERPRINT = runner.servings_fingerprint(TEST_SERVINGS)

# The fixture rates: small enough that every scripted call's
# worst case fits its arm's ceiling, so the REAL guard admits
# every call the dry run's script makes.
FIXTURE_PROMPT_RATE = 0.0000001
FIXTURE_COMPLETION_RATE = 0.0000002


def _fixture_catalogue(servings: dict[str, Any] = TEST_SERVINGS
                       ) -> list[dict[str, Any]]:
    """The fixture catalogue: every serving the test lineup
    names, with the fixture's rates and the parameters the
    preflight checks (the dry run's own fixture shape)."""
    return [
        {
            "id": serving,
            "pricing": {"prompt": f"{FIXTURE_PROMPT_RATE}",
                        "completion": f"{FIXTURE_COMPLETION_RATE}"},
            "context_length": 200000,
            "max_completion_tokens": 32768,
            "supported_parameters": [
                "tools", "response_format", "max_tokens",
                "temperature"],
        }
        for serving in runner._all_servings(servings)
    ]


@pytest.fixture
def fixture_rates():
    """The fixture's rates installed in the REAL pricing
    table (the seam the dry run uses), restored afterwards:
    the guard the doubles pass through is the real one."""
    from autornd.routing import openrouter as _openrouter
    catalogue = _fixture_catalogue()
    saved = {entry["id"]: _openrouter._model_pricing.get(
        entry["id"]) for entry in catalogue}
    runner._install_dry_run_rates(catalogue)
    try:
        yield {entry["id"]: (FIXTURE_PROMPT_RATE,
                             FIXTURE_COMPLETION_RATE)
               for entry in catalogue}
    finally:
        for serving, rates in saved.items():
            if rates is None:
                _openrouter._model_pricing.pop(serving, None)
            else:
                _openrouter._model_pricing[serving] = rates


# ── The scripted outcomes (the dry run's own shapes) ──────

def _answer(content: str, finish_reason: str = "stop",
            sleep: float = 0.0) -> dict[str, Any]:
    return {"content": content, "finish_reason": finish_reason,
            "prompt_tokens": 900, "completion_tokens": 1200,
            "sleep": sleep}


def _tool_call(name: str, arguments: dict[str, Any]
               ) -> dict[str, Any]:
    return {"content": "", "finish_reason": "tool_calls",
            "tool_calls": [{
                "id": "test", "type": "function",
                "function": {"name": name,
                             "arguments": json.dumps(arguments)}}]}


def _provider_failure(detail: str) -> dict[str, Any]:
    return {"provider_failure": detail}


def _correct(question_id: str) -> str:
    """The recorded real answer where the record holds one
    (the twelve vectors), the frozen key's model answer
    elsewhere - the dry run's own default."""
    recorded: dict[str, str] = {}
    for _run, qid, answer in regression_12.load_vectors():
        recorded.setdefault(qid, answer)
    return recorded.get(question_id) or KEYS[question_id][
        "model_answer"]


def _wrong(question_id: str) -> str:
    return KEYS[question_id]["common_wrong_answers"][0][
        "answer"]


def _script(
        calls: dict[tuple[str, int, str],
                        list[dict[str, Any]]] | None = None,
        arm_e: dict[str, dict[str, Any]] | None = None,
        deadlines: dict[tuple[str, int, str], float]
        | None = None,
        tool_failures: set[tuple[str, int, str]]
        | frozenset[tuple[str, int, str]] = frozenset(),
        ) -> runner.DryRunScript:
    """A dry-run script carrying only the entries the test
    names; every unit it does not name runs the DryRunScript
    default (an empty outcome list, which the client answers
    with an empty reply)."""
    script = runner.DryRunScript()
    for key, outcomes in (calls or {}).items():
        script._calls[key] = list(outcomes)
    for scenario_id, outcome in (arm_e or {}).items():
        script._arm_e[scenario_id] = dict(outcome)
    for key, seconds in (deadlines or {}).items():
        script._deadlines[key] = seconds
    script._tool_failures.update(tool_failures)
    return script


class RecordingClient(runner.DryRunClient):
    """The dry run's scripted client, with what every call was
    offered recorded beside it: the serving named, the tools
    offered, the response format, and the registered
    parameters. The billing is the inherited real machinery -
    the real guard, the real reservation, the real
    reconciliation, the real failure booking."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.offers: list[dict[str, Any]] = []

    async def chat(
            self, function: str, system_prompt: str,
            user_message: str,
            response_format: dict[str, Any] | None = None,
            temperature: float = 0.3,
            max_tokens: int = 16384,
            model: str | None = None,
            tools: list[dict[str, Any]] | None = None,
            tool_choice: str | None = None,
    ) -> runner.ModelResponse:
        self.offers.append({
            "function": function, "model": model,
            "tools": tools, "response_format": response_format,
            "tool_choice": tool_choice,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "user_message": user_message})
        return await super().chat(
            function, system_prompt, user_message,
            response_format=response_format,
            temperature=temperature, max_tokens=max_tokens,
            model=model, tools=tools,
            tool_choice=tool_choice)


class _Wiring:
    """The dry run's seams, wired for one test: the scripted
    client factory (recording what each call was offered), the
    tool dispatcher, the pipeline stand-in, and the clients
    the factory created - the test's window into what the
    runner did to the serving layer."""

    def __init__(self, script: runner.DryRunScript,
                 rates: dict[str, tuple[float, float]]) -> None:
        self.context = runner._DryRunContext()
        self.clients: list[RecordingClient] = []

        def factory(unit_key, arm, serving, ceiling,
                    call_limit):
            self.context.unit_key = unit_key
            client = RecordingClient(
                script, unit_key, serving, rates, ceiling,
                call_limit)
            self.clients.append(client)
            return client

        self.client_factory = factory
        self.tool_dispatcher = runner._dry_run_tool_dispatcher(
            script, self.context)
        self.scenario_runner = runner.DryRunScenarioRunner(
            script)


def _run(coro):
    return asyncio.run(coro)


# ── (a) The order ─────────────────────────────────────────

class TestATheOrder:
    def test_the_order_is_the_guard_reconstruction(self):
        # The stage-1 plan's order: over the seven
        # selected questions, not the frozen set's 25.
        selected = runner.stage1_questions()
        assert [q["id"] for q in selected] == list(
            runner.STAGE1_QUESTION_IDS)
        order = runner.build_order(
            runner.SEED, runner.REPITIONS, runner.ARMS,
            selected)
        # The independent reconstruction: the manifest's own
        # comprehension and seed, built here from the frozen
        # questions, not from the runner's code.
        units = [[question["id"], repetition, arm]
                 for question in selected
                 for repetition in (1, 2, 3)
                 for arm in runner.ARMS]
        random.Random(runner.SEED).shuffle(units)
        # The runner's order IS that reconstruction.
        assert order == units
        # A permutation: 105 units, every one once, none
        # invented, none dropped.
        assert len(order) == 105
        assert len({tuple(unit) for unit in order}) == 105
        assert {tuple(unit) for unit in order} == {
            tuple(unit) for unit in units}
        # The digest both sides compute is the same figure.
        assert (runner.order_digest(order)
                == runner.order_digest(units))
        # The seed is load-bearing: a different seed must not
        # reproduce the order, or the reconstruction proves
        # nothing.
        other = runner.build_order(
            runner.SEED + 1, runner.REPITIONS, runner.ARMS,
            selected)
        assert other != order
        # Break-proof (runner.py, build_order):
        #     random.Random(seed).shuffle(units)
        #     -> random.Random(seed + 1).shuffle(units)
        # FAILED tests/test_tier3_runner.py::TestATheOrder::
        # test_the_order_is_the_guard_reconstruction -
        # AssertionError: assert [['Q4', 1, 'B... 3, 'C'],
        # ...] == [['Q18', 2, '... 1, 'C'], ...] / At index
        # 0 diff: ['Q4', 1, 'B'] != ['Q18', 2, 'D'] : the
        # runner's order is not the guard's reconstruction -
        # the two shuffles disagree from the first unit, so
        # the seed the manifest registers is not the seed the
        # runner executes.


# ── (b) The arm treatments and call limits ────────────────

class TestBTheArmTreatments:
    def test_arms_a_and_d_make_one_call_with_no_tools(
            self, fixture_rates):
        script = _script(calls={("Q1", 1, "A"): [
            _answer(_correct("Q1"))]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q1", 1, "A"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory))
        assert result.status == "delivered"
        assert result.calls == 1
        assert result.scorer["verdict"] == "PASS"
        client = wiring.clients[0]
        assert len(client.offers) == 1
        # The registered call: the serving named directly,
        # the registered max_tokens and temperature, and no
        # tools - arms A and D differ only in the serving.
        offer = client.offers[0]
        assert offer["model"] == TEST_SERVINGS["A"]
        assert offer["tools"] is None
        assert offer["max_tokens"] == runner.REGISTERED_MAX_TOKENS
        assert offer["temperature"] == runner.REGISTERED_TEMPERATURE
        # Break-proof (runner.py, _arm_single):
        #     response = await _registered_call(
        #         client, f"tier3_arm_{arm.lower()}", ...)
        #     -> one extra _registered_call appended after it
        # FAILED ...::test_arms_a_and_d_make_one_call_with_
        # no_tools - AssertionError: assert 'incomplete'
        # == 'delivered' : the second call hit the unit
        # client's registered call ceiling (the guard
        # refused it), so the single-call arms made two
        # calls - the A-vs-D gap would be a call-count
        # gap, not a serving gap.

    def test_arm_b_keeps_the_tools_declared_on_the_final_call(
            self, fixture_rates):
        citation = runner._citation_in(QUESTIONS["Q7"]["question"])
        assert citation == "29 CFR 1910.95"
        script = _script(calls={("Q7", 1, "B"): [
            _tool_call("fetch_primary_source",
                       {"citation": citation}),
            _tool_call("recompute", {"expression": "90 / 2"}),
            _answer(_correct("Q7")),
        ]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q7", 1, "B"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory,
            tool_dispatcher=wiring.tool_dispatcher))
        assert result.status == "delivered"
        assert result.calls == runner.ARM_B_CALL_LIMIT
        assert result.scorer["verdict"] == "PASS"
        client = wiring.clients[0]
        # Calls 1 and 2 offer the tools with no
        # tool_choice; call 3 keeps them declared, with
        # tool_choice "none" - the model sees the tools
        # it may not use, and answers.
        assert client.offers[0]["tools"] == runner.TOOL_SPEC
        assert client.offers[0]["tool_choice"] is None
        assert client.offers[1]["tools"] == runner.TOOL_SPEC
        assert client.offers[1]["tool_choice"] is None
        assert client.offers[2]["tools"] == runner.TOOL_SPEC
        assert client.offers[2]["tool_choice"] == "none"
        # Every call carries the registered parameters and
        # names the serving (arm B's pin is arm A's pin).
        for offer in client.offers:
            assert offer["model"] == TEST_SERVINGS["B"]
            assert offer["max_tokens"] == (
                runner.REGISTERED_MAX_TOKENS)
            assert offer["temperature"] == (
                runner.REGISTERED_TEMPERATURE)
        # Each round's tool results are inlined into the next
        # call's user message - the text the model would have
        # seen in a tool-result turn. The second call carries
        # the fetch's archived text; the third carries the
        # recompute's value.
        assert "fetch_primary_source" in (
            client.offers[1]["user_message"])
        assert "July 1, 2014" in (
            client.offers[1]["user_message"])
        assert "recompute" in client.offers[2]["user_message"]
        assert "90 / 2" in client.offers[2]["user_message"]
        # Every invocation is recorded: the tool, its
        # arguments, the result's size, no error.
        assert len(result.tool_invocations) == 2
        for invocation in result.tool_invocations:
            assert invocation["ok"] is True
            assert invocation["result_size"] > 0
        assert result.tool_invocations[0]["tool"] == (
            "fetch_primary_source")
        assert result.tool_invocations[1]["tool"] == "recompute"
        # The fetch returned the archived July 1, 2014 text.
        assert result.tool_invocations[0]["result"][
            "available"] is True
        assert result.tool_invocations[0]["result"][
            "edition"] == "July 1, 2014"
        # Break-proof (runner.py, _arm_b):
        #     choice = ("none" if call_number == ARM_B_CALL_LIMIT
        #               else None)
        #     -> choice = None
        # FAILED ...::test_arm_b_keeps_the_tools_declared_on_
        # the_final_call - AssertionError: assert
        # None == 'none' : the final call was sent no
        # tool_choice, so the serving saw the tools with
        # no instruction not to use them - the registered
        # treatment (call 3 keeps them declared with
        # tool_choice "none") is not what the runner
        # sent.

    def test_arm_b_stops_at_the_registered_call_limit(
            self, fixture_rates):
        # A serving that asks for a tool on every call: the
        # loop stops at the registered 3-call limit, and the
        # unit is a refusal (the third call's content is the
        # answer, and a tool-call outcome carries none).
        tool = _tool_call("recompute", {"expression": "1 + 1"})
        script = _script(calls={("Q1", 1, "B"): [
            tool, tool, tool]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q1", 1, "B"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory,
            tool_dispatcher=wiring.tool_dispatcher))
        client = wiring.clients[0]
        assert len(client.offers) == runner.ARM_B_CALL_LIMIT
        assert result.calls == runner.ARM_B_CALL_LIMIT
        assert result.status == "refusal"
        # Break-proof (runner.py, _arm_b):
        #     for call_number in range(1, ARM_B_CALL_LIMIT + 1):
        #     -> for call_number in range(1, ARM_B_CALL_LIMIT)
        # (the drafted widening to range(1, 10) is defeated
        # by the break at the limit - the range and the
        # break bound the loop together; the narrowing
        # proves the test pins the exact bound)
        # FAILED ...::test_arm_b_stops_at_the_registered_call_
        # limit - AssertionError: assert 2 == 3 (the
        # offers count) : the loop ran two of the three
        # registered calls, so the registered call limit
        # was not the bound the runner enforced - a model
        # that never answered would drive the unit's call
        # count (and its cost) off the registered bound.

    def test_arm_c_delivers_the_draft_when_the_check_concurs(
            self, fixture_rates):
        draft = _correct("Q1")
        script = _script(calls={("Q1", 1, "C"): [
            _answer(draft),
            _answer('{"concur": true, "objections": []}'),
        ]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q1", 1, "C"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory))
        assert result.status == "delivered"
        # No third call: the check concurred, so there is
        # nothing to revise - the protocol, not the model's
        # discretion, decides what is delivered.
        assert result.calls == 2
        assert result.answer == draft
        assert result.check["status"] == "concurred"
        assert result.check["verdict"] == {
            "concur": True, "objections": []}
        # The check was requested as JSON through the client's
        # response_format handling, on the check serving.
        check_offer = wiring.clients[0].offers[1]
        assert check_offer["response_format"] == {
            "type": "json_object"}
        assert check_offer["model"] == TEST_SERVINGS["C"][1]
        # Break-proof (runner.py, _arm_c):
        #     if verdict.concur:
        #         check_record["status"] = "concurred"
        #         return draft, finish_reasons, check_record
        #     -> the return deleted (the concurring branch
        #        no longer returns the draft)
        # FAILED ...::test_arm_c_delivers_the_draft_when_the_
        # check_concurred - AssertionError: assert
        # 'refusal' == 'delivered' : a concurring check
        # no longer returned the draft - the unit fell
        # through to the revision round, whose scripted
        # call carries no answer, and the unit was recorded
        # a refusal. The draft the protocol delivers on
        # concurrence was never returned.

    def test_arm_c_revises_once_when_the_check_objects(
            self, fixture_rates):
        draft = _wrong("Q1")
        revised = _correct("Q1")
        objection = ("Step 2 divides by the pressure it "
                     "just measured; the question's text "
                     "requires the pressure before release.")
        script = _script(calls={("Q1", 1, "C"): [
            _answer(draft),
            _answer(json.dumps(
                {"concur": False, "objections": [objection]})),
            _answer(revised),
        ]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q1", 1, "C"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory))
        assert result.status == "delivered"
        assert result.calls == runner.ARM_C_CALL_LIMIT
        assert result.check["status"] == "objected"
        assert result.check["verdict"] == {
            "concur": False, "objections": [objection]}
        # The delivered answer is the revision, and the
        # objections reached the revision call.
        assert result.answer == revised
        assert objection in wiring.clients[0].offers[2][
            "user_message"]
        # Break-proof (runner.py, _arm_c):
        #     if verdict.concur:
        #     -> if True:
        # FAILED ...::test_arm_c_revises_once_when_the_check_
        # objects - AssertionError: assert 2 == 3 (the
        # call count; the check record reads 'concurred',
        # not 'objected') : an objecting check was
        # recorded as concurrence, no revision ran, and
        # the wrong draft was delivered - the one
        # revision round the protocol registers never
        # happened.

    def test_arm_c_records_an_invalid_verdict_unavailable(
            self, fixture_rates):
        # The check answers in prose, twice: no valid verdict
        # after the bounded retries, recorded as unavailable -
        # never as concurrence - and the draft delivered.
        draft = _correct("Q1")
        script = _script(calls={("Q1", 1, "C"): [
            _answer(draft),
            _answer("The draft looks sound to me; I have no "
                    "objections to raise."),
            _answer("I concur with the draft as it stands."),
        ]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q1", 1, "C"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory))
        assert result.status == "delivered"
        assert result.calls == runner.ARM_C_CALL_LIMIT
        assert result.check["status"] == "unavailable"
        assert result.check["verdict"] is None
        assert result.check["attempts"] == (
            runner.ARM_C_CHECK_ATTEMPTS)
        assert result.check["raw_replies"] == [
            "The draft looks sound to me; I have no "
            "objections to raise.",
            "I concur with the draft as it stands."]
        # The draft is delivered - an unavailable check is
        # never a concurrence, and never a refusal to deliver.
        assert result.answer == draft
        # Break-proof (runner.py, _arm_c):
        #     if verdict is None:
        #         check_record["status"] = "unavailable"
        #         return draft, finish_reasons, check_record
        #     -> check_record["status"] = "concurred"
        #        (return unchanged)
        # FAILED ...::test_arm_c_records_an_invalid_verdict_
        # unavailable - AssertionError: assert
        # 'concurred' == 'unavailable' : a check that
        # answered in prose twice was recorded as
        # concurrence - control flow read prose, and an
        # unvalidated draft would have been delivered as
        # checked.

    def test_arm_c_starves_the_revision_when_no_call_remains(
            self, fixture_rates):
        # The first check reply is invalid, the second objects:
        # the bounded retries spent the third call, so the
        # revision is starved - recorded, not hidden - and the
        # draft is delivered with the objection beside it.
        draft = _correct("Q1")
        script = _script(calls={("Q1", 1, "C"): [
            _answer(draft),
            _answer("not a verdict"),
            _answer(json.dumps(
                {"concur": False,
                 "objections": ["The draft omits the second "
                               "part the question asks."]})),
        ]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q1", 1, "C"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory))
        assert result.calls == runner.ARM_C_CALL_LIMIT
        assert result.check["status"] == "starved"
        assert result.check["verdict"]["concur"] is False
        assert result.answer == draft
        # Break-proof (runner.py, _arm_c):
        #     if calls >= ARM_C_CALL_LIMIT:
        #         check_record["status"] = "starved"
        #         return draft, finish_reasons, check_record
        #     -> removed (the revision call runs unconditionally)
        # FAILED ...::test_arm_c_starves_the_revision_when_the_
        # objection_spends_the_last_call - AssertionError:
        # assert 0 == 3 (the call count; the unit is
        # 'incomplete') : the revision call ran past the
        # hard whole-sequence call bound and the unit's
        # own client refused it (the guard's call
        # ceiling), so the check's bounded retries no
        # longer compete with the revision for the third
        # call - the bound the manifest registers is not
        # the bound the runner enforces.

    def test_the_typed_check_accepts_only_typed_verdicts(self):
        concur = runner.parse_check_verdict(
            '{"concur": true, "objections": []}')
        assert concur is not None and concur.concur is True
        assert concur.objections == []
        object_ = runner.parse_check_verdict(
            '{"concur": false, "objections": ["Step 2 is wrong."]}')
        assert object_ is not None and object_.concur is False
        assert object_.objections == ["Step 2 is wrong."]
        # Every invalid shape is not a verdict: concur with
        # objections, not-concur without them, a non-bool
        # concur, missing fields, non-list objections,
        # non-string entries, prose, and a non-object.
        for payload in (
                '{"concur": true, "objections": ["x"]}',
                '{"concur": false, "objections": []}',
                '{"concur": "true", "objections": []}',
                '{"concur": true}',
                '{"objections": []}',
                '{"concur": true, "objections": "none"}',
                '{"concur": true, "objections": [1]}',
                'concur',
                '[{"concur": true, "objections": []}]'):
            assert runner.parse_check_verdict(payload) is None, (
                f"the payload {payload!r} parsed as a verdict - "
                "control flow would read prose")
        # Break-proof (runner.py, parse_check_verdict):
        #     if concur and objections:
        #         return None
        #     -> removed
        # FAILED ...::test_the_typed_check_accepts_only_typed_
        # verdicts - AssertionError: the payload
        # '{"concur": true, "objections": ["x"]}' parsed
        # as a verdict - assert
        # CooperationCheckVerdict(concur=True,
        # objections=['x']) is None : a verdict with
        # concur true AND a non-empty objections list
        # parsed - the two fields contradict each other,
        # and the runner would have delivered the
        # contradiction as a check.

    def test_the_failure_classes_through_the_unit_driver(
            self, fixture_rates):
        # Refusal: a serving that chose to answer nothing.
        script = _script(calls={("Q1", 1, "A"): [
            _answer("")]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q1", 1, "A"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory))
        assert result.status == "refusal"
        # Incomplete: a serving that consumed its budget and
        # emitted nothing - and the call it failed after
        # dispatch keeps its worst case as liability.
        script = _script(calls={("Q1", 1, "D"): [
            _provider_failure(
                "scripted: the serving consumed its budget and "
                "emitted nothing")]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q1", 1, "D"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory))
        assert result.status == "incomplete"
        assert result.stop_reason.startswith("ProviderFailure")
        assert result.unreconciled_liability > 0.0
        # Deadline: a call that outlasts the unit's deadline,
        # cancelled by the runner's wait_for.
        script = _script(
            calls={("Q2", 1, "D"): [
                _answer(_correct("Q2"), sleep=0.25)]},
            deadlines={("Q2", 1, "D"): 0.05})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q2", 1, "D"), QUESTIONS, TEST_SERVINGS, None,
            deadline_overrides={("Q2", 1, "D"): 0.05},
            client_factory=wiring.client_factory))
        assert result.status == "deadline"
        assert "deadline" in (result.stop_reason or "").lower()
        # Break-proof (runner.py, run_unit):
        #     except asyncio.TimeoutError:
        #         result.status = "deadline"
        #     -> result.status = "incomplete"
        # FAILED ...::test_the_failure_classes_through_the_unit_
        # driver - AssertionError: assert 'incomplete'
        # == 'deadline' : a unit the watchdog stopped
        # was recorded as incomplete, so the timeout
        # failure class the manifest names would be
        # invisible in the census.

    def test_serving_error_is_its_own_failure_class(
            self, fixture_rates):
        # An empty reply with finish "error" on arm B's
        # final call: the serving failed the call (the
        # stage-1 run's 13 arm-B final-call errors
        # carried finish "error" and 0 tokens), so the
        # unit is a serving_error - its own class, never
        # a refusal.
        script = _script(calls={("Q7", 1, "B"): [
            _tool_call("fetch_primary_source",
                       {"citation": "29 CFR 1910.95"}),
            _tool_call("recompute",
                       {"expression": "90 / 2"}),
            _answer("", finish_reason="error")]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q7", 1, "B"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory,
            tool_dispatcher=wiring.tool_dispatcher))
        assert result.status == "serving_error"
        assert "finish 'error'" in result.stop_reason
        assert result.calls == runner.ARM_B_CALL_LIMIT
        # The census counts it in its own class, beside
        # and never inside the refusal count.
        census = runner.failure_census([result.record()])
        assert census.get("serving_error") == 1
        assert "refusal" not in census
        # A plain empty reply (finish "stop") stays a
        # refusal: only finish "error" names the serving.
        script = _script(calls={("Q7", 1, "B"): [
            _answer("")]})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q7", 1, "B"), QUESTIONS, TEST_SERVINGS, None,
            client_factory=wiring.client_factory,
            tool_dispatcher=wiring.tool_dispatcher))
        assert result.status == "refusal"
        # Break-proof (runner.py, run_unit):
        #     result.status = "serving_error"
        #     -> result.status = "refusal"
        # FAILED ...::test_serving_error_is_its_own_
        # failure_class - AssertionError: assert
        # 'refusal' == 'serving_error' : the
        # serving's failed call was charged to the
        # model as a refusal - the class the
        # manifest names would be invisible in the
        # census, and the arm's refusal rate would
        # carry the provider's failures.


# ── (c) The ratification gates ──────────────────────

def _settings(**overrides: str) -> runner.Tier3Settings:
    values = {
        "tier3_arm_a": TEST_SERVINGS["A"],
        "tier3_arm_b": TEST_SERVINGS["B"],
        "tier3_arm_c_1": TEST_SERVINGS["C"][0],
        "tier3_arm_c_2": TEST_SERVINGS["C"][1],
        "tier3_arm_d": TEST_SERVINGS["D"],
    }
    values.update(overrides)
    return runner.Tier3Settings(**values)


@contextlib.contextmanager
def _gates_cleared():
    """The suite's environment with every TIER3_* pin
    absent - the owner's run, before the owner sets
    anything (AUTORND_TESTING keeps .env out of the
    suite, so the environment is the whole state)."""
    names = ("TIER3_ARM_A", "TIER3_ARM_B", "TIER3_ARM_C_1",
             "TIER3_ARM_C_2", "TIER3_ARM_D",
             "TIER3_SERVINGS_RATIFIED",
             "TIER3_SPEND_AUTHORIZED",
             "TIER3_PILOT_AUTHORIZED")
    saved = {name: os.environ.get(name) for name in names}
    for name in names:
        os.environ.pop(name, None)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class TestCTheGates:
    def test_a_cleared_run_has_no_missing_gate(self):
        tier3 = _settings(
            tier3_servings_ratified=TEST_FINGERPRINT,
            tier3_spend_authorized=f"{runner.MAIN_CEILING:.2f}")
        missing = runner.gate_report(
            tier3, TEST_SERVINGS, TEST_FINGERPRINT,
            pilot=False)
        assert missing == []

    def test_each_gate_refuses_and_names_what_to_set(self):
        # Gate 1, unset: the ratification itself.
        tier3 = _settings()
        missing = runner.gate_report(
            tier3, TEST_SERVINGS, TEST_FINGERPRINT,
            pilot=False)
        assert "TIER3_SERVINGS_RATIFIED is not set" in missing
        assert "TIER3_SPEND_AUTHORIZED is not set" in missing
        # Gate 1, set wrong: the refusal names the
        # fingerprint and the value the owner gave.
        tier3 = _settings(tier3_servings_ratified="deadbeef")
        missing = runner.gate_report(
            tier3, TEST_SERVINGS, TEST_FINGERPRINT,
            pilot=False)
        assert any(
            "TIER3_SERVINGS_RATIFIED is 'deadbeef'" in d
            and TEST_FINGERPRINT in d for d in missing)
        # Gate 1, arm B's pin resolving to a different
        # serving than arm A's: the refusal names both.
        tier3 = _settings(
            tier3_arm_b="test/arm-b",
            tier3_servings_ratified=TEST_FINGERPRINT,
            tier3_spend_authorized=f"{runner.MAIN_CEILING:.2f}")
        missing = runner.gate_report(
            tier3, TEST_SERVINGS, TEST_FINGERPRINT,
            pilot=False)
        assert any(
            "TIER3_ARM_B does not resolve to the same "
            "serving as TIER3_ARM_A" in d
            and "test/arm-b" in d and "test/arm-a" in d
            for d in missing)
        # Gate 2, below the ceiling: the refusal names
        # the amount and the ceiling.
        tier3 = _settings(
            tier3_servings_ratified=TEST_FINGERPRINT,
            tier3_spend_authorized="10.00")
        missing = runner.gate_report(
            tier3, TEST_SERVINGS, TEST_FINGERPRINT,
            pilot=False)
        assert any(
            "TIER3_SPEND_AUTHORIZED is 10.00, below the "
            "main run's authorization ceiling $30.00" in d
            for d in missing)
        # Gate 2, not a dollar amount at all.
        tier3 = _settings(
            tier3_servings_ratified=TEST_FINGERPRINT,
            tier3_spend_authorized="yes")
        missing = runner.gate_report(
            tier3, TEST_SERVINGS, TEST_FINGERPRINT,
            pilot=False)
        assert any("not a dollar amount" in d for d in missing)
        # The pilot's own gate: its ceiling, its
        # authorization, named as the pilot's.
        tier3 = _settings(
            tier3_servings_ratified=TEST_FINGERPRINT,
            tier3_pilot_authorized="1.00")
        missing = runner.gate_report(
            tier3, TEST_SERVINGS, TEST_FINGERPRINT,
            pilot=True)
        assert any(
            "TIER3_PILOT_AUTHORIZED is 1.00, below the "
            "pilot's authorization ceiling $7.50" in d
            for d in missing)
        # Break-proof (runner.py, gate_report):
        #     if tier3.tier3_arm_b != tier3.tier3_arm_a:
        #     -> if tier3.tier3_arm_b == tier3.tier3_arm_a:
        # FAILED ...::test_each_gate_refuses_and_names_what_to_
        # set - AssertionError: assert False, where
        # False = any(... "TIER3_ARM_B does not resolve
        # to the same serving as TIER3_ARM_A" ...) : an
        # arm-B-mismatch lineup reported no missing gate
        # - the gate that isolates the tool treatment
        # would not stop a mismatched lineup (and a
        # cleared run would have reported one).

    def test_the_run_refuses_when_a_gate_is_missing(
            self, tmp_path):
        path = tmp_path / "refused.jsonl"
        with _gates_cleared():
            with pytest.raises(runner.ExperimentRefused) as raised:
                _run(runner.run_experiment(
                    "main", results_path=path))
        assert (raised.value.reason
                == "the ratification gates are not cleared")
        assert any("TIER3_SERVINGS_RATIFIED is not set"
                   in d for d in raised.value.detail)
        assert any("TIER3_SPEND_AUTHORIZED is not set"
                   in d for d in raised.value.detail)
        # The refusal carries the map it would have run.
        assert raised.value.servings == runner.resolve_servings(
            runner.Tier3Settings())
        assert raised.value.fingerprint
        # Nothing was written: the refusal precedes the
        # record, and no unit ran.
        assert not path.exists()
        # Break-proof (runner.py, run_experiment):
        #     if missing:
        #         raise ExperimentRefused(...)
        #     -> if missing and False:
        # FAILED ...::test_the_run_refuses_when_a_gate_is_
        # missing - DID NOT RAISE
        # <class 'tier3_runner.ExperimentRefused'>; the
        # run started with the gates uncleared and
        # reached for the provider catalogue - GET
        # https://openrouter.ai/api/v1/models - until
        # the suite's network guard stopped it
        # (httpx.ConnectError: the suite may not reach
        # "b'openrouter.ai'" — no network
        # (ARCH-20261002-112); network guard: 1
        # non-loopback attempt(s) recorded -
        # ["resolve b'openrouter.ai'"]) : a process
        # with the owner's unset .env would have
        # paid for units the owner never authorized.


# ── (d) Every failure class in its arm's denominator ─

class TestDTheFailureClasses:
    def test_the_dry_run_proves_the_whole_machinery(
            self, tmp_path):
        # The dry run's evidence paths are the runner's
        # own (evals/results/, git-ignored scratch); the
        # test redirects them so the run starts from a
        # clean slate whatever earlier runs left there -
        # the resume guard refuses a results file whose
        # recorded plan differs, and an earlier version's
        # file is exactly that.
        saved_results_dir = runner.RESULTS_DIR
        runner.RESULTS_DIR = tmp_path
        try:
            result = _run(runner.dry_run())
        finally:
            runner.RESULTS_DIR = saved_results_dir
        # The main run: 105 units, killed after the
        # registered point, resumed to the end.
        assert result["main"]["units"] == 105
        assert result["main"]["resumed"] is True
        assert result["main"]["charged_liability"] > 0.0
        killed = result["killed"]
        assert killed["units"] == runner.DRY_RUN_KILL_AFTER
        assert killed["in_flight"] is not None
        # The pilot: 50 units, 25 per arm.
        assert result["pilot"]["units"] == 50
        # Every failure class the command names, counted -
        # in the census, and in its arm's 21-unit
        # denominator (the planned count is the
        # denominator, never the delivered count).
        census = result["main"]["census"]
        for failure in (
                "refusal", "serving_error", "deadline",
                "tool_failure",
                "incomplete",
                "check:concurred", "check:objected",
                "check:unavailable",
                "delivery:shipped",
                "delivery:approved, not shipped",
                "delivery:no answer"):
            assert census.get(failure, 0) >= 1, (
                f"the dry run's census holds no "
                f"{failure!r} - the failure class the "
                f"command names is not included")
        measures = result["main"]["measures"][
            "delivered_correctness_per_arm"]
        for arm in runner.ARMS:
            assert measures[arm]["planned"] == 21, (
                f"arm {arm}'s denominator is not 21")
        # The order's digest is the guard's reconstruction
        # (test (a) rebuilds it independently).
        units = [[question["id"], repetition, arm]
                 for question in runner.stage1_questions()
                 for repetition in (1, 2, 3)
                 for arm in runner.ARMS]
        random.Random(runner.SEED).shuffle(units)
        assert (result["order_sha256"]
                == runner.order_digest(units))
        # The reading sheet exists, and the merge
        # demonstrates both its agreement and its
        # disagreement paths.
        sheet = result["reading_sheet"]
        assert sheet["entries"] > 0
        assert (sheet["merged"]
                + len(sheet["disagreements"])
                + len(sheet["unread"])) == sheet["entries"]
        # The measures, computed both ways, are reported
        # side by side (test (j) proves the computation).
        assert "measures_read" in result["main"]
        # Break-proof (runner.py, failure_census):
        #     if any(not invocation.get("ok", True)
        #            for invocation in record.get(
        #                "tool_invocations") or []):
        #     -> if False:
        # FAILED ...::test_the_dry_run_proves_the_whole_
        # machinery - AssertionError: the dry run's
        # census holds no 'tool_failure' - the failure
        # class the command names is not included;
        # assert 0 >= 1, where 0 = {'delivered': 371,
        # 'delivery:shipped': 73, 'check:concurred': 73,
        # 'check:unavailable': 1, ...}.get(
        # 'tool_failure', 0) : the tool-failure
        # class the manifest names was not counted, so a
        # run whose tools all failed would read as a clean
        # one.


# ── (e) The resume ──────────────────────────────────

class TestETheResume:
    def test_resume_skips_recorded_and_reruns_the_in_flight(
            self, tmp_path, fixture_rates):
        path = tmp_path / "results.jsonl"
        catalogue = _fixture_catalogue()
        script = runner.build_dry_run_script()
        wiring = _Wiring(script, fixture_rates)

        class _CountingScenarioRunner:
            """The dry run's pipeline stand-in, counting
            its runs: arm E's units execute here, the way
            arms A-D's execute in the client factory -
            the two seams together are every unit that
            runs."""

            def __init__(self, inner) -> None:
                self.inner = inner
                self.runs = 0

            async def __call__(self, *args, **kwargs):
                self.runs += 1
                return await self.inner(*args, **kwargs)

        scenario_runner = _CountingScenarioRunner(
            runner.DryRunScenarioRunner(script))
        overrides = {
            "TIER3_ARM_A": TEST_SERVINGS["A"],
            "TIER3_ARM_B": TEST_SERVINGS["B"],
            "TIER3_ARM_C_1": TEST_SERVINGS["C"][0],
            "TIER3_ARM_C_2": TEST_SERVINGS["C"][1],
            "TIER3_ARM_D": TEST_SERVINGS["D"],
            "TIER3_SERVINGS_RATIFIED": TEST_FINGERPRINT,
            "TIER3_SPEND_AUTHORIZED": (
                f"{runner.MAIN_CEILING:.2f}"),
            "TIER3_PILOT_AUTHORIZED": (
                f"{runner.PILOT_CEILING:.2f}"),
        }
        with runner._env_overrides(overrides), \
                runner._harness_pin_overrides(
                    TEST_SERVINGS["E"]):
            # The kill: three units run, the fourth is
            # left in flight, exactly as a process kill
            # leaves the record.
            killed = _run(runner.run_experiment(
                "main", results_path=path, stop_after=3,
                client_factory=wiring.client_factory,
                tool_dispatcher=wiring.tool_dispatcher,
                scenario_runner=scenario_runner,
                catalogue=catalogue))
            assert len(killed["records"]) == 3
            assert (len(wiring.clients)
                    + scenario_runner.runs) == 3
            in_flight = killed["left_in_flight"]
            assert in_flight is not None
            assert in_flight not in {
                (r["question_id"], r["repetition"], r["arm"])
                for r in killed["records"]}
            # The resume, on the same file.
            units_before = len(wiring.clients)
            e_runs_before = scenario_runner.runs
            resumed = _run(runner.run_experiment(
                "main", results_path=path,
                client_factory=wiring.client_factory,
                tool_dispatcher=wiring.tool_dispatcher,
                scenario_runner=scenario_runner,
                catalogue=catalogue))
        # Every unit recorded exactly once: nothing ran
        # twice, nothing was dropped. The two seams are
        # invoked once per unit that RUNS (arms A-D in
        # the client factory, arm E at the pipeline
        # boundary), so their total across both
        # invocations is the whole plan - the three
        # recorded units were skipped, not re-run.
        ran = ((len(wiring.clients) - units_before)
               + (scenario_runner.runs - e_runs_before))
        assert ran == 105 - 3
        assert (len(wiring.clients)
                + scenario_runner.runs) == 105
        keys = [(r["question_id"], r["repetition"], r["arm"])
                for r in resumed["records"]]
        assert len(keys) == 105
        assert len(set(keys)) == 105
        # The in-flight unit was charged its full ceiling
        # against the sweep as unreconciled liability, and
        # re-run (its record is in the file).
        assert resumed["resumed"] is True
        assert resumed["charged_liability"] == (
            runner.ARM_CEILINGS[in_flight[2]])
        assert resumed["in_flight"] == in_flight
        assert in_flight in keys
        # And the file the resume wrote carries no unit
        # in flight: the re-run completed, so a restart
        # reading the same file finds nothing to charge.
        header = json.loads(
            path.read_text(encoding="utf-8").splitlines()[0])
        reopened = runner.Tier3ResultsLog(path, config={
            "record": "header",
            "manifest_version": header["manifest_version"],
            "order_sha256": header["order_sha256"]})
        assert reopened.in_flight() is None
        # The charged liability is part of what the sweep
        # spent, and the summary says so.
        assert (f"${resumed['charged_liability']:.4f} of it "
                "the in-flight unit's liability charge"
                in resumed["summary"])
        # A restart with a different plan refuses: the
        # guard is the recorded manifest version and order
        # digest, not the file's existence.
        with pytest.raises(ValueError, match="resume only "
                           "the same plan"):
            runner.Tier3ResultsLog(path, config={
                "record": "header", "manifest_version": "tier3-1",
                "order_sha256": "0" * 64})
        # Break-proof (runner.py, run_experiment):
        #     charged = ARM_CEILINGS[in_flight[2]]
        #     -> charged = 0.0
        # FAILED ...::test_resume_skips_recorded_and_reruns_
        # the_in_flight - AssertionError: assert 0.0
        # == 0.2 : the in-flight unit was not charged
        # its ceiling, so an interruption would
        # understate what the run was on the hook for
        # by a whole unit's authorization.


# ── (f) Arm E's delivery rule ───────────────────────

class TestFArmEDelivery:
    def test_approved_not_shipped_is_never_delivered(
            self, fixture_rates):
        # A judge-approved draft that no completed terminal
        # shipped: the D38 watchdog's case.
        correct = _correct("Q3")
        script = _script(arm_e={
            "tier3_e_Q3_r1": runner._approved_not_shipped(
                correct)})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q3", 1, "E"), QUESTIONS, TEST_SERVINGS, None,
            scenario_runner=wiring.scenario_runner))
        assert result.status == "delivered"
        assert result.delivered_kind == "approved, not shipped"
        # The draft is scored - the answer the judge
        # approved is the one the scorer reads.
        assert result.answer == correct
        assert result.scorer["verdict"] == "PASS"
        # But the unit did not deliver: the property and
        # the record agree.
        assert result.delivered is False
        record = result.record()
        assert record["delivered"] is False
        # The measures: counted in approved_not_shipped,
        # never in delivered_correct.
        measures = runner.compute_measures([record])
        arm_e = measures["delivered_correctness_per_arm"]["E"]
        assert arm_e["approved_not_shipped"] == 1
        assert arm_e["delivered_correct"] == 0
        assert arm_e["planned"] == 1
        # Break-proof (runner.py, UnitResult.delivered):
        #     return self.arm != "E" or self.delivered_kind \
        #         == "shipped"
        #     -> return self.status == "delivered"
        # FAILED ...::test_approved_not_shipped_is_never_
        # delivered - AssertionError: assert True is
        # False, where True = UnitResult(question_id=
        # 'Q3', repetition=1, arm='E', status='delivered',
        # ...).delivered : a judge-approved draft that
        # never shipped counted as delivered - the
        # experiment would have measured the judge's
        # approval as the harness's delivery.

    def test_arm_e_delivers_what_the_pipeline_ships(
            self, fixture_rates):
        correct = _correct("Q2")
        script = _script(arm_e={
            "tier3_e_Q2_r1": runner._shipped(correct)})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q2", 1, "E"), QUESTIONS, TEST_SERVINGS, None,
            scenario_runner=wiring.scenario_runner))
        assert result.status == "delivered"
        assert result.delivered_kind == "shipped"
        assert result.delivered is True
        assert result.answer == correct
        # The pipeline run's own accounting is the unit's.
        assert result.calls == 14
        assert result.cost == 0.11
        assert result.scorer["verdict"] == "PASS"
        # And a run that ended without an answer is an
        # incomplete unit, counted in the denominator.
        script = _script(arm_e={
            "tier3_e_Q4_r1": runner._no_answer()})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q4", 1, "E"), QUESTIONS, TEST_SERVINGS, None,
            scenario_runner=wiring.scenario_runner))
        assert result.status == "incomplete"
        assert result.delivered_kind == "no answer"
        assert result.answer is None
        assert result.scorer is None
        # Break-proof (runner.py, _arm_e / answer_of use):
        #     answer, kind = answer_of(unit)
        #     -> answer, kind = unit["verdicts"]["implement"]
        #        ["summary"], "shipped"
        # FAILED ...::test_arm_e_delivers_what_the_pipeline_
        # ships - AssertionError: assert '' ==
        # 'no answer' : a run that ended without an
        # answer (no verdicts at all) carried no
        # delivery kind - the delivery reader was
        # replaced by a direct read of the terminal's
        # summary, so a run that never reached the
        # completed terminal would read as delivered -
        # the D49/D50 (3) rule the command registers.

    def test_arm_e_record_carries_the_pipeline_internals(
            self, fixture_rates):
        # R1: the unit record carries the scenario run's
        # internals - the plan's success criteria and
        # blockers, the run's final verdicts (review,
        # rework_review, domain_review, judges,
        # feasibility, triage), the build-loop iterations
        # (verdicts, dissent, findings), the escalation
        # verdict, the tokens by tier and the watchdog's
        # typed record.
        correct = _correct("Q2")
        outcome = runner._shipped(correct)
        outcome["verdicts"] = {
            "implement": {"summary": correct},
            "plan": {
                "ready": True,
                "plan": "implement the check",
                "success_criteria": [
                    "the readout zeroed before the first reading",
                    "the verdict stated with its value"],
                "blockers": []},
            "escalation": {
                "root_cause_analysis":
                    "the readout was never zeroed",
                "architectural_correction": None,
                "resolution_directive":
                    "zero the readout first",
                "requires_human": False},
            # The run's final verdicts, as the eval
            # traces carry them: the review findings
            # live in the review verdict, not in the
            # iterations.
            "review": {
                "ship": False,
                "findings": [
                    {"lens": "safety", "severity": "high",
                     "detail":
                         "the readout was never zeroed"}],
                "verdict": "one blocking finding"},
            "rework_review": {
                "routed_to": "review_rework_loop",
                "reason": "the review blocked"},
            "domain_review": {
                "concerns": ["the readout's zero"],
                "critical": True,
                "reviewers": 2},
            "judges": {
                "passed": False,
                "detail": "not agreed - validate is red",
                "dissenting": ["validate"],
                "judges": ["consistency", "coverage",
                           "implement", "validate"],
                "unchecked": []},
            "feasibility": {
                "feasibility_blockers": [],
                "considerations": ["the readout's zero"]},
            "triage": {
                "domains": ["control systems"],
                "risk": "high",
                "specialists": ["controls_engineer"],
                "unrecallable": False,
                "summary": "a firmware readout zeroing"}}
        outcome["iterations"] = [
            {"iteration": 1, "dissenting": ["validate"],
             "implement_summary": "first draft",
             "implement_green": False,
             "implement_red_cause":
                 "the readout was not zeroed",
             "validate_green": False,
             "validate_red_cause": "the verdict was missing",
             "validate_evidence": [],
             "domain_concerns": ["the readout's zero"]},
            {"iteration": 2, "dissenting": [],
             "implement_summary": correct,
             "implement_green": True,
             "validate_green": True}]
        outcome["tokens_by_tier"] = {
            "triage": {"prompt": 1200, "completion": 300},
            "engineering": {"prompt": 9000, "completion": 2100}}
        outcome["watchdog"] = {
            "armed": True, "budget_seconds": 1800.0,
            "fired": False, "rule": None, "node": None,
            "slow_calls": []}
        script = _script(arm_e={"tier3_e_Q2_r1": outcome})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q2", 1, "E"), QUESTIONS, TEST_SERVINGS, None,
            scenario_runner=wiring.scenario_runner))
        pipeline = result.record()["pipeline"]
        assert pipeline is not None
        # The plan's success criteria and blockers.
        assert pipeline["plan"] == {
            "ready": True,
            "success_criteria": [
                "the readout zeroed before the first reading",
                "the verdict stated with its value"],
            "blockers": []}
        # The escalation verdict.
        assert pipeline["escalation"][
            "resolution_directive"] == "zero the readout first"
        # The run's final verdicts, as the eval
        # traces carry them - the review findings live
        # in the review verdict, not in the iterations.
        assert pipeline["verdicts"]["review"] == {
            "ship": False,
            "findings": [
                {"lens": "safety", "severity": "high",
                 "detail": "the readout was never zeroed"}],
            "verdict": "one blocking finding"}
        assert pipeline["verdicts"]["rework_review"][
            "routed_to"] == "review_rework_loop"
        assert pipeline["verdicts"]["domain_review"][
            "concerns"] == ["the readout's zero"]
        assert pipeline["verdicts"]["judges"][
            "dissenting"] == ["validate"]
        assert pipeline["verdicts"]["feasibility"][
            "considerations"] == ["the readout's zero"]
        assert pipeline["verdicts"]["triage"][
            "risk"] == "high"
        # The iterations: verdicts, dissent, findings.
        assert pipeline["iterations"][0]["dissenting"] == \
            ["validate"]
        assert pipeline["iterations"][0]["implement_summary"] == \
            "first draft"
        assert pipeline["iterations"][0]["domain_concerns"] == \
            ["the readout's zero"]
        # The tokens by tier.
        assert pipeline["tokens_by_tier"]["engineering"] == \
            {"prompt": 9000, "completion": 2100}
        # The watchdog's typed record.
        assert pipeline["watchdog"]["budget_seconds"] == 1800.0
        # A run that never escalated carries no escalation
        # verdict, and a plan that never ran carries no
        # criteria: None, not an empty shell.
        script = _script(arm_e={
            "tier3_e_Q4_r1": runner._no_answer()})
        wiring = _Wiring(script, fixture_rates)
        result = _run(runner.run_unit(
            ("Q4", 1, "E"), QUESTIONS, TEST_SERVINGS, None,
            scenario_runner=wiring.scenario_runner))
        pipeline = result.record()["pipeline"]
        assert pipeline["plan"] is None
        assert pipeline["escalation"] is None
        # Nor did any of the final verdicts' nodes
        # run: None for each, not an empty shell.
        assert pipeline["verdicts"] == {
            "review": None, "rework_review": None,
            "domain_review": None, "judges": None,
            "feasibility": None, "triage": None}
        # Break-proof (runner.py, run_unit):
        #     result.pipeline = _pipeline_record(run)
        #     -> result.pipeline = None
        # FAILED tests/test_tier3_runner.py::TestFArmEDelivery::
        # test_arm_e_record_carries_the_pipeline_internals -
        # AssertionError: assert None is not None (line 1238):
        # the unit record dropped the scenario run's internals -
        # the plan's criteria and blockers, the iterations, the
        # escalation verdict, the tokens by tier and the watchdog
        # - so the record could no longer say why the pipeline
        # ended the way it did.
        # Break-proof (runner.py, _pipeline_record):
        #     name: verdicts.get(name) for name in (
        #     -> name: (None if name == "review"
        #               else verdicts.get(name))
        # FAILED tests/test_tier3_runner.py::TestFArmEDelivery::
        # test_arm_e_record_carries_the_pipeline_internals -
        # AssertionError: assert None == {'ship': False,
        # 'findings': [{'lens': 'safety', 'severity': 'high',
        # 'detail': 'the readout was never zeroed'}],
        # 'verdict': 'one blocking finding'}
        # (tests/test_tier3_runner.py:1347): the record
        # dropped the review verdict, so the review findings -
        # which live in the verdict, not in the iterations -
        # were lost with it.


# ── (g) The preflight ───────────────────────────────

def _entry(serving: str) -> dict[str, Any]:
    return {"id": serving}


class TestGThePreflight:
    def test_the_clean_lineup_passes(self):
        report = runner.run_preflight(
            TEST_SERVINGS, _fixture_catalogue())
        assert report.refusals == []
        assert report.reports == []

    def test_case_one_refuses_a_worst_case_above_the_ceiling(
            self):
        # Arm A's completion rate is high enough that one
        # call's worst case exceeds the arm's $0.10
        # ceiling: (prompt bytes + the template allowance)
        # x the prompt rate + max_tokens x the completion
        # rate, at the registered max_tokens.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["A"]:
                entry["pricing"] = {
                    "prompt": f"{FIXTURE_PROMPT_RATE}",
                    "completion": "0.001"}
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "arm A: the worst case of its 1-call sequence "
            "is $" in refusal
            and "above its per-unit ceiling $0.10" in refusal
            for refusal in report.refusals), report.refusals
        # Break-proof (runner.py, run_preflight, case 1):
        #     if worst > ceiling:
        #     -> if worst > ceiling * 1000:
        # FAILED ...::test_case_one_refuses_a_worst_case_
        # above_the_ceiling - AssertionError: assert
        # False, where False = any(... "arm A: the
        # worst case of its 1-call sequence is $" ...)
        # over refusals == [] : a call sequence whose
        # worst case exceeds the arm's per-unit ceiling
        # would have started, and the spend guard - not
        # the preflight - would have stopped it
        # mid-unit.

    def test_case_two_refuses_a_serving_without_tool_support(
            self):
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["B"]:
                entry["supported_parameters"] = [
                    "response_format", "max_tokens",
                    "temperature"]
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "arm B" in refusal
            and "does not list tool support" in refusal
            for refusal in report.refusals), report.refusals
        # The catalogue's blindness about supported_parameters
        # is a report, not a guess.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["B"]:
                del entry["supported_parameters"]
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "blind about" in note
            and "tool support is unverified" in note
            for note in report.reports), report.reports
        assert not any("tool support" in refusal
                       for refusal in report.refusals)
        # Break-proof (runner.py, run_preflight, case 2):
        #     elif "tools" not in supported:
        #     -> elif "tools" in supported:
        # FAILED ...::test_case_two_refuses_a_serving_
        # without_tool_support - AssertionError: assert
        # False, where False = any(... "does not list
        # tool support" ...) over refusals == [] : a
        # serving that cannot call tools would have run
        # arm B, and the tool treatment would have been
        # measured as a no-tool run.

    def test_case_three_refuses_a_context_window_too_small(
            self):
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["B"]:
                entry["context_length"] = 1000
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "arm B: the largest prompt" in refusal
            and "exceeds" in refusal
            and "context window of 1000" in refusal
            for refusal in report.refusals), report.refusals
        # Blindness about the context length is a report.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["B"]:
                del entry["context_length"]
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "blind about" in note
            and "capacity check could not run" in note
            for note in report.reports), report.reports
        # Break-proof (runner.py, run_preflight, case 3):
        #     elif prompt_bytes + REGISTERED_MAX_TOKENS \
            #         > context:
        #     -> elif prompt_bytes + REGISTERED_MAX_TOKENS \
            #         < context:
        # FAILED ...::test_case_three_refuses_a_context_
        # window_too_small - AssertionError: assert
        # False, where False = any(... "arm B: the
        # largest prompt" ...) over refusals == [] : an
        # arm B prompt larger than the serving's context
        # window would have been truncated at the
        # provider, and the unit would have measured
        # the truncation, not the treatment.

    def test_case_four_refuses_every_unpriced_serving(self):
        # A serving absent from the catalogue.
        servings = dict(TEST_SERVINGS)
        servings["A"] = "test/absent"
        report = runner.run_preflight(
            servings, _fixture_catalogue())
        assert any(
            "arm A: the serving 'test/absent' is not in "
            "the provider catalogue" in refusal
            for refusal in report.refusals), report.refusals
        # A catalogue entry that prices neither side of
        # the call.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["D"]:
                entry["pricing"] = {}
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "arm D: the serving test/arm-d has no catalogue "
            "price the guard can bound" in refusal
            for refusal in report.refusals), report.refusals
        # An entry carrying a charge the bound cannot
        # cover: a cache component priced above the
        # prompt rate, which the token-only bound
        # understates. The guard is blind for it
        # (D49: an unknown price is not free). A
        # per-request charge is not this case — the
        # bound adds it once per call — and neither
        # is a component priced at or below the rate
        # its side is charged at: the repair the PR
        # #152 review ordered made both bounded.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["C"][0]:
                entry["pricing"]["input_cache_read"] = \
                    f"{FIXTURE_PROMPT_RATE * 2}"
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "arm C: the serving test/arm-c-1 has no catalogue "
            "price the guard can bound" in refusal
            and "input_cache_read" in refusal
            for refusal in report.refusals), report.refusals
        # Arm E's tiers are covered by the same case: the
        # gate covers the standing pins.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["E"]["judge"]:
                entry["pricing"] = {}
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "arm E: the serving test/arm-e-judge has no "
            "catalogue price" in refusal
            for refusal in report.refusals), report.refusals
        # Break-proof (runner.py, run_preflight, case 4):
        #     for arm in ARMS:
        #         for serving in _arm_servings(arm, servings):
        #     -> for arm in ("A",):
        # FAILED ...::test_case_four_refuses_every_
        # unpriced_serving - AssertionError: assert
        # False, where False = any(... "arm D: the
        # serving test/arm-d has no catalogue price the
        # guard can bound" ...) over refusals == []
        # (and arm C's and arm E's the same) : an
        # unpriced serving outside arm A would have
        # run unrated - the guard blind, the preflight
        # silent.

    def test_case_five_refuses_max_tokens_over_the_endpoint_cap(
            self):
        # The owner's addition: an arm A-D call's
        # registered max_tokens exceeds the pinned
        # endpoint's max_completion_tokens - the client
        # does not clamp, so the call would fail at the
        # provider.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["A"]:
                entry["max_completion_tokens"] = 4000
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "arm A: the registered max_tokens 8000 exceeds "
            "test/arm-a's max_completion_tokens 4000" in refusal
            for refusal in report.refusals), report.refusals
        # Arm E's tiers are reported, not refused: arm E
        # runs under the guard as it ships.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["E"]["judge"]:
                entry["max_completion_tokens"] = 4000
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "arm E/judge: the standing cap" in note
            and "reported, not refused" in note
            for note in report.reports), report.reports
        assert not any("arm E" in refusal
                       for refusal in report.refusals)
        # The catalogue's blindness about the cap is a
        # report for both.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["B"]:
                del entry["max_completion_tokens"]
        report = runner.run_preflight(TEST_SERVINGS, catalogue)
        assert any(
            "blind about" in note
            and "could not be checked against it" in note
            for note in report.reports), report.reports
        # Break-proof (runner.py, run_preflight, the
        # owner's addition):
        #     elif REGISTERED_MAX_TOKENS > cap:
        #     -> elif REGISTERED_MAX_TOKENS < cap:
        # FAILED ...::test_case_five_refuses_max_tokens_
        # over_the_endpoint_cap - AssertionError: assert
        # False over refusals == ["arm C: the registered
        # max_tokens 8000 exceeds test/arm-c-1's
        # max_completion_tokens 32768 — ...", "arm D:
        # ... 32768 — ..."] : arm A's own refusal
        # (cap 4000) was gone, and arms whose endpoints
        # list 32768 were refused instead - a
        # registered max_tokens above the endpoint's cap
        # would have failed at the provider, mid-unit,
        # after the spend was committed.

    def test_the_arm_e_worst_case_table_states_its_figures(
            self):
        rows = runner.arm_e_worst_case(
            TEST_SERVINGS, _fixture_catalogue())
        assert len(rows) == len(runner.PIPELINE_TIERS)
        for row in rows:
            assert row["tier"] in runner.PIPELINE_TIERS
            assert row["cap"] > 0
            # The boundable rows carry the guard's own
            # formula at the catalogue's rates.
            assert "worst_case" in row
            assert row["unit_ceiling"] == runner.ARM_CEILINGS["E"]
            assert row["refusable_above_spend"] == (
                runner.ARM_CEILINGS["E"] - row["worst_case"])
            # The guard's formula, recomputed here: the
            # largest question the pipeline's entry point
            # carries, at the registered standing cap.
            expected = runner.worst_case_cost(
                FIXTURE_PROMPT_RATE, FIXTURE_COMPLETION_RATE,
                len(QUESTIONS[max(
                    QUESTIONS,
                    key=lambda qid: len(QUESTIONS[qid]["question"]))]["question"].encode("utf-8")),
                row["cap"])
            assert row["worst_case"] == pytest.approx(expected)
        # Break-proof (runner.py, arm_e_worst_case):
        #     worst = worst_case_cost(prompt_rate,
        #         completion_rate, prompt_bytes, cap)
        #     -> worst = worst_case_cost(prompt_rate,
        #         completion_rate, prompt_bytes, 1)
        # FAILED ...::test_the_arm_e_worst_case_table_
        # states_its_figures - AssertionError:
        # assert 0.00016109999999999999 ==
        # 0.0034376999999999997 ± 3.4e-09 : the
        # table's worst cases were computed at a
        # 1-token output instead of the tier's
        # standing cap, so the figures would have
        # understated every tier's worst case by the
        # cap they were meant to bound.


# ── (g2) The worst-case bound's own repair ──────────
#
# The bound covers what its own rates already charge: a
# variant suffix resolves to the base entry's price, the
# cache and reasoning components are bounded against the
# rates their sides are charged at, a flat per-request
# charge is added once per call, and the guard stays blind
# only for a component priced above the rate its side is
# charged at — or one the bound does not know.

# A lineup whose arm E/architecture serving is a variant
# endpoint: served (the per-model endpoint confirmed it)
# but priced by its base entry, the way the catalogue
# prices the ':exacto' servings the ratified lineup names.
VARIANT_SERVINGS = {
    "A": "test/arm-a",
    "B": "test/arm-a",
    "C": ["test/arm-c-1", "test/arm-c-2"],
    "D": "test/arm-d",
    "E": {tier: ("test/arm-e-architecture:exacto"
                 if tier == "architecture"
                 else f"test/arm-e-{tier}")
          for tier in runner.PIPELINE_TIERS},
}


def _variant_catalogue() -> list[dict[str, Any]]:
    """The fixture catalogue with the architecture tier's
    serving as a confirmed variant: the serving itself
    carries no pricing (the per-model endpoint confirms it
    is served and carries none), and its base entry, priced
    at the fixture's rates, is the entry that bounds it."""
    catalogue = _fixture_catalogue(VARIANT_SERVINGS)
    entries = {entry["id"]: entry for entry in catalogue}
    variant = entries["test/arm-e-architecture:exacto"]
    variant["pricing"] = {}
    variant["confirmed_served"] = True
    for parameter in ("context_length", "max_completion_tokens",
                      "supported_parameters"):
        variant.pop(parameter, None)
    catalogue.append({
        "id": "test/arm-e-architecture",
        "pricing": {"prompt": f"{FIXTURE_PROMPT_RATE}",
                    "completion": f"{FIXTURE_COMPLETION_RATE}"},
        "context_length": 200000,
        "max_completion_tokens": 32768,
        "supported_parameters": [
            "tools", "response_format", "max_tokens",
            "temperature"],
    })
    return catalogue


class TestG2TheWorstCaseBound:
    def test_a_variant_suffix_resolves_to_its_base_entry(self):
        rows = runner.arm_e_worst_case(
            VARIANT_SERVINGS, _variant_catalogue())
        (row,) = [row for row in rows
                  if row["tier"] == "architecture"]
        assert not row.get("unknown")
        # The base entry's rates, not a guess: the row
        # states which entry priced the serving.
        assert row["priced_as"] == "test/arm-e-architecture"
        assert row["prompt_rate"] == FIXTURE_PROMPT_RATE
        assert row["completion_rate"] == FIXTURE_COMPLETION_RATE
        assert row["per_request_charge"] == 0.0
        # The guard's formula, written out here rather than
        # recomputed through the function under test: the
        # largest question the pipeline's entry point
        # carries, the 512-byte chat-template allowance,
        # the fixture's rates and the tier's standing cap.
        prompt_bytes = len(QUESTIONS[max(
            QUESTIONS,
            key=lambda qid: len(QUESTIONS[qid]["question"]))]["question"].encode("utf-8"))
        expected = ((prompt_bytes + 512)
                    * FIXTURE_PROMPT_RATE
                    + row["cap"] * FIXTURE_COMPLETION_RATE)
        assert row["worst_case"] == pytest.approx(expected)
        # Break-proof (runner.py, _resolve_entry):
        #     if entry.get("pricing"):
        #         return entry
        # -> if True:
        #         return entry
        # FAILED ...::test_a_variant_suffix_resolves_to_
        # its_base_entry - AssertionError: assert not True,
        # where True = row.get('unknown') — the variant's
        # own (empty) entry priced the serving, so the table
        # reported it served but blind, and the preflight
        # refused it ("arm E: the serving
        # test/arm-e-architecture:exacto has no catalogue
        # price the guard can bound (served but not priced
        # in the catalogue ...)"), where the base entry's
        # published price is the known price the bound reads.

    def test_a_serving_the_catalogue_never_carried_stays_unlisted(
            self):
        # Resolution only borrows a price for an id the
        # catalogue actually carries: an id it never listed
        # and never confirmed is not in the catalogue, even
        # when its base model is priced.
        servings = dict(VARIANT_SERVINGS)
        servings["E"] = dict(VARIANT_SERVINGS["E"])
        servings["E"]["architecture"] = "test/never-listed:exacto"
        rows = runner.arm_e_worst_case(
            servings, _variant_catalogue())
        (row,) = [row for row in rows
                  if row["tier"] == "architecture"]
        assert row["unknown"]
        assert row["reason"] == "not in the provider catalogue"

    def test_a_per_request_charge_is_added_once_per_call(self):
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["E"]["search"]:
                entry["pricing"]["web_search"] = "0.005"
        rows = runner.arm_e_worst_case(TEST_SERVINGS, catalogue)
        (row,) = [row for row in rows
                  if row["tier"] == "search"]
        assert not row.get("unknown")
        assert row["per_request_charge"] == pytest.approx(0.005)
        # The guard's formula, written out here rather than
        # recomputed through the function under test: the
        # largest question the pipeline's entry point
        # carries, the 512-byte chat-template allowance,
        # the fixture's rates, the tier's standing cap,
        # and the per-request charge added once.
        prompt_bytes = len(QUESTIONS[max(
            QUESTIONS,
            key=lambda qid: len(QUESTIONS[qid]["question"]))]["question"].encode("utf-8"))
        expected = ((prompt_bytes + 512)
                    * FIXTURE_PROMPT_RATE
                    + row["cap"] * FIXTURE_COMPLETION_RATE
                    + 0.005)
        assert row["worst_case"] == pytest.approx(expected)
        # Break-proof (runner.py, worst_case_cost):
        #     + max_tokens * completion_rate
        #     + per_request_charge)
        # -> + max_tokens * completion_rate)
        # FAILED ...::test_a_per_request_charge_is_added_
        # once_per_call - AssertionError: Obtained
        # 0.0009608999999999999, Expected 0.0059609
        # ± 6.0e-09 : the table's worst case omitted the
        # per-request charge, so every call the search tier
        # makes would have been understated by the flat fee
        # the provider charges it.

    def test_the_components_the_bound_covers_are_bounded(
            self):
        # The cache components at (and below) the prompt
        # rate, reasoning at the completion rate, and the
        # modality components a text-only call never
        # carries: none of them unrates the serving.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["E"]["triage"]:
                entry["pricing"].update({
                    "input_cache_read": f"{FIXTURE_PROMPT_RATE}",
                    "input_cache_write": "0",
                    "internal_reasoning":
                        f"{FIXTURE_COMPLETION_RATE}",
                    "image": "0.00000075",
                    "audio": "0.00000075",
                    "input_audio_cache": "0.000000075"})
        rows = runner.arm_e_worst_case(TEST_SERVINGS, catalogue)
        (row,) = [row for row in rows
                  if row["tier"] == "triage"]
        assert not row.get("unknown")

    def test_a_component_priced_above_its_side_stays_blind(self):
        # A cache component priced above the prompt rate is
        # a charge the bound understates: the guard says so,
        # naming the component, rather than bounding it.
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["E"]["triage"]:
                entry["pricing"]["input_cache_read"] = \
                    f"{FIXTURE_PROMPT_RATE * 10}"
        rows = runner.arm_e_worst_case(TEST_SERVINGS, catalogue)
        (row,) = [row for row in rows
                  if row["tier"] == "triage"]
        assert row["unknown"]
        assert "input_cache_read" in row["reason"]
        # Break-proof (runner.py, _unboundable_reason):
        #     if prompt is None or rate > prompt:
        #         charges.append(key)
        # -> if False:
        #         charges.append(key)
        # FAILED ...::test_a_component_priced_above_its_
        # side_stays_blind (the row reported the
        # serving boundable) and
        # ...::test_the_two_instruments_apply_the_
        # same_test - AssertionError:
        # {'prompt': '1e-07', 'completion': '2e-07',
        # 'input_cache_read': '1e-06'} assert False
        # == True : a cache component priced ten times
        # the prompt rate was reported as bounded, the
        # two instruments disagreed on the same entry,
        # and the worst case would have understated
        # every cached-token charge the call can carry.

    def test_a_component_the_bound_does_not_know_stays_blind(
            self):
        catalogue = _fixture_catalogue()
        for entry in catalogue:
            if entry["id"] == TEST_SERVINGS["E"]["triage"]:
                entry["pricing"]["fine_tuning"] = "0.01"
        rows = runner.arm_e_worst_case(TEST_SERVINGS, catalogue)
        (row,) = [row for row in rows
                  if row["tier"] == "triage"]
        assert row["unknown"]
        assert "fine_tuning" in row["reason"]

    def test_the_preflight_prices_a_variant_through_its_base(
            self):
        report = runner.run_preflight(
            VARIANT_SERVINGS, _variant_catalogue())
        assert not any(
            "test/arm-e-architecture:exacto" in refusal
            for refusal in report.refusals), report.refusals

    def test_the_two_instruments_apply_the_same_test(self):
        # The preflight's classifier and the client's parse
        # are two copies of one ruling; a battery of catalog
        # shapes proves they still agree, missing sides
        # included (the client folds that check into its
        # parse, the preflight states it as its own reason).
        import autornd.routing.openrouter as _openrouter
        battery = [
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}"},
            {"prompt": "0", "completion": "0"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}",
             "web_search": "0.005"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}",
             "request": "0.01"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}",
             "input_cache_read": f"{FIXTURE_PROMPT_RATE}"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}",
             "input_cache_read": f"{FIXTURE_PROMPT_RATE * 10}"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}",
             "internal_reasoning":
                 f"{FIXTURE_COMPLETION_RATE}"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}",
             "internal_reasoning":
                 f"{FIXTURE_COMPLETION_RATE * 10}"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}",
             "image": "0.00000075", "audio": "0.00000075",
             "input_audio_cache": "0.000000075"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}",
             "fine_tuning": "0.01"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}",
             "web_search": "a price that does not parse"},
            {"prompt": f"{FIXTURE_PROMPT_RATE}",
             "completion": f"{FIXTURE_COMPLETION_RATE}",
             "input_cache_read": "0"},
        ]
        for pricing in battery:
            entry = {"id": "vendor/x", "pricing": dict(pricing)}
            preflight_blind = (
                runner._unboundable_reason(entry) is not None)
            sides_missing = ("prompt" not in pricing
                             or "completion" not in pricing)
            client_blind = (
                sides_missing
                or _openrouter._prices_what_the_guard_cannot_bound(
                    pricing))
            assert preflight_blind == client_blind, pricing


# ── (h) The recompute whitelist ─────────────────────

class TestHTheRecomputeWhitelist:
    def test_recompute_accepts_the_registered_grammar(self):
        assert runner.recompute("2 + 3 * 4")["value"] == 14.0
        # The written forms the questions and the models
        # use, translated before parsing.
        assert runner.recompute("2×3")["value"] == 6.0
        assert runner.recompute("12÷4")["value"] == 3.0
        assert runner.recompute("2^10")["value"] == 1024.0
        assert runner.recompute("−5 + 2")["value"] == -3.0
        # Parentheses, the constants, and the whitelisted
        # functions.
        assert runner.recompute(
            "(2.00 + 4.00) / (2.00 * 3.00)")["value"] == 1.0
        assert runner.recompute("pi")["value"] == math.pi
        assert runner.recompute("e")["value"] == math.e
        assert runner.recompute(
            "sqrt(16) + log10(100)")["value"] == 6.0
        assert runner.recompute(
            "min(3, 1, 2) + max(3, 1, 2)")["value"] == 4.0
        assert runner.recompute(
            "abs(-2) + sin(0) + cos(0) + tan(0)")["value"] == 3.0
        assert runner.recompute(
            "exp(0) + ln(1)")["value"] == 1.0
        # A result at the bound is accepted: 2^996 is the
        # largest power of two inside ±1e300.
        assert runner.recompute("2^996")["value"] == (
            2.0 ** 996)
        # Break-proof (runner.py, recompute):
        #     .replace("^", "**")
        #     -> removed (the power form no longer
        #        translated before parsing)
        # FAILED ...::test_recompute_accepts_the_registered_
        # grammar - KeyError: 'value' : the expression
        # '2^10' parsed as a bitwise XOR, which the
        # whitelisted grammar rejects - the typed
        # rejection carries no 'value', and the caret
        # form the questions and the models write was
        # rejected as outside the grammar.

    def test_recompute_rejects_what_the_whitelist_excludes(
            self):
        cases = (
            # A bare name outside the whitelist - the
            # escape hatch any eval would give.
            ("os", "a name outside the whitelist"),
            # A call that is not a bare name.
            ("__import__('os').system('echo pwned')",
             "an attribute call"),
            ("(lambda: 1)()",
             "a call whose function is not a bare name"),
            # A call outside the whitelist. The numeric
            # argument is what reaches the function table:
            # a non-numeric argument is rejected earlier,
            # by the constant check, so it does not prove
            # the function whitelist.
            ("open(1)", "a call outside the whitelist"),
            ("len(1)", "a call outside the whitelist"),
            ("open('/etc/passwd')",
             "a call whose argument is not a number"),
            # An oversized exponent and an overflowing
            # result.
            ("2^1001", "an exponent beyond the bound"),
            ("10^1000", "a result beyond the bound"),
            # Arithmetic the whitelist refuses.
            ("1/0", "division by zero"),
            # Non-numbers in the grammar's places.
            ("'a' + 'b'", "a string constant"),
            ("True", "a boolean constant"),
            # Keyword arguments, and syntax the grammar
            # does not hold.
            ("min(1, 2, x=3)", "keyword arguments"),
            ("2 @ 3", "not a parseable expression"),
            ("import os", "not a parseable expression"),
        )
        for expression, why in cases:
            result = runner.recompute(expression)
            assert result["ok"] is False, (
                f"{expression!r} ({why}) was accepted - "
                "the whitelist let it through")
            assert result["expression"] == expression
            assert result["error"], (
                f"{expression!r} was rejected without a "
                "typed error naming what is outside")
        # The rejection is a RESULT, not an exception: the
        # model sees the answer to its request either way -
        # including the power that overflows the float
        # range inside the exponent bound.
        for expression, _why in cases:
            try:
                runner.recompute(expression)
            except Exception as exc:      # pragma: no cover
                raise AssertionError(
                    f"{expression!r} raised {exc!r} instead "
                    "of returning a typed rejection")
        # Break-proof (runner.py, _eval_node, the call
        # branch):
        #     if node.func.id not in _ALLOWED_FUNCTIONS:
        #         raise RecomputeError(...)
        #     -> if False:
        # FAILED ...::test_recompute_rejects_what_the_
        # whitelist_excludes - KeyError: 'open', raised
        # at _ALLOWED_FUNCTIONS[node.func.id] in
        # _eval_node (evals/tier3/runner.py:1001) : the
        # call whitelist was disabled, so "open(1)"
        # reached the function table - the expression's
        # own text was one step from being executed as
        # code (hard rule 3).


# ── (i) The closed-world fetch ──────────────────────

class TestITheClosedWorldFetch:
    def test_fetch_answers_every_lookup_in_its_written_form(
            self):
        # Convention 28: the probe must have computed its
        # subject - an empty lookup set would pass vacuously.
        lookup_questions = []
        for question_id, question in QUESTIONS.items():
            citation = runner._citation_in(question["question"])
            if citation is None:
                continue
            lookup_questions.append((question_id, citation))
            result = runner.fetch_primary_source(citation)
            assert result["available"] is True, (
                f"{question_id}'s citation {citation!r} is "
                f"not in the archive: {result}")
            assert result["text"], (
                f"{question_id}'s archived text is empty")
            assert result["edition"] == "July 1, 2014"
            assert result["source"].endswith(".txt")
        # The frozen set holds lookup questions, and the
        # citations are the questions' own written forms -
        # with and without the '§', with and without the
        # paragraph, in the LaTeX-wrapped figure the
        # questions wrap their citations in.
        assert lookup_questions, (
            "no question in the frozen set carries a CFR "
            "citation - the probe set is empty")
        assert ("Q2", "29 CFR 1910.146(b)") in lookup_questions
        assert ("Q7", "29 CFR 1910.95") in lookup_questions
        assert ("Q12", "40 CFR 141.62(b)") in lookup_questions
        # The tool opens no socket: the suite's guard
        # (tests/conftest.py) refuses every non-loopback
        # socket and fails the offending test - this test
        # passing under the guard is the proof.
        # Break-proof (runner.py, fetch_primary_source):
        #     if path is None:
        #         return {"available": False, ...}
        #     -> if path is not None:
        # FAILED ...::test_fetch_answers_every_lookup_
        # question_in_its_written_form - AssertionError:
        # Q2's citation '29 CFR 1910.146(b)' is not in
        # the archive: {'available': False, 'citation':
        # '29 CFR 1910.146(b)', 'reason': '29 CFR
        # 1910.146 is not in the archived July 1, 2014
        # editions under .../evals/tier2/sources'} ;
        # assert False is True : the archived citations
        # were reported as not available, so arm B's
        # source tool would have answered every lookup
        # question with a typed refusal.

    def test_fetch_accepts_a_citation_copied_verbatim(
            self):
        # The review's defect, 2026-10-04: a model
        # that copies the citation exactly as the
        # question writes it - with the LaTeX '$'
        # wrappers wherever the question puts them -
        # must still resolve it. The questions wrap
        # each figure separately, so the three with
        # a paragraph inside the wrappers (Q2, Q12,
        # Q22) carry a trailing '$' after the
        # paragraph, which defeated the anchored
        # match and returned not-available.
        wrapped = re.compile(
            r"\$?\d+\$?\s+CFR\s+§?\s*\$?\d+"
            r"(?:\.\d+)*\$?(?:\([^)]*\))?\$?")
        verbatim = {}
        for question_id, question in QUESTIONS.items():
            found = wrapped.search(question["question"])
            if found:
                verbatim[question_id] = found.group(0)
        # Convention 28: the probe must have computed
        # its subject - an empty or partial set would
        # pass vacuously.
        assert set(verbatim) == {
            "Q2", "Q7", "Q12", "Q17", "Q22"}, (
            f"the frozen set carries other wrapped "
            f"citations: {sorted(verbatim)}")
        for question_id, citation in verbatim.items():
            assert "$" in citation, (
                f"{question_id}'s citation {citation!r} "
                f"carries no wrapper - not the verbatim "
                f"form the question writes")
            result = runner.fetch_primary_source(citation)
            assert result["available"] is True, (
                f"{question_id}'s verbatim citation "
                f"{citation!r} is not in the archive: "
                f"{result}")
            assert result["edition"] == "July 1, 2014"
            assert result["text"], (
                f"{question_id}'s archived text is empty")
        # Break-proof (runner.py, fetch_primary_source):
        #     match = _CITATION.match(
        #             (citation or "").replace("$", ""))
        #     -> match = _CITATION.match(citation or "")
        # FAILED ...::test_fetch_accepts_a_citation_
        # copied_verbatim - AssertionError: Q2's
        # verbatim citation '$29$ CFR § $1910.146(b)$'
        # is not in the archive: {'available': False,
        # 'citation': '$29$ CFR § $1910.146(b)$',
        # 'reason': 'not a CFR citation in a form the
        # questions write it'} : assert False is True

    def test_fetch_is_typed_not_available_outside_the_archive(
            self):
        for citation in (
                "29 CFR § 1910.1000(b)",   # a section not
                                            # archived
                "99 CFR § 1.1",             # a title not
                                            # archived
                "not a citation",
                "",
                "29 CFR",                    # no section
                "CFR 1910.146",              # no title number
                ):
            result = runner.fetch_primary_source(citation)
            assert result["available"] is False, (
                f"the citation {citation!r} was served from "
                "outside the archive")
            assert result["citation"] == citation
            assert result["reason"], (
                f"the citation {citation!r} was refused "
                "without a typed reason")
        # The archive is the whole world: a citation of an
        # archived section in a form the questions do not
        # write (the regex anchors the whole citation) is
        # not available either.
        result = runner.fetch_primary_source(
            "29 CFR 1910.146(b) and 40 CFR 141.62(b)")
        assert result["available"] is False
        # Break-proof (runner.py, fetch_primary_source):
        #     the pattern's "\s*$" end anchor
        #     -> "\s*" (the drafted ".match" -> ".search"
        #        is defeated by the "^" start anchor,
        #        which makes search behave as match)
        # FAILED ...::test_fetch_is_typed_not_available_
        # outside_the_archive - AssertionError:
        # assert True is False : the two-citation
        # prompt '29 CFR 1910.146(b) and 40 CFR
        # 141.62(b)' was served the first section's
        # text, silently dropping the second - the
        # tool would have answered a two-citation
        # prompt from the archive.


# ── (j) The reading sheet and the measures ──────────

def _record(question_id: str, repetition: int, arm: str,
            verdict: str, *, delivered: bool = True,
            delivered_kind: str = "",
            answer: str = "an answer") -> dict[str, Any]:
    return {
        "question_id": question_id, "repetition": repetition,
        "arm": arm,
        "status": "delivered" if delivered else "incomplete",
        "delivered": delivered,
        "delivered_kind": delivered_kind,
        "answer": answer,
        "scorer": {"verdict": verdict, "items": []},
        "cost": 0.01, "seconds": 1.0,
        "unreconciled_liability": 0.0,
    }


class TestJTheReadingSheetAndMeasures:
    def _records(self) -> list[dict[str, Any]]:
        # Two arms over two questions, three repetitions
        # each: arm A answers Q1 correctly twice and Q2
        # once; arm D answers both questions correctly
        # twice - enough for every measure to have shape.
        records = [
            _record("Q1", 1, "A", "PASS"),
            _record("Q1", 2, "A", "PASS"),
            _record("Q1", 3, "A", "FAIL"),
            _record("Q2", 1, "A", "PASS"),
            _record("Q2", 2, "A", "FAIL"),
            _record("Q2", 3, "A", "FAIL"),
            _record("Q1", 1, "D", "PASS"),
            _record("Q1", 2, "D", "FAIL"),
            _record("Q1", 3, "D", "PASS"),
            _record("Q2", 1, "D", "PASS"),
            _record("Q2", 2, "D", "PASS"),
            _record("Q2", 3, "D", "FAIL"),
        ]
        return records

    def test_the_sheet_carries_the_failures_and_no_arm_label(
            self, tmp_path):
        records = self._records()
        path = tmp_path / "sheet.json"
        sheet = runner.export_reading_sheet(
            records, QUESTIONS, scorer.KEYS, path,
            seed=runner.SEED)
        # The sheet is written where the readers read it.
        assert path.exists()
        # Every scorer FAIL is on the sheet.
        fails = [r for r in records
                 if r["scorer"]["verdict"] == "FAIL"]
        assert len(fails) == 5
        fail_entries = [entry for entry in sheet["entries"]
                        if entry["scorer_verdict"] == "FAIL"]
        assert len(fail_entries) == 5
        # A seeded sample of ten PASSes per arm (here:
        # every PASS - three for arm A, four for arm
        # D), in a seeded order.
        assert sheet["sample_per_arm"] == 10
        pass_entries = [entry for entry in sheet["entries"]
                        if entry["scorer_verdict"] == "PASS"]
        assert len(pass_entries) == 7
        assert len(sheet["entries"]) == 12
        # The readers see the question, the answer and the
        # key's required items - and no arm label: the
        # readings are blind to the treatment.
        for entry in sheet["entries"]:
            assert "arm" not in entry
            assert entry["question"] == (
                QUESTIONS[entry["question_id"]]["question"])
            assert entry["required_items"] == (
                next(k["required_items"] for k in scorer.KEYS
                     if k["id"] == entry["question_id"]))
            assert entry["reading_1"] is None
            assert entry["reading_2"] is None
        # The seeded order is reproducible.
        again = runner.export_reading_sheet(
            records, QUESTIONS, scorer.KEYS,
            tmp_path / "sheet-again.json", seed=runner.SEED)
        assert ([entry["question_id"]
                 for entry in again["entries"]]
                == [entry["question_id"]
                    for entry in sheet["entries"]])
        # A different seed orders the sheet differently.
        other = runner.export_reading_sheet(
            records, QUESTIONS, scorer.KEYS,
            tmp_path / "sheet-other.json",
            seed=runner.SEED + 1)
        assert ([entry["question_id"]
                 for entry in other["entries"]]
                != [entry["question_id"]
                    for entry in sheet["entries"]])
        # Break-proof (runner.py, export_reading_sheet):
        #     sheet_entries.append({...  "scorer_verdict":
        #         (record.get("scorer") or {}).get("verdict"),
        #     -> "scorer_verdict": "PASS",
        # FAILED ...::test_the_sheet_carries_the_failures_
        # and_no_arm_label - AssertionError:
        # assert 0 == 5, where 0 = len([]) : the
        # sheet carried no FAIL entries - the two hand
        # readings that are the primary measure would
        # have had nothing to read.

    def test_the_merge_records_agreement_disagreement_and_unread(
            self, tmp_path):
        records = self._records()
        sheet = runner.export_reading_sheet(
            records, QUESTIONS, scorer.KEYS,
            tmp_path / "sheet.json", seed=runner.SEED)
        entries = sheet["entries"]
        # Reader 1 reads what the scorer read; reader 2
        # agrees except on one entry, read the other way.
        reader_1 = {entry["entry"]: entry["scorer_verdict"]
                    for entry in entries}
        reader_2 = dict(reader_1)
        flipped = entries[1]["entry"]
        reader_2[flipped] = ("PASS" if reader_2[flipped] == "FAIL"
                             else "FAIL")
        merged = runner.merge_readings(sheet, reader_1, reader_2)
        # The agreements are merged; the one disagreement
        # is listed with both readings and no resolution -
        # a disagreement is reported, never settled by
        # editing the scorer inside the run that found it.
        assert len(merged["merged"]) == len(entries) - 1
        assert len(merged["disagreements"]) == 1
        assert merged["disagreements"][0]["entry"] == flipped
        assert merged["disagreements"][0]["reading_1"] == (
            reader_1[flipped])
        assert merged["disagreements"][0]["reading_2"] == (
            reader_2[flipped])
        assert merged["disagreements"][0]["resolution"] is None
        # An entry neither reader read is unread, not
        # merged.
        partial = dict(reader_1)
        del partial[entries[0]["entry"]]
        merged = runner.merge_readings(sheet, partial, reader_2)
        assert entries[0]["entry"] in merged["unread"]
        assert entries[0]["entry"] not in merged["merged"]
        # Break-proof (runner.py, merge_readings):
        #     if first == second:
        #         merged[index] = first
        #     else:
        #         disagreements.append({...})
        #     -> merged[index] = first (the disagreement
        #        branch deleted - every entry merges)
        # FAILED ...::test_the_merge_records_agreement_
        # disagreement_and_unread - AssertionError:
        # assert 12 == (12 - 1), where 12 = len({...})
        # : the readers' disagreement was merged away
        # instead of listed - the primary measure would
        # have hidden the one reading the two readers
        # split on.

    def test_the_measures_are_computed_both_ways(self):
        records = self._records()
        scorer_only = runner.compute_measures(records)
        # The scorer-only measures: the fractions of the
        # planned units, the repeat-outcome distribution,
        # the paired wins and losses, the totals.
        correctness = scorer_only["delivered_correctness_per_arm"]
        assert correctness["A"] == {
            "delivered_correct": 3, "planned": 6,
            "fraction": 0.5, "not_delivered": 0,
            "approved_not_shipped": 0}
        assert correctness["D"]["delivered_correct"] == 4
        # The repeat outcomes: Q1 is 2/3 for arm A, 2/3
        # for arm D; Q2 is 1/3 for A, 2/3 for D.
        assert scorer_only["per_question_repeat_outcomes"][
            "A"] == {"2/3": 1, "1/3": 1}
        assert scorer_only["per_question_repeat_outcomes"][
            "D"] == {"2/3": 2}
        # Paired against A: D wins Q1 (2 > 2 is a tie...
        # D wins Q2: 2 > 1), ties Q1, and the paired
        # counts are wins 1, losses 0, ties 1.
        paired = scorer_only["paired_wins_and_losses_against_A"]
        assert paired["D"] == {"wins": 1, "losses": 0,
                               "ties": 1}
        # And against D (the strong reference): A loses
        # Q2, ties Q1.
        against_d = scorer_only["comparison_with_D"]
        assert against_d["A"] == {"wins": 0, "losses": 1,
                                  "ties": 1}
        # The totals include every failure: the cost and
        # the latency of all twelve units, by status.
        totals = scorer_only["total_cost_and_latency_including_failures"]
        assert totals["units"] == 12
        assert totals["total_cost"] == pytest.approx(0.12)
        assert totals["by_status"] == {"delivered": 12}
        # Now the readers' verdicts: reader 2 read arm A's
        # Q1 third repetition (a scorer FAIL) as PASS. The
        # measures computed with the readings differ from
        # the scorer-only measures exactly where a reader
        # read - and the two are reported side by side.
        readings = {("Q1", 3, "A"): "PASS"}
        read = runner.compute_measures(records, readings)
        assert read["delivered_correctness_per_arm"]["A"][
            "delivered_correct"] == 4
        assert read["per_question_repeat_outcomes"]["A"] == (
            {"3/3": 1, "1/3": 1})
        # The paired measures move with the reading: arm
        # A now answers Q1 three times to arm D's two, so
        # the pairing flips on Q1 and holds on Q2.
        assert read["paired_wins_and_losses_against_A"][
            "D"] == {"wins": 1, "losses": 1, "ties": 0}
        assert read["comparison_with_D"]["A"] == {
            "wins": 1, "losses": 1, "ties": 0}
        # And a reading that disagrees with the scorer
        # moves the other way: a PASS read as FAIL.
        readings = {("Q1", 1, "A"): "FAIL"}
        read = runner.compute_measures(records, readings)
        assert read["delivered_correctness_per_arm"]["A"][
            "delivered_correct"] == 2
        # An unscored unit is not a pass either way: a
        # reading cannot rescue a failure class.
        incomplete = dict(_record("Q1", 1, "A", "FAIL",
                                  delivered=False))
        incomplete["status"] = "deadline"
        read = runner.compute_measures(
            [incomplete], {("Q1", 1, "A"): "PASS"})
        assert read["delivered_correctness_per_arm"]["A"][
            "delivered_correct"] == 0
        # Break-proof (runner.py, compute_measures):
        #     if readings and key in readings:
        #         return readings[key]
        #     -> if False:
        #        return readings[key]
        # (the readings branch removed)
        # FAILED ...::test_the_measures_are_computed_both_
        # ways - AssertionError: assert 3 == 4 : the
        # measures with the readers' verdicts were
        # identical to the scorer-only measures - the
        # two hand readings the ruling makes the
        # primary measure never reached the measures
        # at all.
