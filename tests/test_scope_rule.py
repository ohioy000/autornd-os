"""Ruling D43: the request sets the scope (ARCH-20261001-105).

Provider-free, through the real prompt builders: run_plan and run_implement
are called with the billing double, and the prompt each sends is read off
the call. The plan prompt carries the scope rule after D36's four rules,
whose text is pinned by a hash taken before the change (D36 is
owner-supplied and not a word of it may move). The implement prompt carries
the scope sentence.
"""

from __future__ import annotations

import hashlib

from autornd.engine import phases
from autornd.models.verdicts import PlanVerdict, TriageVerdict
from autornd.specialists.registry import get_specialists
from tests.conftest import make_mock_client

# sha256 of D36's block, from "Rules for the plan (each measured
# 2026-09-30, ..." up to "The success criteria are the most important
# thing you produce.", taken from main 81da1e0 before D43.
D36_SHA256 = "5bd19bc0cfb39888b969bd65d10134fb0638446ecb8140b2aa114929dceb0928"
D36_START = "Rules for the plan (each measured 2026-09-30, each a loop-killer when broken):"
D36_END = "The success criteria are the most important thing you produce."
SCOPE_RULE = (
    "Scope (Ruling D43): the request sets the scope. Every success criterion must\n"
    "test something the request asks for: an output, figure, constraint, format or\n"
    "verdict the request states, or a fact the grounding supplies to answer it. A\n"
    "criterion may not add specifics the request did not ask for, such as component\n"
    "values, part numbers, presentation layout, or the exact form of a derivation.\n"
    "The four rules above govern how you reason the plan; they do not add to what\n"
    "the answer must contain.")
IMPLEMENT_SENTENCE = ("Answer the request, and include the plan's falsifiers, kill "
                      "triggers or assumption tables only if the request asks for them.")

TRIAGE = TriageVerdict(domains=["electrical"], risk="low",
                       specialists=["hardware_engineer"], summary="Logic")
PLAN = PlanVerdict(ready=True, plan="OR the doors, AND with the brake.", blockers=[],
                   success_criteria=["The answer names an OR and an AND gate"])
RESPONSES = {"default": {"ready": True, "plan": "p", "blockers": [],
                         "success_criteria": ["c"], "done": True, "green": True,
                         "red_cause": None, "summary": "s"}}


async def _plan_prompt() -> str:
    client = make_mock_client(RESPONSES)
    await phases.run_plan(client, "Describe a logic circuit.", TRIAGE,
                          get_specialists(["hardware_engineer"]), context="")
    return client.chat_json.await_args.kwargs.get("user_message") or \
        client.chat_json.await_args.args[2]


async def _implement_prompt() -> str:
    client = make_mock_client(RESPONSES)
    await phases.run_implement(client, "Describe a logic circuit.", PLAN,
                               get_specialists(["hardware_engineer"]), iteration=1,
                               context="")
    return client.chat_json.await_args.kwargs.get("user_message") or \
        client.chat_json.await_args.args[2]


class TestThePlanPromptCarriesTheScopeRule:
    async def test_the_rule_is_present_after_d36(self):
        prompt = await _plan_prompt()
        assert SCOPE_RULE in prompt
        assert prompt.index(D36_START) < prompt.index(SCOPE_RULE)

    async def test_d36_is_byte_identical(self):
        prompt = await _plan_prompt()
        block = prompt[prompt.index(D36_START):prompt.index(D36_END)]
        assert hashlib.sha256(block.encode()).hexdigest() == D36_SHA256


class TestTheImplementPromptCarriesTheScopeSentence:
    async def test_the_sentence_is_present(self):
        assert IMPLEMENT_SENTENCE in await _implement_prompt()
